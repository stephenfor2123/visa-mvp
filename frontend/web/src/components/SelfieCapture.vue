<!-- SelfieCapture.vue — 自拍活体(Atlys 风格:3-2-1 倒计时 + 质量检查动画) -->
<template>
  <Transition name="fade">
    <div v-if="open" class="selfie-overlay" @click.self="onClose">
      <div class="selfie-modal">
        <button class="selfie-modal__close" @click="onClose" data-testid="selfie-close">×</button>

        <!-- 状态:init(请求摄像头) -->
        <template v-if="stage === 'init'">
          <div class="selfie-init">
            <div class="selfie-init__icon">📷</div>
            <h2 class="selfie-init__title">{{ t('selfie.title', 'Take a selfie') }}</h2>
            <p class="selfie-init__sub">{{ t('selfie.sub', 'We need to verify your identity. Look straight at the camera.') }}</p>
            <button class="selfie-init__btn" @click="startCamera" data-testid="selfie-start">
              {{ t('selfie.start', 'Start camera') }}
            </button>
            <button class="selfie-init__alt" @click="onUploadAlt">
              {{ t('selfie.upload_alt', 'Or upload a photo') }}
            </button>
          </div>
        </template>

        <!-- 状态:capture(实时画面 + 倒计时) -->
        <template v-else-if="stage === 'capture'">
          <div class="selfie-capture">
            <h3 class="selfie-capture__hint">{{ t('selfie.look', 'Great! Please look at the camera') }}</h3>
            <div class="selfie-capture__circle">
              <video ref="videoEl" class="selfie-capture__video" autoplay muted playsinline />
              <div class="selfie-capture__ring" />
              <div v-if="countdown" class="selfie-capture__countdown">{{ countdown }}</div>
            </div>
            <p class="selfie-capture__tip">{{ t('selfie.tip', 'Hold still, face well-lit') }}</p>
          </div>
        </template>

        <!-- 状态:review(刚拍完,确认) -->
        <template v-else-if="stage === 'review'">
          <div class="selfie-review">
            <h3 class="selfie-review__title">{{ t('selfie.preview', 'Look good?') }}</h3>
            <img v-if="capturedUrl" :src="capturedUrl" class="selfie-review__img" alt="captured selfie" />
            <div class="selfie-review__actions">
              <button class="selfie-review__btn selfie-review__btn--ghost" @click="retake">
                {{ t('selfie.retake', 'Retake') }}
              </button>
              <button class="selfie-review__btn selfie-review__btn--primary" @click="useThis" data-testid="selfie-use">
                {{ t('selfie.use', 'Use this photo') }}
              </button>
            </div>
          </div>
        </template>

        <!-- 状态:checking(质量检查动画) -->
        <template v-else-if="stage === 'checking'">
          <div class="selfie-check">
            <h3 class="selfie-check__title">{{ t('selfie.checking', 'Performing Quality Checks') }}</h3>
            <div class="selfie-check__items">
              <div
                v-for="(c, i) in checks"
                :key="c.key"
                class="selfie-check__item"
                :class="{ 'is-done': c.done }"
              >
                <span class="selfie-check__icon">{{ c.done ? '✓' : '⏳' }}</span>
                <span class="selfie-check__label">{{ c.label }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 状态:done(成功) -->
        <template v-else-if="stage === 'done'">
          <div class="selfie-done">
            <div class="selfie-done__big">✓</div>
            <h3 class="selfie-done__title">{{ t('selfie.verified', 'Photo verified successfully') }}</h3>
          </div>
        </template>

        <p v-if="errMsg" class="selfie-err">{{ errMsg }}</p>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'captured'])

const { t } = useI18n()

const stage = ref('init')           // init | capture | review | checking | done
const countdown = ref(0)            // 3,2,1
const capturedBlob = ref(null)
const capturedUrl = ref(null)
const videoEl = ref(null)
const errMsg = ref('')

let mediaStream = null
let countdownTimer = null
let stageTimer = null

