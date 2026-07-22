<template>
  <div
    class="uic"
    :class="{ 'is-done': record.collected, 'is-error': !!record.error || phase === 'photo_fail', 'is-uploading': phase === 'uploading' }"
    :data-testid="`uic-${itemKey}`"
  >
    <div class="uic__head">
      <div class="uic__title">
        {{ t(item.labelKey) }}
        <span v-if="item.optional" class="uic__optional">{{ t('wizard.optional_badge') }}</span>
      </div>
      <div v-if="record.collected && !record.error" class="uic__check">
        <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
          <path d="M3 8 L7 12 L13 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    </div>
    <p class="uic__hint">{{ t(item.hintKey, hintParams) }}</p>
    <!-- W59: 文件限制 — 用户上传前就知道支持什么、多大,免得选错浪费一次请求 -->
    <div class="uic__constraints" data-testid="uic-constraints">
      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 8v4M12 16h.01"/>
      </svg>
      <span>{{ t('wizard.file_constraints', { types: 'JPG / PNG / WebP / PDF', size: '10MB' }) }}</span>
    </div>

    <!-- idle: 选文件 or 摄像头拍摄 -->
    <div v-if="!record.collected && phase === 'idle'" class="uic__actions">
      <button class="uic__btn uic__btn--primary" data-testid="uic-pick-file" @click="pickFile">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 16V4M7 9l5-5 5 5" />
          <path d="M5 15v4h14v-4" />
        </svg>
        {{ t('wizard.pick_file') }}
      </button>
      <input ref="fileInput" type="file" :accept="isPhoto ? 'image/jpeg,image/png,image/webp' : 'image/jpeg,image/png,image/webp,application/pdf'" style="display:none" @change="onFilePicked" />
    </div>

    <!-- photo check failed: offer Htex photo toolbox -->
    <div v-else-if="phase === 'photo_fail'" class="uic__photo-fail" data-testid="uic-photo-fail">
      <div v-if="pendingPreviewUrl" class="uic__photo-fail-preview">
        <img :src="pendingPreviewUrl" alt="" />
      </div>
      <div class="uic__photo-fail-title">{{ t('wizard.photo_toolbox.fail_title') }}</div>
      <ul v-if="photoFailReasons.length" class="uic__photo-fail-list">
        <li v-for="(reason, i) in photoFailReasons" :key="i">{{ reason }}</li>
      </ul>
      <p class="uic__photo-fail-hint">{{ t('wizard.photo_toolbox.fail_hint') }}</p>
      <div class="uic__actions">
        <button
          type="button"
          class="uic__btn uic__btn--primary"
          data-testid="uic-open-toolbox"
          @click="openToolbox"
        >
          {{ t('wizard.photo_toolbox.open_cta') }}
        </button>
        <button
          type="button"
          class="uic__btn uic__btn--ghost"
          data-testid="uic-skip-toolbox"
          @click="skipToolboxUpload"
        >
          {{ t('wizard.photo_toolbox.skip_original') }}
        </button>
        <button type="button" class="uic__btn uic__btn--ghost" data-testid="uic-photo-repick" @click="clearPhotoFail">
          {{ t('wizard.photo_toolbox.repick') }}
        </button>
      </div>
    </div>

    <!-- camera capture -->
    <div v-else-if="phase === 'camera'" class="uic__camera">
      <video ref="videoEl" class="uic__video" autoplay muted playsinline />
      <div class="uic__camera-actions">
        <button class="uic__btn uic__btn--ghost" @click="cancelCamera">{{ t('wizard.camera_cancel') }}</button>
        <button class="uic__btn uic__btn--primary" data-testid="uic-snap" @click="capture">{{ t('wizard.camera_capture') }}</button>
      </div>
    </div>

    <!-- uploading -->
    <div v-if="phase === 'uploading'" class="uic__progress">
      <div class="uic__progress-bar"><div class="uic__progress-fill" :style="{ width: progress + '%' }" /></div>
      <div class="uic__progress-text">{{ progress < 100 ? t('wizard.uploading') : t('wizard.recognizing') }}</div>
    </div>

    <!-- done -->
    <div v-if="record.collected && phase !== 'uploading' && !record.error" class="uic__done">
      <button type="button" class="uic__uploaded-state" disabled>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 16V4M7 9l5-5 5 5" />
          <path d="M5 15v4h14v-4" />
        </svg>
        {{ t('wizard.uploaded') }}
      </button>
      <div class="uic__file">
        <button
          v-if="record.thumbUrl || record.fileUrl"
          type="button"
          class="uic__thumb-btn"
          data-testid="uic-thumb"
          :title="t('wizard.preview_title')"
          @click="openPreview"
        >
          <img v-if="record.thumbUrl" :src="record.thumbUrl" alt="" class="uic__thumb" />
          <span v-else-if="record.fileUrl" class="uic__thumb uic__thumb--fallback">📄</span>
          <span v-else class="uic__thumb uic__thumb--fallback">📄</span>
        </button>
        <span v-else class="uic__thumb uic__thumb--fallback">📄</span>
        <span class="uic__filename">{{ record.fileName }}</span>
        <span class="uic__filetype" v-if="record.fileType">{{ fileTypeBadge }}</span>
      </div>

      <!-- W62: 卡内所有非阻断性提示合并到一个黄框容器内,逐行展示:
           - isBlurry(图片模糊)
           - !isComplete(证件边缘被裁切)
           - record.photoWarnings(证件照片客户端预检警告,仅 photo item)
           - inlineIssues(visa_diagnoser 给本 item 的 issue 列表,由父 MaterialWizard 传入)
           原来这些各占一个 div,现在并到一个 .uic__warn-box 里,卡片下方不再重复堆块。 -->
      <div
        v-if="hasInlineWarnings"
        class="uic__warn uic__warn--box"
        data-testid="uic-warn-box"
      >
        <div v-if="record.isBlurry" class="uic__warn-line">
          <span class="uic__warn-icon" aria-hidden="true">⚠️</span>
          <span class="uic__warn-text">{{ t('wizard.warn_blurry') }}</span>
        </div>
        <div v-if="!record.isComplete" class="uic__warn-line">
          <span class="uic__warn-icon" aria-hidden="true">⚠️</span>
          <span class="uic__warn-text">{{ t('wizard.warn_incomplete') }}</span>
        </div>
        <template v-if="itemKey === 'photo' && record.photoWarnings?.length">
          <div v-for="(w, wi) in record.photoWarnings" :key="`pw-${wi}`" class="uic__warn-line">
            <span class="uic__warn-icon" aria-hidden="true">⚠️</span>
            <span class="uic__warn-text">{{ w }}</span>
          </div>
        </template>
      </div>

      <!-- W63+ 银行流水非阻断性审核提示 (itemKey=bank_statement 才显示) -->
      <div
        v-if="itemKey === 'bank_statement' && record.bankAnalysis?.rules?.length"
        class="uic__warn uic__warn--box"
        :data-testid="`uic-bank-review-${itemKey}`"
      >
        <div
          v-for="rule in record.bankAnalysis.rules"
          :key="rule.code"
          class="uic__warn-line"
          :class="`is-${ruleSeverityClass(rule.severity)}`"
          :data-testid="`uic-bank-rule-${rule.code}`"
        >
          <span class="uic__warn-icon" aria-hidden="true">{{ ruleSeverityIcon(rule.severity) }}</span>
          <span class="uic__warn-text">
            <b>{{ t(`bank_review.title_${rule.code}`) }}</b>
            · {{ t(`bank_review.detail_${rule.code}`, rule.suggestion_params || {}) }}
          </span>
        </div>
      </div>
      <div v-if="passportPreview" class="uic__ocr-preview">
        <span>{{ passportPreview.name }}</span>
        <span>{{ passportPreview.no }}</span>
        <span>{{ passportPreview.expiry }}</span>
      </div>

      <button class="uic__reupload" data-testid="uic-reupload" @click="reupload">{{ t('wizard.reupload') }}</button>
    </div>

    <!-- error (generic upload errors; photo_fail has its own panel) -->
    <div v-if="record.error && phase !== 'photo_fail'" class="uic__error" data-testid="uic-error">{{ record.error }}</div>

    <PhotoToolboxModal
      :open="toolboxOpen"
      :file="pendingPhotoFile"
      :country-code="countryCode"
      @confirm="onToolboxConfirm"
      @cancel="toolboxOpen = false"
    />

    <!-- Lightbox: 点击缩略图弹出,按 fileType 选 <img> 或 <iframe> 渲染 -->
    <Teleport to="body">
      <div
        v-if="previewOpen"
        class="uic-lightbox"
        role="dialog"
        aria-modal="true"
        :aria-label="t('wizard.preview_title')"
        data-testid="uic-lightbox"
        @click.self="closePreview"
      >
        <div class="uic-lightbox__panel">
          <div class="uic-lightbox__bar">
            <span class="uic-lightbox__name">{{ record.fileName }}</span>
            <span class="uic-lightbox__type">{{ fileTypeBadge }}</span>
            <button
              type="button"
              class="uic-lightbox__close"
              data-testid="uic-lightbox-close"
              :aria-label="t('wizard.preview_close')"
              @click="closePreview"
            >×</button>
          </div>
          <div class="uic-lightbox__body">
            <img
              v-if="isImage"
              :src="record.fileUrl || record.thumbUrl"
              :alt="record.fileName"
              class="uic-lightbox__img"
            />
            <iframe
              v-else-if="isPdf && (record.fileUrl || record.thumbUrl)"
              :src="record.fileUrl || record.thumbUrl"
              class="uic-lightbox__pdf"
              :title="record.fileName"
            />
            <div v-else class="uic-lightbox__fallback">
              <div class="uic-lightbox__fallback-icon">📄</div>
              <div class="uic-lightbox__fallback-name">{{ record.fileName }}</div>
              <div class="uic-lightbox__fallback-hint">{{ t('wizard.preview_unsupported') }}</div>
              <a
                v-if="record.fileUrl || record.thumbUrl"
                :href="record.fileUrl || record.thumbUrl"
                :download="record.fileName"
                target="_blank"
                rel="noopener"
                class="uic-lightbox__fallback-btn"
              >{{ t('wizard.preview_download') }}</a>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <SensitiveDataConsent
      :open="consentOpen"
      @accept="onConsentAccept"
      @cancel="onConsentCancel"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import SensitiveDataConsent from '@/components/SensitiveDataConsent.vue'
