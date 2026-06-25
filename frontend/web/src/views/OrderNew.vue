<template>
  <div class="ordernew-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
        <span v-if="auth.user" class="app-header__user">👋 {{ auth.user.nickname || auth.user.phone }}</span>
      </div>
    </header>

    <main class="app-container app-page ordernew-shell">
      <!-- Top country + progress -->
      <div class="hero">
        <div class="hero__left">
          <div class="hero__country">
            <span class="hero__flag">{{ flagEmoji(destination?.country_code || 'US') }}</span>
            <div>
              <h1 class="hero__title">
                {{ destination?.country_name || '—' }} ·
                <span class="hero__visa">{{ visaTypeLabel }}</span>
              </h1>
              <p v-if="prefillPercent > 0" class="hero__ocr" data-testid="ordernew-ocr-pct">
                <span class="hero__ocr-icon">⚡</span>
                <span>{{ t('orders.ocr_prefilled', { percent: prefillPercent }) }}</span>
              </p>
            </div>
          </div>
        </div>
        <div class="hero__right">
          <button
            class="hero__back"
            @click="goBackMaterials"
            data-testid="ordernew-back"
          >← {{ t('orders.btn_back_materials') }}</button>
        </div>
      </div>

      <!-- W25 redesign: 5-step 拉链/锯齿状 wizard nav (matches Destinations zigzag style) -->
      <nav class="wizard" role="navigation" aria-label="签证申请步骤">
        <template v-for="(step, idx) in wizardSteps" :key="step.key">
          <button
            class="wizard__step"
            :class="{
              'is-done': step.status === 'done',
              'is-active': step.status === 'active',
              'is-pending': step.status === 'pending',
              'is-locked': step.status === 'locked',
            }"
            :disabled="step.status === 'locked' || step.status === 'pending'"
            :data-testid="`ordernew-wizard-${step.key}`"
            @click="onWizardStepClick(step)"
          >
            <span class="wizard__num">
              <template v-if="step.status === 'done'">✓</template>
              <template v-else>{{ idx + 1 }}</template>
            </span>
            <span class="wizard__body">
              <span class="wizard__title">{{ t(step.titleKey) }}</span>
              <span class="wizard__sub">{{ t(step.subKey) }}</span>
            </span>
          </button>
          <!-- Zigzag connector between steps -->
          <div
            v-if="idx < wizardSteps.length - 1"
            class="wizard__zip"
            :class="{
              'is-done': step.status === 'done' && wizardSteps[idx + 1].status !== 'pending',
              'is-active': step.status === 'active',
            }"
            aria-hidden="true"
          >
            <svg viewBox="0 0 32 24" preserveAspectRatio="none">
              <polygon
                points="0,12 6,0 12,12 18,0 24,12 30,0 32,12 30,24 24,12 18,24 12,12 6,24 0,12"
                fill="currentColor"
              />
            </svg>
          </div>
        </template>
      </nav>

      <!-- Sub-step tabs (only visible when wizard is on "fill" step) -->
      <nav v-if="wizardActiveStep === 'fill'" class="form-tabs" role="tablist">
        <button
          v-for="tab in subTabs"
          :key="tab.key"
          class="form-tab"
          :class="{ on: activeTab === tab.key, done: isTabDone(tab.key) }"
          :data-testid="`ordernew-tab-${tab.key}`"
          role="tab"
          :aria-selected="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          <span class="form-tab__check" v-if="isTabDone(tab.key)">✓</span>
          <span class="form-tab__check form-tab__check--empty" v-else>•</span>
          <span>{{ t(tab.label) }}</span>
        </button>
      </nav>

      <!-- Loading/Error -->
      <div v-if="loading" class="state-block" data-testid="ordernew-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('common.loading') }}
      </div>
      <div v-else-if="loadError" class="state-block state-block--err" data-testid="ordernew-error">
        <p>❌ {{ loadError }}</p>
        <AppButton ref="retryBtnRef" variant="outline" size="md" data-testid="ordernew-retry">{{ t('common.retry') }}</AppButton>
      </div>

      <template v-else>
        <!-- ============== Basic ============== -->
        <section v-show="activeTab === 'basic'" class="form-card" data-testid="ordernew-section-basic">
          <h2 class="form-card__title">{{ t('orders.section_basic') }}</h2>

          <div class="form-grid">
            <div class="form-cell">
              <AppInput
                v-model="form.surname"
                :label="t('orders.field_surname')"
                :placeholder="'SANTOSO'"
                :error="errors.surname"
                required
                maxlength="64"
                data-testid="ordernew-surname"
              />
              <span v-if="ocrMarked.surname" class="form-cell__ocr" data-testid="ordernew-ocr-surname">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.given_name"
                :label="t('orders.field_given_name')"
                :placeholder="'BUDI'"
                :error="errors.given_name"
                required
                maxlength="64"
                data-testid="ordernew-given-name"
              />
              <span v-if="ocrMarked.given_name" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <div class="form-cell">
              <label class="form-cell__label">
                {{ t('orders.field_sex') }}<span class="form-cell__required">*</span>
              </label>
              <div class="radio-group" data-testid="ordernew-sex">
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
              <AppInput
                v-model="form.dob"
                :label="t('orders.field_dob')"
                type="date"
                :error="errors.dob"
                required
                :max="todayIso"
                data-testid="ordernew-dob"
              />
              <span v-if="ocrMarked.dob" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <div class="form-cell">
              <label class="form-cell__label">
                {{ t('orders.field_nationality') }}<span class="form-cell__required">*</span>
              </label>
              <select
                v-model="form.nationality"
                class="form-cell__select"
                :class="{ 'is-error': !!errors.nationality }"
                data-testid="ordernew-nationality"
              >
                <option value="">— {{ t('orders.placeholder_select') }} —</option>
                <option v-for="n in nationalities" :key="n.code" :value="n.code">
                  {{ n.flag }} {{ t(n.nameKey) }}
                </option>
              </select>
              <span v-if="errors.nationality" class="form-cell__error">{{ errors.nationality }}</span>
              <span v-else-if="ocrMarked.nationality" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.passport_no"
                :label="t('orders.field_passport_no')"
                :placeholder="'A12345678'"
                :error="errors.passport_no"
                required
                maxlength="12"
                data-testid="ordernew-passport-no"
              />
              <span v-if="ocrMarked.passport_no" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.passport_expiry"
                :label="t('orders.field_passport_expiry')"
                type="date"
                :error="errors.passport_expiry"
                :min="minPassportExpiry"
                data-testid="ordernew-passport-expiry"
              />
              <span v-if="ocrMarked.passport_expiry" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
            </div>

            <!-- A-W9-2: affiliate source (aff_code) - from affiliate link /?aff=AFF001 or manual input -->
            <div class="form-cell form-cell--full">
              <AppInput
                v-model="form.aff_code"
                :label="t('affiliate.code_label')"
                :placeholder="t('affiliate.code_placeholder')"
                :hint="affiliateHint"
                :error="errors.aff_code"
                maxlength="32"
                data-testid="ordernew-aff-code"
              >
                <template #suffix>
                  <span v-if="affiliateAuto" class="form-cell__ocr" data-testid="ordernew-aff-auto">⚡ {{ t('affiliate.code_auto') }}</span>
                </template>
              </AppInput>
            </div>
          </div>
        </section>

        <!-- ============== Travel ============== -->
        <section v-show="activeTab === 'travel'" class="form-card" data-testid="ordernew-section-travel">
          <h2 class="form-card__title">{{ t('orders.section_travel') }}</h2>

          <div class="form-grid">
            <div class="form-cell">
              <label class="form-cell__label">
                {{ t('orders.field_destination') }}<span class="form-cell__required">*</span>
              </label>
              <select
                v-model="form.destination_id"
                class="form-cell__select"
                :class="{ 'is-error': !!errors.destination_id }"
                data-testid="ordernew-destination"
              >
                <option value="">— {{ t('orders.placeholder_select') }} —</option>
                <option v-for="d in destinations" :key="d.id" :value="d.id" :disabled="!d.enabled">
                  {{ flagEmoji(d.country_code) }} {{ d.country_name || t(d.country_name_key) }} ({{ d.country_code }}){{ d.enabled ? '' : ' · ' + t('dest.coming_soon') }}
                </option>
              </select>
              <span v-if="errors.destination_id" class="form-cell__error">{{ errors.destination_id }}</span>
            </div>

            <div class="form-cell">
              <label class="form-cell__label">
                {{ t('orders.field_visa_type') }}<span class="form-cell__required">*</span>
              </label>
              <div class="radio-group" data-testid="ordernew-visa-type">
                <label class="radio-pill" :class="{ on: form.visa_type === 'tourism' }">
                  <input v-model="form.visa_type" type="radio" value="tourism" />
                  <span>✈ {{ t('orders.visa_tourism') }}</span>
                </label>
                <label class="radio-pill" :class="{ on: form.visa_type === 'student' }">
                  <input v-model="form.visa_type" type="radio" value="student" />
                  <span>🎓 {{ t('orders.visa_student') }}</span>
                </label>
              </div>
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.arrival_date"
                :label="t('orders.field_arrival_date')"
                type="date"
                :error="errors.arrival_date"
                required
                :min="todayIso"
                data-testid="ordernew-arrival"
              />
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.departure_date"
                :label="t('orders.field_departure_date')"
                type="date"
                :error="errors.departure_date"
                required
                :min="form.arrival_date || todayIso"
                data-testid="ordernew-departure"
              />
            </div>

            <div class="form-cell">
              <AppInput
                v-model.number="form.stay_days"
                :label="t('orders.field_stay_days')"
                type="number"
                :error="errors.stay_days"
                min="1"
                max="365"
                :hint="stayDaysHint"
                data-testid="ordernew-stay-days"
              />
            </div>
          </div>
        </section>

        <!-- ============== Emergency ============== -->
        <section v-show="activeTab === 'emergency'" class="form-card" data-testid="ordernew-section-emergency">
          <h2 class="form-card__title">{{ t('orders.section_emergency') }}</h2>

          <div class="form-grid">
            <div class="form-cell">
              <AppInput
                v-model="form.emergency_name"
                :label="t('orders.field_emergency_name')"
                :placeholder="t('orders.field_emergency_name')"
                :error="errors.emergency_name"
                required
                maxlength="64"
                data-testid="ordernew-emergency-name"
              />
            </div>

            <div class="form-cell">
              <AppInput
                v-model="form.emergency_phone"
                :label="t('orders.field_emergency_phone')"
                :placeholder="t('orders.placeholder_phone')"
                :error="errors.emergency_phone"
                required
                inputmode="numeric"
                maxlength="20"
                data-testid="ordernew-emergency-phone"
              />
            </div>

            <div class="form-cell">
              <label class="form-cell__label">
                {{ t('orders.field_emergency_relation') }}<span class="form-cell__required">*</span>
              </label>
              <select
                v-model="form.emergency_relation"
                class="form-cell__select"
                :class="{ 'is-error': !!errors.emergency_relation }"
                data-testid="ordernew-emergency-relation"
              >
                <option value="">— {{ t('orders.placeholder_select') }} —</option>
                <option v-for="r in relations" :key="r.value" :value="r.value">{{ t(r.label) }}</option>
              </select>
              <span v-if="errors.emergency_relation" class="form-cell__error">{{ errors.emergency_relation }}</span>
            </div>
          </div>
        </section>

        <!-- Bottom actions - W3 root-fix: AppButton + ref.onTrigger pattern (Option 1) -->
        <footer class="form-footer">
          <AppButton ref="prevBtnRef" variant="ghost" size="md" :disabled="!hasPrevTab" data-testid="ordernew-prev">← {{ t('orders.btn_prev') }}</AppButton>
          <div class="form-footer__right">
            <AppButton
              v-if="!isLastTab"
              ref="nextBtnRef"
              variant="primary"
              size="md"
              data-testid="ordernew-next"
            >{{ t('orders.btn_next') }} →</AppButton>
            <AppButton
              v-else
              ref="submitBtnRef"
              variant="primary"
              size="lg"
              :loading="submitting"
              data-testid="ordernew-submit"
            >{{ submitting ? t('orders.btn_submitting') : t('orders.btn_submit') }}</AppButton>
          </div>
        </footer>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  fetchMaterialsForForm,
  extractApplicantDraft,
  createOrder
} from '@/api/orders'
import { listDestinations } from '@/api/destinations'
// A-W9-2: affiliate wrapper - affiliate link auto-fill + submit-time attribute
import { trackClick, attributeOrder, loadPendingClick, savePendingClick } from '@/api/affiliate'

