<!--
  AdminUsers.vue — W34 / W63

  C 端用户管理页面（任何有 user.view 的 staff 都能进）。
  - 列出所有 C 端用户（分页，按注册时间倒序）
  - 查看用户详情（手机/邮箱/语言/最近登录 IP）+ 该用户的历史订单
  - 禁用 / 恢复账号（要 user.disable）
  - 重置密码（要 user.reset_password，会把新密码显示给管理员一次性告知用户）

  W63 改动：之前这个 component 调的是 listAdminUsers() 查 admin 账号，
  跟 AdminLayout 菜单写的"用户管理"错位（C 端用户列表）。改成查 C 端用户。
  后台账号（ops_manager/reviewer/finance 这类）管理走 /admin/roles 角色管理页面。
-->
<template>
  <main class="admin-main">
    <header class="admin-main__head">
      <h1>{{ t('admin.users.page_title') }}</h1>
      <p class="admin-main__sub">{{ t('admin.users.page_subtitle') }}</p>
    </header>

    <section>
      <!-- Filter bar -->
      <div class="users-toolbar">
        <label class="users-status-filter">
          <span>{{ t('admin.users.filter_status') }}</span>
          <select v-model="status" @change="onStatusChange">
            <option value="">{{ t('admin.users.status_all') }}</option>
            <option value="active">{{ t('admin.users.status_active') }}</option>
            <option value="pending_destroy">{{ t('admin.users.status_pending_destroy') }}</option>
            <option value="disabled">{{ t('admin.users.status_disabled') }}</option>
          </select>
        </label>
        <div class="users-count">
          {{ t('admin.users.total_count', { count: total }) }}
        </div>
      </div>

      <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
      <div v-else-if="error" class="admin-error">{{ error }}</div>
      <template v-else>
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('admin.users.col_id') }}</th>
              <th>{{ t('admin.users.col_nickname') }}</th>
              <th>{{ t('admin.users.col_email') }}</th>
              <th>{{ t('admin.users.col_phone') }}</th>
              <th>{{ t('admin.users.col_lang') }}</th>
              <th>{{ t('admin.users.col_status') }}</th>
              <th>{{ t('admin.users.col_last_login') }}</th>
              <th>{{ t('admin.users.col_created') }}</th>
              <th>{{ t('admin.order_detail.col_action') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" data-testid="users-row">
              <td>#{{ u.id }}</td>
              <td>{{ u.nickname || u.username || '—' }}</td>
              <td>{{ u.email || '—' }}</td>
              <td>{{ u.phone ? `${u.phone_country || ''} ${u.phone}` : '—' }}</td>
              <td>{{ u.language_pref || '—' }}</td>
              <td>
                <span class="status-pill" :class="`is-${u.status}`">
                  {{ statusLabel(u.status) }}
                </span>
              </td>
              <td>{{ fmtDate(u.last_login_at) || '—' }}</td>
              <td>{{ fmtDate(u.created_at) }}</td>
              <td>
                <button class="btn-text" @click="openDetail(u)" data-testid="users-detail-btn">
                  {{ t('admin.users.detail') }}
                </button>
                <button
                  v-if="u.status === 'active' && canDisable"
                  class="btn-text btn-text--danger"
                  @click="doDisable(u)"
                  data-testid="users-disable-btn"
                >
                  {{ t('admin.users.disable') }}
                </button>
                <button
                  v-else-if="u.status === 'disabled' || u.status === 'pending_destroy'"
                  class="btn-text"
                  @click="doRestore(u)"
                  data-testid="users-restore-btn"
                >
                  {{ t('admin.users.restore') }}
                </button>
              </td>
            </tr>
            <tr v-if="!users.length">
              <td colspan="9" class="users-empty">{{ t('admin.users.empty') }}</td>
            </tr>
          </tbody>
        </table>
        <!-- Pagination -->
        <div v-if="totalPages > 1" class="pagination">
          <button class="btn-secondary" :disabled="page <= 1" @click="changePage(page - 1)">
            {{ t('admin.payments.prev') }}
          </button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button class="btn-secondary" :disabled="page >= totalPages" @click="changePage(page + 1)">
            {{ t('admin.payments.next') }}
          </button>
        </div>
      </template>
    </section>

    <!-- Detail drawer -->
    <Teleport to="body">
      <div v-if="detailUser" class="modal-overlay" @click.self="detailUser = null">
        <div class="modal modal--lg">
          <div class="modal__head">
            <h2>{{ t('admin.users.detail_title', { id: detailUser.id, name: detailUser.username || detailUser.nickname }) }}</h2>
            <button class="modal__close" @click="detailUser = null">×</button>
          </div>
          <div class="modal__body" v-if="detailLoading">
            <div class="admin-loading">{{ t('admin.loading') }}</div>
          </div>
          <div class="modal__body" v-else-if="detailError">
            <div class="admin-error">{{ detailError }}</div>
          </div>
          <div class="modal__body detail-grid" v-else-if="detailFull">
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_id') }}</span>
              <span class="detail-val">#{{ detailFull.id }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_nickname') }}</span>
              <span class="detail-val">{{ detailFull.nickname || '—' }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_email') }}</span>
              <span class="detail-val">{{ detailFull.email || '—' }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_phone') }}</span>
              <span class="detail-val">{{ detailFull.phone_country }} {{ detailFull.phone }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_lang') }}</span>
              <span class="detail-val">{{ detailFull.language_pref }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_status') }}</span>
              <span class="detail-val">
                <span class="status-pill" :class="`is-${detailFull.status}`">
                  {{ statusLabel(detailFull.status) }}
                </span>
              </span>
            </div>
            <div class="detail-line">
              <span class="detail-key">MFA</span>
              <span class="detail-val">{{ detailFull.mfa_enabled ? t('admin.users.mfa_on') : t('admin.users.mfa_off') }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_created') }}</span>
              <span class="detail-val">{{ fmtDate(detailFull.created_at) }}</span>
            </div>
            <div class="detail-line">
              <span class="detail-key">{{ t('admin.users.col_last_login') }}</span>
              <span class="detail-val">
                {{ fmtDate(detailFull.last_login_at) || '—' }}
                <span v-if="detailFull.last_login_ip" class="detail-sub">({{ detailFull.last_login_ip }})</span>
              </span>
            </div>
            <div class="detail-stats">
              <div class="detail-stat">
                <span class="detail-stat__n">{{ detailFull.order_count ?? 0 }}</span>
                <span class="detail-stat__l">{{ t('admin.users.stat_orders') }}</span>
              </div>
              <div class="detail-stat">
                <span class="detail-stat__n">{{ detailFull.material_count ?? 0 }}</span>
                <span class="detail-stat__l">{{ t('admin.users.stat_materials') }}</span>
              </div>
            </div>

            <!-- 后台操作 -->
            <div class="detail-actions">
              <button
                v-if="canResetPwd && generatedPassword == null"
                class="btn-secondary"
                @click="doResetPassword(detailFull.id)"
                data-testid="users-reset-pwd-btn"
              >
                {{ t('admin.users.reset_password') }}
              </button>
              <div v-if="canResetPwd && generatedPassword" class="pwd-display" data-testid="users-new-pwd">
                <span>{{ t('admin.users.new_password_hint') }}</span>
                <code>{{ generatedPassword }}</code>
                <button class="btn-text" @click="generatedPassword = null">{{ t('common.cancel') }}</button>
              </div>
            </div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="detailUser = null">{{ t('common.close') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import {
  listCUsers,
  getCUser,
  disableCUser,
  restoreCUser,
  resetCUserPassword,
} from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

// Perm gates
const canDisable = computed(() => admin.hasPermission('user.disable'))
const canResetPwd = computed(() => admin.hasPermission('user.reset_password'))

// Filter state
const status = ref('')
const users = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = 20
const totalPages = ref(1)

// Detail drawer state
const detailUser = ref(null)
const detailFull = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const generatedPassword = ref(null)

onMounted(() => fetchUsers())

async function fetchUsers() {
  loading.value = true
  error.value = ''
  try {
    const res = await listCUsers({
      page: page.value,
      page_size: pageSize,
      status: status.value || null,
    })
    users.value = res.items
    total.value = res.total
    totalPages.value = res.total_pages
  } catch (e) {
    error.value = e.message || t('admin.error_load')
  } finally {
    loading.value = false
  }
}

function onStatusChange() {
  page.value = 1
  fetchUsers()
}

function changePage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchUsers()
}

async function openDetail(u) {
  detailUser.value = u
  detailFull.value = null
  detailError.value = ''
  generatedPassword.value = null
  detailLoading.value = true
  try {
    detailFull.value = await getCUser(u.id)
  } catch (e) {
    detailError.value = e.message || t('admin.error_load')
  } finally {
    detailLoading.value = false
  }
}

async function doDisable(u) {
  if (!confirm(t('admin.users.confirm_disable', { name: u.username || u.id }))) return
  try {
    await disableCUser(u.id)
    await fetchUsers()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  }
}

async function doRestore(u) {
  try {
    await restoreCUser(u.id)
    await fetchUsers()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  }
}

async function doResetPassword(userId) {
  if (!confirm(t('admin.users.confirm_reset_pwd'))) return
  try {
    const res = await resetCUserPassword(userId)
    generatedPassword.value = res?.password || ''
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  }
}

function statusLabel(s) {
  if (s === 'active') return t('admin.users.status_active')
  if (s === 'pending_destroy') return t('admin.users.status_pending_destroy')
  if (s === 'disabled') return t('admin.users.status_disabled')
  return s || '—'
}

function fmtDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}
</script>

<style scoped>
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e4e7ed; font-size: 14px; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.status-pill { font-size: 12px; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.status-pill.is-active { background: #f0f9eb; color: #67c23a; }
.status-pill.is-disabled, .status-pill.is-pending_destroy { background: #f4f4f5; color: #909399; }
.users-empty { text-align: center; padding: 30px; color: #909399; }

.users-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.users-status-filter { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #606266; }
.users-status-filter select { padding: 6px 10px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; }
.users-count { font-size: 13px; color: #909399; }

.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 16px; }

.btn-primary { background: #409eff; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary { background: #fff; color: #606266; border: 1px solid #dcdfe6; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-danger { background: #f56c6c; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; font-size: 13px; padding: 0 4px; }
.btn-text--danger { color: #f56c6c; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }

.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 480px; max-width: 90vw; max-height: 85vh; overflow-y: auto; }
.modal--lg { width: 640px; }
.modal__head { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e4e7ed; }
.modal__head h2 { margin: 0; font-size: 16px; }
.modal__close { background: none; border: none; font-size: 20px; cursor: pointer; color: #909399; }
.modal__body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px; border-top: 1px solid #e4e7ed; }

.detail-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
.detail-line { display: flex; gap: 16px; align-items: baseline; font-size: 14px; }
.detail-key { flex: 0 0 90px; color: #909399; font-size: 13px; }
.detail-val { color: #1f2937; }
.detail-sub { color: #909399; font-size: 12px; margin-left: 6px; }
.detail-stats { display: flex; gap: 12px; margin-top: 8px; padding-top: 12px; border-top: 1px dashed #e4e7ed; }
.detail-stat { flex: 1; display: flex; flex-direction: column; align-items: center; padding: 10px; background: #f8fafc; border-radius: 8px; }
.detail-stat__n { font-size: 22px; font-weight: 600; color: #3b6ef5; }
.detail-stat__l { font-size: 12px; color: #909399; margin-top: 4px; }
.detail-actions { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #e4e7ed; display: flex; flex-direction: column; gap: 8px; }
.pwd-display { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 10px 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; }
.pwd-display code { font-family: ui-monospace, Menlo, monospace; font-weight: 600; color: #92400e; padding: 2px 6px; background: #fef3c7; border-radius: 4px; }
</style>
