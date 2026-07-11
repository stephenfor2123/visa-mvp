<template>
  <div class="transfer-h5">
    <header class="transfer-h5__head">
      <h1 class="transfer-h5__title">{{ t('transfer.h5_title') }}</h1>
    </header>

    <!-- Claiming -->
    <div v-if="phase === 'claiming'" class="transfer-h5__panel">
      <p class="transfer-h5__msg">{{ t('transfer.h5_connecting') }}</p>
    </div>

    <!-- Claim failed -->
    <div v-else-if="phase === 'failed'" class="transfer-h5__panel transfer-h5__panel--err">
      <p class="transfer-h5__msg transfer-h5__msg--err">
        {{ errorMessage }}
      </p>
    </div>

    <!-- 抢完了 — 已 claimed by another device -->
    <div v-else-if="phase === 'taken'" class="transfer-h5__panel transfer-h5__panel--err">
      <p class="transfer-h5__msg transfer-h5__msg--err">
        {{ t('transfer.h5_taken') }}
      </p>
    </div>

    <!-- Active upload -->
    <template v-else-if="phase === 'active'">
      <div class="transfer-h5__panel">
        <p class="transfer-h5__msg">
          {{ t('transfer.h5_subtitle') }}
        </p>
        <p class="transfer-h5__countdown">
          {{ t('transfer.expires_in') }} <strong>{{ countdownLabel }}</strong>
        </p>
      </div>

      <!-- File input: 直接 capture 走相机, accept 限常见图片/pdf -->
      <div class="transfer-h5__cam">
        <label class="transfer-h5__cam-btn">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
            <path d="M4 7h3l2-2h6l2 2h3v12H4z" stroke="currentColor" stroke-width="1.6" />
            <circle cx="12" cy="13" r="4" stroke="currentColor" stroke-width="1.6" />
          </svg>
          {{ t('transfer.h5_take_photo') }}
          <input
            ref="cameraInputEl"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            capture="environment"
            data-testid="transfer-h5-camera"
            @change="onCameraPick"
          />
        </label>
        <label class="transfer-h5__cam-btn transfer-h5__cam-btn--secondary">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6" />
            <circle cx="9" cy="11" r="1.6" fill="currentColor" />
            <path d="M21 17l-5-5-7 7" stroke="currentColor" stroke-width="1.6" />
          </svg>
          {{ t('transfer.h5_pick_file') }}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            data-testid="transfer-h5-pick"
            @change="onCameraPick"
          />
        </label>
      </div>

      <!-- 上传中/结果 -->
      <ul v-if="busyFiles.length || doneFiles.length" class="transfer-h5__list">
        <li v-for="f in busyFiles" :key="f.key" class="transfer-h5__item transfer-h5__item--busy">
          <span class="transfer-h5__fname">{{ f.name }}</span>
          <span class="transfer-h5__progress">{{ f.progress }}%</span>
        </li>
        <li v-for="f in doneFiles" :key="`done-${f.material_id || f.file_name}`" class="transfer-h5__item transfer-h5__item--done">
          <span class="transfer-h5__fname">{{ f.file_name }}</span>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.6" />
            <path d="M8 12.5l3 3 5-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </li>
      </ul>

      <button
        v-if="doneFiles.length > 0"
        type="button"
        class="transfer-h5__done-btn"
        data-testid="transfer-h5-done"
        @click="onDone"
      >
        {{ t('transfer.h5_done') }}
      </button>
    </template>

    <p class="transfer-h5__foot">
      {{ t('transfer.h5_foot') }}
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import {
  claimTransferSession,
  leaveTransferSession,
  uploadTransferFile,
} from '@/api/transfer'

const { t } = useI18n()
const route = useRoute()

const sid = String(route.query.sid || '')
const token = String(route.query.t || '')

const phase = ref('claiming')       // claiming | active | done | taken | failed
const errorMessage = ref('')
const expiresAt = ref(0)
const countdown = ref(0)

const busyFiles = ref([])
const doneFiles = ref([])

const cameraInputEl = ref(null)

const countdownLabel = computed(() => {
  const s = Math.max(0, Math.floor(countdown.value))
  return `${s}s`
})

let countdownHandle = null

