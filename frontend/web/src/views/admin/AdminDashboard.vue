<!--
  AdminDashboard.vue — 运营总览 (Dashboard)
  W37+ 重写版：用后端 5 个真端点 (summary/trend/funnel/top-countries/alerts),
  替代原 W14-11 占位页面。

  模块:
    1. 顶部 4 张 KPI 卡 (今日订单 / 营收 / 新用户 / 成功率) + 与上周同日对比
    2. 待处理订单 / 本月订单 / 总用户数 (次要 KPI)
    3. 每日趋势折线图 (订单/营收/新用户 三选一, 7d/30d/90d 切换)
    4. 转化漏斗 (4 步)
    5. 热门目的地 Top10
    6. 异常告警 (规则命中才出现)
-->
<template>
  <main class="admin-main">
    <header class="admin-main__head">
      <div class="admin-main__head-brand">
        <HtexLogo :size="24" color="#0F172A" />
        <h1>{{ t('admin.dashboard.page_title') }}</h1>
      </div>
      <div class="admin-main__head-actions">
        <button class="btn-secondary" :disabled="loading" @click="reload" data-testid="dashboard-refresh">
          <span v-if="loading" class="spinner-inline"></span>
          {{ loading ? '刷新中…' : '↻ 刷新' }}
        </button>
        <button class="btn-secondary" @click="openExport" data-testid="dashboard-export">
          导出 CSV
        </button>
      </div>
    </header>

    <!-- 1. 主 KPI 4 卡 -->
    <section class="kpi-grid" data-testid="dashboard-kpi">
      <AppCard class="kpi-card">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_orders') }}</div>
        <div class="kpi-card__value">{{ fmt(summary.today_orders) }}</div>
        <DeltaPct :value="summary.delta_orders_pct" :label="t('admin.dashboard.delta_vs_last_week')" />
      </AppCard>
      <AppCard class="kpi-card">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_revenue') }}</div>
        <div class="kpi-card__value">${{ fmtNum(summary.today_revenue_usd) }}</div>
        <DeltaPct :value="summary.delta_revenue_pct" :label="t('admin.dashboard.delta_vs_last_week')" />
      </AppCard>
      <AppCard class="kpi-card">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_new_users') }}</div>
        <div class="kpi-card__value">{{ fmt(summary.today_new_users) }}</div>
        <DeltaPct :value="summary.delta_users_pct" :label="t('admin.dashboard.delta_vs_last_week')" />
      </AppCard>
      <AppCard class="kpi-card">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_success_rate') }}</div>
        <div class="kpi-card__value">{{ fmtPct(summary.today_success_rate) }}</div>
        <div class="kpi-card__delta">支付成功订单 / 总订单</div>
      </AppCard>
    </section>

    <!-- 2. 次要 KPI 3 卡 -->
    <section class="kpi-grid kpi-grid--mini">
      <AppCard class="kpi-card kpi-card--mini">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_pending_orders') }}</div>
        <div class="kpi-card__value kpi-card__value--sm">{{ fmt(summary.pending_orders) }}</div>
      </AppCard>
      <AppCard class="kpi-card kpi-card--mini">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_month_orders') }}</div>
        <div class="kpi-card__value kpi-card__value--sm">{{ fmt(summary.month_orders) }}</div>
      </AppCard>
      <AppCard class="kpi-card kpi-card--mini">
        <div class="kpi-card__label">{{ t('admin.dashboard.kpi_total_users') }}</div>
        <div class="kpi-card__value kpi-card__value--sm">{{ fmt(summary.total_users) }}</div>
      </AppCard>
    </section>

    <!-- 2b. 待跟进运营提示 -->
    <section v-if="attentionTotal > 0" class="attention-grid" data-testid="dashboard-attention">
      <AppCard
        v-for="item in attentionItems"
        :key="item.key"
        v-show="item.count > 0"
        class="attention-card"
        :class="`attention-card--${item.key}`"
      >
        <div class="attention-card__count">{{ fmt(item.count) }}</div>
        <div class="attention-card__label">{{ t(`admin.dashboard.attention_${item.key}`) }}</div>
        <router-link to="/admin/orders" class="attention-card__link">{{ t('admin.dashboard.attention_go') }}</router-link>
      </AppCard>
    </section>

    <!-- 3. 趋势图 -->
    <AppCard class="admin-panel">
      <template #header>
        <div class="panel-head">
          <h3>{{ t('admin.dashboard.trend_title') }}</h3>
          <div class="panel-head__controls">
            <!-- 指标切换 -->
            <div class="seg">
              <button
                v-for="m in METRICS" :key="m.value"
                :class="['seg__btn', { 'is-active': trendMetric === m.value }]"
                :data-testid="`trend-metric-${m.value}`"
                @click="setMetric(m.value)"
              >{{ m.label }}</button>
            </div>
            <!-- 时间范围 -->
            <div class="seg">
              <button
                v-for="r in RANGES" :key="r.value"
                :class="['seg__btn', { 'is-active': trendRange === r.value }]"
                :data-testid="`trend-range-${r.value}`"
                @click="setRange(r.value)"
              >{{ r.label }}</button>
            </div>
          </div>
        </div>
      </template>
      <TrendChart
        :points="trend.points"
        :metric="trendMetric"
        :loading="trendLoading"
      />
      <div v-if="trend.points?.length" class="trend-totals">
        <span>{{ t('admin.dashboard.trend_metric_orders') }}: <b>{{ fmt(trend.total_orders) }}</b></span>
        <span>{{ t('admin.dashboard.trend_metric_revenue') }}: <b>${{ fmtNum(trend.total_revenue_usd) }}</b></span>
        <span>{{ t('admin.dashboard.trend_metric_users') }}: <b>{{ fmt(trend.total_new_users) }}</b></span>
      </div>
    </AppCard>

    <!-- 4. 转化漏斗 + 5. 热门目的地 (两列) -->
    <section class="dashboard-row">
      <AppCard class="admin-panel dashboard-col">
        <template #header>
          <h3>{{ t('admin.dashboard.funnel_title') }}</h3>
          <span class="admin-panel__meta">{{ t('admin.dashboard.funnel_overall') }}: {{ fmtPct((funnel.overall_conversion_pct || 0) / 100) }}</span>
        </template>
        <FunnelChart :steps="funnel.steps" :loading="funnelLoading" />
      </AppCard>

      <AppCard class="admin-panel dashboard-col">
        <template #header>
          <h3>{{ t('admin.dashboard.top_countries_title', { n: topCountries.items?.length || 0 }) }}</h3>
          <div class="seg seg--sm">
            <button
              v-for="r in TOP_RANGES" :key="r.value"
              :class="['seg__btn', { 'is-active': topRange === r.value }]"
              :data-testid="`top-range-${r.value}`"
              @click="setTopRange(r.value)"
            >{{ r.label }}</button>
          </div>
        </template>
        <div v-if="topLoading" class="admin-panel__placeholder">{{ t('admin.dashboard.loading') }}</div>
        <div v-else-if="!topCountries.items?.length" class="admin-panel__placeholder">
          {{ t('admin.dashboard.top_countries_no_data', { days: topRange === '30d' ? 30 : 7 }) }}
        </div>
        <ul v-else class="top-list">
          <li v-for="(it, i) in topCountries.items" :key="it.destination_id" class="top-row">
            <span class="top-rank">{{ i + 1 }}</span>
            <div class="top-info">
              <div class="top-info__name">
                <span class="top-flag">{{ flagFor(it.country_code) }}</span>
                {{ it.country_name }}
              </div>
              <div class="top-bar">
                <span class="top-bar__fill" :style="{ width: barWidth(it.conversion_pct, topCountries.items) + '%' }"></span>
              </div>
            </div>
            <div class="top-stats">
              <div class="top-stats__count">{{ fmt(it.order_count) }}</div>
              <div class="top-stats__rev">${{ fmtNum(it.revenue_usd) }}</div>
            </div>
          </li>
        </ul>
      </AppCard>
    </section>

    <!-- 6. 异常告警 -->
    <AppCard v-if="alerts.items?.length" class="admin-panel alerts-panel">
      <template #header>
        <h3>{{ t('admin.dashboard.alerts_title') }}</h3>
      </template>
      <ul class="alerts-list">
        <li v-for="a in alerts.items" :key="a.code" :class="['alert-row', `alert-row--${a.severity}`]">
          <span :class="['alert-badge', `alert-badge--${a.severity}`]">
            {{ t(`admin.dashboard.alerts_severity_${a.severity}`) }}
          </span>
          <div class="alert-info">
            <div class="alert-info__title">{{ a.title }}</div>
            <div class="alert-info__detail">{{ a.detail }}</div>
          </div>
        </li>
      </ul>
    </AppCard>
    <AppCard v-else class="admin-panel">
      <template #header>
        <h3>{{ t('admin.dashboard.alerts_title') }}</h3>
      </template>
      <div class="admin-panel__placeholder">{{ t('admin.dashboard.alerts_empty') }} ✓</div>
    </AppCard>

    <!-- 导出 CSV 配置 Modal -->
    <Teleport to="body">
      <div v-if="showExport" class="drawer-overlay" @click.self="showExport = false" data-testid="dashboard-export-modal">
        <div class="drawer export-drawer">
          <div class="drawer__head">
            <h2>导出 CSV 报表</h2>
            <button class="modal__close" @click="showExport = false">×</button>
          </div>
          <div class="drawer__body export-body">
            <!-- 时间范围 -->
            <section class="export-section">
              <h3>时间范围</h3>
              <div class="seg-grid">
                <button
                  v-for="r in EXPORT_RANGES" :key="r.value"
                  :class="['seg__btn', { 'is-active': exportRange === r.value }]"
                  :data-testid="`export-range-${r.value}`"
                  @click="setExportRange(r.value)"
                >{{ r.label }}</button>
              </div>
              <div v-if="exportRange === 'custom'" class="custom-range">
                <label>开始日期 <input type="date" v-model="exportStart" class="form-input" /></label>
                <label>结束日期 <input type="date" v-model="exportEnd" class="form-input" /></label>
              </div>
            </section>

            <!-- 导出模块 -->
            <section class="export-section">
              <h3>导出模块</h3>
              <label class="check-row">
                <input type="checkbox" v-model="exportModules.kpi" />
                <span>KPI 摘要(今日/本月/总用户)</span>
              </label>
              <label class="check-row">
                <input type="checkbox" v-model="exportModules.trend" />
                <span>每日趋势(按所选范围)</span>
              </label>
              <label class="check-row">
                <input type="checkbox" v-model="exportModules.funnel" />
                <span>转化漏斗(注册→创建→提交→完成)</span>
              </label>
              <label class="check-row">
                <input type="checkbox" v-model="exportModules.top" />
                <span>热门目的地 Top 10</span>
              </label>
              <label class="check-row">
                <input type="checkbox" v-model="exportModules.alerts" />
                <span>异常告警列表</span>
              </label>
            </section>
          </div>
          <div class="drawer__foot">
            <button class="btn-secondary" @click="showExport = false">取消</button>
            <button
              class="btn-primary"
              :disabled="exporting || !hasModuleSelected"
              @click="doExport"
              data-testid="export-confirm"
            >
              {{ exporting ? '导出中…' : '确认导出' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, h } from 'vue'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import HtexLogo from '@/components/HtexLogo.vue'
import { useAdminStore } from '@/stores/admin'
import {
  getDashboardSummary,
  getDashboardTrend,
  getDashboardFunnel,
  getDashboardTopCountries,
  getDashboardAlerts,
  getOrderAttentionCounts,
} from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()
const profile = computed(() => admin.profile)
const username = computed(() => admin.username)

// 4 国国旗 emoji 简单映射 (admin 内部用, 不会触达 C 端)
const FLAG = { US:'🇺🇸', GB:'🇬🇧', AU:'🇦🇺', DE:'🇩🇪', FR:'🇫🇷', JP:'🇯🇵', KR:'🇰🇷',
  CA:'🇨🇦', SG:'🇸🇬', TH:'🇹🇭', ID:'🇮🇩', VN:'🇻🇳', MY:'🇲🇾', PH:'🇵🇭',
  IN:'🇮🇳', NL:'🇳🇱', IT:'🇮🇹', ES:'🇪🇸', CH:'🇨🇭', NZ:'🇳🇿' }
function flagFor(cc) { return cc ? (FLAG[cc] || '🏳️') : '🏳️' }

// 状态
const loading = ref(false)
const summary = ref({})
const trend = ref({ points: [], total_orders: 0, total_revenue_usd: 0, total_new_users: 0 })
const funnel = ref({ steps: [], overall_conversion_pct: 0 })
const topCountries = ref({ items: [] })
const alerts = ref({ items: [] })
const attention = ref({})

const attentionItems = computed(() => [
  { key: 'payment_expiring_soon', count: attention.value.payment_expiring_soon || 0 },
  { key: 'paid_awaiting_diagnosis', count: attention.value.paid_awaiting_diagnosis || 0 },
  { key: 'completed_awaiting_portal', count: attention.value.completed_awaiting_portal || 0 },
  { key: 'refund_pending', count: attention.value.refund_pending || 0 },
  { key: 'refund_failed', count: attention.value.refund_failed || 0 },
])
const attentionTotal = computed(() => attentionItems.value.reduce((s, i) => s + i.count, 0))

const trendLoading = ref(false)
const funnelLoading = ref(false)
const topLoading = ref(false)

const trendMetric = ref('orders')
const trendRange = ref('7d')
const topRange = ref('7d')

// 导出配置
const showExport = ref(false)
const exporting = ref(false)
const exportRange = ref('7d')
const exportStart = ref('')
const exportEnd = ref('')
const exportModules = ref({ kpi: true, trend: true, funnel: true, top: true, alerts: false })
const EXPORT_RANGES = [
  { value: 'today', label: '今日' },
  { value: '7d',   label: '近 7 天' },
  { value: '30d',  label: '近 30 天' },
  { value: '90d',  label: '近 90 天' },
  { value: 'custom', label: '自定义' },
]
const hasModuleSelected = computed(() => Object.values(exportModules.value).some(Boolean))

const METRICS = [
  { value: 'orders',   label: '订单' },
  { value: 'revenue',  label: '营收' },
  { value: 'users',    label: '新用户' },
]
const RANGES = [
  { value: '7d',  label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
]
const TOP_RANGES = [
  { value: '7d',  label: '7d' },
  { value: '30d', label: '30d' },
]

// 格式化
function fmt(n) { return Number(n || 0).toLocaleString() }
function fmtNum(n) { return Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 }) }
function fmtPct(x) {
  const v = Number(x) || 0
  // 兼容 0~1 和 0~100 两种入参: 后端 trend 用 0~1, funnel 用 0~100
  const p = v <= 1 ? v * 100 : v
  return p.toFixed(1) + '%'
}
function barWidth(pct, all) {
  if (!all?.length) return 0
  const max = Math.max(...all.map(x => x.conversion_pct || 0))
  if (max === 0) return 0
  return Math.max(2, ((pct || 0) / max) * 100)
}