import PhotoToolboxModal from '@/components/PhotoToolboxModal.vue'

const { t, locale } = useI18n()

const props = defineProps({
  itemKey: { type: String, required: true },
  item: { type: Object, required: true },
  record: { type: Object, required: true },
  uploadFn: { type: Function, required: true }, // (file, onProgress) => Promise
  countryCode: { type: String, default: '' },
  // W62: visa_diagnoser 给本 item 的 issue 列表(由父 MaterialWizard 按 itemKey 过滤后传过来)。
  // 卡内黄框统一展示:record.isBlurry + record.isComplete + record.photoWarnings + inlineIssues,
  // 不再在卡下 mw-issues 块重复堆出独立块。
  inlineIssues: { type: Array, default: () => [] },
})

// W45 fix: bank-statement / insurance hints used to hardcode "¥50,000" which
// looked wrong on the en-US locale with US/GB/Schengen destinations. Map the
// destination country to the local currency symbol (or the conventional code
// in zh-CN / vi-VN) and inject it as {cur} into the i18n string.
// W46: extend coverage — VN/ID/TH/KR/IN now route to their local currency
// (IDR/VND/THB/KRW/INR) instead of falling back to ¥, and {amount} is
// looked up per (item, country) so that "5万元" becomes "US$7,000" /
// "Rp 100.000.000" / etc.
// W48: also render a "local-currency note" inside the parentheses — the main
// {cur}{amount} stays anchored to the destination country's currency (US =
// $7,000 for a US visa), but the parenthetical is reformatted into the
// *user's* familiar currency so vi users see "≈ 175.000.000 ₫" instead of
// "≈ ¥50.000 CNY" (which most vi users can't relate to).
//
// Conversion approach: we don't call an FX API. We pre-compute each locale's
// equivalent using the same CNY anchor used by the old `bank_cny_note` (≈
// 50,000 CNY for the US bank-statement threshold). The exact rate doesn't
// matter — these are "order-of-magnitude" hints to help the user feel "yes
// my savings are in the right ballpark" — they will still read the formal
// amount on the destination side ({cur}{amount}).
const CURRENCY_BY_COUNTRY = {
  // 美元区
  US: '$', CA: 'CA$', AU: 'A$', NZ: 'NZ$', SG: 'S$',
  // 欧洲
  GB: '£',
  // 申根成员国共用欧元
  AT: '€', BE: '€', HR: '€', CZ: '€', DK: '€', EE: '€', FI: '€', FR: '€',
  DE: '€', GR: '€', HU: '€', IS: '€', IT: '€', LV: '€', LI: '€', LT: '€',
  LU: '€', MT: '€', NL: '€', NO: '€', PL: '€', PT: '€', SK: '€', SI: '€',
  ES: '€', SE: '€',
  // 亚洲
  JP: '¥',     // JPY
  CN: '¥',     // CNY（与 JPY 符号相同，靠 amount 区分）
  KR: '₩',
  TH: '฿',
  IN: '₹',
  VN: '₫',
  ID: 'Rp',
}
function currencyFor(cc) {
  return CURRENCY_BY_COUNTRY[cc] || '¥'
}

