<template>
  <div
    class="uploader"
    :class="{ 'uploader--dragover': isDragOver }"
    @dragenter.prevent="isDragOver = true"
    @dragleave.prevent="isDragOver = false"
    @dragover.prevent
    @drop.prevent="onDrop"
    @click="onUploaderClick"
    role="button"
    tabindex="0"
    :aria-label="t('materials.upload_title')"
    @keydown.enter="onUploaderClick"
    data-testid="material-uploader"
  >
    <SensitiveDataConsent
      :open="consentOpen"
      @accept="onConsentAccept"
      @cancel="onConsentCancel"
    />
    <input
      ref="fileInput"
      type="file"
      :accept="acceptAttr"
      class="uploader__input"
      @change="onChange"
      data-testid="uploader-input"
    />

    <!-- idle -->
    <template v-if="phase === 'idle'">
      <div class="uploader__icon">📤</div>
      <div class="uploader__title">{{ t('materials.upload_title') }}</div>
      <div class="uploader__desc">{{ t('materials.upload_desc') }}</div>
      <div class="uploader__hint">
        <span>{{ t('materials.format_hint') }}</span>
        <span class="uploader__sep">·</span>
        <span>{{ t('materials.size_hint') }}</span>
      </div>
    </template>

    <!-- uploading -->
    <template v-else-if="phase === 'uploading'">
      <div class="uploader__icon">⏳</div>
      <div class="uploader__title">{{ uploadingName }}</div>
      <div class="uploader__progress-bar">
        <div class="uploader__progress-fill" :style="{ width: progress + '%' }" />
      </div>
      <div class="uploader__pct">{{ progress }}%</div>
    </template>

    <!-- done -->
    <template v-else-if="phase === 'done'">
      <div class="uploader__preview">
        <img v-if="previewUrl" :src="previewUrl" :alt="t('materials.thumb_alt')" />
        <div v-else class="uploader__preview-fallback">📄</div>
      </div>
      <div class="uploader__done-name">{{ doneName }}</div>
      <div class="uploader__done-count">{{ t('materials.uploaded_count', { n: uploadedCount }) }}</div>
    </template>

    <!-- preprocess preview (功能1: 自动扫描剪裁) -->
    <template v-else-if="phase === 'preview'">
      <div class="uploader__preview-title">🔍 {{ t('materials.preview_title', '自动扫描结果') }}</div>
      <div class="uploader__preview-grid">
        <div class="uploader__preview-cell">
          <div class="uploader__preview-label">原图</div>
          <img v-if="originalPreview" :src="originalPreview" class="uploader__preview-img" alt="原图" />
        </div>
        <div class="uploader__preview-arrow">→</div>
        <div class="uploader__preview-cell">
          <div class="uploader__preview-label">剪裁后 ({{ previewMeta.width }}×{{ previewMeta.height }})</div>
          <img v-if="processedPreview" :src="processedPreview" class="uploader__preview-img" alt="剪裁后" />
        </div>
      </div>
      <div v-if="previewMeta.corrected" class="uploader__preview-info">
        ✨ 检测到文档边缘,自动透视变换 · 置信度 {{ Math.round((previewMeta.confidence || 0) * 100) }}%
      </div>
      <div v-else class="uploader__preview-info warn">
        ⚠️ 未检测到清晰文档边界,建议手动重拍或使用原图上传
      </div>
      <div class="uploader__preview-actions">
        <button
          class="uploader__btn uploader__btn--primary"
          @click.stop="confirmProcessed"
          data-testid="uploader-confirm-processed"
        >
          ✅ 使用剪裁版本
        </button>
        <button
          class="uploader__btn uploader__btn--ghost"
          @click.stop="confirmOriginal"
          data-testid="uploader-confirm-original"
        >
          📷 使用原图
        </button>
      </div>
    </template>

    <!-- scanning -->
    <template v-else-if="phase === 'scanning'">
      <div class="uploader__icon">🔍</div>
      <div class="uploader__title">{{ t('materials.scanning', '正在自动扫描...') }}</div>
      <div class="uploader__hint">{{ scanningFileName }}</div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { processMaterial, preprocessImage, getAcceptTypes, getMaxBytes } from '@/api/materials'
