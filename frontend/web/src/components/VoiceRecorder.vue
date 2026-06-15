<template>
  <div class="vrec" data-testid="voice-recorder">
    <!-- 控制条:语言切换 + 开始/停止 + 重录 -->
    <div class="vrec__controls">
      <div class="vrec__lang" role="group" :aria-label="t('materials.voice_lang_label')">
        <button
          v-for="opt in langOptions"
          :key="opt.value"
          type="button"
          class="vrec__lang-btn"
          :class="{ on: lang === opt.value }"
          :data-testid="`vrec-lang-${opt.value}`"
          @click="onLangChange(opt.value)"
        >
          <span class="vrec__lang-flag">{{ opt.flag }}</span>
          <span>{{ opt.label }}</span>
        </button>
      </div>

      <button
        type="button"
        class="vrec__mic"
        :class="{ recording: phase === 'recording' }"
        :disabled="phase === 'uploading' || phase === 'recognizing'"
        :aria-label="phase === 'recording' ? t('materials.voice_stop') : t('materials.voice_start')"
        :data-testid="'vrec-toggle'"
        @click="onToggle"
      >
        <span class="vrec__mic-icon">
          {{ phase === 'recording' ? '⏹' : '🎙' }}
        </span>
      </button>

      <div class="vrec__timer" data-testid="vrec-timer">
        <span v-if="phase === 'recording'" class="vrec__dot" />
        <span>{{ formatTime(elapsedSec) }}</span>
        <span class="vrec__max">/ {{ maxSeconds }}s</span>
      </div>
    </div>

    <!-- 状态/结果展示 -->
    <div class="vrec__body">
      <p v-if="phase === 'idle'" class="vrec__hint">
        {{ t('materials.voice_hint_idle') }}
      </p>

      <p v-else-if="phase === 'recording'" class="vrec__hint vrec__hint--rec">
        {{ t('materials.voice_hint_recording') }}
      </p>

      <p v-else-if="phase === 'uploading' || phase === 'recognizing'" class="vrec__hint">
        <span class="vrec__spinner" />
        {{ t('materials.voice_hint_processing') }}
      </p>

      <p v-else-if="phase === 'error'" class="vrec__hint vrec__hint--err" data-testid="vrec-error">
        {{ errorMessage || t('materials.voice_hint_error') }}
      </p>

      <!-- 识别结果 + 可编辑表单 -->
      <div
        v-else-if="phase === 'done' && result"
        class="vrec__result"
        data-testid="vrec-result"
      >
        <header class="vrec__result-head">
          <span class="vrec__result-tag">✓ {{ t('materials.voice_done_tag') }}</span>
          <span class="vrec__result-meta">
            {{ result.engine }} · {{ Math.round((result.confidence || 0) * 100) }}%
          </span>
        </header>

        <div class="vrec__row">
          <label class="vrec__label" for="vrec-name">{{ t('materials.voice_field_name') }}</label>
          <input
            id="vrec-name"
            v-model="editable.name"
            type="text"
            class="vrec__input"
            data-testid="vrec-input-name"
            :placeholder="t('materials.voice_field_name_ph')"
          />
        </div>

        <div class="vrec__row">
          <label class="vrec__label" for="vrec-addr">{{ t('materials.voice_field_address') }}</label>
          <input
            id="vrec-addr"
            v-model="editable.address"
            type="text"
            class="vrec__input"
            data-testid="vrec-input-address"
            :placeholder="t('materials.voice_field_address_ph')"
          />
        </div>

        <div class="vrec__row">
          <label class="vrec__label" for="vrec-date">{{ t('materials.voice_field_travel_date') }}</label>
          <input
            id="vrec-date"
            v-model="editable.travel_date"
            type="date"
            class="vrec__input"
            data-testid="vrec-input-travel-date"
          />
        </div>

        <details v-if="result.raw_text" class="vrec__raw">
          <summary>{{ t('materials.voice_raw_summary') }}</summary>
          <p data-testid="vrec-raw-text">{{ result.raw_text }}</p>
        </details>

        <div class="vrec__actions">
          <button
            type="button"
            class="vrec__btn vrec__btn--ghost"
            data-testid="vrec-retry"
            @click="onRetry"
          >
            ↻ {{ t('materials.voice_retry') }}
          </button>
          <button
            type="button"
            class="vrec__btn vrec__btn--primary"
            data-testid="vrec-apply"
            @click="onApply"
          >
            ✓ {{ t('materials.voice_apply') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 浏览器不支持 fallback -->
    <p v-if="!isSupported" class="vrec__unsupported" data-testid="vrec-unsupported">
      {{ t('materials.voice_unsupported') }}
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { uploadAudio, getSupportedLangs, validateAudioFile } from '@/api/voice'

const { t, locale } = useI18n()

const emit = defineEmits(['recognized', 'error'])

// ----------------------------------------------------------------- //
// Props                                                              //
// ----------------------------------------------------------------- //
const props = defineProps({
  /** Default language code; one of 'zh-CN' / 'en' / 'id' / 'vi'. */
  defaultLang: {
    type: String,
    default: 'zh-CN'
  },
  /** Maximum recording duration, in seconds. */
  maxSeconds: {
    type: Number,
    default: 60
  },
  /** Override the auto-detected i18n locale. */
  i18nLang: {
    type: String,
    default: ''
  }
})

// ----------------------------------------------------------------- //
// State                                                              //
// ----------------------------------------------------------------- //
const phase = ref('idle') // idle | recording | uploading | recognizing | done | error
const lang = ref(props.defaultLang)
const elapsedSec = ref(0)
const errorMessage = ref('')
const result = ref(null)
const editable = reactive({ name: '', address: '', travel_date: '' })

let mediaRecorder = null
let mediaStream = null
let recordedChunks = []
let timerId = null
let startedAt = 0

// ----------------------------------------------------------------- //
// Computed                                                           //
// ----------------------------------------------------------------- //
const isSupported = computed(() => {
  if (typeof window === 'undefined') return false
  return Boolean(navigator.mediaDevices?.getUserMedia)
    && typeof window.MediaRecorder !== 'undefined'
})

const langOptions = computed(() => {
  const supported = getSupportedLangs()
  return supported.map((code) => ({
    value: code,
    flag: flagOf(code),
    label: labelOf(code)
  }))
})

function flagOf(code) {
  return ({ 'zh-CN': '🇨🇳', en: '🇺🇸', id: '🇮🇩', vi: '🇻🇳' })[code] || '🌐'
}

function labelOf(code) {
  return ({
    'zh-CN': '中文',
    en: 'EN',
    id: 'ID',
    vi: 'VI'
  })[code] || code
}

function formatTime(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

// ----------------------------------------------------------------- //
// Watchers                                                           //
// ----------------------------------------------------------------- //
watch(locale, (val) => {
  if (val && !lang.value) lang.value = mapI18nToLang(val)
})

watch(
  () => props.i18nLang,
  (val) => {
    if (val) lang.value = mapI18nToLang(val)
  },
  { immediate: true }
)

function mapI18nToLang(l) {
  if (!l) return props.defaultLang
  if (l.startsWith('zh')) return 'zh-CN'
  if (l.startsWith('id')) return 'id'
  if (l.startsWith('vi')) return 'vi'
  return 'en'
}

// ----------------------------------------------------------------- //
// Recording lifecycle                                                //
// ----------------------------------------------------------------- //
async function onToggle() {
  if (phase.value === 'recording') {
    stopRecording()
  } else if (phase.value === 'idle' || phase.value === 'done' || phase.value === 'error') {
    await startRecording()
  }
}

function onLangChange(code) {
  lang.value = code
}

async function startRecording() {
  if (!isSupported.value) {
    setError(t('materials.voice_unsupported'))
    return
  }
  errorMessage.value = ''
  result.value = null
  recordedChunks = []
  elapsedSec.value = 0

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (err) {
    setError(t('materials.voice_mic_denied'))
    return
  }

  // 选一个后端/浏览器都能吃的 mime
  const mimeCandidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
    'audio/wav'
  ]
  const mimeType = mimeCandidates.find(
    (m) => window.MediaRecorder?.isTypeSupported?.(m)
  ) || ''

  try {
    mediaRecorder = mimeType
      ? new MediaRecorder(mediaStream, { mimeType })
      : new MediaRecorder(mediaStream)
  } catch (err) {
    setError(t('materials.voice_recorder_init_failed'))
    stopStream()
    return
  }

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordedChunks.push(e.data)
  }
  mediaRecorder.onstop = onRecorderStop

  startedAt = Date.now()
  mediaRecorder.start(250) // 每 250ms 一片
  phase.value = 'recording'

  if (timerId) clearInterval(timerId)
  timerId = setInterval(() => {
    elapsedSec.value = Math.floor((Date.now() - startedAt) / 1000)
    if (elapsedSec.value >= props.maxSeconds) {
      stopRecording()
    }
  }, 250)
}

function stopRecording() {
  if (timerId) {
    clearInterval(timerId)
    timerId = null
  }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try {
      mediaRecorder.stop()
    } catch (e) {
      // ignore
    }
  }
  stopStream()
}