// 各目的地国家的"银行流水建议余额 / 保险保额"下限（当地币种，业内常用值）。
// 按 itemKey + countryCode 查表；查不到时退回 CNY 兜底。
// 数值用 number 类型，i18n 字符串里 {amount} 会自动 toLocaleString 出千分位。
const AMOUNT_TABLE = {
  bank_statement: {
    US: 7000, CA: 10000, AU: 10000, NZ: 10000, SG: 10000,
    GB: 5500,
    AT: 6500, BE: 6500, HR: 6500, CZ: 6500, DK: 6500, EE: 6500, FI: 6500,
    FR: 6500, DE: 6500, GR: 6500, HU: 6500, IS: 6500, IT: 6500, LV: 6500,
    LI: 6500, LT: 6500, LU: 6500, MT: 6500, NL: 6500, NO: 6500, PL: 6500,
    PT: 6500, SK: 6500, SI: 6500, ES: 6500, SE: 6500,
    JP: 1000000, KR: 10000000, TH: 200000, VN: 150000000, ID: 100000000,
    IN: 500000, CN: 50000,
  },
  insurance: {
    US: 50000, CA: 50000, AU: 50000, NZ: 50000, SG: 30000,
    GB: 30000,
    // 申根法定下限 3 万欧元
    AT: 30000, BE: 30000, HR: 30000, CZ: 30000, DK: 30000, EE: 30000,
    FI: 30000, FR: 30000, DE: 30000, GR: 30000, HU: 30000, IS: 30000,
    IT: 30000, LV: 30000, LI: 30000, LT: 30000, LU: 30000, MT: 30000,
    NL: 30000, NO: 30000, PL: 30000, PT: 30000, SK: 30000, SI: 30000,
    ES: 30000, SE: 30000,
    JP: 5000000, KR: 30000000, TH: 1000000, VN: 500000000, ID: 500000000,
    IN: 3000000, CN: 300000,
  },
}
function amountFor(itemKey, countryCode) {
  const cc = countryCode || 'CN'
  const table = AMOUNT_TABLE[itemKey]
  if (!table) return '50,000'
  const n = table[cc] != null ? table[cc] : table.CN
  // 按当前 i18n locale 输出千分位: en/zh 用逗号, id/vi 用点号
  return n.toLocaleString(locale.value || 'en-US')
}

