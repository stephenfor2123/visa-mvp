<template>
  <div class="scan-page">
    <header class="scan-header">
      <button class="scan-back" @click="goBack" data-testid="scan-back" aria-label="back">←</button>
      <div class="scan-title">{{ t('materials.scan_title') }}</div>
      <button
        class="scan-flash"
        :class="{ on: flashOn }"
        @click="toggleFlash"
        :title="flashOn ? t('materials.flash_on') : t('materials.flash_off')"
        data-testid="scan-flash"
      >🔦</button>
    </header>

    <!-- Material type chip (V2 §3.3.2: 7 chips, but task scope picks 1) -->
    <div class="scan-types">
      <button
        v-for="opt in typeOptions"
        :key="opt.value"
        class="scan-type-chip"
        :class="{ on: materialType === opt.value }"
        @click="materialType = opt.value"
        :data-testid="`scan-type-${opt.value}`"
      >{{ t(opt.label) }}</button>
    </div>

    <!-- Viewfinder frame -->
    <div class="scan-viewfinder" :class="{ 'is-flash': flashOn }">
      <video
        ref="videoEl"
        class="scan-video"
        autoplay
        muted
        playsinline
        data-testid="scan-video"
      ></video>
      <!-- 4-corner alignment guides -->
      <div class="scan-frame">
        <span class="corner corner--tl"></span>
        <span class="corner corner--tr"></span>
        <span class="corner corner--bl"></span>
        <span class="corner corner--br"></span>
        <span class="scan-hint">{{ hintText }}</span>
      </div>

      <!-- Countdown ring -->
      <div v-if="countdown > 0" class="scan-countdown" data-testid="scan-countdown">
        {{ countdown }}
      </div>

      <!-- Permission denied -->
      <div v-if="permissionDenied" class="scan-perm" data-testid="scan-permission-denied">
        <p>📵 {{ t('errors.network_error') }}</p>
        <p class="scan-perm__sub">{{ t('materials.scan_perm_hint', [t('materials.tab_pdf')]) }}</p>
      </div>

      <!-- Capture success preview -->
      <div v-if="capturedDataUrl" class="scan-preview" data-testid="scan-preview">
        <img :src="capturedDataUrl" alt="captured" />
        <p class="scan-preview__tip">✓ {{ t('materials.capture_taken') }}</p>
      </div>
    </div>

    <!-- Bottom capture button + countdown hint -->
    <div class="scan-foot">
      <p class="scan-tip">{{ t('materials.countdown_tip') }}</p>
      <button
        class="scan-capture"
        :class="{ disabled: capturing }"
        :disabled="capturing"
        @click="captureNow"
        data-testid="scan-capture"
        aria-label="capture"
      >
        <span class="scan-capture__ring"></span>
        <span class="scan-capture__dot"></span>
      </button>
      <p class="scan-tip-mini">{{ hintText }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { processMaterial, getMaterialTypeOptions, getAcceptTypes, getMaxBytes } from '@/api/materials'
import { addLocalDocument, fileToDataUrl } from '@/utils/localPrivacyStorage'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const toast = useToast()

const videoEl = ref(null)
const stream = ref(null)
const flashOn = ref(false)
const materialType = ref(route.query.type || 'passport')
const countdown = ref(0)
const capturing = ref(false)
const capturedDataUrl = ref('')
const permissionDenied = ref(false)
let countdownTimer = null
let autoCaptureTimer = null
let streamReattachTimer = null

const typeOptions = getMaterialTypeOptions()

const hintText = computed(() => {
  // V2 §3.3.5 hints: different text per material type
  return t(`materials.scan_hint_${materialType.value}`) || t('materials.scan_hint_passport')
})

watch(materialType, () => {
  // Reset countdown when switching material type
  if (!capturing) startCountdown()
})

function startCountdown(seconds = 3) {
  if (countdownTimer) clearInterval(countdownTimer)
  countdown.value = seconds
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      countdownTimer = null
      autoCapture()
    }
  }, 1000)
}

