<!-- AdminPricing.vue — 平台服务费 + 促销定价 -->
<template>
  <main class="admin-main" data-testid="admin-pricing">
    <header class="admin-main__head">
      <h1>{{ t('admin.pricing.page_title') }}</h1>
      <p class="admin-main__sub">{{ t('admin.pricing.page_subtitle') }}</p>
    </header>

    <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
    <div v-else-if="loadError" class="admin-error">{{ loadError }}</div>
    <template v-else>
      <!-- 实时预览 -->
      <section class="preview-card">
        <h3>{{ t('admin.pricing.preview_title') }}</h3>
        <div class="preview-price">
          <span v-if="preview.is_promo" class="preview-price__list">${{ fmt(preview.list_price_usd) }}</span>
          <span class="preview-price__current">${{ fmt(preview.display_price_usd) }}</span>
          <span v-if="preview.is_promo" class="preview-badge">{{ t('admin.pricing.badge_promo') }}</span>
          <span v-else class="preview-badge preview-badge--regular">{{ t('admin.pricing.badge_regular') }}</span>
        </div>
        <p class="preview-meta">
          <template v-if="form.promo_enabled && form.promo_starts_at && form.promo_ends_at">
            {{ t('admin.pricing.preview_window', { start: fmtDate(form.promo_starts_at), end: fmtDate(form.promo_ends_at) }) }}
          </template>
          <template v-else>{{ t('admin.pricing.preview_no_window') }}</template>
        </p>
      </section>

      <form class="pricing-form" @submit.prevent="submit">
        <div class="form-grid">
          <div class="form-field">
            <label>{{ t('admin.pricing.field_list') }}</label>
            <div class="input-prefix">
              <span>$</span>
              <input v-model.number="form.list_price_usd" type="number" step="0.01" min="0.01" class="form-input" required />
            </div>
            <p class="field-hint">{{ t('admin.pricing.hint_list') }}</p>
          </div>
          <div class="form-field">
            <label>{{ t('admin.pricing.field_promo') }}</label>
            <div class="input-prefix">
              <span>$</span>
              <input v-model.number="form.promo_price_usd" type="number" step="0.01" min="0.01" class="form-input" required />
            </div>
            <p class="field-hint">{{ t('admin.pricing.hint_promo') }}</p>
          </div>
          <div class="form-field">
            <label>{{ t('admin.pricing.field_starts') }}</label>
            <input v-model="form.promo_starts_at" type="datetime-local" class="form-input" />
          </div>
          <div class="form-field">
            <label>{{ t('admin.pricing.field_ends') }}</label>
            <input v-model="form.promo_ends_at" type="datetime-local" class="form-input" />
          </div>
        </div>

        <div class="form-field">
          <label class="switch-row">
            <input v-model="form.promo_enabled" type="checkbox" />
            <span>{{ t('admin.pricing.field_enabled') }}</span>
          </label>
        </div>

        <div class="form-field">
          <label>{{ t('admin.pricing.field_note') }}</label>
          <textarea v-model="form.marketing_note" class="form-input" rows="2" :placeholder="t('admin.pricing.note_placeholder')" />
        </div>

        <p v-if="saveError" class="form-error">{{ saveError }}</p>
        <p v-if="saveOk" class="form-ok">{{ t('admin.pricing.save_ok') }}</p>

        <div class="form-actions">
          <button type="button" class="btn-secondary" @click="reload">{{ t('admin.pricing.reset') }}</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? t('admin.saving') : t('admin.pricing.save') }}
          </button>
        </div>
      </form>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import { getPlatformPricingAdmin, updatePlatformPricingAdmin } from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const saveOk = ref(false)
const snapshot = ref(null)

const form = reactive({
  list_price_usd: 99.9,
  promo_price_usd: 19.9,
  currency: 'USD',
  promo_enabled: true,
  promo_starts_at: '',
  promo_ends_at: '',
  marketing_note: '',
})