// ---------------------------------------------------------------------------
// Local-currency note — W48.
// Convert the destination-country {amount} into the user's familiar currency
// (the i18n locale) for the parenthetical hint. We use a static CNY anchor
// (50,000 CNY for the US bank-statement threshold) and cross-rate it to
// every other locale at known ratios. All numbers below are conservative
// "good enough" approximations; see comment block above for rationale.
//
// key format: `${itemKey}__${cc}`  →  { locale: amountInThatLocale, ... }
// Each `amountInThatLocale` is a plain Number; we still apply toLocaleString
// downstream so thousands separators match the locale.
// ---------------------------------------------------------------------------
const LOCAL_NOTE_TABLE = {
  // US bank_statement $7,000 ≈ ¥50,000 CNY ≈ 175,000,000 VND ≈ 112,000,000 IDR
  // For other countries we cross-rate from the destination {amount} through
  // CNY so the conversion stays internally consistent.
  bank_statement: {
    US: {
      'zh-CN': 50000, 'zh': 50000,
      'en': 7000, 'en-US': 7000,
      'vi': 175000000, 'vi-VN': 175000000,
      'id': 112000000, 'id-ID': 112000000,
    },
    CA: {
      'zh-CN': 72000, 'en': 10000,
      'vi': 250000000, 'id': 160000000,
    },
    AU: {
      'zh-CN': 48000, 'en': 10000,
      'vi': 168000000, 'id': 108000000,
    },
    NZ: {
      'zh-CN': 48000, 'en': 10000,
      'vi': 168000000, 'id': 108000000,
    },
    SG: {
      'zh-CN': 54000, 'en': 10000,
      'vi': 188000000, 'id': 120000000,
    },
    GB: {
      'zh-CN': 40000, 'en': 5500,
      'vi': 140000000, 'id': 90000000,
    },
    // 申根 €6,500 ≈ ¥50,000
    AT: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    BE: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    HR: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    CZ: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    DK: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    EE: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    FI: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    FR: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    DE: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    GR: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    HU: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    IS: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    IT: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    LV: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    LI: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    LT: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    LU: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    MT: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    NL: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    NO: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    PL: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    PT: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    SK: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    SI: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    ES: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    SE: { 'zh-CN': 50000, 'en': 6500, 'vi': 175000000, 'id': 112000000 },
    JP: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    KR: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    TH: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    IN: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    VN: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    ID: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
    CN: { 'zh-CN': 50000, 'en': 7000, 'vi': 175000000, 'id': 112000000 },
  },
  insurance: {
    US: { 'zh-CN': 360000, 'en': 50000, 'vi': 1260000000, 'id': 805000000 },
    GB: { 'zh-CN': 220000, 'en': 30000, 'vi': 770000000, 'id': 490000000 },
    // 申根法定下限 3 万欧元
    AT: { 'zh-CN': 230000, 'en': 30000, 'vi': 805000000, 'id': 515000000 },
    FR: { 'zh-CN': 230000, 'en': 30000, 'vi': 805000000, 'id': 515000000 },
    DE: { 'zh-CN': 230000, 'en': 30000, 'vi': 805000000, 'id': 515000000 },
    SG: { 'zh-CN': 220000, 'en': 30000, 'vi': 770000000, 'id': 490000000 },
    CA: { 'zh-CN': 360000, 'en': 50000, 'vi': 1260000000, 'id': 805000000 },
    AU: { 'zh-CN': 360000, 'en': 50000, 'vi': 1260000000, 'id': 805000000 },
    NZ: { 'zh-CN': 360000, 'en': 50000, 'vi': 1260000000, 'id': 805000000 },
  },
}

// Symbol + thousands-separator style for each locale's local-currency note.
// We use the user's everyday currency, not the destination's. If the locale
// is missing we fall back to zh-CN (CNY) for parity with the old behaviour.
const LOCAL_SYMBOL_BY_LOCALE = {
  'zh-CN': '¥',
  'zh': '¥',
  'en': '$',
  'en-US': '$',
  'vi': '₫',
  'vi-VN': '₫',
  'id': 'Rp',
  'id-ID': 'Rp',
}
const LOCAL_SYMBOL_AFTER = new Set(['₫', 'Rp'])  // vi/id put symbol after number

