<!-- Orders.vue — W2 P2: 重写为"用户视角"状态机
     W28: 卡片 + 状态时间线（保留）
     W2:  user-facing status 替代原始后端 status (4 国 i18n)
     W2:  国家 + 国旗 + 价格
     W2:  rejected 走 ✗ 路径（不跟 approved 混） -->
<template>
  <div class="orders-page">
    <AppHeader scope="orders" />
    <main class="app-container app-page orders-shell">
      <div class="page-header">
        <PageHero :title="t('order_list.title') || 'My Applications'" :subtitle="t('order_list.subtitle')" />
      </div>

      <!-- Loading -->
      <div v-if="loading" class="state-block" data-testid="orders-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('order_list.loading') }}
      </div>

      <!-- Error -->
      <div v-else-if="loadError" class="state-block state-block--err" data-testid="orders-error">
        <!-- W56: 401 → "会话过期"块,跳 /login(顶部 App.vue 也会同时显示提示条) -->
        <template v-if="isAuthExpiredState">
          <p>🔒 {{ t('orderdetail.session_expired_msg') }}</p>
          <AppButton variant="primary" size="md" @click="goRelogin">{{ t('common.relogin') }}</AppButton>
        </template>
        <template v-else>
          <p>❌ {{ loadError }}</p>
          <AppButton variant="outline" size="md" @click="loadOrders">{{ t('order_list.retry') }}</AppButton>
        </template>
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

      <!-- Order Cards -->
      <div v-else class="orders-list" data-testid="orders-list">

        <article
          v-for="order in orders"
          :key="order.order_no"
          class="order-card"
          :data-testid="`order-card-${order.order_no}`"
          :data-status="order.status"
          :data-user-status="userStatusOf(order).key"
        >
          <header class="order-card__head">
            <div class="order-card__left">
              <span class="order-card__flag" aria-hidden="true">{{ flagEmoji(order.country_code) }}</span>
              <div class="order-card__heading">
                <h2 class="order-card__country">{{ order.country_name || order.country_code || '—' }}</h2>
                <p class="order-card__meta">
                  <span class="order-card__visa">{{ visaTypeLabel(order.visa_type) }}</span>
                  <span class="order-card__sep">·</span>
                  <span class="order-card__no">{{ order.order_no }}</span>
                </p>
              </div>
            </div>
            <div class="order-card__right">
              <span
                class="status-badge"
                :class="`status-badge--${userStatusOf(order).tone}`"
                :data-testid="`order-status-${order.order_no}`"
              >
                {{ userStatusOf(order).label }}
              </span>
              <p class="order-card__created">{{ formatDate(order.created_at) }}</p>
            </div>
          </header>

          <!-- Status timeline (user-facing stages) — W67+: 横向 stepper
               5 步并排,圆 + 连线,圆下方放标题+状态徽章+时间。
               配色: 完成=深色实心+绿徽章 / 进行=深蓝边白底+蓝徽章 / 待办=灰边灰字 -->
          <ol class="stepper-horizontal" :data-testid="`order-timeline-${order.order_no}`">
            <li
              v-for="(step, i) in timelineOf(order)"
              :key="step.key"
              class="stepper-h-step"
              :class="{
                'stepper-h-completed': step.state === 'done',
                'stepper-h-active':    step.state === 'current',
                'stepper-h-pending':   step.state === 'pending',
                'stepper-h-failed':    step.state === 'failed'
              }"
            >
              <div class="stepper-h-row">
                <div
                  v-if="i > 0"
                  class="stepper-h-bar stepper-h-bar--left"
                  :class="{ 'is-done': i <= currentStepIndex(order) }"
                ></div>
                <div class="stepper-h-circle" :data-testid="`order-timeline-step-${step.key}`">
                  <svg v-if="step.state === 'done'" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M5 12 L10 17 L20 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <svg v-else-if="step.state === 'failed'" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M6 6 L18 18 M18 6 L6 18" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
                  </svg>
                  <span v-else class="stepper-h-num">{{ i + 1 }}</span>
                </div>
                <div
                  v-if="i < timelineOf(order).length - 1"
                  class="stepper-h-bar stepper-h-bar--right"
                  :class="{ 'is-done': i < currentStepIndex(order) }"
                ></div>
              </div>
              <div class="stepper-h-content">
                <div class="stepper-h-title">{{ step.label }}</div>
                <span
                  v-if="step.state === 'done'"
                  class="stepper-h-pill stepper-h-pill--done"
                  :data-testid="`order-timeline-status-${step.key}`"
                >{{ t('order_list.timeline_status.completed', '已完成') }}</span>
                <span
                  v-else-if="step.state === 'current'"
                  class="stepper-h-pill stepper-h-pill--current"
                  :data-testid="`order-timeline-status-${step.key}`"
                >{{ t('order_list.timeline_status.current', '进行中') }}</span>
                <span
                  v-else-if="step.state === 'failed'"
                  class="stepper-h-pill stepper-h-pill--failed"
                  :data-testid="`order-timeline-status-${step.key}`"
                >{{ t('order_list.timeline_status.failed', '已失败') }}</span>
                <span
                  v-else
                  class="stepper-h-pill stepper-h-pill--pending"
                  :data-testid="`order-timeline-status-${step.key}`"
                >{{ t('order_list.timeline_status.pending', '待处理') }}</span>
                <div v-if="step.state === 'done'" class="stepper-h-time">{{ formatDate(order.created_at) }}</div>
              </div>
            </li>
          </ol>

          <footer class="order-card__foot">
            <div class="order-card__amount">
              <span class="order-card__amount-label">{{ t('order_list.amount_due') || '应付' }}</span>
              <span class="order-card__amount-value">
                {{ formatAmount(order.total_amount, order.currency) }}
              </span>
            </div>
            <div class="order-card__actions">
              <!-- W67: draft-only delete affordance. Subtle ghost link so it
                   doesn't compete with the primary "View details" CTA. -->
              <button
                v-if="order.status === 'created'"
                type="button"
                class="order-card__delete"
                :data-testid="`order-delete-${order.order_no}`"
                @click.stop="onDeleteClick(order)"
              >🗑 {{ t('order_list.action_delete') || '删除草稿' }}</button>
              <router-link
                :to="`/orders/${order.order_no}`"
                class="order-card__view"
                :data-testid="`order-view-${order.order_no}`"
              >
                {{ t('order_list.action_view') || 'View details' }} →
              </router-link>
            </div>
          </footer>
        </article>
      </div>
    </main>

    <!-- W67: delete-draft confirmation modal (list-page variant).
         Same shape as OrderDetail's modal — kept separate so a future
         i18n divergence (e.g. "do you really want to start over?") can
         tweak one without touching the other. -->
    <div v-if="deleteModal" class="modal-mask" @click.self="deleteModal = false" data-testid="orders-delete-modal">
      <div class="modal-box modal-box--danger">
        <h3 class="modal-box__title">{{ t('orderdetail.delete_confirm_title') }}</h3>
        <p class="modal-box__body">{{ t('orderdetail.delete_confirm_body', { n: (deleteTarget?.material_ids?.length ?? 0) }) }}</p>
        <div class="modal-box__actions">
          <AppButton ref="deleteNoRef" variant="ghost" size="md" data-testid="orders-delete-no">
            {{ t('orderdetail.delete_confirm_no') }}
          </AppButton>
          <AppButton ref="deleteYesRef" variant="danger" size="md" :loading="deleting" data-testid="orders-delete-yes">
            🗑 {{ t('orderdetail.delete_confirm_ok') }}
          </AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listOrders, deleteOrder } from '@/api/orders'
