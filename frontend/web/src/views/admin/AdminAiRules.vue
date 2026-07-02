<!-- AdminAiRules.vue — W35: AI 校验规则 -->
<template>
<div class="admin-ai-rules">
    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.ai_rules.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.ai_rules.page_subtitle') }}</p>
      </header>
      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>{{ t('admin.ai_rules.col_code') }}</th>
            <th>{{ t('admin.ai_rules.col_name') }}</th>
            <th>{{ t('admin.ai_rules.col_operator') }}</th>
            <th>{{ t('admin.ai_rules.col_threshold') }}</th>
            <th>{{ t('admin.ai_rules.col_severity') }}</th>
            <th>{{ t('admin.ai_rules.col_country') }}</th>
            <th>{{ t('admin.ai_rules.col_enabled') }}</th>
            <th>{{ t('admin.ai_rules.col_updated') }}</th>
            <th>{{ t('admin.orders.col_action') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rules" :key="r.id || r.rule_code">
            <td><code>{{ r.rule_code }}</code></td>
            <td>{{ r.rule_name || '—' }}</td>
            <td><code>{{ r.operator }}</code></td>
            <td>{{ formatThreshold(r.threshold) }}</td>
            <td><span class="sev-pill" :class="`sev-${r.severity}`">{{ t(`admin.ai_rules.sev_${r.severity}`) }}</span></td>
            <td>{{ r.country_code || 'ALL' }}</td>
            <td>
              <label class="switch"><input type="checkbox" :checked="r.enabled" @change="toggle(r)" /><span class="slider"></span></label>
            </td>
            <td>{{ fmtDate(r.updated_at) }}</td>
            <td>
              <button class="btn-text" @click="openTest(r)">{{ t('admin.ai_rules.test') }}</button>
              <button class="btn-text" @click="openHistory(r)">{{ t('admin.ai_rules.history') }}</button>
            </td>
          </tr>
          <tr v-if="!rules.length"><td colspan="9" class="empty">{{ t('admin.ai_rules.empty') }}</td></tr>
        </tbody>
      </table>
    </main>

    <!-- Test modal -->
    <Teleport to="body">
      <div v-if="testRule" class="modal-overlay" @click.self="testRule = null">
        <div class="modal modal--sm">
          <div class="modal__head"><h2>{{ t('admin.ai_rules.test_title') }}</h2><button class="modal__close" @click="testRule = null">×</button></div>
          <div class="modal__body">
            <p><code>{{ testRule.rule_code }}</code> ({{ testRule.operator }})</p>
            <div class="form-field">
              <label>{{ t('admin.ai_rules.test_sample') }}</label>
              <input v-model="testValue" class="form-input" :placeholder="String(testRule.threshold || '')" />
            </div>
            <div v-if="testResult" class="test-result" :class="testResult.matched ? 'matched' : 'not-matched'">
              <div>{{ t('admin.ai_rules.test_matched') }}: <b>{{ testResult.matched }}</b></div>
              <div>{{ t('admin.ai_rules.test_severity') }}: {{ testResult.severity }}</div>
              <div v-if="testResult.message">{{ testResult.message }}</div>
            </div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="testRule = null">{{ t('common.cancel') }}</button>
            <button class="btn-primary" @click="runTest">{{ t('admin.ai_rules.run_test') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- History modal -->
    <Teleport to="body">
      <div v-if="historyRule" class="modal-overlay" @click.self="historyRule = null">
        <div class="modal">
          <div class="modal__head"><h2>{{ t('admin.ai_rules.history_title') }}: {{ historyRule.rule_code }}</h2><button class="modal__close" @click="historyRule = null">×</button></div>
          <div class="modal__body">
            <ul class="history-list">
              <li v-for="h in history" :key="h.id">
                <div class="hl-time">{{ fmtDate(h.created_at) }}</div>
                <div class="hl-meta">{{ h.action }} by {{ h.actor_type }}#{{ h.actor_id }}</div>
                <pre v-if="h.payload" class="hl-payload">{{ h.payload }}</pre>
              </li>
              <li v-if="!history.length" class="empty">{{ t('admin.ai_rules.no_history') }}</li>
            </ul>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

const { t } = useI18n()

const rules = ref([])
const loading = ref(false)
const error = ref('')
const testRule = ref(null)
const testValue = ref('')
const testResult = ref(null)
const historyRule = ref(null)
const history = ref([])

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function load() {
  loading.value = true; error.value = ''
  try {
    const r = await http.get('/v2/admin/config/validation-rules')
    rules.value = r.data?.data || []
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

function openTest(r) { testRule.value = r; testValue.value = ''; testResult.value = null }
async function runTest() {
  if (!testRule.value) return
  try {
    const r = await http.post('/v2/admin/config/validation-rules/test', { rule_code: testRule.value.rule_code, sample_value: testValue.value })
    testResult.value = r.data?.data
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

async function openHistory(r) {
  historyRule.value = r; history.value = []
  try {
    const res = await http.get(`/v2/admin/config/validation-rules/${encodeURIComponent(r.rule_code)}/history`)
    history.value = res.data?.data || []
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

async function toggle(r) {
  try {
    const list = rules.value.map(x => ({ ...x, enabled: x.rule_code === r.rule_code ? !r.enabled : x.enabled }))
    await http.put('/v2/admin/config/validation-rules', { rules: list })
    r.enabled = !r.enabled
  } catch (e) { alert(e.response?.data?.message || e.message) }
}

function formatThreshold(v) {
  if (v == null) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
function fmtDate(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso } }

onMounted(load)
</script>

<style scoped>
.admin-main { padding: 24px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 8px 10px; border-bottom: 1px solid #e4e7ed; font-size: 13px; text-align: left; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.sev-pill { font-size: 11px; padding: 2px 6px; border-radius: 3px; }
.sev-pill.sev-block { background: #fef0f0; color: #f56c6c; }
.sev-pill.sev-warn { background: #fdf6ec; color: #e6a23c; }
.sev-pill.sev-info { background: #ecf5ff; color: #409eff; }
.switch { position: relative; display: inline-block; width: 32px; height: 18px; }
.switch input { display: none; }
.slider { position: absolute; cursor: pointer; inset: 0; background: #dcdfe6; border-radius: 18px; }
.slider::before { content: ''; position: absolute; width: 14px; height: 14px; left: 2px; top: 2px; background: #fff; border-radius: 50%; transition: 0.3s; }
.switch input:checked + .slider { background: #67c23a; }
.switch input:checked + .slider::before { transform: translateX(14px); }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; font-size: 12px; padding: 0 4px; }
.btn-primary, .btn-secondary { padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; border: none; }
.btn-primary { background: #409eff; color: #fff; }
.btn-secondary { background: #fff; border: 1px solid #dcdfe6; color: #606266; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 540px; max-width: 90vw; max-height: 85vh; overflow-y: auto; }
.modal--sm { width: 420px; }
.modal__head, .modal__foot { padding: 14px 20px; }
.modal__head { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e4e7ed; }
.modal__head h2 { margin: 0; font-size: 16px; }
.modal__close { background: none; border: none; font-size: 22px; cursor: pointer; color: #909399; }
.modal__body { padding: 20px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid #e4e7ed; }
.form-field label { display: block; font-size: 13px; color: #606266; margin-bottom: 4px; }
.form-input { width: 100%; box-sizing: border-box; border: 1px solid #dcdfe6; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.test-result { padding: 10px; border-radius: 6px; font-size: 13px; margin-top: 12px; }
.test-result.matched { background: #fef0f0; color: #f56c6c; }
.test-result.not-matched { background: #f0f9eb; color: #67c23a; }
.history-list { list-style: none; padding: 0; margin: 0; }
.history-list li { padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.hl-time { color: #909399; font-size: 12px; }
.hl-meta { color: #606266; margin: 2px 0; }
.hl-payload { background: #f5f7fa; padding: 6px 8px; border-radius: 4px; font-size: 12px; overflow: auto; }
.empty { color: #909399; text-align: center; padding: 24px; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>