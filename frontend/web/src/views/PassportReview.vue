<!-- PassportReview.vue — OCR 提取字段后,用户确认/编辑 + 自动判国籍 -->
<template>
  <div class="pr-page">
    <AppHeader scope="materials-validate" />

    <div class="pr-layout">
      <!-- 左侧步骤导航(沿用 Materials 同款) -->
      <aside class="pr-side">
        <button class="pr-side__back" @click="$router.back()">
          ← {{ t('common.back') }}
        </button>
        <ul class="pr-steps">
          <li
            v-for="(s, i) in STEPS"
            :key="s.key"
            class="pr-step"
            :class="{
              'is-active': s.key === 'docs',
              'is-done': i < 2,
            }"
          >
            <span class="pr-step__icon">{{ s.icon }}</span>
            <span class="pr-step__label">{{ s.label }}</span>
            <span v-if="i < 2" class="pr-step__check">✓</span>
          </li>
        </ul>
      </aside>

      <main class="pr-main">
        <h1 class="page-title">{{ t('pr.title', 'Review passport details') }}</h1>
        <p class="page-sub">{{ t('pr.sub', 'Auto-extracted via OCR. You can edit any field before saving.') }}</p>

        <!-- 顶部 passport 预览图 + edit 按钮 -->
        <div class="pr-passport">
          <img v-if="fileUrl" :src="fileUrl" class="pr-passport__img" alt="passport" />
          <div v-else class="pr-passport__placeholder">📘</div>
          <button class="pr-passport__edit" @click="onRetake">
            ✎ {{ t('pr.retake', 'Replace photo') }}
          </button>
        </div>

        <!-- 字段编辑 -->
        <div class="pr-fields">
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.first_name', 'First Name') }} <span class="req">*</span></label>
            <input
              v-model="form.first_name"
              class="pr-field__input"
              :placeholder="t('pr.first_name_ph', 'Given name')"
              data-testid="pr-first-name"
            />
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.last_name', 'Last Name') }}</label>
            <input
              v-model="form.last_name"
              class="pr-field__input"
              :placeholder="t('pr.last_name_ph', 'Surname')"
              data-testid="pr-last-name"
            />
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.gender', 'Gender') }} <span class="req">*</span></label>
            <div class="pr-field__select-wrap">
              <select v-model="form.gender" class="pr-field__input pr-field__select" data-testid="pr-gender">
                <option value="">{{ t('pr.please_select', 'Please select') }}</option>
                <option value="M">{{ t('pr.male', 'Male') }}</option>
                <option value="F">{{ t('pr.female', 'Female') }}</option>
                <option value="X">{{ t('pr.other', 'Other') }}</option>
              </select>
              <span class="pr-field__chev">▾</span>
            </div>
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.passport_no', 'Passport Number') }} <span class="req">*</span></label>
            <div class="pr-field__input-wrap">
              <input
                v-model="form.passport_no"
                class="pr-field__input"
                placeholder="E12345678"
                data-testid="pr-passport-no"
              />
              <button class="pr-field__icon-btn" type="button" @click="onCopyPassportNo">⧉</button>
            </div>
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.dob', 'Date of Birth') }} <span class="req">*</span></label>
            <input
              v-model="form.date_of_birth"
              class="pr-field__input"
              type="date"
              data-testid="pr-dob"
            />
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.issue_date', 'Passport Issued On') }}</label>
            <input
              v-model="form.issue_date"
              class="pr-field__input"
              type="date"
              data-testid="pr-issue"
            />
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.expiry', 'Passport Valid Till') }}</label>
            <input
              v-model="form.expiry_date"
              class="pr-field__input"
              type="date"
              data-testid="pr-expiry"
            />
          </div>
          <div class="pr-field">
            <label class="pr-field__label">{{ t('pr.nationality', 'Nationality') }} <span class="req">*</span></label>
            <div class="pr-field__select-wrap">
              <select v-model="form.nationality" class="pr-field__input pr-field__select" data-testid="pr-nationality">
                <option value="">{{ t('pr.please_select', 'Please select') }}</option>
                <option v-for="n in NATIONALITIES" :key="n.code" :value="n.code">
                  {{ n.flag }} {{ n.name }}
                </option>
              </select>
              <span class="pr-field__chev">▾</span>
            </div>
            <p v-if="autoDetectedNationality" class="pr-field__auto" data-testid="pr-auto-detected">
              ✨ {{ t('pr.auto_detected', 'Auto-detected from your passport') }}
            </p>
          </div>
        </div>

        <!-- Contact details (Atlys 风格:折叠分组) -->
        <details class="pr-section" open>
          <summary class="pr-section__title">
            <span class="pr-section__icon">📞</span>
            {{ t('pr.contact', 'Contact Details') }}
            <span class="pr-section__chev">▾</span>
          </summary>
          <p class="pr-section__hint">{{ t('pr.contact_hint', 'Required for sharing essential visa updates. In real time.') }}</p>
          <div class="pr-fields">
            <div class="pr-field">
              <label class="pr-field__label">{{ t('pr.email', 'Email') }} <span class="req">*</span></label>
              <input
                v-model="form.email"
                type="email"
                class="pr-field__input"
                placeholder="you@example.com"
                data-testid="pr-email"
              />
            </div>
            <div class="pr-field">
              <label class="pr-field__label">{{ t('pr.phone', 'Phone') }}</label>
              <input
                v-model="form.phone"
                class="pr-field__input"
                placeholder="+86 138 0000 0000"
                data-testid="pr-phone"
              />
            </div>
          </div>
        </details>

        <!-- Footer -->
        <div class="pr-footer">
          <button class="pr-btn pr-btn--ghost" @click="onRetake">
            {{ t('pr.retake_btn', 'Retake photo') }}
          </button>
          <button
            class="pr-btn pr-btn--primary"
            :class="{ 'is-disabled': !isValid }"
            :disabled="!isValid"
            data-testid="pr-confirm"
            @click="onConfirm"
          >
            {{ t('pr.confirm', 'Confirm & Continue') }} →
          </button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import { useMaterialsProgress, STEPS } from '@/composables/useMaterialsProgress'