// 加载
async function loadSummary() {
  const r = await getDashboardSummary()
  summary.value = r
}
async function loadTrend() {
  trendLoading.value = true
  try {
    const r = await getDashboardTrend({ metric: trendMetric.value, range: trendRange.value })
    trend.value = r
  } finally { trendLoading.value = false }
}
async function loadFunnel() {
  funnelLoading.value = true
  try {
    const r = await getDashboardFunnel({ range: '7d' })
    funnel.value = r
  } finally { funnelLoading.value = false }
}
async function loadTopCountries() {
  topLoading.value = true
  try {
    const r = await getDashboardTopCountries({ range: topRange.value, limit: 10 })
    topCountries.value = r
  } finally { topLoading.value = false }
}
async function loadAlerts() {
  const r = await getDashboardAlerts()
  alerts.value = r
}

async function loadAttention() {
  attention.value = await getOrderAttentionCounts()
}

async function reload() {
  loading.value = true
  try {
    await Promise.all([
      loadSummary(), loadTrend(), loadFunnel(), loadTopCountries(), loadAlerts(), loadAttention(),
    ])
  } finally { loading.value = false }
}

function setMetric(v) { trendMetric.value = v; loadTrend() }
function setRange(v)  { trendRange.value = v;  loadTrend() }
function setTopRange(v) { topRange.value = v; loadTopCountries() }

