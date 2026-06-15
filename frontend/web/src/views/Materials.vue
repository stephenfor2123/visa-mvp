<template>
  <div class="mat-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
        <span v-if="auth.user" class="app-header__user">👋 {{ auth.user.nickname || auth.user.phone }}</span>
      </div>
    </header>

    <main class="mat-shell">
      <h1 class="page-title">{{ t('materials.title') }}</h1>
      <p class="page-sub">{{ t('materials.subtitle') }}</p>

      <!-- 3 tab entries -->
      <div class="mat-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="mat-tab"
          :class="{ on: activeTab === tab.key }"
          :data-testid="`mat-tab-${tab.key}`"
          role="tab"
          :aria-selected="activeTab === tab.key"
          @click="onTabClick(tab)"
        >
          <span class="mat-tab__icon">{{ tab.icon }}</span>
          <span class="mat-tab__label">{{ t(tab.label) }}</span>
        </button>
      </div>

      <!-- Uploader (photo/PDF/WebP) -->
      <div v-if="activeTab === 'pdf'" class="mat-uploader-wrap" data-testid="mat-uploader-wrap">
        <MaterialUploader
          @uploaded="onUploaded"
          data-testid="mat-uploader"
        />
      </div>

      <!-- Audio recording -->
      <div v-if="activeTab === 'voice'" class="mat-voice" data-testid="mat-voice-panel">
        <VoiceRecorder
          :default-lang="voiceLang"
          :max-seconds="60"
          :i18n-lang="currentI18nLang"
          @recognized="onVoiceRecognized"
          @error="onVoiceError"
          data-testid="mat-voice-recorder"
        />
      </div>

      <!-- Collected list -->
      <section class="mat-list-section" data-testid="mat-list-section">
        <header class="mat-list-section__head">
          <h2>{{ t('materials.collected_count', { n: items.length }) }}</h2>
          <span v-if="lastValidated" class="mat-list-section__badge">
            ✓ {{ t('materials.validated_ok') }}
          </span>
        </header>

        <div v-if="loading" class="state-loading">⏳ {{ t('common.loading') }}</div>
        <div v-else-if="items.length === 0" class="mat-empty" data-testid="mat-empty">
          <div class="mat-empty__icon">📂</div>
          <p>{{ t('materials.empty') }}</p>
          <AppButton ref="emptyCtaBtnRef" variant="primary" size="md" data-testid="mat-empty-cta">
            {{ t('materials.add_first') }}
          </AppButton>
        </div>

        <div v-else class="mat-list">
          <AppCard
            v-for="m in items"
            :key="m.id || m.material_id"
            class="mat-item"
            :data-testid="`mat-item-${m.material_id || m.id}`"
          >
            <div class="mat-item__row">
              <div class="mat-item__thumb">
                <img
                  v-if="m.thumbnail_url"
                  :src="m.thumbnail_url"
                  :alt="t('materials.thumb_alt')"
                />
                <div v-else class="mat-item__thumb-fallback">📄</div>
              </div>
              <div class="mat-item__meta">
                <div class="mat-item__name">{{ m.file_name || `${m.material_type}.jpg` }}</div>
                <div class="mat-item__sub">
                  <span class="tag tag--type">{{ t(`materials.type_${m.material_type}`) }}</span>
                  <span class="mat-item__size">{{ formatSize(m.file_size) }}</span>
                </div>
                <div class="mat-item__status">
                  <span class="badge" :class="ocrBadgeClass(m.ocr_status)">
                    {{ ocrLabel(m.ocr_status) }}
                  </span>
                </div>
              </div>
              <button
                class="mat-item__del"
                @click="onDelete(m)"
                :data-testid="`mat-del-${m.material_id || m.id}`"
                aria-label="delete"
              >🗑</button>
            </div>
          </AppCard>
        </div>
      </section>

      <!-- Submit validation -->
      <footer v-if="items.length > 0" class="mat-foot">
        <AppButton
          ref="validateBtnRef"
          variant="primary"
          size="lg"
          :loading="validating"
          :disabled="items.length === 0"
          data-testid="mat-validate-btn"
        >
          {{ validating ? t('materials.validating_btn') : t('materials.validate_btn') }}
        </AppButton>

        <!-- After validation: jump to /orders/new to create order (Story 1.2.1b) -->
        <AppButton
          v-if="lastValidated"
          ref="continueFormBtnRef"
          variant="outline"
          size="lg"
          data-testid="mat-continue-form-btn"
        >
          {{ t('orders.btn_continue') }} →
        </AppButton>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppButton from '@/components/AppButton.vue'