const { t, te, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

// Country List (V2 first batch 9 countries, aligned with destinations API)
const destinations = ref([])
const loading = ref(false)
const loadError = ref('')
const submitting = ref(false)

const todayIso = new Date().toISOString().slice(0, 10)
const minPassportExpiry = (() => {
  const d = new Date()
  d.setMonth(d.getMonth() + 6)
  return d.toISOString().slice(0, 10)
})()

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
const nationalities = computed(() => nationalityOptions)

const relations = [
  { value: 'spouse', label: 'orders.relation_spouse' },
  { value: 'parent', label: 'orders.relation_parent' },
  { value: 'child', label: 'orders.relation_child' },
  { value: 'sibling', label: 'orders.relation_sibling' },
  { value: 'friend', label: 'orders.relation_friend' },
  { value: 'colleague', label: 'orders.relation_colleague' },
  { value: 'other', label: 'orders.relation_other' }
]

// 5-step wizard (拉链/锯齿状导航)
//   1. 选国家  2. 选签证  3. 填表 (含 3 个 sub-tab)  4. 付款  5. RPA 提交
// current step status: done | active | pending | locked
const subTabs = [
  { key: 'basic', label: 'orders.tab_basic' },
  { key: 'travel', label: 'orders.tab_travel' },
  { key: 'emergency', label: 'orders.tab_emergency' }
]
const activeTab = ref('basic')

// Map current destination/visa/form progress into wizard step status
const wizardActiveStep = ref('fill')   // 'country' | 'visa' | 'fill' | 'pay' | 'rpa'

// All 5 wizard steps — status computed reactively from current state
const wizardSteps = computed(() => {
  // W25 logic:
  //   - country:  always done (came from /destinations with ?country=XX)
  //   - visa:     always done (came with ?type=tourism)
  //   - fill:     active when on this page
  //   - pay:      pending until submit
  //   - rpa:      pending
  const current = wizardActiveStep.value
  const order = ['country', 'visa', 'fill', 'pay', 'rpa']
  return [
    { key: 'country', titleKey: 'orders.wz_country', subKey: 'orders.wz_country_sub', status: 'done' },
    { key: 'visa',    titleKey: 'orders.wz_visa',    subKey: 'orders.wz_visa_sub',    status: 'done' },
    { key: 'fill',    titleKey: 'orders.wz_fill',    subKey: 'orders.wz_fill_sub',    status: 'active' },
    { key: 'pay',     titleKey: 'orders.wz_pay',     subKey: 'orders.wz_pay_sub',     status: 'pending' },
    { key: 'rpa',     titleKey: 'orders.wz_rpa',     subKey: 'orders.wz_rpa_sub',     status: 'pending' },
  ]
})

function onWizardStepClick(step) {
  // Only "done" or "active" steps are clickable; locked/pending are no-op
  if (step.status === 'pending' || step.status === 'locked') return
  // In this MVP, only "fill" is interactive on this page.
  // Future: wire up "country" → /destinations, "pay" → payment, "rpa" → /rpa/submit
  if (step.key === 'country') {
    router.push('/destinations')
  } else if (step.key === 'fill') {
    wizardActiveStep.value = 'fill'
  }
}

// Query params
const materialIds = computed(() => {
  const raw = (route.query.material_ids || '').toString()
  return raw.split(',').map((s) => s.trim()).filter(Boolean)
})
const visaType = computed(() => (route.query.visa_type || 'tourism').toString())
const countryCode = computed(() => (route.query.country || '').toString())

// Form state
const form = reactive({
  surname: '',
  given_name: '',
  sex: '',
  dob: '',
  nationality: '',
  passport_no: '',
  passport_expiry: '',
  destination_id: '',
  visa_type: visaType.value,
  arrival_date: '',
  departure_date: '',
  stay_days: 7,
  emergency_name: '',
  emergency_phone: '',
  emergency_relation: '',
  // A-W9-2: affiliate source (optional) - from affiliate link /?aff=AFF001 or manual input
  aff_code: ''
})
const errors = reactive({
  surname: '', given_name: '', sex: '', dob: '', nationality: '',
  passport_no: '', passport_expiry: '', destination_id: '',
  arrival_date: '', departure_date: '', stay_days: '',
  emergency_name: '', emergency_phone: '', emergency_relation: '',
  aff_code: ''
})
// OCR marker: which fields auto-filled from materials (show "⚡ AUTO · OCR" badge)
const ocrMarked = reactive({
  surname: false, given_name: false, sex: false, dob: false,
  nationality: false, passport_no: false, passport_expiry: false
})
const prefillPercent = ref(0)

// ============== A-W9-2: affiliate source ==============
// click_id (from affiliate link /?aff=AFF001&click=cid_xxx or LS) - bind attribute on order submit
// aff_code is affiliate code, affiliateAuto flag if auto-filled (manually changed becomes false)
const pendingClick = ref(null)  // { click_id, aff_code, ts }
const affiliateAuto = ref(false)  // Auto-prefill flag (⚡ badge)
const affiliateHint = computed(() => {
  if (form.aff_code && affiliateAuto.value) {
    return t('affiliate.code_hint_auto', { code: form.aff_code })
  }
  return t('affiliate.code_hint_optional')
})

// Read aff_code from URL query or LS, auto-mint click_id and track
function autoFillAffiliate() {
  // 1) URL priority: /?aff=AFF001&click=cid_xxx
  const urlAff = (route.query.aff || '').toString().trim()
  const urlClick = (route.query.click || '').toString().trim()
  if (urlAff && /^[A-Za-z0-9_-]{4,32}$/.test(urlAff)) {
    form.aff_code = urlAff
    affiliateAuto.value = true
    const clickId = urlClick && /^[A-Za-z0-9_-]{4,64}$/.test(urlClick) ? urlClick : null
    // track + save
    trackClick({ aff_code: urlAff, click_id: clickId, landing_path: route.fullPath || '/' })
      .then((r) => {
        if (r?.click_id) {
          savePendingClick({ click_id: r.click_id, aff_code: urlAff, landing_path: route.fullPath || '/' })
          pendingClick.value = { click_id: r.click_id, aff_code: urlAff, ts: Date.now() }
        }
      })
      .catch((e) => { console.warn('[ordernew] trackClick failed:', e?.message) })
    return
  }
  // 2) LS fallback: affiliate click from last session
  const stored = loadPendingClick()
  if (stored && stored.aff_code) {
    form.aff_code = stored.aff_code
    affiliateAuto.value = true
    pendingClick.value = stored
  }
}

// After user manually changes aff_code, auto badge cancels (avoid misinterpreting as URL prefill)
let _initialAffCode = ''
watch(() => form.aff_code, (v) => {
  if (affiliateAuto.value && v !== _initialAffCode) {
    affiliateAuto.value = false
  }
})

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

// Watch travel dates, auto-calc stay_days
watch([() => form.arrival_date, () => form.departure_date], () => {
  if (form.arrival_date && form.departure_date) {
    const a = new Date(form.arrival_date)
    const b = new Date(form.departure_date)
    if (b >= a) {
      form.stay_days = Math.round((b - a) / 86400000) + 1
    }
  }
})

// visa_type label: use te() check key exists then translate, else fallback
const visaTypeLabel = computed(() => {
  const k = `orders.visa_${form.visa_type || 'tourism'}`
  return te(k) ? t(k) : t('orders.visa_tourism')
})

// Watch destination linkage
const destination = computed(() => {
  return destinations.value.find(
    (d) => d.id === Number(form.destination_id) || d.country_code === countryCode.value
  )
})

function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}

