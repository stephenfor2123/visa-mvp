<!-- AdminCleanup.vue — W35: 文件清理 / 72h 注销清理 -->
<template>
<main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.cleanup.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.cleanup.page_subtitle') }}</p>
      </header>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <div v-else-if="stats" class="cleanup-grid">
        <!-- 2026-07-07: 临时文件 + 归档合并为一个"清理缓存"按钮, 阈值在后端配置 -->
        <div class="cleanup-card">
          <h3>{{ t('admin.cleanup.cache_files') }}</h3>
          <div class="cleanup-stat">
            <span class="num">{{ (stats.temp_candidates || 0) + (stats.archive_candidates || 0) }}</span>
            <span class="lbl">{{ t('admin.cleanup.candidates') }}</span>
          </div>
          <p class="muted">{{ t('admin.cleanup.cache_hint') }}</p>
          <button class="btn-danger" :disabled="running.cache" @click="run('cache')">
            {{ running.cache ? t('admin.saving') : t('admin.cleanup.run') }}
          </button>
          <div v-if="results.cache" class="result">
            {{ t('admin.cleanup.result_deleted') }}: {{ results.cache.deleted_count }} ({{ Math.round((results.cache.freed_bytes || 0) / 1024) }} KB, {{ results.cache.duration_ms }} ms)
          </div>
        </div>

        <div class="cleanup-card">
          <h3>{{ t('admin.cleanup.pending_destroys') }}</h3>
          <div class="cleanup-stat">
            <span class="num">{{ stats.pending_destroy_users }}</span>
            <span class="lbl">{{ t('admin.cleanup.candidates') }}</span>
          </div>
          <p class="muted">{{ t('admin.cleanup.destroy_hint') }}</p>
          <button class="btn-danger" :disabled="running.destroy" @click="run('destroy')">
            {{ running.destroy ? t('admin.saving') : t('admin.cleanup.run') }}
          </button>
          <div v-if="results.destroy" class="result">
            {{ t('admin.cleanup.result_deleted') }}: {{ results.destroy.deleted_count }} ({{ results.destroy.duration_ms }} ms)
          </div>
        </div>
      </div>

      <section v-if="stats" class="storage-section">
        <h2>{{ t('admin.cleanup.storage_title') }}</h2>
        <div class="storage-bar">
          <div class="storage-num">{{ Math.round((stats.storage_bytes || 0) / 1024 / 1024 * 100) / 100 }} MB</div>
          <div class="storage-lbl">{{ t('admin.cleanup.storage_lbl') }}</div>
        </div>
      </section>
    </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import axios from 'axios'

const { t } = useI18n()
const admin = useAdminStore()

const stats = ref(null)
const loading = ref(false)
const error = ref('')
const results = ref({ temp: null, archive: null, destroy: null })
const running = ref({ temp: false, archive: false, destroy: false })

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function load() {
  loading.value = true; error.value = ''
  try {
    const r = await http.get('/v2/admin/cleanup/stats')
    stats.value = r.data?.data
  } catch (e) { error.value = e.response?.data?.message || e.message }
  finally { loading.value = false }
}

async function run(kind) {
  if (!confirm(t('admin.cleanup.confirm_run', { kind: t(`admin.cleanup.${kind}`) }))) return
  running.value[kind] = true
  const url = kind === 'cache'
    ? '/v2/admin/cleanup/cache-files'
    : '/v2/admin/cleanup/pending-destroys'
  try {
    const r = await http.post(url)
    results.value[kind] = r.data?.data
    await load()
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { running.value[kind] = false }
}


onMounted(load)
</script>

<style scoped>
.admin-main { padding: 24px; }
.cleanup-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.cleanup-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; }
.cleanup-card h3 { margin: 0 0 12px; font-size: 15px; }
.cleanup-stat { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.cleanup-stat .num { font-size: 32px; font-weight: 600; color: #409eff; }
.cleanup-stat .lbl { font-size: 12px; color: #909399; }
.muted { color: #909399; font-size: 12px; margin: 4px 0 12px; }
.btn-danger { background: #f56c6c; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
.result { margin-top: 10px; padding: 8px 10px; background: #f0f9eb; color: #67c23a; border-radius: 6px; font-size: 12px; }
.storage-section { margin-top: 24px; background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; }
.storage-section h2 { margin: 0 0 12px; font-size: 15px; }
.storage-bar { display: flex; align-items: baseline; gap: 12px; }
.storage-num { font-size: 24px; font-weight: 600; }
.storage-lbl { font-size: 12px; color: #909399; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>