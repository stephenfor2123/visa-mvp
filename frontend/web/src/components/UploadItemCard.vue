<template>
  <div
    class="uic"
    :class="{ 'is-done': record.collected, 'is-error': !!record.error, 'is-uploading': phase === 'uploading' }"
    :data-testid="`uic-${itemKey}`"
  >
    <div class="uic__head">
      <div class="uic__title">
        {{ t(item.labelKey) }}
        <span v-if="item.optional" class="uic__optional">{{ t('wizard.optional_badge') }}</span>
      </div>
      <div v-if="record.collected && !record.error" class="uic__check">
        <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
          <path d="M3 8 L7 12 L13 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    </div>
    <p class="uic__hint">{{ t(item.hintKey, { cur: currencyFor(props.countryCode) }) }}</p>

    <!-- idle: 上传 or 现场扫描 -->
    <div v-if="!record.collected && phase === 'idle'" class="uic__actions">
      <button class="uic__btn uic__btn--primary" data-testid="uic-pick-file" @click="pickFile">
        📁 {{ t('wizard.pick_file') }}
      </button>
      <button class="uic__btn uic__btn--ghost" data-testid="uic-scan" @click="startCamera">
        📷 {{ t('wizard.scan_camera') }}
      </button>
      <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" style="display:none" @change="onFilePicked" />
    </div>

    <!-- camera capture -->
    <div v-else-if="phase === 'camera'" class="uic__camera">
      <video ref="videoEl" class="uic__video" autoplay muted playsinline />
      <div class="uic__camera-actions">
        <button class="uic__btn uic__btn--ghost" @click="cancelCamera">{{ t('wizard.camera_cancel') }}</button>
        <button class="uic__btn uic__btn--primary" data-testid="uic-snap" @click="capture">{{ t('wizard.camera_capture') }}</button>
      </div>
    </div>

    <!-- uploading -->
    <div v-else-if="phase === 'uploading'" class="uic__progress">
      <div class="uic__progress-bar"><div class="uic__progress-fill" :style="{ width: progress + '%' }" /></div>
      <div class="uic__progress-text">{{ progress < 100 ? t('wizard.uploading') : t('wizard.recognizing') }}</div>
    </div>

    <!-- done -->
    <div v-else-if="record.collected" class="uic__done">
      <div class="uic__file">
        <img v-if="record.thumbUrl" :src="record.thumbUrl" alt="" class="uic__thumb" />
        <span v-else class="uic__thumb uic__thumb--fallback">📄</span>
        <span class="uic__filename">{{ record.fileName }}</span>
      </div>

      <div v-if="record.isBlurry" class="uic__warn">
        ⚠️ {{ t('wizard.warn_blurry') }}
      </div>
      <div v-if="!record.isComplete" class="uic__warn">
        ⚠️ {{ t('wizard.warn_incomplete') }}
      </div>
      <div v-if="passportPreview" class="uic__ocr-preview">
        <span>{{ passportPreview.name }}</span>
        <span>{{ passportPreview.no }}</span>
        <span>{{ passportPreview.expiry }}</span>
      </div>

      <button class="uic__reupload" data-testid="uic-reupload" @click="reupload">{{ t('wizard.reupload') }}</button>
    </div>

    <!-- error -->
    <div v-if="record.error" class="uic__error" data-testid="uic-error">{{ record.error }}</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  itemKey: { type: String, required: true },
  item: { type: Object, required: true },
  record: { type: Object, required: true },
  uploadFn: { type: Function, required: true }, // (file, onProgress) => Promise
  countryCode: { type: String, default: '' },
})

// W45 fix: bank-statement / insurance hints used to hardcode "¥50,000" which
// looked wrong on the en-US locale with US/GB/Schengen destinations. Map the
// destination country to the local currency symbol (or the conventional code
// in zh-CN / vi-VN) and inject it as {cur} into the i18n string.
const CURRENCY_BY_COUNTRY = {
  US: '$',      CA: 'CA$', AU: 'A$', NZ: 'NZ$', SG: 'S$', JP: '¥',
  GB: '£',
  // Schengen member states share the euro for the customer-facing hint
  AT: '€', BE: '€', HR: '€', CZ: '€', DK: '€', EE: '€', FI: '€', FR: '€',
  DE: '€', GR: '€', HU: '€', IS: '€', IT: '€', LV: '€', LI: '€', LT: '€',
  LU: '€', MT: '€', NL: '€', NO: '€', PL: '€', PT: '€', SK: '€', SI: '€',
  ES: '€', SE: '€',
}
function currencyFor(cc) {
  return CURRENCY_BY_COUNTRY[cc] || '¥'
}
const emit = defineEmits(['remove'])

const phase = ref('idle') // idle | camera | uploading
const progress = ref(0)
const fileInput = ref(null)
const videoEl = ref(null)
let mediaStream = null