function isTabDone(key) {
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

const currentTabIndex = computed(() => tabs.findIndex((x) => x.key === activeTab.value))
const isLastTab = computed(() => currentTabIndex.value === tabs.length - 1)
const hasPrevTab = computed(() => currentTabIndex.value > 0)

function goNext() {
  if (!validateTab(activeTab.value, { silent: true })) {
    validateTab(activeTab.value, { silent: false })
    return
  }
  if (!isLastTab.value) {
    activeTab.value = tabs[currentTabIndex.value + 1].key
  }
}
function goPrev() {
  if (hasPrevTab.value) {
    activeTab.value = tabs[currentTabIndex.value - 1].key
  }
}

// ============== Validation ==============
function clearErrors() {
  Object.keys(errors).forEach((k) => { errors[k] = '' })
}

function validateTab(tabKey, { silent = false } = {}) {
  if (silent) clearErrors()
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
  // A-W9-2: aff_code optional, but if filled must match 4-32 [A-Za-z0-9_-] format
  if (form.aff_code && !/^[A-Za-z0-9_-]{4,32}$/.test(form.aff_code.trim())) {
    ok = false
    if (!silent) errors.aff_code = t('affiliate.err_format')
  }
  return ok
}

function validateAll() {
  clearErrors()
  const r1 = validateTab('basic', { silent: true })
  const r2 = validateTab('travel', { silent: true })
  const r3 = validateTab('emergency', { silent: true })
  if (!r1) validateTab('basic', { silent: false })
  else if (!r2) {
    activeTab.value = 'travel'
    validateTab('travel', { silent: false })
  } else if (!r3) {
    activeTab.value = 'emergency'
    validateTab('emergency', { silent: false })
  }
  return r1 && r2 && r3
}

// ============== Loading ==============
async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    // 1) destinations - hardcode fallback, real API failure degrades silently, no toast
    destinations.value = FALLBACK_DESTINATIONS
    try {
      const real = await listDestinations({ lang: locale.value || 'zh-CN' })
      if (Array.isArray(real) && real.length > 0) {
        destinations.value = real
      }
    } catch (e) {
      console.warn('[ordernew] destinations load failed, using fallback:', e?.message)
    }
    // Default destination linkage
    if (countryCode.value) {
      const d = destinations.value.find((x) => x.country_code === countryCode.value)
      if (d) form.destination_id = d.id
    }
    if (!form.destination_id && destinations.value.length) {
      const us = destinations.value.find((x) => x.country_code === 'US' && x.enabled)
      form.destination_id = (us || destinations.value[0]).id
    }

    // 2) materials -> OCR prefill
    const ids = materialIds.value
    let mats = []
    if (ids.length > 0) {
      mats = await fetchMaterialsForForm(ids)
    }
    const { draft, percent } = extractApplicantDraft(mats)
    prefillPercent.value = percent
    for (const k of Object.keys(draft)) {
      if (draft[k]) {
        form[k] = draft[k]
        ocrMarked[k] = true
      }
    }
    // Default travel dates: today + 30 / today + 37 / 7 days (give user a starting point)
    if (!form.arrival_date) {
      const a = new Date(); a.setDate(a.getDate() + 30)
      form.arrival_date = a.toISOString().slice(0, 10)
    }
    if (!form.departure_date) {
      const b = new Date(); b.setDate(b.getDate() + 37)
      form.departure_date = b.toISOString().slice(0, 10)
    }
    form.visa_type = visaType.value
  } catch (e) {
    loadError.value = e?.message || t('orders.load_failed')
  } finally {
    loading.value = false
  }
}

