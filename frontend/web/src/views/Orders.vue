<!-- Orders.vue — W12 Story 1.2.3: Order List Page
     W28 P2 #11: 重写为卡片 + 状态时间线 + ETA 显示(借鉴 atlys My Applications) -->
<template>
  <div class="orders-page">
    <AppHeader scope="orders" />
    <main class="app-container app-page orders-shell">
      <div class="page-header">
        <h1 class="page-title">{{ t('order_list.title') || 'My Applications' }}</h1>
        <p class="page-sub">{{ t('order_list.subtitle') }}</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="state-block" data-testid="orders-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('order_list.loading') }}
      </div>

      <!-- Error -->
      <div v-else-if="loadError" class="state-block state-block--err" data-testid="orders-error">
        <p>❌ {{ loadError }}</p>
        <AppButton variant="outline" size="md" @click="loadOrders">{{ t('order_list.retry') }}</AppButton>
      </div>

      <!-- Empty -->
      <div v-else-if="orders.length === 0" class="orders-empty" data-testid="orders-empty">
        <p class="orders-empty__icon">📋</p>
        <p class="orders-empty__title">{{ t('order_list.empty') }}</p>
        <p class="orders-empty__desc">{{ t('order_list.empty_desc') }}</p>
        <AppButton variant="primary" size="lg" @click="$router.push('/home')">
          {{ t('order_list.go_destinations') }}
        </AppButton>
      </div>

      <!-- Order Cards (W28: card layout + status timeline) -->
      <div v-else class="orders-list" data-testid="orders-list">
        <article
          v-for="order in orders"
          :key="order.order_no"
          class="order-card"
          :data-testid="`order-card-${order.order_no}`"
          :data-status="order.status"
        >
          <!-- 卡片头:国旗 + 国家 + 签种 + status badge -->
          <header class="order-card__head">
            <div class="order-card__left">
              <span class="order-card__flag">{{ flagEmoji(order.country_code) }}</span>
              <div class="order-card__heading">
                <h2 class="order-card__country">{{ order.country_name }}</h2>
                <p class="order-card__meta">
                  <span class="order-card__visa">{{ order.visa_type || '—' }}</span>
                  <span class="order-card__sep">·</span>
                  <span class="order-card__no">{{ order.order_no }}</span>
                </p>
              </div>
            </div>
            <div class="order-card__right">
              <span class="status-badge" :class="`status-badge--${order.status}`" :data-testid="`order-status-${order.order_no}`">
                {{ statusLabel(order.status) }}
              </span>
              <p class="order-card__created">{{ formatDate(order.created_at) }}</p>
            </div>
          </header>

          <!-- W28: 状态时间线 -->
          <ol class="status-timeline" :data-testid="`order-timeline-${order.order_no}`">
            <li
              v-for="(step, i) in getTimelineSteps(order)"
              :key="step.key"
              class="status-timeline__step"
              :class="{
                'is-done': step.state === 'done',
                'is-current': step.state === 'current',
                'is-failed': step.state === 'failed',
                'is-pending': step.state === 'pending'
              }"
            >
              <span class="status-timeline__node">
                <svg v-if="step.state === 'done'" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M5 12 L10 17 L20 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else-if="step.state === 'failed'" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M6 6 L18 18 M18 6 L6 18" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
                </svg>
                <span v-else class="status-timeline__dot"></span>
              </span>
              <span class="status-timeline__label">{{ step.label }}</span>
              <span v-if="i < getTimelineSteps(order).length - 1" class="status-timeline__bar"></span>
            </li>
          </ol>

          <!-- 卡片底部:ETA + 操作 -->
          <footer class="order-card__foot">
            <div class="order-card__eta">
              <span v-if="order.eta_label" class="order-card__eta-pill">
                <span aria-hidden="true">⏱</span>
                {{ t('order_list.eta') || 'ETA' }}: <b>{{ order.eta_label }}</b>
              </span>
              <span v-else-if="order.processed_at" class="order-card__eta-pill order-card__eta-pill--done">
                <span aria-hidden="true">✓</span>
                {{ t('order_list.completed_at') || 'Completed' }}: {{ formatDate(order.processed_at) }}
              </span>
            </div>
            <router-link
              :to="`/orders/${order.order_no}`"
              class="order-card__view"
              :data-testid="`order-view-${order.order_no}`"
            >
              {{ t('order_list.action_view') || 'View details' }} →
            </router-link>
          </footer>
        </article>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listOrders } from '@/api/orders'
