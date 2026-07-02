<!-- AdminCountries.vue — W35: 国家配置 -->
<template>
<main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.countries.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.countries.page_subtitle') }}</p>
        <div class="admin-main__actions">
          <button class="btn-primary" @click="openCreate">+ {{ t('admin.countries.create') }}</button>
        </div>
      </header>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <div v-else class="country-grid">
        <div
          v-for="c in countries"
          :key="c.id"
          class="country-card"
          :class="{ 'is-disabled': !c.enabled }"
          draggable="true"
          @dragstart="onDragStart(c, $event)"
          @dragover.prevent
          @drop="onDrop(c, $event)"
        >
          <div class="country-card__header">
            <span class="country-card__flag">{{ c.flag_emoji || '🏳️' }}</span>
            <span class="country-card__name">{{ c.name_zh || c.name }}</span>
            <span class="country-card__code">{{ c.code }}</span>
            <span class="country-card__handle" title="拖动排序">⋮⋮</span>
          </div>
          <div class="country-card__types">
            <span v-for="vt in (c.visa_types || [])" :key="vt" class="type-tag">{{ t(`admin.countries.type_${vt}`) }}</span>
          </div>
          <p v-if="c.description" class="country-card__desc">{{ c.description }}</p>
          <div class="country-card__footer">
            <label class="switch">
              <input type="checkbox" :checked="c.enabled" @change="toggle(c)" />
              <span class="slider"></span>
            </label>
            <span class="country-card__actions">
              <button class="btn-text" @click="openEdit(c)">{{ t('admin.countries.edit') }}</button>
              <button class="btn-text btn-text--danger" @click="confirmDelete(c)">{{ t('admin.countries.delete') }}</button>
            </span>
          </div>
        </div>
        <p v-if="!countries.length" class="empty">{{ t('admin.countries.empty') }}</p>
      </div>
    </main>

    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal__head">
            <h2>{{ editing ? t('admin.countries.modal_edit') : t('admin.countries.modal_create') }}</h2>
            <button class="modal__close" @click="closeModal">×</button>
          </div>
          <div class="modal__body">
            <div class="form-field"><label>{{ t('admin.countries.form_code') }} *</label><input v-model="form.code" class="form-input" :disabled="!!editing" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_name') }} *</label><input v-model="form.name" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_name_zh') }}</label><input v-model="form.name_zh" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_flag') }}</label><input v-model="form.flag_emoji" class="form-input" placeholder="🇺🇸" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_capital') }}</label><input v-model="form.capital_city" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_types') }}</label>
              <div class="perm-grid">
                <label class="perm-check"><input type="checkbox" value="tourism" v-model="form.visa_types" /> {{ t('admin.countries.type_tourism') }}</label>
              </div>
            </div>
            <div class="form-field"><label>{{ t('admin.countries.form_template') }}</label><input v-model="form.form_template_url" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_desc') }}</label><textarea v-model="form.description" class="form-input" rows="3"></textarea></div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="closeModal">{{ t('common.cancel') }}</button>
            <button class="btn-primary" @click="submit" :disabled="submitting">{{ submitting ? t('admin.saving') : t('common.confirm') }}</button>
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

const countries = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editing = ref(null)
const submitting = ref(false)
const dragSrc = ref(null)
const form = ref({ code: '', name: '', name_zh: '', flag_emoji: '🏳️', capital_city: '', visa_types: [], form_template_url: '', description: '', enabled: true })

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function load() {
  loading.value = true; error.value = ''
  try {
    const r = await http.get('/v2/admin/config/countries')
    countries.value = r.data?.data?.items || []
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

function openCreate() { editing.value = null; form.value = { code: '', name: '', name_zh: '', flag_emoji: '🏳️', capital_city: '', visa_types: ['tourism'], form_template_url: '', description: '', enabled: true }; showModal.value = true }
function openEdit(c) { editing.value = c; form.value = { ...c, visa_types: [...(c.visa_types || [])] }; showModal.value = true }
function closeModal() { showModal.value = false }

async function submit() {
  if (!form.value.code || !form.value.name) return
  submitting.value = true
  try {
    if (editing.value) await http.put(`/v2/admin/config/countries/${editing.value.id}`, form.value)
    else await http.post('/v2/admin/config/countries', form.value)
    closeModal(); await load()
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { submitting.value = false }
}

async function toggle(c) {
  try {
    await http.post(`/v2/admin/config/countries/${c.id}/toggle`, { enabled: !c.enabled })
    c.enabled = !c.enabled
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

async function confirmDelete(c) {
  if (!confirm(t('admin.countries.confirm_delete', { name: c.name }))) return
  try { await http.delete(`/v2/admin/config/countries/${c.id}`); await load() } catch (e) { alert(e.response?.data?.message || e.message) }
}

function onDragStart(c, e) { dragSrc.value = c; e.dataTransfer.effectAllowed = 'move' }
async function onDrop(target) {
  if (!dragSrc.value || dragSrc.value.id === target.id) return
  const src = dragSrc.value; dragSrc.value = null
  const srcIdx = countries.value.findIndex(c => c.id === src.id)
  const tgtIdx = countries.value.findIndex(c => c.id === target.id)
  if (srcIdx < 0 || tgtIdx < 0) return
  countries.value.splice(srcIdx, 1)
  countries.value.splice(tgtIdx, 0, src)
  const orders = countries.value.map((c, i) => ({ id: c.id, display_order: i }))
  try { await http.post('/v2/admin/config/countries/reorder', { orders }) } catch (e) { alert('排序失败') }
}


onMounted(load)
</script>

<style scoped>
.admin-main { padding: 24px; }
.country-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.country-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 14px 16px; cursor: grab; transition: box-shadow 0.2s; }
.country-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.country-card.is-disabled { opacity: 0.55; }
.country-card__header { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.country-card__flag { font-size: 22px; }
.country-card__name { font-size: 15px; font-weight: 600; flex: 1; }
.country-card__code { font-size: 11px; background: #f4f4f5; color: #909399; padding: 1px 6px; border-radius: 4px; }
.country-card__handle { color: #c0c4cc; cursor: grab; font-size: 14px; }
.country-card__types { display: flex; gap: 4px; margin-bottom: 8px; }
.type-tag { font-size: 11px; background: #ecf5ff; color: #409eff; padding: 1px 6px; border-radius: 3px; }
.country-card__desc { font-size: 12px; color: #909399; margin: 4px 0; line-height: 1.5; }
.country-card__footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.country-card__actions { display: flex; gap: 8px; }
.switch { position: relative; display: inline-block; width: 36px; height: 20px; }
.switch input { display: none; }
.slider { position: absolute; cursor: pointer; inset: 0; background: #dcdfe6; border-radius: 20px; transition: 0.3s; }
.slider::before { content: ''; position: absolute; width: 16px; height: 16px; left: 2px; top: 2px; background: #fff; border-radius: 50%; transition: 0.3s; }
.switch input:checked + .slider { background: #67c23a; }
.switch input:checked + .slider::before { transform: translateX(16px); }
.btn-primary { background: #409eff; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #fff; border: 1px solid #dcdfe6; color: #606266; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; font-size: 13px; }
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
.form-input:focus { outline: none; border-color: #409eff; }
.form-input:disabled { background: #f5f7fa; }
.perm-grid { display: flex; gap: 16px; }
.perm-check { display: flex; align-items: center; gap: 4px; font-size: 13px; cursor: pointer; }
.empty { color: #909399; text-align: center; padding: 32px; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>