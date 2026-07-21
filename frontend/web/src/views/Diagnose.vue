<template>
  <div class="diagnose-page">
    <AppHeader scope="diagnose" />

    <main class="app-container app-page diagnose-main">
      <header v-if="step !== 2" class="diagnose-hero">
        <h1 class="diagnose-hero__title">{{ t('diagnose.title') }}</h1>
        <p class="diagnose-hero__sub">{{ t('diagnose.sub') }}</p>
      </header>

      <!-- Step 1: 国家选 -->
      <section v-if="step === 1" class="diagnose-section" data-testid="diagnose-step-1">
        <h2 class="diagnose-section__title">{{ t('diagnose.step_country') }}</h2>
        <div class="diagnose-countries">
          <div
            v-for="(group, gKey) in groupedCountries"
            :key="gKey"
            class="diagnose-country-group"
            :data-testid="`diagnose-group-${gKey}`"
          >
            <h3 class="diagnose-country-group__title">
              {{ t(`common.country_group_${gKey}`) }}
              <span class="diagnose-country-group__count">{{ group.length }}</span>
            </h3>
            <div class="diagnose-country-group__grid">
              <button
                v-for="c in group"
                :key="c.country_code"
                type="button"
                class="diagnose-country"
                :class="{ 'is-selected': form.country_code === c.country_code }"
                :data-testid="`diagnose-country-${c.country_code}`"
                @click="selectCountry(c.country_code)"
              >
                <span class="diagnose-country__flag">{{ flagOf(c.country_code) }}</span>
                <span class="diagnose-country__name">{{ countryName(c.country_code) }}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Step 2: 表单（对齐 diagnose-income-redesign） -->
      <section v-else-if="step === 2" class="diagnose-step2" data-testid="diagnose-step-2">
        <button class="diagnose-back" data-testid="diagnose-back" @click="step = 1">
          ← {{ t('diagnose.back') }}
        </button>

        <div class="diagnose-card">
          <header class="diagnose-card__header">
            <h2 class="diagnose-card__title">
              {{ t('diagnose.step_form') }} · <span>{{ selectedCountryName }}</span>
            </h2>
          </header>

          <form class="diagnose-form" @submit.prevent="onSubmit">
            <div class="diagnose-form__grid">
              <!-- 婚姻 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.marital') }}</label>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in MARITAL_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.marital_status === opt.value }"
                    :data-testid="`diagnose-marital-${opt.value}`"
                    @click="form.marital_status = opt.value"
                  >{{ t(`diagnose.marital_${opt.value}`) }}</button>
                </div>
              </div>

              <!-- 收入 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.income', { cur: t('diagnose.cur') }) }}</label>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in INCOME_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.income_bucket === opt.value }"
                    :data-testid="`diagnose-income-${opt.value}`"
                    @click="form.income_bucket = opt.value"
                  >{{ incomeLabel(opt.value) }}</button>
                </div>
              </div>

              <!-- 出行目的 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.purpose') }}</label>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in PURPOSE_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.travel_purpose === opt.value }"
                    :data-testid="`diagnose-purpose-${opt.value}`"
                    @click="form.travel_purpose = opt.value"
                  >{{ t(`diagnose.purpose_${opt.value}`) }}</button>
                </div>
              </div>

              <!-- 出行记录 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.travel_history') }}</label>
                <p class="diagnose-field__tip">{{ t('diagnose.travel_history_tip') }}</p>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in TRAVEL_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.travel_history === opt.value }"
                    :data-testid="`diagnose-travel-${opt.value}`"
                    @click="form.travel_history = opt.value"
                  >{{ t(`diagnose.travel_${opt.value}`) }}</button>
                </div>
              </div>

              <!-- 签证历史 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.visa_history') }}</label>
                <p class="diagnose-field__tip">{{ t('diagnose.visa_history_tip') }}</p>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in VISA_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.visa_history === opt.value }"
                    :data-testid="`diagnose-visa-${opt.value}`"
                    @click="form.visa_history = opt.value"
                  >{{ t(`diagnose.visa_${opt.value}`) }}</button>
                </div>
              </div>

              <!-- 在职 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.employment') }}</label>
                <p class="diagnose-field__tip">{{ t('diagnose.employment_tip') }}</p>
                <div class="diagnose-pills">
                  <button
                    v-for="opt in EMP_OPTS"
                    :key="opt.value"
                    type="button"
                    class="diagnose-pill"
                    :class="{ 'is-selected': form.employment === opt.value }"
                    :data-testid="`diagnose-emp-${opt.value}`"
                    @click="form.employment = opt.value"
                  >{{ t(`diagnose.emp_${opt.value}`) }}</button>
                </div>
              </div>

              <!-- 年龄 + 单身女性 -->
              <div class="diagnose-field">
                <label class="diagnose-field__label">{{ t('diagnose.extras') }}</label>
                <div class="diagnose-extras">
                  <label class="diagnose-extras__age">
                    <span>{{ t('diagnose.age') }}</span>
                    <input
                      v-model.number="form.age"
                      type="number"
                      min="10" max="90"
                      :placeholder="t('diagnose.age_ph')"
                      data-testid="diagnose-age"
                    />
                  </label>
                  <label class="diagnose-extras__check">
                    <input v-model="form.is_solo_female" type="checkbox" data-testid="diagnose-solo" />
                    <span>{{ t('diagnose.solo_female') }}</span>
                  </label>
                </div>
              </div>
            </div>

            <div class="diagnose-actions">
              <span class="diagnose-save">{{ t('diagnose.autosaved') }}</span>
              <div class="diagnose-actions__btns">
                <button
                  type="button"
                  class="diagnose-btn diagnose-btn--secondary"
                  data-testid="diagnose-prev"
                  @click="step = 1"
                >{{ t('diagnose.prev') }}</button>
                <button
                  type="submit"
                  class="diagnose-btn diagnose-btn--primary"
                  :disabled="!canSubmit || loading"
                  data-testid="diagnose-submit"
                >
                  {{ loading ? t('diagnose.analyzing') : t('diagnose.next') }}
                </button>
              </div>
            </div>
          </form>
        </div>
      </section>

      <!-- Step 3: 结果 -->
      <section v-else-if="step === 3 && result" class="diagnose-section" data-testid="diagnose-step-3">
        <button class="diagnose-back" data-testid="diagnose-restart" @click="restart">
          ← {{ t('diagnose.restart') }}
        </button>

        <!-- 大分数 + level -->
        <div class="diagnose-result-hero" :class="`is-${result.level}`" data-testid="diagnose-result-hero">
          <div class="diagnose-result-hero__score">
            <div class="diagnose-result-hero__big">{{ result.score }}</div>
            <div class="diagnose-result-hero__suffix">/ 100</div>
          </div>
          <div class="diagnose-result-hero__meta">
            <div class="diagnose-result-hero__level">
              {{ t(`diagnose.level_${result.level}`) }}
            </div>
            <div class="diagnose-result-hero__country">
              {{ flagOf(result.country_code) }} {{ selectedCountryName }}
            </div>
            <div v-if="result.policy_summary" class="diagnose-result-hero__policy">
              {{ result.policy_summary }}
            </div>
          </div>
        </div>

        <!-- Factors -->
        <h2 class="diagnose-section__title">{{ t('diagnose.factors') }}</h2>
        <div class="diagnose-factors">
          <div
            v-for="(f, i) in result.factors"
            :key="i"
            class="diagnose-factor"
            :class="`is-${f.category}`"
            :data-testid="`diagnose-factor-${i}`"
          >
            <div class="diagnose-factor__impact" :class="f.impact >= 0 ? 'is-pos' : 'is-neg'">
              {{ f.impact >= 0 ? '+' : '' }}{{ f.impact }}
            </div>
            <div>
              <div class="diagnose-factor__name">{{ f.name }}</div>
              <div class="diagnose-factor__detail">{{ f.detail }}</div>
            </div>
          </div>
        </div>

        <!-- Suggestions -->
        <h2 class="diagnose-section__title">{{ t('diagnose.suggestions') }}</h2>
        <ul class="diagnose-suggestions">
          <li v-for="(s, i) in result.suggestions" :key="i">{{ s }}</li>
        </ul>

        <button class="diagnose-cta" data-testid="diagnose-cta" @click="goApply">
          {{ t('diagnose.cta_apply') }}
        </button>
      </section>

      <div v-if="error" class="diagnose-error" data-testid="diagnose-error">
        {{ error }}
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import { listDestinations } from '@/api/destinations'
import http from '@/api/http'
import { groupCountriesByVisaType } from '@/utils/countries'