// Fallback: when B backend /v2/destinations not ready or DB missing table (V2 first batch 9 countries)
const FALLBACK_DESTINATIONS = [
  { id: 1, country_code: 'US', country_name_key: 'country.us', visa_types: ['tourism', 'student'], enabled: true },
  { id: 2, country_code: 'JP', country_name_key: 'country.jp', visa_types: ['tourism', 'student'], enabled: false },
  { id: 3, country_code: 'UK', country_name_key: 'country.uk', visa_types: ['tourism', 'student'], enabled: false },
  { id: 4, country_code: 'AU', country_name_key: 'country.au', visa_types: ['tourism', 'student'], enabled: false },
  { id: 5, country_code: 'CA', country_name_key: 'country.ca', visa_types: ['tourism', 'student'], enabled: false },
  { id: 6, country_code: 'DE', country_name_key: 'country.de_schengen', visa_types: ['tourism', 'student'], enabled: false },
  { id: 7, country_code: 'FR', country_name_key: 'country.fr_schengen', visa_types: ['tourism', 'student'], enabled: false },
  { id: 8, country_code: 'SG', country_name_key: 'country.sg', visa_types: ['tourism', 'student'], enabled: false },
  { id: 9, country_code: 'NZ', country_name_key: 'country.nz', visa_types: ['tourism', 'student'], enabled: false }
]

