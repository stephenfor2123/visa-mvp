<template>
  <div class="apply-page app-container">
    <AppHeader scope="apply" />

    <main class="apply-main">
      <header class="apply-hero">
        <h1 class="apply-hero__title">{{ t('apply.title') }}</h1>
        <p class="apply-hero__sub">{{ t('apply.sub') }}</p>
      </header>

      <!-- Step 1: 国家选 -->
      <section v-if="step === 1" class="apply-section" data-testid="apply-step-1">
        <h2 class="apply-section__title">{{ t('apply.step_country') }}</h2>
        <div class="apply-countries">
          <div
            v-for="(group, gKey) in groupedCountries"
            :key="gKey"
            class="apply-country-group"
            :data-testid="`apply-group-${gKey}`"
          >
            <h3 class="apply-country-group__title">
              {{ t(`common.country_group_${gKey}`) }}
              <span class="apply-country-group__count">{{ group.length }}</span>
            </h3>
            <div class="apply-country-group__grid">
              <button
                v-for="c in group"
                :key="c.country_code"
                type="button"
                class="apply-country"
                :class="{ 'is-selected': form.country_code === c.country_code }"
                :data-testid="`apply-country-${c.country_code}`"
                @click="selectCountry(c.country_code)"
              >
                <span class="apply-country__flag">{{ flagOf(c.country_code) }}</span>
                <span class="apply-country__name">{{ c.country_name }}</span>
                <span v-if="form.country_code === c.country_code" class="apply-country__badge">
                  <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
                    <path d="M3 8 L7 12 L13 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Step 2: 材料清单(RAG 拉出) -->
      <section v-else-if="step === 2" class="apply-section" data-testid="apply-step-2">
        <button class="apply-back" data-testid="apply-back" @click="step = 1">
          ← {{ t('apply.back') }}
        </button>
        <h2 class="apply-section__title">
          <span class="apply-section__cc">
            <span class="apply-section__flag">{{ flagOf(form.country_code) }}</span>
            {{ selectedCountryName }}
          </span>
          · {{ t('apply.checklist') }}
        </h2>

        <div v-if="loading" class="apply-loading" data-testid="apply-loading">
          <div class="apply-spinner" />
          {{ t('apply.loading') }}
        </div>

        <template v-else-if="checklist">
          <!-- Meta: fee / time / validity -->
          <div v-if="checklist.fee || checklist.processing_time || checklist.validity" class="apply-meta">
            <div v-if="checklist.fee" class="apply-meta__cell">
              <span class="apply-meta__icon apply-meta__icon--fee">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M12 7v10M9.5 9.3c0-1.1 1-2 2.5-2s2.5.8 2.5 1.9c0 2.6-5 1.3-5 3.9 0 1.1 1.1 1.9 2.5 1.9s2.5-.9 2.5-2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                </svg>
              </span>
              <div>
                <div class="apply-meta__label">{{ t('apply.fee') }}</div>
                <div class="apply-meta__val">{{ checklist.fee }}</div>
              </div>
            </div>
            <div v-if="checklist.processing_time" class="apply-meta__cell">
              <span class="apply-meta__icon apply-meta__icon--time">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.8"/>
                  <path d="M12 7.5v5l3.2 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
              <div>
                <div class="apply-meta__label">{{ t('apply.processing') }}</div>
                <div class="apply-meta__val">{{ checklist.processing_time }}</div>
              </div>
            </div>
            <div v-if="checklist.validity" class="apply-meta__cell">
              <span class="apply-meta__icon apply-meta__icon--validity">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                  <path d="M12 3.5l7 3v5.2c0 4.6-3 7.9-7 8.8-4-.9-7-4.2-7-8.8V6.5l7-3z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
                  <path d="M9 12l2 2 4-4.2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
              <div>
                <div class="apply-meta__label">{{ t('apply.validity') }}</div>
                <div class="apply-meta__val">{{ checklist.validity }}</div>
              </div>
            </div>
          </div>

          <!-- Materials grouped by category -->
          <div v-if="groupedMaterials.length" class="apply-materials">
            <div v-for="(g, i) in groupedMaterials" :key="i" class="apply-material-group">
              <h3 class="apply-material-group__title">
                <span class="apply-material-group__icon" :class="`is-${g.key}`">
                  <!-- identity: ID card -->
                  <svg v-if="g.key === 'identity'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <rect x="3" y="5" width="18" height="14" rx="2.5" stroke="currentColor" stroke-width="1.7"/>
                    <circle cx="8.5" cy="11" r="1.8" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M5.5 16c.6-1.7 1.9-2.5 3-2.5s2.4.8 3 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <path d="M14.5 10h4M14.5 13h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <!-- financial: coin -->
                  <svg v-else-if="g.key === 'financial'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.7"/>
                    <path d="M9.3 9.3c0-1.1 1.1-2 2.7-2s2.7.9 2.7 2c0 2.8-5.4 1.4-5.4 4.2 0 1.1 1.2 2 2.7 2s2.7-.9 2.7-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <path d="M12 6v1.3M12 16.7V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <!-- work: briefcase -->
                  <svg v-else-if="g.key === 'work'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <rect x="3" y="8" width="18" height="11" rx="2" stroke="currentColor" stroke-width="1.7"/>
                    <path d="M8.5 8V6.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V8" stroke="currentColor" stroke-width="1.7"/>
                    <path d="M3 13h18" stroke="currentColor" stroke-width="1.5"/>
                  </svg>
                  <!-- travel: plane -->
                  <svg v-else-if="g.key === 'travel'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <path d="M13 3.5l-2.4 2.4L4 7.3l-.9 1.6 6.6 1.6-.4 4.3-1.9 1.4.2 1.6 2.9-1 1.6 2.6 1.5-.6-.5-3 4-3 1.6-4.3-1.6-1.6-3.3.9-1-2.9z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
                  </svg>
                  <!-- insurance: shield -->
                  <svg v-else-if="g.key === 'insurance'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <path d="M12 3.5l7 3v5.2c0 4.6-3 7.9-7 8.8-4-.9-7-4.2-7-8.8V6.5l7-3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                    <path d="M9 12l2 2 4-4.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <!-- form: document -->
                  <svg v-else-if="g.key === 'form'" viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <path d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                    <path d="M14 3.5V8h4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                    <path d="M9 12.5h6M9 15.5h6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <!-- base / fallback: folder -->
                  <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
                    <path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4l1.6 2H19a1.5 1.5 0 0 1 1.5 1.5V17A1.5 1.5 0 0 1 19 18.5H5A1.5 1.5 0 0 1 3.5 17V6.5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                  </svg>
                </span>
                {{ t(`apply.cat_${g.key}`) }}
                <span class="apply-material-group__count">{{ g.items.length }}</span>
              </h3>
              <ul class="apply-material-list">
                <li
                  v-for="(m, j) in g.items"
                  :key="j"
                  class="apply-material"
                  :data-testid="`apply-material-${g.key}-${j}`"
                >
                  <span class="apply-material__check">
                    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                      <path d="M3 8 L7 12 L13 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </span>
                  <span class="apply-material__name">{{ m.name }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div v-else class="apply-empty">
            {{ t('apply.no_materials') }}
          </div>

          <div v-if="checklist.source_name" class="apply-source">
            {{ t('apply.source') }}: {{ checklist.source_name }}
            <a v-if="checklist.source_url" :href="checklist.source_url" target="_blank" rel="noopener">
              {{ t('apply.view_source') }} ↗
            </a>
          </div>

          <!-- 行动 -->
          <div class="apply-actions">
            <button class="apply-cta" data-testid="apply-cta" @click="goOrderNew">
              {{ t('apply.cta') }} →
            </button>
          </div>
        </template>

        <div v-else-if="error" class="apply-error" data-testid="apply-error">
          {{ error }}
        </div>
      </section>
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
import { useToast } from '@/composables/useToast'
import { groupCountriesByVisaType } from '@/utils/countries'

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const step = ref(1)
const countries = ref([])
const loading = ref(false)
const error = ref('')
const checklist = ref(null)

const form = reactive({
  country_code: '',
})

const CATEGORY_ORDER = ['identity', 'financial', 'work', 'travel', 'insurance', 'form', 'base']
const flagMap = {
  US: '🇺🇸', JP: '🇯🇵', KR: '🇰🇷', SG: '🇸🇬', GB: '🇬🇧', FR: '🇫🇷',
  ID: '🇮🇩', VN: '🇻🇳', TH: '🇹🇭', DE: '🇩🇪', AU: '🇦🇺', CA: '🇨🇦',
  NZ: '🇳🇿', SCHENGEN: '🇪🇺', EU: '🇪🇺',
  // 申根成员国 (W35: 26国全部可选，之前只有 DE/FR 有旗帜)
  AT: '🇦🇹', BE: '🇧🇪', HR: '🇭🇷', CZ: '🇨🇿', DK: '🇩🇰', EE: '🇪🇪',
  FI: '🇫🇮', GR: '🇬🇷', HU: '🇭🇺', IS: '🇮🇸', IT: '🇮🇹', LV: '🇱🇻',
  LI: '🇱🇮', LT: '🇱🇹', LU: '🇱🇺', MT: '🇲🇹', NL: '🇳🇱', NO: '🇳🇴',
  PL: '🇵🇱', PT: '🇵🇹', SK: '🇸🇰', SI: '🇸🇮', ES: '🇪🇸', SE: '🇸🇪',
  CH: '🇨🇭',
}
function flagOf(cc) { return flagMap[cc] || '🌐' }

const selectedCountryName = computed(() => {
  const c = countries.value.find(x => x.country_code === form.country_code)
  return c?.country_name || form.country_code
})

// 按签证体系分组 (W27): 国别签证 / 申根签证
const groupedCountries = computed(() => {
  const g = groupCountriesByVisaType(countries.value)
  return { national: g.national, schengen: g.schengen }
})

const groupedMaterials = computed(() => {
  if (!checklist.value?.materials) return []
  const buckets = {}
  for (const m of checklist.value.materials) {
    const cat = m.category || 'base'
    if (!buckets[cat]) buckets[cat] = []
    buckets[cat].push(m)
  }
  return CATEGORY_ORDER
    .filter(k => buckets[k])
    .map(k => ({ key: k, items: buckets[k] }))
})

function selectCountry(cc) {
  form.country_code = cc
  step.value = 2
  loadChecklist()
}

async function loadChecklist() {
  loading.value = true
  error.value = ''
  checklist.value = null
  try {
    // Map Vue i18n locale → backend language bucket.
    //   en     → 'en'
    //   id-ID  → 'id'
    //   vi-VN  → 'vi'
    //   zh-CN / anything else → 'zh-CN'
    const rawLocale = (locale.value || 'zh-CN').toString().toLowerCase()
    let lang = 'zh-CN'
    if (rawLocale.startsWith('en')) lang = 'en'
    else if (rawLocale.startsWith('id')) lang = 'id'
    else if (rawLocale.startsWith('vi')) lang = 'vi'
    const env = await http.get('/v2/rag/checklist', { params: { country_code: form.country_code, lang } })
    if (env.code !== '1000') throw new Error(env.message || 'checklist failed')
    checklist.value = env.data
  } catch (e) {
    error.value = e?.message || t('apply.err_network')
  } finally {
    loading.value = false
  }
}

function goOrderNew() {
  // W36: 先进材料收集向导（分大类强校验），完成后向导会带着 material_ids 跳 OrderNew
  router.push({ name: 'MaterialWizard', query: { country: form.country_code } })
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
.apply-page { min-height: 100vh; background: #ffffff; display: flex; flex-direction: column; }
.apply-main {
  flex: 1; max-width: 1200px; width: 100%;
  margin: 0 auto; padding: 32px 24px 80px;
}
.apply-hero {
  text-align: center; margin-bottom: 32px;
  &__title {
    font-size: 34px; font-weight: 800; margin: 0 0 8px; letter-spacing: -.6px;
    background: linear-gradient(135deg, #0f172a 0%, #3B6EF5 120%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  &__sub { font-size: 15px; color: #64748b; margin: 0; }
}
.apply-section {
  background: #fff; border: 1px solid #e9edf5; border-radius: 20px;
  padding: 28px 30px; margin-bottom: 18px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, .06);
}
.apply-section__title {
  font-size: 19px; font-weight: 700; color: #0f172a; margin: 0 0 18px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.apply-section__cc { color: #0f172a; font-weight: 700; }
.apply-section__flag { font-size: 22px; }
.apply-back {
  background: transparent; border: 0; color: #64748b; font-size: 13px;
  padding: 0 0 14px; cursor: pointer; font-weight: 500;
  &:hover { color: #3b6ef5; }
}
.apply-loading {
  text-align: center; padding: 60px 0; color: #64748b; font-size: 14px;
}
.apply-spinner {
  display: inline-block; width: 24px; height: 24px;
  border: 3px solid #e2e8f0; border-top-color: #3b6ef5;
  border-radius: 50%; animation: spin .8s linear infinite;
  margin-right: 8px; vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }
.apply-countries {
  display: flex; flex-direction: column; gap: 22px;
}
.apply-country-group {
  display: flex; flex-direction: column; gap: 12px;
  &__title {
    font-size: 13px; font-weight: 700; color: #475569;
    margin: 0; letter-spacing: .3px; text-transform: uppercase;
    display: flex; align-items: center; gap: 8px;
  }
  &__count {
    font-size: 11px; color: #94a3b8; font-weight: 600;
    background: #f1f5f9; padding: 2px 8px; border-radius: 999px;
  }
  &__grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px;
  }
}
.apply-country {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  background: #FFFFFF; border: 1.5px solid #e9edf5; border-radius: 14px;
  padding: 15px 16px; cursor: pointer;
  transition: transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .18s ease, border-color .18s ease, background .18s ease;
  font-size: 14px; color: #0f172a;
  &:hover { border-color: #93b4fb; background: #FFFFFF; transform: translateY(-2px); box-shadow: 0 10px 22px rgba(59,110,245,.12); }
  &.is-selected {
    background: #FFFFFF;
    border-color: #3b6ef5;
    box-shadow: 0 8px 20px rgba(59,110,245,.16);
  }
  &__flag { font-size: 23px; }
  &__name { font-weight: 600; }
  &__badge {
    position: absolute; top: -7px; right: -7px;
    width: 18px; height: 18px; border-radius: 50%;
    background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
    color: #fff; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(59,110,245,.4);
  }
}
.apply-meta {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px; margin-bottom: 20px;
  &__cell {
    display: flex; align-items: center; gap: 12px;
    background: #f8fafc; border: 1px solid #eef1f6; border-radius: 14px; padding: 12px 14px;
  }
  &__icon {
    flex-shrink: 0; width: 34px; height: 34px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    &--fee { background: #ecfdf3; color: #16a34a; }
    &--time { background: #eff6ff; color: #3b6ef5; }
    &--validity { background: #fdf4ff; color: #a21caf; }
  }
  &__label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 3px; }
  &__val { font-size: 13px; color: #0f172a; line-height: 1.4; font-weight: 600; }
}
.apply-materials { display: flex; flex-direction: column; gap: 18px; margin-bottom: 20px; }
.apply-material-group {
  &__title {
    display: flex; align-items: center; gap: 10px;
    font-size: 14.5px; font-weight: 700; color: #334155; margin: 0 0 12px;
  }
  &__icon {
    flex-shrink: 0; width: 28px; height: 28px; border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    background: #f1f5f9; color: #64748b;
    &.is-identity { background: #eff6ff; color: #3b6ef5; }
    &.is-financial { background: #ecfdf3; color: #16a34a; }
    &.is-work { background: #eef2ff; color: #4f46e5; }
    &.is-travel { background: #ecfeff; color: #0891b2; }
    &.is-insurance { background: #fffbeb; color: #d97706; }
    &.is-form { background: #fdf2f8; color: #db2777; }
  }
  &__count {
    font-size: 11px; background: #f1f5f9; color: #64748b;
    padding: 1px 8px; border-radius: 999px; font-weight: 600;
  }
}
.apply-material-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 7px; }
.apply-material {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 12px; border-radius: 10px; background: #fff;
  border: 1px solid #f1f5f9; transition: border-color .15s ease, box-shadow .15s ease;
  &:hover { border-color: #e2e8f0; box-shadow: 0 4px 12px rgba(15,23,42,.05); }
  &__check {
    width: 22px; height: 22px; border-radius: 7px;
    background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  &__name { font-size: 13.5px; color: #0f172a; flex: 1; }
}
.apply-empty {
  text-align: center; padding: 40px 20px; color: #94a3b8; font-size: 13.5px;
}
.apply-source {
  font-size: 12px; color: #94a3b8; margin-top: 12px; padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  a { color: #3b6ef5; margin-left: 8px; text-decoration: none; }
}
.apply-actions { margin-top: 20px; }
.apply-cta {
  width: 100%;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0; padding: 15px;
  border-radius: 14px; font-size: 15px; font-weight: 700; cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease;
  box-shadow: 0 10px 24px rgba(15,23,42,.18);
  &:hover { transform: translateY(-1px); box-shadow: 0 14px 30px rgba(15,23,42,.24); }
}
.apply-error {
  text-align: center; color: #b91c1c; font-size: 13px;
  padding: 12px; background: #fef2f2; border-radius: 10px; margin-top: 16px;
}
</style>
