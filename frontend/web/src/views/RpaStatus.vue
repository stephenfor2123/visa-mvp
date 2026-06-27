<!--
  RpaStatus.vue — W14 RPA 状态查询页
  ================================
  功能: 输入订单号或任务 ID 查询 RPA 状态
  实时刷新按钮 (30s polling)
  所有文案使用 t() i18n
-->
<template>
  <div class="rpa-status-page">
    <AppHeader scope="rpa-status" />
    <main class="app-container app-page rpa-status-shell">
      <h1 class="page-title">{{ t('rpa.status_page_title') }}</h1>
      <p class="page-sub">{{ t('rpa.status_page_subtitle') }}</p>

      <!-- 查询表单 -->
      <section class="query-card" data-testid="rpa-query-form">
        <div class="query-row">
          <AppInput
            v-model="queryInput"
            :placeholder="t('rpa.query_placeholder')"
            class="query-input"
            data-testid="rpa-query-input"
          />
          <AppButton ref="searchBtnRef" variant="primary" size="md" :loading="searching" data-testid="rpa-search-btn">
            {{ t('rpa.search_btn') }}
          </AppButton>
        </div>
        <p class="query-hint">{{ t('rpa.query_hint') }}</p>
      </section>

      <!-- Loading -->
      <div v-if="searching && !taskData" class="state-block" data-testid="rpa-status-loading">
        <span class="spinner"></span> {{ t('common.loading') }}
      </div>

      <!-- 错误 -->
      <div v-if="searchError" class="state-block state-block--err" data-testid="rpa-status-error">
        <p>❌ {{ searchError }}</p>
        <AppButton variant="outline" size="md" @click="clearError">{{ t('common.close') }}</AppButton>
      </div>

      <!-- 结果 -->
      <template v-if="taskData && !searching">
        <section class="result-card" data-testid="rpa-status-result">
          <!-- 状态 badge -->
          <div class="result-header">
            <span
              class="status-badge"
              :class="`status-badge--${taskData.status.toLowerCase()}`"
              data-testid="rpa-status-badge"
            >
              {{ statusLabel(taskData.status) }}
            </span>
            <span class="result-order-no">{{ t('rpa.order_no_label') }}: {{ taskData.order_no }}</span>
          </div>

          <!-- 任务 ID -->
          <div class="result-row">
            <span class="result-label">{{ t('rpa.task_id_label') }}</span>
            <code class="result-value">{{ taskData.task_id }}</code>
          </div>

          <!-- 当前步骤 -->
          <div class="result-row">
            <span class="result-label">{{ t('rpa.current_step_label') }}</span>
            <span class="result-value result-value--highlight">{{ t(taskData.step_label_key) }}</span>
          </div>

          <!-- 提交时间 -->
          <div v-if="taskData.created_at" class="result-row">
            <span class="result-label">{{ t('rpa.submit_time_label') }}</span>
            <span class="result-value">{{ formatDateTime(taskData.created_at) }}</span>
          </div>

          <!-- 完成时间 -->
          <div v-if="taskData.completed_at" class="result-row">
            <span class="result-label">{{ t('rpa.completed_time_label') }}</span>
            <span class="result-value">{{ formatDateTime(taskData.completed_at) }}</span>
          </div>

          <!-- 进度条 -->
          <div class="result-progress" data-testid="rpa-status-progress">
            <div class="result-progress__bar">
              <div
                class="result-progress__fill"
                :style="{ width: taskData.progress + '%' }"
                :class="`result-progress__fill--${taskData.phase}`"
              ></div>
            </div>
            <span class="result-progress__pct">{{ taskData.progress }}%</span>
          </div>

          <!-- 异常信息 -->
          <div v-if="taskData.error" class="result-error" data-testid="rpa-status-error-detail">
            <span class="result-error__icon">⚠️</span>
            <span>{{ taskData.error }}</span>
          </div>
        </section>

        <!-- 操作按钮 -->
        <div class="result-actions" data-testid="rpa-status-actions">
          <AppButton ref="refreshBtnRef" variant="outline" size="md" :loading="searching" data-testid="rpa-refresh-btn">
            🔄 {{ t('rpa.refresh_btn') }}
          </AppButton>
          <span class="polling-hint">{{ t('rpa.polling_hint', { sec: countdownSec }) }}</span>
          <AppButton variant="ghost" size="md" @click="toggleAutoRefresh">
            {{ autoRefresh ? t('rpa.stop_auto_refresh') : t('rpa.start_auto_refresh') }}
          </AppButton>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-if="!taskData && !searching && !searchError" class="state-empty" data-testid="rpa-status-empty">
        <div class="state-empty__icon">🔍</div>
        <p>{{ t('rpa.empty_result') }}</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppButton from '@/components/AppButton.vue'
import AppInput from '@/components/AppInput.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useToast } from '@/composables/useToast'
import { getRpaStatus } from '@/api/rpa'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()

// ── Refs ─────────────────────────────────────────────────────────────────────
const queryInput = ref('')
const taskData = ref(null)
const searching = ref(false)
const searchError = ref('')
const autoRefresh = ref(false)
const countdownSec = ref(30)

