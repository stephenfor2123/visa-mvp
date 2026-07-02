<!--
  AdminOrders.vue — W34

  Order management list page. Mirrors the sidebar/header pattern from
  AdminDashboard.vue, but the main column is a filterable order table.

  - 9 status filter chips (all + 8 states) — clicking one re-fetches the
    list scoped to that status. URL query param reflects the active filter
    so the back button preserves state.
  - Table columns: order #, user, country (dest id), amount, status pill,
    created, action (view).
  - State pills use a small colour map so reviewers can scan the queue
    at a glance (reviewing = amber, approved = green, rejected = red, etc.).
  - Click "View" → /admin/orders/:id.
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.orders.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.orders.page_subtitle') }}</p>
      </header>

      <!-- Status filter chips -->
      <section class="admin-filter" role="tablist" aria-label="status filter">
        <button
          v-for="f in filters"
          :key="f.value || 'all'"
          class="admin-filter__chip"
          :class="{ 'is-active': activeFilter === f.value }"
          @click="setFilter(f.value)"
          :data-testid="`admin-orders-filter-${f.value || 'all'}`"
        >
          {{ t(f.labelKey) }}
          <span v-if="counts[f.value] != null" class="admin-filter__count">{{ counts[f.value] }}</span>
        </button>
      </section>

      <AppCard class="admin-panel">
        <template #header>
          <div class="admin-panel__head">
            <h3>{{ activeFilter ? t(`admin.orders.filter_${activeFilter}`) : t('admin.orders.filter_all') }}</h3>
            <span class="admin-panel__meta">{{ items.length }} / {{ total }}</span>
          </div>
        </template>

        <div v-if="loading" class="admin-panel__placeholder">{{ t('admin.orders.loading') }}</div>
        <div v-else-if="loadError" class="admin-panel__placeholder admin-panel__placeholder--err">{{ t('admin.orders.load_error') }}: {{ loadError }}</div>
        <div v-else-if="!items.length" class="admin-panel__placeholder">{{ t('admin.orders.empty') }}</div>
        <table v-else class="admin-table">
          <thead>
            <tr>
              <th>{{ t('admin.orders.col_order') }}</th>
              <th>{{ t('admin.orders.col_user') }}</th>
              <th>{{ t('admin.orders.col_country') }}</th>
              <th>{{ t('admin.orders.col_amount') }}</th>
              <th>{{ t('admin.orders.col_status') }}</th>
              <th>{{ t('admin.orders.col_created') }}</th>
              <th>{{ t('admin.orders.col_action') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in items" :key="o.id" :data-testid="`admin-order-row-${o.id}`">
              <td class="admin-table__mono">{{ o.order_no }}</td>
              <td>#{{ o.user_id }}</td>
              <td>#{{ o.destination_id }} · {{ o.visa_type }}</td>
              <td>¥{{ formatAmount(o.total_amount, o.currency) }}</td>
              <td>
                <span class="admin-pill" :class="`admin-pill--${o.status}`">
                  {{ t(`admin.order_detail.status_${o.status}`) }}
                </span>
              </td>
              <td class="admin-table__muted">{{ formatTime(o.created_at) }}</td>
              <td>
                <router-link
                  :to="`/admin/orders/${o.id}`"
                  class="admin-link"
                  :data-testid="`admin-order-view-${o.id}`"
                >
                  {{ t('admin.orders.view_detail') }} →
                </router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </AppCard>
    </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'
import { listAdminOrders } from '@/api/admin'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const admin = useAdminStore()

const filters = [
  { value: '', labelKey: 'admin.orders.filter_all' },
  { value: 'created', labelKey: 'admin.orders.filter_created' },
  { value: 'submitted', labelKey: 'admin.orders.filter_submitted' },
  { value: 'reviewing', labelKey: 'admin.orders.filter_reviewing' },
  { value: 'approved', labelKey: 'admin.orders.filter_approved' },
  { value: 'rejected', labelKey: 'admin.orders.filter_rejected' },
  { value: 'closed', labelKey: 'admin.orders.filter_closed' },
  { value: 'abnormal', labelKey: 'admin.orders.filter_abnormal' },
  { value: 'failed', labelKey: 'admin.orders.filter_failed' },
]

const activeFilter = ref('')
const items = ref([])
const total = ref(0)
const counts = ref({})
const loading = ref(false)
const loadError = ref('')

function setFilter(v) {
  activeFilter.value = v
  router.replace({ query: { ...route.query, status: v || undefined } })
  fetchList()
}

async function fetchList() {
  loading.value = true
  loadError.value = ''
  try {
    const out = await listAdminOrders({ status: activeFilter.value || null, page: 1, page_size: 50 })
    items.value = out.items
    total.value = out.total
    // Count chips by status across the unfiltered result
    if (!activeFilter.value) {
      const tally = {}
      for (const o of out.items) tally[o.status] = (tally[o.status] || 0) + 1
      counts.value = tally
    }
  } catch (err) {
    loadError.value = err?.message || String(err)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchCounts() {
  // Pull all (no filter) once at mount so each chip can show a tally.
  try {
    const out = await listAdminOrders({ page: 1, page_size: 100 })
    const tally = {}
    for (const o of out.items) tally[o.status] = (tally[o.status] || 0) + 1
    counts.value = tally
  } catch {
    /* counts are decorative; don't break the page if this fails */
  }
}

function formatAmount(cents, currency) {
  if (cents == null) return '—'
  const n = Number(cents) / 100
  return n.toFixed(2) + (currency ? ' ' + currency : '')
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}


watch(() => route.query.status, (s) => {
  if ((s || '') !== activeFilter.value) {
    activeFilter.value = s || ''
    fetchList()
  }
})

onMounted(async () => {
  activeFilter.value = (route.query.status || '').toString()
  await Promise.all([fetchList(), fetchCounts()])
})
</script>

<style scoped lang="scss">
.admin-main { padding: 28px 32px; min-width: 0; }
.admin-main__head { margin-bottom: 20px; }
.admin-main__head h1 { font-size: 22px; font-weight: 700; color: #0F172A; margin: 0 0 4px; }
.admin-main__sub { font-size: 13px; color: #64748B; margin: 0; }

.admin-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}
.admin-filter__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  color: #475569;
  border: 1px solid #E2E8F0;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
}
.admin-filter__chip:hover { border-color: #94A3B8; color: #0F172A; }
.admin-filter__chip.is-active {
  background: #3B6EF5;
  color: #fff;
  border-color: #3B6EF5;
}
.admin-filter__count {
  font-size: 11px;
  font-weight: 700;
  background: rgba(255, 255, 255, .25);
  padding: 1px 6px;
  border-radius: 8px;
}
.admin-filter__chip:not(.is-active) .admin-filter__count {
  background: #F1F5F9;
  color: #64748B;
}

.admin-panel__head { display: flex; justify-content: space-between; align-items: center; }
.admin-panel__meta { font-size: 12px; color: #94A3B8; font-weight: 600; }
.admin-panel__placeholder { padding: 32px 0; text-align: center; color: #94A3B8; font-size: 13px; }
.admin-panel__placeholder--err { color: #DC2626; }

.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th {
  text-align: left;
  font-weight: 600;
  color: #475569;
  font-size: 12px;
  letter-spacing: .03em;
  text-transform: uppercase;
  padding: 10px 12px;
  border-bottom: 1px solid #E2E8F0;
  background: #F8FAFC;
}
.admin-table td {
  padding: 12px;
  border-bottom: 1px solid #F1F5F9;
  color: #0F172A;
}
.admin-table tr:hover td { background: #F8FAFC; }
.admin-table__mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }
.admin-table__muted { color: #94A3B8; font-size: 12px; }

.admin-link {
  color: #3B6EF5;
  text-decoration: none;
  font-weight: 600;
  font-size: 13px;
}
.admin-link:hover { text-decoration: underline; }

/* Status pills — colour map mirrors V2 §4.2.4 */
.admin-pill {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .03em;
  background: #F1F5F9;
  color: #475569;
}
.admin-pill--created   { background: #E0E7FF; color: #4338CA; }
.admin-pill--submitted { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--reviewing { background: #FEF3C7; color: #B45309; }
.admin-pill--approved  { background: #D1FAE5; color: #047857; }
.admin-pill--rejected  { background: #FEE2E2; color: #B91C1C; }
.admin-pill--closed    { background: #E2E8F0; color: #475569; }
.admin-pill--abnormal  { background: #FCE7F3; color: #9D174D; }
.admin-pill--failed    { background: #FECACA; color: #991B1B; }
</style>
