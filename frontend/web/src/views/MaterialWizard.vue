<template>
  <div class="mw-page">
    <AppHeader scope="materials" />

    <main class="mw-main">
      <header class="mw-hero">
        <h1 class="mw-hero__title">{{ t('wizard.title') }}</h1>
        <p class="mw-hero__sub">{{ flagOf(countryCode) }} {{ destinationName || countryCode }} · {{ t('wizard.subtitle') }}</p>
      </header>

      <!-- 整体进度条 -->
      <div class="mw-progress">
        <div class="mw-progress__bar"><div class="mw-progress__fill" :style="{ width: wizard.overallPercent.value + '%' }" /></div>
        <div class="mw-progress__text">{{ wizard.overallPercent.value }}% {{ t('wizard.progress_done') }}</div>
      </div>

      <!-- 分类导航 -->
      <div class="mw-steps">
        <button
          v-for="(cat, i) in wizard.CATEGORIES"
          :key="cat.key"
          type="button"
          class="mw-step"
          :class="{
            'is-active': wizard.state.activeCategory === cat.key,
            'is-done': wizard.categoryDone(cat.key),
          }"
          :data-testid="`mw-step-${cat.key}`"
          @click="wizard.goToCategory(cat.key)"
        >
          <span class="mw-step__icon" :class="`is-${cat.icon}`">
            <CategoryIcon :name="cat.icon" />
          </span>
          <span class="mw-step__label">{{ t(cat.labelKey) }}</span>
          <span v-if="wizard.categoryDone(cat.key)" class="mw-step__check">✓</span>
        </button>
      </div>

      <!-- 当前分类内容 -->
      <section class="mw-panel" :data-testid="`mw-panel-${wizard.activeCategoryDef.value.key}`">
        <h2 class="mw-panel__title">{{ t(wizard.activeCategoryDef.value.labelKey) }}</h2>

        <!-- 签证表格：6 大类收尾 — 在同一页内直接展开 3 个 sub-tab 表单，不再跳转 OrderNew。
             旧版：mw-finish + "开始填写申请表 →" 按钮跳 /orders/new，体验跨度大。
             新版：把 OrderNew.vue 的 3 个表单 section（basic/travel/emergency）原样嵌进来，
             用户填完直接 submit，登录墙在 onSubmit 触发时弹。 -->
        <template v-if="wizard.activeCategoryDef.value.isFormStep">
          <!-- Loading/Error -->
          <div v-if="formLoading" class="state-block" data-testid="mw-form-loading">
            <span class="spinner" aria-hidden="true"></span> {{ t('common.loading') }}
          </div>
          <div v-else-if="formLoadError" class="state-block state-block--err" data-testid="mw-form-error">
            <p>❌ {{ formLoadError }}</p>
            <button class="form-footer__retry" @click="loadFormData" data-testid="mw-form-retry">{{ t('common.retry') }}</button>
          </div>

          <template v-else>
            <!-- OCR 预填提示 -->
            <div v-if="prefillPercent > 0" class="mw-form-ocr-hint" data-testid="mw-form-ocr-pct">
              <span class="mw-form-ocr-icon">⚡</span>
              <span>{{ t('orders.ocr_prefilled', { percent: prefillPercent }) }} · {{ t('wizard.ocr_complete_remaining') }}</span>
            </div>

            <!-- Sub-tab 切换 -->
            <nav class="form-tabs" role="tablist" data-testid="mw-form-tabs">
              <button
                v-for="tab in subTabs"
                :key="tab.key"
                class="form-tab"
                :class="{ on: activeTab === tab.key, done: isFormTabDone(tab.key) }"
                :data-testid="`mw-form-tab-${tab.key}`"
                role="tab"
                :aria-selected="activeTab === tab.key"
                @click="activeTab = tab.key"
              >
                <span class="form-tab__check" v-if="isFormTabDone(tab.key)">✓</span>
                <span class="form-tab__check form-tab__check--empty" v-else>•</span>
                <span>{{ t(tab.label) }}</span>
              </button>
              <span class="form-tabs__counter" data-testid="mw-form-sub-counter">
                {{ formSubDoneCount }} / {{ formSubTotal }} {{ t('orders.sub_tabs_done', 'sections completed') }}
              </span>
            </nav>

            <!-- ============== Basic ============== -->
            <section v-show="activeTab === 'basic'" class="form-card" data-testid="mw-form-section-basic">
              <h2 class="form-card__title">{{ t('orders.section_basic') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <AppInput v-model="form.surname" :label="t('orders.field_surname')" placeholder="SANTOSO" :error="errors.surname" required maxlength="64" data-testid="mw-form-surname" />
                  <span v-if="ocrMarked.surname" class="form-cell__ocr" data-testid="mw-form-ocr-surname">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.given_name" :label="t('orders.field_given_name')" placeholder="BUDI" :error="errors.given_name" required maxlength="64" data-testid="mw-form-given-name" />
                  <span v-if="ocrMarked.given_name" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_sex') }}<span class="form-cell__required">*</span></label>
                  <div class="radio-group" data-testid="mw-form-sex">
                    <label class="radio-pill" :class="{ on: form.sex === 'M' }">
                      <input v-model="form.sex" type="radio" value="M" />
                      <span>♂ {{ t('orders.field_sex_male') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.sex === 'F' }">
                      <input v-model="form.sex" type="radio" value="F" />
                      <span>♀ {{ t('orders.field_sex_female') }}</span>
                    </label>
                  </div>
                  <span v-if="errors.sex" class="form-cell__error">{{ errors.sex }}</span>
                  <span v-else-if="ocrMarked.sex" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.dob" :label="t('orders.field_dob')" type="date" :error="errors.dob" required :max="todayIso" data-testid="mw-form-dob" />
                  <span v-if="ocrMarked.dob" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_nationality') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.nationality" class="form-cell__select" :class="{ 'is-error': !!errors.nationality }" data-testid="mw-form-nationality">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                  <span v-if="errors.nationality" class="form-cell__error">{{ errors.nationality }}</span>
                  <span v-else-if="ocrMarked.nationality" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_no" :label="t('orders.field_passport_no')" placeholder="A12345678" :error="errors.passport_no" required maxlength="12" data-testid="mw-form-passport-no" />
                  <span v-if="ocrMarked.passport_no" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_expiry" :label="t('orders.field_passport_expiry')" type="date" :error="errors.passport_expiry" :min="minPassportExpiry" data-testid="mw-form-passport-expiry" />
                  <span v-if="ocrMarked.passport_expiry" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
              </div>
            </section>

            <!-- ============== Travel ============== -->
            <section v-show="activeTab === 'travel'" class="form-card" data-testid="mw-form-section-travel">
              <h2 class="form-card__title">{{ t('orders.section_travel') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_destination') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.destination_id" class="form-cell__select" :class="{ 'is-error': !!errors.destination_id }" data-testid="mw-form-destination">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="d in destinations" :key="d.id" :value="d.id" :disabled="!d.enabled">
                      {{ flagEmoji(d.country_code) }} {{ d.country_name || t(d.country_name_key) }} ({{ d.country_code }}){{ d.enabled ? '' : ' · ' + t('dest.coming_soon') }}
                    </option>
                  </select>
                  <span v-if="errors.destination_id" class="form-cell__error">{{ errors.destination_id }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_visa_type') }}<span class="form-cell__required">*</span></label>
                  <div class="radio-group" data-testid="mw-form-visa-type">
                    <label class="radio-pill" :class="{ on: form.visa_type === 'tourism' }">
                      <input v-model="form.visa_type" type="radio" value="tourism" />
                      <span>✈ {{ t('orders.visa_tourism') }}</span>
                    </label>
                  </div>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.arrival_date" :label="t('orders.field_arrival_date')" type="date" :error="errors.arrival_date" required :min="todayIso" data-testid="mw-form-arrival" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.departure_date" :label="t('orders.field_departure_date')" type="date" :error="errors.departure_date" required :min="form.arrival_date || todayIso" data-testid="mw-form-departure" />
                </div>
                <div class="form-cell">
                  <AppInput v-model.number="form.stay_days" :label="t('orders.field_stay_days')" type="number" :error="errors.stay_days" min="1" max="365" :hint="stayDaysHint" data-testid="mw-form-stay-days" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.flight_no" :label="t('orders.field_flight_no')" data-testid="mw-form-flight-no" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.hotel_name" :label="t('orders.field_hotel_name')" data-testid="mw-form-hotel-name" />
                </div>
              </div>
              <div v-if="itineraryText" class="itinerary-preview" data-testid="mw-form-itinerary-preview">
                <div class="itinerary-preview__title">{{ t('orders.itinerary_generated_title') }}</div>
                <pre class="itinerary-preview__text">{{ itineraryText }}</pre>
              </div>
            </section>

            <!-- ============== Emergency ============== -->
            <section v-show="activeTab === 'emergency'" class="form-card" data-testid="mw-form-section-emergency">
              <h2 class="form-card__title">{{ t('orders.section_emergency') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <AppInput v-model="form.emergency_name" :label="t('orders.field_emergency_name')" :placeholder="t('orders.field_emergency_name')" :error="errors.emergency_name" required maxlength="64" data-testid="mw-form-emergency-name" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.emergency_phone" :label="t('orders.field_emergency_phone')" :placeholder="t('orders.placeholder_phone')" :error="errors.emergency_phone" required inputmode="numeric" maxlength="20" data-testid="mw-form-emergency-phone" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_emergency_relation') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.emergency_relation" class="form-cell__select" :class="{ 'is-error': !!errors.emergency_relation }" data-testid="mw-form-emergency-relation">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="r in relations" :key="r.value" :value="r.value">{{ t(r.label) }}</option>
                  </select>
                  <span v-if="errors.emergency_relation" class="form-cell__error">{{ errors.emergency_relation }}</span>
                </div>
              </div>
            </section>

            <!-- 表单大类底部操作 — 与上传大类不同：prev/submit 而不是 skip/next -->
            <footer class="form-footer" data-testid="mw-form-footer">
              <button class="form-footer__prev" :disabled="!hasPrevFormTab" data-testid="mw-form-prev" @click="goPrevFormTab">← {{ t('orders.btn_prev') }}</button>
              <div class="form-footer__right">
                <button v-if="!isLastFormTab" class="form-footer__next" data-testid="mw-form-next" @click="goNextFormTab">{{ t('orders.btn_next') }} →</button>
                <button v-else class="form-footer__submit" :disabled="submitting" data-testid="mw-form-submit" @click="onSubmitForm">
                  {{ submitting ? t('orders.btn_submitting') : t('orders.btn_submit') }}
                </button>
              </div>
            </footer>
          </template>
        </template>

        <!-- 行程住宿 -->
        <template v-else-if="wizard.activeCategoryDef.value.isTravelPlanner">
          <TravelPlanner
            :plan="wizard.state.travelPlan"
            :destination-name="destinationName"
            :country-code="countryCode"
            :on-generate-itinerary="wizard.generateItinerary"
            :on-compile-itinerary-text="wizard.compileItineraryText"
            :on-rebuild-days="wizard.rebuildTravelDays"
            :on-validate-for-generate="wizard.validateForGenerate"
            :day-city-display-fn="wizard.dayCityDisplay"
            :on-mark-day-field-manual="wizard.markDayFieldManual"
            :on-sync-destination-to-days="wizard.syncDestinationToDays"
          />
        </template>

        <!-- 普通上传大类 -->
        <template v-else>
          <div class="mw-items">
            <UploadItemCard
              v-for="item in wizard.activeCategoryDef.value.items"
              :key="item.key"
              :item-key="item.key"
              :item="item"
              :record="wizard.state.categories[wizard.activeCategoryDef.value.key].items[item.key]"
              :upload-fn="(file, onProgress) => wizard.uploadItem(wizard.activeCategoryDef.value.key, item.key, file, onProgress)"
              :country-code="countryCode"
              @remove="wizard.removeItem(wizard.activeCategoryDef.value.key, item.key)"
            />
          </div>

          <!-- 参考样本（中英双语）—— 仅 3 个材料大类（identity / financial / work）显示 -->
          <MaterialTemplatePreview
            v-if="['identity', 'financial', 'work'].includes(wizard.activeCategoryDef.value.key)"
            :category-key="wizard.activeCategoryDef.value.key"
            :country-code="countryCode"
          />
        </template>

        <!-- 校验问题 -->
        <div v-if="currentIssues.length" class="mw-issues" data-testid="mw-issues">
          <div v-for="(iss, i) in currentIssues" :key="i" class="mw-issue" :class="`is-${iss.severity}`">
            <b>{{ iss.title }}</b>
            <span v-if="iss.detail">{{ iss.detail }}</span>
          </div>
        </div>

        <!-- 底部操作 -->
        <div v-if="!wizard.activeCategoryDef.value.isFormStep" class="mw-footer">
          <button
            v-if="wizard.activeCategoryDef.value.skippable && !wizard.categoryDone(wizard.activeCategoryDef.value.key)"
            class="mw-footer__skip"
            data-testid="mw-skip"
            @click="onSkip"
          >
            {{ t('wizard.skip') }}
          </button>
          <button
            class="mw-footer__next"
            :class="{ 'is-disabled': !canAdvance }"
            :disabled="!canAdvance || validating"
            data-testid="mw-next"
            @click="onNext"
          >
            {{ validating ? t('wizard.validating') : t('wizard.next') + ' →' }}
          </button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import AppInput from '@/components/AppInput.vue'
import UploadItemCard from '@/components/UploadItemCard.vue'
import TravelPlanner from '@/components/TravelPlanner.vue'
import MaterialTemplatePreview from '@/components/MaterialTemplatePreview.vue'
import { useMaterialWizard } from '@/composables/useMaterialWizard'
import { listDestinations } from '@/api/destinations'
import { fetchMaterialsForForm, extractApplicantDraft, createOrder } from '@/api/orders'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const { t, locale, te } = useI18n()
const auth = useAuthStore()
const toast = useToast()

const countryCode = (route.query.country || '').toString().toUpperCase()
const visaType = (route.query.visa_type || 'tourism').toString()

const wizard = useMaterialWizard(countryCode, visaType)
// 组合式函数里的 computed 在 <script setup> 顶层会被自动解包，但这里我们把整个
// wizard 对象透传给 template，所以模板里读取时手动 .value（wizard.overallPercent.value 等）。

const destinationName = ref('')
listDestinations({ lang: locale.value }).then((list) => {
  const d = (list || []).find((x) => x.country_code === countryCode)
  if (d) destinationName.value = d.country_name
}).catch(() => {})

const FLAG_MAP = {
  US: '🇺🇸', GB: '🇬🇧', AU: '🇦🇺', FR: '🇫🇷', DE: '🇩🇪', IT: '🇮🇹', ES: '🇪🇸',
}
function flagOf(cc) { return FLAG_MAP[cc] || '🌐' }

// 通用 country flag emoji (OrderNew 风格)
function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}

const validating = ref(false)

const currentIssues = computed(() => {
  const cat = wizard.state.categories[wizard.activeCategoryDef.value.key]
  return cat?.issues || []
})

const canAdvance = computed(() => wizard.activeCategoryReady.value)

async function onNext() {
  if (!canAdvance.value) return
  validating.value = true
  try {
    const result = await wizard.validateCategory(wizard.activeCategoryDef.value.key)
    if (result.validated) {
      wizard.goToNextCategory()
    }
  } finally {
    validating.value = false
  }
}

function onSkip() {
  wizard.skipCategory(wizard.activeCategoryDef.value.key)
  wizard.goToNextCategory()
}

// ============================================================ //
// 签证表格：6 大类收尾 — 在同一页内直接展开 3 个 sub-tab 表单        //
// 旧版：goToOrderForm() 跳 /orders/new（OrderNew.vue）                  //
// 新版：把 OrderNew.vue 的 3 个 section 嵌到 MaterialWizard 里                //
// ============================================================ //

// ----- 基础数据 -----
const todayIso = new Date().toISOString().slice(0, 10)
const minPassportExpiry = (() => {
  const d = new Date()
  d.setMonth(d.getMonth() + 6)
  return d.toISOString().slice(0, 10)
})()

// fallback destinations (与 OrderNew 同源,防止后端 /v2/destinations 未就绪)
const FALLBACK_DESTINATIONS = [
  { id: 1, country_code: 'US', country_name_key: 'country.us', visa_types: ['tourism'], enabled: true },
  { id: 2, country_code: 'JP', country_name_key: 'country.jp', visa_types: ['tourism'], enabled: false },
  { id: 3, country_code: 'UK', country_name_key: 'country.uk', visa_types: ['tourism'], enabled: false },
  { id: 4, country_code: 'AU', country_name_key: 'country.au', visa_types: ['tourism'], enabled: false },
  { id: 5, country_code: 'CA', country_name_key: 'country.ca', visa_types: ['tourism'], enabled: false },
  { id: 6, country_code: 'DE', country_name_key: 'country.de_schengen', visa_types: ['tourism'], enabled: false },
  { id: 7, country_code: 'FR', country_name_key: 'country.fr_schengen', visa_types: ['tourism'], enabled: false },
  { id: 8, country_code: 'SG', country_name_key: 'country.sg', visa_types: ['tourism'], enabled: false },
  { id: 9, country_code: 'NZ', country_name_key: 'country.nz', visa_types: ['tourism'], enabled: false }
]

const nationalityOptions = [
  { code: 'CN', nameKey: 'country.cn', flag: '🇨🇳' },
  { code: 'ID', nameKey: 'country.id', flag: '🇮🇩' },
  { code: 'VN', nameKey: 'country.vn', flag: '🇻🇳' },
  { code: 'PH', nameKey: 'country.ph', flag: '🇵🇭' },
  { code: 'MY', nameKey: 'country.my', flag: '🇲🇾' },
  { code: 'TH', nameKey: 'country.th', flag: '🇹🇭' },
  { code: 'SG', nameKey: 'country.sg', flag: '🇸🇬' },
  { code: 'US', nameKey: 'country.us', flag: '🇺🇸' },
  { code: 'JP', nameKey: 'country.jp', flag: '🇯🇵' },
  { code: 'GB', nameKey: 'country.gb', flag: '🇬🇧' },
  { code: 'AU', nameKey: 'country.au', flag: '🇦🇺' },
  { code: 'CA', nameKey: 'country.ca', flag: '🇨🇦' },
  { code: 'DE', nameKey: 'country.de', flag: '🇩🇪' },
  { code: 'FR', nameKey: 'country.fr', flag: '🇫🇷' },
  { code: 'KR', nameKey: 'country.kr', flag: '🇰🇷' }
]

const relations = [
  { value: 'spouse', label: 'orders.relation_spouse' },
  { value: 'parent', label: 'orders.relation_parent' },
  { value: 'child', label: 'orders.relation_child' },
  { value: 'sibling', label: 'orders.relation_sibling' },
  { value: 'friend', label: 'orders.relation_friend' },
  { value: 'colleague', label: 'orders.relation_colleague' },
  { value: 'other', label: 'orders.relation_other' }
]

// 表单 sub-tabs
const subTabs = [
  { key: 'basic', label: 'orders.tab_basic' },
  { key: 'travel', label: 'orders.tab_travel' },
  { key: 'emergency', label: 'orders.tab_emergency' }
]
const activeTab = ref('basic')

// 表单 state（从 OrderNew.vue 原样搬过来,加自动保存）
const form = reactive({
  surname: '',
  given_name: '',
  sex: '',
  dob: '',
  nationality: '',
  passport_no: '',
  passport_expiry: '',
  destination_id: '',
  visa_type: visaType,
  arrival_date: '',
  departure_date: '',
  stay_days: 7,
  flight_no: '',
  hotel_name: '',
  emergency_name: '',
  emergency_phone: '',
  emergency_relation: ''
})
const errors = reactive({
  surname: '', given_name: '', sex: '', dob: '', nationality: '',
  passport_no: '', passport_expiry: '', destination_id: '',
  arrival_date: '', departure_date: '', stay_days: '',
  emergency_name: '', emergency_phone: '', emergency_relation: ''
})
const ocrMarked = reactive({
  surname: false, given_name: false, sex: false, dob: false,
  nationality: false, passport_no: false, passport_expiry: false
})
const prefillPercent = ref(0)
const itineraryText = ref('')

const destinations = ref([])
const formLoading = ref(false)
const formLoadError = ref('')
const submitting = ref(false)

// 行程天数提示
const stayDaysHint = computed(() => {
  if (form.arrival_date && form.departure_date) {
    const a = new Date(form.arrival_date)
    const b = new Date(form.departure_date)
    if (b > a) {
      const days = Math.round((b - a) / 86400000) + 1
      return t('orders.stay_days_hint', { next: t('orders.stay_days_auto'), days })
    }
  }
  return ''
})

watch([() => form.arrival_date, () => form.departure_date], () => {
  if (form.arrival_date && form.departure_date) {
    const a = new Date(form.arrival_date)
    const b = new Date(form.departure_date)
    if (b >= a) {
      form.stay_days = Math.round((b - a) / 86400000) + 1
    }
  }
})

// 表单自动保存 — key 包含 countryCode+visaType,避免不同国家/签种串数据
// TTL 7 天(跟 OrderNew 的 ordernew_draft 一致)
const FORM_DRAFT_KEY = 'wizard.orderForm'
const FORM_DRAFT_TTL_MS = 7 * 24 * 3600 * 1000

function draftKey() {
  return `${FORM_DRAFT_KEY}.${countryCode || 'na'}.${visaType || 'na'}`
}

function saveFormDraft() {
  try {
    localStorage.setItem(draftKey(), JSON.stringify({
      form: { ...form },
      errors: { ...errors },
      ocrMarked: { ...ocrMarked },
      activeTab: activeTab.value,
      prefillPercent: prefillPercent.value,
      itineraryText: itineraryText.value,
      savedAt: Date.now()
    }))
  } catch { /* quota / privacy mode, ignore */ }
}

function loadFormDraft() {
  try {
    const raw = localStorage.getItem(draftKey())
    if (!raw) return false
    const draft = JSON.parse(raw)
    if (!draft || !draft.form) return false
    if (Date.now() - (draft.savedAt || 0) > FORM_DRAFT_TTL_MS) {
      localStorage.removeItem(draftKey())
      return false
    }
    Object.assign(form, draft.form)
    Object.assign(errors, draft.errors || {})
    Object.assign(ocrMarked, draft.ocrMarked || {})
    if (draft.activeTab) activeTab.value = draft.activeTab
    if (typeof draft.prefillPercent === 'number') prefillPercent.value = draft.prefillPercent
    if (typeof draft.itineraryText === 'string') itineraryText.value = draft.itineraryText
    return true
  } catch {
    return false
  }
}

// 表单状态变化 → 自动保存(去抖,避免每个键都写 localStorage)
let _saveTimer = null
function scheduleSaveFormDraft() {
  if (_saveTimer) clearTimeout(_saveTimer)
  _saveTimer = setTimeout(saveFormDraft, 300)
}

// 监听 form + activeTab + itineraryText 任一变化都自动保存
// (errors 是 form 的派生,会被 form watch 顺带捕获)
watch(form, scheduleSaveFormDraft, { deep: true })
watch(activeTab, scheduleSaveFormDraft)
watch(itineraryText, scheduleSaveFormDraft)
watch(prefillPercent, scheduleSaveFormDraft)

// ---- 加载数据 (destinations + material OCR prefill) ----
async function loadFormData() {
  formLoading.value = true
  formLoadError.value = ''
  try {
    // 1) destinations — 硬编码兜底 + 真实接口
    destinations.value = FALLBACK_DESTINATIONS
    try {
      const real = await listDestinations({ lang: locale.value || 'zh-CN' })
      if (Array.isArray(real) && real.length > 0) {
        destinations.value = real
      }
    } catch (e) {
      console.warn('[materialwizard] destinations load failed, using fallback:', e?.message)
    }

    // 2) 选 destination_id (与 countryCode 关联)
    if (countryCode) {
      const d = destinations.value.find((x) => x.country_code === countryCode)
      if (d) form.destination_id = d.id
    }
    if (!form.destination_id && destinations.value.length) {
      const us = destinations.value.find((x) => x.country_code === 'US' && x.enabled)
      form.destination_id = (us || destinations.value[0]).id
    }

    // 3) 恢复 draft — 7 天内有效,避免重填
    loadFormDraft()

    // 4) OCR 预填 — 拉材料 → 抽 applicant 字段 → 灌进 form
    const ids = wizard.allMaterialIds.value
    if (ids.length > 0) {
      const mats = await fetchMaterialsForForm(ids)
      const { draft, percent } = extractApplicantDraft(mats)
      prefillPercent.value = percent
      // 已经有用户填的内容（来自 draft 恢复）就保留,否则用 OCR
      for (const k of Object.keys(draft)) {
        if (draft[k] && !form[k]) {
          form[k] = draft[k]
          ocrMarked[k] = true
        }
      }
    }

    // 5) 默认旅行日期 (没有 draft 也没用户输入时给个起点)
    if (!form.arrival_date) {
      const a = new Date(); a.setDate(a.getDate() + 30)
      form.arrival_date = a.toISOString().slice(0, 10)
    }
    if (!form.departure_date) {
      const b = new Date(); b.setDate(b.getDate() + 37)
      form.departure_date = b.toISOString().slice(0, 10)
    }
    form.visa_type = visaType

    // 6) 从 wizard 拉行程单(MaterialWizard 行程住宿步骤生成)
    if (!itineraryText.value) {
      const wp = wizard.state.travelPlan
      if (wp?.itineraryText) itineraryText.value = wp.itineraryText
    }
  } catch (e) {
    formLoadError.value = e?.message || t('orders.load_failed')
  } finally {
    formLoading.value = false
  }
}

// 进入"签证表格"分类时按需加载 (避免一开始就发请求)
watch(
  () => wizard.activeCategoryDef.value.isFormStep,
  (isForm) => {
    if (isForm && destinations.value.length === 0 && !formLoading.value) {
      loadFormData()
    }
  },
  { immediate: true }
)

// ---- sub-tab 切换 ----
const currentFormTabIndex = computed(() => subTabs.findIndex((x) => x.key === activeTab.value))
const isLastFormTab = computed(() => currentFormTabIndex.value === subTabs.length - 1)
const hasPrevFormTab = computed(() => currentFormTabIndex.value > 0)

function goNextFormTab() {
  if (!validateTab(activeTab.value, { silent: true })) {
    validateTab(activeTab.value, { silent: false })
    return
  }
  if (!isLastFormTab.value) {
    activeTab.value = subTabs[currentFormTabIndex.value + 1].key
  }
}
function goPrevFormTab() {
  if (hasPrevFormTab.value) {
    activeTab.value = subTabs[currentFormTabIndex.value - 1].key
  }
}

function isFormTabDone(key) {
  if (key === 'basic') {
    return !!(form.surname && form.given_name && form.sex && form.dob && form.nationality && form.passport_no)
  }
  if (key === 'travel') {
    return !!(form.destination_id && form.arrival_date && form.departure_date && form.stay_days)
  }
  if (key === 'emergency') {
    return !!(form.emergency_name && form.emergency_phone && form.emergency_relation)
  }
  return false
}
const formSubDoneCount = computed(() => subTabs.filter((x) => isFormTabDone(x.key)).length)
const formSubTotal = subTabs.length

// ---- 校验 ----
function clearFormErrors() {
  Object.keys(errors).forEach((k) => { errors[k] = '' })
}

function validateTab(tabKey, { silent = false } = {}) {
  if (silent) clearFormErrors()
  let ok = true
  if (tabKey === 'basic') {
    if (!form.surname) { ok = false; if (!silent) errors.surname = t('orders.err_surname') }
    if (!form.given_name) { ok = false; if (!silent) errors.given_name = t('orders.err_given_name') }
    if (!form.sex) { ok = false; if (!silent) errors.sex = t('orders.err_sex') }
    if (!form.dob) { ok = false; if (!silent) errors.dob = t('orders.err_dob') }
    else if (form.dob > todayIso) { ok = false; if (!silent) errors.dob = t('orders.err_dob_future') }
    if (!form.nationality) { ok = false; if (!silent) errors.nationality = t('orders.err_nationality') }
    if (!form.passport_no) { ok = false; if (!silent) errors.passport_no = t('orders.err_passport_format') }
    else if (form.nationality === 'CN' && !/^[A-Z][0-9]{8}$/.test(form.passport_no.toUpperCase())) {
      ok = false
      if (!silent) errors.passport_no = t('orders.err_passport_format')
    }
    if (form.passport_expiry && form.passport_expiry < minPassportExpiry) {
      ok = false
      if (!silent) errors.passport_expiry = t('orders.err_passport_expiry')
    }
  }
  if (tabKey === 'travel') {
    if (!form.destination_id) { ok = false; if (!silent) errors.destination_id = t('orders.err_required') }
    if (!form.arrival_date) { ok = false; if (!silent) errors.arrival_date = t('orders.err_arrival_date') }
    if (!form.departure_date) { ok = false; if (!silent) errors.departure_date = t('orders.err_departure_date') }
    if (form.arrival_date && form.departure_date && form.departure_date < form.arrival_date) {
      ok = false
      if (!silent) errors.departure_date = t('orders.err_date_range')
    }
    const d = Number(form.stay_days)
    if (!d || d < 1 || d > 365) {
      ok = false
      if (!silent) errors.stay_days = t('orders.err_stay_days')
    }
  }
  if (tabKey === 'emergency') {
    if (!form.emergency_name) { ok = false; if (!silent) errors.emergency_name = t('orders.err_emergency_name') }
    if (!form.emergency_phone) { ok = false; if (!silent) errors.emergency_phone = t('orders.err_emergency_phone') }
    else if (!/^\+?\d{6,20}$/.test(form.emergency_phone.replace(/\s/g, ''))) {
      ok = false
      if (!silent) errors.emergency_phone = t('orders.err_emergency_phone')
    }
    if (!form.emergency_relation) { ok = false; if (!silent) errors.emergency_relation = t('orders.err_emergency_relation') }
  }
  return ok
}

function validateAllFormTabs() {
  clearFormErrors()
  const r1 = validateTab('basic', { silent: true })
  const r2 = validateTab('travel', { silent: true })
  const r3 = validateTab('emergency', { silent: true })
  if (!r1) { activeTab.value = 'basic'; validateTab('basic', { silent: false }) }
  else if (!r2) { activeTab.value = 'travel'; validateTab('travel', { silent: false }) }
  else if (!r3) { activeTab.value = 'emergency'; validateTab('emergency', { silent: false }) }
  return r1 && r2 && r3
}

// ---- 提交 ----
async function onSubmitForm() {
  if (!validateAllFormTabs()) {
    toast.error(t('orders.err_form_incomplete') || '请补全必填字段')
    return
  }
  // 登录墙：未登录时先保存 draft,跳 Login,登录后回跳续提
  if (!auth.isLoggedIn) {
    saveFormDraft() // 确保最后一次必填内容存住
    return router.push({
      name: 'Login',
      query: {
        redirect: route.fullPath,
        intent: 'submit_form',
        hint: 'login_needed'
      }
    })
  }
  submitting.value = true
  try {
    const payload = {
      destination_id: Number(form.destination_id),
      visa_type: form.visa_type,
      material_ids: wizard.allMaterialIds.value.filter(Boolean),
      applicant_data: {
        surname: form.surname.trim().toUpperCase(),
        given_name: form.given_name.trim().toUpperCase(),
        sex: form.sex,
        dob: form.dob,
        nationality: form.nationality,
        passport_no: form.passport_no.toUpperCase(),
        passport_expiry: form.passport_expiry,
        arrival_date: form.arrival_date,
        departure_date: form.departure_date,
        stay_days: Number(form.stay_days),
        flight_no: form.flight_no.trim(),
        hotel_name: form.hotel_name.trim(),
        itinerary_text: itineraryText.value,
        emergency_contact: {
          name: form.emergency_name.trim(),
          phone: form.emergency_phone.trim(),
          relation: form.emergency_relation
        }
      }
    }
    const order = await createOrder(payload)
    // 提交成功 → 清掉 draft,跳 RpaSubmit
    try { localStorage.removeItem(draftKey()) } catch { /* ignore */ }
    toast.success(t('orders.submit_success'))
    setTimeout(() => {
      const destCountry = countryCode || (destinations.value.find((d) => d.id === Number(form.destination_id))?.country_code) || ''
      const visa = form.visa_type || 'tourism'
      const passportData = {
        surname: form.surname.trim().toUpperCase(),
        given_name: form.given_name.trim().toUpperCase(),
        sex: form.sex,
        dob: form.dob,
        nationality: form.nationality,
        passport_no: form.passport_no.toUpperCase(),
        passport_expiry: form.passport_expiry
      }
      try {
        sessionStorage.setItem(`rpa_passport_${order.order_no}`, JSON.stringify(passportData))
      } catch { /* ignore */ }
      router.push({
        name: 'RpaSubmit',
        query: {
          orderNo: order.order_no,
          countryCode: destCountry,
          visaType: visa
        }
      }).catch(() => {
        router.push({ name: 'OrderDetail', params: { orderNo: order.order_no } })
      })
    }, 600)
  } catch (e) {
    toast.error(e?.message || t('orders.submit_failed'))
  } finally {
    submitting.value = false
  }
}

// 登录后从 Login 跳回来 (intent=submit_form) → 自动续提
onMounted(() => {
  auth.hydrate()
  if (auth.isLoggedIn && route.query?.intent === 'submit_form') {
    router.replace({ path: route.path, query: {} })
    // 等 form 状态稳定再提交
    setTimeout(() => onSubmitForm(), 200)
  }
})

// ------------------------------------------------------------------ //
// 分类图标 — 与 Apply.vue 材料预览用的同一套线条图标，保持视觉一致           //
// ------------------------------------------------------------------ //
const CategoryIcon = {
  props: { name: String },
  render() {
    const common = { viewBox: '0 0 24 24', width: 16, height: 16, fill: 'none', 'aria-hidden': 'true' }
    const stroke = { stroke: 'currentColor' }
    switch (this.name) {
      case 'identity':
        return h('svg', common, [
          h('rect', { x: 3, y: 5, width: 18, height: 14, rx: 2.5, ...stroke, 'stroke-width': 1.7 }),
          h('circle', { cx: 8.5, cy: 11, r: 1.8, ...stroke, 'stroke-width': 1.5 }),
          h('path', { d: 'M5.5 16c.6-1.7 1.9-2.5 3-2.5s2.4.8 3 2.5', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M14.5 10h4M14.5 13h4', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'financial':
        return h('svg', common, [
          h('circle', { cx: 12, cy: 12, r: 8.5, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M9.3 9.3c0-1.1 1.1-2 2.7-2s2.7.9 2.7 2c0 2.8-5.4 1.4-5.4 4.2 0 1.1 1.2 2 2.7 2s2.7-.9 2.7-2', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M12 6v1.3M12 16.7V18', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'work':
        return h('svg', common, [
          h('rect', { x: 3, y: 8, width: 18, height: 11, rx: 2, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M8.5 8V6.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V8', ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M3 13h18', ...stroke, 'stroke-width': 1.5 }),
        ])
      case 'travel':
        return h('svg', common, [
          h('path', { d: 'M13 3.5l-2.4 2.4L4 7.3l-.9 1.6 6.6 1.6-.4 4.3-1.9 1.4.2 1.6 2.9-1 1.6 2.6 1.5-.6-.5-3 4-3 1.6-4.3-1.6-1.6-3.3.9-1-2.9z', ...stroke, 'stroke-width': 1.4, 'stroke-linejoin': 'round' }),
        ])
      case 'insurance':
        return h('svg', common, [
          h('path', { d: 'M12 3.5l7 3v5.2c0 4.6-3 7.9-7 8.8-4-.9-7-4.2-7-8.8V6.5l7-3z', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M9 12l2 2 4-4.2', ...stroke, 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
        ])
      case 'form':
      default:
        return h('svg', common, [
          h('path', { d: 'M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5z', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M14 3.5V8h4', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M9 12.5h6M9 15.5h6', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
    }
  },
}
</script>

<style scoped lang="scss">
.mw-page { min-height: 100vh; background: #FFFFFF; }
.mw-main { max-width: 1200px; margin: 0 auto; padding: 32px 24px 80px; }

.mw-hero { text-align: center; margin-bottom: 24px; }
.mw-hero__title {
  font-size: 30px; font-weight: 800; margin: 0 0 6px; letter-spacing: -.5px;
  background: linear-gradient(135deg, #0f172a 0%, #3B6EF5 120%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.mw-hero__sub { font-size: 14px; color: #64748b; margin: 0; }

.mw-progress { margin-bottom: 24px; }
.mw-progress__bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.mw-progress__fill { height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0); border-radius: 999px; transition: width .4s ease; }
.mw-progress__text { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: #94a3b8; text-align: center; margin-top: 8px; }

.mw-steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 24px; }
.mw-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 6px; border-radius: 12px; border: 1.5px solid transparent; background: transparent;
  cursor: pointer; transition: all .15s ease; position: relative;
  &.is-active { background: #eff6ff; border-color: #3b6ef5; }
  &.is-done .mw-step__icon { background: #ecfdf3; color: #16a34a; }
}
.mw-step__icon {
  width: 30px; height: 30px; border-radius: 9px; background: #f1f5f9; color: #64748b;
  display: flex; align-items: center; justify-content: center;
}
.mw-step__label { font-size: 11px; font-weight: 600; color: #475569; text-align: center; }
.mw-step__check {
  position: absolute; top: 4px; right: 4px; width: 14px; height: 14px; border-radius: 50%;
  background: #16a34a; color: #fff; font-size: 9px; display: flex; align-items: center; justify-content: center;
}

.mw-panel {
  background: #fff; border: 1px solid #e9edf5; border-radius: 20px;
  padding: 28px 30px; box-shadow: 0 8px 28px rgba(15,23,42,.06);
}
.mw-panel__title { font-size: 19px; font-weight: 700; color: #0f172a; margin: 0 0 18px; }

.mw-items { display: flex; flex-direction: column; gap: 14px; }

.mw-finish { text-align: center; padding: 20px 0; }
.mw-finish__text { color: #475569; font-size: 14px; margin: 0 0 20px; line-height: 1.6; }
.mw-finish__cta {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0;
  padding: 14px 28px; border-radius: 14px; font-size: 15px; font-weight: 700; cursor: pointer;
  box-shadow: 0 10px 24px rgba(15,23,42,.18);
}

.mw-issues { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
.mw-issue {
  font-size: 12.5px; padding: 10px 14px; border-radius: 10px; display: flex; flex-direction: column; gap: 2px;
  &.is-error, &.is-critical { background: #fef2f2; color: #b91c1c; }
  &.is-warning { background: #fffbeb; color: #b45309; }
  &.is-info { background: #eff6ff; color: #1e40af; }
}

.mw-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.mw-footer__skip {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
  padding: 12px 20px; border-radius: 12px; font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.mw-footer__next {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff; border: 0;
  padding: 12px 26px; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px rgba(59,110,245,.25);
  &.is-disabled { background: #e2e8f0; color: #94a3b8; box-shadow: none; cursor: not-allowed; }
}

@media (max-width: 640px) {
  .mw-steps { grid-template-columns: repeat(3, 1fr); }
}

// ============================================================ //
// 签证表格：6 大类收尾 — 嵌在面板里的 OrderNew 风格表单样式            //
// ============================================================ //
.mw-form-ocr-hint {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: #F0FDF4; border: 1px solid #86EFAC;
  border-radius: 999px; font-size: 12px; color: #166534;
  margin-bottom: 16px;
}
.mw-form-ocr-icon { color: #16A34A; }

// ---- Tabs (与 OrderNew 同款) ----
.form-tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; align-items: center; }
.form-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; font-size: 13px; font-weight: 500;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px; color: var(--ink-3, #64748B); cursor: pointer;
  transition: all .15s;
}
.form-tab:hover { border-color: #3B6EF5; color: #2D5BFF; }
/* W47c: 统一品牌主色蓝 (跟步骤条 .mw-step.is-active 同源 #3B6EF5)。
   之前 done 用绿 (#16A34A) + active 用蓝 (#3B6EF5), 两种语义两种色 → 割裂。
   现在:
   - active: 蓝填充 + 白字
   - done:   蓝填充(浅) + 蓝字 + 蓝勾 (浅一档, 跟 active 形成层级差但不抢色)
   - todo:   白底灰字
*/
.form-tab.on { background: #3B6EF5; color: #fff; border-color: #3B6EF5; font-weight: 600; }
.form-tab.done { background: rgba(59, 110, 245, .08); color: #3B6EF5; border-color: rgba(59, 110, 245, .35); font-weight: 600; }
.form-tab.done .form-tab__check { color: #3B6EF5; }
.form-tab.on.done { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.form-tabs__counter { margin-left: auto; font-size: 12px; font-weight: 600; color: #3B6EF5; background: rgba(59, 110, 245, .08); padding: 6px 12px; border-radius: 999px; letter-spacing: 0.2px; }
.form-tab.on.done .form-tab__check { color: #fff; }
.form-tab__check--empty { color: #94A3B8; }
.form-tab.on .form-tab__check--empty { color: rgba(255,255,255,.7); }

// ---- Form Card ----
.form-card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 24px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
  margin-bottom: 20px;
  @media (max-width: 480px) { padding: 18px 16px; }
}
.form-card__title {
  margin: 0 0 18px; font-size: 17px; font-weight: 600;
  color: var(--ink-1, #0F172A);
  display: flex; align-items: center; gap: 8px;
  &::before {
    content: ''; width: 3px; height: 16px; background: #3B6EF5; border-radius: 2px;
  }
}

.itinerary-preview {
  margin-top: 18px; border: 1px dashed #cbd5e1; border-radius: 12px;
  padding: 14px 16px; background: #f8fafc;
}
.itinerary-preview__title { font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 8px; }
.itinerary-preview__text {
  font-family: 'SF Mono', Menlo, monospace; font-size: 12.5px; color: #0f172a;
  white-space: pre-wrap; margin: 0; line-height: 1.6;
}

.form-grid {
  display: grid; gap: 16px 20px;
  grid-template-columns: 1fr 1fr;
  @media (max-width: 640px) { grid-template-columns: 1fr; }
}
.form-cell { position: relative; display: flex; flex-direction: column; }
.form-cell--full { grid-column: 1 / -1; }
.form-cell__label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--ink-2, #334155); margin-bottom: 6px;
}
.form-cell__required { color: var(--el-color-danger, #DC2626); margin-left: 2px; }
.form-cell__error { margin-top: 4px; font-size: 12px; color: var(--el-color-danger, #DC2626); }
.form-cell__ocr {
  position: absolute; right: 0; top: 0;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 8px; background: #EAF0FE; color: #2D5BFF;
  border-radius: 999px; font-size: 10px; font-weight: 600;
  letter-spacing: 0.04em;
  margin-top: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-cell__select {
  width: 100%; height: 40px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; padding: 0 12px;
  background: #fff; font-size: 14px; color: var(--ink-1, #0F172A);
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'><path d='M1 1l5 5 5-5' stroke='%2394A3B8' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
  transition: border-color .15s, box-shadow .15s;
}
.form-cell__select:focus { outline: none; border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59,110,245,.15); }
.form-cell__select.is-error { border-color: #DC2626; }
.radio-group { display: flex; gap: 8px; }
.radio-pill {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 14px;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; cursor: pointer;
  font-size: 14px; color: var(--ink-2, #334155);
  transition: all .15s;
  input { position: absolute; opacity: 0; pointer-events: none; }
}
.radio-pill:hover { border-color: #3B6EF5; }
.radio-pill.on { background: #EAF0FE; border-color: #3B6EF5; color: #2D5BFF; font-weight: 600; }

// ---- Form Footer ----
.form-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-top: 4px;
  @media (max-width: 480px) { flex-direction: column-reverse; align-items: stretch; }
}
.form-footer__right { display: flex; gap: 8px; }
.form-footer__prev,
.form-footer__next,
.form-footer__submit {
  border: 0; cursor: pointer;
  padding: 12px 20px; border-radius: 12px; font-size: 14px; font-weight: 700;
  transition: all .15s;
}
.form-footer__prev {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
}
.form-footer__prev:disabled { opacity: .4; cursor: not-allowed; }
.form-footer__next {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff;
  box-shadow: 0 8px 20px rgba(59,110,245,.25);
}
.form-footer__submit {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff;
  padding: 12px 26px; box-shadow: 0 10px 24px rgba(15,23,42,.18);
}
.form-footer__submit:disabled { opacity: .6; cursor: not-allowed; }
.form-footer__retry {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
  padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer;
  margin-left: 12px;
}

// ---- State Block ----
.state-block {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 40px; text-align: center;
  color: var(--ink-3, #64748B); font-size: 14px;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.state-block--err { color: #DC2626; }
.state-block--err p { margin: 0; }
.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #3B6EF5; border-top-color: transparent;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
