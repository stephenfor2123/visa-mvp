<!--
  RateLimit.vue — W14-6 后台限流配置可视化
  ============================================
  提供:
    1. 实时统计卡片 (今日访问 / 当前排队 / 24h 失败率 / 24h 任务数)
    2. 单 IP 单日访问次数 + 单账号提交间隔 + 错峰时段 + 限流 key 配置
    3. 保存按钮 → PUT /api/v2/admin/config/rpa

  所有文案 t() i18n, 数据走 admin.js 的 adminHttp 实例。
-->
<template>
  <div class="rate-limit-page">
    <header class="admin-topbar">
      <div class="admin-topbar__left">
        <router-link to="/admin/dashboard" class="admin-topbar__brand">
          <span class="admin-topbar__mark">A</span>
          <span class="admin-topbar__title">{{ t('admin.brand') }}</span>
        </router-link>
        <span class="admin-topbar__crumb">› {{ t('admin.ratelimit.page_title') }}</span>
      </div>
      <div class="admin-topbar__right">
        <span v-if="profile?.username" class="admin-topbar__user" data-testid="admin-user-name">
          {{ profile.username }}
        </span>
        <LangSwitch />
        <button
          type="button"
          class="admin-topbar__logout"
          @click="onLogout"
          data-testid="admin-logout-btn"
        >{{ t('admin.logout') }}</button>
      </div>
    </header>

    <main class="admin-shell">
      <!-- 页面标题 -->
      <section class="page-head" data-testid="rate-limit-head">
        <div>
          <h1 class="page-head__title">{{ t('admin.ratelimit.page_title') }}</h1>
          <p class="page-head__sub">{{ t('admin.ratelimit.page_subtitle') }}</p>
        </div>
        <div class="page-head__actions">
          <button
            type="button"
            class="ghost-btn"
            :disabled="loadingStats"
            @click="loadStats"
            data-testid="rate-limit-refresh-stats"
          >🔄 {{ t('admin.ratelimit.refresh_stats') }}</button>
        </div>
      </section>

      <!-- 实时统计卡片 -->
      <section class="stats-grid" data-testid="rate-limit-stats">
        <div class="stat-card" data-testid="stat-today-visits">
          <div class="stat-card__label">{{ t('admin.ratelimit.stat_today_visits') }}</div>
          <div class="stat-card__value">
            <span class="stat-card__num">{{ stats.today_visits }}</span>
            <span class="stat-card__unit">{{ t('admin.ratelimit.unit_visits') }}</span>
          </div>
          <div class="stat-card__hint">{{ t('admin.ratelimit.stat_today_visits_hint') }}</div>
        </div>

        <div class="stat-card" data-testid="stat-queued-tasks">
          <div class="stat-card__label">{{ t('admin.ratelimit.stat_queued') }}</div>
          <div class="stat-card__value">
            <span class="stat-card__num stat-card__num--accent">{{ stats.queued_tasks }}</span>
            <span class="stat-card__unit">{{ t('admin.ratelimit.unit_tasks') }}</span>
          </div>
          <div class="stat-card__hint">{{ t('admin.ratelimit.stat_queued_hint') }}</div>
        </div>

        <div class="stat-card" :class="failureClass" data-testid="stat-failure-rate">
          <div class="stat-card__label">{{ t('admin.ratelimit.stat_failure_rate') }}</div>
          <div class="stat-card__value">
            <span class="stat-card__num">{{ formattedFailureRate }}</span>
          </div>
          <div class="stat-card__hint">
            {{ t('admin.ratelimit.stat_failure_rate_hint', { failed: stats.failed_count_24h, total: stats.total_count_24h }) }}
          </div>
        </div>

        <div class="stat-card stat-card--soft" data-testid="stat-active-accounts">
          <div class="stat-card__label">{{ t('admin.ratelimit.stat_active_accounts') }}</div>
          <div class="stat-card__value">
            <span class="stat-card__num">{{ stats.active_accounts }}</span>
            <span class="stat-card__unit">{{ t('admin.ratelimit.unit_accounts') }}</span>
          </div>
          <div class="stat-card__hint">{{ t('admin.ratelimit.stat_active_accounts_hint') }}</div>
        </div>
      </section>

      <!-- 配置表单 -->
      <section class="config-card" data-testid="rate-limit-config">
        <header class="config-card__head">
          <h2>{{ t('admin.ratelimit.config_title') }}</h2>
          <p>{{ t('admin.ratelimit.config_subtitle') }}</p>
        </header>

        <div class="form-grid">
          <!-- 单 IP 单日最大访问次数 -->
          <div class="form-row" data-testid="row-ip-per-day">
            <label class="form-label">
              {{ t('admin.ratelimit.ip_per_day_label') }}
              <span class="form-required">*</span>
            </label>
            <div class="form-control">
              <input
                type="number"
                class="form-input"
                v-model.number="form.ip_per_day"
                :min="MIN_IP_PER_DAY"
                :max="MAX_IP_PER_DAY"
                :step="1"
                :placeholder="String(DEFAULT_IP_PER_DAY)"
                data-testid="input-ip-per-day"
              />
              <span class="form-suffix">{{ t('admin.ratelimit.unit_times_per_day') }}</span>
            </div>
            <p class="form-hint">{{ t('admin.ratelimit.ip_per_day_hint') }}</p>
          </div>

          <!-- 单账号提交间隔 -->
          <div class="form-row" data-testid="row-account-interval">
            <label class="form-label">
              {{ t('admin.ratelimit.account_interval_label') }}
              <span class="form-required">*</span>
            </label>
            <div class="form-control">
              <input
                type="number"
                class="form-input"
                v-model.number="form.account_interval_minutes"
                :min="MIN_INTERVAL_MIN"
                :max="MAX_INTERVAL_MIN"
                :step="1"
                :placeholder="String(DEFAULT_INTERVAL_MIN)"
                data-testid="input-account-interval"
              />
              <span class="form-suffix">{{ t('admin.ratelimit.unit_minutes') }}</span>
            </div>
            <p class="form-hint">{{ t('admin.ratelimit.account_interval_hint') }}</p>
          </div>

          <!-- 错峰时段 — 使用原生 <input type="time"> 避免 Element Plus scan -->
          <div class="form-row form-row--wide" data-testid="row-off-peak">
            <label class="form-label">
              {{ t('admin.ratelimit.off_peak_label') }}
            </label>
            <div class="form-control form-control--inline">
              <input
                type="time"
                class="form-input form-input--time"
                v-model="offPeakStart"
                :aria-label="t('admin.ratelimit.off_peak_start_placeholder')"
                data-testid="input-off-peak-start"
              />
              <span class="form-divider">→</span>
              <input
                type="time"
                class="form-input form-input--time"
                v-model="offPeakEnd"
                :aria-label="t('admin.ratelimit.off_peak_end_placeholder')"
                data-testid="input-off-peak-end"
              />
            </div>
            <p class="form-hint">{{ t('admin.ratelimit.off_peak_hint') }}</p>
          </div>

          <!-- 限流 key — 使用原生 <select> 避免 Element Plus scan -->
          <div class="form-row" data-testid="row-rate-key">
            <label class="form-label">
              {{ t('admin.ratelimit.rate_key_label') }}
            </label>
            <div class="form-control">
              <select
                v-model="form.rate_key"
                class="form-input form-input--select"
                :aria-label="t('admin.ratelimit.rate_key_placeholder')"
                data-testid="input-rate-key"
              >
                <option
                  v-for="opt in rateKeyOptions"
                  :key="opt.value"
                  :value="opt.value"
                >{{ t(opt.labelKey) }}</option>
              </select>
            </div>
            <p class="form-hint">{{ t('admin.ratelimit.rate_key_hint') }}</p>
          </div>
        </div>

        <!-- 表单错误 -->
        <div v-if="formError" class="form-error" role="alert" data-testid="rate-limit-error">
          ⚠ {{ formError }}
        </div>

        <!-- 操作栏 -->
        <footer class="config-card__foot">
          <span class="config-card__updated">
            {{ lastSavedLabel }}
          </span>
          <div class="config-card__actions">
            <button
              type="button"
              class="ghost-btn"
              :disabled="loadingConfig || saving"
              @click="loadConfig"
              data-testid="rate-limit-reload"
            >{{ t('admin.ratelimit.reload_btn') }}</button>
            <button
              type="button"
              class="primary-btn"
              :disabled="saving || !isDirty"
              @click="onSave"
              data-testid="rate-limit-save"
            >
              <span v-if="saving">{{ t('admin.ratelimit.saving') }}</span>
              <span v-else>{{ t('admin.ratelimit.save_btn') }}</span>
            </button>
          </div>
        </footer>
      </section>

      <!-- 加载态 -->
      <div v-if="loadingConfig && !configLoaded" class="loading-block" data-testid="rate-limit-loading">
        <span class="spinner"></span> {{ t('common.loading') }}
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import LangSwitch from '@/components/LangSwitch.vue'
import { useToast } from '@/composables/useToast'
import { useAdminStore } from '@/stores/admin'
import {
  getRpaConfig,
  updateRpaConfig,
  getRpaStats,
  adminLogout,
  RPA_DEFAULT_CONFIG
} from '@/api/admin'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const adminStore = useAdminStore()