const passportPreview = computed(() => {
  const f = props.record.ocrFields
  if (!f || !props.item.checkExpiry) return null
  const name = [f.given_name, f.surname].filter(Boolean).join(' ')
  return {
    name: name || t('wizard.preview_name_unknown'),
    no: f.passport_no ? t('wizard.preview_no_prefix', { no: f.passport_no }) : '',
    expiry: (f.expiry || f.date_of_expiry) ? t('wizard.preview_expiry_prefix', { date: f.expiry || f.date_of_expiry }) : '',
  }
})

function pickFile() {
  fileInput.value?.click()
}

function onFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (file) doUpload(file)
}

async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    phase.value = 'camera'
    setTimeout(() => { if (videoEl.value) videoEl.value.srcObject = mediaStream }, 50)
  } catch {
    // 摄像头不可用时退回文件选择
    pickFile()
  }
}

function cancelCamera() {
  teardownCamera()
  phase.value = 'idle'
}

function capture() {
  const v = videoEl.value
  if (!v) return
  const canvas = document.createElement('canvas')
  canvas.width = v.videoWidth || 1280
  canvas.height = v.videoHeight || 720
  canvas.getContext('2d').drawImage(v, 0, 0, canvas.width, canvas.height)
  teardownCamera()
  canvas.toBlob((blob) => {
    if (blob) doUpload(new File([blob], `${props.itemKey}_scan.jpg`, { type: 'image/jpeg' }))
  }, 'image/jpeg', 0.92)
}

function teardownCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
}

async function doUpload(file) {
  phase.value = 'uploading'
  progress.value = 0
  try {
    await props.uploadFn(file, (p) => { progress.value = p })
  } catch {
    // record.error 已经在 uploadFn 内部（组合式函数）里写好了，这里不用重复处理
  } finally {
    phase.value = 'idle'
  }
}

function reupload() {
  emit('remove')
  phase.value = 'idle'
}
</script>

<style scoped lang="scss">
.uic {
  border: 1.5px solid #e9edf5; border-radius: 16px; padding: 18px 20px;
  background: #fff; transition: border-color .15s ease, box-shadow .15s ease;
  &.is-done { border-color: #bbf7d0; background: #f7fefb; }
  &.is-error { border-color: #fecaca; background: #fef2f2; }
}
.uic__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.uic__title { font-size: 15px; font-weight: 700; color: #0f172a; }
.uic__optional { font-size: 10px; font-weight: 600; color: #94a3b8; background: #f1f5f9; padding: 1px 8px; border-radius: 999px; margin-left: 6px; }
.uic__check {
  width: 22px; height: 22px; border-radius: 50%; background: #16a34a; color: #fff;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.uic__hint { font-size: 12.5px; color: #64748b; margin: 6px 0 14px; line-height: 1.5; }

.uic__actions { display: flex; gap: 10px; }
.uic__btn {
  flex: 1; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; border: 0; transition: all .15s ease;
  &--primary { background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff; }
  &--primary:hover { box-shadow: 0 6px 16px rgba(59,110,245,.3); }
  &--ghost { background: #f1f5f9; color: #475569; }
  &--ghost:hover { background: #e2e8f0; }
}

.uic__camera { display: flex; flex-direction: column; gap: 10px; }
.uic__video { width: 100%; border-radius: 10px; background: #0f172a; aspect-ratio: 4/3; object-fit: cover; }
.uic__camera-actions { display: flex; gap: 10px; }

.uic__progress-bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.uic__progress-fill { height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0); transition: width .15s ease; }
.uic__progress-text { font-size: 12px; color: #64748b; margin-top: 6px; }

.uic__done { display: flex; flex-direction: column; gap: 8px; }
.uic__file { display: flex; align-items: center; gap: 10px; }
.uic__thumb { width: 44px; height: 44px; border-radius: 8px; object-fit: cover; background: #f1f5f9; }
.uic__thumb--fallback { display: flex; align-items: center; justify-content: center; font-size: 20px; }
.uic__filename { font-size: 13px; color: #0f172a; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uic__warn { font-size: 12px; color: #b45309; background: #fffbeb; padding: 6px 10px; border-radius: 8px; }
.uic__ocr-preview {
  display: flex; flex-wrap: wrap; gap: 6px 12px; font-size: 12px; color: #0f172a;
  background: #f8fafc; padding: 8px 10px; border-radius: 8px;
}
.uic__reupload {
  align-self: flex-start; background: transparent; border: 1px solid #cbd5e1; color: #475569;
  font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 999px; cursor: pointer;
}
.uic__reupload:hover { background: #f1f5f9; }
.uic__error { margin-top: 10px; font-size: 12.5px; color: #b91c1c; }
</style>