import { addLocalDocument, fileToDataUrl } from '@/utils/localPrivacyStorage'
import SensitiveDataConsent from '@/components/SensitiveDataConsent.vue'
import {
  hasLocalSensitiveConsent,
  markLocalSensitiveConsent,
  syncSensitiveConsentToServer,
} from '@/utils/sensitiveConsent'

const emit = defineEmits(['uploaded'])

const { t } = useI18n()

const fileInput = ref(null)
const isDragOver = ref(false)
const consentOpen = ref(false)
let pendingPick = null
const phase = ref('idle')          // 'idle' | 'scanning' | 'preview' | 'uploading' | 'done'
const progress = ref(0)
const uploadingName = ref('')
const scanningFileName = ref('')
const doneName = ref('')
const previewUrl = ref('')
const uploadedCount = ref(0)

// preprocess state (功能1)
const pendingFile = ref(null)          // user-picked file waiting for confirmation
const processedBlob = ref(null)        // cropped/scan-optimized blob
const originalPreview = ref('')       // data: URL of original
const processedPreview = ref('')      // data: URL of processed
const previewMeta = ref({})

const ACCEPT = getAcceptTypes()
const MAX_BYTES = getMaxBytes()
const acceptAttr = ACCEPT.join(',')

function validate(file) {
  if (!file) return false
  if (file.size > MAX_BYTES) {
    alert(t('materials.file_too_big'))
    return false
  }
  if (file.type && !ACCEPT.includes(file.type)) {
    alert(t('materials.file_type_invalid'))
    return false
  }
  return true
}

// image MIME types that benefit from preprocess
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

async function pickFile(file) {
  if (!validate(file)) return
  if (!hasLocalSensitiveConsent()) {
    pendingPick = file
    consentOpen.value = true
    return
  }
  await startPick(file)
}

async function onConsentAccept() {
  markLocalSensitiveConsent()
  await syncSensitiveConsentToServer()
  consentOpen.value = false
  const f = pendingPick
  pendingPick = null
  if (f) await startPick(f)
  else fileInput.value?.click()
}

function onConsentCancel() {
  consentOpen.value = false
  pendingPick = null
}

function onUploaderClick() {
  if (!hasLocalSensitiveConsent()) {
    pendingPick = null
    consentOpen.value = true
    return
  }
  fileInput.value?.click()
}

async function startPick(file) {
  // 功能1: 图片类型才走 preprocess; PDF 直接 upload
  if (IMAGE_TYPES.includes(file.type)) {
    await runPreprocess(file)
  } else {
    doUpload(file)
  }
}

async function runPreprocess(file) {
  phase.value = 'scanning'
  scanningFileName.value = file.name
  pendingFile.value = file

  // 显示原图
  originalPreview.value = await fileToDataUrl(file)

  try {
    const result = await preprocessImage(file, {})
    processedBlob.value = base64ToBlob(result.image_base64, result.meta.mime_type || 'image/jpeg')
    processedPreview.value = `data:${result.meta.mime_type || 'image/jpeg'};base64,${result.image_base64}`
    previewMeta.value = result.meta
    phase.value = 'preview'
  } catch (err) {
    // preprocess failed — fall back to original
    console.warn('[uploader] preprocess failed, using original:', err)
    phase.value = 'uploading'
    doUpload(file)
  }
}

function confirmProcessed() {
  if (!processedBlob.value) {
    confirmOriginal()
    return
  }
  // wrap blob into a File with the original name
  const file = new File([processedBlob.value], pendingFile.value.name, {
    type: processedBlob.value.type,
  })
  phase.value = 'uploading'
  doUpload(file)
}

function confirmOriginal() {
  phase.value = 'uploading'
  doUpload(pendingFile.value)
}

function base64ToBlob(b64, mime) {
  const bytes = atob(b64)
  const arr = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
  return new Blob([arr], { type: mime })
}