function localNote(itemKey, cc, loc) {
  // W49 fix: en UI 下括号里的换算跟主金额同币种同值(都是 $7,000),
  // 显示出来是冗余 "(≈ ≈ $7,000)"。跳过 en,让 fallback 到空模板
  // 不渲染括号。
  const locKey = loc || 'zh-CN'
  if (locKey.startsWith('en')) return null
  const tbl = LOCAL_NOTE_TABLE[itemKey]
  if (!tbl) return null
  const row = tbl[cc] || tbl.US
  let n = row[locKey]
  if (n == null && locKey.includes('-')) n = row[locKey.split('-')[0]]
  if (n == null) n = row['zh-CN']
  const symbol = LOCAL_SYMBOL_BY_LOCALE[locKey]
    || LOCAL_SYMBOL_BY_LOCALE[(locKey || '').split('-')[0]]
    || '¥'
  const formatted = n.toLocaleString(locKey || 'en-US')
  return LOCAL_SYMBOL_AFTER.has(symbol)
    ? `≈ ${formatted} ${symbol}`
    : `≈ ${symbol}${formatted}`
}

// W60: 银行流水 hint 后面追加 CNY 换算 (业内通用 ≈ 50,000 CNY 财务证明下限),
// W48: replaced fixed `cny_note` with a per-locale `local_note` string that
// reformats the same anchor into the user's familiar currency (vi → ₫,
// id → Rp, zh → ¥, en → $). The hint template `{cur}{amount} ({local_note})`
// still anchors the main amount to the destination country's currency, but
// the parenthetical now reads in the user's own money so they can relate.
// W62: 卡内合并黄框的可见性:4 类提示任意一条命中即显示容器。
const hasInlineWarnings = computed(() => {
  if (props.record.isBlurry) return true
  if (!props.record.isComplete) return true
  if (props.itemKey === 'photo' && props.record.photoWarnings?.length) return true
  if (props.inlineIssues?.length) return true
  return false
})

const hintParams = computed(() => {
  const base = {
    cur: currencyFor(props.countryCode),
    amount: amountFor(props.itemKey, props.countryCode),
  }
  if (props.itemKey === 'bank_statement' || props.itemKey === 'insurance') {
    const note = localNote(props.itemKey, props.countryCode, locale.value)
    return { ...base, local_note: note || t('wizard.bank_cny_note') }
  }
  return base
})
const emit = defineEmits(['remove'])

const phase = ref('idle') // idle | camera | uploading | photo_fail
const progress = ref(0)
const fileInput = ref(null)
const videoEl = ref(null)
let mediaStream = null

const pendingPhotoFile = ref(null)
const pendingPreviewUrl = ref('')
const photoFailReasons = ref([])
const toolboxOpen = ref(false)

function setPendingPhoto(file) {
  pendingPhotoFile.value = file
  if (pendingPreviewUrl.value) URL.revokeObjectURL(pendingPreviewUrl.value)
  pendingPreviewUrl.value = file ? URL.createObjectURL(file) : ''
}

function clearPendingPhoto() {
  pendingPhotoFile.value = null
  photoFailReasons.value = []
  if (pendingPreviewUrl.value) {
    URL.revokeObjectURL(pendingPreviewUrl.value)
    pendingPreviewUrl.value = ''
  }
}

function openToolbox() {
  if (!pendingPhotoFile.value) return
  toolboxOpen.value = true
}

async function onToolboxConfirm(file) {
  toolboxOpen.value = false
  clearPendingPhoto()
  props.record.error = null
  await doUpload(file)
}

async function skipToolboxUpload() {
  const file = pendingPhotoFile.value
  if (!file) return
  clearPendingPhoto()
  props.record.error = null
  await doUpload(file)
}

function clearPhotoFail() {
  toolboxOpen.value = false
  clearPendingPhoto()
  props.record.error = null
  phase.value = 'idle'
}

const passportPreview = computed(() => {
  const f = props.record.ocrFields
  if (!f || !props.item.checkExpiry) return null
  const name = [f.given_name, f.surname].filter(Boolean).join(' ')
  return {
    name: name || t('wizard.preview_name_unknown'),
    no: f.passport_no ? t('wizard.preview_no_prefix', { no: f.passport_no }) : '',
    expiry: (f.expiry || f.date_of_expiry) ? t('wizard.preview_expiry_prefix', { date: f.expiry || f.date_of_expiry }) : '',
  }
})

// W63+ 银行流水的非阻断性提示 — 严重度到 CSS class / 图标映射
function ruleSeverityClass(severity) {
  if (severity >= 3) return 'critical'
  if (severity >= 2) return 'warning'
  return 'info'
}

// W67: 检测 issue 字段看起来是不是未翻译的 i18n key 字符串。
// 比如 'diagnose.passport_no_suspicious_title'、'wizard.diag_expiry_missing_detail'。
// 这些 dot-separated snake_case 模式不像自然语言,大概率是 t() 没找到 key
// 而返回的 fallback。识别出来后,渲染层就避开它们,改用 issue 后端原 zh 文案。
function looksLikeI18nKey(s) {
  if (typeof s !== 'string') return false
  return /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]+$/.test(s.trim())
}

