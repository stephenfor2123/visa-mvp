<!--
  RpaSubmit.vue — W14 RPA 提交页面
  ================================
  流程: Materials.vue 校验通过后 -> RpaSubmit.vue
  负责: 显示 RPA 进度条 + 任务 ID + 异常处理 + 重试按钮
  所有文案使用 t() i18n
-->
<template>
  <div class="rpa-submit-page">
    <AppHeader scope="rpa-submit" />
    <main class="app-container app-page rpa-submit-shell">
      <!-- 顶部状态卡 -->
      <section class="rpa-card" data-testid="rpa-submit-card">
        <div class="rpa-card__icon">
          <span v-if="phase === 'done'">✅</span>
          <span v-else-if="phase === 'error'">❌</span>
          <span v-else>🤖</span>
        </div>
        <h1 class="rpa-card__title">{{ mainTitle }}</h1>
        <p class="rpa-card__subtitle">{{ mainSubtitle }}</p>

        <!-- 任务 ID -->
        <div v-if="taskId" class="rpa-task-id" data-testid="rpa-task-id">
          <span class="rpa-task-id__label">{{ t('rpa.task_id_label') }}</span>
          <code class="rpa-task-id__value">{{ taskId }}</code>
        </div>

        <!-- 进度条 (非错误状态) -->
        <div v-if="phase !== 'error'" class="rpa-progress" data-testid="rpa-progress">
          <div class="rpa-progress__bar">
            <div
              class="rpa-progress__fill"
              :style="{ width: progress + '%' }"
              :class="`rpa-progress__fill--${phase}`"
            ></div>
          </div>
          <div class="rpa-progress__meta">
            <span class="rpa-progress__pct">{{ progress }}%</span>
            <span class="rpa-progress__step">{{ t(stepLabelKey) }}</span>
          </div>
        </div>

        <!-- 步骤指示器 -->
        <div class="rpa-steps" data-testid="rpa-steps">
          <div
            v-for="(s, idx) in steps"
            :key="s.key"
            class="rpa-step"
            :class="{
              'rpa-step--done': stepIndex > idx,
              'rpa-step--active': stepIndex === idx,
              'rpa-step--pending': stepIndex < idx
            }"
          >
            <div class="rpa-step__dot">
              <span v-if="stepIndex > idx">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="rpa-step__label">{{ t(s.label) }}</span>
          </div>
        </div>

        <!-- 异常状态 -->
        <div v-if="phase === 'error'" class="rpa-error" data-testid="rpa-error">
          <div class="rpa-error__icon">⚠️</div>
          <h2 class="rpa-error__title">{{ t('rpa.error_title') }}</h2>
          <p class="rpa-error__msg">{{ errorMessage }}</p>
          <div class="rpa-error__actions">
            <AppButton ref="retryBtnRef" variant="primary" size="lg" :loading="submitting" data-testid="rpa-retry-btn">
              {{ t('common.retry') }}
            </AppButton>
            <AppButton variant="ghost" size="lg" @click="goHome" data-testid="rpa-home-btn">
              {{ t('rpa.back_home') }}
            </AppButton>
          </div>
        </div>

        <!-- 完成状态: 跳转按钮 -->
        <div v-if="phase === 'done'" class="rpa-done-actions" data-testid="rpa-done-actions">
          <AppButton ref="viewOrderBtnRef" variant="primary" size="lg" data-testid="rpa-view-order-btn">
            {{ t('rpa.view_order_detail') }}
          </AppButton>
          <AppButton variant="ghost" size="lg" @click="goHome" data-testid="rpa-home-btn">
            {{ t('nav.home') }}
          </AppButton>
        </div>
      </section>

      <!-- 底部说明 -->
      <p class="rpa-foot-note">
        {{ t('rpa.foot_note') }}
      </p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useToast } from '@/composables/useToast'
import { postRpaSubmit, getRpaStatus } from '@/api/rpa'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()

// ── Refs ─────────────────────────────────────────────────────────────────────
const taskId = ref('')
const status = ref('SUBMITTING')    // SUBMITTING | WAITING | DONE | FAILED
const phase = ref('accessing')      // accessing | filling | submitting | done | error
const stepLabelKey = ref('rpa.step_accessing')
const errorMessage = ref('')
const submitting = ref(false)
const orderNo = ref('')
// W19: backend RPA submit endpoint requires country_code + visa_type + passport_data
// (read from router query set by OrderNew, and passport from sessionStorage stash)
const countryCode = ref('')
const visaType = ref('tourism')

/**
 * Read passport data stashed by OrderNew in sessionStorage.
 * Falls back to {} (backend will reject with 422 if a real submission is attempted
 * with empty passport data; MOCK mode ignores it).
 */