const checks = ref([
  { key: 'standards', label: 'Matching official standards', done: false },
  { key: 'features',  label: 'Scanning facial features',    done: false },
  { key: 'verified',  label: 'Photo verified successfully',  done: false },
])

watch(() => props.open, (v) => {
  if (v) {
    stage.value = 'init'
    errMsg.value = ''
    capturedBlob.value = null
    capturedUrl.value = null
  } else {
    teardown()
  }
})

async function startCamera() {
  errMsg.value = ''
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 640 },
      audio: false,
    })
    stage.value = 'capture'
    // wait a tick so <video> mounts
    setTimeout(() => {
      if (videoEl.value && mediaStream) {
        videoEl.value.srcObject = mediaStream
      }
      startCountdown()
    }, 100)
  } catch (e) {
    errMsg.value = t('selfie.err_cam', 'Camera not available, please upload a photo instead')
    // 退回 init,等用户用 upload alt
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
  }, 800)
}

function capture() {
  if (!videoEl.value) return
  const v = videoEl.value
  const canvas = document.createElement('canvas')
  canvas.width = v.videoWidth || 640
  canvas.height = v.videoHeight || 640
  const ctx = canvas.getContext('2d')
  // 水平翻转(自拍镜像)
  ctx.translate(canvas.width, 0)
  ctx.scale(-1, 1)
  ctx.drawImage(v, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => {
    capturedBlob.value = blob
    capturedUrl.value = URL.createObjectURL(blob)
    stage.value = 'review'
    teardownCamera()
  }, 'image/jpeg', 0.85)
}

function retake() {
  if (capturedUrl.value) URL.revokeObjectURL(capturedUrl.value)
  capturedBlob.value = null
  capturedUrl.value = null
  startCamera()
}

function useThis() {
  // 进入 checking 状态,3 步打勾
  stage.value = 'checking'
  checks.value[0].done = true
  setTimeout(() => { checks.value[1].done = true }, 700)
  setTimeout(() => { checks.value[2].done = true }, 1400)
  setTimeout(() => {
    stage.value = 'done'
    setTimeout(() => {
      if (capturedBlob.value) emit('captured', capturedBlob.value)
    }, 500)
  }, 1900)
}

function onUploadAlt() {
  // 退回 init,弹 file picker
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    capturedBlob.value = f
    capturedUrl.value = URL.createObjectURL(f)
    stage.value = 'review'
  }
  input.click()
}

function onClose() {
  teardown()
  emit('close')
}

function teardownCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function teardown() {
  teardownCamera()
  if (stageTimer) {
    clearTimeout(stageTimer)
    stageTimer = null
  }
  if (capturedUrl.value && !capturedBlob.value) {
    URL.revokeObjectURL(capturedUrl.value)
  }
}

onUnmounted(() => teardown())
</script>