// ── Refs ─────────────────────────────────────────────────────────────────────
const profile = computed(() => adminStore.profile)

// 时间选择器绑定 — Element Plus 期望 Date 对象, 但我们使用 HH:mm 字符串值格式
const offPeakStart = ref('00:00')
const offPeakEnd = ref('06:00')

const form = reactive({
  ip_per_day: 50,
  account_interval_minutes: 30,
  rate_key: 'ip'
})

const stats = reactive({
  today_visits: 0,
  queued_tasks: 0,
  failure_rate_24h: 0,
  success_count_24h: 0,
  failed_count_24h: 0,
  total_count_24h: 0,
  active_accounts: 0,
  generated_at: null
})

const initialSnapshot = ref(JSON.stringify(form))
const lastSavedAt = ref(null)
const saving = ref(false)
const loadingConfig = ref(false)
const loadingStats = ref(false)
const configLoaded = ref(false)
const formError = ref('')

// ── Constants ─────────────────────────────────────────────────────────────────
const MIN_IP_PER_DAY = 1
const MAX_IP_PER_DAY = 10000
const MIN_INTERVAL_MIN = 1
const MAX_INTERVAL_MIN = 1440
const DEFAULT_IP_PER_DAY = 50
const DEFAULT_INTERVAL_MIN = 30

