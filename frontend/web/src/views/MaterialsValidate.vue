<template>
  <div class="validate-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <HtexLogo :size="28" />
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
      </div>
    </header>

    <main class="app-container app-page validate-shell">
      <h1 class="page-title">{{ t('validation.page_title') }}</h1>
      <p class="page-sub">{{ t('validation.page_subtitle') }}</p>

      <!-- Loading -->
      <div v-if="loading" class="state-loading">
        <span class="spinner" aria-hidden="true"></span>
        {{ t('validation.loading_validate') }}
      </div>

      <!-- Error -->
      <div v-else-if="loadError" class="state-error">
        <p>❌ {{ loadError }}</p>
        <AppButton ref="revalidateBtnRef" variant="outline" size="md" data-testid="validate-revalidate">
          {{ t('validation.btn_revalidate') }}
        </AppButton>
      </div>

      <!-- Empty state -->
      <div v-else-if="!hasResults" class="state-empty">
        <p class="empty-title">{{ t('validation.empty_title') }}</p>
        <p class="empty-desc">{{ t('validation.empty_desc') }}</p>
        <AppButton variant="primary" size="md" @click="$router.push('/materials')">
          {{ t('validation.go_materials') }}
        </AppButton>
      </div>

      <!-- Normal result -->
      <template v-else>
        <p class="summary" data-testid="validate-summary">
          {{ t('validation.summary', { total: counts.total, fail: counts.fail, warn: counts.warn, pass: counts.pass }) }}
        </p>

        <!-- 4 stat cards -->
        <div class="stat-grid">
          <div class="stat-card stat-card--total">
            <div class="stat-card__num">{{ counts.total }}</div>
            <div class="stat-card__label">{{ t('validation.stat_total') }}</div>
          </div>
          <div class="stat-card stat-card--pass">
            <div class="stat-card__num">{{ counts.pass }}</div>
            <div class="stat-card__label">{{ t('validation.stat_pass') }}</div>
          </div>
          <div class="stat-card stat-card--warn">
            <div class="stat-card__num">{{ counts.warn }}</div>
            <div class="stat-card__label">{{ t('validation.stat_warn') }}</div>
          </div>
          <div class="stat-card stat-card--fail">
            <div class="stat-card__num">{{ counts.fail }}</div>
            <div class="stat-card__label">{{ t('validation.stat_fail') }}</div>
          </div>
        </div>

        <!-- Field List (Grouping: Error / Warning / Pass) -->
        <section
          v-for="group in groupedResults"
          :key="group.severity"
          class="group"
          :class="`group--${group.severity}`"
        >
          <header class="group__header">
            <span class="group__dot" :class="`group__dot--${group.severity}`" aria-hidden="true"></span>
            <span class="group__title">{{ groupTitle(group.severity) }}</span>
            <span class="group__count">{{ group.items.length }}</span>
          </header>

          <ul class="item-list">
            <li
              v-for="r in group.items"
              :key="r.code"
              class="item"
              :class="`item--${r.severity}`"
              :data-testid="`validate-item-${r.severity}`"
            >
              <div class="item__head">
                <span class="item__icon" :class="`item__icon--${r.severity}`" aria-hidden="true">
                  {{ iconFor(r.severity) }}
                </span>
                <div class="item__head-text">
                  <div class="item__title">{{ fieldLabel(r.field) }}</div>
                  <div class="item__rule">{{ r.code }} · {{ severityLabel(r.severity) }}</div>
                </div>
              </div>

              <p class="item__msg">{{ resolveMessage(r) }}</p>

              <div v-if="r.severity !== 'pass' && r.details" class="item__details">
                <div v-if="r.details.value !== undefined" class="item__detail-row">
                  <span class="item__detail-label">{{ t('validation.details') }}:</span>
                  <code class="item__value item__value--bad">{{ r.details.value || t('validation.empty_value') }}</code>
                </div>
                <div v-else-if="r.details.months_remaining !== undefined" class="item__detail-row">
                  <span class="item__detail-label">{{ t('validation.details') }}:</span>
                  <span class="item__value">{{ t('validation.months_remaining', { n: r.details.months_remaining }) }}</span>
                </div>
                <div v-else-if="r.details.confidence !== undefined" class="item__detail-row">
                  <span class="item__detail-label">{{ t('validation.details') }}:</span>
                  <span class="item__value">{{ Math.round(r.details.confidence * 100) }}%</span>
                </div>
              </div>

              <div class="item__remediation" v-if="r.severity === 'error'">
                <span class="item__remediation-label">{{ t('validation.remediation') }}:</span>
                <span>{{ resolveMessage(r) }}</span>
              </div>

              <div class="item__actions" v-if="r.severity === 'error'">
                <AppButton
                  ref="rescanBtnRefs"
                  :item-key="r.code"
                  variant="danger"
                  size="sm"
                  :data-testid="`validate-rescan-${r.code}`"
                >
                  {{ t('validation.btn_rescan') }}
                </AppButton>
              </div>
            </li>
          </ul>
        </section>

        <!-- Bottom buttons - W3 root-fix: AppButton + ref.setOnTrigger pattern -->
        <footer class="page-footer">
          <AppButton
            ref="rescanAllBtnRef"
            variant="outline"
            size="md"
            data-testid="validate-rescan-all"
          >
            {{ t('validation.btn_rescan') }}
          </AppButton>
          <AppButton
            ref="continueBtnRef"
            variant="primary"
            size="md"
            :disabled="counts.fail > 0"
            :title="counts.fail > 0 ? t('validation.btn_continue_hint') : ''"
            data-testid="validate-continue"
          >
            {{ t('validation.btn_continue') }}
            <span v-if="counts.fail > 0" class="badge-warn">W2-D3</span>
          </AppButton>
        </footer>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import HtexLogo from '@/components/HtexLogo.vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { validateMaterials } from '@/api/materials'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'

