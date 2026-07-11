<template>
  <div class="qr-upload-modal" role="dialog" aria-modal="true" :aria-label="t('transfer.modal_title')">
    <div class="qr-upload-modal__card">
      <header class="qr-upload-modal__head">
        <h2 class="qr-upload-modal__title">{{ t('transfer.modal_title') }}</h2>
        <button
          type="button"
          class="qr-upload-modal__close"
          :aria-label="t('common.close')"
          data-testid="qr-upload-close"
          @click="onClose"
        >
          ×
        </button>
      </header>

      <div v-if="loading" class="qr-upload-modal__loading">
        {{ t('transfer.preparing') }}
      </div>

      <template v-else-if="sessionSid && qrPayload">
        <!-- QR + 倒计时 -->
        <div class="qr-upload-modal__qr">
          <div ref="qrCanvasEl" class="qr-upload-modal__qr-img" data-testid="qr-upload-qr"></div>
          <div class="qr-upload-modal__countdown">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7" />
              <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
            </svg>
            {{ t('transfer.expires_in') }} <strong>{{ countdownLabel }}</strong>
          </div>
        </div>

        <!-- 状态分阶段展示 -->
        <div class="qr-upload-modal__status" :data-testid="`qr-upload-status-${phase}`">
          <template v-if="phase === 'waiting'">
            <p class="qr-upload-modal__hint">
              {{ t('transfer.scan_hint') }}
            </p>
            <p class="qr-upload-modal__hint qr-upload-modal__hint--small">
              {{ t('transfer.scan_hint_sub') }}
            </p>
          </template>

          <template v-else-if="phase === 'claimed'">
            <p class="qr-upload-modal__hint">
              <strong>{{ t('transfer.phone_connected') }}</strong>
            </p>
            <p class="qr-upload-modal__hint qr-upload-modal__hint--small">
              {{ t('transfer.phone_waiting') }}
            </p>
          </template>

          <template v-else-if="phase === 'received'">
            <p class="qr-upload-modal__hint">
              <strong>{{ t('transfer.received_count', { n: receivedFiles.length }) }}</strong>
            </p>
            <ul class="qr-upload-modal__files">
              <li
                v-for="(f, i) in receivedFiles"
                :key="`${f.material_id || f.file_name || i}`"
                class="qr-upload-modal__file"
              >
                <img
                  v-if="f.thumbnail_url"
                  :src="f.thumbnail_url"
                  :alt="f.file_name"
                  class="qr-upload-modal__thumb"
                />
                <span class="qr-upload-modal__fname">{{ f.file_name }}</span>
              </li>
            </ul>
          </template>

          <template v-else-if="phase === 'closed'">
            <p class="qr-upload-modal__hint">
              {{ closeReasonText }}
            </p>
          </template>
        </div>

        <!-- 操作 -->
        <div class="qr-upload-modal__actions">
          <button
            v-if="phase !== 'closed' && receivedFiles.length > 0"
            type="button"
            class="qr-upload-modal__btn qr-upload-modal__btn--ghost"
            data-testid="qr-upload-clear"
            @click="onClear"
          >
            {{ t('transfer.clear_list') }}
          </button>
          <button
            type="button"
            class="qr-upload-modal__btn qr-upload-modal__btn--primary"
            data-testid="qr-upload-done"
            @click="onClose"
          >
            {{ t('transfer.done') }}
          </button>
        </div>
      </template>

      <div v-else class="qr-upload-modal__error" data-testid="qr-upload-error">
        <div>{{ errorMessage }}</div>
        <button
          v-if="errorCode === 'auth'"
          class="qr-upload-modal__retry-btn"
          data-testid="qr-upload-go-login"
          @click="goLogin"
        >
          {{ t('transfer.go_login') }}
        </button>
        <button
          v-else
          class="qr-upload-modal__retry-btn"
          data-testid="qr-upload-retry"
          @click="start"
        >
          {{ t('transfer.retry') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'
import {
  closeTransferSession,
  createTransferSession,
  openTransferEvents,
} from '@/api/transfer'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  open: { type: Boolean, required: true },
})
const emit = defineEmits(['update:open', 'received'])
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

// 错误态: 区分未登录(3001) vs 其它 — 影响弹窗里给"去登录"还是"重试"
const errorMessage = ref('')
const errorCode = ref('') // '' | 'auth' | 'other'
function goLogin() {
  // 关掉弹窗,带 redirect 回 wizard 当前页
  emit('update:open', false)
  router.push({ name: 'Login', query: { redirect: router.currentRoute.value.fullPath } })
}

const { t, locale } = useI18n()

// session
const loading = ref(false)
const sessionSid = ref('')
const qrPayload = ref('')
const expiresAt = ref(0)
const phase = ref('waiting') // waiting | claimed | received | closed | error
const closeReasonText = ref('')
const receivedFiles = ref([])
const countdown = ref(0)

let tickHandle = null
let countdownHandle = null
let eventSource = null

const countdownLabel = computed(() => {
  const s = Math.max(0, Math.floor(countdown.value))
  const m = Math.floor(s / 60)
  const r = s % 60
  return m > 0 ? `${m}:${String(r).padStart(2, '0')}` : `${r}s`
})

const qrCanvasEl = ref(null)

async function drawQr() {
  if (!qrCanvasEl.value || !qrPayload.value) return
  await QRCode.toCanvas(qrCanvasEl.value, qrPayload.value, {
    width: 224,
    margin: 1,
    errorCorrectionLevel: 'M',
    color: { dark: '#1F2937', light: '#FFFFFF' },
  })
}