// W67: 当 issue.title / detail 看起来都是 raw i18n key 字符串,渲染层降级
// 到翻译过得的、能用的字段;再不行就用后端 zh 硬编码 (issue._rawTitle/_rawDetail)。
function issueFallbackText(iss) {
  // 优先用后端硬编码 (issue.title 是 raw,detail 也是 raw 时,这个字段被 translate 跳过 -> 未使用)
  // 实际上后端返回的 title/detail 已是中文,所以直接显示
  const t = (typeof iss.title === 'string' && !looksLikeI18nKey(iss.title)) ? iss.title : ''
  const d = (typeof iss.detail === 'string' && !looksLikeI18nKey(iss.detail)) ? iss.detail : ''
  if (t && d) return `${t} · ${d}`
  if (t) return t
  if (d) return d
  return ''  // 真没办法了,空字符串不渲染
}
function ruleSeverityIcon(severity) {
  // 统一只用 ⚠️,不再用 ℹ️ / ⛔ 区分 severity
  // (W63+: 银行流水的 severity 分级已经体现在文案/颜色上,icon 不需要再分两套)
  return '⚠️'
}

// W62: 证件照片(itemKey === 'photo')需要在上传前调用 /v2/materials/photo/check
// 让人脸/宽高比/背景色都不对的文件被拦在客户端,避免污染 storage。
// 其他材料类型 (passport / bank / form / etc.) 走原 doUpload 即可。
const isPhoto = computed(() => props.itemKey === 'photo')

import {
  hasLocalSensitiveConsent,
  markLocalSensitiveConsent,
  syncSensitiveConsentToServer,
} from '@/utils/sensitiveConsent'

const SENSITIVE_KEYS = new Set(['passport', 'photo', 'bank_statement'])
const consentOpen = ref(false)
let pendingAction = null

function hasSensitiveConsent() {
  return hasLocalSensitiveConsent()
}

function needsConsent() {
  return SENSITIVE_KEYS.has(props.itemKey) && !hasSensitiveConsent()
}

function ensureConsent(action) {
  if (!needsConsent()) return true
  pendingAction = action
  consentOpen.value = true
  return false
}

async function onConsentAccept() {
  markLocalSensitiveConsent()
  await syncSensitiveConsentToServer()
  consentOpen.value = false
  if (pendingAction === 'file') fileInput.value?.click()
  else if (pendingAction === 'camera') startCameraInner()
  pendingAction = null
}

function onConsentCancel() {
  consentOpen.value = false
  pendingAction = null
}

function pickFile() {
  if (!ensureConsent('file')) return
  fileInput.value?.click()
}

async function onFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (isPhoto.value) {
    await runPhotoCheck(file)
  } else {
    await doUpload(file)
  }
}

// 调用后端 /v2/materials/photo/check,根据返回 errors / warnings 决定是否上传。
// errors 阻断(显示在卡片上,不进 uploadFn);
// warnings 不阻断(显示在卡片上,允许上传)。
async function runPhotoCheck(file) {
  phase.value = 'uploading'        // 复用 uploading 状态显示进度环
  progress.value = 5              // 起步 5% 给点视觉反馈
  try {
    const fd = new FormData()
    fd.append('file', file)
    if (props.countryCode) fd.append('country_code', props.countryCode)
    const resp = await http.post('/v2/materials/photo/check', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    // http.js 拦截器已把 axios 响应的 .data 提上来,这里 resp 形如
    //   { code: '1000', message: 'OK', data: { ok, errors, warnings, ... } }
    // 兼容老 axios 形态 (resp.data.data),以及极端情况 (resp.data) 都接得住。
    const data = resp?.data?.data || resp?.data || {}
    const errs = Array.isArray(data.errors) ? data.errors : []
    const warns = Array.isArray(data.warnings) ? data.warnings : []
    if (errs.length) {
      // 阻断:不调 doUpload；进入 photo_fail，引导使用照片工具箱
      setPendingPhoto(file)
      photoFailReasons.value = errs
      props.record.error = errs.join(' / ')
      props.record.photoWarnings = null
      phase.value = 'photo_fail'
      return
    }
    // 警告:放进 record.photoWarnings(默认状态是 null,避免重复渲染)
    props.record.photoWarnings = warns.length ? warns : null
    clearPendingPhoto()
    await doUpload(file)
  } catch (e) {
    // 后端 check 失败不阻塞用户(可能 cv2 还没装 / 服务重启中),降级放行
    console.warn('[upload-item-card] photo check failed, falling back to direct upload:', e?.message)
    props.record.photoWarnings = null
    clearPendingPhoto()
    await doUpload(file)
  } finally {
    // photo_fail 需保留；其余路径由 doUpload 自己收尾，这里只清掉「预检中」状态
    if (phase.value === 'uploading') phase.value = 'idle'
  }
}

async function startCamera() {
  if (!ensureConsent('camera')) return
  await startCameraInner()
}

async function startCameraInner() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    phase.value = 'camera'
    setTimeout(() => { if (videoEl.value) videoEl.value.srcObject = mediaStream }, 50)
  } catch {
    pickFile()
  }
}

