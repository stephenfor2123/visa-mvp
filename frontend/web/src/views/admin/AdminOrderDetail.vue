<!--
  AdminOrderDetail.vue — W34

  Order detail with full state-machine UI.

  - Basics block: order_no, user, country, status, amounts, timestamps.
  - Applicant block: pretty-printed JSON of applicant_data (surname,
    given_name, passport, travel_window, emergency_contact).
  - Status timeline: server-rendered status_history rows in chronological
    order, showing from→to + source + note + timestamp.
  - Action block: button group for every status in `allowed_next_statuses`.
    The server is the source of truth — clicking sends PUT and reloads,
    so any new transition (or block) is reflected after the response.
  - Confirm dialog before each transition; note textarea (optional) gets
    appended to the OrderStatusHistory row + audit log.
-->
<template>
<div class="admin-order-detail" data-testid="admin-order-detail">

    <main class="admin-main">
      <header class="admin-main__head">
        <router-link to="/admin/orders" class="admin-back" data-testid="admin-order-back">
          {{ t('admin.order_detail.back_to_list') }}
        </router-link>
        <h1>
          {{ t('admin.order_detail.page_title') }}
          <span v-if="order" class="admin-main__sub">· {{ order.order_no }}</span>
        </h1>
      </header>

      <div v-if="loading" class="admin-panel__placeholder">{{ t('admin.orders.loading') }}</div>
      <div v-else-if="loadError" class="admin-panel__placeholder admin-panel__placeholder--err">{{ loadError }}</div>
      <template v-else-if="order">
        <!-- Basics -->
        <AppCard class="admin-panel">
          <template #header>
            <h3>{{ t('admin.order_detail.section_basic') }}</h3>
