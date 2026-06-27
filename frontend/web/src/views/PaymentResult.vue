<!--
  PaymentResult.vue — W14 支付结果页
  ===================================
  V2 §3.5.6 + 交接文档 §3.4:支付结果页

  4 种状态:
    - success   绿色 ✓ + 订单号 + 预计处理时间
    - failed    红色 ✗ + 失败原因(多语种)+ 重试按钮
    - pending   黄色 ⏳ + 轮询中动画(30s 间隔)
    - cancelled 灰色 — + 用户主动取消提示

  数据:
    GET /api/v2/payment/status/{orderId}   - 轮询
    POST /api/v2/payment/cancel/{orderId}
    POST /api/v2/payment/retry/{orderId}

  路由:
    /payment/result?orderId=xxx&status=xxx

  Mock 模式: VITE_MOCK=true 走 localStorage.visa.payments
-->
<template>
  <div class="paymentresult-page">
    <AppHeader scope="payment-result" />
    <main class="app-container app-page paymentresult-shell">
      <!-- Loading -->
      <div v-if="loading && !payment" class="state-block" data-testid="paymentresult-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('payment.loading_state') }}
      </div>

      <!-- Not found -->
      <section
        v-else-if="notFound"
        class="state-block state-block--warn"
        data-testid="paymentresult-not-found"
      >
        <p class="state-block__icon">⚠️</p>
        <h2 class="state-block__title">{{ t('payment.not_found_title') }}</h2>
        <p class="state-block__body">{{ t('payment.not_found_message', { orderId }) }}</p>
        <AppButton
          ref="nfBackBtnRef"
          variant="outline"
          size="md"
          data-testid="paymentresult-not-found-back"
        >{{ t('payment.back_to_orders') }}</AppButton>
      </section>

      <!-- Network / load error -->
      <section
        v-else-if="loadError && !payment"
        class="state-block state-block--err"
        data-testid="paymentresult-error"
      >
        <p>❌ {{ loadError }}</p>
        <AppButton
          ref="retryLoadBtnRef"
          variant="outline"
          size="md"
          data-testid="paymentresult-retry-load"
        >{{ t('payment.retry_load') }}</AppButton>
      </section>

      <!-- Status block -->
      <template v-else-if="payment">
        <!-- PENDING — animated polling -->
        <section
          v-if="status === 'pending'"
          class="status-card status-card--pending"
          data-testid="paymentresult-status-pending"
        >
          <div class="status-icon status-icon--pending">
            <span class="status-icon__emoji" aria-hidden="true">{{ t('payment.icon_pending') }}</span>
          </div>
          <h1 class="status-title">{{ t('payment.pending_title') }}</h1>
          <p class="status-message">{{ t('payment.pending_message') }}</p>
          <p class="status-hint">{{ t('payment.pending_wait_hint') }}</p>
          <div class="polling-bar">
            <span class="polling-dot" aria-hidden="true"></span>
            <span class="polling-dot" aria-hidden="true"></span>
            <span class="polling-dot" aria-hidden="true"></span>
          </div>
          <p class="polling-label" data-testid="paymentresult-polling-label">
            {{ t('payment.pending_polling_label', { sec: countdownSec }) }}
          </p>
          <div class="action-row">
            <AppButton
              ref="refreshBtnRef"
              variant="outline"
              size="md"
              data-testid="paymentresult-refresh"
            >{{ t('payment.pending_refresh_now') }}</AppButton>
            <AppButton
              ref="cancelBtnRef"
              variant="ghost"
              size="md"
              data-testid="paymentresult-cancel"
            >{{ t('common.cancel') }}</AppButton>
          </div>
        </section>

        <!-- SUCCESS -->
        <section
          v-else-if="status === 'success'"
          class="status-card status-card--success"
          data-testid="paymentresult-status-success"
        >
          <div class="status-icon status-icon--success">
            <span class="status-icon__emoji" aria-hidden="true">{{ t('payment.icon_success') }}</span>
          </div>
          <h1 class="status-title">{{ t('payment.success_title') }}</h1>
          <p class="status-message">{{ t('payment.success_message') }}</p>
          <p
            v-if="payment.estimated_processing_hours"
            class="status-eta"
            data-testid="paymentresult-eta"
          >
            {{ t('payment.estimated_processing', { hours: payment.estimated_processing_hours }) }}
          </p>
          <div class="action-row">
            <AppButton
              ref="successDetailBtnRef"
              variant="primary"
              size="md"
              data-testid="paymentresult-view-order"
            >{{ t('payment.success_next') }} →</AppButton>
          </div>
        </section>

        <!-- FAILED -->
        <section
          v-else-if="status === 'failed'"
          class="status-card status-card--failed"
          data-testid="paymentresult-status-failed"
        >
          <div class="status-icon status-icon--failed">
            <span class="status-icon__emoji" aria-hidden="true">{{ t('payment.icon_failed') }}</span>
          </div>
          <h1 class="status-title">{{ t('payment.failed_title') }}</h1>
          <p
            class="status-reason"
            data-testid="paymentresult-reason"
          >{{ reasonText }}</p>
          <div class="action-row">
            <AppButton
              ref="retryPayBtnRef"
              variant="primary"
              size="md"
              :loading="retrying"
              data-testid="paymentresult-retry-pay"
            >{{ t('payment.retry_button') }}</AppButton>
            <AppButton
              ref="failedBackBtnRef"
              variant="ghost"
              size="md"
              data-testid="paymentresult-failed-back"
            >{{ t('payment.back_to_orders') }}</AppButton>
          </div>
        </section>

        <!-- CANCELLED -->
        <section
          v-else-if="status === 'cancelled'"
          class="status-card status-card--cancelled"
          data-testid="paymentresult-status-cancelled"
        >
          <div class="status-icon status-icon--cancelled">
            <span class="status-icon__emoji" aria-hidden="true">{{ t('payment.icon_cancelled') }}</span>
          </div>
          <h1 class="status-title">{{ t('payment.cancelled_title') }}</h1>
          <p class="status-message">{{ t('payment.cancelled_message') }}</p>
          <div class="action-row">
            <AppButton
              ref="recontinueBtnRef"
              variant="primary"
              size="md"
              :loading="recontinuing"
              data-testid="paymentresult-recontinue"
            >{{ t('payment.cancelled_continue_button') }}</AppButton>
          </div>
        </section>

        <!-- Order summary card (always rendered when payment exists) -->
        <section class="summary-card" data-testid="paymentresult-summary">
          <h2 class="summary-card__title">{{ t('payment.order_id') }}</h2>
          <p class="summary-card__order-id" data-testid="paymentresult-order-id">
            {{ payment.order_id }}
          </p>
          <dl class="info-list">
            <div class="info-list__row">
              <dt>{{ t('payment.amount') }}</dt>
              <dd>{{ formatAmount(payment.amount_cents, payment.currency) }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('payment.method') }}</dt>
              <dd>{{ methodLabel(payment.method) }}</dd>
            </div>
            <div
              v-if="payment.transaction_id"
              class="info-list__row"
            >
              <dt>{{ t('payment.transaction_id') }}</dt>
              <dd class="info-list__mono">{{ payment.transaction_id }}</dd>
            </div>
          </dl>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