function cancelCamera() {
  teardownCamera()
  phase.value = 'idle'
}

function capture() {
  const v = videoEl.value
  if (!v) return
  const canvas = document.createElement('canvas')
  canvas.width = v.videoWidth || 1280
  canvas.height = v.videoHeight || 720
  canvas.getContext('2d').drawImage(v, 0, 0, canvas.width, canvas.height)
  teardownCamera()
  canvas.toBlob((blob) => {
    if (!blob) return
    const file = new File([blob], `${props.itemKey}_scan.jpg`, { type: 'image/jpeg' })
    if (isPhoto.value) runPhotoCheck(file)
    else doUpload(file)
  }, 'image/jpeg', 0.92)
}

function teardownCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
}

async function doUpload(file) {
  phase.value = 'uploading'
  progress.value = 0
  try {
    await props.uploadFn(file, (p) => { progress.value = p })
  } catch {
    // record.error 已经在 uploadFn 内部（组合式函数）里写好了，这里不用重复处理
  } finally {
    phase.value = 'idle'
  }
}

function reupload() {
  toolboxOpen.value = false
  clearPendingPhoto()
  emit('remove')
  phase.value = 'idle'
}

// ---------- Lightbox (按文件类型分别预览) ----------
const previewOpen = ref(false)
const isImage = computed(() => (props.record.fileType || '').startsWith('image/'))
const isPdf = computed(() => (props.record.fileType || '') === 'application/pdf')
const fileTypeBadge = computed(() => {
  const ft = props.record.fileType || ''
  if (ft.startsWith('image/')) {
    // image/jpeg → JPG, image/png → PNG, image/webp → WEBP
    const ext = ft.split('/')[1] || 'IMG'
    return ext.toUpperCase()
  }
  if (ft === 'application/pdf') return 'PDF'
  if (ft) return ft.split('/').pop().toUpperCase()
  return 'FILE'
})

function openPreview() {
  previewOpen.value = true
  document.body.style.overflow = 'hidden'
}
function closePreview() {
  previewOpen.value = false
  document.body.style.overflow = ''
}
function onKeydown(e) {
  if (e.key === 'Escape' && previewOpen.value) closePreview()
}
// 监听 ESC 关 lightbox(组件挂载期间一直有效)
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKeydown)
}
onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('keydown', onKeydown)
  // 兜底:组件卸载时如果 lightbox 还开着,恢复 body 滚动
  if (previewOpen.value) document.body.style.overflow = ''
  clearPendingPhoto()
  toolboxOpen.value = false
})
</script>

