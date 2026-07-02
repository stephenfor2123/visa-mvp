<template>
  <div class="diagnose-page app-container">
    <AppHeader scope="diagnose" />

    <main class="diagnose-main">
      <header class="diagnose-hero">
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
                <span class="diagnose-country__name">{{ c.country_name }}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Step 2: 表单 -->
      <section v-else-if="step === 2" class="diagnose-section" data-testid="diagnose-step-2">
        <button class="diagnose-back" data-testid="diagnose-back" @click="step = 1">
          ← {{ t('diagnose.back') }}
        </button>
        <h2 class="diagnose-section__title">
          {{ t('diagnose.step_form') }} · <span class="diagnose-section__cc">{{ selectedCountryName }}</span>
        </h2>

        <form class="diagnose-form" @submit.prevent="onSubmit">
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
            <label class="diagnose-field__label">{{ t('diagnose.income') }}</label>
            <div class="diagnose-pills">
              <button
                v-for="opt in INCOME_OPTS"
                :key="opt.value"
                type="button"
                class="diagnose-pill"
                :class="{ 'is-selected': form.income_bucket === opt.value }"
                :data-testid="`diagnose-income-${opt.value}`"
                @click="form.income_bucket = opt.value"
              >{{ t(`diagnose.income_${opt.value}`) }}</button>
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

          <button
            type="submit"
            class="diagnose-submit"
            :disabled="!canSubmit || loading"
            data-testid="diagnose-submit"
          >
            {{ loading ? t('diagnose.analyzing') : t('diagnose.submit') }}
          </button>
        </form>
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
import { computed, onMounted, reactive, ref } from 'vue'
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

const selectedCountryName = computed(() => {
  const c = countries.value.find(x => x.country_code === form.country_code)
  return c?.country_name || form.country_code
})

// 按签证体系分组 (W27): 国别签证 / 申根签证
const groupedCountries = computed(() => {
  const g = groupCountriesByVisaType(countries.value)
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
    error.value = e?.message || t('diagnose.err_network')
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
</script>

<style scoped lang="scss">
.diagnose-page { min-height: 100vh; background: #fff; display: flex; flex-direction: column; }
.diagnose-main {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.diagnose-hero {
  text-align: center;
  margin-bottom: 28px;
  &__title {
    font-size: 32px; font-weight: 700; color: #0f172a;
    margin: 0 0 8px; letter-spacing: -.5px;
  }
  &__sub { font-size: 15px; color: #64748b; margin: 0; }
}
.diagnose-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px 28px; margin-bottom: 18px; }
.diagnose-section__title {
  font-size: 18px; font-weight: 600; color: #0f172a; margin: 0 0 16px;
}
.diagnose-section__cc { color: #3b6ef5; font-weight: 500; }
.diagnose-back {
  background: transparent; border: 0; color: #64748b; font-size: 13px; padding: 0 0 12px;
  cursor: pointer;
  &:hover { color: #3b6ef5; }
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
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px; cursor: pointer; transition: all .15s ease;
  font-size: 14px; color: #0f172a;
  &:hover { border-color: #3b6ef5; transform: translateY(-1px); }
  &.is-selected { background: #eff6ff; border-color: #3b6ef5; }
  &__flag { font-size: 22px; }
  &__name { font-weight: 500; }
}

.diagnose-form { display: flex; flex-direction: column; gap: 22px; }
.diagnose-field { display: flex; flex-direction: column; gap: 8px; }
.diagnose-field__label {
  font-size: 13px; font-weight: 500; color: #475569;
}
.diagnose-field__tip {
  font-size: 12px; color: #94a3b8; margin: 0 0 2px;
  line-height: 1.5;
}
.diagnose-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.diagnose-pill {
  background: #f8fafc; border: 1px solid #e2e8f0; color: #475569;
  padding: 8px 16px; border-radius: 999px; font-size: 13px; cursor: pointer;
  transition: all .15s ease;
  &:hover { border-color: #3b6ef5; color: #0f172a; }
  &.is-selected {
    background: #3b6ef5; color: #fff; border-color: #3b6ef5;
  }
}
.diagnose-extras { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.diagnose-extras__age {
  display: flex; align-items: center; gap: 8px; font-size: 13px; color: #475569;
  input {
    width: 80px; padding: 7px 10px; border: 1px solid #e2e8f0; border-radius: 8px;
    font-size: 14px; outline: none; color: #0f172a;
    &:focus { border-color: #3b6ef5; }
  }
}
.diagnose-extras__check {
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: #475569;
  input { width: 16px; height: 16px; cursor: pointer; }
}
.diagnose-submit {
  background: #3b6ef5; color: #fff; border: 0; padding: 14px;
  border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer;
  margin-top: 8px;
  &:hover { background: #2553d6; }
  &:disabled { background: #cbd5e1; cursor: not-allowed; }
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
  padding: 12px 14px; border-radius: 10px; background: #f8fafc;
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
