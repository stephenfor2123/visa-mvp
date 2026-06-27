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
              <div class="apply-meta__label">{{ t('apply.fee') }}</div>
              <div class="apply-meta__val">{{ checklist.fee }}</div>
            </div>
            <div v-if="checklist.processing_time" class="apply-meta__cell">
              <div class="apply-meta__label">{{ t('apply.processing') }}</div>
              <div class="apply-meta__val">{{ checklist.processing_time }}</div>
            </div>
            <div v-if="checklist.validity" class="apply-meta__cell">
              <div class="apply-meta__label">{{ t('apply.validity') }}</div>
              <div class="apply-meta__val">{{ checklist.validity }}</div>
            </div>
          </div>

          <!-- Materials grouped by category -->
          <div v-if="groupedMaterials.length" class="apply-materials">
            <div v-for="(g, i) in groupedMaterials" :key="i" class="apply-material-group">
              <h3 class="apply-material-group__title">
                <span class="apply-material-group__dot" :class="`is-${g.key}`" />
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
                  <button
                    class="apply-material__ocr"
                    :data-testid="`apply-ocr-${g.key}-${j}`"
                    :title="t('apply.scan_tip')"
                    @click="onScan(m)"
                  >
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.8"/>
                      <path d="M3 10h18M8 5V3M16 5V3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                      <circle cx="12" cy="14.5" r="2.4" stroke="currentColor" stroke-width="1.8"/>
                    </svg>
                    <span>{{ t('apply.scan') }}</span>
                  </button>
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

    <!-- OCR Demo Modal -->
    <div v-if="scanTarget" class="apply-ocr-modal" data-testid="apply-ocr-modal" @click="scanTarget = null">
      <div class="apply-ocr-modal__body" @click.stop>
        <h3 class="apply-ocr-modal__title">{{ t('apply.scan_title') }}</h3>
        <p class="apply-ocr-modal__desc">{{ t('apply.scan_desc', { name: scanTarget.name }) }}</p>
        <div class="apply-ocr-modal__demo">
          <div class="apply-ocr-modal__row"><b>{{ t('apply.scan_passport') }}</b> G12345678</div>
          <div class="apply-ocr-modal__row"><b>{{ t('apply.scan_name') }}</b> ZHANG SAN</div>
          <div class="apply-ocr-modal__row"><b>{{ t('apply.scan_dob') }}</b> 1990-01-01</div>
          <div class="apply-ocr-modal__row"><b>{{ t('apply.scan_expiry') }}</b> 2030-12-31</div>
        </div>
        <p class="apply-ocr-modal__hint">{{ t('apply.scan_hint') }}</p>
        <div class="apply-ocr-modal__actions">
          <button class="apply-ocr-modal__close" @click="scanTarget = null">
            {{ t('apply.scan_close') }}
          </button>
          <button class="apply-ocr-modal__cta" @click="goOrderNew">
            {{ t('apply.cta') }} →
          </button>
        </div>
      </div>
    </div>
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
const scanTarget = ref(null)

const form = reactive({
  country_code: '',
})

const CATEGORY_ORDER = ['identity', 'financial', 'work', 'travel', 'insurance', 'form', 'base']
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
    const env = await http.get('/v2/rag/checklist', { params: { country_code: form.country_code } })
    if (env.code !== '1000') throw new Error(env.message || 'checklist failed')
    checklist.value = env.data
  } catch (e) {
    error.value = e?.message || t('apply.err_network')
  } finally {
    loading.value = false
  }
}

function onScan(material) {
  scanTarget.value = material
}