<style scoped lang="scss">
.selfie-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .55);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(6px);
  padding: 20px;
}
.selfie-modal {
  position: relative;
  background: #fff;
  border-radius: 20px;
  padding: 32px;
  max-width: 480px; width: 100%;
  box-shadow: 0 24px 64px rgba(15, 23, 42, .35);
  min-height: 420px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.selfie-modal__close {
  position: absolute; top: 16px; right: 16px;
  background: transparent; border: 0;
  font-size: 24px; color: var(--ink-3, #64748B);
  cursor: pointer; width: 32px; height: 32px;
  border-radius: 50%;
}
.selfie-modal__close:hover { background: #F1F5F9; }

.selfie-init { text-align: center; width: 100%; }
.selfie-init__icon { font-size: 64px; margin-bottom: 16px; }
.selfie-init__title { font-size: 22px; font-weight: 700; margin: 0 0 8px; color: var(--ink-1, #0F172A); }
.selfie-init__sub { color: var(--ink-3, #64748B); font-size: 14px; margin: 0 0 24px; }
.selfie-init__btn {
  background: linear-gradient(135deg, #3B6EF5, #6E59F0);
  color: #fff; border: 0; border-radius: 999px;
  padding: 12px 32px; font-size: 15px; font-weight: 700;
  cursor: pointer; width: 100%;
}
.selfie-init__btn:hover { box-shadow: 0 6px 18px rgba(59, 110, 245, .4); }
.selfie-init__alt {
  background: transparent; border: 0;
  color: var(--el-color-primary, #3B6EF5);
  font-size: 13px; cursor: pointer; margin-top: 12px;
  text-decoration: underline;
}

.selfie-capture { text-align: center; width: 100%; }
.selfie-capture__hint { font-size: 16px; color: var(--ink-1, #0F172A); margin: 0 0 20px; font-weight: 600; }
.selfie-capture__circle {
  position: relative; width: 280px; height: 280px;
  margin: 0 auto 20px;
  border-radius: 50%;
  overflow: hidden;
  background: #0F172A;
}
.selfie-capture__video {
  width: 100%; height: 100%; object-fit: cover;
  transform: scaleX(-1);   // mirror like a selfie
}
.selfie-capture__ring {
  position: absolute; inset: -4px;
  border-radius: 50%;
  border: 4px solid #10B981;
  animation: ringPulse 1.6s ease-in-out infinite;
  pointer-events: none;
}
@keyframes ringPulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.04); opacity: .6; }
}
.selfie-capture__countdown {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 120px; font-weight: 900; color: #fff;
  text-shadow: 0 4px 16px rgba(0,0,0,.5);
  animation: countPop .8s ease-out;
}
@keyframes countPop {
  0%   { transform: scale(0.4); opacity: 0; }
  30%  { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1);   opacity: 1; }
}
.selfie-capture__tip { color: var(--ink-3, #64748B); font-size: 13px; }

.selfie-review { text-align: center; width: 100%; }
.selfie-review__title { font-size: 18px; font-weight: 700; margin: 0 0 16px; }
.selfie-review__img {
  width: 200px; height: 200px;
  border-radius: 50%; object-fit: cover;
  border: 4px solid #10B981;
  margin-bottom: 20px;
}
.selfie-review__actions { display: flex; gap: 12px; justify-content: center; }
.selfie-review__btn {
  border: 0; border-radius: 999px;
  padding: 10px 24px; font-size: 14px; font-weight: 600;
  cursor: pointer;
}
.selfie-review__btn--ghost { background: #F1F5F9; color: var(--ink-1, #0F172A); }
.selfie-review__btn--primary { background: linear-gradient(135deg, #3B6EF5, #6E59F0); color: #fff; }

.selfie-check { text-align: center; width: 100%; }
.selfie-check__title { font-size: 18px; font-weight: 700; margin: 0 0 24px; }
.selfie-check__items { display: flex; flex-direction: column; gap: 14px; align-items: flex-start; max-width: 280px; margin: 0 auto; }
.selfie-check__item {
  display: flex; align-items: center; gap: 10px;
  font-size: 14px; color: var(--ink-3, #64748B);
  transition: color .3s;
}
.selfie-check__item.is-done { color: var(--ink-1, #0F172A); font-weight: 600; }
.selfie-check__icon {
  width: 22px; height: 22px; border-radius: 50%;
  background: #F1F5F9; color: var(--ink-3, #94A3B8);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px;
}
.selfie-check__item.is-done .selfie-check__icon { background: #10B981; color: #fff; }

.selfie-done { text-align: center; }
.selfie-done__big {
  width: 80px; height: 80px; border-radius: 50%;
  background: #10B981; color: #fff;
  font-size: 40px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 16px;
  animation: popIn .4s ease-out;
}
@keyframes popIn { from { transform: scale(0); } to { transform: scale(1); } }
.selfie-done__title { font-size: 18px; font-weight: 700; }

.selfie-err {
  position: absolute; bottom: 16px; left: 24px; right: 24px;
  background: #FEF2F2; color: #DC2626;
  padding: 10px 14px; border-radius: 8px;
  font-size: 13px; text-align: center;
  margin: 0;
}

.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