function startCountdown() {
  countdownHandle = setInterval(() => {
    const now = Date.now() / 1000
    countdown.value = Math.max(0, expiresAt.value - now)
    if (countdown.value <= 0 && phase.value === 'active') {
      // session 已超时,但允许本地继续展示上传列表 — service 那边会拒
    }
  }, 250)
}

function stopCountdown() {
  if (countdownHandle) clearInterval(countdownHandle)
  countdownHandle = null
}

async function claim() {
  if (!sid || !token) {
    phase.value = 'failed'
    errorMessage.value = t('transfer.h5_invalid_qr')
    return
  }
  try {
    const r = await claimTransferSession(sid, token)
    expiresAt.value = Number(r.expires_at) || (Date.now() / 1000 + 120)
    countdown.value = Math.max(0, expiresAt.value - Date.now() / 1000)
    phase.value = 'active'
    startCountdown()
  } catch (e) {
    if (e && e.status === 409) {
      phase.value = 'taken'
    } else if (e && (e.status === 410 || e.status === 404)) {
      phase.value = 'failed'
      errorMessage.value = t('transfer.h5_session_expired')
    } else {
      phase.value = 'failed'
      errorMessage.value = t('transfer.h5_unknown_error')
    }
  }
}

function uid() {
  return Math.random().toString(36).slice(2, 10)
}

async function onCameraPick(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    // 直接弹 localStorage 风格的 toast 状态 (提示大于 10MB)
    busyFiles.value.push({
      key: uid(),
      name: `${file.name} (${t('transfer.h5_too_big')})`,
      progress: 0,
      error: true,
    })
    ev.target.value = ''
    return
  }
  const itemKey = uid()
  busyFiles.value.push({ key: itemKey, name: file.name, progress: 0, error: false })
  try {
    const result = await uploadTransferFile(sid, token, file, 'other')
    busyFiles.value = busyFiles.value.filter((f) => f.key !== itemKey)
    doneFiles.value.push({
      material_id: result.material_id,
      file_name: result.file_name || file.name,
    })
  } catch (e) {
    busyFiles.value = busyFiles.value.map((f) =>
      f.key === itemKey ? { ...f, progress: 'ERR', error: true } : f
    )
  } finally {
    ev.target.value = ''  // reset input so picking same file twice triggers change
  }
}

async function onDone() {
  phase.value = 'done'
  await leaveTransferSession(sid, token).catch(() => {})
}

onMounted(claim)
onBeforeUnmount(() => {
  stopCountdown()
  // 用户离开页面也通知服务端
  if (phase.value === 'active') {
    leaveTransferSession(sid, token).catch(() => {})
  }
})
</script>

<style scoped>
.transfer-h5 {
  min-height: 100dvh;
  background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.transfer-h5__head { padding-top: 12px; }
.transfer-h5__title {
  font-size: 22px;
  margin: 0;
  color: #0F172A;
  font-weight: 700;
}
.transfer-h5__panel {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.transfer-h5__panel--err {
  border: 1px solid #FCA5A5;
  background: #FEF2F2;
}
.transfer-h5__msg {
  margin: 0;
  color: #1F2937;
  font-size: 15px;
  text-align: center;
}
.transfer-h5__msg--err { color: #B91C1C; }
.transfer-h5__countdown {
  margin: 8px 0 0;
  text-align: center;
  font-size: 13px;
  color: #475569;
}
.transfer-h5__countdown strong { color: #2563EB; }
.transfer-h5__cam {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.transfer-h5__cam-btn {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 18px 12px;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: #1F2937;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.transfer-h5__cam-btn input[type=file] { display: none; }
.transfer-h5__cam-btn--secondary { color: #475569; }
.transfer-h5__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.transfer-h5__item {
  background: #fff;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}
.transfer-h5__item--busy { border: 1px solid #BFDBFE; color: #1D4ED8; }
.transfer-h5__item--done { border: 1px solid #BBF7D0; color: #047857; }
.transfer-h5__fname {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  margin-right: 8px;
}
.transfer-h5__progress { font-size: 12px; }
.transfer-h5__done-btn {
  margin-top: 4px;
  background: #2563EB;
  color: #fff;
  border: 0;
  border-radius: 12px;
  padding: 14px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.transfer-h5__foot {
  text-align: center;
  font-size: 12px;
  color: #94A3B8;
  margin-top: auto;
}
</style>