import LangSwitch from '@/components/LangSwitch.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()
const orders = ref([])
const loading = ref(true)
const loadError = ref('')

function onLogout() {
  auth.logout()
  try { toast.success(t('toast.logout_success')) } catch (_) {}
  router.push('/home')
}

async function loadOrders() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await listOrders()
    orders.value = data.items || []
  } catch (e) {
    loadError.value = e.message || t('order_list.load_error')
  } finally {
    loading.value = false
  }
}

function flagEmoji(code) {
  if (!code) return ''
  return code
    .toUpperCase()
    .split('')
    .map((c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
    .join('')
}

function statusLabel(status) {
  const map = {
    created: t('order_list.status_created'),
    submitted: t('order_list.status_submitted'),
    reviewing: t('order_list.status_reviewing'),
    approved: t('order_list.status_approved'),
    rejected: t('order_list.status_rejected'),
    cancelled: t('order_list.status_cancelled')
  }
  return map[status] || status || '—'
}

function formatDate(iso) {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

// W28 P2 #11: 状态时间线 — 把 5 态规范映射为 5 步视觉进度
const FLOW_STEPS = [
  { key: 'created',   label: t('order_list.status_created')   || 'Created' },
  { key: 'submitted', label: t('order_list.status_submitted') || 'Submitted' },
  { key: 'reviewing', label: t('order_list.status_reviewing') || 'Reviewing' },
  { key: 'approved',  label: t('order_list.status_approved')  || 'Approved' },
  { key: 'rejected',  label: t('order_list.status_rejected')  || 'Rejected' },
]

const STATUS_INDEX = {
  created:   0,
  submitted: 1,
  reviewing: 2,
  approved:  3,
  rejected:  3,
  cancelled: 1,   // created→submitted 之后取消
  closed:    3,
  failed:    2,
  abnormal:  2,
}

function getTimelineSteps(order) {
  const cur = (order.status || 'created').toLowerCase()
  const curIdx = STATUS_INDEX[cur] ?? 0
  const isRejected = cur === 'rejected' || cur === 'failed'
  const isCancelled = cur === 'cancelled'
  const isDone = cur === 'approved' || cur === 'closed'
  // 取消 / 失败时:submitted 之后被中断,用 X 标记当前步
  return FLOW_STEPS.map((step, i) => {
    let state = 'pending'
    if (i < curIdx) state = 'done'
    else if (i === curIdx) {
      if (isRejected && (step.key === 'approved' || step.key === 'rejected')) {
        state = step.key === 'rejected' ? 'failed' : 'pending'
      } else if (isCancelled && i > 1) {
        state = 'pending'
      } else if (isDone && i > 3) {
        state = 'pending'
      } else {
        state = 'current'
      }
    }
    return { ...step, state }
  })
}

onMounted(loadOrders)
</script>

<style scoped>
.orders-page {
  min-height: 100vh;
  background: var(--bg-page, #f5f7fa);
}
.orders-shell {
  padding-top: 24px;
  padding-bottom: 48px;
}
.page-header {
  margin-bottom: 24px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 6px;
}
.page-sub {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}
.state-block {
  text-align: center;
  padding: 48px 0;
  color: #6b7280;
}
.state-block--err {
  color: #ef4444;
}
.orders-empty {
  text-align: center;
  padding: 64px 0;
}
.orders-empty__icon {
  font-size: 48px;
  margin: 0 0 16px;
}
.orders-empty__title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 8px;
}
.orders-empty__desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 24px;
}
/* W28 P2 #11: 订单卡片 + 状态时间线(借鉴 atlys My Applications) */
.orders-list {
  display: grid;
  gap: 14px;
}
.order-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 16px;
  padding: 18px 22px 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .04);
  transition: box-shadow .2s ease, transform .2s ease;
}
.order-card:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, .08);
}
.order-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.order-card__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.order-card__flag {
  font-size: 32px;
  line-height: 1;
  flex-shrink: 0;
}
.order-card__heading {
  min-width: 0;
}
.order-card__country {
  margin: 0 0 2px;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}