function stopStream() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
}

async function onRecorderStop() {
  phase.value = 'uploading'
  const blob = new Blob(recordedChunks, {
    type: recordedChunks[0]?.type || 'audio/webm'
  })
  // 用 mime 推一个扩展名,后端按 magic bytes 二次校验
  const ext = (blob.type.split('/')[1] || 'webm').split(';')[0] || 'webm'
  const file = new File([blob], `voice.${ext}`, { type: blob.type })

  try {
    validateAudioFile(file)
  } catch (err) {
    setError(err.message || t('materials.voice_hint_error'))
    return
  }

  phase.value = 'recognizing'
  try {
    const data = await uploadAudio(file, lang.value)
    result.value = data
    editable.name = data.name || ''
    editable.address = data.address || ''
    editable.travel_date = data.travel_date || ''
    phase.value = 'done'
  } catch (err) {
    setError(err?.message || t('materials.voice_hint_error'))
  }
}

// ----------------------------------------------------------------- //
// Result actions                                                     //
// ----------------------------------------------------------------- //
function onRetry() {
  result.value = null
  editable.name = ''
  editable.address = ''
  editable.travel_date = ''
  errorMessage.value = ''
  phase.value = 'idle'
}

function onApply() {
  if (!result.value) return
  emit('recognized', {
    ...result.value,
    name: editable.name?.trim() || null,
    address: editable.address?.trim() || null,
    travel_date: editable.travel_date || null,
    lang: lang.value
  })
}