const { t, locale } = useI18n()
const router = useRouter()
const step = ref(1)
const countries = ref([])
const error = ref('')
const loading = ref(false)
const result = ref(null)

const form = reactive({
  country_code: '',
  marital_status: 'single',
  income_bucket: '15k_30k',
  travel_purpose: 'tourism',
  travel_history: '1_3',
  visa_history: 'none',
  employment: 'employed',
  age: null,
  is_solo_female: false,
})

const MARITAL_OPTS = [
  { value: 'single' }, { value: 'married' }, { value: 'divorced' }, { value: 'widowed' },
]
const INCOME_OPTS = [
  { value: 'below_5k' }, { value: '5k_15k' }, { value: '15k_30k' },
  { value: '30k_100k' }, { value: 'above_100k' },
]
const PURPOSE_OPTS = [
  { value: 'business' }, { value: 'tourism' }, { value: 'family' },
  { value: 'study' }, { value: 'other' },
]
const TRAVEL_OPTS = [
  { value: 'none' }, { value: '1_3' }, { value: '4_10' }, { value: 'above_10' },
]
const VISA_OPTS = [
  { value: 'none' }, { value: '1_2' }, { value: 'above_2' },
]
const EMP_OPTS = [
  { value: 'employed' }, { value: 'freelancer' }, { value: 'student' },
  { value: 'retired' }, { value: 'unemployed' },
]