function readPassportData(orderNoKey) {
  if (!orderNoKey) return {}
  try {
    const raw = sessionStorage.getItem(`rpa_passport_${orderNoKey}`)
    if (!raw) return {}
    // Clean up after read so it's not lingering
    sessionStorage.removeItem(`rpa_passport_${orderNoKey}`)
    return JSON.parse(raw) || {}
  } catch (e) {
    console.warn('[rpa] readPassportData failed:', e?.message)
    return {}
  }
}

// AppButton refs
const retryBtnRef = ref(null)
const viewOrderBtnRef = ref(null)

// ── Polling ──────────────────────────────────────────────────────────────────
let pollTimer = null
const POLL_INTERVAL = 3000  // 3s 轮询

async function pollStatus() {
  if (!taskId.value) return
  try {
    const data = await getRpaStatus(taskId.value)
    status.value = data.status
    phase.value = data.phase
    // W45 fix: the backend's `progress` field is a 0..1 float that doesn't
    // always align with the textual phase (eg. fake-progress animation can
    // leave progress=0.7 while phase is still 'accessing' / step 1/3).
    // Derive the bar fill from the phase index instead so the percentage
    // can never disagree with the visible step number: 1/3 ≤ 33%, 2/3 ≤ 66%,
    // 3/3 = 100%. Within each step we still display the backend's
    // fractional progress for some motion, but cap it to that step's max.
    stepLabelKey.value = data.step_label_key

    if (data.status === 'DONE') {
      clearInterval(pollTimer)
      toast.success(t('rpa.toast_done'))
    } else if (data.status === 'FAILED') {
      clearInterval(pollTimer)
      phase.value = 'error'
      errorMessage.value = data.error || t('rpa.error_unknown')
    }
  } catch (e) {
    console.warn('[rpa-submit] poll error:', e?.message)
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollStatus, POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ── Computed ─────────────────────────────────────────────────────────────────
const steps = [
  { key: 'accessing',  label: 'rpa.step_accessing'  },
  { key: 'filling',    label: 'rpa.step_filling'    },
  { key: 'submitting', label: 'rpa.step_submitting' }
]

const stepIndex = computed(() => {
  if (phase.value === 'done')    return 2
  if (phase.value === 'accessing')  return 0
  if (phase.value === 'filling')    return 1
  if (phase.value === 'submitting') return 2
  return 0
})

// W45 fix: derive the progress-bar fill from the step index so the visible
// percentage can never contradict the textual step ("Step 1/3" / "Step 2/3" /
// "Step 3/3"). Bounds:
//   - step 0 (1/3) → 0..33%
//   - step 1 (2/3) → 34..66%
//   - step 2 (3/3) → 67..99% (until the backend flips to DONE → 100%)
// The cap is 99 on the last step so the user keeps seeing motion until the
// "完成" toast and the step dots both switch to green.
const STEP_MAX = [33, 66, 99]
const progress = computed(() => {
  if (phase.value === 'done') return 100
  if (phase.value === 'error') return 0
  const idx = stepIndex.value
  return STEP_MAX[idx] ?? 0
})

const mainTitle = computed(() => {
  if (phase.value === 'done')  return t('rpa.title_done')
  if (phase.value === 'error') return t('rpa.title_error')
  return t('rpa.title_submitting')
})

const mainSubtitle = computed(() => {
  if (phase.value === 'done')  return t('rpa.subtitle_done')
  if (phase.value === 'error') return t('rpa.subtitle_error')
  return t('rpa.subtitle_submitting')
})

// ── Actions ──────────────────────────────────────────────────────────────────
async function doSubmit() {
  if (submitting.value) return
  submitting.value = true
  phase.value = 'accessing'
  // `progress` is now a computed derived from `phase` — setting it is a
  // no-op (Vue warns on writable-computed assignment) so we just rely on
  // the phase change to drive the bar to 0..33%.
  errorMessage.value = ''
  stepLabelKey.value = 'rpa.step_accessing'

  try {
    // W19: pass country_code + visa_type + passport_data (backend Pydantic schema)
    const passportData = readPassportData(orderNo.value)
    const data = await postRpaSubmit({
      orderNo: orderNo.value,
      countryCode: countryCode.value,
      visaType: visaType.value,
      passportData
    })
    taskId.value = data.task_id
    toast.info(t('rpa.toast_started'))
    startPolling()
  } catch (e) {
    phase.value = 'error'
    errorMessage.value = e?.message || t('rpa.error_unknown')
    toast.error(t('rpa.toast_failed'))
  } finally {
    submitting.value = false
  }
}

function goHome() {
  router.push({ name: 'Home' })
}

function goOrderDetail() {
  if (orderNo.value) {
    router.push({ name: 'OrderDetail', params: { orderNo: orderNo.value } })
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  orderNo.value = route.query.orderNo || route.params.orderNo || 'ORD_DEMO_001'
  // W19: read country_code + visa_type from query (set by OrderNew)
  countryCode.value = (route.query.countryCode || '').toString().toUpperCase()
  visaType.value = (route.query.visaType || 'tourism').toString()

  // 绑定 AppButton refs
  await nextTick()
  if (retryBtnRef.value) {
    retryBtnRef.value.setOnTrigger(() => doSubmit())
  }
  if (viewOrderBtnRef.value) {
    viewOrderBtnRef.value.setOnTrigger(() => goOrderDetail())
  }

  // 自动触发提交
  await doSubmit()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped lang="scss">
.rpa-submit-page { min-height: 100vh; background: #FFFFFF; }

.rpa-submit-shell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 48px;
  padding-bottom: 48px;
}

.rpa-card {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 16px;
  padding: 40px 36px;
  width: 100%;
  max-width: 560px;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0, 0, 0, .06);
}

.rpa-card__icon {
  font-size: 48px;
  margin-bottom: 16px;
  animation: float 2s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.rpa-card__title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink-1, #0F172A);
  margin: 0 0 8px;
}
.rpa-card__subtitle {
  font-size: 14px;
  color: var(--ink-3, #64748B);
  margin: 0 0 24px;
  line-height: 1.6;
}

.rpa-task-id {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #F1F5F9;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px;
  padding: 6px 12px;
  margin-bottom: 20px;
}
.rpa-task-id__label {
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
.rpa-task-id__value {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: var(--ink-1, #0F172A);
  background: transparent;
}

// ── Progress ─────────────────────────────────────────────────────────────────
.rpa-progress { margin-bottom: 28px; }
.rpa-progress__bar {
  height: 8px;
  background: #E2E8F0;
  border-radius: 999px;
  overflow: hidden;
}
.rpa-progress__fill {
  height: 100%;
  border-radius: 999px;
  transition: width .5s ease;
  background: linear-gradient(90deg, #3B6EF5, #6E59F0);
}
.rpa-progress__fill--done { background: linear-gradient(90deg, #22C55E, #16A34A); }
.rpa-progress__fill--error { background: linear-gradient(90deg, #EF4444, #DC2626); }

.rpa-progress__meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
}
.rpa-progress__pct { font-weight: 600; color: var(--ink-1, #0F172A); }
.rpa-progress__step { color: var(--ink-3, #64748B); }

// ── Steps ─────────────────────────────────────────────────────────────────────
.rpa-steps {
  display: flex;
  justify-content: center;
  gap: 0;
  margin-bottom: 24px;
}
.rpa-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  flex: 1;
  & + .rpa-step::before {
    content: '';
    position: absolute;
    top: 14px;
    left: -50%;
    width: 100%;
    height: 2px;
    background: #E2E8F0;
    z-index: 0;
  }
}
.rpa-step--done + .rpa-step::before,
.rpa-step--done::before { background: #22C55E; }

.rpa-step__dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #E2E8F0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3, #64748B);
  z-index: 1;
  transition: all .3s;
}
.rpa-step--done .rpa-step__dot {
  border-color: #22C55E;
  background: #22C55E;
  color: #fff;
}
.rpa-step--active .rpa-step__dot {
  border-color: #3B6EF5;
  background: #3B6EF5;
  color: #fff;
  animation: pulse-dot 1.5s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59,110,245,.4); }
  50% { box-shadow: 0 0 0 8px rgba(59,110,245,0); }
}

.rpa-step__label { font-size: 12px; color: var(--ink-3, #64748B); }
.rpa-step--done .rpa-step__label  { color: #22C55E; font-weight: 500; }
.rpa-step--active .rpa-step__label { color: #3B6EF5; font-weight: 600; }

// ── Error ─────────────────────────────────────────────────────────────────────
.rpa-error {
  margin-top: 8px;
  .rpa-error__icon { font-size: 40px; margin-bottom: 12px; }
  .rpa-error__title { font-size: 18px; font-weight: 600; color: #B91C1C; margin: 0 0 8px; }
  .rpa-error__msg {
    font-size: 14px;
    color: #7F1D1D;
    background: #FEE2E2;
    border: 1px solid #FECACA;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 24px;
    line-height: 1.6;
  }
  .rpa-error__actions { display: flex; gap: 12px; justify-content: center; }
}

// ── Done ──────────────────────────────────────────────────────────────────────
.rpa-done-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 8px;
}

// ── Footer ────────────────────────────────────────────────────────────────────
.rpa-foot-note {
  margin-top: 24px;
  font-size: 12px;
  color: var(--ink-3, #64748B);
  text-align: center;
  max-width: 480px;
  line-height: 1.6;
}

@media (max-width: 600px) {
  .rpa-card { padding: 28px 20px; }
  .rpa-steps { gap: 0; }
}
</style>