async function start() {
  if (!props.open) return
  loading.value = true
  errorMessage.value = ''
  errorCode.value = ''
  cleanup()
  try {
    const r = await createTransferSession()
    sessionSid.value = r.sid
    qrPayload.value = r.qr_payload
    expiresAt.value = Number(r.expires_at) || 0
    countdown.value = Math.max(0, expiresAt.value - Date.now() / 1000)
    phase.value = 'waiting'
    receivedFiles.value = []
    loading.value = false
    await drawQr()
    subscribeEvents()
    startCountdown()
  } catch (e) {
    loading.value = false
    sessionSid.value = ''
    // axios 错误对象结构 / http.js wrap 后 .code 是业务码
    const code = e?.code || e?.response?.data?.code || ''
    if (code === '3001' || /not\s*found/i.test(e?.response?.data?.message || '')) {
      // 后端 BizException 3001 = user not found / 未登录或 token 失效
      errorCode.value = 'auth'
      errorMessage.value = t('transfer.err_unauthorized')
    } else {
      errorCode.value = 'other'
      errorMessage.value = t('transfer.create_failed')
    }
    phase.value = 'error'
  }
}

function subscribeEvents() {
  if (!sessionSid.value) return
  const es = openTransferEvents(sessionSid.value)
  eventSource = es

  es.addEventListener('claimed', () => {
    phase.value = 'claimed'
  })

  es.addEventListener('file_received', (ev) => {
    let payload = null
    try { payload = JSON.parse(ev.data) } catch (_) { payload = null }
    if (!payload) return
    // 用 _emitted 标没收到 (server 端已经控制只发 1 次 — PC 这边按时间顺序追加即可)
    receivedFiles.value = [...receivedFiles.value, payload]
    phase.value = 'received'
    emit('received', payload)
  })

  es.addEventListener('closed', (ev) => {
    let payload = null
    try { payload = JSON.parse(ev.data) } catch (_) { payload = null }
    closeReasonText.value = payload?.reason ? t(`transfer.close_reason_${payload.reason}`) : t('transfer.close_done')
    phase.value = 'closed'
  })

  es.onerror = () => {
    // EventSource 在连接断时会自动重连 — 不动 phase,留着让 server 那侧超时自然走 closed
  }
}

function startCountdown() {
  countdownHandle = setInterval(() => {
    const now = Date.now() / 1000
    countdown.value = Math.max(0, expiresAt.value - now)
    if (countdown.value <= 0 && phase.value !== 'closed') {
      // local timeout — service-side will also close via expires check; UI 兜底切到 closed
      closeReasonText.value = t('transfer.close_reason_expired')
      phase.value = 'closed'
      stopCountdown()
    }
  }, 250)
}

function stopCountdown() {
  if (countdownHandle) clearInterval(countdownHandle)
  countdownHandle = null
}

function cleanup() {
  if (tickHandle) clearTimeout(tickHandle)
  tickHandle = null
  stopCountdown()
  if (eventSource) {
    try { eventSource.close() } catch (_) {}
    eventSource = null
  }
}

function onClose() {
  if (sessionSid.value && phase.value !== 'closed') {
    closeTransferSession(sessionSid.value)
  }
  cleanup()
  const out = receivedFiles.value
  receivedFiles.value = []
  sessionSid.value = ''
  qrPayload.value = ''
  phase.value = 'waiting'
  emit('update:open', false)
  if (out.length) emit('received-end', out) // 通知父页面
}

function onClear() {
  receivedFiles.value = []
  if (phase.value === 'received') phase.value = 'claimed'
}

watch(() => props.open, (v) => {
  if (v) start()
  else cleanup()
})

onMounted(() => { if (props.open) start() })
onBeforeUnmount(cleanup)
</script>

<style scoped>
.qr-upload-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}
.qr-upload-modal__card {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 16px;
  padding: 20px 20px 16px;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.qr-upload-modal__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.qr-upload-modal__title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.qr-upload-modal__close {
  border: 0;
  background: transparent;
  font-size: 24px;
  line-height: 1;
  color: #64748B;
  cursor: pointer;
}
.qr-upload-modal__loading,
.qr-upload-modal__error {
  text-align: center;
  color: #64748B;
  padding: 32px 0;
}
.qr-upload-modal__qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.qr-upload-modal__qr-img {
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 8px;
  background: #fff;
}
.qr-upload-modal__qr-img canvas {
  display: block;
}
.qr-upload-modal__countdown {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #475569;
}
.qr-upload-modal__countdown strong {
  color: #2563EB;
  font-weight: 600;
}
.qr-upload-modal__status {
  border-top: 1px dashed #E2E8F0;
  padding-top: 12px;
}
.qr-upload-modal__hint {
  font-size: 14px;
  color: #1F2937;
  margin: 0 0 4px;
  text-align: center;
}
.qr-upload-modal__hint--small {
  font-size: 12px;
  color: #64748B;
}
.qr-upload-modal__files {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 8px;
  max-height: 120px;
  overflow-y: auto;
}
.qr-upload-modal__file {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #475569;
}
.qr-upload-modal__thumb {
  width: 56px;
  height: 56px;
  border-radius: 6px;
  object-fit: cover;
  background: #F1F5F9;
}
.qr-upload-modal__fname {
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}
.qr-upload-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid #F1F5F9;
  padding-top: 12px;
}
.qr-upload-modal__btn {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #CBD5E1;
  background: #fff;
  color: #475569;
}
.qr-upload-modal__btn--primary {
  background: #2563EB;
  color: #fff;
  border-color: #2563EB;
}
</style>
