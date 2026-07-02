<!--
  AdminDashboard.vue — W14-11
  Minimal admin home / overview placeholder. Shows logged-in profile,
  a small navigation list, and a logout button. Subsequent stories
  (W14-12+) will fill in real metrics and CRUD pages.
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.dashboard') }}</h1>
        <p class="admin-main__hello">
          {{ profile?.display_name || profile?.username || username || 'admin' }}
        </p>
      </header>

      <section class="admin-cards">
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.menu_orders') }} · 今日</div>
          <div class="admin-card__value">{{ fmt(stats.today_new_orders) }}</div>
          <div class="admin-card__delta">本周 {{ fmt(stats.week_new_orders) }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">待处理 (created + submitted)</div>
          <div class="admin-card__value">{{ fmt(stats.pending_orders) }}</div>
          <div class="admin-card__delta">已完成 {{ fmt(stats.completed_orders) }}</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">提交成功率</div>
          <div class="admin-card__value">{{ fmtPct(stats.payment_success_rate) }}</div>
          <div class="admin-card__delta">最近数据, 60s 缓存</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">RPA · 今日访问</div>
          <div class="admin-card__value">{{ fmt(rpaStats.today_visits) }}</div>
          <div class="admin-card__delta">队列 {{ fmt(rpaStats.queued_tasks) }} · 24h 失败 {{ fmtPct(rpaStats.failure_rate_24h) }}</div>
        </AppCard>
      </section>

      <AppCard class="admin-panel">
        <template #header>
          <h3>{{ t('admin.menu_overview') }}</h3>
        </template>
        <p class="admin-panel__placeholder">
          <!-- placeholder copy — real KPIs/charts arrive in W14-12 -->
          Welcome, <b>{{ profile?.username || username }}</b>. This dashboard will surface orders, users, and RPA health in upcoming stories.
        </p>
        <ul class="admin-panel__links">
          <li><router-link to="/admin/rate-limit">{{ t('admin.menu_settings') }} →</router-link></li>
        </ul>
      </AppCard>
    </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { setLocale } from '@/i18n'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'
import { getDashboardStats, getRpaStats } from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const profile = computed(() => admin.profile)
const username = computed(() => admin.username)

// W34: real data from /dashboard/stats + /rpa-stats. Falls back to the
// previous hardcoded numbers only if the API errors out (so the page
// never goes blank during a backend blip).
const stats = ref({
  today_new_orders: 0,
  week_new_orders: 0,
  pending_orders: 0,
  completed_orders: 0,
  payment_success_rate: 0,
})
const rpaStats = ref({
  today_visits: 0,
  queued_tasks: 0,
  failure_rate_24h: 0,
  success_count_24h: 0,
})
const statsLoading = ref(true)

function fmt(n) { return Number(n || 0).toLocaleString() }
function fmtPct(x) { return ((Number(x) || 0) * 100).toFixed(1) + '%' }


onMounted(async () => {
  // Pull both stat endpoints in parallel; degrade gracefully.
  const [a, b] = await Promise.allSettled([
    getDashboardStats(),
    getRpaStats(),
  ])
  if (a.status === 'fulfilled') stats.value = { ...stats.value, ...a.value }
  if (b.status === 'fulfilled') rpaStats.value = { ...rpaStats.value, ...b.value }
  statsLoading.value = false
})
</script>

<style scoped lang="scss">

.admin-main {
  padding: 28px 32px;
  overflow-y: auto;
}

.admin-main__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 20px;
}

.admin-main__head h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
}

.admin-main__hello {
  margin: 0;
  font-size: 13px;
  color: #64748B;
}

.admin-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}

.admin-card {
  padding: 16px 18px;
}

.admin-card__label {
  font-size: 12px;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: .5px;
}

.admin-card__value {
  font-size: 26px;
  font-weight: 700;
  color: #0F172A;
  margin: 6px 0 4px;
}

.admin-card__delta {
  font-size: 12px;
  color: #16A34A;
}

.admin-panel__placeholder {
  margin: 0 0 12px;
  font-size: 14px;
  color: #475569;
}

.admin-panel__links {
  margin: 0;
  padding: 0;
  list-style: none;
}

.admin-panel__links a {
  color: #3B6EF5;
  text-decoration: none;
  font-size: 14px;
}

.admin-panel__links a:hover { text-decoration: underline; }
</style>