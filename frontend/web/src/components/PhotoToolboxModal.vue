<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="ptb"
      role="dialog"
      aria-modal="true"
      data-testid="photo-toolbox-modal"
      @click.self="onCancel"
    >
      <div class="ptb__panel">
        <header class="ptb__head">
          <div>
            <div class="ptb__badge">{{ t('wizard.photo_toolbox.badge') }}</div>
            <h2 class="ptb__title">{{ t('wizard.photo_toolbox.title') }}</h2>
            <p class="ptb__sub">{{ subtitle }}</p>
          </div>
          <button type="button" class="ptb__close" :aria-label="t('wizard.photo_toolbox.cancel')" @click="onCancel">×</button>
        </header>

        <div class="ptb__grid">
          <section class="ptb__card">
            <h3>{{ t('wizard.photo_toolbox.preview') }}</h3>
            <div class="ptb__stage">
              <div class="ptb__pane">
                <div class="ptb__pane-label">
                  <span>{{ t('wizard.photo_toolbox.original') }}</span>
                  <span>{{ t('wizard.photo_toolbox.check_failed') }}</span>
                </div>
                <div class="ptb__pane-body">
                  <img v-if="sourceUrl" :src="sourceUrl" alt="" />
                </div>
              </div>
              <div class="ptb__pane">
                <div class="ptb__pane-label">
                  <span>{{ t('wizard.photo_toolbox.result') }}</span>
                  <span>{{ outMeta }}</span>
                </div>
                <div class="ptb__pane-body">
                  <div class="ptb__frame" :style="{ '--ar': aspectRatio }">
                    <canvas ref="canvasEl" />
                    <div class="ptb__guide" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>
            <div class="ptb__actions">
              <button type="button" class="ptb__btn ptb__btn--primary" data-testid="ptb-one-click" @click="oneClick">
                {{ t('wizard.photo_toolbox.one_click') }}
              </button>
              <button type="button" class="ptb__btn ptb__btn--success" :disabled="busy" data-testid="ptb-confirm" @click="onConfirm">
                {{ t('wizard.photo_toolbox.confirm') }}
              </button>
              <button type="button" class="ptb__btn" data-testid="ptb-cancel" @click="onCancel">
                {{ t('wizard.photo_toolbox.cancel') }}
              </button>
            </div>
          </section>

          <aside class="ptb__card">
            <h3>{{ t('wizard.photo_toolbox.spec_title') }}</h3>
            <div class="ptb__spec">
              <div><strong>{{ t(spec.labelKey) }}</strong></div>
              <div>{{ t('wizard.photo_toolbox.spec_mm', { w: spec.mmW, h: spec.mmH }) }}</div>
              <div>{{ t('wizard.photo_toolbox.spec_px', { w: spec.pxW, h: spec.pxH }) }}</div>
              <div>{{ t('wizard.photo_toolbox.spec_bg') }}</div>
            </div>
            <label class="ptb__ctrl">
              <span>{{ t('wizard.photo_toolbox.zoom') }} <b>{{ zoom.toFixed(2) }}×</b></span>
              <input v-model.number="zoom" type="range" min="0.85" max="1.6" step="0.01" @input="render" />
            </label>
            <label class="ptb__ctrl">
              <span>{{ t('wizard.photo_toolbox.offset_y') }} <b>{{ offY }}</b></span>
              <input v-model.number="offY" type="range" min="-40" max="40" step="1" @input="render" />
            </label>
            <label class="ptb__ctrl">
              <span>{{ t('wizard.photo_toolbox.offset_x') }} <b>{{ offX }}</b></span>
              <input v-model.number="offX" type="range" min="-40" max="40" step="1" @input="render" />
            </label>
            <div class="ptb__locked-bg">{{ t('wizard.photo_toolbox.bg_locked') }}</div>
            <p class="ptb__note">{{ t('wizard.photo_toolbox.note') }}</p>
          </aside>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  canvasToJpegFile,
  loadImageFromFile,
  renderVisaPhoto,
  resolvePhotoSpec,
} from '@/utils/visaPhotoToolbox'

const props = defineProps({
  open: { type: Boolean, default: false },
  file: { type: File, default: null },
  countryCode: { type: String, default: '' },
})

const emit = defineEmits(['confirm', 'cancel'])

const { t } = useI18n()
const canvasEl = ref(null)
const sourceUrl = ref('')
const imgRef = ref(null)
const zoom = ref(1.08)
const offX = ref(0)
const offY = ref(-6)
const busy = ref(false)
const outMeta = ref('—')