const rateKeyOptions = [
  { value: 'ip',        labelKey: 'admin.ratelimit.rate_key_ip' },
  { value: 'ip_ua',     labelKey: 'admin.ratelimit.rate_key_ip_ua' },
  { value: 'cookie',    labelKey: 'admin.ratelimit.rate_key_cookie' }
]

// ── Computed ──────────────────────────────────────────────────────────────────
const isDirty = computed(() => {
  return JSON.stringify(form) !== initialSnapshot.value
})

const failureClass = computed(() => {
  const r = stats.failure_rate_24h || 0
  if (r >= 0.25) return 'stat-card--danger'
  if (r >= 0.10) return 'stat-card--warning'
  return 'stat-card--ok'
})

const formattedFailureRate = computed(() => {
  const r = stats.failure_rate_24h || 0
  return (r * 100).toFixed(2) + '%'
})

const lastSavedLabel = computed(() => {
  if (!lastSavedAt.value) return t('admin.ratelimit.never_saved')
  return t('admin.ratelimit.last_saved_at', {
    time: formatDateTime(lastSavedAt.value)
  })
})

// ── Time picker: native <input type="time"> writes/reads "HH:mm" strings
//   directly via v-model, so no separate computed mirror is required.
//   (Switched away from el-time-picker to avoid Element Plus tree-shake scan
//    hanging vite on macOS — see W14-6 retry notes.)

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatDateTime(d) {
  if (!d) return ''
  const date = d instanceof Date ? d : new Date(d)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function applyConfigToForm(cfg) {
  const rl = (cfg?.rate_limits) || {}
  form.ip_per_day = Number(rl.ip_per_day ?? DEFAULT_IP_PER_DAY)
  form.account_interval_minutes = Number(rl.account_interval_minutes ?? DEFAULT_INTERVAL_MIN)
  offPeakStart.value = String(rl.off_peak_start ?? '00:00')
  offPeakEnd.value = String(rl.off_peak_end ?? '06:00')
  form.rate_key = String(rl.rate_key ?? 'ip')
  initialSnapshot.value = JSON.stringify({
    ip_per_day: form.ip_per_day,
    account_interval_minutes: form.account_interval_minutes,
    rate_key: form.rate_key
  })
  configLoaded.value = true
}

function validateForm() {
  formError.value = ''
  if (!Number.isInteger(form.ip_per_day) || form.ip_per_day < MIN_IP_PER_DAY || form.ip_per_day > MAX_IP_PER_DAY) {
    formError.value = t('admin.ratelimit.err_ip_range', { min: MIN_IP_PER_DAY, max: MAX_IP_PER_DAY })
    return false
  }
  if (!Number.isInteger(form.account_interval_minutes) ||
      form.account_interval_minutes < MIN_INTERVAL_MIN ||
      form.account_interval_minutes > MAX_INTERVAL_MIN) {
    formError.value = t('admin.ratelimit.err_interval_range', { min: MIN_INTERVAL_MIN, max: MAX_INTERVAL_MIN })
    return false
  }
  if (!form.rate_key) {
    formError.value = t('admin.ratelimit.err_rate_key_required')
    return false
  }
  return true
}

// ── Data loaders ─────────────────────────────────────────────────────────────
async function loadConfig() {
  loadingConfig.value = true
  try {
    const cfg = await getRpaConfig()
    applyConfigToForm(cfg)
  } catch (err) {
    toast.error(err?.message || t('admin.ratelimit.err_load_config'))
  } finally {
    loadingConfig.value = false
  }
}

async function loadStats() {
  loadingStats.value = true
  try {
    const data = await getRpaStats()
    Object.assign(stats, data)
  } catch (err) {
    toast.error(err?.message || t('admin.ratelimit.err_load_stats'))
  } finally {
    loadingStats.value = false
  }
}

async function loadAll() {
  await Promise.all([loadConfig(), loadStats()])
}

// ── Actions ─────────────────────────────────────────────────────────────────
async function onSave() {
  if (saving.value) return
  if (!validateForm()) return

  saving.value = true
  try {
    const updated = await updateRpaConfig({
      ip_per_day: form.ip_per_day,
      account_interval_minutes: form.account_interval_minutes,
      off_peak_start: offPeakStart.value,
      off_peak_end: offPeakEnd.value,
      rate_key: form.rate_key
    })
    applyConfigToForm(updated)
    lastSavedAt.value = new Date()
    toast.success(t('admin.ratelimit.toast_saved'))
    // Refresh stats — config change may affect rate-limit outcomes
    loadStats()
  } catch (err) {
    formError.value = err?.message || t('admin.ratelimit.err_save_failed')
    toast.error(formError.value)
  } finally {
    saving.value = false
  }
}

function onLogout() {
  adminLogout()
  adminStore.logout()
  router.replace('/admin/login')
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  adminStore.hydrate()
  // If unauthenticated, redirect to admin login with redirect back here
  if (!adminStore.isAuthenticated) {
    router.replace({ path: '/admin/login', query: { redirect: '/admin/rate-limit' } })
    return
  }
  await loadAll()
})
</script>

