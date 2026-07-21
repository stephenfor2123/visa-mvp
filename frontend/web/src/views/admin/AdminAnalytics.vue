<template>
  <main class="analytics-page">
    <header class="page-head">
      <div>
        <h1>{{ t('admin.analytics.page_title') }}</h1>
        <p>{{ t('admin.analytics.page_subtitle') }}</p>
      </div>
      <div class="range-switch">
        <button
          v-for="item in ranges"
          :key="item.value"
          :class="{ active: range === item.value }"
          @click="range = item.value; load()"
        >{{ item.label }}</button>
      </div>
    </header>

    <div v-if="error" class="error-box">{{ error }}</div>

    <section class="kpi-grid">
      <article class="kpi-card">
        <span>{{ t('admin.analytics.total_events') }}</span>
        <strong>{{ fmt(data.total_events) }}</strong>
      </article>
      <article class="kpi-card">
        <span>{{ t('admin.analytics.unique_sessions') }}</span>
        <strong>{{ fmt(data.unique_sessions) }}</strong>
      </article>
      <article class="kpi-card">
        <span>{{ t('admin.analytics.identified_users') }}</span>
        <strong>{{ fmt(data.identified_users) }}</strong>
      </article>
      <article class="kpi-card">
        <span>{{ t('admin.analytics.event_types') }}</span>
        <strong>{{ fmt(data.event_types) }}</strong>
      </article>
    </section>

    <section class="analytics-grid">
      <article class="panel">
        <header class="panel__head">
          <h2>{{ t('admin.analytics.daily_trend') }}</h2>
          <span>{{ t('admin.analytics.events_and_sessions') }}</span>
        </header>
        <div v-if="loading" class="empty">{{ t('admin.analytics.loading') }}</div>
        <div v-else-if="!hasDailyData" class="empty">{{ t('admin.analytics.no_data') }}</div>
        <div v-else class="daily-chart">
          <div v-for="point in data.daily" :key="point.date" class="daily-col">
            <div class="daily-bars">
              <span
                class="daily-bar daily-bar--sessions"
                :style="{ height: barHeight(point.unique_sessions, maxDaily) }"
                :title="`${point.date}: ${point.unique_sessions}`"
              />
              <span
                class="daily-bar daily-bar--events"
                :style="{ height: barHeight(point.count, maxDaily) }"
                :title="`${point.date}: ${point.count}`"
              />
            </div>
            <small>{{ point.date.slice(5) }}</small>
          </div>
        </div>
        <div class="legend">
          <span><i class="legend-events" />{{ t('admin.analytics.events') }}</span>
          <span><i class="legend-sessions" />{{ t('admin.analytics.sessions') }}</span>
        </div>
      </article>

      <article class="panel">
        <header class="panel__head">
          <h2>{{ t('admin.analytics.event_distribution') }}</h2>
        </header>
        <div v-if="loading" class="empty">{{ t('admin.analytics.loading') }}</div>
        <div v-else-if="!data.events?.length" class="empty">{{ t('admin.analytics.no_data') }}</div>
        <ul v-else class="event-list">
          <li v-for="event in data.events" :key="event.event_name">
            <div class="event-row">
              <span>{{ eventLabel(event.event_name) }}</span>
              <strong>{{ fmt(event.count) }} <small>{{ event.share_pct.toFixed(1) }}%</small></strong>
            </div>
            <div class="event-track"><span :style="{ width: `${event.share_pct}%` }" /></div>
          </li>
        </ul>
      </article>
    </section>

    <section class="panel recent-panel">
      <header class="panel__head">
        <h2>{{ t('admin.analytics.recent_events') }}</h2>
        <span>{{ t('admin.analytics.recent_hint') }}</span>
      </header>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('admin.analytics.time') }}</th>
              <th>{{ t('admin.analytics.event') }}</th>
              <th>{{ t('admin.analytics.source') }}</th>
              <th>{{ t('admin.analytics.path') }}</th>
              <th>{{ t('admin.analytics.country') }}</th>
              <th>{{ t('admin.analytics.session') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.recent" :key="row.id">
              <td>{{ formatTime(row.created_at) }}</td>
              <td><span class="event-badge">{{ eventLabel(row.event_name) }}</span></td>
              <td>{{ row.source }}</td>
              <td class="path-cell">{{ row.path || '—' }}</td>
              <td>{{ row.country_code || '—' }}</td>
              <td>{{ row.session_id || '—' }}</td>
            </tr>
            <tr v-if="!loading && !data.recent?.length">
              <td colspan="6" class="empty">{{ t('admin.analytics.no_data') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getAnalyticsStats } from '@/api/admin'

const { t } = useI18n()
const loading = ref(false)
const error = ref('')
const range = ref('7d')
const data = ref({ events: [], daily: [], recent: [] })
const ranges = [
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
]

const maxDaily = computed(() => Math.max(1, ...data.value.daily.flatMap((p) => [p.count, p.unique_sessions])))
const hasDailyData = computed(() => data.value.daily.some((p) => p.count > 0))
const eventKeys = {
  page_view: 'page_view',
  country_selected: 'country_selected',
  wizard_started: 'wizard_started',
  form_completed: 'form_completed',
  login_wall_shown: 'login_wall_shown',
  auth_succeeded: 'auth_succeeded',
  order_created: 'order_created',
  checkout_viewed: 'checkout_viewed',
  checkout_started: 'checkout_started',
  payment_succeeded: 'payment_succeeded',
  payment_failed: 'payment_failed',
  order_detail_viewed: 'order_detail_viewed',
  order_completed: 'order_completed',
}

function eventLabel(name) {
  const key = eventKeys[name]
  return key ? t(`admin.analytics.event_names.${key}`) : name
}
function fmt(value) { return Number(value || 0).toLocaleString() }
function barHeight(value, max) { return `${Math.max(value ? 5 : 0, (Number(value || 0) / max) * 100)}%` }
function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getAnalyticsStats({ range: range.value, limit: 100 })
  } catch (err) {
    error.value = err?.message || t('admin.analytics.load_failed')
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.analytics-page { padding: 28px 32px 48px; color: #0f172a; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.page-head h1 { margin: 0; font-size: 24px; }
.page-head p { margin: 6px 0 0; color: #64748b; font-size: 13px; }
.range-switch { display: flex; padding: 3px; background: #e2e8f0; border-radius: 8px; }
.range-switch button { border: 0; background: transparent; padding: 7px 14px; border-radius: 6px; color: #64748b; cursor: pointer; }
.range-switch button.active { background: #fff; color: #2563eb; box-shadow: 0 1px 3px rgba(15,23,42,.1); }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px; }
.kpi-card, .panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; }
.kpi-card { padding: 18px; }
.kpi-card span { display: block; color: #64748b; font-size: 12px; }
.kpi-card strong { display: block; margin-top: 8px; font-size: 28px; }
.analytics-grid { display: grid; grid-template-columns: 1.25fr .75fr; gap: 12px; margin-bottom: 12px; }
.panel { padding: 20px; min-width: 0; }
.panel__head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 18px; }
.panel__head h2 { margin: 0; font-size: 16px; }
.panel__head span { color: #94a3b8; font-size: 12px; }
.daily-chart { height: 210px; display: flex; align-items: stretch; gap: 6px; padding-top: 10px; overflow-x: auto; }
.daily-col { min-width: 22px; flex: 1; display: flex; flex-direction: column; align-items: center; }
.daily-bars { flex: 1; width: 100%; display: flex; gap: 2px; align-items: flex-end; justify-content: center; }
.daily-bar { width: min(10px, 42%); border-radius: 3px 3px 0 0; min-height: 0; }
.daily-bar--events { background: #2563eb; }
.daily-bar--sessions { background: #93c5fd; }
.daily-col small { color: #94a3b8; font-size: 9px; margin-top: 6px; white-space: nowrap; }
.legend { display: flex; gap: 16px; justify-content: flex-end; color: #64748b; font-size: 11px; margin-top: 10px; }
.legend span { display: flex; align-items: center; gap: 5px; }
.legend i { width: 8px; height: 8px; border-radius: 2px; }
.legend-events { background: #2563eb; } .legend-sessions { background: #93c5fd; }
.event-list { list-style: none; padding: 0; margin: 0; }
.event-list li { margin-bottom: 14px; }
.event-row { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; margin-bottom: 6px; }
.event-row small { color: #94a3b8; font-weight: 400; margin-left: 6px; }
.event-track { height: 6px; border-radius: 999px; background: #f1f5f9; overflow: hidden; }
.event-track span { display: block; height: 100%; background: #2563eb; border-radius: inherit; }
.recent-panel { padding-bottom: 8px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { text-align: left; color: #64748b; font-weight: 600; padding: 10px; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
td { padding: 10px; border-bottom: 1px solid #f1f5f9; color: #475569; }
.event-badge { display: inline-block; padding: 3px 7px; border-radius: 6px; background: #eff6ff; color: #2563eb; white-space: nowrap; }
.path-cell { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { padding: 40px 16px; text-align: center; color: #94a3b8; }
.error-box { margin-bottom: 12px; padding: 12px; background: #fef2f2; color: #b91c1c; border-radius: 8px; }
@media (max-width: 900px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .analytics-grid { grid-template-columns: 1fr; }
}
</style>