<style scoped lang="scss">
.uic {
  border: 1.5px solid #e9edf5; border-radius: 16px; padding: 18px 20px;
  background: #fff; transition: border-color .15s ease, box-shadow .15s ease;
  &.is-done { border-color: #bbf7d0; background: #fff; }
  &.is-error { border-color: #fecaca; background: #fef2f2; }
}
.uic__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.uic__title { font-size: 15px; font-weight: 700; color: #0f172a; }
.uic__optional { font-size: 10px; font-weight: 600; color: #94a3b8; background: #f1f5f9; padding: 1px 8px; border-radius: 999px; margin-left: 6px; }
.uic__check {
  width: 22px; height: 22px; border-radius: 50%; background: #16a34a; color: #fff;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.uic__hint { font-size: 12.5px; color: #64748b; margin: 6px 0 14px; line-height: 1.5; }
.uic__constraints {
  display: flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: #94a3b8; font-weight: 500;
  margin: -8px 0 12px;
}
.uic__constraints svg { color: #cbd5e1; flex-shrink: 0; }

.uic__actions { display: flex; gap: 10px; flex-wrap: wrap; }
.uic__btn {
  flex: 1; min-width: 120px; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; border: 0; transition: all .15s ease;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  &--primary {
    background: #2563EB;
    color: #fff;
    border: 1px solid #2563EB;
    &:hover { background: #1D4ED8; border-color: #1D4ED8; }
  }
  &--primary:hover { box-shadow: 0 6px 16px rgba(59,110,245,.3); }
  &--ghost { background: #f1f5f9; color: #475569; }
  &--ghost:hover { background: #e2e8f0; }
}

.uic__photo-fail {
  margin-top: 4px;
}
.uic__photo-fail-preview {
  width: 88px;
  height: 110px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #fecaca;
  background: #fff;
  margin-bottom: 10px;
  img { width: 100%; height: 100%; object-fit: cover; display: block; }
}
.uic__photo-fail-title {
  font-size: 13px;
  font-weight: 700;
  color: #b91c1c;
  margin-bottom: 6px;
}
.uic__photo-fail-list {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 12.5px;
  color: #991b1b;
  line-height: 1.5;
}
.uic__photo-fail-hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  color: #64748b;
  line-height: 1.5;
}

.uic__camera { display: flex; flex-direction: column; gap: 10px; }
.uic__video { width: 100%; border-radius: 10px; background: #0f172a; aspect-ratio: 4/3; object-fit: cover; }
.uic__camera-actions { display: flex; gap: 10px; }

.uic__progress-bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.uic__progress-fill { height: 100%; background: #2563EB; transition: width .15s ease; }
.uic__progress-text { font-size: 12px; color: #64748b; margin-top: 6px; }

.uic__done { display: flex; flex-direction: column; gap: 8px; }
.uic__uploaded-state {
  width: 100%; min-height: 40px; border: 0; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: #A1A1AA; color: #fff;
  font-size: 13px; font-weight: 600; opacity: 1; cursor: default;
}
.uic__file { display: flex; align-items: center; gap: 10px; }
.uic__thumb { width: 44px; height: 44px; border-radius: 8px; object-fit: cover; background: #f1f5f9; }
.uic__thumb--fallback { display: flex; align-items: center; justify-content: center; font-size: 20px; }
.uic__filename { font-size: 13px; color: #0f172a; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uic__warn { color: #b45309; }
/* W67: 去掉黄色方框背景 (用户反馈: 视觉冗余,过于警示)。
   保留 warn 信息 + 颜色 (橘色文字 + ⚠️ 图标) — 只是不再用 box 包住。
   信息密度参考：在职证明样式，warn 行跟外部白底走，但保留语义色。 */
.uic__warn--box {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0 2px;
  font-size: 13px;
  line-height: 1.6;
}
.uic__warn-line {
  display: flex;
  gap: 6px;
  align-items: baseline;
}
.uic__warn-line.is-critical,
.uic__warn-line.is-error { color: #b91c1c; }
.uic__warn-icon { font-size: 12px; line-height: 1; flex-shrink: 0; }
.uic__warn-text { flex: 1; min-width: 0; }
.uic__warn-text b { font-weight: 600; color: #92400e; }
.uic__warn-line.is-critical .uic__warn-text b,
.uic__warn-line.is-error .uic__warn-text b { color: #b91c1c; }

.uic__ocr-preview {
  display: flex; flex-wrap: wrap; gap: 6px 12px; font-size: 12px; color: #0f172a;
  background: #f8fafc; padding: 8px 10px; border-radius: 8px;
}
.uic__reupload {
  align-self: flex-start; background: transparent; border: 1px solid #cbd5e1; color: #475569;
  font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 999px; cursor: pointer;
}
.uic__reupload:hover { background: #f1f5f9; }
.uic__error { margin-top: 10px; font-size: 12.5px; color: #b91c1c; }

// 缩略图可点击按钮(去掉默认 button 样式,看起来跟 img 一致)
.uic__thumb-btn {
  background: transparent; border: 0; padding: 0; margin: 0; cursor: zoom-in;
  border-radius: 8px; line-height: 0;
}
.uic__thumb-btn:focus-visible { outline: 2px solid #3B6EF5; outline-offset: 2px; }
// 文件类型徽章(显示在文件名右侧,直接告诉用户是 PDF / JPG / PNG 等)
.uic__filetype {
  font-size: 10px; font-weight: 700; color: #64748b; background: #f1f5f9;
  padding: 2px 7px; border-radius: 6px; letter-spacing: 0.4px; flex-shrink: 0;
}

// ---------- Lightbox 全屏预览 ----------
.uic-lightbox {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(15, 23, 42, 0.85);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.uic-lightbox__panel {
  width: 100%; max-width: 1100px; height: 100%; max-height: 90vh;
  background: #fff; border-radius: 14px; overflow: hidden;
  display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.uic-lightbox__bar {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 16px; border-bottom: 1px solid #e9edf5; background: #f8fafc;
}
.uic-lightbox__name { font-size: 13px; font-weight: 600; color: #0f172a; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uic-lightbox__type { font-size: 10px; font-weight: 700; color: #475569; background: #e2e8f0; padding: 2px 8px; border-radius: 6px; letter-spacing: 0.4px; }
.uic-lightbox__close {
  background: transparent; border: 0; font-size: 26px; line-height: 1; color: #64748b;
  cursor: pointer; padding: 0 8px; border-radius: 6px; transition: background .15s ease;
}
.uic-lightbox__close:hover { background: #e2e8f0; color: #0f172a; }
.uic-lightbox__body {
  flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center;
  background: #0f172a; padding: 16px; overflow: auto;
}
.uic-lightbox__img {
  max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px;
  background: #1e293b;
}
.uic-lightbox__pdf {
  width: 100%; height: 100%; min-height: 70vh; border: 0; background: #fff; border-radius: 6px;
}
.uic-lightbox__fallback {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  color: #cbd5e1; text-align: center;
}
.uic-lightbox__fallback-icon { font-size: 48px; opacity: 0.6; }
.uic-lightbox__fallback-name { font-size: 14px; font-weight: 600; color: #f1f5f9; max-width: 480px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uic-lightbox__fallback-hint { font-size: 12px; color: #94a3b8; }
.uic-lightbox__fallback-btn {
  margin-top: 4px; padding: 8px 16px; border-radius: 8px;
  background: #3B6EF5; color: #fff; font-size: 13px; font-weight: 600; text-decoration: none;
}
.uic-lightbox__fallback-btn:hover { background: #2548c5; }
</style>