</template>
          <dl class="admin-dl">
            <dt>{{ t('admin.order_detail.field_order_no') }}</dt>
            <dd class="admin-mono">{{ order.order_no }}</dd>
            <dt>{{ t('admin.order_detail.field_user') }}</dt>
            <dd>#{{ order.user_id }}</dd>
            <dt>{{ t('admin.order_detail.field_country') }}</dt>
            <dd>#{{ order.destination_id }} · {{ order.destination_url || '—' }}</dd>
            <dt>{{ t('admin.order_detail.field_visa_type') }}</dt>
            <dd>{{ t(`admin.order_detail.visa_type_${order.visa_type}`) }}</dd>
            <dt>{{ t('admin.order_detail.field_amount') }}</dt>
            <dd>{{ formatAmount(order.total_amount, order.currency) }}</dd>
            <dt>{{ t('admin.order_detail.field_status') }}</dt>
            <dd>
              <span class="admin-pill" :class="`admin-pill--${order.status}`">
                {{ t(`admin.order_detail.status_${order.status}`) }}
              </span>
            </dd>
            <dt>{{ t('admin.order_detail.field_aff') }}</dt>
            <dd>{{ order.aff_code || t('admin.order_detail.field_no_aff') }}</dd>
            <dt>{{ t('admin.order_detail.field_rpa_task') }}</dt>
            <dd class="admin-mono">{{ order.rpa_task_id || t('admin.order_detail.field_no_rpa') }}</dd>
            <dt>{{ t('admin.order_detail.field_created') }}</dt>
            <dd>{{ formatTime(order.created_at) }}</dd>
            <dt>{{ t('admin.order_detail.field_submitted') }}</dt>
            <dd>{{ formatTime(order.submitted_at) }}</dd>
            <dt>{{ t('admin.order_detail.field_reviewed') }}</dt>
            <dd>{{ formatTime(order.reviewed_at) }}</dd>
            <dt>{{ t('admin.order_detail.field_closed') }}</dt>
            <dd>{{ formatTime(order.closed_at) }}</dd>
          </dl>
        </AppCard>

        <!-- Applicant -->
        <AppCard class="admin-panel" v-if="applicantParsed">
          <template #header>
            <h3>{{ t('admin.order_detail.section_applicant') }}</h3>
          </template>
          <dl class="admin-dl">
            <template v-for="(v, k) in applicantParsed" :key="k">
              <dt>{{ k }}</dt>
              <dd>{{ v }}</dd>
            </template>
          </dl>
        </AppCard>

        <!-- 支付信息（W34: 订单与资金流分开） -->
        <AppCard class="admin-panel">
          <template #header>
            <h3>{{ t('admin.order_detail.section_payment') }}</h3>
          </template>
          <dl class="admin-dl" v-if="order.payment">
            <dt>{{ t('admin.order_detail.payment_trade_no') }}</dt>
            <dd class="admin-mono">{{ order.payment.trade_no || '—' }}</dd>
            <dt>{{ t('admin.order_detail.payment_status') }}</dt>
            <dd>
              <span class="admin-pill" :class="`admin-pill--payment-${order.payment.status}`">
                {{ t(`admin.order_detail.payment_${order.payment.status}`) }}
              </span>
            </dd>
            <dt>{{ t('admin.order_detail.payment_amount') }}</dt>
            <dd>¥{{ formatAmount(order.payment.amount_cents, order.payment.currency) }}</dd>
            <dt>{{ t('admin.order_detail.payment_paid_at') }}</dt>
            <dd>{{ order.payment.paid_at ? formatTime(order.payment.paid_at) : '—' }}</dd>
          </dl>
          <p v-else class="admin-panel__placeholder">{{ t('admin.order_detail.payment_none') }}</p>
        </AppCard>

        <!-- 完整审计日志（W34: 订单流/资金流/日志三栏） -->
        <AppCard class="admin-panel">
          <template #header>
            <h3>{{ t('admin.order_detail.section_audit') }}</h3>
          </template>
          <div v-if="!order.audit_logs?.length" class="admin-panel__placeholder">暂无日志</div>
          <ol v-else class="admin-timeline">
            <li v-for="log in order.audit_logs" :key="log.id" class="admin-timeline__row">
              <span class="admin-timeline__src">{{ formatActor(log) }}</span>
              <span class="admin-timeline__note">{{ formatAction(log) }}</span>
              <span class="admin-timeline__time">{{ formatTime(log.created_at) }}</span>
            </li>
          </ol>
        </AppCard>

        <!-- Status timeline -->
        <AppCard class="admin-panel">
          <template #header>
            <h3>{{ t('admin.order_detail.section_history') }}</h3>
          </template>
          <ol v-if="order.status_history?.length" class="admin-timeline">
            <li v-for="(h, i) in order.status_history" :key="i" class="admin-timeline__row">
              <span class="admin-pill" :class="`admin-pill--${h.to_status}`">
                {{ h.from_status || '∅' }} → {{ h.to_status }}
              </span>
              <span class="admin-timeline__src">{{ h.source }}</span>
              <span class="admin-timeline__note">{{ h.note || '' }}</span>
              <span class="admin-timeline__time">{{ formatTime(h.created_at) }}</span>
            </li>
          </ol>
          <p v-else class="admin-panel__placeholder">—</p>
        </AppCard>

        <!-- Action: state machine -->
        <AppCard class="admin-panel">
          <template #header>
            <h3>{{ t('admin.order_detail.section_action') }}</h3>
          </template>
          <div v-if="!allowed.length" class="admin-panel__placeholder">
            {{ t('admin.order_detail.transition_invalid') }}
          </div>
          <div v-else class="admin-actions">
            <button
              v-for="s in allowed"
              :key="s"
              class="admin-action"
              :class="`admin-action--${s}`"
              :data-testid="`admin-order-action-${s}`"
              @click="openConfirm(s)"
            >
              {{ t(`admin.order_detail.status_${s}`) }}
            </button>
          </div>
          <p v-if="actionMessage" class="admin-actions__msg" :class="actionOk ? 'is-ok' : 'is-err'">
            {{ actionMessage }}
          </p>
        </AppCard>
      </template>
    </main>

    <!-- Confirm modal -->
    <div v-if="confirming" class="admin-modal-mask" @click.self="cancelConfirm">
      <div class="admin-modal" data-testid="admin-order-confirm">
        <p class="admin-modal__title">
          {{ t('admin.order_detail.transition_prompt', {
            from: t(`admin.order_detail.status_${order.status}`),
            to:   t(`admin.order_detail.status_${confirming}`)
          }) }}
        </p>
        <label class="admin-modal__label">{{ t('admin.order_detail.transition_note') }}</label>
        <textarea
          v-model="note"
          class="admin-modal__textarea"
          rows="3"
          data-testid="admin-order-confirm-note"
        />
        <div class="admin-modal__actions">
          <button class="admin-modal__btn" @click="cancelConfirm">取消</button>
          <button
            class="admin-modal__btn admin-modal__btn--primary"
            :disabled="submitting"
            @click="submitTransition"
            data-testid="admin-order-confirm-submit"
          >
            {{ submitting ? '...' : t('admin.order_detail.transition_btn') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'
import { getAdminOrder, updateAdminOrderStatus } from '@/api/admin'

const { t } = useI18n()
const route = useRoute()
const admin = useAdminStore()


const order = ref(null)
const loading = ref(false)
const loadError = ref('')
const confirming = ref('')
const note = ref('')
const submitting = ref(false)
const actionMessage = ref('')
const actionOk = ref(true)

const allowed = computed(() => order.value?.allowed_next_statuses || [])

const applicantParsed = computed(() => {
  if (!order.value?.applicant_data) return null
  try {
    const a = JSON.parse(order.value.applicant_data)
    const ec = a.emergency_contact || {}
    return {
      '姓 / Surname': a.surname || '—',
      '名 / Given name': a.given_name || '—',
      '性别 / Sex': a.sex || '—',
      '出生 / DOB': a.dob || '—',
      '国籍 / Nationality': a.nationality || '—',
      '护照号 / Passport': a.passport_no || '—',
      '护照到期 / Expiry': a.passport_expiry || '—',
      '入境 / Arrival': a.arrival_date || '—',
      '离境 / Departure': a.departure_date || '—',
      '停留 / Stay days': a.stay_days ?? '—',
      '紧急联系人': ec.name || '—',
      '紧急电话': ec.phone || '—',
      '关系': ec.relation || '—',
    }
  } catch {
    return null
  }
})

async function fetchOrder() {
  loading.value = true
  loadError.value = ''
  try {
    order.value = await getAdminOrder(Number(route.params.id))
  } catch (err) {
    loadError.value = err?.message || String(err)
    order.value = null
  } finally {
    loading.value = false
  }
}

function openConfirm(s) {
  confirming.value = s
  note.value = ''
  actionMessage.value = ''
}
function cancelConfirm() {
  confirming.value = ''
  note.value = ''
}

async function submitTransition() {
  if (!confirming.value) return
  submitting.value = true
  actionMessage.value = ''
  try {
    await updateAdminOrderStatus(Number(route.params.id), {
      status: confirming.value,
      note: note.value || undefined,
    })
    actionOk.value = true
    actionMessage.value = t('admin.order_detail.transition_success')
    confirming.value = ''
    await fetchOrder()
  } catch (err) {
    actionOk.value = false
    actionMessage.value = t('admin.order_detail.transition_failed') + ': ' + (err?.message || err)
  } finally {
    submitting.value = false
  }
}

function formatAmount(cents, currency) {
  if (cents == null) return '—'
  const n = Number(cents) / 100
  return n.toFixed(2) + (currency ? ' ' + currency : '')
}
function formatTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function formatActor(log) {
  const map = { admin: '管理员', user: '用户', system: '系统', rpa: 'RPA机器人' }
  return map[log.actor_type] || log.actor_type || '未知'
}

function formatAction(log) {
  // action → 中文描述
  const map = {
    'order.create': '订单创建',
    'order.submit': '订单提交',
    'order.cancel': '订单取消',
    'order.approve': '审核通过',
    'order.reject': '审核拒绝',
    'order.close': '订单关闭',
    'order.abnormal': '订单异常',
    'order.update_status': '状态变更',
    'payment.create': '发起支付',
    'payment.notify': '支付回调',
    'rpa.start': 'RPA 启动',
    'rpa.submit': 'RPA 提交',
    'rpa.done': 'RPA 完成',
    'rpa.failed': 'RPA 失败',
    'admin.login': '管理员登录',
    'admin.order.update_status': '管理员操作状态',
  }
  const label = map[log.action] || log.action || ''
  if (log.payload && typeof log.payload === 'object') {
    const from = log.payload?.from_status
    const to = log.payload?.to_status
    if (from && to) return `${label}：${from} → ${to}`
  }
  return label
}


watch(() => route.params.id, () => { fetchOrder() })

onMounted(() => { admin.hydrate(); fetchOrder() })
</script>

<style scoped lang="scss">
.admin-main { padding: 28px 32px; min-width: 0; }
.admin-main__head { margin-bottom: 20px; }
.admin-main__head h1 { font-size: 22px; font-weight: 700; color: #0F172A; margin: 4px 0 0; }
.admin-main__sub { font-size: 14px; color: #64748B; font-weight: 500; margin-left: 6px; }
.admin-back { font-size: 13px; color: #3B6EF5; text-decoration: none; font-weight: 600; }
.admin-back:hover { text-decoration: underline; }
.admin-panel { margin-bottom: 18px; }
.admin-panel__placeholder { padding: 24px 0; text-align: center; color: #94A3B8; font-size: 13px; }
.admin-panel__placeholder--err { color: #DC2626; }
.admin-panel h3 { margin: 0; font-size: 15px; color: #0F172A; }

.admin-dl { display: grid; grid-template-columns: 200px 1fr; gap: 8px 16px; margin: 0; font-size: 13px; }
.admin-dl dt { color: #94A3B8; font-weight: 600; }
.admin-dl dd { margin: 0; color: #0F172A; }
.admin-mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }

.admin-pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: .03em;
  background: #F1F5F9; color: #475569;
}
.admin-pill--created   { background: #E0E7FF; color: #4338CA; }
.admin-pill--submitted { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--reviewing { background: #FEF3C7; color: #B45309; }
.admin-pill--approved  { background: #D1FAE5; color: #047857; }
.admin-pill--rejected  { background: #FEE2E2; color: #B91C1C; }
.admin-pill--closed    { background: #E2E8F0; color: #475569; }
.admin-pill--abnormal  { background: #FCE7F3; color: #9D174D; }
.admin-pill--failed    { background: #FECACA; color: #991B1B; }
.admin-pill--payment-none    { background: #F1F5F9; color: #64748B; }
.admin-pill--payment-pending { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--payment-paid    { background: #D1FAE5; color: #047857; }
.admin-pill--payment-closed  { background: #E2E8F0; color: #475569; }
.admin-pill--payment-failed  { background: #FECACA; color: #991B1B; }

.admin-timeline { list-style: none; padding: 0; margin: 0; }
.admin-timeline__row {
  display: grid;
  grid-template-columns: 200px 80px 1fr 160px;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #F1F5F9;
  font-size: 13px;
}
.admin-timeline__row:last-child { border-bottom: 0; }
.admin-timeline__src { color: #64748B; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
.admin-timeline__note { color: #475569; }
.admin-timeline__time { color: #94A3B8; font-size: 12px; text-align: right; }

.admin-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.admin-action {
  background: #fff; color: #0F172A;
  border: 1px solid #E2E8F0; border-radius: 8px;
  padding: 9px 18px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background .15s, border-color .15s, color .15s;
}
.admin-action:hover { border-color: #3B6EF5; color: #3B6EF5; }
.admin-action--approved { color: #047857; border-color: #A7F3D0; }
.admin-action--approved:hover { background: #D1FAE5; border-color: #047857; }
.admin-action--rejected { color: #B91C1C; border-color: #FECACA; }
.admin-action--rejected:hover { background: #FEE2E2; border-color: #B91C1C; }
.admin-action--closed { color: #475569; }
.admin-action--abnormal, .admin-action--failed { color: #9D174D; border-color: #FBCFE8; }
.admin-actions__msg { margin-top: 12px; font-size: 13px; }
.admin-actions__msg.is-ok { color: #047857; }
.admin-actions__msg.is-err { color: #B91C1C; }

.admin-modal-mask {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .45);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.admin-modal {
  background: #fff; border-radius: 12px;
  padding: 24px;
  width: 100%; max-width: 440px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, .25);
}
.admin-modal__title { margin: 0 0 14px; font-size: 15px; font-weight: 600; color: #0F172A; }
.admin-modal__label { font-size: 12px; color: #64748B; font-weight: 600; display: block; margin-bottom: 6px; }
.admin-modal__textarea {
  width: 100%; box-sizing: border-box;
  border: 1px solid #E2E8F0; border-radius: 6px;
  padding: 8px 10px; font-size: 13px; font-family: inherit;
  resize: vertical;
}
.admin-modal__textarea:focus { outline: none; border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59, 110, 245, .15); }
.admin-modal__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.admin-modal__btn {
  background: #fff; color: #475569;
  border: 1px solid #E2E8F0; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.admin-modal__btn--primary { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.admin-modal__btn--primary:disabled { opacity: .6; cursor: not-allowed; }
</style>
