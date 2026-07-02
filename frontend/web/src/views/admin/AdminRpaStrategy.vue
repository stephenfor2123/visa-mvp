<!-- AdminRpaStrategy.vue — W35: RPA 策略配置 -->
<template>
<div class="admin-rpa-strategy">
    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.rpa_strategy.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.rpa_strategy.page_subtitle') }}</p>
        <button class="btn-primary" @click="save" :disabled="saving">{{ saving ? t('admin.saving') : t('admin.rpa_strategy.save') }}</button>

      </header>

      <!-- Stats panel -->
      <section class="stats-row">
        <div class="stat-card"><div class="stat-num">{{ stats.today_visits || 0 }}</div><div class="stat-lbl">{{ t('admin.rpa_strategy.stat_visits') }}</div></div>
        <div class="stat-card"><div class="stat-num">{{ stats.queued_tasks || 0 }}</div><div class="stat-lbl">{{ t('admin.rpa_strategy.stat_queued') }}</div></div>
        <div class="stat-card"><div class="stat-num">{{ ((stats.failure_rate_24h || 0) * 100).toFixed(1) }}%</div><div class="stat-lbl">{{ t('admin.rpa_strategy.stat_fail') }}</div></div>
        <div class="stat-card"><div class="stat-num">{{ stats.active_accounts || 0 }}</div><div class="stat-lbl">{{ t('admin.rpa_strategy.stat_accounts') }}</div></div>
      </section>

      <!-- Config editor -->
      <section v-if="config" class="config-section">
        <h2>{{ t('admin.rpa_strategy.rate_limits') }}</h2>
        <div class="kv-grid">
          <div class="form-field"><label>ip_per_day</label><input v-model.number="config.rate_limits.ip_per_day" class="form-input" type="number" /></div>
          <div class="form-field"><label>account_interval_minutes</label><input v-model.number="config.rate_limits.account_interval_minutes" class="form-input" type="number" /></div>
          <div class="form-field"><label>off_peak_start</label><input v-model="config.rate_limits.off_peak_start" class="form-input" placeholder="00:00" /></div>
          <div class="form-field"><label>off_peak_end</label><input v-model="config.rate_limits.off_peak_end" class="form-input" placeholder="06:00" /></div>
          <div class="form-field"><label>max_concurrent_tasks</label><input v-model.number="config.rate_limits.max_concurrent_tasks" class="form-input" type="number" /></div>
        </div>

        <h2>{{ t('admin.rpa_strategy.polling') }}</h2>
        <div class="kv-grid">
          <div class="form-field"><label>polling_interval_seconds</label><input v-model.number="config.polling_interval_seconds" class="form-input" type="number" /></div>
          <div class="form-field"><label>session_ttl_minutes</label><input v-model.number="config.session_ttl_minutes" class="form-input" type="number" /></div>
        </div>

        <h2 v-if="config.captcha">{{ t('admin.rpa_strategy.captcha') }}</h2>
        <div v-if="config.captcha" class="kv-grid">
          <div class="form-field"><label>engine</label><input v-model="config.captcha.engine" class="form-input" /></div>
          <div class="form-field"><label>api_url</label><input v-model="config.captcha.api_url" class="form-input" /></div>
          <div class="form-field"><label>min_confidence</label><input v-model.number="config.captcha.min_confidence" class="form-input" type="number" step="0.05" /></div>
        </div>

        <h2 v-if="config.retry">{{ t('admin.rpa_strategy.retry') }}</h2>
        <div v-if="config.retry" class="kv-grid">
          <div class="form-field"><label>captcha_max_retries</label><input v-model.number="config.retry.captcha_max_retries" class="form-input" type="number" /></div>
          <div class="form-field"><label>page_max_retries</label><input v-model.number="config.retry.page_max_retries" class="form-input" type="number" /></div>
          <div class="form-field"><label>backoff_multiplier</label><input v-model.number="config.retry.backoff_multiplier" class="form-input" type="number" step="0.5" /></div>
          <div class="form-field"><label>initial_backoff_seconds</label><input v-model.number="config.retry.initial_backoff_seconds" class="form-input" type="number" /></div>
        </div>
      </section>

      <div v-else-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import axios from 'axios'

const { t } = useI18n()
const admin = useAdminStore()

const config = ref(null)
const stats = ref({})
const loading = ref(false)
const error = ref('')
const saving = ref(false)

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function load() {
  loading.value = true; error.value = ''
  try {
    const [c, s] = await Promise.all([
      http.get('/v2/admin/config/rpa'),
      http.get('/v2/admin/stats/rpa'),
    ])
    config.value = c.data?.data || {}
    stats.value = s.data?.data || {}
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

async function save() {
  saving.value = true
  try {
    await http.put('/v2/admin/config/rpa', config.value)
    alert(t('admin.rpa_strategy.saved'))
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { saving.value = false }
}


onMounted(load)
</script>

<style scoped>
.admin-main { padding: 24px; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.stat-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; text-align: center; }
.stat-num { font-size: 24px; font-weight: 600; color: #409eff; }
.stat-lbl { font-size: 12px; color: #909399; margin-top: 4px; }
.config-section { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; }
.config-section h2 { font-size: 15px; margin: 16px 0 12px; color: #606266; }
.config-section h2:first-child { margin-top: 0; }
.kv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.form-field label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; font-family: monospace; }
.form-input { width: 100%; box-sizing: border-box; border: 1px solid #dcdfe6; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.btn-primary { background: #409eff; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>