function setError(msg) {
  errorMessage.value = msg
  phase.value = 'error'
  emit('error', { code: 'VOICE_RECOGNIZE_FAILED', message: msg })
}

onBeforeUnmount(() => {
  if (timerId) clearInterval(timerId)
  stopStream()
})
</script>

<style scoped lang="scss">
.vrec {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 22px 22px 18px;
}

.vrec__controls {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.vrec__lang {
  display: inline-flex;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px;
  padding: 3px;
  background: #F8FAFC;
}
.vrec__lang-btn {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2, #475569);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all .15s;
}
.vrec__lang-btn:hover { color: #2D5BFF; }
.vrec__lang-btn.on {
  background: #fff;
  color: #2D5BFF;
  box-shadow: 0 1px 2px rgba(15,23,42,.06);
}
.vrec__lang-flag { font-size: 14px; }

.vrec__mic {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  background: linear-gradient(135deg, #3B6EF5, #6E59F0);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(59,110,245,.28);
  transition: transform .15s, box-shadow .15s;
}
.vrec__mic:hover:not(:disabled) { transform: scale(1.04); }
.vrec__mic:disabled { opacity: 0.5; cursor: not-allowed; }
.vrec__mic.recording {
  background: #DC2626;
  animation: vrec-pulse 1s ease-in-out infinite;
}
.vrec__mic-icon { font-size: 26px; line-height: 1; }
@keyframes vrec-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,.5); }
  50%      { box-shadow: 0 0 0 16px rgba(220,38,38,0); }
}

.vrec__timer {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-1, #0F172A);
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.vrec__dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #DC2626;
  animation: vrec-blink 1s ease-in-out infinite;
}
@keyframes vrec-blink { 0%,100%{opacity:1} 50%{opacity:.3} }
.vrec__max { color: var(--ink-3, #94A3B8); font-size: 13px; font-weight: 500; }

.vrec__body { min-height: 80px; }
.vrec__hint {
  font-size: 13px;
  color: var(--ink-3, #64748B);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.vrec__hint--rec { color: #DC2626; font-weight: 500; }
.vrec__hint--err { color: #B91C1C; font-weight: 500; }
.vrec__unsupported {
  margin-top: 8px;
  font-size: 12px;
  color: #B91C1C;
}

.vrec__spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid #CBD5E1;
  border-top-color: #2D5BFF;
  border-radius: 50%;
  animation: vrec-spin 0.8s linear infinite;
}
@keyframes vrec-spin { to { transform: rotate(360deg); } }

.vrec__result { display: flex; flex-direction: column; gap: 12px; }
.vrec__result-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px;
  background: #F0FDF4;
  border: 1px solid #86EFAC;
  border-radius: 8px;
}
.vrec__result-tag { color: #166534; font-weight: 600; font-size: 13px; }
.vrec__result-meta { color: #166534; font-size: 12px; opacity: .8; }

.vrec__row {
  display: grid;
  grid-template-columns: 110px 1fr;
  align-items: center;
  gap: 12px;
}
.vrec__label {
  font-size: 12px;
  color: var(--ink-3, #64748B);
  font-weight: 500;
}
.vrec__input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ink-1, #0F172A);
  background: #fff;
  transition: border-color .15s;
}
.vrec__input:focus {
  outline: none;
  border-color: #3B6EF5;
  box-shadow: 0 0 0 3px rgba(59,110,245,.12);
}

.vrec__raw {
  font-size: 12px;
  color: var(--ink-3, #64748B);
  background: #F8FAFC;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 6px;
  padding: 8px 10px;
}
.vrec__raw summary { cursor: pointer; user-select: none; }
.vrec__raw p { margin: 6px 0 0; line-height: 1.5; }

.vrec__actions {
  display: flex; gap: 10px; justify-content: flex-end; margin-top: 6px;
}
.vrec__btn {
  border: 1px solid transparent;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s;
}
.vrec__btn--ghost {
  background: #fff;
  border-color: var(--border, #E2E8F0);
  color: var(--ink-2, #475569);
}
.vrec__btn--ghost:hover { background: #F1F5F9; }
.vrec__btn--primary {
  background: linear-gradient(135deg, #3B6EF5, #6E59F0);
  color: #fff;
  border-color: transparent;
}
.vrec__btn--primary:hover { box-shadow: 0 4px 10px rgba(59,110,245,.25); }

@media (max-width: 540px) {
  .vrec__row { grid-template-columns: 1fr; gap: 4px; }
  .vrec__timer { margin-left: 0; }
}
</style>
