<!-- PassportUploadModal.vue — 3 种上传方式(拍照/文件/扫码) + OCR → emit uploaded -->
<template>
  <Transition name="fade">
    <div v-if="open" class="pum-overlay" @click.self="close">
      <div class="pum-modal">
        <button class="pum-modal__close" @click="close" data-testid="pum-close">×</button>

        <header class="pum-header">
          <h2 class="pum-header__title">{{ t('pum.title', 'Upload Passport Front Page') }}</h2>
          <p class="pum-header__sub">{{ t('pum.sub', 'AES-256 encryption · Auto-extract info via OCR') }}</p>
        </header>

        <!-- 阶段:选择上传方式 -->
        <div v-if="stage === 'choose'" class="pum-modes">
          <button class="pum-mode" data-testid="pum-mode-camera" @click="startCamera">
            <span class="pum-mode__icon">📷</span>
            <span class="pum-mode__label">{{ t('pum.camera', 'Take a photo') }}</span>
            <span class="pum-mode__hint">{{ t('pum.camera_hint', 'Use your computer camera') }}</span>
          </button>

          <button class="pum-mode" data-testid="pum-mode-file" @click="triggerFile">
            <span class="pum-mode__icon">📁</span>
            <span class="pum-mode__label">{{ t('pum.file', 'Select file') }}</span>
            <span class="pum-mode__hint">{{ t('pum.file_hint', 'JPG / PNG / WebP / PDF · Max 10MB') }}</span>
          </button>

          <button class="pum-mode" data-testid="pum-mode-mobile" @click="startMobile">
            <span class="pum-mode__icon">📱</span>
            <span class="pum-mode__label">{{ t('pum.mobile', 'Upload from device') }}</span>
            <span class="pum-mode__hint">{{ t('pum.mobile_hint', 'Scan a QR code with your phone') }}</span>
          </button>
        </div>

        <!-- 阶段:摄像头预览 + 拍 -->
        <div v-else-if="stage === 'camera'" class="pum-camera">
          <div class="pum-camera__viewport">
            <video ref="videoEl" class="pum-camera__video" autoplay muted playsinline />
            <div class="pum-camera__overlay" />
            <div v-if="countdown" class="pum-camera__countdown">{{ countdown }}</div>
          </div>
          <div class="pum-camera__actions">
            <button class="pum-btn pum-btn--ghost" @click="cancelCamera">
              {{ t('common.cancel', 'Cancel') }}
            </button>
            <button class="pum-btn pum-btn--primary" @click="capture" data-testid="pum-snap">
              {{ t('pum.snap', 'Capture now') }}
            </button>
          </div>
        </div>

        <!-- 阶段:扫码 -->
        <div v-else-if="stage === 'mobile'" class="pum-mobile">
          <p class="pum-mobile__hint">
            {{ t('pum.scan_hint', 'Scan this QR code with your phone camera to upload the passport directly') }}
          </p>
          <div class="pum-mobile__qr">
            <!-- QR 由 qrcode 库或纯 SVG 生成,这里用占位 SVG -->
            <div class="pum-mobile__qr-img">
              <svg viewBox="0 0 100 100" width="180" height="180">
                <rect width="100" height="100" fill="#fff" />
                <!-- 伪 QR 码: 定位符 + 噪声格 -->
                <rect x="6" y="6" width="22" height="22" fill="#0F172A" />
                <rect x="11" y="11" width="12" height="12" fill="#fff" />
                <rect x="15" y="15" width="4" height="4" fill="#0F172A" />
                <rect x="72" y="6" width="22" height="22" fill="#0F172A" />
                <rect x="77" y="11" width="12" height="12" fill="#fff" />
                <rect x="81" y="15" width="4" height="4" fill="#0F172A" />
                <rect x="6" y="72" width="22" height="22" fill="#0F172A" />
                <rect x="11" y="77" width="12" height="12" fill="#fff" />
                <rect x="15" y="81" width="4" height="4" fill="#0F172A" />
                <!-- data area: 随机散点 -->
                <g v-for="(d, i) in qrDots" :key="i">
                  <rect :x="d.x" :y="d.y" width="3" height="3" fill="#0F172A" />
                </g>
              </svg>
            </div>
            <div class="pum-mobile__url">
              {{ mobileUrl }}
            </div>
          </div>
          <div class="pum-mobile__status" :class="{ 'is-arrived': mobileArrived }">
            <span class="pum-mobile__dot" />
            <span v-if="!mobileArrived">{{ t('pum.waiting', 'Waiting for upload…') }}</span>
            <span v-else>{{ t('pum.arrived', '✓ File received from your phone') }}</span>
          </div>
          <button class="pum-btn pum-btn--ghost" @click="cancelMobile">
            {{ t('common.cancel', 'Cancel') }}
          </button>
        </div>

        <!-- 阶段:OCR 处理中 -->
        <div v-else-if="stage === 'ocr'" class="pum-ocr">
          <div class="pum-ocr__spinner" />
          <h3 class="pum-ocr__title">{{ t('pum.ocr_running', 'Scanning your passport…') }}</h3>
          <p class="pum-ocr__hint">{{ t('pum.ocr_hint', 'Extracting name, number, nationality, dates') }}</p>
        </div>

        <!-- 阶段:错误(非护照图) -->
        <div v-else-if="stage === 'error'" class="pum-err">
          <div class="pum-err__icon">⚠️</div>
          <h3 class="pum-err__title">{{ t('pum.err_title', 'We couldn\'t read this as a passport') }}</h3>
          <p class="pum-err__msg">{{ errMsg }}</p>
          <div class="pum-err__actions">
            <button class="pum-btn pum-btn--primary" @click="stage = 'choose'">
              {{ t('pum.try_again', 'Try again') }}
            </button>
          </div>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          style="display:none"
          @change="onFilePicked"
        />
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import { useMaterialsProgress } from '@/composables/useMaterialsProgress'