async function onSubmit() {
  submitting.value = true
  try {
    const payload = {
      destination_id: Number(form.destination_id),
      visa_type: form.visa_type,
      material_ids: materialIds.value.filter(Boolean),
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
        emergency_contact: {
          name: form.emergency_name.trim(),
          phone: form.emergency_phone.trim(),
          relation: form.emergency_relation
        }
      },
      // A-W9-2: affiliate source (aff_code from affiliate link + last minted click_id)
      aff_code: (form.aff_code || '').trim(),
      click_id: (pendingClick.value?.click_id || '').trim()
    }
    const order = await createOrder(payload)
    // A-W9-2: after order created, bind click_id to order_id (backend affiliate attribute)
    // attribute failure does not affect order success toast (user already ordered, just affiliate attribution failed)
    if (payload.aff_code && payload.click_id && order?.order_no) {
      attributeOrder({ order_id: order.order_no, click_id: payload.click_id })
        .then(() => { console.log('[ordernew] attribute ok') })
        .catch((e) => { console.warn('[ordernew] attribute failed:', e?.message) })
    }
    toast.success(t('orders.submit_success'))
    setTimeout(() => {
      // W19: rpa submit needs country_code + visa_type + passport_data (align with backend Pydantic schema).
      // Look up country_code from the resolved destination.
      const destCountry = (destination.value && destination.value.country_code) || ''
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
      // Stash passport data in sessionStorage so RpaSubmit can pick it up
      // (URL query is too long; history.state is not always preserved across
      // router.push when the target page is a separate chunk).
      try {
        sessionStorage.setItem(`rpa_passport_${order.order_no}`, JSON.stringify(passportData))
      } catch (e) { /* sessionStorage may be unavailable */ }
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

function goBackMaterials() {
  router.push({ name: 'Materials', query: route.query })
}

// ============== W3 P0 root-fix: ref + onTrigger pattern ==============
// 4 AppButtons use ref to expose onTrigger, Vue @click bubbling no longer depends on AppButton internals
// W6-7 robustness: next/submit is v-if mutex, ref remounts on isLastTab switch, need watch + nextTick re-inject
const retryBtnRef = ref(null)
const prevBtnRef = ref(null)
const nextBtnRef = ref(null)
const submitBtnRef = ref(null)

// W6-7 defensive inject: extract to function, onMounted + watch isLastTab both call
function injectBottomButtons() {
  if (retryBtnRef.value) retryBtnRef.value.setOnTrigger(loadAll)
  if (prevBtnRef.value) prevBtnRef.value.setOnTrigger(goPrev)
  if (nextBtnRef.value) nextBtnRef.value.setOnTrigger(goNext)
  if (submitBtnRef.value) submitBtnRef.value.setOnTrigger(onSubmit)
}

onMounted(async () => {
  auth.hydrate()
  // A-W9-2: fill affiliate first (URL/LS), then loadAll (avoid being overwritten after prefill)
  autoFillAffiliate()
  _initialAffCode = form.aff_code
  await loadAll()
  // First inject (retry/prev persistent, next/submit decide mount by isLastTab)
  injectBottomButtons()
})

// W6-7 robustness: next/submit is v-if mutex - ref remounts on isLastTab flip
// onMounted only runs once, newly mounted ref without setOnTrigger silently fails
// Use watch(isLastTab) + nextTick to re-inject immediately after v-if switch (only inject the flipped one)
watch(isLastTab, async (val) => {
  await nextTick()
  if (val) {
    if (submitBtnRef.value) submitBtnRef.value.setOnTrigger(onSubmit)
  } else {
    if (nextBtnRef.value) nextBtnRef.value.setOnTrigger(goNext)
  }
})
</script>

<style scoped lang="scss">
.ordernew-page { min-height: 100vh; background: var(--bg-alt, #F8FAFC); }
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; background: #fff; border-bottom: 1px solid var(--border, #E2E8F0);
}
.app-header__brand { display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--ink, #1A1D29); font-weight: 600; }
.app-header__brand-mark { width: 28px; height: 28px; border-radius: 8px; background: #3B6EF5; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
.app-header__right { display: flex; align-items: center; gap: 12px; }
.app-header__user { font-size: 13px; color: var(--ink-3, #64748B); }

.ordernew-shell { max-width: 960px; margin: 0 auto; padding: 24px 20px 60px; }

// ============== Hero ==============
.hero {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 16px;
  flex-wrap: wrap;
}
.hero__country { display: flex; align-items: center; gap: 14px; }
.hero__flag { font-size: 36px; }
.hero__title { margin: 0; font-size: 24px; font-weight: 700; color: var(--ink-1, #0F172A); }
.hero__visa { color: var(--el-color-primary, #3B6EF5); }
.hero__ocr {
  margin: 6px 0 0; display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; background: #F0FDF4; border: 1px solid #86EFAC;
  border-radius: 999px; font-size: 12px; color: #166534;
  max-width: 100%;
  box-sizing: border-box;
}
.hero__ocr-icon { color: #16A34A; }
.hero__back {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; padding: 8px 14px; font-size: 13px;
  color: var(--ink-2, #334155); cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.hero__back:hover { background: #F8FAFC; }

@media (max-width: 600px) {
  .hero { gap: 10px; }
  .hero__flag { font-size: 28px; }
  .hero__title { font-size: 18px; }
  .hero__back { padding: 6px 10px; font-size: 12px; }
}

// ============== Tabs ==============
.form-tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
.form-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; font-size: 13px; font-weight: 500;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px; color: var(--ink-3, #64748B); cursor: pointer;
  transition: all .15s;
}
.form-tab:hover { border-color: #3B6EF5; color: #2D5BFF; }
.form-tab.on { background: #3B6EF5; color: #fff; border-color: #3B6EF5; font-weight: 600; }
.form-tab.done .form-tab__check { color: #16A34A; }
.form-tab.on.done .form-tab__check { color: #fff; }
.form-tab__check--empty { color: #94A3B8; }
.form-tab.on .form-tab__check--empty { color: rgba(255,255,255,.7); }

/* ============================================================
   W25 — 5-step 拉链/锯齿状 wizard 导航 (matches Destinations zigzag)
   ============================================================ */
.wizard {
  display: flex;
  align-items: stretch;
  margin: 0 0 24px;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  border: 1px solid #E5E7EB;
}

.wizard__step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background .2s ease, color .2s ease;
  text-align: left;
  position: relative;
  z-index: 1;
}
.wizard__step:not(:disabled):hover { background: #F0F4FF; }
.wizard__step:disabled { cursor: not-allowed; }

.wizard__num {
  flex-shrink: 0;
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700;
  font-size: 15px;
  border: 2px solid #CBD5E1;
  color: #94A3B8;
  background: #fff;
  transition: all .25s ease;
}

.wizard__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.wizard__title {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wizard__sub {
  font-size: 11px;
  color: #94A3B8;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wizard__step.is-done .wizard__num {
  background: linear-gradient(135deg, #16A34A 0%, #22C55E 100%);
  border-color: #16A34A;
  color: #fff;
  box-shadow: 0 2px 6px rgba(22, 163, 74, 0.3);
}
.wizard__step.is-done .wizard__title { color: #15803D; }
.wizard__step.is-done .wizard__sub { color: #16A34A; }

.wizard__step.is-active {
  background: linear-gradient(135deg, #EEF2FF 0%, #F0F9FF 100%);
}
.wizard__step.is-active .wizard__num {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
  border-color: #3B6EF5;
  color: #fff;
  box-shadow: 0 4px 12px rgba(59, 110, 245, 0.4);
  transform: scale(1.1);
  animation: wiz-pulse 2s ease-in-out infinite;
}
.wizard__step.is-active .wizard__title { color: #1E40AF; }
.wizard__step.is-active .wizard__sub { color: #3B6EF5; font-weight: 600; }

@keyframes wiz-pulse {
  0%, 100% { box-shadow: 0 4px 12px rgba(59, 110, 245, 0.4); }
  50% { box-shadow: 0 4px 20px rgba(59, 110, 245, 0.6); }
}

.wizard__step.is-pending .wizard__num,
.wizard__step.is-locked .wizard__num {
  background: #F8FAFC;
  color: #CBD5E1;
  border-color: #E2E8F0;
}
.wizard__step.is-pending .wizard__title,
.wizard__step.is-locked .wizard__title { color: #94A3B8; font-weight: 500; }

/* zigzag connector (zip) */
.wizard__zip {
  flex-shrink: 0;
  width: 28px;
  align-self: stretch;
  display: flex;
  align-items: center;
  color: #E2E8F0;
  transition: color .25s ease;
}
.wizard__zip svg { width: 100%; height: 100%; display: block; }
.wizard__zip.is-done { color: #16A34A; }
.wizard__zip.is-active { color: #3B6EF5; }

@media (max-width: 720px) {
  .wizard { flex-direction: column; }
  .wizard__zip { width: 100%; height: 16px; }
  .wizard__zip svg { transform: rotate(90deg); }
}

// ============== Form Card ==============
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

// ============== Footer ==============
.form-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-top: 4px;
  @media (max-width: 480px) { flex-direction: column-reverse; align-items: stretch; }
  @media (max-width: 480px) { .form-footer__right { flex-direction: column; } }
}
.form-footer__right { display: flex; gap: 8px; }

// ============== State ==============
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
