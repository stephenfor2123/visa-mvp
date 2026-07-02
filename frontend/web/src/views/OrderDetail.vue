<!--
  OrderDetail.vue — A Story 1.2.2a
  =================================
  N4 Order status detail page (V2 §3.6.2)

  Key capabilities:
    1) 5-state timeline: created -> submitted -> reviewing -> approved (rejected branch)
    2) WebSocket primary (ws://.../ws/orders/{orderNo}) + 30s polling fallback
    3) ETag If-None-Match (304 not updating UI)
    4) Current state highlight (blue/green/red/grey)
    5) RPA screenshot replay (rpa_screenshot_url + rpa_screenshots array)
    6) Cancel order (created state only, 4010 toast)
    7) Logout (clear localStorage.visa.auth -> jump /login)

  Mock mode: VITE_MOCK=true (default) uses localStorage fallback, WS via window.__visaMockPush()
  Real backend mode: VITE_MOCK=false direct to B /api/v2/orders/{no}, WS direct to backend ws endpoint
-->
<template>
  <div class="orderdetail-page">
    <AppHeader scope="order-detail" />
    <main class="app-container app-page orderdetail-shell">
      <!-- Loading/Error -->
      <div v-if="loading && !order" class="state-block" data-testid="orderdetail-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('common.loading') }}
      </div>
      <div v-else-if="loadError" class="state-block state-block--err" data-testid="orderdetail-error">
        <p>❌ {{ loadError }}</p>
        <AppButton ref="retryBtnRef" variant="outline" size="md">{{ t('orderdetail.retry_btn') }}</AppButton>
      </div>

      <template v-else-if="order">
        <!-- Top: order number + current status badge -->
        <section class="hero" data-testid="orderdetail-hero">
          <div class="hero__left">
            <p class="hero__label">{{ t('orderdetail.order_no_label') }}</p>
            <h1 class="hero__no" data-testid="orderdetail-order-no">{{ order.order_no }}</h1>
            <p class="hero__sub">{{ t('orderdetail.page_subtitle') }}</p>
          </div>
          <div class="hero__right">
            <span
              class="status-badge"
              :class="`status-badge--${order.status}`"
              data-testid="orderdetail-status-badge"
            >
              <span class="status-badge__icon">{{ statusIcon(order.status) }}</span>
              <span>{{ statusLabel(order.status) }}</span>
            </span>
            <p class="hero__updated" data-testid="orderdetail-updated">
              {{ t('orderdetail.updated_at_label') }}: {{ formatDateTime(order.updated_at) }}
            </p>
          </div>
        </section>

        <!-- 5-state timeline -->
        <section class="card" data-testid="orderdetail-timeline">
          <h2 class="card__title">{{ t('orderdetail.section_timeline') }}</h2>
          <div class="timeline">
            <div
              v-for="(step, idx) in TIMELINE_STEPS"
              :key="step.key"
              class="tl-step"
              :class="{
                'tl-step--done': isStepDone(step.key, order.status),
                'tl-step--current': order.status === step.key,
                'tl-step--pending': !isStepDone(step.key, order.status) && order.status !== step.key
              }"
              :data-testid="`orderdetail-tl-${step.key}`"
            >
              <div class="tl-step__node">
                <span v-if="isStepDone(step.key, order.status) && order.status !== step.key" class="tl-step__check">✓</span>
                <span v-else>{{ statusIcon(step.key) }}</span>
              </div>
              <div class="tl-step__body">
                <p class="tl-step__label">{{ t(step.label) }}</p>
                <p class="tl-step__desc">{{ t(`orderdetail.desc_${step.key}`) }}</p>
                <p
                  v-if="order.status === step.key"
                  class="tl-step__now"
                  data-testid="orderdetail-tl-current"
                >● {{ statusLabel(order.status) }}</p>
              </div>
              <div v-if="idx < TIMELINE_STEPS.length - 1" class="tl-step__line"></div>
            </div>

            <!-- Branch state: rejected / cancelled shown separately (W3 cancel flow strengthened add cancelled terminal) -->
            <template v-for="branch in TIMELINE_BRANCHES" :key="branch.key">
              <div
                v-if="isBranchReached(branch.key, order.status)"
                class="tl-step tl-step--branch"
                :class="{
                  'tl-step--current': order.status === branch.key,
                  [`tl-step--branch-${branch.key}`]: true
                }"
                :data-testid="`orderdetail-tl-${branch.key}`"
              >
              <div class="tl-step__node">
                <span>{{ statusIcon(branch.key) }}</span>
              </div>
              <div class="tl-step__body">
                <p class="tl-step__label">{{ t(branch.label) }}</p>
                <p class="tl-step__desc">{{ t(`orderdetail.desc_${branch.key}`) }}</p>
                <p
                  v-if="order.status === branch.key"
                  class="tl-step__now"
                  :data-testid="`orderdetail-tl-${branch.key}-current`"
                >● {{ statusLabel(order.status) }}</p>
              </div>
              </div>
            </template>
          </div>
        </section>

        <!-- Order basic info -->
        <section class="card" data-testid="orderdetail-info">
          <h2 class="card__title">{{ t('orderdetail.section_basic') }}</h2>
          <dl class="info-list">
            <div class="info-list__row">
              <dt>{{ t('orderdetail.destination_label') }}</dt>
              <dd>{{ destinationName }} <span v-if="order.destination_id" class="info-list__chip">#{{ order.destination_id }}</span></dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.visa_type_label') }}</dt>
              <dd>{{ visaTypeName }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.amount_label') }}</dt>
              <dd>{{ formatAmount(order.total_amount, order.currency) }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.created_at_label') }}</dt>
              <dd>{{ formatDateTime(order.created_at) }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.status_label') }}</dt>
              <dd>
                <span class="status-chip" :class="`status-chip--${order.status}`">
                  {{ statusIcon(order.status) }} {{ statusLabel(order.status) }}
                </span>
              </dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.materials_count', { n: (order.material_ids || []).length }) }}</dt>
              <dd>
                <span v-if="(order.material_ids || []).length === 0">—</span>
                <span v-else class="info-list__ids">
                  <span
                    v-for="mid in order.material_ids"
                    :key="mid"
                    class="info-list__chip"
                  >#{{ mid }}</span>
                </span>
              </dd>
            </div>
            <!-- A-W9-2: affiliate source (only shown when commission loaded) -->
            <div
              v-if="commission"
              class="info-list__row"
              data-testid="orderdetail-affiliate-row"
            >
              <dt>{{ t('affiliate.commission_label') }}</dt>
              <dd>
                <span class="affiliate-pill" data-testid="orderdetail-affiliate-pill">
                  <span class="affiliate-pill__icon">🤝</span>
                  <span class="affiliate-pill__partner">{{ commission.partner_id }}</span>
                  <span class="affiliate-pill__rate">{{ formatRate(commission.commission_rate) }}</span>
                  <span class="affiliate-pill__amount" v-if="commission.commission_amount_cents">
                    · {{ formatCommission(commission.commission_amount_cents, commission.currency) }}
                  </span>
                </span>
              </dd>
            </div>
          </dl>

          <!-- Rejection reason -->
          <div
            v-if="order.status === 'rejected' && order.rejection_reason"
            class="rejection-box"
            data-testid="orderdetail-rejection"
          >
            <h3 class="rejection-box__title">❌ {{ t('orderdetail.rejection_reason_title') }}</h3>
            <p class="rejection-box__text">
              {{ order.rejection_reason[locale] || order.rejection_reason.zh || order.rejection_reason.en }}
            </p>
          </div>
        </section>

        <!-- RPA screenshots -->
        <section class="card" data-testid="orderdetail-rpa">
          <h2 class="card__title">{{ t('orderdetail.section_rpa') }}</h2>
          <div v-if="rpaImages.length === 0" class="rpa-empty" data-testid="orderdetail-rpa-empty">
            <span class="rpa-empty__icon">📷</span>
            <p>{{ t('orderdetail.rpa_empty') }}</p>
          </div>
          <div v-else class="rpa-grid" data-testid="orderdetail-rpa-grid">
            <a
              v-for="(url, i) in rpaImages"
              :key="i"
              :href="url"
              target="_blank"
              rel="noopener noreferrer"
              class="rpa-card"
            >
              <img
                :src="url"
                :alt="`RPA Step ${i + 1}`"
                loading="lazy"
                @error="onImgError($event, i)"
              />
              <span class="rpa-card__step">Step {{ i + 1 }}</span>
            </a>
          </div>
        </section>

        <!-- Action area -->
        <section class="card" data-testid="orderdetail-actions">
          <h2 class="card__title">{{ t('orderdetail.section_actions') }}</h2>
          <div class="actions-row">
            <!-- Cancel order: only clickable in created state -->
            <AppButton
              v-if="order.status === 'created'"
              ref="cancelBtnRef"
              variant="danger"
              size="md"
              :loading="cancelling"
              data-testid="orderdetail-cancel-btn"
            >{{ t('orderdetail.cancel_btn') }}</AppButton>
            <span
              v-else
              class="actions-hint"
              data-testid="orderdetail-cancel-hint"
            >{{ t('orderdetail.cancel_blocked') }}</span>

            <!-- Visa issued PDF download -->
            <AppButton
              v-if="order.status === 'approved' && order.visa_pdf_url"
              ref="pdfBtnRef"
              variant="primary"
              size="md"
              data-testid="orderdetail-pdf-btn"
            >⬇ {{ t('orderdetail.visa_pdf_btn') }}</AppButton>

            <!-- Re-apply after rejection -->
            <AppButton
              v-if="order.status === 'rejected'"
              ref="reapplyBtnRef"
              variant="outline"
              size="md"
              data-testid="orderdetail-reapply-btn"
            >↻ {{ t('orderdetail.reapply_btn') }}</AppButton>

            <!-- Back -->
            <AppButton
              ref="backBtnRef"
              variant="ghost"
              size="md"
              data-testid="orderdetail-back-btn"
            >← {{ t('orderdetail.back_btn') }}</AppButton>
          </div>
        </section>
      </template>
    </main>

    <!-- Cancel order confirmation modal -->
    <div v-if="cancelModal" class="modal-mask" @click.self="cancelModal = false" data-testid="orderdetail-cancel-modal">
      <div class="modal-box">
        <h3 class="modal-box__title">{{ t('orderdetail.cancel_confirm_title') }}</h3>
        <p class="modal-box__body">{{ t('orderdetail.cancel_confirm_body') }}</p>
        <div class="modal-box__actions">
          <AppButton ref="cancelNoRef" variant="ghost" size="md" data-testid="orderdetail-cancel-no">
            {{ t('orderdetail.cancel_confirm_no') }}
          </AppButton>
          <AppButton ref="cancelYesRef" variant="danger" size="md" :loading="cancelling" data-testid="orderdetail-cancel-yes">
            {{ t('orderdetail.cancel_confirm_ok') }}
          </AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  getOrder,
  cancelOrder,
  pollOrderStatus,
  TIMELINE_STEPS,
  BRANCH_STEPS
} from '@/api/orders'
// A-W9-2: query order commission, detail page shows "Affiliate source: PARTNER001 (5% commission)"
import { getCommission } from '@/api/affiliate'
import AppHeader from '@/components/AppHeader.vue'

const { t, te, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

// ============== State ==============
const order = ref(null)
const loading = ref(false)
const loadError = ref('')
const cancelling = ref(false)
const cancelModal = ref(false)
const wsState = ref('connecting')  // connecting | connected | fallback
const countdownSec = ref(30)
const imgErrors = reactive(new Set())
// A-W9-2: commission data { partner_id, commission_rate, commission_amount_cents, currency }
// null means no affiliate source (404 silent) or Loading
const commission = ref(null)

let cancelPoll = null
let countdownTimer = null

const orderNo = computed(() => (route.params.orderNo || '').toString())

// W3 Story 3.2.2 cancel flow strengthened: extend branch, add cancelled terminal (W2 1.2.2a only had rejected)
const TIMELINE_BRANCHES = [
  ...BRANCH_STEPS,
  { key: 'cancelled', label: 'orderdetail.status_cancelled' }
]

// ============== Status mapping ==============
function statusLabel(s) {
  const k = `orderdetail.status_${s}`
  return te(k) ? t(k) : s
}
function statusIcon(s) {
  const k = `orderdetail.icon_${s}`
  if (te(k)) return t(k)
  // fallback unicode
  const map = {
    created: '📝', submitted: '📤', reviewing: '🔍',
    approved: '✅', rejected: '❌', cancelled: '🚫',
    closed: '🔒', failed: '⚠️', abnormal: '🆘'
  }
  return map[s] || '•'
}

function isStepDone(stepKey, currentStatus) {
  const order5 = ['created', 'submitted', 'reviewing', 'approved']
  const si = order5.indexOf(stepKey)
  if (si < 0) return false
  // On rejection, reviewing also counts as done
  if (currentStatus === 'rejected') {
    return si <= order5.indexOf('reviewing')
  }
  // On cancel, created reaches main axis start (only mark created done)
  if (currentStatus === 'cancelled') {
    return si <= order5.indexOf('created')
  }
  const ci = order5.indexOf(currentStatus)
  if (ci < 0) return false
  return si <= ci
}
function isBranchReached(branchKey, status) {
  // W3 cycle 5 double check: must reach branch (status in rejected/cancelled) + this branchKey equals status
  // Otherwise cancelled will also render rejected branch (cycle 1-4 bug)
  const terminalReached = status === 'rejected' || status === 'cancelled'
  return terminalReached && branchKey === status
}

const destinationName = computed(() => {
  if (!order.value) return '—'
  // mock mode: from destinations cache or hardcode guess (L4 i18n: use t() with i18n key)
  if (order.value.destination_id === 1) return t('country.us')
  if (order.value.destination_id === 2) return t('country.jp')
  if (order.value.destination_id === 3) return t('country.uk')
  if (order.value.destination_id === 4) return t('country.au')
  if (order.value.destination_id === 5) return t('country.ca')
  if (order.value.destination_id === 6) return t('country.de_schengen')
  if (order.value.destination_id === 7) return t('country.fr_schengen')
  if (order.value.destination_id === 8) return t('country.sg')
  if (order.value.destination_id === 9) return t('country.nz')
  return `#${order.value.destination_id}`
})

const visaTypeName = computed(() => {
  if (!order.value) return '—'
  return order.value.visa_type === 'tourism' ? t('orders.visa_tourism')
       : order.value.visa_type === 'student' ? t('orders.visa_student')
       : order.value.visa_type
})

const rpaImages = computed(() => {
  if (!order.value) return []
  const arr = order.value.rpa_screenshots || []
  const single = order.value.rpa_screenshot_url
  if (single && !arr.includes(single)) arr.unshift(single)
  return arr.filter((u) => u && !imgErrors.has(u))
})

// ============== Formatters ==============
function formatDateTime(s) {
  if (!s) return '—'
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}`
  } catch {
    return s
  }
}
function formatAmount(n, currency) {
  if (n == null || n === 0) return '—'
  return `${currency || 'USD'} ${Number(n).toFixed(2)}`
}
function onImgError(e, idx) {
  const src = e?.target?.src
  if (src) imgErrors.add(src)
}

// ============== Data Loading + Realtime subscription ==============
async function loadInitial() {
  if (!orderNo.value) {
    loadError.value = t('orderdetail.not_found')
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const r = await getOrder(orderNo.value, { etag: null })
    if (r.data) {
      order.value = r.data
    } else if (r.notModified) {
      // Rare: first is 304, keep current
    }
  } catch (e) {
    if (e?.code === '4004' || e?.status === 404) {
      loadError.value = t('orderdetail.not_found')
    } else {
      loadError.value = e?.message || t('orderdetail.load_failed')
    }
    order.value = null
  } finally {
    loading.value = false
  }
  // A-W9-2: load commission (silent, failure as no source)
  loadCommission()
  // Start pollOrderStatus (WebSocket primary + polling fallback)
  startRealtime()
}

// A-W9-2: load commission - call /api/v2/affiliate/commission/{order_id}
// Return null means no source (404 silent), UI hides source row
async function loadCommission() {
  if (!order.value?.order_no) return
  try {
    const data = await getCommission(order.value.order_no)
    commission.value = data
  } catch (_) {
    commission.value = null
  }
}

// Commission display helper: convert cents to "$1.25" format
function formatCommission(cents, currency) {
  if (cents == null) return ''
  const cur = currency || 'USD'
  const val = (Number(cents) / 100).toFixed(2)
  return `${cur} ${val}`
}
// Commission rate "0.05" -> "5%"
function formatRate(rate) {
  if (!rate) return ''
  const n = Number(rate)
  if (isNaN(n)) return String(rate)
  return `${(n * 100).toFixed(0)}%`
}

function startRealtime() {
  stopRealtime()
  wsState.value = 'connecting'
  countdownSec.value = 30
  // Countdown (display)
  countdownTimer = setInterval(() => {
    countdownSec.value = Math.max(0, countdownSec.value - 1)
    if (countdownSec.value === 0) countdownSec.value = 30
  }, 1000)
  // Realtime subscription
  cancelPoll = pollOrderStatus(orderNo.value, (data, source) => {
    if (!data) return
    if (data.__ws === 'connected') {
      wsState.value = 'connected'
      return
    }
    if (data.__ws === 'error' || data.__ws === 'closed') {
      wsState.value = 'fallback'
      return
    }
    // Normal data update
    if (source === 'ws-mock' || source === 'ws' || source === 'polling' || source === 'polling-same') {
      order.value = { ...(order.value || {}), ...data }
      countdownSec.value = 30
      if (source === 'polling' || source === 'ws-mock') {
        // eslint-disable-next-line no-console
        if (typeof console !== 'undefined' && console.log) {
          console.log(`[orderdetail] status update via ${source}:`, data.status)
        }
      }
    }
  }, { intervalMs: 30000, wsTimeoutMs: 3000 })
}

function stopRealtime() {
  if (cancelPoll) {
    try { cancelPoll() } catch (_) {}
    cancelPoll = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ============== Actions ==============
function onCancel() {
  cancelModal.value = true
}
async function doCancel() {
  if (!order.value) return
  cancelling.value = true
  try {
    await cancelOrder(order.value.order_no)
    order.value = { ...order.value, status: 'cancelled', updated_at: new Date().toISOString() }
    cancelModal.value = false
    toast.success(t('orderdetail.cancel_success'))
  } catch (e) {
    if (e?.code === '4010') {
      toast.error(t('orderdetail.cancel_blocked'))
    } else {
      toast.error(e?.message || t('orderdetail.cancel_failed'))
    }
  } finally {
    cancelling.value = false
  }
}

function onDownloadPdf() {
  if (order.value?.visa_pdf_url) {
    window.open(order.value.visa_pdf_url, '_blank', 'noopener,noreferrer')
  }
}
function onReapply() {
  // Jump back to /destinations to re-select
  router.push('/destinations')
}
function goBack() {
  // Back via history stack, else go /home
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/home')
  }
}

// Route change (orderNo change) reload
watch(orderNo, (v, prev) => {
  if (v && v !== prev) {
    order.value = null
    loadInitial()
  }
})

// ============== W4 P0 root-fix: ref + onTrigger pattern (reuse W3 A-3.1.1a) ==============
// 8 AppButtons use ref to expose onTrigger, Vue @click bubbling no longer depends on AppButton internals
// 6 persistent: logout / retry / cancel / pdf / reapply / back
// 2 modal: cancelNo / cancelYes (v-if controlled, nextTick inject on open)
const retryBtnRef = ref(null)
const cancelBtnRef = ref(null)
const pdfBtnRef = ref(null)
const reapplyBtnRef = ref(null)
const backBtnRef = ref(null)
const cancelNoRef = ref(null)
const cancelYesRef = ref(null)

// Inject 2 button triggers on modal open (v-if mount after ref has value)
watch(cancelModal, async (val) => {
  if (val) {
    await nextTick()
    if (cancelNoRef.value) cancelNoRef.value.setOnTrigger(() => { cancelModal.value = false })
    if (cancelYesRef.value) cancelYesRef.value.setOnTrigger(doCancel)
  }
})

onMounted(async () => {
  auth.hydrate()
  await loadInitial()
  // Inject 5 persistent AppButton click callbacks (W3 root-fix AppButton + setOnTrigger pattern)
  if (retryBtnRef.value) retryBtnRef.value.setOnTrigger(loadInitial)
  if (cancelBtnRef.value) cancelBtnRef.value.setOnTrigger(onCancel)
  if (pdfBtnRef.value) pdfBtnRef.value.setOnTrigger(onDownloadPdf)
  if (reapplyBtnRef.value) reapplyBtnRef.value.setOnTrigger(onReapply)
  if (backBtnRef.value) backBtnRef.value.setOnTrigger(goBack)
})

onBeforeUnmount(() => {
  stopRealtime()
})
</script>

<style scoped lang="scss">
.orderdetail-page { min-height: 100vh; background: #FFFFFF; }

// ============== Header ==============
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; background: #fff; border-bottom: 1px solid var(--border, #E2E8F0);
}
.ws-pill {
  display: inline-flex; align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.ws-pill--ok { background: #DCFCE7; color: #166534; border: 1px solid #86EFAC; }
.ws-pill--pending { background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }
.ws-pill--fallback { background: #EAF0FE; color: #2D5BFF; border: 1px solid #93C5FD; }

.orderdetail-shell { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }

// ============== Hero ==============
.hero {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 18px;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 22px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
}
.hero__label { margin: 0 0 4px; font-size: 12px; color: var(--ink-3, #64748B); letter-spacing: 0.04em; text-transform: uppercase; }
.hero__no { margin: 0; font-size: 24px; font-weight: 700; color: var(--ink-1, #0F172A); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.hero__sub { margin: 6px 0 0; font-size: 13px; color: var(--ink-3, #64748B); }
.hero__right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.hero__updated { margin: 0; font-size: 12px; color: var(--ink-3, #64748B); }

.status-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 999px;
  font-size: 14px; font-weight: 600;
}
.status-badge__icon { font-size: 16px; }
.status-badge--created   { background: #F1F5F9; color: #475569; }
.status-badge--submitted { background: #DBEAFE; color: #1E40AF; }
.status-badge--reviewing { background: #FEF3C7; color: #92400E; }
.status-badge--approved  { background: #DCFCE7; color: #166534; }
.status-badge--rejected  { background: #FEE2E2; color: #991B1B; }
.status-badge--cancelled { background: #F1F5F9; color: #64748B; }
.status-badge--closed    { background: #E2E8F0; color: #475569; }
.status-badge--failed    { background: #FEF2F2; color: #B91C1C; }
.status-badge--abnormal  { background: #FFF7ED; color: #C2410C; }

// ============== Card ==============
.card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 22px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
  margin-bottom: 18px;
}
.card__title {
  margin: 0 0 16px; font-size: 17px; font-weight: 600;
  color: var(--ink-1, #0F172A);
  display: flex; align-items: center; gap: 8px;
  &::before {
    content: ''; width: 3px; height: 16px; background: #3B6EF5; border-radius: 2px;
  }
}

// ============== Timeline ==============
.timeline {
  position: relative;
  display: flex; flex-direction: column; gap: 4px;
}
.tl-step {
  position: relative;
  display: flex; align-items: flex-start; gap: 14px;
  padding: 12px 0;
  &__node {
    flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%;
    background: #F1F5F9; color: #94A3B8;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 16px;
    border: 2px solid #E2E8F0;
    transition: all .2s;
  }
  &__check { color: #16A34A; font-weight: 700; }
  &__body { flex: 1; min-width: 0; }
  &__label { margin: 0 0 2px; font-size: 14px; font-weight: 600; color: var(--ink-1, #0F172A); }
  &__desc  { margin: 0; font-size: 12px; color: var(--ink-3, #64748B); }
  &__now {
    margin: 6px 0 0; font-size: 12px; color: var(--el-color-primary, #3B6EF5);
    font-weight: 600; display: inline-flex; align-items: center; gap: 4px;
    animation: pulse 1.6s ease-in-out infinite;
  }
  &__line {
    position: absolute; left: 17px; top: 48px; bottom: -16px; width: 2px;
    background: #E2E8F0;
  }
  &--done &__node { background: #DCFCE7; border-color: #86EFAC; color: #166534; }
  &--done &__label { color: var(--ink-2, #334155); }
  &--current &__node { background: #3B6EF5; border-color: #3B6EF5; color: #fff; box-shadow: 0 0 0 4px rgba(59,110,245,.15); }
  &--current &__label { color: #2D5BFF; }
  &--pending &__node { background: #F8FAFC; border-color: #E2E8F0; color: #94A3B8; }
  &--branch { padding-left: 0; }
  &--branch &__node { background: #FEE2E2; border-color: #FCA5A5; color: #991B1B; }
  &--branch.tl-step--current &__node { background: #DC2626; border-color: #DC2626; color: #fff; box-shadow: 0 0 0 4px rgba(220,38,38,.15); }
  // W3 cancelled terminal branch style (grey, not glaring)
  &--branch-cancelled &__node { background: #F1F5F9; border-color: #CBD5E1; color: #64748B; }
  &--branch-cancelled.tl-step--current &__node { background: #64748B; border-color: #64748B; color: #fff; box-shadow: 0 0 0 4px rgba(100,116,139,.15); }
}
.tl-step:last-child .tl-step__line { display: none; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .55; }
}

// ============== Info list ==============
.info-list { margin: 0; padding: 0; }
.info-list__row {
  display: grid; grid-template-columns: 130px 1fr;
  gap: 12px; padding: 9px 0;
  border-bottom: 1px dashed var(--border, #E2E8F0);
  font-size: 14px;
}
.info-list__row:last-child { border-bottom: none; }
.info-list__row dt { color: var(--ink-3, #64748B); margin: 0; }
.info-list__row dd { color: var(--ink-1, #0F172A); margin: 0; font-weight: 500; }
.info-list__ids { display: inline-flex; flex-wrap: wrap; gap: 4px; }
.info-list__chip {
  display: inline-block; padding: 1px 8px; background: #EAF0FE; color: #2D5BFF;
  border-radius: 999px; font-size: 11px; font-weight: 500; font-family: ui-monospace, monospace;
}

.status-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 500;
}
.status-chip--created   { background: #F1F5F9; color: #475569; }
.status-chip--submitted { background: #DBEAFE; color: #1E40AF; }
.status-chip--reviewing { background: #FEF3C7; color: #92400E; }
.status-chip--approved  { background: #DCFCE7; color: #166534; }
.status-chip--rejected  { background: #FEE2E2; color: #991B1B; }
.status-chip--cancelled { background: #F1F5F9; color: #64748B; }

// A-W9-2: affiliate source pill (order detail commission display)
.affiliate-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; background: #FEF3C7; color: #92400E;
  border: 1px solid #FCD34D; border-radius: 999px;
  font-size: 12px; font-weight: 500;
  &__icon { font-size: 14px; }
  &__partner { font-family: ui-monospace, monospace; font-weight: 600; }
  &__rate { color: #B45309; font-weight: 600; }
  &__amount { color: var(--ink-3, #64748B); font-size: 11px; }
}

.rejection-box {
  margin-top: 18px;
  background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 10px;
  padding: 14px 16px;
}
.rejection-box__title { margin: 0 0 6px; font-size: 14px; color: #991B1B; font-weight: 600; }
.rejection-box__text  { margin: 0; font-size: 13px; color: #7F1D1D; line-height: 1.55; }

// ============== RPA ==============
.rpa-empty {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 30px; color: var(--ink-3, #64748B);
  background: var(--bg-alt, #F8FAFC); border: 1px dashed var(--border, #E2E8F0);
  border-radius: 10px;
}
.rpa-empty__icon { font-size: 32px; }
.rpa-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.rpa-card {
  position: relative; display: block;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 10px; overflow: hidden;
  text-decoration: none;
  transition: transform .15s, box-shadow .15s;
}
.rpa-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(15,23,42,.08); }
.rpa-card img { display: block; width: 100%; height: 140px; object-fit: cover; background: #F1F5F9; }
.rpa-card__step {
  position: absolute; top: 8px; left: 8px;
  background: rgba(15,23,42,.7); color: #fff;
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px;
}

// ============== Actions ==============
.actions-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
}
.actions-hint { font-size: 12px; color: var(--ink-3, #64748B); }

// ============== State ==============
.state-block {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 40px; text-align: center;
  color: var(--ink-3, #64748B); font-size: 14px;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.state-block--err { color: #DC2626; flex-direction: column; }
.state-block--err p { margin: 0; }
.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #3B6EF5; border-top-color: transparent;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

// ============== Modal ==============
.modal-mask {
  position: fixed; inset: 0;
  background: rgba(15,23,42,.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.modal-box {
  background: #fff; border-radius: 14px;
  padding: 24px 26px;
  max-width: 420px; width: calc(100% - 40px);
  box-shadow: 0 20px 60px rgba(15,23,42,.2);
  &__title { margin: 0 0 8px; font-size: 17px; font-weight: 700; color: #0F172A; }
  &__body  { margin: 0 0 18px; font-size: 14px; color: #475569; line-height: 1.55; }
  &__actions { display: flex; justify-content: flex-end; gap: 8px; }
}
</style>
