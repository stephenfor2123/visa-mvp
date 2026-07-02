<!-- AdminI18n.vue — W35: 语种资源 -->
<template>
<main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.i18n.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.i18n.page_subtitle') }}</p>
        <div class="admin-main__actions">
          <button class="btn-primary" @click="openCreate">+ {{ t('admin.i18n.create') }}</button>
          <button class="btn-secondary" @click="doExport">{{ t('admin.i18n.export') }}</button>
          <button class="btn-secondary" @click="showImport = true">{{ t('admin.i18n.import') }}</button>
        </div>
      </header>

      <div class="locale-tabs">
        <button v-for="l in locales" :key="l" class="locale-tab" :class="{ 'is-active': locale === l }" @click="setLocale(l)">{{ l }}</button>
      </div>

      <div class="filter-bar">
        <input v-model="search" class="form-input filter-input" :placeholder="t('admin.i18n.search_placeholder')" @input="reload" />
      </div>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <table v-else class="data-table">
        <thead><tr>
          <th>{{ t('admin.i18n.col_key') }}</th>
          <th>{{ t('admin.i18n.col_value') }}</th>
          <th>{{ t('admin.i18n.col_original') }}</th>
          <th>{{ t('admin.i18n.col_updated') }}</th>
          <th>{{ t('admin.orders.col_action') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="o in overrides" :key="o.id">
            <td><code>{{ o.key }}</code></td>
            <td>{{ o.value }}</td>
            <td class="muted">{{ o.original_value || '—' }}</td>
            <td>{{ fmtDate(o.updated_at) }}</td>
            <td>
              <button class="btn-text" @click="openEdit(o)">{{ t('admin.i18n.edit') }}</button>
              <button class="btn-text btn-text--danger" @click="del(o)">{{ t('admin.i18n.delete') }}</button>
            </td>
          </tr>
          <tr v-if="!overrides.length"><td colspan="5" class="empty">{{ t('admin.i18n.empty') }}</td></tr>
        </tbody>
      </table>
    </main>

    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal__head"><h2>{{ editing ? t('admin.i18n.modal_edit') : t('admin.i18n.modal_create') }}</h2><button class="modal__close" @click="closeModal">×</button></div>
          <div class="modal__body">
            <div class="form-field"><label>{{ t('admin.i18n.form_key') }} *</label><input v-model="form.key" class="form-input" :disabled="!!editing" /></div>
            <div class="form-field"><label>{{ t('admin.i18n.form_value') }} *</label><textarea v-model="form.value" class="form-input" rows="3"></textarea></div>
            <div class="form-field"><label>{{ t('admin.i18n.form_original') }}</label><input v-model="form.original_value" class="form-input" /></div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="closeModal">{{ t('common.cancel') }}</button>
            <button class="btn-primary" @click="submit" :disabled="submitting">{{ submitting ? t('admin.saving') : t('common.confirm') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Import modal -->
    <Teleport to="body">
      <div v-if="showImport" class="modal-overlay" @click.self="showImport = false">
        <div class="modal">
          <div class="modal__head"><h2>{{ t('admin.i18n.import_title') }}</h2><button class="modal__close" @click="showImport = false">×</button></div>
          <div class="modal__body">
            <div class="form-field"><label>locale</label><input v-model="importLocale" class="form-input" /></div>
            <div class="form-field"><label>JSON</label><textarea v-model="importJson" class="form-input" rows="10" placeholder='{"home.hero.title": "..."}'></textarea></div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="showImport = false">{{ t('common.cancel') }}</button>
            <button class="btn-primary" @click="doImport" :disabled="submitting">{{ submitting ? t('admin.saving') : t('admin.i18n.import') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import axios from 'axios'

const { t } = useI18n()
const admin = useAdminStore()

const locales = ['zh-CN', 'en', 'vi', 'id']
const locale = ref('zh-CN')
const search = ref('')
const overrides = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const showImport = ref(false)
const editing = ref(null)
const submitting = ref(false)
const importLocale = ref('en')
const importJson = ref('')
const form = ref({ key: '', value: '', original_value: '' })

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function reload() {
  loading.value = true; error.value = ''
  try {
    const params = new URLSearchParams({ page: '1', page_size: '100' })
    if (locale.value) params.set('locale', locale.value)
    if (search.value) params.set('q', search.value)
    const r = await http.get(`/v2/admin/i18n/overrides?${params.toString()}`)
    overrides.value = r.data?.data?.items || []
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

function setLocale(l) { locale.value = l; reload() }

function openCreate() { editing.value = null; form.value = { key: '', value: '', original_value: '' }; showModal.value = true }
function openEdit(o) { editing.value = o; form.value = { key: o.key, value: o.value, original_value: o.original_value || '' }; showModal.value = true }
function closeModal() { showModal.value = false }

async function submit() {
  if (!form.value.key || !form.value.value) return
  submitting.value = true
  try {
    const body = { locale: locale.value, key: form.value.key, value: form.value.value, original_value: form.value.original_value || null }
    if (editing.value) await http.put(`/v2/admin/i18n/overrides/${editing.value.id}`, body)
    else await http.post('/v2/admin/i18n/overrides', body)
    closeModal(); await reload()
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { submitting.value = false }
}

async function del(o) {
  if (!confirm(t('admin.i18n.confirm_delete', { key: o.key }))) return
  try { await http.delete(`/v2/admin/i18n/overrides/${o.id}`); await reload() } catch (e) { alert(e.response?.data?.message || e.message) }
}

async function doExport() {
  try {
    const r = await http.get(`/v2/admin/i18n/overrides/export?locale=${locale.value}`)
    const blob = new Blob([JSON.stringify(r.data?.data?.entries || {}, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = `i18n-${locale.value}.json`; a.click()
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

async function doImport() {
  submitting.value = true
  try {
    const entries = JSON.parse(importJson.value || '{}')
    await http.post('/v2/admin/i18n/overrides/import', { locale: importLocale.value, entries })
    showImport.value = false
    if (importLocale.value === locale.value) await reload()
    alert(t('admin.i18n.imported'))
  } catch (e) { alert(e.message) }
  finally { submitting.value = false }
}

function fmtDate(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso } }

onMounted(reload)
</script>

<style scoped>
.admin-main { padding: 24px; }
.locale-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.locale-tab { padding: 6px 16px; border: 1px solid #dcdfe6; background: #fff; border-radius: 6px; cursor: pointer; font-size: 13px; }
.locale-tab.is-active { background: #409eff; color: #fff; border-color: #409eff; }
.filter-bar { margin-bottom: 12px; }
.filter-input { max-width: 320px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 8px 10px; border-bottom: 1px solid #e4e7ed; font-size: 13px; text-align: left; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.muted { color: #909399; }
.btn-primary, .btn-secondary { padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; border: none; margin-right: 8px; }
.btn-primary { background: #409eff; color: #fff; }
.btn-secondary { background: #fff; border: 1px solid #dcdfe6; color: #606266; }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; font-size: 12px; padding: 0 4px; }
.btn-text--danger { color: #f56c6c; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 540px; max-width: 90vw; max-height: 85vh; overflow-y: auto; }
.modal__head, .modal__foot { padding: 14px 20px; }
.modal__head { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e4e7ed; }
.modal__head h2 { margin: 0; font-size: 16px; }
.modal__close { background: none; border: none; font-size: 22px; cursor: pointer; color: #909399; }
.modal__body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid #e4e7ed; }
.form-field label { display: block; font-size: 13px; color: #606266; margin-bottom: 4px; }
.form-input { width: 100%; box-sizing: border-box; border: 1px solid #dcdfe6; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.form-input:disabled { background: #f5f7fa; }
.empty { color: #909399; text-align: center; padding: 24px; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>