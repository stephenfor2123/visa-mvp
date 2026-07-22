<!-- AdminCountries.vue — W35: 国家配置 -->
<template>
<main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.countries.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.countries.page_subtitle') }}</p>
        <p class="admin-main__hint">关闭开关后，首页与办签证入口将不再展示该国家。</p>
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
            <span class="country-card__name">{{ c.country_name_zh || c.country_name_en }}</span>
            <span class="region-tag">{{ regionFor(c.country_code) }}</span>
            <span class="country-card__code">{{ c.country_code }}</span>
            <span class="country-card__handle" title="拖动排序">⋮⋮</span>
          </div>
          <div class="country-card__types">
            <span v-for="vt in supportedVisaTypes(c.visa_types)" :key="vt" class="type-tag">{{ t(`admin.countries.type_${vt}`) }}</span>
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
            <div class="form-field"><label>{{ t('admin.countries.form_code') }} *</label><input v-model="form.country_code" class="form-input" :disabled="!!editing" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_name') }} *</label><input v-model="form.country_name_en" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_name_zh') }}</label><input v-model="form.country_name_zh" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_flag') }}</label><input v-model="form.flag_emoji" class="form-input" placeholder="🇺🇸" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_capital') }}</label><input v-model="form.capital_city" class="form-input" /></div>
            <div class="form-field"><label>{{ t('admin.countries.form_types') }}</label>
              <div class="perm-grid">
                <label class="perm-check"><input type="checkbox" value="tourism" v-model="form.visa_types" /> {{ t('admin.countries.type_tourism') }}</label>
                <span class="form-help">当前产品仅支持旅游签证；历史签种数据会保留但不再提供新增入口。</span>
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
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { adminRegionFor as regionFor, supportedAdminVisaTypes as supportedVisaTypes } from '@/utils/adminDisplay'

const { t } = useI18n()

const countries = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editing = ref(null)
const submitting = ref(false)
const dragSrc = ref(null)
const emptyForm = () => ({
  country_code: '',
  country_name_en: '',
  country_name_zh: '',
  flag_emoji: '🏳️',
  capital_city: '',
  visa_types: ['tourism'],
  form_template_url: '',
  description: '',
  enabled: true,
})
const form = ref(emptyForm())

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

function openCreate() { editing.value = null; form.value = emptyForm(); showModal.value = true }
function openEdit(c) {
  editing.value = c
  form.value = {
    country_code: c.country_code,
    country_name_en: c.country_name_en,
    country_name_zh: c.country_name_zh,
    flag_emoji: c.flag_emoji || '🏳️',
    capital_city: c.capital_city || '',
    visa_types: supportedVisaTypes(c.visa_types),
    form_template_url: c.form_template_url || '',
    description: c.description || '',
    enabled: c.enabled,
  }
  showModal.value = true
}
function closeModal() { showModal.value = false }

async function submit() {
  if (!form.value.country_code || !form.value.country_name_en) return
  submitting.value = true
  try {
    const payload = {
      country_code: form.value.country_code,
      country_name_en: form.value.country_name_en,
      country_name_zh: form.value.country_name_zh || form.value.country_name_en,
      flag_emoji: form.value.flag_emoji,
      capital_city: form.value.capital_city || null,
      visa_types: supportedVisaTypes(form.value.visa_types),
      form_template_url: form.value.form_template_url || null,
      description: form.value.description || null,
      enabled: form.value.enabled,
    }
    if (editing.value) {
      const { country_code, ...updatePayload } = payload
      await http.put(`/v2/admin/config/countries/${editing.value.id}`, updatePayload)
    } else {
      await http.post('/v2/admin/config/countries', payload)
    }
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
  if (!confirm(t('admin.countries.confirm_delete', { name: c.country_name_zh || c.country_name_en }))) return
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
.country-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.country-card { background: var(--admin-card-bg, #fff); border: 1px solid var(--admin-border, #e5e7eb); border-radius: 12px; padding: 16px; transition: opacity .2s; }
.country-card.is-disabled { opacity: .45; }
.country-card__header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.country-card__flag { font-size: 1.5rem; }
.country-card__name { font-weight: 600; flex: 1; }
.country-card__code { font-size: .75rem; color: #9ca3af; font-family: monospace; }
.region-tag { font-size: .68rem; color: #475569; background: #F1F5F9; padding: 2px 6px; border-radius: 999px; }
.form-help { color: #64748B; font-size: .78rem; }
.country-card__handle { cursor: grab; color: #d1d5db; }
.country-card__types { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.type-tag { font-size: .7rem; background: #eff6ff; color: #1d4ed8; padding: 2px 8px; border-radius: 999px; }
.country-card__desc { font-size: .8rem; color: #6b7280; margin: 0 0 12px; }
.country-card__footer { display: flex; align-items: center; justify-content: space-between; }
.country-card__actions { display: flex; gap: 8px; }
.btn-text { background: none; border: none; color: #3b82f6; cursor: pointer; font-size: .85rem; }
.btn-text--danger { color: #ef4444; }
.switch { position: relative; display: inline-block; width: 40px; height: 22px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; inset: 0; background: #d1d5db; border-radius: 22px; transition: .2s; }
.slider::before { content: ''; position: absolute; width: 16px; height: 16px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: .2s; }
.switch input:checked + .slider { background: #3b82f6; }
.switch input:checked + .slider::before { transform: translateX(18px); }
.empty { grid-column: 1 / -1; text-align: center; color: #9ca3af; padding: 40px; }
.admin-main__hint { margin: 0 0 12px; font-size: .85rem; color: #6b7280; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 90%; max-width: 480px; max-height: 90vh; overflow-y: auto; }
.modal__head { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e7eb; }
.modal__head h2 { margin: 0; font-size: 1.1rem; }
.modal__close { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #9ca3af; }
.modal__body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 20px; border-top: 1px solid #e5e7eb; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: .8rem; font-weight: 500; color: #374151; }
.form-input { padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: .9rem; }
.perm-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.perm-check { display: flex; align-items: center; gap: 4px; font-size: .85rem; }
</style>