import MaterialUploader from '@/components/MaterialUploader.vue'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import {
  uploadMaterial,
  listMaterials,
  deleteMaterial,
  validateMaterials,
  getAcceptTypes,
  getMaterialTypeOptions,
  clearMockDb
} from '@/api/materials'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()

const tabs = [
  { key: 'photo', label: t('materials.tab_photo'), icon: '📷' },
  { key: 'pdf', label: t('materials.tab_pdf'), icon: '📄' },
  { key: 'voice', label: t('materials.tab_voice'), icon: '🎙' }
]
const activeTab = ref('photo')
const items = ref([])
const loading = ref(false)
const validating = ref(false)
const lastValidated = ref(false)
const selectedType = ref(route.query.type || 'passport')

const currentI18nLang = computed(() => String(locale.value || ''))
const voiceLang = computed(() => {
  const l = String(locale.value || '').toLowerCase()
  if (l.startsWith('zh')) return 'zh-CN'
  if (l.startsWith('id')) return 'id'
  if (l.startsWith('vi')) return 'vi'
  return 'en'
})

// W4 P0 root-fix: ref + setOnTrigger pattern (reuse W3 A-3.1.1a)
// 3 AppButtons all v-if conditional mount, need watch trigger + nextTick inject
const emptyCtaBtnRef = ref(null)
const validateBtnRef = ref(null)
const continueFormBtnRef = ref(null)



function formatSize(b) {
  if (!b || b <= 0) return ''
  if (b > 1024 * 1024) return (b / (1024 * 1024)).toFixed(1) + ' MB'
  return Math.round(b / 1024) + ' KB'
}

function ocrLabel(status) {
  if (status === 'done') return t('materials.ocr_done')
  if (status === 'processing') return t('materials.ocr_processing')
  if (status === 'failed') return t('materials.ocr_failed')
  return t('materials.ocr_pending')
}
function ocrBadgeClass(status) {
  if (status === 'done') return 'badge--success'
  if (status === 'processing') return 'badge--info'
  if (status === 'failed') return 'badge--error'
  return 'badge--warning'
}

function onTabClick(tab) {
  activeTab.value = tab.key
  if (tab.key === 'photo') {
    // Jump to scan page (W2 internal route, query pass-through orderNo/country)
    const params = new URLSearchParams()
    if (route.query.orderNo) params.set('orderNo', route.query.orderNo)
    if (route.query.country) params.set('country', route.query.country)
    if (selectedType.value) params.set('type', selectedType.value)
    const qs = params.toString()
    window.location.href = `/materials/scan${qs ? '?' + qs : ''}`
  } else if (tab.key === 'pdf') {
    // MaterialUploader handles file picking
  }
  // voice tab operates inside panel
}

function onUploaded(material) {
  // MaterialUploader emitted — add to list + show toast
  items.value.unshift(material)
  toast.success(`✓ ${material.file_name}`)
}

function toggleRecord() {
  // Kept for backwards compat — no-op now, VoiceRecorder handles UI.
}

function startRecord() {
  // Kept for backwards compat — no-op now, VoiceRecorder handles UI.
}

function stopRecord() {
  // Kept for backwards compat — no-op now, VoiceRecorder handles UI.
}

/**
 * VoiceRecorder emitted a successful recognition result.
 * W14-5: push a virtual material card with the parsed fields so the
 * user can immediately see the auto-filled applicant info.
 */
function onVoiceRecognized(payload) {
  if (!payload) return
  const id = 'mat_voice_' + Date.now()
  const mat = {
    id,
    material_id: id,
    material_type: selectedType.value,
    file_name: `voice_${id.slice(-6)}.${(payload.mime_type || 'audio/webm').split('/')[1]?.split(';')[0] || 'webm'}`,
    file_size: payload.audio_bytes || 0,
    mime_type: payload.mime_type || 'audio/webm',
    thumbnail_url: `https://placehold.co/200x240/EAF0FE/2D5BFF?text=VOICE`,
    ocr_status: 'done',
    classification: {
      transcript: payload.raw_text,
      lang: payload.lang,
      engine: payload.engine,
      confidence: payload.confidence,
      fields: {
        name: payload.name,
        address: payload.address,
        travel_date: payload.travel_date
      }
    },
    created_at: new Date().toISOString()
  }
  items.value.unshift(mat)
  // Also stash the editable fields on a window-scoped bag so the order
  // form can read them without a full prop-drill.
  try {
    window.__visaVoiceFields = {
      name: payload.name,
      address: payload.address,
      travel_date: payload.travel_date
    }
  } catch (e) {
    // ignore (SSR / non-browser)
  }
  toast.success(
    `✓ ${t('materials.voice_apply')} · ${payload.name || t('materials.voice_field_name_ph')}`
  )
}