const { t } = useI18n()
const router = useRouter()
const { state, setSlot } = useMaterialsProgress()

const NATIONALITIES = [
  { code: 'CN', flag: '🇨🇳', name: 'China' },
  { code: 'ID', flag: '🇮🇩', name: 'Indonesia' },
  { code: 'VN', flag: '🇻🇳', name: 'Vietnam' },
  { code: 'US', flag: '🇺🇸', name: 'United States' },
  { code: 'GB', flag: '🇬🇧', name: 'United Kingdom' },
  { code: 'IN', flag: '🇮🇳', name: 'India' },
  { code: 'PH', flag: '🇵🇭', name: 'Philippines' },
  { code: 'TH', flag: '🇹🇭', name: 'Thailand' },
  { code: 'MY', flag: '🇲🇾', name: 'Malaysia' },
  { code: 'SG', flag: '🇸🇬', name: 'Singapore' },
  { code: 'JP', flag: '🇯🇵', name: 'Japan' },
  { code: 'KR', flag: '🇰🇷', name: 'South Korea' },
  { code: 'AU', flag: '🇦🇺', name: 'Australia' },
  { code: 'CA', flag: '🇨🇦', name: 'Canada' },
  { code: 'FR', flag: '🇫🇷', name: 'France' },
  { code: 'DE', flag: '🇩🇪', name: 'Germany' },
  { code: 'OTHER', flag: '🌐', name: 'Other' },
]

const form = reactive({
  first_name: '',
  last_name: '',
  gender: '',
  passport_no: '',
  date_of_birth: '',
  issue_date: '',
  expiry_date: '',
  nationality: '',
  email: '',
  phone: '',
})

const fileUrl = ref('')
const autoDetectedNationality = ref(false)

const isValid = computed(() => {
  return form.first_name && form.gender && form.passport_no && form.date_of_birth && form.nationality
})

// 从 OCR 字段填表 + 启发式判国籍
function hydrateFromOCR(fields) {
  if (!fields) return
  // 兼容各种 OCR 引擎返回的 key 命名
  form.first_name   = fields.given_name || fields.first_name || fields.givenName || ''
  form.last_name    = fields.surname    || fields.last_name  || fields.familyName || ''
  form.passport_no  = fields.passport_no || fields.passportNo || fields.document_no || ''
  form.gender       = (fields.sex || fields.gender || '').toUpperCase().startsWith('F') ? 'F'
                    : (fields.sex || fields.gender || '').toUpperCase().startsWith('M') ? 'M' : ''
  form.date_of_birth = normalizeDate(fields.date_of_birth || fields.dob || fields.birth_date)
  form.issue_date   = normalizeDate(fields.issue_date || fields.date_of_issue || fields.issueDate)
  form.expiry_date  = normalizeDate(fields.expiry_date || fields.date_of_expiry || fields.expiryDate)
  // 自动判国籍
  const nat = detectNationality(fields)
  if (nat) {
    form.nationality = nat
    autoDetectedNationality.value = true
  }
}

