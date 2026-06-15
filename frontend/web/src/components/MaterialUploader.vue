<template>
  <div
    class="uploader"
    :class="{ 'uploader--dragover': isDragOver }"
    @dragenter.prevent="isDragOver = true"
    @dragleave.prevent="isDragOver = false"
    @dragover.prevent
    @drop.prevent="onDrop"
    @click="fileInput?.click()"
    role="button"
    tabindex="0"
    :aria-label="t('materials.upload_title')"
    @keydown.enter="fileInput?.click()"
    data-testid="material-uploader"
  >
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { uploadMaterial, getAcceptTypes, getMaxBytes } from '@/api/materials'

const emit = defineEmits(['uploaded'])

const { t } = useI18n()

const fileInput = ref(null)
const isDragOver = ref(false)
const phase = ref('idle')          // 'idle' | 'uploading' | 'done'
const progress = ref(0)
const uploadingName = ref('')
const doneName = ref('')
const previewUrl = ref('')
const uploadedCount = ref(0)

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

function pickFile(file) {
  if (!validate(file)) return
  doUpload(file)
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
    // simulate progress (real xhr would use upload.onprogress)
    const ticker = setInterval(() => {
      if (progress.value < 88) progress.value += 12
    }, 100)

    const m = await uploadMaterial(file)
    clearInterval(ticker)
    progress.value = 100

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
</style>