function onVoiceError(err) {
  console.warn('[voice] recognize failed:', err)
  toast.error(err?.message || t('materials.voice_hint_error'))
}

async function refresh() {
  loading.value = true
  try {
    const list = await listMaterials({ orderNo: route.query.orderNo || null })
    items.value = list
  } catch (e) {
    console.warn('[materials] refresh failed:', e?.message)
    items.value = []
  } finally {
    loading.value = false
  }
}

async function onDelete(m) {
  const id = m.id || m.material_id
  try {
    await deleteMaterial(id)
    toast.info(`🗑 ${m.file_name}`)
    await refresh()
  } catch (e) {
    toast.error(e?.message || 'delete failed')
  }
}

async function onValidate() {
  validating.value = true
  try {
    const ids = items.value.map((m) => m.id || m.material_id).filter(Boolean)
    if (ids.length === 0) return
    const result = await validateMaterials(ids)
    lastValidated.value = true
    const { pass = 0, warning = 0, error = 0 } = result.summary || {}
    toast.success(`✓ ${t('materials.validated_ok')} · pass=${pass} warn=${warning} err=${error}`)
  } catch (e) {
    toast.error(e?.message || 'validate failed')
  } finally {
    validating.value = false
  }
}

function goToForm() {
  const ids = items.value.map((m) => m.id || m.material_id).filter(Boolean)
  const params = new URLSearchParams()
  if (ids.length) params.set('material_ids', ids.join(','))
  if (route.query.country) params.set('country', route.query.country)
  if (route.query.visa_type) params.set('visa_type', route.query.visa_type)
  router.push({ name: 'OrderNew', query: Object.fromEntries(params.entries()) })
}

onMounted(async () => {
  auth.hydrate()
  // demo fallback: when no materials, inject 2 mocks so screenshots show card style
  // (B 1.1.1a not yet live, VITE_MOCK=false will also return empty)
  await refresh()
  if (items.value.length === 0) {
    const sample = [
      {
        id: 'mat_demo_passport',
        material_id: 'mat_demo_passport',
        material_type: 'passport',
        file_name: 'passport_E1234567.jpg',
        file_size: 412 * 1024,
        mime_type: 'image/jpeg',
        thumbnail_url: 'https://placehold.co/200x240/EAF0FE/2D5BFF?text=PASSPORT',
        ocr_status: 'done',
        created_at: new Date(Date.now() - 1000 * 60 * 8).toISOString()
      },
      {
        id: 'mat_demo_photo',
        material_id: 'mat_demo_photo',
        material_type: 'photo',
        file_name: 'visa_photo_2inch.jpg',
        file_size: 280 * 1024,
        mime_type: 'image/jpeg',
        thumbnail_url: 'https://placehold.co/200x240/FEF3C7/B45309?text=PHOTO',
        ocr_status: 'processing',
        created_at: new Date(Date.now() - 1000 * 60 * 3).toISOString()
      }
    ]
    items.value = sample
  }
})

// 3 AppButtons all v-if conditional mount, each watch + nextTick inject trigger
// Empty state CTA: mounts when items.length === 0
watch(
  () => items.value.length === 0,
  async (val) => {
    if (val) {
      await nextTick()
      if (emptyCtaBtnRef.value) emptyCtaBtnRef.value.setOnTrigger(() => onTabClick(tabs[0]))
    }
  }
)
// Validate button: mounts when items.length > 0
watch(
  () => items.value.length > 0,
  async (val) => {
    if (val) {
      await nextTick()
      if (validateBtnRef.value) validateBtnRef.value.setOnTrigger(onValidate)
    }
  }
)
// Continue form button: mounts when lastValidated=true
watch(lastValidated, async (val) => {
  if (val) {
    await nextTick()
    if (continueFormBtnRef.value) continueFormBtnRef.value.setOnTrigger(goToForm)
  }
})
</script>

