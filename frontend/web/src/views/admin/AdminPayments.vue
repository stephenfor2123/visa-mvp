<!--
  AdminPayments.vue — W34 + refund sub-track

  - 支付状态筛选 + 退款状态筛选
  - 表格含订单状态、退款状态
  - 统计卡片含退款待审/失败
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.payments.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.payments.page_subtitle') }}</p>
      </header>

      <!-- 视图切换 -->
      <section class="admin-filter" role="tablist">
        <button
          class="admin-filter__chip"
          :class="{ 'is-active': viewMode === 'payment' }"
          @click="setViewMode('payment')"
        >
          {{ t('admin.payments.view_payment') }}
        </button>
        <button
          class="admin-filter__chip"
          :class="{ 'is-active': viewMode === 'refund' }"
          @click="setViewMode('refund')"
        >
          {{ t('admin.payments.view_refund') }}
        </button>
      </section>

      <!-- 统计卡片 -->
      <section class="admin-cards">
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_total') }}</div>
          <div class="admin-card__value">{{ fmt(stats.total_count) }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_amount') }}</div>
          <div class="admin-card__value">{{ money(stats.total_amount_cents, stats.currency || 'USD') }}</div>
        </AppCard>
        <AppCard v-if="viewMode === 'payment'" class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_paid') }}</div>
          <div class="admin-card__value">{{ fmt(stats.paid_count) }}</div>
        </AppCard>
        <AppCard v-if="viewMode === 'payment'" class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_pending') }}</div>
          <div class="admin-card__value">{{ fmt(stats.pending_count) }}</div>
        </AppCard>
        <AppCard v-if="viewMode === 'refund'" class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_refund_pending') }}</div>
          <div class="admin-card__value">{{ fmt(stats.refund_pending_count) }}</div>
        </AppCard>
        <AppCard v-if="viewMode === 'refund'" class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_refund_failed') }}</div>
          <div class="admin-card__value">{{ fmt(stats.refund_failed_count) }}</div>
        </AppCard>
      </section>

      <!-- 状态筛选 -->
      <section class="admin-filter" role="tablist">
        <button
          v-for="f in activeFilters"
          :key="f.value || 'all'"
          class="admin-filter__chip"
          :class="{ 'is-active': activeFilter === f.value }"
          @click="setFilter(f.value)"
        >
          {{ t(f.labelKey) }}
        </button>
      </section>

      <!-- 表格 -->
      <AppCard class="admin-panel">
        <template #header>
          <div class="admin-panel__head">
            <h3>{{ activeFilter ? t(activeFilterLabel) : t('admin.payments.filter_all') }}</h3>
            <span class="admin-panel__meta">{{ items.length }} / {{ total }}</span>
          </div>
        </template>

        <div v-if="loading" class="admin-panel__placeholder">{{ t('admin.orders.loading') }}</div>
        <div v-else-if="loadError" class="admin-panel__placeholder admin-panel__placeholder--err">{{ loadError }}</div>
        <div v-else-if="!items.length" class="admin-panel__placeholder">{{ t('admin.payments.empty') }}</div>
        <table v-else class="admin-table">
          <thead>
            <tr>
              <th>{{ t('admin.payments.col_order') }}</th>
              <th>{{ t('admin.payments.col_user') }}</th>
              <th>{{ t('admin.payments.col_trade') }}</th>
              <th>{{ t('admin.payments.col_amount') }}</th>
              <th>{{ t('admin.payments.col_order_status') }}</th>
              <th>{{ t('admin.payments.col_status') }}</th>
              <th v-if="viewMode === 'refund'">{{ t('admin.payments.col_refund_status') }}</th>
              <th>{{ t('admin.payments.col_paid_at') }}</th>
              <th>{{ t('admin.payments.col_action') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in items" :key="p.order_id">
              <td class="admin-table__mono">{{ p.order_no }}</td>
              <td>{{ p.user_name || maskEmail(p.user_email) || `用户 ${p.user_id}` }}</td>
              <td class="admin-table__mono">{{ p.trade_no || '—' }}</td>
              <td>{{ money(p.amount_cents, p.currency) }}</td>
              <td>
                <span class="admin-pill" :class="`admin-pill--${p.order_status || 'created'}`">
                  {{ t(`admin.order_detail.status_${p.order_status || 'created'}`) }}
                </span>
              </td>
              <td>
                <span class="admin-pill" :class="`admin-pill--payment-${p.status}`">
                  {{ t(`admin.order_detail.payment_${p.status}`) }}
                </span>
              </td>
              <td v-if="viewMode === 'refund'">
                <span class="admin-pill" :class="`admin-pill--refund-${p.refund_status || 'none'}`">
                  {{ t(`admin.order_detail.refund_status_${p.refund_status || 'none'}`) }}
                </span>
              </td>
              <td class="admin-table__muted">{{ p.paid_at ? formatTime(p.paid_at) : '—' }}</td>
              <td>
                <router-link :to="`/admin/orders/${p.order_id}`" class="admin-link">
                  {{ t('admin.payments.view_order') }}
                </router-link>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="totalPages > 1" class="admin-pagination">
          <button class="admin-page-btn" :disabled="page <= 1" @click="page--">
            {{ t('admin.payments.prev') }}
          </button>
          <span class="admin-page-info">{{ page }} / {{ totalPages }}</span>
          <button class="admin-page-btn" :disabled="page >= totalPages" @click="page++">
            {{ t('admin.payments.next') }}
          </button>
        </div>
      </AppCard>
    </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'
import { listPayments } from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const paymentFilters = [
  { value: '', labelKey: 'admin.payments.filter_all' },
  { value: 'pending', labelKey: 'admin.payments.filter_pending' },
  { value: 'paid', labelKey: 'admin.payments.filter_paid' },
  { value: 'closed', labelKey: 'admin.payments.filter_closed' },
  { value: 'failed', labelKey: 'admin.payments.filter_failed' },
  { value: 'refunded', labelKey: 'admin.payments.filter_refunded' },
]
const refundFilters = [
  { value: '', labelKey: 'admin.payments.filter_all' },
  { value: 'pending', labelKey: 'admin.payments.filter_refund_pending' },
  { value: 'approved', labelKey: 'admin.payments.filter_refund_approved' },
  { value: 'completed', labelKey: 'admin.payments.filter_refund_completed' },
  { value: 'rejected', labelKey: 'admin.payments.filter_refund_rejected' },
  { value: 'failed', labelKey: 'admin.payments.filter_refund_failed' },
]

const viewMode = ref('payment')
const activeFilter = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const stats = ref({
  total_count: 0, total_amount_cents: 0, paid_count: 0, pending_count: 0,
  refund_pending_count: 0, refund_failed_count: 0,
})
const loading = ref(false)
const loadError = ref('')

const activeFilters = computed(() => viewMode.value === 'refund' ? refundFilters : paymentFilters)
const activeFilterLabel = computed(() => {
  if (!activeFilter.value) return 'admin.payments.filter_all'
  return viewMode.value === 'refund'
    ? `admin.payments.filter_refund_${activeFilter.value}`
    : `admin.payments.filter_${activeFilter.value}`
})
const totalPages = computed(() => Math.ceil(total.value / pageSize))

function setViewMode(mode) {
  viewMode.value = mode
  activeFilter.value = ''
  page.value = 1
  fetchList()
}

function setFilter(v) {
  activeFilter.value = v
  page.value = 1
  fetchList()
}

async function fetchList() {
  loading.value = true
  loadError.value = ''
  try {
    const params = { page: page.value, page_size: pageSize }
    if (viewMode.value === 'payment' && activeFilter.value) {
      params.status = activeFilter.value
    }
    if (viewMode.value === 'refund' && activeFilter.value) {
      params.refund_status = activeFilter.value
    }
    const out = await listPayments(params)
    items.value = out.items
    total.value = out.total
    if (out.stats) {
      stats.value = out.stats
    }
  } catch (err) {
    loadError.value = err?.message || String(err)
    items.value = []
  } finally {
    loading.value = false
  }
}

function formatAmount(cents, currency) {
  if (cents == null) return '—'
  return (Number(cents) / 100).toFixed(2)
}

function fmtAmount(cents) {
  return (Number(cents || 0) / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}
function money(cents, currency = 'USD') {
  if (cents == null) return '—'
  const amount = Number(cents) / 100
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount) }
  catch { return `${currency} ${amount.toFixed(2)}` }
}
function maskEmail(email) {
  if (!email) return ''
  const [name, domain] = String(email).split('@')
  return domain ? `${name.slice(0, 3)}***@${domain}` : email
}

function fmt(n) { return Number(n || 0).toLocaleString() }

function formatTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

watch(page, () => fetchList())

onMounted(() => { admin.hydrate(); fetchList() })
</script>

<style scoped lang="scss">
.admin-main { padding: 28px 32px; min-width: 0; }
.admin-main__head { margin-bottom: 20px; }
.admin-main__head h1 { font-size: 22px; font-weight: 700; color: #0F172A; margin: 0 0 4px; }
.admin-main__sub { font-size: 13px; color: #64748B; margin: 0; }

.admin-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}
.admin-card { padding: 16px 18px; }
.admin-card__label { font-size: 12px; color: #64748B; text-transform: uppercase; letter-spacing: .5px; }
.admin-card__value { font-size: 26px; font-weight: 700; color: #0F172A; margin: 6px 0 4px; }

.admin-filter { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.admin-filter__chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: #fff; color: #475569;
  border: 1px solid #E2E8F0; border-radius: 999px;
  padding: 6px 14px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background .15s, border-color .15s, color .15s;
}
.admin-filter__chip:hover { border-color: #94A3B8; color: #0F172A; }
.admin-filter__chip.is-active { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }

.admin-panel__head { display: flex; justify-content: space-between; align-items: center; }
.admin-panel__meta { font-size: 12px; color: #94A3B8; font-weight: 600; }
.admin-panel__placeholder { padding: 32px 0; text-align: center; color: #94A3B8; font-size: 13px; }
.admin-panel__placeholder--err { color: #DC2626; }

.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th {
  text-align: left; font-weight: 600; color: #475569;
  font-size: 12px; letter-spacing: .03em; text-transform: uppercase;
  padding: 10px 12px; border-bottom: 1px solid #E2E8F0; background: #F8FAFC;
}
.admin-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; color: #0F172A; }
.admin-table tr:hover td { background: #F8FAFC; }
.admin-table__mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }
.admin-table__muted { color: #94A3B8; font-size: 12px; }
.admin-link { color: #3B6EF5; font-weight: 600; text-decoration: none; font-size: 12px; }
.admin-link:hover { text-decoration: underline; }

.admin-pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: .03em;
  background: #F1F5F9; color: #475569;
}
.admin-pill--created, .admin-pill--paid { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--completed { background: #D1FAE5; color: #047857; }
.admin-pill--cancelled { background: #E2E8F0; color: #475569; }
.admin-pill--payment-none { background: #F1F5F9; color: #64748B; }
.admin-pill--payment-pending { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--payment-paid { background: #D1FAE5; color: #047857; }
.admin-pill--payment-closed { background: #E2E8F0; color: #475569; }
.admin-pill--payment-failed { background: #FECACA; color: #991B1B; }
.admin-pill--payment-refunded { background: #E0E7FF; color: #4338CA; }
.admin-pill--refund-none { background: #F1F5F9; color: #64748B; }
.admin-pill--refund-pending { background: #FEF3C7; color: #B45309; }
.admin-pill--refund-approved { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--refund-completed { background: #D1FAE5; color: #047857; }
.admin-pill--refund-rejected { background: #FEE2E2; color: #B91C1C; }
.admin-pill--refund-failed { background: #FECACA; color: #991B1B; }

.admin-pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
.admin-page-btn {
  background: #fff; color: #475569; border: 1px solid #E2E8F0;
  border-radius: 6px; padding: 7px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer;
}
.admin-page-btn:disabled { opacity: .5; cursor: not-allowed; }
.admin-page-info { font-size: 13px; color: #64748B; font-weight: 600; }
</style>
