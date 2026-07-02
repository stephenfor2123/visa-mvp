<!--
  AdminUsers.vue — W34

  账号管理页面（超级管理员专属）。
  - 列出所有后台账号（分页）
  - 新建 / 编辑 / 禁用账号
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.users.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.users.page_subtitle') }}</p>
        <div class="admin-main__actions">
          <button class="btn-primary" @click="openCreate" data-testid="users-create-btn">
            + {{ t('admin.users.create') }}
          </button>
        </div>
      </header>

      <!-- User table -->
      <section>
        <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
        <div v-else-if="error" class="admin-error">{{ error }}</div>
        <template v-else>
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('admin.users.col_username') }}</th>
                <th>{{ t('admin.users.col_role') }}</th>
                <th>{{ t('admin.users.col_status') }}</th>
                <th>{{ t('admin.users.col_created') }}</th>
                <th>{{ t('admin.users.col_last_login') }}</th>
                <th>{{ t('admin.order_detail.col_action') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.username }}</td>
                <td>{{ user.role_name }}</td>
                <td>
                  <span class="status-pill" :class="user.is_active ? 'is-active' : 'is-inactive'">
                    {{ user.is_active ? t('admin.users.active') : t('admin.users.inactive') }}
                  </span>
                </td>
                <td>{{ fmtDate(user.created_at) }}</td>
                <td>{{ fmtDate(user.last_login) || '—' }}</td>
                <td>
                  <button class="btn-text" @click="openEdit(user)" data-testid="users-edit-btn">
                    {{ t('admin.users.edit') }}
                  </button>
                  <button
                    v-if="user.is_active"
                    class="btn-text btn-text--danger"
                    @click="confirmDelete(user)"
                    data-testid="users-delete-btn"
                  >
                    {{ t('admin.users.delete') }}
                  </button>
                </td>
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
    </main>

    <!-- Create/Edit modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal__head">
            <h2>{{ editingUser ? t('admin.users.modal_edit') : t('admin.users.modal_create') }}</h2>
            <button class="modal__close" @click="closeModal">×</button>
          </div>
          <div class="modal__body">
            <div class="form-field">
              <label>{{ t('admin.users.form_username') }} *</label>
              <input v-model="form.username" class="form-input" :disabled="!!editingUser" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.users.form_password') }} {{ editingUser ? '' : '*' }}</label>
              <input v-model="form.password" type="password" class="form-input" :placeholder="editingUser ? t('admin.users.password_unchanged_hint') : ''" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.users.form_role') }} *</label>
              <select v-model="form.role_id" class="form-input">
                <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
              </select>
            </div>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="closeModal">{{ t('common.cancel') }}</button>
            <button class="btn-primary" @click="submitForm" :disabled="submitting">
              {{ submitting ? t('admin.saving') : t('common.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete confirm modal -->
    <Teleport to="body">
      <div v-if="showDeleteModal" class="modal-overlay" @click.self="showDeleteModal = false">
        <div class="modal modal--sm">
          <div class="modal__head">
            <h2>{{ t('admin.users.confirm_delete_title') }}</h2>
          </div>
          <div class="modal__body">
            <p>{{ t('admin.users.confirm_delete_msg', { name: deletingUser?.username }) }}</p>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="showDeleteModal = false">
              {{ t('common.cancel') }}
            </button>
            <button class="btn-danger" @click="doDelete" :disabled="submitting">
              {{ submitting ? t('admin.saving') : t('admin.users.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import { listAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser, listRoles } from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const users = ref([])
const roles = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const showDeleteModal = ref(false)
const editingUser = ref(null)
const deletingUser = ref(null)
const submitting = ref(false)
const page = ref(1)
const totalPages = ref(1)

const form = ref({ username: '', password: '', role_id: null })

onMounted(async () => {
  await Promise.all([fetchUsers(), fetchRoles()])
})

async function fetchUsers() {
  loading.value = true
  error.value = ''
  try {
    const res = await listAdminUsers({ page: page.value, page_size: 20 })
    users.value = res.items
    totalPages.value = res.total_pages
  } catch (e) {
    error.value = e.message || t('admin.error_load')
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    roles.value = await listRoles()
    if (roles.value.length && !form.value.role_id) {
      form.value.role_id = roles.value[0].id
    }
  } catch {}
}

function openCreate() {
  editingUser.value = null
  form.value = { username: '', password: '', role_id: roles.value[0]?.id || null }
  showModal.value = true
}

function openEdit(user) {
  editingUser.value = user
  form.value = { username: user.username, password: '', role_id: user.role_id }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function submitForm() {
  if (!form.value.username || (!editingUser.value && !form.value.password) || !form.value.role_id) return
  submitting.value = true
  try {
    const body = { role_id: form.value.role_id }
    if (form.value.password) body.password = form.value.password
    if (editingUser.value) {
      await updateAdminUser(editingUser.value.id, body)
    } else {
      await createAdminUser({ username: form.value.username, password: form.value.password, role_id: form.value.role_id })
    }
    closeModal()
    await fetchUsers()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  } finally {
    submitting.value = false
  }
}

function confirmDelete(user) {
  deletingUser.value = user
  showDeleteModal.value = true
}

async function doDelete() {
  submitting.value = true
  try {
    await deleteAdminUser(deletingUser.value.id)
    showDeleteModal.value = false
    await fetchUsers()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  } finally {
    submitting.value = false
  }
}

function changePage(p) {
  page.value = p
  fetchUsers()
}

function fmtDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }) } catch { return iso }
}

</script>

<style scoped>
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e4e7ed; font-size: 14px; }
.data-table th { background: #f5f7fa; font-weight: 600; color: #606266; }
.status-pill { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.status-pill.is-active { background: #f0f9eb; color: #67c23a; }
.status-pill.is-inactive { background: #f4f4f5; color: #909399; }
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
.modal--sm { width: 400px; }
.modal__head { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e4e7ed; }
.modal__head h2 { margin: 0; font-size: 16px; }
.modal__close { background: none; border: none; font-size: 20px; cursor: pointer; color: #909399; }
.modal__body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px; border-top: 1px solid #e4e7ed; }

.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: 13px; color: #606266; }
.form-input { border: 1px solid #dcdfe6; border-radius: 6px; padding: 7px 12px; font-size: 14px; width: 100%; box-sizing: border-box; background: #fff; }
.form-input:focus { outline: none; border-color: #409eff; }
.form-input:disabled { background: #f5f7fa; }

.admin-main__actions { margin-top: 4px; }
</style>