import AppHeader from '@/components/AppHeader.vue'
  queryPaymentStatus,
  cancelPayment,
  retryPayment
} from '@/api/payment'

const { t, te } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

// ============== State ==============
const payment = ref(null)
const loading = ref(false)
const loadError = ref('')
const notFound = ref(false)
const retrying = ref(false)
const recontinuing = ref(false)
const countdownSec = ref(30)
const POLLING_INTERVAL_MS = 30000

let pollTimer = null
let countdownTimer = null

const orderId = computed(() => {
  const q = route.query.orderId
  return (typeof q === 'string' ? q : Array.isArray(q) ? q[0] : '') || ''
})

// 4 状态(已规范)
const VALID_STATUSES = ['success', 'failed', 'pending', 'cancelled']
const TERMINAL_STATUSES = ['success', 'failed', 'cancelled']

const status = computed(() => {
  const s = payment.value?.status
  return VALID_STATUSES.includes(s) ? s : 'pending'
})

// ============== Formatters ==============
function formatAmount(cents, currency) {
  if (cents == null) return '—'
  const cur = currency || 'USD'
  const val = (Number(cents) / 100).toFixed(2)
  return `${cur} ${val}`
}

function methodLabel(method) {
  if (!method) return '—'
  const key = `payment.method_${method}`
  return te(key) ? t(key) : method
}

// 失败原因多语种
const reasonText = computed(() => {
  const r = payment.value?.reason || payment.value?.reason_message || 'unknown'
  const key = `payment.failed_reason_${r}`
  if (te(key)) return t(key)
  return t('payment.failed_reason_unknown')
})