<style scoped lang="scss">
.mat-page { min-height: 100vh; background: var(--bg, #FAFBFC); }
.mat-shell { max-width: 960px; margin: 0 auto; padding: 24px; }
.page-title { font-size: 28px; font-weight: 600; margin: 0 0 6px; color: var(--ink, #1A1D29); }
.page-sub { color: var(--ink-2, #5A5F6D); margin: 0 0 24px; font-size: 14px; }

.mat-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.mat-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 18px 14px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2, #334155);
  cursor: pointer;
  transition: all .15s;
}
.mat-tab:hover {
  border-color: #3B6EF5;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 110, 245, .12);
}
.mat-tab.on {
  border-color: #3B6EF5;
  background: #EAF0FE;
  color: #2D5BFF;
  font-weight: 600;
}
.mat-tab__icon { font-size: 28px; }
.mat-tab__label { font-size: 13px; }

.mat-file-hidden { display: none; }

.mat-uploader-wrap { margin-bottom: 24px; }

.mat-voice {
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  padding: 28px;
  text-align: center;
  margin-bottom: 24px;
}
.mat-voice__btn {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}
.mat-voice__mic {
  width: 80px; height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3B6EF5, #6E59F0);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 32px;
  box-shadow: 0 8px 20px rgba(59,110,245,.3);
  transition: transform .15s;
}
.mat-voice__btn:hover .mat-voice__mic { transform: scale(1.05); }
.mat-voice__btn.recording .mat-voice__mic {
  background: #DC2626;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,.5); }
  50% { box-shadow: 0 0 0 16px rgba(220,38,38,0); }
}
.mat-voice__label { font-size: 14px; font-weight: 500; color: var(--ink-2, #334155); }
.mat-voice__tip { margin: 14px 0 0; font-size: 12px; color: var(--ink-3, #64748B); }
.mat-voice__text {
  margin: 16px auto 0;
  max-width: 480px;
  padding: 12px 14px;
  background: #F0FDF4;
  border: 1px solid #86EFAC;
  border-radius: 8px;
  font-size: 14px;
  color: #166534;
  text-align: left;
  line-height: 1.6;
}

.mat-list-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  h2 { margin: 0; font-size: 16px; font-weight: 600; color: var(--ink-1, #0F172A); }
}
.mat-list-section__badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #DCFCE7;
  color: #166534;
  font-weight: 500;
}

.state-loading { padding: 40px; text-align: center; color: var(--muted, #9CA3AF); }

.mat-empty {
  text-align: center;
  padding: 60px 20px;
  background: #fff;
  border: 1px dashed var(--border, #E2E8F0);
  border-radius: 12px;
  color: var(--ink-3, #64748B);
}
.mat-empty__icon { font-size: 48px; margin-bottom: 8px; }
.mat-empty p { margin: 0 0 16px; font-size: 14px; }

.mat-list {
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr;
}
@media (min-width: 720px) {
  .mat-list { grid-template-columns: 1fr 1fr; }
}

.mat-item__row {
  display: flex;
  gap: 14px;
  align-items: center;
}
.mat-item__thumb {
  flex-shrink: 0;
  width: 72px; height: 88px;
  border-radius: 8px;
  overflow: hidden;
  background: #F1F5F9;
  display: flex; align-items: center; justify-content: center;
}
.mat-item__thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.mat-item__thumb-fallback { font-size: 32px; color: var(--muted, #94A3B8); }
.mat-item__meta { flex: 1; min-width: 0; }
.mat-item__name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-1, #0F172A);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mat-item__sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: #EAF0FE;
  color: #2D5BFF;
}
.mat-item__status { margin-top: 6px; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}
.badge--success { background: #DCFCE7; color: #166534; }
.badge--warning { background: #FEF3C7; color: #B45309; }
.badge--info    { background: #DBEAFE; color: #1E40AF; }
.badge--error   { background: #FEE2E2; color: #B91C1C; }

.mat-item__del {
  background: transparent;
  border: none;
  color: var(--muted, #94A3B8);
  font-size: 18px;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  flex-shrink: 0;
}
.mat-item__del:hover { background: #FEE2E2; color: #B91C1C; }

.mat-foot {
  margin-top: 28px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}
.mat-foot .app-btn { min-width: 200px; }

@media (max-width: 600px) {
  .mat-shell { padding: 16px; }
  .mat-tabs { grid-template-columns: 1fr; }
}
</style>