const flagMap = {
  US: '🇺🇸', JP: '🇯🇵', KR: '🇰🇷', SG: '🇸🇬', GB: '🇬🇧', FR: '🇫🇷',
  ID: '🇮🇩', VN: '🇻🇳', TH: '🇹🇭', DE: '🇩🇪', AU: '🇦🇺', CA: '🇨🇦',
  NZ: '🇳🇿', SCHENGEN: '🇪🇺', EU: '🇪🇺',
}
function flagOf(cc) { return flagMap[cc] || '🌐' }

// W57: 国家名优先用 i18n 的 country.<code>, 避免 lang=vi 但 mock 返回中文 "澳大利亚"。
const selectedCountryName = computed(() => {
  const code = form.country_code
  if (!code) return ''
  const i18nName = t(`country.${code.toLowerCase()}`, { default: '' })
  if (i18nName) return i18nName
  // fallback: Backend 返回的 country_name（已过 localizeName,可能仍是中文）
  const c = countries.value.find(x => x.country_code === code)
  return c?.country_name || code
})

// W57: 收入档 — 单位跟 cur 一起 i18n,每档文案随 locale 数字量级调整。
//            zh-CN   en       vi                 id
// below_5k    5k 以下  Below 1k  Dưới 5 triệu    Di bawah 5 juta
// 5k_15k      5k-15k  1k-3k    5-15 triệu       5-15 juta
// 15k_30k     15k-30k 3k-5k   15-30 triệu      15-30 juta
// 30k_100k    30k-100k 5k-10k 30-100 triệu     30-100 juta
// above_100k  100k+   10k+     100 triệu+       100 juta+
//   i18n text already carries the magnitude; we just append the {cur}
// 收入档 chip 不带单位 — 文字已经隐含 magnitude(例 "5 - 15 triệu"),单位只在 label 上展示一次
function incomeLabel(value) {
  return t(`diagnose.income_${value}`)
}

// W57: 国家名 lookup — 优先 vue-i18n country.<code>, fallback 到 backend 已 localize 的字段。
//              这样即便后端 lang=vi 的多语言没就绪,前端也能按 locale 兜底翻译。
function countryName(code) {
  if (!code) return ''
  const i18nName = t(`country.${code.toLowerCase()}`, { default: '' })
  if (i18nName) return i18nName
  const c = countries.value.find(x => x.country_code === code)
  return c?.country_name || code
}

// 按签证体系分组 (W27): 国别签证 / 申根签证
// 与 /apply 对齐:只展示 enabled 产品线(美/英/澳 + 申根 DE/FR),
// 种子里的 JP/CA/SG/NZ 等 Coming Soon 国不得出现在诊断选国.
const groupedCountries = computed(() => {
  const visible = countries.value.filter((c) => c.enabled !== false)
  const g = groupCountriesByVisaType(visible)
  // 顺序:国别签证在前 (US/AU/GB,数量少,精挑细选)
  return { national: g.national, schengen: g.schengen }
})

const canSubmit = computed(() => {
  return form.country_code && form.marital_status && form.income_bucket &&
    form.travel_purpose && form.travel_history && form.visa_history && form.employment
})

function selectCountry(cc) {
  form.country_code = cc
  step.value = 2
}

