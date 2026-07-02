<!--
  AdminPayments.vue — W34

  资金流管理页面，独立于订单状态机。
  - 顶部统计卡片：总笔数、总金额、已支付、待支付
  - 状态筛选 tabs: 全部 / 待支付 / 已支付 / 已关闭 / 支付失败
  - 表格：订单号、用户、流水号、金额、状态、支付时间、创建时间
  - 分页
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.payments.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.payments.page_subtitle') }}</p>
      </header>

      <!-- 统计卡片 -->
      <section class="admin-cards">
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_total') }}</div>
          <div class="admin-card__value">{{ fmt(stats.total_count) }}</div>
          <div class="admin-card__delta">{{ t('admin.payments.stat_total_hint') }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_amount') }}</div>
          <div class="admin-card__value">¥{{ fmtAmount(stats.total_amount_cents) }}</div>
          <div class="admin-card__delta">{{ t('admin.payments.stat_amount_hint') }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_paid') }}</div>
          <div class="admin-card__value">{{ fmt(stats.paid_count) }}</div>
          <div class="admin-card__delta">{{ t('admin.payments.stat_paid_hint') }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.payments.stat_pending') }}</div>
          <div class="admin-card__value">{{ fmt(stats.pending_count) }}</div>
          <div class="admin-card__delta">{{ t('admin.payments.stat_pending_hint') }}</div>
        </AppCard>
      </section>

      <!-- 状态筛选 -->
      <section class="admin-filter" role="tablist">
        <button
          v-for="f in filters"
          :key="f.value || 'all'"
          class="admin-filter__chip"
          :class="{ 'is-active': activeFilter === f.value }"
          @click="setFilter(f.value)"
        >
          {{ t(f.labelKey) }}
          <span v-if="counts[f.value] != null" class="admin-filter__count">{{ counts[f.value] }}</span>
        </button>
      </section>

      <!-- 表格 -->
      <AppCard class="admin-panel">
        <template #header>
          <div class="admin-panel__head">
            <h3>{{ activeFilter ? t(`admin.payments.filter_${activeFilter}`) : t('admin.payments.filter_all') }}</h3>
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
              <th>{{ t('admin.payments.col_status') }}</th>
              <th>{{ t('admin.payments.col_paid_at') }}</th>
              <th>{{ t('admin.payments.col_created') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in items" :key="p.order_id">
              <td class="admin-table__mono">{{ p.order_no }}</td>
              <td>#{{ p.user_id }}</td>
              <td class="admin-table__mono">{{ p.trade_no || '—' }}</td>
              <td>¥{{ formatAmount(p.amount_cents, p.currency) }}</td>
              <td>
                <span class="admin-pill" :class="`admin-pill--payment-${p.status}`">
                  {{ t(`admin.order_detail.payment_${p.status}`) }}
                </span>
              </td>
              <td class="admin-table__muted">{{ p.paid_at ? formatTime(p.paid_at) : '—' }}</td>
              <td class="admin-table__muted">{{ formatTime(p.created_at) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
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

const filters = [
  { value: '', labelKey: 'admin.payments.filter_all' },
  { value: 'pending', labelKey: 'admin.payments.filter_pending' },
  { value: 'paid', labelKey: 'admin.payments.filter_paid' },
  { value: 'closed', labelKey: 'admin.payments.filter_closed' },
  { value: 'failed', labelKey: 'admin.payments.filter_failed' },
  { value: 'none', labelKey: 'admin.payments.filter_none' },
]

const activeFilter = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const counts = ref({})
const stats = ref({ total_count: 0, total_amount_cents: 0, paid_count: 0, pending_count: 0 })
const loading = ref(false)
const loadError = ref('')

const totalPages = computed(() => Math.ceil(total.value / pageSize))

function setFilter(v) {
  activeFilter.value = v
  page.value = 1
  fetchList()
}

async function fetchList() {
  loading.value = true
  loadError.value = ''
  try {
    const out = await listPayments({
      status: activeFilter.value || null,
      page: page.value,
      page_size: pageSize,
    })
    items.value = out.items
    total.value = out.total
    if (!activeFilter.value) {
      // 汇总统计（无筛选时一次性算好）
      let totalAmt = 0, paidCnt = 0, pendingCnt = 0
      const tally = {}
      for (const p of out.items) {
        totalAmt += p.amount_cents
        if (p.status === 'paid') paidCnt++
        if (p.status === 'pending') pendingCnt++
        tally[p.status] = (tally[p.status] || 0) + 1
      }
      counts.value = tally
      stats.value = {
        total_count: out.total,
        total_amount_cents: totalAmt,
        paid_count: paidCnt,
        pending_count: pendingCnt,
      }
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
  const n = Number(cents) / 100
  return n.toFixed(2)
}

function fmtAmount(cents) {
  return (Number(cents || 0) / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

function fmt(n) { return Number(n || 0).toLocaleString() }

function formatTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function onLogout() {
  admin.logout()
  // 动态导入避免循环
  import('vue-router').then(({ useRouter }) => {
    const router = useRouter()
    router.replace('/admin/login')
  })
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
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}
.admin-card { padding: 16px 18px; }
.admin-card__label { font-size: 12px; color: #64748B; text-transform: uppercase; letter-spacing: .5px; }
.admin-card__value { font-size: 26px; font-weight: 700; color: #0F172A; margin: 6px 0 4px; }
.admin-card__delta { font-size: 12px; color: #16A34A; }

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
.admin-filter__count { font-size: 11px; font-weight: 700; background: rgba(255,255,255,.25); padding: 1px 6px; border-radius: 8px; }
.admin-filter__chip:not(.is-active) .admin-filter__count { background: #F1F5F9; color: #64748B; }

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

.admin-pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: .03em;
  background: #F1F5F9; color: #475569;
}
.admin-pill--payment-none    { background: #F1F5F9; color: #64748B; }
.admin-pill--payment-pending { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--payment-paid    { background: #D1FAE5; color: #047857; }
.admin-pill--payment-closed  { background: #E2E8F0; color: #475569; }
.admin-pill--payment-failed  { background: #FECACA; color: #991B1B; }

.admin-pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
.admin-page-btn {
  background: #fff; color: #475569; border: 1px solid #E2E8F0;
  border-radius: 6px; padding: 7px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background .15s;
}
.admin-page-btn:hover { background: #F8FAFC; }
.admin-page-btn:disabled { opacity: .5; cursor: not-allowed; }
.admin-page-info { font-size: 13px; color: #64748B; font-weight: 600; }
</style>