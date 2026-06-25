<!-- Orders.vue — W12 Story 1.2.3: Order List Page -->
<template>
  <div class="orders-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <HtexLogo :size="28" />
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
      </div>
    </header>

    <main class="app-container app-page orders-shell">
      <div class="page-header">
        <h1 class="page-title">{{ t('order_list.title') }}</h1>
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
        <AppButton variant="primary" size="lg" @click="$router.push('/destinations')">
          {{ t('order_list.go_destinations') }}
        </AppButton>
      </div>

      <!-- Order List -->
      <div v-else class="orders-list" data-testid="orders-list">
        <div class="orders-table">
          <div class="orders-table__head">
            <span>{{ t('order_list.col_destination') }}</span>
            <span>{{ t('order_list.col_visa_type') }}</span>
            <span>{{ t('order_list.col_status') }}</span>
            <span>{{ t('order_list.col_created') }}</span>
            <span></span>
          </div>

          <router-link
            v-for="order in orders"
            :key="order.order_no"
            :to="`/orders/${order.order_no}`"
            class="orders-table__row"
            data-testid="orders-row"
          >
            <span class="orders-table__dest">
              <span class="dest-flag">{{ flagEmoji(order.country_code) }}</span>
              {{ order.country_name }}
            </span>
            <span class="orders-table__visa">{{ order.visa_type || '—' }}</span>
            <span class="status-badge" :class="`status-badge--${order.status}`">
              {{ statusLabel(order.status) }}
            </span>
            <span class="orders-table__date">{{ formatDate(order.created_at) }}</span>
            <span class="orders-table__action">{{ t('order_list.action_view') }} →</span>
          </router-link>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import HtexLogo from '@/components/HtexLogo.vue'
import { useI18n } from 'vue-i18n'
import { listOrders } from '@/api/orders'
import LangSwitch from '@/components/LangSwitch.vue'
import AppButton from '@/components/AppButton.vue'

const { t } = useI18n()
const orders = ref([])
const loading = ref(true)
const loadError = ref('')

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
.orders-table {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.orders-table__head {
  display: grid;
  grid-template-columns: 2fr 1.5fr 1fr 1.2fr 80px;
  padding: 12px 16px;
  background: #f9fafb;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: .05em;
  border-bottom: 1px solid #e5e7eb;
}
.orders-table__row {
  display: grid;
  grid-template-columns: 2fr 1.5fr 1fr 1.2fr 80px;
  padding: 14px 16px;
  align-items: center;
  text-decoration: none;
  color: inherit;
  border-bottom: 1px solid #f0f0f0;
  transition: background .15s;
  cursor: pointer;
}
.orders-table__row:last-child { border-bottom: none; }
.orders-table__row:hover { background: #f9fafb; }
.orders-table__dest {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #1a1a2e;
}
.dest-flag { font-size: 20px; }
.orders-table__visa {
  font-size: 13px;
  color: #6b7280;
}
.orders-table__date {
  font-size: 13px;
  color: #6b7280;
}
.orders-table__action {
  font-size: 13px;
  color: var(--color-primary, #3b6ef5);
  text-align: right;
}
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
</style>