// 把 "16 MAR 1993" / "1993-03-16" / "16/03/1993" 等都转成 YYYY-MM-DD
function normalizeDate(s) {
  if (!s) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  const months = { jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06', jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12' }
  const m = s.match(/^(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})$/)
  if (m) return `${m[3]}-${months[m[2].toLowerCase().slice(0, 3)] || '01'}-${m[1].padStart(2, '0')}`
  const m2 = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/)
  if (m2) return `${m2[3]}-${m2[2].padStart(2, '0')}-${m2[1].padStart(2, '0')}`
  return s
}

// 启发式判国籍: 看 OCR 返回里的 country/nationality 字段 + MRZ 头 3 位
function detectNationality(fields) {
  const nat = (fields.nationality || fields.country || fields.nationality_code || '').toLowerCase().trim()
  if (!nat) return ''
  // 直接匹配
  if (nat.includes('china') || nat.includes('chinese') || nat === 'cn') return 'CN'
  if (nat.includes('indonesia') || nat.includes('indonesian') || nat === 'id') return 'ID'
  if (nat.includes('vietnam') || nat.includes('vietnamese') || nat === 'vn') return 'VN'
  if (nat.includes('united states') || nat.includes('american') || nat === 'us') return 'US'
  if (nat.includes('united kingdom') || nat.includes('british') || nat === 'gb') return 'GB'
  if (nat.includes('india') || nat.includes('indian') || nat === 'in') return 'IN'
  // MRZ fallback: 头 3 位 ISO 3166-1 alpha-3
  const mrz = fields.mrz || ''
  if (mrz.length >= 3) {
    const c = mrz.slice(0, 3).toUpperCase()
    const map = { CHN: 'CN', IDN: 'ID', VNM: 'VN', USA: 'US', GBR: 'GB', IND: 'IN', PHL: 'PH', THA: 'TH', MYS: 'MY', SGP: 'SG', JPN: 'JP', KOR: 'KR', AUS: 'AU', CAN: 'CA', FRA: 'FR', DEU: 'DE' }
    if (map[c]) return map[c]
  }
  return ''
}

function onCopyPassportNo() {
  if (form.passport_no) navigator.clipboard?.writeText(form.passport_no)
}

function onRetake() {
  // 清除 passport slot,回 Materials 重新拍照
  setSlot('passport', { collected: false, fileUrl: null, ocrResult: null, error: null })
  router.push('/materials')
}

function onConfirm() {
  if (!isValid.value) return
  // 写回 passport slot 的 ocrResult,标记 docs step 完成(如果其他 slot 也都完成)
  setSlot('passport', {
    collected: true,
    fileUrl: fileUrl.value,
    ocrResult: { ...form },
    error: null,
  })
  router.push('/materials')
}

onMounted(() => {
  // 从 progress store 拿 OCR 数据
  const slot = state.value.slots.passport
  if (slot?.ocrResult) {
    fileUrl.value = slot.fileUrl || ''
    hydrateFromOCR(slot.ocrResult)
  }
})
</script>