const { t, te } = useI18n()
const router = useRouter()
const route = useRoute()
const toast = useToast()

// Real backend may be slower; mock 600ms; give 1.2x buffer
const REQUEST_TIMEOUT_MS = 15000

const loading = ref(false)
const loadError = ref('')
const results = ref([])

const counts = computed(() => {
  const c = { total: 0, pass: 0, warn: 0, fail: 0 }
  for (const r of results.value) {
    c.total += 1
    if (r.severity === 'error') c.fail += 1
    else if (r.severity === 'warning') c.warn += 1
    else if (r.severity === 'pass') c.pass += 1
  }
  return c
})

const hasResults = computed(() => results.value.length > 0)

const groupedResults = computed(() => {
  // Order: error -> warning -> pass
  const order = ['error', 'warning', 'pass']
  const buckets = { error: [], warning: [], pass: [] }
  for (const r of results.value) {
    const k = buckets[r.severity] ? r.severity : 'pass'
    buckets[k].push(r)
  }
  return order
    .filter((k) => buckets[k].length)
    .map((k) => ({ severity: k, items: buckets[k] }))
})

function severityLabel(s) {
  if (s === 'error') return t('validation.severity_error')
  if (s === 'warning') return t('validation.severity_warn')
  return t('validation.severity_pass')
}

function groupTitle(s) {
  if (s === 'error') return t('validation.stat_fail')
  if (s === 'warning') return t('validation.stat_warn')
  return t('validation.stat_pass')
}

function iconFor(s) {
  if (s === 'error') return '✕'
  if (s === 'warning') return '!'
  return '✓'
}

// field -> friendly label (use i18n; fall back to original field name)
function fieldLabel(field) {
  if (!field) return ''
  const key = `validation.field_${field}`
  return te(key) ? t(key) : field
}

// Use message_key to find i18n; te() check if key exists
function resolveMessage(r) {
  if (r.message_key && te(r.message_key)) {
    return t(r.message_key)
  }
  // Fallback: use code as text
  return r.message_key || r.code
}