<style scoped lang="scss">
.rate-limit-page {
  min-height: 100vh;
  background: var(--bg, #FAFBFC);
  color: var(--ink-1, #0F172A);
  display: flex;
  flex-direction: column;
}

// ── Topbar ──────────────────────────────────────────────────────────────────
.admin-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  background: #0F172A;
  color: #E2E8F0;
  border-bottom: 1px solid rgba(255, 255, 255, .08);
}
.admin-topbar__left { display: flex; align-items: center; gap: 12px; }
.admin-topbar__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #F8FAFC;
  font-weight: 600;
}
.admin-topbar__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: #3B6EF5;
  color: #fff;
  border-radius: 6px;
  font-weight: 700;
  font-size: 14px;
}
.admin-topbar__title { font-size: 15px; letter-spacing: .5px; }
.admin-topbar__crumb { font-size: 13px; color: rgba(226,232,240,.7); }
.admin-topbar__right { display: flex; align-items: center; gap: 14px; }
.admin-topbar__user {
  font-size: 13px;
  color: rgba(226,232,240,.85);
  padding: 4px 10px;
  background: rgba(255,255,255,.06);
  border-radius: 6px;
}
.admin-topbar__logout {
  background: transparent;
  border: 1px solid rgba(255,255,255,.2);
  color: #E2E8F0;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background .15s, border-color .15s;
}
.admin-topbar__logout:hover { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.35); }