<style scoped lang="scss">
.pr-page { min-height: 100vh; background: #fff; }
.pr-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 24px 80px;
  gap: 32px;
}
.pr-side { position: sticky; top: 88px; align-self: start; }
.pr-side__back { background: transparent; border: 0; color: var(--ink-3, #64748B); font-size: 13px; cursor: pointer; padding: 4px 0; margin-bottom: 24px; }
.pr-side__back:hover { color: var(--el-color-primary, #3B6EF5); }
.pr-steps { list-style: none; padding: 0; margin: 0; }
.pr-step {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 12px; border-radius: 10px;
  font-size: 14px; color: var(--ink-3, #64748B);
  margin-bottom: 4px;
}
.pr-step.is-active { background: rgba(59, 110, 245, .08); color: var(--ink-1, #0F172A); font-weight: 600; }
.pr-step.is-done { color: var(--ink-1, #0F172A); }
.pr-step__icon { font-size: 18px; width: 24px; text-align: center; }
.pr-step__label { flex: 1; }
.pr-step__check { font-size: 12px; font-weight: 700; width: 18px; height: 18px; border-radius: 50%; background: #10B981; color: #fff; display: flex; align-items: center; justify-content: center; }

.pr-main { min-width: 0; }
.page-title { font-size: 28px; font-weight: 700; color: var(--ink-1, #0F172A); margin: 24px 0 4px; letter-spacing: -0.4px; }
.page-sub { color: var(--ink-3, #64748B); font-size: 14px; margin: 0 0 24px; }

.pr-passport {
  position: relative;
  background: #F8FAFC;
  border-radius: 14px;
  padding: 24px;
  display: flex; align-items: center; justify-content: center;
  min-height: 200px;
  margin-bottom: 24px;
  border: 1px solid #E2E8F0;
}
.pr-passport__img {
  max-width: 100%; max-height: 240px; object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, .12);
}
.pr-passport__placeholder { font-size: 80px; opacity: .3; }
.pr-passport__edit {
  position: absolute; top: 12px; right: 12px;
  background: #fff; border: 1px solid #E2E8F0;
  border-radius: 999px; padding: 6px 14px;
  font-size: 12px; font-weight: 600; color: var(--ink-1, #0F172A);
  cursor: pointer;
}
.pr-passport__edit:hover { background: #F1F5F9; }

.pr-fields {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.pr-field { display: flex; flex-direction: column; gap: 6px; }
.pr-field__label { font-size: 12px; font-weight: 600; color: var(--ink-1, #0F172A); }
.pr-field__label .req { color: #DC2626; }
.pr-field__input {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid #CBD5E1; border-radius: 8px;
  background: #fff; color: var(--ink-1, #0F172A);
  font-family: inherit;
  transition: border-color .15s, box-shadow .15s;
}
.pr-field__input:focus {
  outline: 0;
  border-color: var(--el-color-primary, #3B6EF5);
  box-shadow: 0 0 0 3px rgba(59, 110, 245, .12);
}
.pr-field__input-wrap { position: relative; }
.pr-field__icon-btn {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  background: transparent; border: 0; cursor: pointer;
  font-size: 14px; color: var(--ink-3, #64748B);
  padding: 4px 8px;
}
.pr-field__icon-btn:hover { color: var(--el-color-primary, #3B6EF5); }
.pr-field__select-wrap { position: relative; }
.pr-field__select { appearance: none; padding-right: 32px; }
.pr-field__chev {
  position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  font-size: 12px; color: var(--ink-3, #64748B); pointer-events: none;
}
.pr-field__auto {
  font-size: 11px; color: #059669; font-weight: 500;
  margin: 4px 0 0;
}

.pr-section {
  border: 1px solid #E2E8F0; border-radius: 12px;
  padding: 20px; margin-bottom: 24px;
  background: #fff;
}
.pr-section summary {
  display: flex; align-items: center; gap: 10px;
  list-style: none;
  cursor: pointer;
  font-size: 16px; font-weight: 700; color: var(--ink-1, #0F172A);
  margin: 0;
}
.pr-section summary::-webkit-details-marker { display: none; }
.pr-section__icon { font-size: 18px; }
.pr-section__title { flex: 1; display: flex; align-items: center; gap: 10px; }
.pr-section__chev { font-size: 14px; color: var(--ink-3, #64748B); transition: transform .2s; }
.pr-section[open] .pr-section__chev { transform: rotate(180deg); }
.pr-section__hint { color: var(--ink-3, #64748B); font-size: 13px; margin: 8px 0 16px; }
.pr-section .pr-fields { margin-bottom: 0; }

.pr-footer {
  display: flex; gap: 12px; justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid #E2E8F0;
  position: sticky; bottom: 0; background: #fff;
}
.pr-btn {
  border: 0; border-radius: 999px;
  padding: 12px 28px; font-size: 14px; font-weight: 700;
  cursor: pointer; font-family: inherit;
  transition: all .2s;
}
.pr-btn--primary { background: linear-gradient(135deg, #3B6EF5, #6E59F0); color: #fff; }
.pr-btn--primary:hover:not(.is-disabled) { box-shadow: 0 6px 18px rgba(59, 110, 245, .4); }
.pr-btn--primary.is-disabled { background: #E2E8F0; color: #94A3B8; cursor: not-allowed; }
.pr-btn--ghost { background: #F1F5F9; color: var(--ink-1, #0F172A); }
.pr-btn--ghost:hover { background: #E2E8F0; }

@media (max-width: 768px) {
  .pr-layout { grid-template-columns: 1fr; }
  .pr-side { position: static; }
  .pr-fields { grid-template-columns: 1fr; }
  .pr-footer { flex-direction: column-reverse; }
  .pr-btn { width: 100%; }
}
</style>
