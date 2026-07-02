<!-- AdminCUserDetail.vue — W35: C 端用户详情页 -->
<template>
<div class="admin-c-user-detail" data-testid="admin-c-user-detail">

    <main class="admin-main">
      <header class="admin-main__head">
        <button class="btn-text" @click="$router.push('/admin/c-users')">{{ t('admin.c_users.back_to_list') }}</button>
        <h1>{{ t('admin.c_users.detail_title') }}</h1>
      </header>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <template v-else-if="user">
        <section class="detail-section">
          <h2>{{ t('admin.c_users.section_basic') }}</h2>
          <div class="kv-grid">
            <div class="kv"><label>{{ t('admin.c_users.col_username') }}</label><span>{{ user.username || '—' }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_email') }}</label><span>{{ user.email || '—' }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_phone') }}</label><span>{{ user.phone || '—' }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_status') }}</label>
              <span class="status-pill" :class="`is-${user.status}`">{{ t(`admin.c_users.status_${user.status}`) }}</span>
            </div>
            <div class="kv"><label>{{ t('admin.c_users.col_language') }}</label><span>{{ user.language_pref || 'zh-CN' }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_mfa') }}</label><span>{{ user.mfa_enabled ? t('admin.c_users.mfa_on') : t('admin.c_users.mfa_off') }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_created') }}</label><span>{{ fmtDate(user.created_at) }}</span></div>
            <div class="kv"><label>{{ t('admin.c_users.col_last_login') }}</label><span>{{ fmtDate(user.last_login_at) || '—' }}</span></div>
          </div>
          <div class="actions">
            <button v-if="user.status === 'active'" class="btn-danger" @click="disableUser" :disabled="submitting">{{ t('admin.c_users.disable') }}</button>
            <button v-if="user.status === 'disabled'" class="btn-primary" @click="restoreUser" :disabled="submitting">{{ t('admin.c_users.restore') }}</button>
            <button class="btn-secondary" @click="resetPwd" :disabled="submitting">{{ t('admin.c_users.reset_password') }}</button>
          </div>
          <div v-if="newPassword" class="alert-success">
            {{ t('admin.c_users.new_password_label') }}: <code>{{ newPassword }}</code>
            <span class="alert-hint">{{ t('admin.c_users.new_password_hint') }}</span>
          </div>
        </section>

        <section class="detail-section">
          <h2>{{ t('admin.c_users.section_orders') }}</h2>
          <table v-if="orders.length" class="data-table">
            <thead><tr>
              <th>{{ t('admin.orders.col_order') }}</th>
              <th>{{ t('admin.orders.col_amount') }}</th>
              <th>{{ t('admin.orders.col_status') }}</th>
              <th>{{ t('admin.orders.col_created') }}</th>
            </tr></thead>
            <tbody><tr v-for="o in orders" :key="o.id">
              <td>{{ o.order_no }}</td>
              <td>{{ o.total_amount }} {{ o.currency }}</td>
              <td>{{ o.status }}</td>
              <td>{{ fmtDate(o.created_at) }}</td>
            </tr></tbody>
          </table>
          <p v-else class="empty">{{ t('admin.c_users.no_orders') }}</p>
        </section>
</template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { adminHttp } from '@/api/admin' // Use authed admin instance
import axios from 'axios'

const { t } = useI18n()
const route = useRoute()
const admin = useAdminStore()

const user = ref(null)
const orders = ref([])
const loading = ref(false)
const error = ref('')
const submitting = ref(false)
const newPassword = ref('')

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
http.interceptors.request.use((c) => {
  try { const t = JSON.parse(localStorage.getItem('admin_token') || 'null'); if (t?.accessToken) c.headers.Authorization = `Bearer ${t.accessToken}` } catch {}
  return c
})

async function loadUser() {
  loading.value = true; error.value = ''
  try {
    const env = await http.get(`/v2/admin/users/${route.params.id}`)
    user.value = env.data?.data
    const ord = await http.get(`/v2/admin/users/${route.params.id}/orders`)
    orders.value = ord.data?.data?.items || []
  } catch (e) {
    error.value = e.response?.data?.message || e.message
  } finally {
    loading.value = false
  }
}

async function disableUser() {
  if (!confirm(t('admin.c_users.confirm_disable'))) return
  submitting.value = true
  try {
    await http.post(`/v2/admin/users/${route.params.id}/disable`)
    await loadUser()
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { submitting.value = false }
}

async function restoreUser() {
  submitting.value = true
  try {
    await http.post(`/v2/admin/users/${route.params.id}/restore`)
    await loadUser()
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { submitting.value = false }
}

async function resetPwd() {
  if (!confirm(t('admin.c_users.confirm_reset_pwd'))) return
  submitting.value = true
  newPassword.value = ''
  try {
    const r = await http.post(`/v2/admin/users/${route.params.id}/reset-password`)
    newPassword.value = r.data?.data?.new_password || ''
  } catch (e) { alert(e.response?.data?.message || e.message) }
  finally { submitting.value = false }
}

function fmtDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso }
}


onMounted(loadUser)
</script>

<style scoped>
.admin-main { padding: 24px; }
.detail-section { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.detail-section h2 { font-size: 16px; margin: 0 0 12px; }
.kv-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.kv label { display: block; font-size: 12px; color: #909399; margin-bottom: 2px; }
.kv span { font-size: 14px; }
.actions { margin-top: 16px; display: flex; gap: 8px; }
.alert-success { margin-top: 12px; padding: 10px 12px; background: #f0f9eb; color: #67c23a; border-radius: 6px; font-size: 14px; }
.alert-hint { font-size: 12px; color: #909399; margin-left: 8px; }
.status-pill { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.status-pill.is-active { background: #f0f9eb; color: #67c23a; }
.status-pill.is-disabled { background: #fef0f0; color: #f56c6c; }
.status-pill.is-pending_destroy { background: #fdf6ec; color: #e6a23c; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 8px 10px; border-bottom: 1px solid #e4e7ed; font-size: 13px; text-align: left; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.empty { color: #909399; font-size: 14px; padding: 16px 0; }
.btn-primary, .btn-secondary, .btn-danger { padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; border: none; }
.btn-primary { background: #409eff; color: #fff; }
.btn-secondary { background: #fff; border: 1px solid #dcdfe6; color: #606266; }
.btn-danger { background: #f56c6c; color: #fff; }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; padding: 0; font-size: 13px; }
.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }
</style>