function goOrderNew() {
  router.push({ name: 'OrderNew', query: { country: form.country_code } })
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
.apply-page { min-height: 100vh; background: #fff; display: flex; flex-direction: column; }
.apply-main {
  flex: 1; max-width: 980px; width: 100%;
  margin: 0 auto; padding: 32px 24px 80px;
}
.apply-hero {
  text-align: center; margin-bottom: 28px;
  &__title { font-size: 32px; font-weight: 700; color: #0f172a; margin: 0 0 8px; letter-spacing: -.5px; }
  &__sub { font-size: 15px; color: #64748b; margin: 0; }
}
.apply-section {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 16px;
  padding: 24px 28px; margin-bottom: 18px;
}
.apply-section__title {
  font-size: 18px; font-weight: 600; color: #0f172a; margin: 0 0 16px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.apply-section__cc { color: #0f172a; font-weight: 600; }
.apply-section__flag { font-size: 22px; }
.apply-back {
  background: transparent; border: 0; color: #64748b; font-size: 13px;
  padding: 0 0 12px; cursor: pointer;
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
  display: flex; flex-direction: column; gap: 20px;
}
.apply-country-group {
  display: flex; flex-direction: column; gap: 10px;
  &__title {
    font-size: 13px; font-weight: 600; color: #475569;
    margin: 0; letter-spacing: .3px;
    display: flex; align-items: center; gap: 8px;
  }
  &__count {
    font-size: 11px; color: #94a3b8; font-weight: 500;
    background: #f1f5f9; padding: 2px 8px; border-radius: 999px;
  }
  &__grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px;
  }
}
.apply-country {
  display: flex; align-items: center; gap: 10px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px; cursor: pointer; transition: all .15s ease;
  font-size: 14px; color: #0f172a;
  &:hover { border-color: #3b6ef5; transform: translateY(-1px); }
  &.is-selected { background: #eff6ff; border-color: #3b6ef5; }
  &__flag { font-size: 22px; }
  &__name { font-weight: 500; }
}
.apply-meta {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px; margin-bottom: 18px;
  &__cell {
    background: #f8fafc; border-radius: 10px; padding: 12px 14px;
  }
  &__label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
  &__val { font-size: 13px; color: #0f172a; line-height: 1.5; }
}
.apply-materials { display: flex; flex-direction: column; gap: 16px; margin-bottom: 18px; }
.apply-material-group {
  &__title {
    display: flex; align-items: center; gap: 8px;
    font-size: 14px; font-weight: 600; color: #475569; margin: 0 0 10px;
  }
  &__dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #94a3b8;
    &.is-identity { background: #3b6ef5; }
    &.is-financial { background: #16a34a; }
    &.is-work { background: #4f46e5; }
    &.is-travel { background: #0891b2; }
    &.is-insurance { background: #d97706; }
    &.is-form { background: #db2777; }
  }
  &__count {
    font-size: 11px; background: #f1f5f9; color: #64748b;
    padding: 1px 8px; border-radius: 999px; font-weight: 500;
  }
}
.apply-material-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.apply-material {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px; background: #fff;
  border: 1px solid #f1f5f9;
  &__check {
    width: 22px; height: 22px; border-radius: 6px;
    background: #3b6ef5; color: #fff; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  &__name { font-size: 13.5px; color: #0f172a; flex: 1; }
  &__ocr {
    display: inline-flex; align-items: center; gap: 4px;
    background: #f1f5f9; border: 0; color: #475569;
    padding: 5px 10px; border-radius: 999px; font-size: 11.5px;
    cursor: pointer; transition: all .15s ease;
    &:hover { background: #e0e7ff; color: #3b6ef5; }
  }
}
.apply-empty {
  text-align: center; padding: 40px 20px; color: #94a3b8; font-size: 13.5px;
}
.apply-source {
  font-size: 12px; color: #94a3b8; margin-top: 12px; padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  a { color: #3b6ef5; margin-left: 8px; text-decoration: none; }
}
.apply-actions { margin-top: 18px; }
.apply-cta {
  width: 100%;
  background: #0f172a; color: #fff; border: 0; padding: 14px;
  border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer;
  &:hover { background: #1e293b; }
}
.apply-error {
  text-align: center; color: #b91c1c; font-size: 13px;
  padding: 12px; background: #fef2f2; border-radius: 10px; margin-top: 16px;
}

.apply-ocr-modal {
  position: fixed; inset: 0; background: rgba(15, 23, 42, .55);
  display: flex; align-items: center; justify-content: center; z-index: 100;
  padding: 20px;
  &__body {
    background: #fff; border-radius: 18px; max-width: 460px; width: 100%;
    padding: 28px 32px; box-shadow: 0 24px 48px -8px rgba(15,23,42,.3);
  }
  &__title { font-size: 20px; font-weight: 700; margin: 0 0 6px; color: #0f172a; }
  &__desc { font-size: 13.5px; color: #64748b; margin: 0 0 18px; }
  &__demo {
    background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 14px;
  }
  &__row { font-size: 13px; color: #0f172a; margin-bottom: 4px; font-family: 'SF Mono', Menlo, monospace; }
  &__hint { font-size: 12px; color: #94a3b8; margin: 0 0 18px; line-height: 1.5; }
  &__actions { display: flex; gap: 8px; justify-content: flex-end; }
  &__close {
    background: #f1f5f9; border: 0; padding: 10px 16px; border-radius: 10px;
    font-size: 13px; color: #475569; cursor: pointer;
  }
  &__cta {
    background: #3b6ef5; color: #fff; border: 0; padding: 10px 18px;
    border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
    &:hover { background: #2553d6; }
  }
}
</style>