async function load(opts = {}) {
  loading.value = true
  loadError.value = ''
  try {
    // Contract (Option A): caller passes material_id array, callee accepts array
    // Prefer query material_ids (from /materials link will carry);
    // Otherwise empty array, backend runs "last submitted" batch (mock also fallback demo)
    const queryIds = (route.query.material_ids || '').toString().split(',').filter(Boolean).map((x) => Number(x))
    const materialIds = queryIds.length ? queryIds : (opts.material_ids || [])
    const data = await withTimeout(
      validateMaterials(materialIds),
      REQUEST_TIMEOUT_MS,
      'timeout'
    )
    results.value = Array.isArray(data?.results) ? data.results : []
  } catch (e) {
    loadError.value = e?.message || t('validation.load_failed')
  } finally {
    loading.value = false
  }
}

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`request_${label}`)), ms)
    promise.then(
      (v) => { clearTimeout(t); resolve(v) },
      (e) => { clearTimeout(t); reject(e) }
    )
  })
}

function onRevalidate() {
  load()
}

function onRescan(item) {
  // Jump to /materials/scan and pass rule code, scan page can prefill
  const qs = new URLSearchParams()
  if (item?.field) qs.set('field', item.field)
  if (item?.code) qs.set('rule', item.code)
  router.push({ path: '/materials/scan', query: Object.fromEntries(qs.entries()) })
}

function onRescanAll() {
  router.push('/materials/scan')
}

function onContinue() {
  if (counts.value.fail > 0) return
  // Pass previous material_ids through, OrderNew reads from query
  const ids = (route.query.material_ids || '').toString()
  const params = new URLSearchParams()
  if (ids) params.set('material_ids', ids)
  if (route.query.country) params.set('country', route.query.country)
  if (route.query.visa_type) params.set('visa_type', route.query.visa_type)
  router.push({ name: 'OrderNew', query: Object.fromEntries(params.entries()) })
}

// ============== W3 P0 root-fix: ref + setOnTrigger pattern ==============
// 3 main AppButtons (revalidate/rescanAll/continue) use ref to expose trigger
// @click direct binding changed to setOnTrigger inject, Vue @click bubbling no longer depends on AppButton internals
// W6-7 extend v-for rescan: use ref="rescanBtnRefs" + item-key inject each item callback
// Keep line 35 (goMaterials Empty state) @click direct bind: v-else-if one-time render, @click direct OK
const revalidateBtnRef = ref(null)
const rescanAllBtnRef = ref(null)
const continueBtnRef = ref(null)
// v-for rescan button: ref="rescanBtnRefs" is array, each element has setOnTrigger
// Use item-key (r.code) in watch then nextTick inject corresponding onRescan(r)
const rescanBtnRefs = ref([])
const rescanItemMap = ref(new Map())  // r.code -> r full object, for setOnTrigger closure

onMounted(() => {
  load()
  // Inject 3 main AppButton click callbacks (W3 root-fix: AppButton + setOnTrigger)
  if (revalidateBtnRef.value) revalidateBtnRef.value.setOnTrigger(onRevalidate)
  if (rescanAllBtnRef.value) rescanAllBtnRef.value.setOnTrigger(onRescanAll)
  if (continueBtnRef.value) continueBtnRef.value.setOnTrigger(onContinue)
})

// W6-7 root-fix: v-for rescan button - when groupedResults changes (error group re-render), inject after nextTick
// Each rescanBtnRefs[i] corresponds to error group i-th item in groupedResults
watch(
  groupedResults,
  async () => {
    await nextTick()
    // Collect all error items from groupedResults (v-for rescan only renders in error severity)
    const errorItems = groupedResults
      .filter((g) => g.severity === 'error')
      .flatMap((g) => g.items)
    rescanItemMap.value = new Map(errorItems.map((r) => [r.code, r]))
    rescanBtnRefs.value.forEach((btnRef, idx) => {
      const r = errorItems[idx]
      if (btnRef && r) {
        btnRef.setOnTrigger(() => onRescan(r))
      }
    })
  },
  { immediate: true, deep: true }
)
</script>