const props = defineProps({
  open: { type: Boolean, default: false },
  slotKey: { type: String, default: 'passport' },
})
const emit = defineEmits(['close', 'uploaded'])

const { t } = useI18n()
const { setSlot, setPendingPassportReview } = useMaterialsProgress()

const stage = ref('choose')     // choose | camera | mobile | ocr | error
const videoEl = ref(null)
const fileInput = ref(null)
const countdown = ref(0)
const errMsg = ref('')
const mobileUrl = ref('')
const mobileArrived = ref(false)
let mediaStream = null
let countdownTimer = null
let mobilePollTimer = null

// 伪 QR 散点(纯静态)
const qrDots = Array.from({ length: 80 }, () => ({
  x: 32 + Math.floor(Math.random() * 36),
  y: 32 + Math.floor(Math.random() * 36),
}))

watch(() => props.open, (v) => {
  if (v) {
    stage.value = 'choose'
    errMsg.value = ''
    mobileArrived.value = false
    mobileUrl.value = ''
  } else {
    teardown()
  }
})

function close() {
  teardown()
  emit('close')
}

// ====== Camera ======
async function startCamera() {
  errMsg.value = ''
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: 1280, height: 720 },
      audio: false,
    })
    stage.value = 'camera'
    setTimeout(() => {
      if (videoEl.value) videoEl.value.srcObject = mediaStream
      startCountdown()
    }, 100)
  } catch (e) {
    errMsg.value = t('pum.err_cam', 'Camera not available')
    stage.value = 'error'
  }
}

function startCountdown() {
  countdown.value = 3
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      countdownTimer = null
      capture()
    }
  }, 700)
}

function capture() {
  if (!videoEl.value) return
  const v = videoEl.value
  const canvas = document.createElement('canvas')
  canvas.width = v.videoWidth || 1280
  canvas.height = v.videoHeight || 720
  const ctx = canvas.getContext('2d')
  ctx.drawImage(v, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => {
    teardownCamera()
    if (blob) runOCR(blob, 'passport_camera.jpg')
  }, 'image/jpeg', 0.9)
}

function cancelCamera() {
  teardownCamera()
  stage.value = 'choose'
}

// ====== File ======
function triggerFile() {
  fileInput.value?.click()
}

function onFilePicked(e) {
  const f = e.target.files?.[0]
  if (!f) return
  e.target.value = ''
  runOCR(f, f.name)
}