async function onSubmit() {
  if (!canSubmit.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const env = await http.post('/v2/diagnose', form)
    if (env.code !== '1000') throw new Error(env.message || 'diagnose failed')
    result.value = env.data
    step.value = 3
  } catch (e) {
    const status = e?.response?.status
    if (status === 405 || /^Request failed with status code \d+/.test(e?.message || '')) {
      error.value = t('diagnose.err_network')
    } else {
      error.value = e?.message || t('diagnose.err_network')
    }
  } finally {
    loading.value = false
  }
}

function restart() {
  step.value = 1
  result.value = null
}

function goApply() {
  router.push({ name: 'Apply', query: { country: form.country_code } })
}

async function loadCountries() {
  try {
    countries.value = await listDestinations({ lang: locale.value })
  } catch (e) {
    countries.value = []
  }
}

onMounted(loadCountries)
// W57: 语言切换时重新拉国家 — 之前只 onMounted 时拉,后续 setLocale 没刷新
watch(() => locale.value, () => loadCountries())
</script>

<style scoped lang="scss">
.diagnose-page { min-height: 100vh; background: #ffffff; display: flex; flex-direction: column; }
.diagnose-main {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.diagnose-hero {
  text-align: left;
  margin-bottom: 28px;
  &__title {
    font-size: 28px; font-weight: 700; color: #0F172A;
    margin: 0 0 8px; letter-spacing: -.5px;
  }
  &__sub { font-size: 15px; color: #64748B; margin: 0; }
}
.diagnose-section {
  background: #fff;
  border: 1px solid #e9edf5;
  border-radius: 20px;
  padding: 32px 34px;
  margin-bottom: 18px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, .06);
}
.diagnose-section__title {
  font-size: 18px; font-weight: 600; color: #0F172A; margin: 0 0 16px;
}
.diagnose-section__cc { color: #2563EB; font-weight: 500; }
.diagnose-back {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 0; color: #64748B; font-size: 14px;
  padding: 0; margin: 0 0 20px; cursor: pointer;
  &:hover { color: #2563EB; }
}

.diagnose-step2 { margin-bottom: 18px; }
.diagnose-card {
  overflow: hidden;
  border: 1px solid #e9edf5;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 28px rgba(15, 23, 42, .06);
}
.diagnose-card__header { padding: 40px 40px 32px; }
.diagnose-card__title {
  margin: 0;
  color: #0F172A;
  font-size: 22px;
  font-weight: 700;
  line-height: normal;
  span { color: #2563EB; }
}

.diagnose-countries {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.diagnose-country-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #475569;
    margin: 0;
    letter-spacing: .3px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  &__count {
    font-size: 11px;
    color: #94a3b8;
    font-weight: 500;
    background: #f1f5f9;
    padding: 2px 8px;
    border-radius: 999px;
  }
  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
  }
}
.diagnose-country {
  display: flex; align-items: center; gap: 10px;
  background: #FFFFFF; border: 1.5px solid #e9edf5; border-radius: 14px;
  padding: 15px 16px; cursor: pointer;
  transition: transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .18s ease, border-color .18s ease, background .18s ease;
  font-size: 14px; color: #0f172a;
  &:hover { border-color: #93b4fb; background: #FFFFFF; transform: translateY(-2px); box-shadow: 0 10px 22px rgba(59,110,245,.12); }
  &.is-selected { background: #FFFFFF; border-color: #3b6ef5; box-shadow: 0 8px 20px rgba(59,110,245,.16); }
  &__flag { font-size: 22px; }
  &__name { font-weight: 600; }
}

.diagnose-form { display: flex; flex-direction: column; }
.diagnose-form__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  row-gap: 32px;
  padding: 0 40px 40px;
}
.diagnose-field { display: flex; flex-direction: column; gap: 0; min-width: 0; }
.diagnose-field__label {
  margin: 0 0 12px;
  font-size: 16px; font-weight: 700; color: #0F172A; line-height: 1.3;
}
.diagnose-field__tip {
  min-height: 0;
  margin: -6px 0 12px;
  font-size: 12px; color: #94A3B8;
  line-height: 18px;
}
.diagnose-pills { display: flex; flex-wrap: wrap; gap: 12px; }
.diagnose-pill {
  min-height: 40px;
  display: inline-flex; align-items: center; justify-content: center;
  background: #FFFFFF; border: 1.5px solid #e9edf5; color: #475569;
  padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer;
  transition: all .15s ease;
  &:hover { border-color: #93b4fb; color: #3b6ef5; background: #FFFFFF; }
  &.is-selected {
    background: #EFF6FF; color: #3b6ef5; border-color: #3b6ef5;
  }
}
.diagnose-extras { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.diagnose-extras__age {
  display: flex; align-items: center; gap: 8px; font-size: 13px; color: #475569;
  input {
    width: 80px; padding: 7px 10px; border: 1px solid #E2E8F0; border-radius: 8px;
    font-size: 14px; outline: none; color: #0F172A; background: #FFFFFF;
    &:focus { border-color: #2563EB; }
  }
}
.diagnose-extras__check {
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: #475569;
  input { width: 16px; height: 16px; cursor: pointer; }
}

.diagnose-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 0 40px;
  padding: 32px 0 40px;
  border-top: 1px solid #F1F5F9;
}
.diagnose-save {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748B;
  font-size: 13px;
  &::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #2563EB;
  }
}
.diagnose-actions__btns { display: flex; gap: 10px; }
.diagnose-btn {
  min-height: 40px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.diagnose-btn--secondary {
  color: #475569;
  border: 1px solid #E2E8F0;
  background: #fff;
  &:hover { color: #1D4ED8; border-color: #1D4ED8; background: #EFF6FF; }
}
.diagnose-btn--primary {
  color: #fff;
  border: 1px solid #2563EB;
  background: #2563EB;
  &:hover { border-color: #1D4ED8; background: #1D4ED8; }
  &:disabled { background: #E2E8F0; border-color: #E2E8F0; color: #94A3B8; cursor: not-allowed; }
}

@media (max-width: 560px) {
  .diagnose-card__header { padding: 32px 20px; }
  .diagnose-form__grid { padding: 0 20px 32px; }
  .diagnose-actions {
    margin: 0 20px;
    padding: 32px 0;
    align-items: stretch;
    flex-direction: column;
  }
  .diagnose-actions__btns {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .diagnose-btn { width: 100%; }
}

.diagnose-result-hero {
  display: flex; align-items: center; gap: 24px;
  padding: 24px; border-radius: 16px; margin-bottom: 22px;
  border: 1px solid #e2e8f0;
  &.is-high { background: linear-gradient(135deg, #ecfdf5, #f0fdf4); border-color: #86efac; }
  &.is-medium { background: linear-gradient(135deg, #fefce8, #fef9c3); border-color: #fde047; }
  &.is-low { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-color: #fca5a5; }
  &__score { text-align: center; min-width: 110px; }
  &__big { font-size: 64px; font-weight: 800; color: #0f172a; line-height: 1; }
  &__suffix { font-size: 14px; color: #64748b; margin-top: 4px; }
  &__meta { flex: 1; }
  &__level {
    font-size: 18px; font-weight: 700;
    &.is-high { color: #16a34a; }
    &.is-medium { color: #ca8a04; }
    &.is-low { color: #dc2626; }
  }
  &__country { font-size: 14px; color: #475569; margin-top: 4px; }
  &__policy { font-size: 12.5px; color: #64748b; margin-top: 8px; line-height: 1.5; }
}
.diagnose-factors { display: flex; flex-direction: column; gap: 8px; margin-bottom: 22px; }
.diagnose-factor {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 14px; border-radius: 10px;
  background: #fff; border: 1px solid #eef1f6;
  &__impact {
    font-size: 14px; font-weight: 700; min-width: 40px; text-align: center;
    padding: 4px 0; border-radius: 8px;
    &.is-pos { color: #16a34a; background: #dcfce7; }
    &.is-neg { color: #dc2626; background: #fee2e2; }
  }
  &__name { font-size: 13.5px; font-weight: 600; color: #0f172a; }
  &__detail { font-size: 12.5px; color: #64748b; margin-top: 2px; line-height: 1.5; }
}
.diagnose-suggestions {
  margin: 0 0 24px; padding-left: 20px; color: #475569; font-size: 13.5px; line-height: 1.7;
  li { margin-bottom: 6px; }
}
.diagnose-cta {
  width: 100%;
  background: #0f172a; color: #fff; border: 0; padding: 14px;
  border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer;
  &:hover { background: #1e293b; }
}
.diagnose-error {
  text-align: center; color: #b91c1c; font-size: 13px;
  padding: 12px; background: #fef2f2; border-radius: 10px; margin-top: 16px;
}
</style>