import { useOrderUserStatus } from '@/composables/useOrderUserStatus'
import LangSwitch from '@/components/LangSwitch.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()
const { statusOf: userStatusOf, timelineOf } = useOrderUserStatus()

// 横向 stepper 的连线要按"当前激活 step 索引"判断左右线是否 done。
// i < curIdx → 两边的线都 done; i === curIdx → 左 done 右 pending; i > curIdx → 全 pending
function currentStepIndex(order) {
  const tl = timelineOf(order)
  return tl.findIndex((s) => s.state === 'current' || s.state === 'failed')
}

const orders = ref([])
const loading = ref(true)
const loadError = ref('')
// W56: 401 → 页面内「会话过期」错误态,不弹顶部 toast
const isAuthExpiredState = ref(false)

// W67: list-page delete-draft flow. We keep the modal here (rather than
// delegating to OrderDetail) so the user can dismiss with one click from
// the list, never having to enter the detail page just to delete.
const deleteModal = ref(false)
const deleteTarget = ref(null)         // order being deleted
const deleting = ref(false)
// v-if mounted refs for AppButton trigger injection (same root-fix pattern
// as OrderDetail.vue so we don't depend on @click bubbling through
// AppButton internals).
const deleteNoRef = ref(null)
const deleteYesRef = ref(null)

function onLogout() {
  auth.logout()
  try { toast.success(t('toast.logout_success')) } catch (_) {}
  router.push('/home')
}

function goRelogin() {
  router.push({ name: 'Login', query: { redirect: route.fullPath } })
}

// W67: open the delete-draft confirm modal
function onDeleteClick(order) {
  deleteTarget.value = order
  deleteModal.value = true
}