// ============== Polling ==============
async function refreshStatus({ showLoading = false } = {}) {
  if (!orderId.value) {
    notFound.value = true
    return
  }
  if (showLoading) loading.value = true
  loadError.value = ''
  try {
    const resp = await queryPaymentStatus(orderId.value)
    const data = resp?.data || resp || null
    if (data) {
      payment.value = data
      notFound.value = false
      // 终态:停止轮询
      if (TERMINAL_STATUSES.includes(data.status)) {
        stopPolling()
      } else {
        countdownSec.value = 30
      }
    } else {
      notFound.value = true
      payment.value = null
      stopPolling()
    }
  } catch (e) {
    if (e?.code === '4004' || e?.status === 404 || /not.?found/i.test(e?.message || '')) {
      notFound.value = true
      payment.value = null
      stopPolling()
    } else {
      loadError.value = e?.message || t('payment.load_failed')
      // 网络错误:fallback UI 已渲染,保持轮询以便自动恢复
    }
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  // 倒计时显示(每 1s)
  countdownTimer = setInterval(() => {
    countdownSec.value = Math.max(0, countdownSec.value - 1)
    if (countdownSec.value === 0) countdownSec.value = POLLING_INTERVAL_MS / 1000
  }, 1000)
  // 主轮询:30s
  pollTimer = setInterval(() => {
    refreshStatus({ showLoading: false })
  }, POLLING_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ============== Actions ==============
async function onCancel() {
  if (!payment.value) return
  try {
    await cancelPayment(payment.value.order_id)
    toast.success(t('common.cancel'))
    // 重新拉一次拿到 cancelled 状态
    await refreshStatus()
  } catch (e) {
    toast.error(e?.message || t('common.cancel'))
  }
}

async function onRetryPay() {
  if (!payment.value) return
  retrying.value = true
  try {
    const resp = await retryPayment(payment.value.order_id)
    payment.value = resp?.data || payment.value
    toast.success(t('payment.retry_button'))
    // 重试后会回 pending,重启轮询
    startPolling()
    await refreshStatus()
  } catch (e) {
    toast.error(e?.message || t('payment.retry_button'))
  } finally {
    retrying.value = false
  }
}

async function onRecontinue() {
  if (!payment.value) return
  recontinuing.value = true
  try {
    const resp = await retryPayment(payment.value.order_id)
    payment.value = resp?.data || payment.value
    toast.success(t('payment.cancelled_continue_button'))
    startPolling()
    await refreshStatus()
  } catch (e) {
    toast.error(e?.message || t('payment.cancelled_continue_button'))
  } finally {
    recontinuing.value = false
  }
}

function goOrderDetail() {
  if (payment.value?.order_id) {
    router.push(`/orders/${encodeURIComponent(payment.value.order_id)}`)
  } else {
    router.push('/orders')
  }
}

function goOrdersList() {
  router.push('/orders')
}

function onRefreshNow() {
  refreshStatus({ showLoading: false })
  countdownSec.value = 30
}

// ============== Refs for AppButton.setOnTrigger pattern ==============
const refreshBtnRef = ref(null)
const cancelBtnRef = ref(null)
const successDetailBtnRef = ref(null)
const retryPayBtnRef = ref(null)
const failedBackBtnRef = ref(null)
const recontinueBtnRef = ref(null)
const retryLoadBtnRef = ref(null)
const nfBackBtnRef = ref(null)

function injectTriggers() {
  if (refreshBtnRef.value) refreshBtnRef.value.setOnTrigger(onRefreshNow)
  if (cancelBtnRef.value) cancelBtnRef.value.setOnTrigger(onCancel)
  if (successDetailBtnRef.value) successDetailBtnRef.value.setOnTrigger(goOrderDetail)
  if (retryPayBtnRef.value) retryPayBtnRef.value.setOnTrigger(onRetryPay)
  if (failedBackBtnRef.value) failedBackBtnRef.value.setOnTrigger(goOrdersList)
  if (recontinueBtnRef.value) recontinueBtnRef.value.setOnTrigger(onRecontinue)
  if (retryLoadBtnRef.value) retryLoadBtnRef.value.setOnTrigger(() => refreshStatus({ showLoading: true }))
  if (nfBackBtnRef.value) nfBackBtnRef.value.setOnTrigger(goOrdersList)
}

// 监听 status 变化(v-if mount/unmount),nextTick 注入 trigger
watch(status, async () => {
  await nextTick()
  injectTriggers()
})

// 监听 notFound/loadError 变化(同样 nextTick 注入)
watch([notFound, loadError], async () => {
  await nextTick()
  injectTriggers()
})

// 路由 query.orderId 变化 → 重新加载
watch(orderId, (v, prev) => {
  if (v && v !== prev) {
    payment.value = null
    notFound.value = false
    loadError.value = ''
    countdownSec.value = 30
    refreshStatus({ showLoading: true })
  }
})

onMounted(async () => {
  auth.hydrate()
  await refreshStatus({ showLoading: true })
  if (status.value === 'pending') {
    startPolling()
  }
  await nextTick()
  injectTriggers()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped lang="scss">
.paymentresult-page { min-height: 100vh; background: var(--bg-alt, #F8FAFC); }

// ============== Header ==============
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; background: #fff; border-bottom: 1px solid var(--border, #E2E8F0);
}
.paymentresult-shell { max-width: 720px; margin: 0 auto; padding: 28px 20px 60px; }

// ============== Status Card (centerpiece) ==============
.status-card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 16px;
  padding: 36px 28px;
  margin-bottom: 22px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
}
.status-card--success   { border-top: 4px solid #16A34A; background: linear-gradient(180deg, #F0FDF4 0%, #fff 60%); }
.status-card--failed    { border-top: 4px solid #DC2626; background: linear-gradient(180deg, #FEF2F2 0%, #fff 60%); }
.status-card--pending   { border-top: 4px solid #D97706; background: linear-gradient(180deg, #FFFBEB 0%, #fff 60%); }
.status-card--cancelled { border-top: 4px solid #64748B; background: linear-gradient(180deg, #F8FAFC 0%, #fff 60%); }

.status-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 72px; height: 72px;
  border-radius: 50%;
  margin-bottom: 14px;
}
.status-icon__emoji { font-size: 40px; font-weight: 700; }
.status-icon--success   { background: #DCFCE7; color: #166534; }
.status-icon--failed    { background: #FEE2E2; color: #991B1B; }
.status-icon--pending   { background: #FEF3C7; color: #92400E; animation: pulse-scale 1.6s ease-in-out infinite; }
.status-icon--cancelled { background: #E2E8F0; color: #475569; }

.status-title {
  margin: 4px 0 10px;
  font-size: 24px; font-weight: 700;
  color: var(--ink-1, #0F172A);
}
.status-message {
  margin: 0 0 10px;
  font-size: 14px; color: var(--ink-2, #334155);
  line-height: 1.6;
}
.status-hint {
  margin: 0 0 18px;
  font-size: 12px; color: var(--ink-3, #64748B);
}
.status-reason {
  margin: 4px auto 18px;
  max-width: 480px;
  padding: 10px 14px;
  background: #FEF2F2; color: #7F1D1D;
  border: 1px solid #FCA5A5; border-radius: 8px;
  font-size: 13px; line-height: 1.5;
}
.status-eta {
  display: inline-block;
  margin: 8px 0 18px;
  padding: 6px 14px;
  background: #DCFCE7; color: #166534;
  border: 1px solid #86EFAC; border-radius: 999px;
  font-size: 12px; font-weight: 500;
}

// ============== Polling animation ==============
.polling-bar {
  display: inline-flex; align-items: center; gap: 6px;
  margin: 6px 0 10px;
}
.polling-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #D97706;
  animation: polling-bounce 1.4s ease-in-out infinite;
}
.polling-dot:nth-child(2) { animation-delay: .2s; }
.polling-dot:nth-child(3) { animation-delay: .4s; }

@keyframes polling-bounce {
  0%, 80%, 100% { transform: scale(0.5); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}
@keyframes pulse-scale {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(217, 119, 6, 0.4); }
  50% { transform: scale(1.05); box-shadow: 0 0 0 12px rgba(217, 119, 6, 0); }
}

.polling-label {
  margin: 0 0 18px;
  font-size: 12px; color: var(--ink-3, #64748B);
  font-variant-numeric: tabular-nums;
}

// ============== Action row ==============
.action-row {
  display: flex; flex-wrap: wrap; gap: 10px;
  justify-content: center;
  margin-top: 4px;
}

// ============== Summary card ==============
.summary-card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px;
  padding: 22px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
}
.summary-card__title {
  margin: 0 0 4px;
  font-size: 11px; font-weight: 600;
  color: var(--ink-3, #64748B);
  letter-spacing: 0.06em; text-transform: uppercase;
}
.summary-card__order-id {
  margin: 0 0 16px;
  font-size: 18px; font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--ink-1, #0F172A);
}

.info-list { margin: 0; padding: 0; }
.info-list__row {
  display: grid; grid-template-columns: 110px 1fr;
  gap: 12px; padding: 9px 0;
  border-bottom: 1px dashed var(--border, #E2E8F0);
  font-size: 14px;
  @media (max-width: 480px) { grid-template-columns: 1fr; gap: 4px; }
}
.info-list__row:last-child { border-bottom: none; }
.info-list__row dt { color: var(--ink-3, #64748B); margin: 0; }
.info-list__row dd { color: var(--ink-1, #0F172A); margin: 0; font-weight: 500; }
.info-list__mono { font-family: ui-monospace, monospace; }

// ============== Generic state blocks ==============
.state-block {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 40px;
  text-align: center; color: var(--ink-3, #64748B); font-size: 14px;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.state-block--err  { color: #DC2626; }
.state-block--warn { color: #92400E; }
.state-block__icon  { margin: 0; font-size: 36px; }
.state-block__title { margin: 4px 0 4px; font-size: 18px; font-weight: 700; color: var(--ink-1, #0F172A); }
.state-block__body  { margin: 0 0 12px; font-size: 13px; color: var(--ink-3, #64748B); }

.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #3B6EF5; border-top-color: transparent;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