// 导出配置
function setExportRange(v) { exportRange.value = v }

function openExport() {
  showExport.value = true
  exportRange.value = trendRange.value
}

// 把"7d"/"30d"/"today"/"custom" 解析为 API 用的 trend.range_key
function rangeForApi(r) {
  if (r === 'today') return '7d'  // API 没 today, 用 7d 占位 (CSV 里会用 today 标签)
  if (r === 'custom') return '7d' // 自定义走 fallback
  return r  // 7d / 30d / 90d
}

function rangeLabel(r) {
  if (r === 'today') return 'today'
  if (r === '7d') return '7d'
  if (r === '30d') return '30d'
  if (r === '90d') return '90d'
  if (r === 'custom') return `${exportStart.value || '?'}~${exportEnd.value || '?'}`
  return r
}

async function doExport() {
  exporting.value = true
  try {
    const apiRange = rangeForApi(exportRange.value)
    // 按需拉取(用户没勾 trend/funnel/top 就不浪费请求)
    const promises = []
    if (exportModules.value.trend && trend.value.points.length === 0) {
      promises.push(getDashboardTrend({ metric: trendMetric.value, range: apiRange }).then(r => { trend.value = r }))
    }
    if (exportModules.value.funnel && funnel.value.steps.length === 0) {
      promises.push(getDashboardFunnel({ range: apiRange }).then(r => { funnel.value = r }))
    }
    if (exportModules.value.top && topCountries.value.items.length === 0) {
      promises.push(getDashboardTopCountries({ range: topRange.value, limit: 10 }).then(r => { topCountries.value = r }))
    }
    if (promises.length) await Promise.all(promises)

    // 构造 CSV
    const lines = []
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    const label = rangeLabel(exportRange.value)
    const m = exportModules.value

    if (m.kpi) {
      lines.push('=== KPI Summary ===')
      lines.push(['指标', '数值'].join(','))
      lines.push(['今日订单', summary.value.today_orders ?? 0].join(','))
      lines.push(['今日营收(USD)', summary.value.today_revenue_usd ?? 0].join(','))
      lines.push(['今日新用户', summary.value.today_new_users ?? 0].join(','))
      lines.push(['今日成功率', summary.value.today_success_rate ?? 0].join(','))
      lines.push(['待处理订单', summary.value.pending_orders ?? 0].join(','))
      lines.push(['本月订单', summary.value.month_orders ?? 0].join(','))
      lines.push(['总用户数', summary.value.total_users ?? 0].join(','))
      lines.push('')
    }

    if (m.trend) {
      lines.push(`=== Daily Trend (${label}) ===`)
      lines.push(['日期', '订单数', '营收(USD)', '新用户'].join(','))
      for (const p of (trend.value.points || [])) {
        lines.push([p.date, p.orders, p.revenue_usd, p.new_users].join(','))
      }
      lines.push('')
    }

    if (m.funnel) {
      lines.push(`=== Conversion Funnel (${label}) ===`)
      lines.push(['步骤', '数量', '转化率(%)'].join(','))
      for (const s of (funnel.value.steps || [])) {
        lines.push([s.label, s.count, s.conversion_pct].join(','))
      }
      lines.push('')
    }

    if (m.top) {
      lines.push(`=== Top Destinations (${topRange.value}) ===`)
      lines.push(['排名', '国家代码', '国家名', '订单数', '营收(USD)', '占比(%)'].join(','))
      ;(topCountries.value.items || []).forEach((it, i) => {
        lines.push([i + 1, it.country_code, it.country_name, it.order_count, it.revenue_usd, it.conversion_pct].join(','))
      })
      lines.push('')
    }

    if (m.alerts) {
      lines.push('=== Alerts ===')
      lines.push(['严重度', '代码', '标题', '详情', '指标值', '阈值'].join(','))
      ;(alerts.value.items || []).forEach(a => {
        lines.push([a.severity, a.code, a.title, a.detail, a.metric_value, a.threshold].map(v => String(v).includes(',') ? `"${v}"` : v).join(','))
      })
      lines.push('')
    }

    const csv = '\ufeff' + lines.join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `htex-dashboard-${label}-${stamp}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showExport.value = false
  } catch (e) {
    alert('导出失败: ' + (e?.message || e))
  } finally {
    exporting.value = false
  }
}

// ---- 子组件: DeltaPct 涨跌标签 ----
const DeltaPct = {
  props: ['value', 'label'],
  setup(props) {
    return () => {
      // W63: 后端返 null = "上周同期为 0, 没有对比基线", 不假装 +100%
      if (props.value === null || props.value === undefined) {
        return h('div', { class: 'delta delta--new' }, [
          h('span', { class: 'delta__arrow' }, '新'),
          h('span', { class: 'delta__label' }, props.label || ''),
        ])
      }
      const v = Number(props.value) || 0
      const pct = (v * 100).toFixed(1)
      const sign = v > 0 ? '↑' : v < 0 ? '↓' : '·'
      const cls = v > 0 ? 'delta delta--up' : v < 0 ? 'delta delta--down' : 'delta'
      return h('div', { class: cls }, [
        h('span', { class: 'delta__arrow' }, `${sign} ${pct}%`),
        h('span', { class: 'delta__label' }, props.label || ''),
      ])
    }
  },
}

// ---- 子组件: TrendChart 轻量 SVG 柱状图 ----
const TrendChart = {
  props: ['points', 'metric', 'loading'],
  setup(props) {
    return () => {
      const pts = props.points || []
      if (props.loading) return h('div', { class: 'admin-panel__placeholder' }, '加载中…')
      if (!pts.length) return h('div', { class: 'admin-panel__placeholder' }, '暂无数据')

      const W = 800, H = 180, P = { l: 50, r: 16, t: 12, b: 28 }
      const innerW = W - P.l - P.r
      const innerH = H - P.t - P.b

      const valueKey = props.metric === 'revenue' ? 'revenue_usd' : props.metric === 'users' ? 'new_users' : 'orders'
      const values = pts.map(p => Number(p[valueKey]) || 0)
      const max = Math.max(...values, 1)

      // 柱宽自适应: < 30 天粗一些 (60% slot), 30-60 天中等 (70%), > 60 天细 (80%)
      const slotW = pts.length > 0 ? innerW / pts.length : innerW
      const fillRatio = pts.length <= 30 ? 0.6 : pts.length <= 60 ? 0.7 : 0.8
      const barW = Math.max(2, slotW * fillRatio)

      // y 轴刻度 (4 条: 0, 1/3, 2/3, max)
      const yTicks = [0, max / 3, (max * 2) / 3, max].map(v => ({
        v, y: P.t + innerH - (v / max) * innerH,
      }))
      // x 轴标签: < 8 天全标; 否则均分 5 个
      const xLabelIdx = pts.length <= 8
        ? pts.map((_, i) => i)
        : Array.from({ length: 5 }, (_, i) => Math.round((i * (pts.length - 1)) / 4))

      return h('svg', {
        viewBox: `0 0 ${W} ${H}`, class: 'trend-svg', preserveAspectRatio: 'none'
      }, [
        // y grid
        ...yTicks.map((t, i) => h('line', {
          key: `yg-${i}`, x1: P.l, y1: t.y, x2: W - P.r, y2: t.y,
          stroke: '#e4e7ed', 'stroke-dasharray': '3 3',
        })),
        // y labels
        ...yTicks.map((t, i) => h('text', {
          key: `yl-${i}`, x: P.l - 8, y: t.y + 4,
          'text-anchor': 'end', 'font-size': 11, fill: '#94a3b8',
        }, fmtAxisVal(t.v))),
        // bars (with hover tooltip via <title>)
        ...values.map((v, i) => {
          const cx = P.l + slotW * i + slotW / 2
          const x = cx - barW / 2
          const y = P.t + innerH - (v / max) * innerH
          const h = (v / max) * innerH
          const isZero = v === 0
          return h('rect', {
            key: `bar-${i}`, x, y: isZero ? y - 2 : y, width: barW, height: isZero ? 2 : h,
            fill: isZero ? '#cbd5e1' : '#3b6ef5', rx: 2,
          }, [
            h('title', { key: 'tt' }, `${pts[i].date}: ${v}`),
          ])
        }),
        // x labels
        ...xLabelIdx.map(i => h('text', {
          key: `xl-${i}`, x: P.l + slotW * i + slotW / 2, y: H - 8,
          'text-anchor': 'middle', 'font-size': 11, fill: '#94a3b8',
        }, (pts[i].date || '').slice(5))),
      ])
    }
  },
}

// ---- 子组件: FunnelChart 漏斗图 ----
const FunnelChart = {
  props: ['steps', 'loading'],
  setup(props) {
    return () => {
      if (props.loading) return h('div', { class: 'admin-panel__placeholder' }, '加载中…')
      const steps = props.steps || []
      if (!steps.length) return h('div', { class: 'admin-panel__placeholder' }, '暂无数据')
      const max = Math.max(...steps.map(s => s.count), 1)

      return h('ul', { class: 'funnel' }, steps.map((s, i) => {
        const w = Math.max(2, (s.count / max) * 100)
        return h('li', { key: s.key, class: 'funnel__step' }, [
          h('div', { class: 'funnel__row' }, [
            h('span', { class: 'funnel__step-label' }, s.label),
            h('span', { class: 'funnel__step-count' }, fmt(s.count)),
            h('span', { class: 'funnel__step-pct' }, `${(s.conversion_pct || 0).toFixed(1)}%`),
          ]),
          h('div', { class: 'funnel__bar-wrap' }, [
            h('div', { class: 'funnel__bar', style: { width: w + '%' } }),
          ]),
        ])
      }))
    }
  },
}

function fmtAxisVal(v) {
  if (v >= 1000) return (v / 1000).toFixed(1) + 'k'
  return Math.round(v).toString()
}

onMounted(reload)
</script>

<style scoped lang="scss">
.admin-main { padding: 28px 32px; overflow-y: auto; }

.admin-main__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 12px;
}
.admin-main__head-brand {
  display: flex; align-items: center; gap: 10px;
}
.admin-main__head h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
}
.admin-main__head-actions {
  display: flex; gap: 8px; align-items: center;
}
.admin-main__hello {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748B;
}
.btn-secondary {
  background: #fff;
  border: 1px solid #dcdfe6;
  color: #606266;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.btn-secondary:hover { background: #f5f7fa; }
.btn-secondary:disabled { opacity: .6; cursor: not-allowed; }
.spinner-inline {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid #3b6ef5;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin .8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.kpi-grid--mini { grid-template-columns: repeat(3, 1fr); margin-bottom: 20px; }
.attention-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.attention-card {
  padding: 14px 16px;
  border-left: 4px solid #F59E0B;
  background: #fffbeb;
}
.attention-card__count { font-size: 22px; font-weight: 700; color: #92400e; }
.attention-card__label { font-size: 12px; color: #78350f; margin: 4px 0 8px; }
.attention-card__link { font-size: 12px; color: #3B6EF5; font-weight: 600; text-decoration: none; }
.attention-card__link:hover { text-decoration: underline; }
.attention-card--refund_pending, .attention-card--refund_failed { border-left-color: #DC2626; background: #FEF2F2; }
.attention-card--refund_pending .attention-card__count,
.attention-card--refund_failed .attention-card__count { color: #991B1B; }
.kpi-card { padding: 16px 18px; }
.kpi-card--mini { padding: 12px 16px; }
.kpi-card__label {
  font-size: 12px;
  color: #64748B;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.kpi-card__label::before {
  content: '';
  width: 3px; height: 12px;
  background: #3b6ef5;
  border-radius: 2px;
}
.kpi-card__value {
  font-size: 26px;
  font-weight: 700;
  color: #0F172A;
  line-height: 1.15;
  margin: 2px 0 4px;
}
.kpi-card__value--sm { font-size: 20px; }
.kpi-card__delta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}
.delta { display: flex; gap: 6px; align-items: center; font-size: 11px; margin-top: 4px; }
.delta__arrow { font-weight: 600; }
.delta__label { color: #94a3b8; }
.delta--up .delta__arrow { color: #16A34A; }
.delta--down .delta__arrow { color: #DC2626; }
.delta--new .delta__arrow { color: #3B6EF5; font-weight: 600; }

/* 面板头 */
.panel-head {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  flex-wrap: wrap;
}
.panel-head__controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.panel-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: #0F172A; }

.seg { display: inline-flex; background: #f1f5f9; border-radius: 6px; padding: 2px; }
.seg--sm { padding: 1px; }
.seg__btn {
  background: transparent; border: none; padding: 5px 12px; font-size: 12px;
  color: #64748b; cursor: pointer; border-radius: 4px; transition: all .15s;
}
.seg--sm .seg__btn { padding: 3px 10px; font-size: 11px; }
.seg__btn:hover { color: #0F172A; }
.seg__btn.is-active { background: #fff; color: #3b6ef5; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.06); }

.admin-panel__placeholder {
  margin: 0; padding: 24px; text-align: center; color: #94a3b8; font-size: 13px;
}
.admin-panel__meta { font-size: 12px; color: #64748b; }

/* 趋势图 */
.trend-svg {
  width: 100%; height: 200px; display: block;
  margin-top: 4px;
}
.trend-totals {
  display: flex; gap: 24px; margin-top: 8px; padding-top: 8px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px; color: #94a3b8;
}
.trend-totals b { color: #0F172A; font-weight: 600; }

/* dashboard row 两列 */
.dashboard-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.dashboard-col { min-width: 0; }

/* 漏斗 */
.funnel { list-style: none; margin: 8px 0 0; padding: 0; }
.funnel__step { margin-bottom: 14px; }
.funnel__step:last-child { margin-bottom: 0; }
.funnel__row {
  display: flex; align-items: baseline; gap: 10px;
  font-size: 13px; margin-bottom: 4px; color: #475569;
}
.funnel__step-label { font-weight: 500; color: #0F172A; min-width: 90px; }
.funnel__step-count { color: #0F172A; font-weight: 600; }
.funnel__step-pct { color: #94a3b8; font-size: 12px; margin-left: auto; }
.funnel__bar-wrap {
  background: #f1f5f9;
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
}
.funnel__bar {
  height: 100%;
  background: linear-gradient(90deg, #3b6ef5, #5b85f5);
  border-radius: 4px;
  transition: width .4s;
}

/* 热门目的地 */
.top-list { list-style: none; margin: 8px 0 0; padding: 0; }
.top-row {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 10px 4px;
  border-bottom: 1px solid #f1f5f9;
}
.top-row:last-child { border-bottom: none; }
.top-rank {
  font-size: 12px; color: #94a3b8; font-weight: 600;
  width: 24px; text-align: center;
}
.top-row:nth-child(1) .top-rank { color: #F59E0B; }
.top-row:nth-child(2) .top-rank { color: #94a3b8; }
.top-row:nth-child(3) .top-rank { color: #B45309; }
.top-info { min-width: 0; }
.top-info__name {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #0F172A; font-weight: 500;
  margin-bottom: 4px;
}
.top-flag { font-size: 14px; }
.top-bar {
  height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden;
}
.top-bar__fill {
  display: block; height: 100%;
  background: linear-gradient(90deg, #3b6ef5, #5b85f5);
  border-radius: 3px;
  transition: width .4s;
}
.top-stats { text-align: right; }
.top-stats__count { font-size: 14px; font-weight: 600; color: #0F172A; }
.top-stats__rev { font-size: 11px; color: #94a3b8; margin-top: 2px; }

/* 告警 */
.alerts-list { list-style: none; margin: 8px 0 0; padding: 0; }
.alert-row {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}
.alert-row--info     { background: #eff6ff; }
.alert-row--warning  { background: #fffbeb; }
.alert-row--critical { background: #fef2f2; }
.alert-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 3px; font-weight: 600;
  white-space: nowrap;
}
.alert-badge--info     { background: #dbeafe; color: #1e40af; }
.alert-badge--warning  { background: #fef3c7; color: #92400e; }
.alert-badge--critical { background: #fecaca; color: #991b1b; }
.alert-info__title { font-size: 13px; font-weight: 600; color: #0F172A; margin-bottom: 2px; }
.alert-info__detail { font-size: 12px; color: #475569; line-height: 1.5; }

/* 导出 drawer */
.drawer-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.45);
  z-index: 1000; display: flex; justify-content: center; align-items: flex-start;
  padding-top: 10vh;
}
.drawer {
  background: #fff;
  width: 480px; max-width: calc(100vw - 24px);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0,0,0,.2);
  display: flex; flex-direction: column;
  max-height: 80vh;
}
.drawer__head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
}
.drawer__head h2 { margin: 0; font-size: 16px; font-weight: 600; }
.modal__close {
  background: none; border: none; font-size: 22px; cursor: pointer;
  color: #94a3b8; line-height: 1; padding: 0 4px;
}
.modal__close:hover { color: #0F172A; }
.drawer__body { padding: 20px; overflow-y: auto; flex: 1; }
.drawer__foot {
  padding: 14px 20px;
  border-top: 1px solid #e4e7ed;
  display: flex; justify-content: flex-end; gap: 8px;
  background: #f8fafc;
}

.export-drawer { width: 480px; }
.export-section { margin-bottom: 22px; }
.export-section:last-child { margin-bottom: 0; }
.export-section h3 {
  margin: 0 0 10px;
  font-size: 13px; font-weight: 600; color: #475569;
  text-transform: uppercase; letter-spacing: .5px;
}
.seg-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px;
  background: #f1f5f9; padding: 3px; border-radius: 6px;
}
.seg-grid .seg__btn {
  padding: 6px 8px; font-size: 12px;
}
.custom-range {
  display: flex; gap: 12px; margin-top: 10px;
}
.custom-range label {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; color: #475569; flex: 1;
}
.check-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  border: 1px solid #e4e7ed; border-radius: 6px;
  cursor: pointer; margin-bottom: 6px;
  transition: all .15s;
}
.check-row:hover { border-color: #3b6ef5; background: #f8fafc; }
.check-row input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; }
.check-row span { font-size: 13px; color: #0F172A; }

.btn-primary {
  background: #3b6ef5; color: #fff; border: none;
  padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;
}
.btn-primary:hover:not(:disabled) { background: #2c5dd9; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }

/* 响应式 */
@media (max-width: 1100px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .dashboard-row { grid-template-columns: 1fr; }
}
</style>