async function doDelete() {
  const target = deleteTarget.value
  if (!target) return
  deleting.value = true
  try {
    const r = await deleteOrder(target.order_no)
    // Optimistic local remove (the order row is gone server-side anyway)
    orders.value = orders.value.filter((o) => o.order_no !== target.order_no)
    deleteModal.value = false
    const count = r?.soft_deleted_materials ?? 0
    if (count > 0) {
      toast.success(t('orderdetail.delete_success_with_materials', { n: count }))
    } else {
      toast.success(t('orderdetail.delete_success'))
    }
  } catch (e) {
    if (e?.code === '4010') {
      toast.error(t('orderdetail.delete_blocked'))
    } else {
      toast.error(e?.message || t('orderdetail.delete_failed'))
    }
  } finally {
    deleting.value = false
    deleteTarget.value = null
  }
}

async function loadOrders() {
  loading.value = true
  loadError.value = ''
  isAuthExpiredState.value = false
  try {
    const data = await listOrders()
    orders.value = data.items || []
  } catch (e) {
    if (e?.isAuthExpired || e?.code === '1005') {
      isAuthExpiredState.value = true
      loadError.value = ''  // 由 isAuthExpiredState 渲染
    } else {
      loadError.value = e.message || t('order_list.load_error')
    }
  } finally {
    loading.value = false
  }
}

