<!-- AdminLogs.vue — W35: 系统日志 -->
<template>
<main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.logs.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.logs.page_subtitle_admin_only') }}</p>
      </header>

      <div class="filter-bar">
        <select v-model="filter.actor_type" class="form-input" @change="reload">
          <option value="">{{ t('admin.logs.all_actor_types') }}</option>
          <option value="admin">admin</option>
          <option value="user">user</option>
          <option value="system">system</option>
          <option value="rpa">rpa</option>
        </select>
        <select v-model="filter.action" class="form-input" @change="reload">
          <option value="">{{ t('admin.logs.all_actions') }}</option>
          <option v-for="a in actionList" :key="a" :value="a">{{ formatAuditAction({ action: a }) }}</option>
        </select>
        <input v-model="filter.target_type" class="form-input" placeholder="target_type" @change="reload" />
        <button class="btn-secondary" @click="reset">{{ t('admin.logs.reset') }}</button>
      </div>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <table v-else class="data-table">
        <thead><tr>
          <th>ID</th>
          <th>{{ t('admin.logs.col_time') }}</th>
          <th>{{ t('admin.logs.col_actor') }}</th>
          <th>{{ t('admin.logs.col_action') }}</th>
          <th>{{ t('admin.logs.col_target') }}</th>
          <th>IP</th>
        </tr></thead>
        <tbody>
          <tr v-for="l in logs" :key="l.id" @click="open(l)" class="clickable">
            <td>{{ l.id }}</td>
            <td>{{ fmtDate(l.created_at) }}</td>
            <td><span class="actor-pill" :class="`actor-${l.actor_type}`">{{ l.actor_type }}</span> #{{ l.actor_id || '—' }}</td>
            <td><code>{{ formatAuditAction(l) }}</code><span class="muted action-code">{{ l.action }}</span></td>
            <td>{{ l.target_type || '—' }}{{ l.target_id ? `#${l.target_id}` : '' }}</td>
            <td class="muted">{{ l.ip || '—' }}</td>
          </tr>
          <tr v-if="!logs.length"><td colspan="6" class="empty">{{ t('admin.logs.empty') }}</td></tr>
        </tbody>
      </table>
    </main>

    <Teleport to="body">
      <div v-if="detail" class="drawer-overlay" @click.self="detail = null">
        <div class="drawer">
          <div class="drawer__head">
            <h2>{{ t('admin.logs.detail_title') }} #{{ detail.id }}</h2>
            <button class="modal__close" @click="detail = null">×</button>
          </div>
          <div class="drawer__body">
            <div class="kv"><label>{{ t('admin.logs.col_time') }}</label><span>{{ fmtDate(detail.created_at) }}</span></div>
            <div class="kv"><label>actor</label><span>{{ detail.actor_type }} #{{ detail.actor_id }}</span></div>
            <div class="kv"><label>action</label><span><code>{{ formatAuditAction(detail) }}</code> <span class="muted">({{ detail.action }})</span></span></div>
            <div class="kv"><label>target</label><span>{{ detail.target_type || '—' }} {{ detail.target_id ? `#${detail.target_id}` : '' }}</span></div>
            <div class="kv"><label>IP</label><span>{{ detail.ip || '—' }}</span></div>
            <div class="kv"><label>UA</label><span class="muted">{{ detail.ua || '—' }}</span></div>
            <div class="kv"><label>payload</label><pre class="payload">{{ formatPayload(detail.payload) }}</pre></div>
          </div>
        </div>
      </div>
    </Teleport>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

import { formatAuditAction } from '@/utils/auditActionLabels'

const { t } = useI18n()

const logs = ref([])
const actionList = ref([])
const loading = ref(false)
const error = ref('')
const detail = ref(null)
const filter = ref({ actor_type: '', action: '', target_type: '' })

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function reload() {
  loading.value = true; error.value = ''
  try {
    const params = new URLSearchParams({ page: '1', page_size: '50' })
    if (filter.value.actor_type) params.set('actor_type', filter.value.actor_type)
    if (filter.value.action) params.set('action', filter.value.action)
    if (filter.value.target_type) params.set('target_type', filter.value.target_type)
    const r = await http.get(`/v2/admin/logs?${params.toString()}`)
    logs.value = r.data?.data?.items || []
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

async function loadActions() {
  try {
    const r = await http.get('/v2/admin/logs/actions')
    actionList.value = r.data?.data || []
  } catch {}
}

async function open(l) {
  try {
    const r = await http.get(`/v2/admin/logs/${l.id}`)
    detail.value = r.data?.data
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

function reset() { filter.value = { actor_type: '', action: '', target_type: '' }; reload() }
function fmtDate(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso } }
function formatPayload(p) {
  if (!p) return '—'
  try { return JSON.stringify(JSON.parse(p), null, 2) } catch { return p }
}

onMounted(() => { reload(); loadActions() })
</script>

<style scoped>
.admin-main { padding: 24px; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.filter-bar .form-input { width: auto; min-width: 140px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 8px 10px; border-bottom: 1px solid #e4e7ed; font-size: 13px; text-align: left; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.data-table tr.clickable { cursor: pointer; }
.data-table tr.clickable:hover { background: #f5f7fa; }
.actor-pill { font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.actor-pill.actor-user { background: #ecf5ff; color: #409eff; }
.actor-pill.actor-admin { background: #f0f9eb; color: #67c23a; }
.actor-pill.actor-system { background: #f4f4f5; color: #909399; }
.actor-pill.actor-rpa { background: #fdf6ec; color: #e6a23c; }
.btn-secondary { background: #fff; border: 1px solid #dcdfe6; color: #606266; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.form-input { border: 1px solid #dcdfe6; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.muted { color: #909399; }
.action-code { display: block; font-size: 11px; margin-top: 2px; }
.drawer-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 1000; display: flex; justify-content: flex-end; }
.drawer { background: #fff; width: 560px; max-width: 100vw; height: 100vh; overflow-y: auto; }
.drawer__head { padding: 16px 20px; border-bottom: 1px solid #e4e7ed; display: flex; justify-content: space-between; align-items: center; }
.drawer__head h2 { margin: 0; font-size: 16px; }
.drawer__body { padding: 20px; }
.drawer__body .kv { margin-bottom: 12px; }
.drawer__body .kv label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.drawer__body .kv span { font-size: 13px; }
.payload { background: #f5f7fa; padding: 10px; border-radius: 6px; font-size: 12px; max-height: 200px; overflow: auto; margin: 0; }
.modal__close { background: none; border: none; font-size: 22px; cursor: pointer; color: #909399; }
.empty { color: #909399; text-align: center; padding: 24px; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>