.order-card__meta {
  margin: 0;
  font-size: 12.5px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
}
.order-card__visa {
  text-transform: capitalize;
  color: #475569;
  font-weight: 500;
}
.order-card__sep { opacity: .5; }
.order-card__no {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 11.5px;
  color: #94a3b8;
}
.order-card__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}
.order-card__created {
  margin: 0;
  font-size: 11.5px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, monospace;
}

/* 状态时间线 */
.status-timeline {
  list-style: none;
  margin: 0 0 16px;
  padding: 4px 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 4px;
  position: relative;
}
.status-timeline__step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  text-align: center;
  min-width: 0;
}
.status-timeline__node {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1.5px #e2e8f0;
  margin-bottom: 6px;
  transition: all .25s ease;
  position: relative;
  z-index: 2;
}
.status-timeline__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
}
.status-timeline__step.is-done .status-timeline__node {
  background: #10b981;
  color: #fff;
  box-shadow: 0 0 0 1.5px #10b981, 0 2px 8px rgba(16, 185, 129, .3);
}
.status-timeline__step.is-current .status-timeline__node {
  background: var(--color-primary, #3b6ef5);
  color: #fff;
  box-shadow: 0 0 0 1.5px var(--color-primary, #3b6ef5), 0 0 0 6px rgba(59, 110, 245, .15);
  animation: pulseRing 2s ease-in-out infinite;
}
@keyframes pulseRing {
  0%, 100% { box-shadow: 0 0 0 1.5px var(--color-primary, #3b6ef5), 0 0 0 6px rgba(59, 110, 245, .15); }
  50%      { box-shadow: 0 0 0 1.5px var(--color-primary, #3b6ef5), 0 0 0 10px rgba(59, 110, 245, 0); }
}
.status-timeline__step.is-failed .status-timeline__node {
  background: #ef4444;
  color: #fff;
  box-shadow: 0 0 0 1.5px #ef4444, 0 2px 8px rgba(239, 68, 68, .3);
}
.status-timeline__label {
  font-size: 11.5px;
  font-weight: 600;
  color: #94a3b8;
  line-height: 1.2;
  white-space: nowrap;
}
.status-timeline__step.is-done .status-timeline__label { color: #065f46; }
.status-timeline__step.is-current .status-timeline__label { color: var(--color-primary, #3b6ef5); font-weight: 700; }
.status-timeline__step.is-failed .status-timeline__label { color: #991b1b; }
.status-timeline__bar {
  position: absolute;
  top: 14px;
  left: calc(50% + 14px);
  right: calc(-50% + 14px);
  height: 2px;
  background: #e2e8f0;
  z-index: 1;
}
.status-timeline__step.is-done .status-timeline__bar { background: #10b981; }

/* 卡片底部 */
.order-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}
.order-card__eta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.order-card__eta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(59, 110, 245, .08);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
}
.order-card__eta-pill b { font-weight: 700; }
.order-card__eta-pill--done {
  background: rgba(16, 185, 129, .1);
  color: #065f46;
}
.order-card__view {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary, #3b6ef5);
  text-decoration: none;
  white-space: nowrap;
  transition: gap .15s ease;
}
.order-card__view:hover { text-decoration: underline; }

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.status-badge--created { background: #f3f4f6; color: #6b7280; }
.status-badge--submitted { background: #dbeafe; color: #1d4ed8; }
.status-badge--reviewing { background: #fef3c7; color: #b45309; }
.status-badge--approved { background: #d1fae5; color: #065f46; }
.status-badge--rejected { background: #fee2e2; color: #991b1b; }
.status-badge--cancelled { background: #f3f4f6; color: #9ca3af; }
.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: var(--color-primary, #3b6ef5);
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 600px) {
  .order-card { padding: 14px 16px; }
  .order-card__head { flex-direction: column; align-items: flex-start; gap: 8px; }
  .order-card__right { flex-direction: row; align-items: center; gap: 12px; }
  .status-timeline__label { font-size: 10px; }
  .order-card__foot { flex-direction: column; align-items: stretch; gap: 10px; }
  .order-card__view { text-align: center; padding: 8px; background: rgba(59, 110, 245, .06); border-radius: 8px; }
}
</style>