// ====== Mobile / QR ======
function startMobile() {
  // 模拟:生成一个 demo URL + 启动轮询"等待上传"
  const token = Math.random().toString(36).slice(2, 10)
  mobileUrl.value = `https://htex.app/u/${token}`
  mobileArrived.value = false
  stage.value = 'mobile'
  // 真实场景:这里应该用 WebSocket/轮询 token 状态
  // V2 demo: 8 秒后模拟"已收到文件" → 触发 mock OCR
  mobilePollTimer = setTimeout(() => {
    mobileArrived.value = true
    setTimeout(() => {
      // mock 一张合成的"护照"图片
      runOCR(makeMockPassportFile(), 'phone_passport.jpg')
    }, 800)
  }, 8000)
}

function cancelMobile() {
  if (mobilePollTimer) {
    clearTimeout(mobilePollTimer)
    mobilePollTimer = null
  }
  mobileArrived.value = false
  stage.value = 'choose'
}

// 合成一个简单的 mock 护照图(纯文本 + 边框)用于 demo
function makeMockPassportFile() {
  const canvas = document.createElement('canvas')
  canvas.width = 600; canvas.height = 380
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#F5EFE0'
  ctx.fillRect(0, 0, 600, 380)
  ctx.strokeStyle = '#0F172A'
  ctx.lineWidth = 2
  ctx.strokeRect(10, 10, 580, 360)
  ctx.fillStyle = '#0F172A'
  ctx.font = 'bold 18px sans-serif'
  ctx.fillText('PASSPORT', 30, 50)
  ctx.font = '14px sans-serif'
  ctx.fillText('CHINA', 30, 80)
  ctx.font = '12px monospace'
  const lines = [
    'Surname: ZHANG',
    'Given Name: WEI',
    'Sex: M',
    'Nationality: CHINESE',
    'Date of Birth: 15 MAY 1990',
    'Place of Birth: BEIJING',
    'Date of Issue: 12 MAR 2019',
    'Date of Expiry: 11 MAR 2029',
    'Passport No: E12345678',
  ]
  lines.forEach((l, i) => ctx.fillText(l, 30, 110 + i * 22))
  return new Promise((resolve) => {
    canvas.toBlob((b) => resolve(new File([b], 'phone_passport.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.9)
  })
}

// ====== OCR ======
async function runOCR(file, filename) {
  stage.value = 'ocr'
  errMsg.value = ''
  const form = new FormData()
  form.append('file', file, filename)
  form.append('lang', 'en')
  try {
    const resp = await http.post('/v2/ocr/recognize', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    const fields = resp?.data?.fields || {}
    const items = resp?.data?.items || []
    // 简单启发:如果一个 item 都没有 + 没有 passport_no 字段,标记为非护照
    if (!fields.passport_no && items.length < 2) {
      errMsg.value = t('pum.err_no_passport', 'Upload the front page of your passport as shown below. This page features your photograph, passport number and other personal details.')
      stage.value = 'error'
      return
    }
    // 成功:把 OCR 结果暂存 + 通知父组件
    const fileUrl = URL.createObjectURL(file)
    setSlot(props.slotKey, { collected: true, fileUrl, ocrResult: fields, error: null })
    setPendingPassportReview(fields, fileUrl)
    emit('uploaded', { slotKey: props.slotKey, fileUrl, ocrResult: fields })
  } catch (e) {
    errMsg.value = e?.response?.data?.message || e?.message || 'OCR failed'
    stage.value = 'error'
  }
}

// ====== teardown ======
function teardownCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = 0
}

function teardown() {
  teardownCamera()
  if (mobilePollTimer) {
    clearTimeout(mobilePollTimer)
    mobilePollTimer = null
  }
  if (videoEl.value) videoEl.value.srcObject = null
}

onUnmounted(() => teardown())
</script>

<style scoped lang="scss">
.pum-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .55);
  display: flex; align-items: center; justify-content: center;
  z-index: 1500;
  backdrop-filter: blur(6px);
  padding: 20px;
}
.pum-modal {
  position: relative;
  background: #fff;
  border-radius: 20px;
  padding: 32px;
  max-width: 540px; width: 100%;
  box-shadow: 0 24px 64px rgba(15, 23, 42, .35);
  min-height: 360px;
  display: flex; flex-direction: column;
}
.pum-modal__close {
  position: absolute; top: 12px; right: 12px;
  background: transparent; border: 0;
  font-size: 24px; color: var(--ink-3, #64748B);
  cursor: pointer; width: 32px; height: 32px;
  border-radius: 50%;
}
.pum-modal__close:hover { background: #F1F5F9; }

.pum-header { text-align: center; margin-bottom: 24px; }
.pum-header__title { font-size: 20px; font-weight: 700; color: var(--ink-1, #0F172A); margin: 0 0 6px; }
.pum-header__sub { color: var(--ink-3, #64748B); font-size: 12px; margin: 0; }

/* 3 modes */
.pum-modes {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.pum-mode {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 24px 12px;
  background: #fff;
  border: 2px solid #E2E8F0;
  border-radius: 14px;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
  min-height: 160px;
  justify-content: center;
}
.pum-mode:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .03);
  transform: translateY(-2px);
}
.pum-mode__icon { font-size: 32px; }
.pum-mode__label { font-size: 14px; font-weight: 600; color: var(--ink-1, #0F172A); }
.pum-mode__hint { font-size: 11px; color: var(--ink-3, #64748B); max-width: 140px; }

/* Camera */
.pum-camera { display: flex; flex-direction: column; gap: 16px; }
.pum-camera__viewport {
  position: relative; aspect-ratio: 16/9;
  background: #0F172A;
  border-radius: 12px; overflow: hidden;
}
.pum-camera__video { width: 100%; height: 100%; object-fit: cover; }
.pum-camera__overlay {
  position: absolute; inset: 0;
  border: 4px dashed rgba(255, 255, 255, .35);
  border-radius: 12px;
  pointer-events: none;
}
.pum-camera__countdown {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 120px; font-weight: 900; color: #fff;
  text-shadow: 0 4px 16px rgba(0,0,0,.5);
}
.pum-camera__actions { display: flex; gap: 12px; justify-content: center; }

/* Mobile */
.pum-mobile { text-align: center; }
.pum-mobile__hint { color: var(--ink-3, #64748B); font-size: 13px; margin: 0 0 16px; }
.pum-mobile__qr { display: flex; flex-direction: column; align-items: center; gap: 8px; margin-bottom: 16px; }
.pum-mobile__qr-img {
  width: 200px; height: 200px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  padding: 10px;
}
.pum-mobile__url { font-size: 11px; color: var(--ink-3, #64748B); font-family: monospace; word-break: break-all; max-width: 280px; }
.pum-mobile__status {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 999px;
  background: #FEF3C7; color: #92400E;
  font-size: 13px; font-weight: 500;
  margin-bottom: 16px;
}
.pum-mobile__status.is-arrived { background: #D1FAE5; color: #065F46; }
.pum-mobile__dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: currentColor;
  animation: blink 1.2s ease-in-out infinite;
}
@keyframes blink { 0%, 100% { opacity: .3; } 50% { opacity: 1; } }

/* OCR spinner */
.pum-ocr { text-align: center; padding: 40px 0; }
.pum-ocr__spinner {
  width: 64px; height: 64px;
  border: 4px solid #E2E8F0;
  border-top-color: var(--el-color-primary, #3B6EF5);
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.pum-ocr__title { font-size: 16px; font-weight: 600; margin: 0 0 6px; }
.pum-ocr__hint { font-size: 13px; color: var(--ink-3, #64748B); margin: 0; }

/* Error */
.pum-err { text-align: center; padding: 24px 0; }
.pum-err__icon { font-size: 56px; margin-bottom: 12px; }
.pum-err__title { font-size: 16px; font-weight: 700; margin: 0 0 8px; color: var(--ink-1, #0F172A); }
.pum-err__msg { color: var(--ink-3, #64748B); font-size: 13px; margin: 0 0 20px; max-width: 380px; margin-left: auto; margin-right: auto; }
.pum-err__actions { display: flex; gap: 12px; justify-content: center; }

/* Buttons */
.pum-btn {
  border: 0; border-radius: 999px;
  padding: 10px 22px; font-size: 13px; font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}
.pum-btn--primary {
  background: linear-gradient(135deg, #3B6EF5, #6E59F0);
  color: #fff;
}
.pum-btn--primary:hover { box-shadow: 0 4px 12px rgba(59, 110, 245, .35); }
.pum-btn--ghost { background: #F1F5F9; color: var(--ink-1, #0F172A); }
.pum-btn--ghost:hover { background: #E2E8F0; }

.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 600px) {
  .pum-modes { grid-template-columns: 1fr; }
}
</style>