function flagEmoji(code) {
  if (!code) return '🌐'
  return code
    .toUpperCase()
    .split('')
    .map((c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
    .join('')
}

function visaTypeLabel(vt) {
  if (!vt) return '—'
  const key = `order_list.visa_type_${vt}`
  return t(key) !== key ? t(key) : vt
}

function formatAmount(amount, currency) {
  if (amount == null) return '—'
  const n = Number(amount)
  if (Number.isNaN(n)) return `${amount} ${currency || ''}`.trim()
  // Use original currency, no FX conversion
  const symbolMap = { USD: '$', GBP: '£', EUR: '€', AUD: 'A$', CNY: '¥' }
  const sym = symbolMap[(currency || '').toUpperCase()] || (currency || '')
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: n % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 })}`
}

function formatDate(iso) {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

// W67: inject AppButton click handlers when the delete modal mounts
watch(deleteModal, async (val) => {
  if (val) {
    await nextTick()
    if (deleteNoRef.value) deleteNoRef.value.setOnTrigger(() => { deleteModal.value = false })
    if (deleteYesRef.value) deleteYesRef.value.setOnTrigger(doDelete)
  }
})

onMounted(loadOrders)
</script>

<style scoped>
.orders-page {
  min-height: 100vh;
  background: #FFFFFF;
}
.orders-shell {
  padding-top: 24px;
  padding-bottom: 48px;
  max-width: 920px;
}
.page-header {
  margin-bottom: 24px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #0F172A;
  margin: 0 0 8px;
  letter-spacing: -.5px;
  line-height: 1.25;
}
.page-sub {
  font-size: 15px;
  color: #64748B;
  margin: 0 0 28px;
  line-height: 1.5;
}

.state-block {
  text-align: center;
  padding: 40px 0;
  color: #6b7280;
  font-size: 14px;
}
.state-block--err {
  color: #b91c1c;
}
.spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 8px;
  vertical-align: -2px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty */
.orders-empty {
  text-align: center;
  padding: 60px 20px;
  background: #fafafa;
  border-radius: 12px;
  border: 1px dashed #e5e7eb;
}
.orders-empty__icon { font-size: 40px; margin: 0 0 12px; }
.orders-empty__title { font-size: 16px; font-weight: 600; margin: 0 0 6px; color: #1a1a2e; }
.orders-empty__desc { font-size: 13px; color: #6b7280; margin: 0 0 18px; }

/* Card list */
.orders-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.order-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px 20px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.order-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.order-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.order-card__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.order-card__flag {
  font-size: 26px;
  line-height: 1;
  flex-shrink: 0;
}
.order-card__heading { min-width: 0; }
.order-card__country {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 2px;
  line-height: 1.3;
}
.order-card__meta {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
  line-height: 1.4;
}
.order-card__sep { margin: 0 6px; opacity: 0.6; }
.order-card__no { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }

.order-card__right {
  text-align: right;
  flex-shrink: 0;
}

/* Status badge — colors driven by tone */
.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1.5;
}
.status-badge--muted      { background: #f3f4f6; color: #4b5563; }
.status-badge--warning    { background: #fef3c7; color: #b45309; }
.status-badge--info       { background: #dbeafe; color: #1d4ed8; }
.status-badge--processing { background: #ede9fe; color: #6d28d9; }
.status-badge--success    { background: #d1fae5; color: #047857; }
.status-badge--danger     { background: #fee2e2; color: #b91c1c; }

.order-card__created {
  font-size: 11px;
  color: #9ca3af;
  margin: 4px 0 0;
}

/* Timeline — W67+: 横向 stepper (5 步并排,圆 + 连线,圆下方标题+徽章+时间) */
.stepper-horizontal {
  list-style: none;
  margin: 0 0 14px;
  padding: 0;
  display: flex;
  align-items: flex-start;
  width: 100%;
}
.stepper-h-step {
  flex: 1;
  min-width: 0;
  text-align: center;
  position: relative;
}
.stepper-h-row {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
  position: relative;
}
.stepper-h-bar {
  flex: 1;
  height: 2px;
  background: #e2e8f0;
  align-self: center;
  /* 圆要压在 bar 上:bar 从圆心到圆心。圆 32px,边 2px → bar 端点退到圆外边 */
}
.stepper-h-bar--left  { margin-right: -16px; }
.stepper-h-bar--right { margin-left:  -16px; }
.stepper-h-bar.is-done { background: #1e3a8a; }   /* 深蓝,跟 done 圆统一 */
.stepper-h-circle {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: #fff;
  border: 2px solid #e2e8f0;
  color: #94a3b8;
  font-size: 13px; font-weight: 600;
  position: relative; z-index: 1;
  flex-shrink: 0;
}
.stepper-h-completed .stepper-h-circle {
  background: #1e3a8a; color: #fff; border-color: #1e3a8a;
}
.stepper-h-active .stepper-h-circle {
  background: #fff; color: #1e3a8a; border-color: #1e3a8a;
  box-shadow: 0 0 0 4px rgba(30, 58, 138, .12);
}
.stepper-h-pending .stepper-h-circle {
  background: #fff; color: #94a3b8; border-color: #e2e8f0;
}
.stepper-h-failed .stepper-h-circle {
  background: #fff; color: #dc2626; border-color: #dc2626;
}
.stepper-h-content {
  padding: 0 4px;
}
.stepper-h-title {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
  line-height: 1.3;
  margin-bottom: 6px;
}
.stepper-h-completed .stepper-h-title { color: #0f172a; font-weight: 600; }
.stepper-h-active    .stepper-h-title { color: #0f172a; font-weight: 600; }
.stepper-h-failed    .stepper-h-title { color: #dc2626; font-weight: 600; }
.stepper-h-pill {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 999px;
  line-height: 1.4;
}
.stepper-h-pill--done    { background: #dcfce7; color: #166534; }
.stepper-h-pill--current { background: #dbeafe; color: #1d4ed8; }
.stepper-h-pill--pending { background: #f1f5f9; color: #64748b; }
.stepper-h-pill--failed  { background: #fee2e2; color: #b91c1c; }
.stepper-h-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.3;
}

/* Foot */
.order-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px dashed #f1f5f9;
}
.order-card__amount {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.order-card__amount-label {
  font-size: 11px;
  color: #6b7280;
}
.order-card__amount-value {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.order-card__view {
  font-size: 13px;
  color: #2563eb;
  text-decoration: none;
  font-weight: 500;
}
.order-card__view:hover {
  text-decoration: underline;
}

/* W67: actions cluster on the right side of the card footer */
.order-card__actions {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}

/* W67: subtle ghost-style "delete draft" link next to the primary CTA.
   Lighter weight + smaller font so it doesn't visually compete with
   "View details". The trash icon is the visual cue for destructive. */
.order-card__delete {
  background: transparent;
  border: 0;
  padding: 0;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
  font-weight: 500;
  font-family: inherit;
  transition: color 0.15s;
}
.order-card__delete:hover {
  color: #dc2626;
  text-decoration: underline;
}

/* W67: shared modal styling (kept local to Orders.vue so it can diverge
   from OrderDetail.vue's modal without coupling) */
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
}
.modal-box__title { margin: 0 0 8px; font-size: 17px; font-weight: 700; color: #0F172A; }
.modal-box__body  { margin: 0 0 18px; font-size: 14px; color: #475569; line-height: 1.55; }
.modal-box__actions { display: flex; justify-content: flex-end; gap: 8px; }
.modal-box--danger {
  border-top: 3px solid #DC2626;
}
.modal-box--danger .modal-box__title {
  color: #991B1B;
}

/* Responsive */
@media (max-width: 640px) {
  .order-card { padding: 14px 16px; }
  .order-card__head { flex-wrap: wrap; }
  .order-card__right { width: 100%; text-align: left; display: flex; align-items: center; gap: 8px; }
  .order-card__created { margin: 0; }
  /* W67+: 横向 stepper 在小屏字号缩小,5 步塞得下 */
  .stepper-h-title  { font-size: 10px; }
  .stepper-h-pill   { font-size: 10px; padding: 1px 6px; }
  .stepper-h-circle { width: 24px; height: 24px; font-size: 11px; }
  .stepper-h-bar--left  { margin-right: -12px; }
  .stepper-h-bar--right { margin-left:  -12px; }
}
</style>