const spec = computed(() => resolvePhotoSpec(props.countryCode))
const aspectRatio = computed(() => `${spec.value.mmW} / ${spec.value.mmH}`)
const subtitle = computed(() =>
  t('wizard.photo_toolbox.subtitle', {
    label: t(spec.value.labelKey),
    w: spec.value.mmW,
    h: spec.value.mmH,
  }),
)

let renderTimer = null

async function boot() {
  if (!props.file) return
  if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value)
  sourceUrl.value = URL.createObjectURL(props.file)
  imgRef.value = await loadImageFromFile(props.file)
  zoom.value = 1.08
  offX.value = 0
  offY.value = -6
  await nextTick()
  await render()
}

async function render() {
  if (!imgRef.value || !canvasEl.value) return
  const meta = await renderVisaPhoto(canvasEl.value, imgRef.value, spec.value, {
    zoom: zoom.value,
    offX: offX.value,
    offY: offY.value,
  })
  outMeta.value = `${meta.mmW}×${meta.mmH}mm`
}

function oneClick() {
  zoom.value = 1.08
  offX.value = 0
  offY.value = -6
  render()
}

async function onConfirm() {
  if (!canvasEl.value || busy.value) return
  busy.value = true
  try {
    const file = await canvasToJpegFile(canvasEl.value)
    emit('confirm', file)
  } finally {
    busy.value = false
  }
}

function onCancel() {
  emit('cancel')
}

watch(
  () => props.open,
  async (v) => {
    if (v) {
      document.body.style.overflow = 'hidden'
      await boot()
    } else {
      document.body.style.overflow = ''
      if (sourceUrl.value) {
        URL.revokeObjectURL(sourceUrl.value)
        sourceUrl.value = ''
      }
      imgRef.value = null
    }
  },
)

watch(
  () => [zoom.value, offX.value, offY.value],
  () => {
    if (!props.open) return
    clearTimeout(renderTimer)
    renderTimer = setTimeout(() => render(), 40)
  },
)

onBeforeUnmount(() => {
  clearTimeout(renderTimer)
  if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.ptb {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 16px;
  overflow: auto;
}
.ptb__panel {
  width: min(980px, 100%);
  background: #fff;
  border-radius: var(--radius-panel, 16px);
  padding: 20px 20px 24px;
  margin: 12px auto 40px;
  box-shadow: var(--shadow-overlay, 0 24px 56px rgba(15, 23, 42, .20));
}
.ptb__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.ptb__badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 4px 10px;
  margin-bottom: 8px;
}
.ptb__title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}
.ptb__sub {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.ptb__close {
  border: 0;
  background: #f1f5f9;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: #334155;
}
.ptb__grid {
  display: grid;
  grid-template-columns: 1.5fr 0.9fr;
  gap: 16px;
}
@media (max-width: 860px) {
  .ptb__grid { grid-template-columns: 1fr; }
}
.ptb__card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
}
.ptb__card h3 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.ptb__stage {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
@media (max-width: 640px) {
  .ptb__stage { grid-template-columns: 1fr; }
}
.ptb__pane {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  background: #f8fafc;
}
.ptb__pane-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
  padding: 8px 10px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}
.ptb__pane-body {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
}
.ptb__pane-body img {
  max-width: 100%;
  max-height: 280px;
  object-fit: contain;
}
.ptb__frame {
  position: relative;
  width: min(100%, 260px);
  aspect-ratio: var(--ar, 1 / 1);
  background: #fff;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  overflow: hidden;
}
.ptb__frame canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.ptb__guide {
  pointer-events: none;
  position: absolute;
  inset: 12% 18% 28%;
  border: 1px dashed rgba(37, 99, 235, 0.45);
  border-radius: 50% / 42%;
}
.ptb__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.ptb__btn {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #0f172a;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.ptb__btn--primary {
  background: var(--el-color-primary, #3B6EF5);
  border-color: var(--el-color-primary, #3B6EF5);
  color: #fff;
}
.ptb__btn--success {
  background: var(--el-color-primary, #3B6EF5);
  border-color: var(--el-color-primary, #3B6EF5);
  color: #fff;
}
.ptb__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.ptb__spec {
  font-size: 13px;
  color: #334155;
  line-height: 1.7;
  margin-bottom: 14px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 10px;
}
.ptb__ctrl {
  display: block;
  margin-bottom: 12px;
  font-size: 12px;
  color: #475569;
}
.ptb__ctrl span {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.ptb__ctrl input[type='range'] {
  width: 100%;
}
.ptb__locked-bg {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin: 8px 0;
}
.ptb__note {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}
</style>