async function initCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    // Web env demo fallback: no camera permission -> render gradient placeholder frame (so screenshots work)
    permissionDenied.value = true
    startCountdown(3)
    return
  }
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: 1280, height: 720 },
      audio: false
    })
    if (videoEl.value) {
      videoEl.value.srcObject = stream.value
      await videoEl.value.play().catch(() => {})
    }
    // Start countdown after permission OK
    startCountdown(3)
  } catch (e) {
    console.warn('[scan] camera init failed', e?.message)
    permissionDenied.value = true
    // Still allow user to click capture button (mock placeholder)
    startCountdown(3)
  }
}

function toggleFlash() {
  flashOn.value = !flashOn.value
  toast.info(flashOn.value ? t('materials.flash_on') : t('materials.flash_off'), { duration: 1500 })
}

function goBack() {
  if (stream.value) {
    stream.value.getTracks().forEach((tk) => tk.stop())
    stream.value = null
  }
  router.push({ name: 'Materials', query: { ...route.query } })
}

function captureNow() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  autoCapture()
}

async function autoCapture() {
  if (capturing.value) return
  capturing.value = true
  try {
    const dataUrl = await grabFrame()
    capturedDataUrl.value = dataUrl
    // Convert dataURL to Blob then wrap as File for upload
    const file = dataUrlToFile(dataUrl, `${materialType.value}_${Date.now()}.jpg`)
    await processMaterial(file, materialType.value)
    const thumbUrl = await fileToDataUrl(file)
    addLocalDocument({
      localId: `scan_${Date.now()}`,
      file_name: file.name,
      file_size: file.size,
      material_type: materialType.value,
      thumbUrl,
      fileUrl: thumbUrl,
    })
    toast.success(`✓ ${file.name}`)
    // Show user 800ms preview then return to list
    autoCaptureTimer = setTimeout(() => {
      goBack()
    }, 800)
  } catch (e) {
    console.error('[scan] capture failed', e)
    toast.error(e?.message || 'capture failed')
  } finally {
    capturing.value = false
  }
}

async function grabFrame() {
  // Camera available -> use canvas to capture current frame
  if (videoEl.value && stream.value) {
    const w = videoEl.value.videoWidth || 640
    const h = videoEl.value.videoHeight || 480
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    // Flash mode: add white overlay to frame
    if (flashOn.value) {
      ctx.fillStyle = '#FFFFFF'
      ctx.fillRect(0, 0, w, h)
    }
    ctx.drawImage(videoEl.value, 0, 0, w, h)
    return canvas.toDataURL('image/jpeg', 0.85)
  }
  // No camera permission -> return synthesized SVG placeholder (dataURL), let flow proceed
  return synthPlaceholder(materialType.value, flashOn.value)
}