function onChange(e) {
  pickFile(e.target.files?.[0])
  e.target.value = ''
}

function onDrop(e) {
  isDragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) pickFile(file)
}

async function doUpload(file) {
  phase.value = 'uploading'
  uploadingName.value = file.name
  progress.value = 0

  try {
    const ticker = setInterval(() => {
      if (progress.value < 88) progress.value += 12
    }, 100)

    const result = await processMaterial(file, 'other', {
      onProgress: (pct) => { progress.value = pct },
    })
    clearInterval(ticker)
    progress.value = 100

    const thumbUrl = file.type.startsWith('image/') ? await fileToDataUrl(file) : ''
    const m = addLocalDocument({
      localId: `up_${Date.now()}`,
      file_name: file.name,
      file_size: file.size,
      material_type: 'other',
      ocr_result: result?.fields || {},
      thumbUrl,
      fileUrl: thumbUrl,
    })

    doneName.value = m.file_name
    previewUrl.value = m.thumbnail_url || ''
    uploadedCount.value += 1
    phase.value = 'done'

    emit('uploaded', m)
  } catch (err) {
    phase.value = 'idle'
    throw err
  }
}
</script>

<style scoped lang="scss">
.uploader {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 160px;
  padding: 28px 20px;
  border: 2px dashed var(--border, #CBD5E1);
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  transition: border-color .15s, background .15s;
  text-align: center;
  position: relative;
}
.uploader:hover,
.uploader--dragover {
  border-color: #3B6EF5;
  background: #F0F4FF;
}
.uploader__input { display: none; }

.uploader__icon { font-size: 40px; line-height: 1; }
.uploader__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-1, #0F172A);
}
.uploader__desc {
  font-size: 13px;
  color: var(--ink-2, #475569);
}
.uploader__hint {
  font-size: 12px;
  color: var(--ink-3, #94A3B8);
  display: flex;
  align-items: center;
  gap: 4px;
}
.uploader__sep { opacity: .5; }

.uploader__progress-bar {
  width: 100%;
  max-width: 280px;
  height: 6px;
  border-radius: 999px;
  background: #E2E8F0;
  overflow: hidden;
}
.uploader__progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3B6EF5, #6E59F0);
  border-radius: 999px;
  transition: width .15s;
}
.uploader__pct {
  font-size: 12px;
  font-weight: 600;
  color: #3B6EF5;
}

.uploader__preview {
  width: 80px;
  height: 100px;
  border-radius: 8px;
  overflow: hidden;
  background: #F1F5F9;
  display: flex;
  align-items: center;
  justify-content: center;
}
.uploader__preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.uploader__preview-fallback { font-size: 32px; }
.uploader__done-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-1, #0F172A);
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.uploader__done-count {
  font-size: 12px;
  color: #16A34A;
  font-weight: 500;
}

/* preprocess preview (功能1) */
.uploader__preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
  margin-bottom: 8px;
}
.uploader__preview-grid {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
  width: 100%;
  max-width: 520px;
}
.uploader__preview-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.uploader__preview-label {
  font-size: 11px;
  color: #94A3B8;
  font-weight: 500;
}
.uploader__preview-img {
  max-width: 180px;
  max-height: 120px;
  border-radius: 6px;
  border: 1px solid #E2E8F0;
  object-fit: contain;
  background: #fff;
}
.uploader__preview-arrow {
  font-size: 24px;
  color: #3B6EF5;
  font-weight: 600;
}
.uploader__preview-info {
  font-size: 12px;
  color: #16A34A;
  background: #F0FDF4;
  padding: 6px 12px;
  border-radius: 6px;
  margin: 8px 0;
  &.warn {
    color: #B45309;
    background: #FEF3C7;
  }
}
.uploader__preview-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.uploader__btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .15s;
  &:hover { opacity: .85; }
}
.uploader__btn--primary {
  background: #3B6EF5;
  color: #fff;
}
.uploader__btn--ghost {
  background: #F1F5F9;
  color: #475569;
}
</style>