const preview = computed(() => {
  const list = Number(form.list_price_usd) || 0
  const promo = Number(form.promo_price_usd) || 0
  const now = Date.now()
  const start = form.promo_starts_at ? new Date(form.promo_starts_at).getTime() : NaN
  const end = form.promo_ends_at ? new Date(form.promo_ends_at).getTime() : NaN
  const inWindow = form.promo_enabled && !Number.isNaN(start) && !Number.isNaN(end) && now >= start && now <= end
  const isPromo = inWindow && promo > 0 && promo < list
  return {
    list_price_usd: list,
    display_price_usd: isPromo ? promo : list,
    is_promo: isPromo,
  }
})

function toLocalInput(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return ''
  }
}

function toIsoLocal(local) {
  if (!local) return null
  try {
    return new Date(local).toISOString()
  } catch {
    return null
  }
}

function applyData(data) {
  snapshot.value = data
  form.list_price_usd = Number(data.list_price_usd)
  form.promo_price_usd = Number(data.promo_price_usd)
  form.currency = data.currency || 'USD'
  form.promo_enabled = Boolean(data.promo_enabled)
  form.promo_starts_at = toLocalInput(data.promo_starts_at)
  form.promo_ends_at = toLocalInput(data.promo_ends_at)
  form.marketing_note = data.marketing_note || ''
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    applyData(await getPlatformPricingAdmin())
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function submit() {
  saving.value = true
  saveError.value = ''
  saveOk.value = false
  try {
    if (form.promo_price_usd >= form.list_price_usd) {
      throw new Error(t('admin.pricing.err_promo_gt_list'))
    }
    const body = {
      list_price_usd: form.list_price_usd,
      promo_price_usd: form.promo_price_usd,
      currency: form.currency,
      promo_enabled: form.promo_enabled,
      promo_starts_at: toIsoLocal(form.promo_starts_at),
      promo_ends_at: toIsoLocal(form.promo_ends_at),
      marketing_note: form.marketing_note || null,
    }
    applyData(await updatePlatformPricingAdmin(body))
    saveOk.value = true
  } catch (e) {
    saveError.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

function fmt(n) {
  const v = Number(n)
  return v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)
}

function fmtDate(local) {
  if (!local) return '—'
  try { return new Date(local).toLocaleString('zh-CN', { hour12: false }) } catch { return local }
}

onMounted(() => { admin.hydrate(); reload() })
</script>

<style scoped>
.admin-main { padding: 24px 32px; max-width: 720px; }
.admin-main__head { margin-bottom: 24px; }
.admin-main__head h1 { margin: 0 0 6px; font-size: 22px; color: #0f172a; }
.admin-main__sub { margin: 0; font-size: 13px; color: #64748b; }
.admin-loading, .admin-error { padding: 24px; text-align: center; color: #64748b; }
.admin-error { color: #dc2626; }

.preview-card {
  background: linear-gradient(135deg, #eff6ff 0%, #fff 100%);
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 28px;
}
.preview-card h3 { margin: 0 0 12px; font-size: 14px; color: #475569; font-weight: 600; }
.preview-price { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.preview-price__list {
  font-size: 20px; color: #94a3b8; text-decoration: line-through; font-weight: 600;
}
.preview-price__current { font-size: 32px; font-weight: 800; color: #1d4ed8; }
.preview-badge {
  font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px;
  background: #fef3c7; color: #b45309;
}
.preview-badge--regular { background: #f1f5f9; color: #64748b; }
.preview-meta { margin: 10px 0 0; font-size: 12px; color: #64748b; }

.pricing-form { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.form-field { margin-bottom: 14px; }
.form-field label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; }
.field-hint { margin: 4px 0 0; font-size: 11px; color: #94a3b8; }
.form-input {
  width: 100%; box-sizing: border-box;
  border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 8px 12px; font-size: 14px;
}
.input-prefix { display: flex; align-items: center; gap: 8px; }
.input-prefix span { color: #64748b; font-weight: 600; }
.input-prefix .form-input { flex: 1; }
.switch-row { display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 500; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px; }
.form-error { color: #dc2626; font-size: 13px; }
.form-ok { color: #047857; font-size: 13px; }
.btn-primary, .btn-secondary {
  border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-primary { background: #3b6ef5; color: #fff; border: none; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary { background: #fff; border: 1px solid #e2e8f0; color: #475569; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