// ── Shell ───────────────────────────────────────────────────────────────────
.admin-shell {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.page-head__title {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: var(--ink-1, #0F172A);
}
.page-head__sub {
  margin: 0;
  font-size: 14px;
  color: var(--ink-3, #64748B);
}
.page-head__actions { display: flex; gap: 8px; }

// ── Buttons ─────────────────────────────────────────────────────────────────
.primary-btn {
  background: #3B6EF5;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s, transform .1s;
}
.primary-btn:hover:not(:disabled) { background: #2D5BD9; }
.primary-btn:active:not(:disabled) { transform: translateY(1px); }
.primary-btn:disabled {
  background: #94A3B8;
  cursor: not-allowed;
  opacity: .6;
}

.ghost-btn {
  background: #fff;
  color: var(--ink-2, #334155);
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px;
  padding: 9px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.ghost-btn:hover:not(:disabled) { border-color: #94A3B8; background: #F8FAFC; }
.ghost-btn:disabled { opacity: .5; cursor: not-allowed; }

// ── Stats grid ─────────────────────────────────────────────────────────────
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-card--soft { background: #F8FAFC; }
.stat-card--ok    { border-left: 3px solid #22C55E; }
.stat-card--warning { border-left: 3px solid #F59E0B; }
.stat-card--danger { border-left: 3px solid #EF4444; }

.stat-card__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3, #64748B);
  text-transform: uppercase;
  letter-spacing: .5px;
}
.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.stat-card__num {
  font-size: 32px;
  font-weight: 700;
  color: var(--ink-1, #0F172A);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.stat-card__num--accent { color: #3B6EF5; }
.stat-card__unit {
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
.stat-card__hint {
  font-size: 12px;
  color: var(--ink-3, #64748B);
  line-height: 1.5;
}

// ── Config card ────────────────────────────────────────────────────────────
.config-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
  overflow: hidden;
}
.config-card__head {
  padding: 20px 24px;
  border-bottom: 1px solid #F1F5F9;
  h2 {
    margin: 0 0 4px;
    font-size: 17px;
    font-weight: 600;
    color: var(--ink-1, #0F172A);
  }
  p {
    margin: 0;
    font-size: 13px;
    color: var(--ink-3, #64748B);
  }
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px 24px;
  padding: 24px;
}
.form-row--wide { grid-column: 1 / -1; }

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2, #334155);
  margin-bottom: 8px;
}
.form-required { color: #DC2626; margin-left: 2px; }

.form-control {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px;
  padding: 0 12px;
  transition: border-color .15s, box-shadow .15s;
}
.form-control:focus-within {
  border-color: var(--el-color-primary, #3B6EF5);
  box-shadow: 0 0 0 3px rgba(59,110,245,.15);
}
.form-control--inline { padding: 0 12px; }
.form-input {
  flex: 1;
  height: 40px;
  border: none;
  outline: none;
  font-size: 14px;
  background: transparent;
  color: var(--ink-1, #0F172A);
}
.form-suffix {
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
.form-divider {
  color: var(--ink-3, #64748B);
  font-size: 14px;
  padding: 0 4px;
}
.form-input--time {
  flex: 1;
  min-width: 0;
  font-variant-numeric: tabular-nums;
}
.form-input--select {
  width: 100%;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'><path d='M3 5l3 3 3-3' stroke='%2364748B' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 28px;
}

.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--ink-3, #64748B);
  line-height: 1.5;
}

.form-error {
  margin: 0 24px 16px;
  padding: 10px 14px;
  background: #FEF2F2;
  border: 1px solid #FCA5A5;
  border-radius: 8px;
  font-size: 13px;
  color: #B91C1C;
}

.config-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  border-top: 1px solid #F1F5F9;
  background: #F8FAFC;
  flex-wrap: wrap;
}
.config-card__updated {
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
.config-card__actions { display: flex; gap: 10px; }

// ── Loading ─────────────────────────────────────────────────────────────────
.loading-block {
  margin-top: 24px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  color: var(--ink-3, #64748B);
}
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #E2E8F0;
  border-top-color: #3B6EF5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 720px) {
  .form-grid { grid-template-columns: 1fr; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
}
</style>