function synthPlaceholder(type, flash) {
  const w = 640
  const h = 480
  const bg = flash ? '#FFFFFF' : '#1F2937'
  const fg = flash ? '#1F2937' : '#FFFFFF'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <rect width="100%" height="100%" fill="${bg}"/>
    <rect x="60" y="80" width="${w - 120}" height="${h - 200}" fill="none" stroke="${fg}" stroke-width="4" stroke-dasharray="14 8" rx="12"/>
    <text x="50%" y="48%" text-anchor="middle" fill="${fg}" font-family="-apple-system, sans-serif" font-size="36" font-weight="700">${type.toUpperCase()}</text>
    <text x="50%" y="58%" text-anchor="middle" fill="${fg}" font-family="-apple-system, sans-serif" font-size="16" opacity="0.7">mock preview (no camera permission)</text>
  </svg>`
  return 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)))
}

function dataUrlToFile(dataUrl, filename) {
  const arr = dataUrl.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] || 'image/jpeg'
  const bin = atob(arr[1])
  const u8 = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i)
  return new File([u8], filename, { type: mime })
}

onMounted(() => {
  initCamera()
})

onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (autoCaptureTimer) clearTimeout(autoCaptureTimer)
  if (streamReattachTimer) clearTimeout(streamReattachTimer)
  if (stream.value) {
    stream.value.getTracks().forEach((tk) => tk.stop())
    stream.value = null
  }
})
</script>

<style scoped lang="scss">
.scan-page {
  min-height: 100vh;
  background: #0B1220;
  color: #fff;
  display: flex;
  flex-direction: column;
  user-select: none;
}
.scan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  position: relative;
  z-index: 2;
}
.scan-back {
  width: 36px; height: 36px;
  border: none; border-radius: 50%;
  background: rgba(255,255,255,.1);
  color: #fff; font-size: 20px;
  cursor: pointer;
}
.scan-back:hover { background: rgba(255,255,255,.2); }
.scan-title { font-size: 16px; font-weight: 600; }
.scan-flash {
  width: 36px; height: 36px;
  border: none; border-radius: 50%;
  background: rgba(255,255,255,.1);
  color: #fff; font-size: 18px;
  cursor: pointer;
}
.scan-flash.on { background: #FACC15; color: #0B1220; }

.scan-types {
  display: flex;
  gap: 8px;
  padding: 0 18px 12px;
  overflow-x: auto;
  flex-wrap: wrap;
}
.scan-type-chip {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.25);
  background: rgba(255,255,255,.06);
  color: rgba(255,255,255,.85);
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.scan-type-chip.on {
  background: #3B6EF5;
  border-color: #3B6EF5;
  color: #fff;
}

.scan-viewfinder {
  flex: 1;
  position: relative;
  margin: 0 18px;
  border-radius: 16px;
  overflow: hidden;
  background: #000;
  min-height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scan-viewfinder.is-flash::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,.6);
  pointer-events: none;
}
.scan-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.scan-frame {
  position: absolute;
  inset: 12% 10%;
  pointer-events: none;
}
.corner {
  position: absolute;
  width: 32px;
  height: 32px;
  border: 3px solid #fff;
}
.corner--tl { top: 0; left: 0; border-right: none; border-bottom: none; border-top-left-radius: 6px; }
.corner--tr { top: 0; right: 0; border-left: none; border-bottom: none; border-top-right-radius: 6px; }
.corner--bl { bottom: 0; left: 0; border-right: none; border-top: none; border-bottom-left-radius: 6px; }
.corner--br { bottom: 0; right: 0; border-left: none; border-top: none; border-bottom-right-radius: 6px; }

.scan-hint {
  position: absolute;
  bottom: -36px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,.6);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.scan-countdown {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 100px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 0 30px rgba(0,0,0,.5);
  animation: pop .9s ease;
  pointer-events: none;
}
@keyframes pop {
  0%   { transform: translate(-50%, -50%) scale(0.6); opacity: 0; }
  35%  { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
  100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
}

.scan-perm {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
  background: rgba(11,18,32,.92);
  font-size: 14px;
}
.scan-perm__sub { font-size: 12px; opacity: .7; margin-top: 6px; }

.scan-preview {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,.85);
}
.scan-preview img { max-width: 80%; max-height: 70%; border-radius: 8px; }
.scan-preview__tip { margin-top: 14px; font-size: 14px; color: #4ADE80; font-weight: 500; }

.scan-foot {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 18px 36px;
  gap: 14px;
}
.scan-tip { font-size: 12px; color: rgba(255,255,255,.7); margin: 0; }
.scan-tip-mini { font-size: 11px; color: rgba(255,255,255,.4); margin: 0; }

.scan-capture {
  width: 76px; height: 76px;
  border-radius: 50%;
  border: none;
  background: transparent;
  position: relative;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scan-capture__ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 4px solid #fff;
  background: transparent;
}
.scan-capture__dot {
  width: 60px; height: 60px;
  border-radius: 50%;
  background: #fff;
  transition: transform .15s;
}
.scan-capture:active .scan-capture__dot { transform: scale(0.92); }
.scan-capture.disabled { opacity: .5; cursor: not-allowed; }
</style>