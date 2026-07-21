<!-- AdminPricing.vue — 全局默认价 + 按国家/签证类型单独定价 -->
<template>
  <main class="admin-main" data-testid="admin-pricing">
    <header class="admin-main__head">
      <h1>{{ t('admin.pricing.page_title', '价格与营销') }}</h1>
      <p class="admin-main__sub">
        {{ t('admin.pricing.page_subtitle_v2', '配置全局默认平台服务费，并为每个国家 / 签证类型单独设置价格与促销。') }}
      </p>
    </header>

    <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
    <div v-else-if="loadError" class="admin-error">{{ loadError }}</div>
    <template v-else>
      <!-- 全局默认 -->
      <section class="panel">
        <div class="panel__head">
          <h2>{{ t('admin.pricing.global_title', '全局默认价') }}</h2>
          <span class="panel__hint">{{ t('admin.pricing.global_hint', '未单独配置的国家将回退到此价格') }}</span>
        </div>
        <div class="preview-card preview-card--compact">
          <span v-if="globalPreview.is_promo" class="preview-price__list">${{ fmt(globalPreview.list_price_usd) }}</span>
          <span class="preview-price__current">${{ fmt(globalPreview.display_price_usd) }}</span>
          <span v-if="globalPreview.is_promo" class="preview-badge">{{ t('admin.pricing.badge_promo', '促销中') }}</span>
        </div>
        <form class="pricing-form" @submit.prevent="submitGlobal">
          <div class="form-grid">
            <div class="form-field">
              <label>{{ t('admin.pricing.field_list', '划线价（原价）') }}</label>
              <div class="input-prefix">
                <span>$</span>
                <input v-model.number="globalForm.list_price_usd" type="number" step="0.01" min="0.01" class="form-input" required />
              </div>
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_promo', '促销价') }}</label>
              <div class="input-prefix">
                <span>$</span>
                <input v-model.number="globalForm.promo_price_usd" type="number" step="0.01" min="0.01" class="form-input" required />
              </div>
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_starts', '促销开始') }}</label>
              <input v-model="globalForm.promo_starts_at" type="datetime-local" class="form-input" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_ends', '促销结束') }}</label>
              <input v-model="globalForm.promo_ends_at" type="datetime-local" class="form-input" />
            </div>
          </div>
          <div class="form-field">
            <label class="switch-row">
              <input v-model="globalForm.promo_enabled" type="checkbox" />
              <span>{{ t('admin.pricing.field_enabled', '启用促销') }}</span>
            </label>
          </div>
          <div class="form-field">
            <label>{{ t('admin.pricing.field_note', '内部备注') }}</label>
            <textarea v-model="globalForm.marketing_note" class="form-input" rows="2" />
          </div>
          <p v-if="globalSaveError" class="form-error">{{ globalSaveError }}</p>
          <p v-if="globalSaveOk" class="form-ok">{{ t('admin.pricing.save_ok', '已保存') }}</p>
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="reload">{{ t('admin.pricing.reset', '重新加载') }}</button>
            <button type="submit" class="btn-primary" :disabled="globalSaving">
              {{ globalSaving ? t('admin.saving', '保存中…') : t('admin.pricing.save_global', '保存全局默认') }}
            </button>
          </div>
        </form>
      </section>

      <!-- 国家 × 签证类型 -->
      <section class="panel">
        <div class="panel__head">
          <h2>{{ t('admin.pricing.dest_title', '国家 / 签证定价') }}</h2>
          <span class="panel__hint">{{ t('admin.pricing.dest_hint', '点击行即可编辑；继承 = 尚未单独配置，下单时用全局默认') }}</span>
        </div>

        <div class="table-wrap">
          <table class="price-table">
            <thead>
              <tr>
                <th>{{ t('admin.pricing.col_country', '国家') }}</th>
                <th>{{ t('admin.pricing.col_visa', '签证类型') }}</th>
                <th>{{ t('admin.pricing.col_list', '划线价') }}</th>
                <th>{{ t('admin.pricing.col_promo', '促销价') }}</th>
                <th>{{ t('admin.pricing.col_display', '当前展示') }}</th>
                <th>{{ t('admin.pricing.col_status', '状态') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in items"
                :key="`${row.country_code}-${row.visa_type}`"
                :class="{ 'is-active': editingKey === rowKey(row) }"
              >
                <td>
                  <strong>{{ row.country_name || row.country_code }}</strong>
                  <span class="mono">{{ row.country_code }}</span>
                </td>
                <td>{{ row.visa_type }}</td>
                <td>${{ fmt(row.list_price_usd) }}</td>
                <td>${{ fmt(row.promo_price_usd) }}</td>
                <td>
                  <strong :class="{ promo: row.is_promo }">${{ fmt(row.display_price_usd) }}</strong>
                </td>
                <td>
                  <span v-if="row.inherited" class="tag tag--muted">{{ t('admin.pricing.tag_inherited', '继承全局') }}</span>
                  <span v-else-if="row.is_promo" class="tag tag--promo">{{ t('admin.pricing.badge_promo', '促销中') }}</span>
                  <span v-else class="tag">{{ t('admin.pricing.badge_regular', '常规定价') }}</span>
                </td>
                <td>
                  <button type="button" class="btn-link" @click="startEdit(row)">
                    {{ t('admin.pricing.edit', '编辑') }}
                  </button>
                </td>
              </tr>
              <tr v-if="!items.length">
                <td colspan="7" class="empty">{{ t('admin.pricing.empty_dest', '暂无启用中的国家，请先在「国家配置」启用目的地') }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="editForm" class="edit-drawer">
          <h3>
            {{ t('admin.pricing.edit_title', '编辑定价') }}
            — {{ editForm.country_name || editForm.country_code }} / {{ editForm.visa_type }}
          </h3>
          <div class="form-grid">
            <div class="form-field">
              <label>{{ t('admin.pricing.field_list', '划线价（原价）') }}</label>
              <div class="input-prefix">
                <span>$</span>
                <input v-model.number="editForm.list_price_usd" type="number" step="0.01" min="0.01" class="form-input" />
              </div>
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_promo', '促销价') }}</label>
              <div class="input-prefix">
                <span>$</span>
                <input v-model.number="editForm.promo_price_usd" type="number" step="0.01" min="0.01" class="form-input" />
              </div>
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_starts', '促销开始') }}</label>
              <input v-model="editForm.promo_starts_at" type="datetime-local" class="form-input" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.pricing.field_ends', '促销结束') }}</label>
              <input v-model="editForm.promo_ends_at" type="datetime-local" class="form-input" />
            </div>
          </div>
          <div class="form-field">
            <label class="switch-row">
              <input v-model="editForm.promo_enabled" type="checkbox" />
              <span>{{ t('admin.pricing.field_enabled', '启用促销') }}</span>
            </label>
          </div>
          <div class="form-field">
            <label>{{ t('admin.pricing.field_note', '内部备注') }}</label>
            <textarea v-model="editForm.marketing_note" class="form-input" rows="2" />
          </div>
          <p v-if="editError" class="form-error">{{ editError }}</p>
          <p v-if="editOk" class="form-ok">{{ t('admin.pricing.save_ok', '已保存') }}</p>
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="cancelEdit">{{ t('common.cancel', '取消') }}</button>
            <button type="button" class="btn-primary" :disabled="editSaving" @click="submitEdit">
              {{ editSaving ? t('admin.saving', '保存中…') : t('admin.pricing.save', '保存定价') }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import {
  listDestinationPricingAdmin,
  updatePlatformPricingAdmin,
  upsertDestinationPricingAdmin,
} from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const loading = ref(true)
const loadError = ref('')
const items = ref([])
const globalForm = reactive({
  list_price_usd: 99.9,
  promo_price_usd: 19.9,
  currency: 'USD',
  promo_enabled: true,
  promo_starts_at: '',
  promo_ends_at: '',
  marketing_note: '',
})
const globalSaving = ref(false)
const globalSaveError = ref('')
const globalSaveOk = ref(false)

const editForm = ref(null)
const editingKey = ref('')
const editSaving = ref(false)
const editError = ref('')
const editOk = ref(false)

const globalPreview = computed(() => previewOf(globalForm))

function previewOf(form) {
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
}

function rowKey(row) {
  return `${row.country_code}|${row.visa_type}`
}

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

function applyGlobal(data) {
  if (!data) return
  globalForm.list_price_usd = Number(data.list_price_usd)
  globalForm.promo_price_usd = Number(data.promo_price_usd)
  globalForm.currency = data.currency || 'USD'
  globalForm.promo_enabled = Boolean(data.promo_enabled)
  globalForm.promo_starts_at = toLocalInput(data.promo_starts_at)
  globalForm.promo_ends_at = toLocalInput(data.promo_ends_at)
  globalForm.marketing_note = data.marketing_note || ''
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await listDestinationPricingAdmin()
    applyGlobal(data.global_pricing)
    items.value = data.items || []
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function submitGlobal() {
  globalSaving.value = true
  globalSaveError.value = ''
  globalSaveOk.value = false
  try {
    if (globalForm.promo_price_usd >= globalForm.list_price_usd) {
      throw new Error(t('admin.pricing.err_promo_gt_list', '促销价必须低于划线价'))
    }
    const body = {
      list_price_usd: globalForm.list_price_usd,
      promo_price_usd: globalForm.promo_price_usd,
      currency: globalForm.currency,
      promo_enabled: globalForm.promo_enabled,
      promo_starts_at: toIsoLocal(globalForm.promo_starts_at),
      promo_ends_at: toIsoLocal(globalForm.promo_ends_at),
      marketing_note: globalForm.marketing_note || null,
    }
    applyGlobal(await updatePlatformPricingAdmin(body))
    globalSaveOk.value = true
    await reload()
  } catch (e) {
    globalSaveError.value = e?.message || String(e)
  } finally {
    globalSaving.value = false
  }
}

function startEdit(row) {
  editingKey.value = rowKey(row)
  editOk.value = false
  editError.value = ''
  editForm.value = {
    country_code: row.country_code,
    country_name: row.country_name,
    visa_type: row.visa_type,
    list_price_usd: Number(row.list_price_usd),
    promo_price_usd: Number(row.promo_price_usd),
    currency: row.currency || 'USD',
    promo_enabled: Boolean(row.promo_enabled),
    promo_starts_at: toLocalInput(row.promo_starts_at),
    promo_ends_at: toLocalInput(row.promo_ends_at),
    marketing_note: row.marketing_note || '',
  }
}

function cancelEdit() {
  editForm.value = null
  editingKey.value = ''
  editError.value = ''
  editOk.value = false
}

async function submitEdit() {
  if (!editForm.value) return
  editSaving.value = true
  editError.value = ''
  editOk.value = false
  try {
    if (editForm.value.promo_price_usd >= editForm.value.list_price_usd) {
      throw new Error(t('admin.pricing.err_promo_gt_list', '促销价必须低于划线价'))
    }
    const body = {
      country_code: editForm.value.country_code,
      visa_type: editForm.value.visa_type,
      list_price_usd: editForm.value.list_price_usd,
      promo_price_usd: editForm.value.promo_price_usd,
      currency: editForm.value.currency,
      promo_enabled: editForm.value.promo_enabled,
      promo_starts_at: toIsoLocal(editForm.value.promo_starts_at),
      promo_ends_at: toIsoLocal(editForm.value.promo_ends_at),
      marketing_note: editForm.value.marketing_note || null,
    }
    const saved = await upsertDestinationPricingAdmin(body)
    const idx = items.value.findIndex((r) => rowKey(r) === rowKey(saved))
    if (idx >= 0) items.value[idx] = { ...items.value[idx], ...saved, inherited: false }
    editOk.value = true
  } catch (e) {
    editError.value = e?.message || String(e)
  } finally {
    editSaving.value = false
  }
}

function fmt(n) {
  const v = Number(n)
  return Number.isNaN(v) ? '—' : (v % 1 === 0 ? v.toFixed(0) : v.toFixed(2))
}

onMounted(() => { admin.hydrate(); reload() })
</script>

<style scoped>
.admin-main { padding: 24px 32px; max-width: 1080px; }
.admin-main__head { margin-bottom: 20px; }
.admin-main__head h1 { margin: 0 0 6px; font-size: 22px; color: #0f172a; }
.admin-main__sub { margin: 0; font-size: 13px; color: #64748b; }
.admin-loading, .admin-error { padding: 24px; text-align: center; color: #64748b; }
.admin-error { color: #dc2626; }

.panel {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 20px 24px; margin-bottom: 20px;
}
.panel__head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.panel__head h2 { margin: 0; font-size: 16px; color: #0f172a; }
.panel__hint { font-size: 12px; color: #94a3b8; }

.preview-card {
  background: linear-gradient(135deg, #eff6ff 0%, #fff 100%);
  border: 1px solid #bfdbfe; border-radius: 10px;
  padding: 14px 18px; margin-bottom: 16px;
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
}
.preview-price__list { font-size: 18px; color: #94a3b8; text-decoration: line-through; font-weight: 600; }
.preview-price__current { font-size: 28px; font-weight: 800; color: #1d4ed8; }
.preview-badge {
  font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px;
  background: #fef3c7; color: #b45309;
}

.pricing-form { margin-top: 4px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px; }
.form-field { margin-bottom: 12px; }
.form-field label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; }
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
.btn-primary, .btn-secondary, .btn-link {
  border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-primary { background: #3b6ef5; color: #fff; border: none; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary { background: #fff; border: 1px solid #e2e8f0; color: #475569; }
.btn-link { background: none; border: none; color: #3b6ef5; padding: 4px 8px; }

.table-wrap { overflow-x: auto; }
.price-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.price-table th, .price-table td {
  text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: middle;
}
.price-table th { font-size: 12px; color: #64748b; font-weight: 600; background: #f8fafc; }
.price-table tr.is-active { background: #eff6ff; }
.price-table .mono { display: block; font-size: 11px; color: #94a3b8; font-weight: 500; }
.price-table .promo { color: #1d4ed8; }
.price-table .empty { text-align: center; color: #94a3b8; padding: 28px; }
.tag {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 999px; background: #f1f5f9; color: #64748b;
}
.tag--promo { background: #fef3c7; color: #b45309; }
.tag--muted { background: #f1f5f9; color: #94a3b8; }

.edit-drawer {
  margin-top: 16px; padding: 16px 18px;
  border: 1px solid #bfdbfe; border-radius: 10px; background: #f8fbff;
}
.edit-drawer h3 { margin: 0 0 12px; font-size: 14px; color: #0f172a; }

@media (max-width: 720px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