<style scoped lang="scss">
.validate-page {
  min-height: 100vh;
  background: var(--bg-alt, #F8FAFC);
  display: flex;
  flex-direction: column;
}

.validate-shell {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 20px 60px;
  width: 100%;
}

.page-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: var(--ink-1, #0F172A);
}
.page-sub {
  margin: 6px 0 24px;
  font-size: 14px;
  color: var(--ink-3, #64748B);
}

.state-loading, .state-error, .state-empty {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  color: var(--ink-3, #64748B);
}
.state-loading { display: flex; align-items: center; justify-content: center; gap: 12px; }
.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid var(--el-color-primary, #3B6EF5);
  border-top-color: transparent;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.state-error p { margin: 0 0 12px; color: var(--el-color-danger, #DC2626); }
.state-empty .empty-title { margin: 0 0 6px; font-size: 16px; font-weight: 600; color: var(--ink-1); }
.state-empty .empty-desc { margin: 0 0 16px; font-size: 13px; }

// Summary
.summary {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--ink-3, #64748B);
}

// 4 stat cards
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 28px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 22px 16px;
  text-align: center;
  border-top-width: 3px;
}
.stat-card--total { border-top-color: var(--el-color-primary, #3B6EF5); }
.stat-card--pass  { border-top-color: #16A34A; }
.stat-card--warn  { border-top-color: #D97706; }
.stat-card--fail  { border-top-color: #DC2626; }

.stat-card__num {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 6px;
  color: var(--ink-1, #0F172A);
}
.stat-card--pass .stat-card__num { color: #16A34A; }
.stat-card--warn .stat-card__num { color: #D97706; }
.stat-card--fail .stat-card__num { color: #DC2626; }

.stat-card__label {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--ink-3, #64748B);
  text-transform: uppercase;
}

// Grouping
.group {
  margin-bottom: 22px;
  &__header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 10px;
    font-size: 13px; font-weight: 600; color: var(--ink-2, #334155);
  }
  &__dot { width: 8px; height: 8px; border-radius: 50%; }
  &__dot--error { background: #DC2626; }
  &__dot--warning { background: #D97706; }
  &__dot--pass { background: #16A34A; }
  &__count {
    margin-left: auto;
    background: var(--bg-alt, #F1F5F9);
    color: var(--ink-3, #64748B);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 500;
  }
}

// List
.item-list {
  list-style: none;
  padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 8px;
}
.item {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-left-width: 3px;
  border-radius: 10px;
  padding: 14px 16px;

  &--error   { border-left-color: #DC2626; background: #FEF2F2; }
  &--warning { border-left-color: #D97706; background: #FFFBEB; }
  &--pass    { border-left-color: #16A34A; }

  &__head {
    display: flex; align-items: flex-start; gap: 10px;
    margin-bottom: 6px;
  }
  &__icon {
    width: 22px; height: 22px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0;
  }
  &__icon--error   { background: #DC2626; }
  &__icon--warning { background: #D97706; }
  &__icon--pass    { background: #16A34A; }

  &__head-text { flex: 1; }
  &__title { font-size: 14px; font-weight: 600; color: var(--ink-1, #0F172A); }
  &__rule { font-size: 11px; color: var(--ink-3, #64748B); font-family: monospace; }

  &__msg {
    margin: 6px 0 0 32px;
    font-size: 13px;
    color: var(--ink-2, #334155);
    line-height: 1.5;
  }

  &__details {
    margin: 6px 0 0 32px;
    font-size: 12px;
  }
  &__detail-row { display: flex; gap: 6px; align-items: center; }
  &__detail-label { color: var(--ink-3, #64748B); }
  &__value {
    font-family: monospace;
    font-size: 12px;
    color: var(--ink-2, #334155);
  }
  &__value--bad { color: #DC2626; font-weight: 600; }

  &__remediation {
    margin: 8px 0 0 32px;
    padding: 8px 10px;
    background: rgba(220, 38, 38, 0.06);
    border-radius: 6px;
    font-size: 12px;
    color: #991B1B;
  }
  &__remediation-label { font-weight: 600; margin-right: 4px; }

  &__actions {
    margin-top: 10px;
    display: flex;
    justify-content: flex-end;
  }
}

// Bottom
.page-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid var(--border, #E2E8F0);
}
.badge-warn {
  margin-left: 6px;
  padding: 1px 6px;
  background: #FEF3C7;
  color: #92400E;
  font-size: 10px;
  font-weight: 600;
  border-radius: 4px;
  letter-spacing: 0.04em;
}

// Responsive
@media (max-width: 720px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .item__msg, .item__details, .item__remediation { margin-left: 0; }
  .item__actions { justify-content: stretch; }
}
</style>