// AppButton refs
const searchBtnRef = ref(null)
const refreshBtnRef = ref(null)

// ── Timers ───────────────────────────────────────────────────────────────────
let autoRefreshTimer = null
let countdownTimer = null

function startAutoRefresh() {
  stopAutoRefresh()
  autoRefresh.value = true
  countdownSec.value = 30

  countdownTimer = setInterval(() => {
    countdownSec.value -= 1
    if (countdownSec.value <= 0) countdownSec.value = 30
  }, 1000)

  autoRefreshTimer = setInterval(async () => {
    if (taskData.value) {
      await doSearch(false)
      countdownSec.value = 30
    }
  }, 30000)
}

function stopAutoRefresh() {
  autoRefresh.value = false
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null }
  if (countdownTimer)   { clearInterval(countdownTimer);   countdownTimer = null }
}

function toggleAutoRefresh() {
  if (autoRefresh.value) {
    stopAutoRefresh()
    toast.info(t('rpa.toast_refresh_stopped'))
  } else {
    startAutoRefresh()
    toast.info(t('rpa.toast_refresh_started'))
  }
}

// ── Search ───────────────────────────────────────────────────────────────────
async function doSearch(showLoading = true) {
  const q = queryInput.value.trim()
  if (!q) {
    searchError.value = t('rpa.err_query_required')
    return
  }

  if (showLoading) searching.value = true
  searchError.value = ''

  try {
    // 支持 orderNo 或 taskId 查询: taskId 以 rpa_ 开头
    const data = await getRpaStatus(q)
    taskData.value = data
  } catch (e) {
    taskData.value = null
    if (e?.code === 'TASK_NOT_FOUND') {
      searchError.value = t('rpa.err_not_found')
    } else {
      searchError.value = e?.message || t('rpa.err_unknown')
    }
  } finally {
    if (showLoading) searching.value = false
  }
}

function clearError() {
  searchError.value = ''
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function statusLabel(status) {
  const map = {
    SUBMITTING: t('rpa.status_submitting'),
    WAITING:    t('rpa.status_waiting'),
    DONE:       t('rpa.status_done'),
    FAILED:     t('rpa.status_failed')
  }
  return map[status] || status
}

function formatDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString()
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  if (searchBtnRef.value) {
    searchBtnRef.value.setOnTrigger(() => doSearch())
  }
  if (refreshBtnRef.value) {
    refreshBtnRef.value.setOnTrigger(() => doSearch(false))
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped lang="scss">
.rpa-status-page { min-height: 100vh; background: var(--bg, #FAFBFC); }

.rpa-status-shell {
  max-width: 640px;
  padding-top: 40px;
}

.page-title { font-size: 28px; font-weight: 600; margin: 0 0 6px; color: var(--ink, #1A1D29); }
.page-sub { color: var(--ink-2, #5A5F6D); margin: 0 0 24px; font-size: 14px; }

.query-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}
.query-row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.query-input { flex: 1; }
.query-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-3, #64748B);
}

.state-block {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  color: var(--ink-3, #64748B);
  margin-bottom: 16px;
}
.state-block--err {
  border-color: #FECACA;
  background: #FEF2F2;
  color: #B91C1C;
}

.state-empty {
  text-align: center;
  padding: 48px;
  .state-empty__icon { font-size: 48px; margin-bottom: 12px; }
  p { color: var(--ink-3, #64748B); font-size: 14px; }
}

.result-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 16px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.result-order-no { font-size: 13px; color: var(--ink-3, #64748B); margin-left: auto; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.status-badge--submitting { background: #DBEAFE; color: #1E40AF; }
.status-badge--waiting    { background: #FEF3C7; color: #B45309; }
.status-badge--done       { background: #DCFCE7; color: #166534; }
.status-badge--failed     { background: #FEE2E2; color: #B91C1C; }

.result-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #F1F5F9;
  &:last-of-type { border-bottom: none; }
}
.result-label { font-size: 13px; color: var(--ink-3, #64748B); min-width: 120px; }
.result-value { font-size: 14px; color: var(--ink-1, #0F172A); }
.result-value--highlight { font-weight: 600; color: #3B6EF5; }

.result-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
.result-progress__bar {
  flex: 1;
  height: 8px;
  background: #E2E8F0;
  border-radius: 999px;
  overflow: hidden;
}
.result-progress__fill {
  height: 100%;
  border-radius: 999px;
  transition: width .5s ease;
  background: linear-gradient(90deg, #3B6EF5, #6E59F0);
}
.result-progress__fill--done    { background: linear-gradient(90deg, #22C55E, #16A34A); }
.result-progress__fill--error   { background: linear-gradient(90deg, #EF4444, #DC2626); }
.result-progress__pct { font-size: 13px; font-weight: 600; color: var(--ink-1, #0F172A); min-width: 36px; }

.result-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: 8px;
  font-size: 14px;
  color: #B91C1C;
  line-height: 1.5;
  .result-error__icon { font-size: 16px; }
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.polling-hint {
  font-size: 12px;
  color: var(--ink-3, #64748B);
  flex: 1;
}

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: spin .7s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 600px) {
  .rpa-status-shell { padding: 16px; }
  .query-row { flex-direction: column; }
}
</style>