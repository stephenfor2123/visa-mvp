<!--
  AdminRoles.vue — W34

  角色管理页面（超级管理员专属）。
  - 列出所有角色 + 权限
  - 新建 / 编辑 / 删除角色
-->
<template>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.roles.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.roles.page_subtitle') }}</p>
        <div class="admin-main__actions">
          <button class="btn-primary" @click="openCreate" data-testid="roles-create-btn">
            + {{ t('admin.roles.create') }}
          </button>
        </div>
      </header>

      <!-- Role list -->
      <section class="role-list">
        <div v-if="loading" class="admin-loading">{{ t('admin.loading') }}</div>
        <div v-else-if="error" class="admin-error">{{ error }}</div>
        <template v-else>
          <div
            v-for="role in roles"
            :key="role.id"
            class="role-card"
            :class="{ 'role-card--super': role.code === 'super_admin' }"
          >
            <div class="role-card__header">
              <div>
                <span class="role-card__name">{{ role.name }}</span>
                <span class="role-card__code">{{ role.code }}</span>
                <span v-if="role.code === 'super_admin'" class="role-card__badge">
                  {{ t('admin.roles.badge_fixed') }}
                </span>
              </div>
              <div class="role-card__actions">
                <button
                  v-if="role.code !== 'super_admin'"
                  class="btn-text"
                  @click="openEdit(role)"
                  data-testid="roles-edit-btn"
                >
                  {{ t('admin.roles.edit') }}
                </button>
                <button
                  v-if="role.code !== 'super_admin'"
                  class="btn-text btn-text--danger"
                  @click="confirmDelete(role)"
                  data-testid="roles-delete-btn"
                >
                  {{ t('admin.roles.delete') }}
                </button>
              </div>
            </div>
            <p v-if="role.description" class="role-card__desc">{{ role.description }}</p>
            <div class="role-card__perms">
              <span
                v-for="perm in role.permissions"
                :key="perm"
                class="perm-tag"
              >{{ t(`admin.perms.${perm}`) || perm }}</span>
            </div>
            <div class="role-card__footer">
              <span class="role-card__status">
                {{ role.is_active ? t('admin.roles.active') : t('admin.roles.inactive') }}
              </span>
            </div>
          </div>
        </template>
      </section>
    </main>

    <!-- Create/Edit modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal__head">
            <h2>{{ editingRole ? t('admin.roles.modal_edit') : t('admin.roles.modal_create') }}</h2>
            <button class="modal__close" @click="closeModal">×</button>
          </div>
          <div class="modal__body">
            <div class="form-field">
              <label>{{ t('admin.roles.form_name') }} *</label>
              <input v-model="form.name" class="form-input" :disabled="!!editingRole" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.roles.form_code') }} *</label>
              <input v-model="form.code" class="form-input" :disabled="!!editingRole"
                placeholder="e.g. staff" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.roles.form_desc') }}</label>
              <input v-model="form.description" class="form-input" />
            </div>
            <div class="form-field">
              <label>{{ t('admin.roles.form_perms') }}</label>
              <div class="perm-groups">
                <div
                  v-for="groupKey in permRegistry.groups_order"
                  :key="groupKey"
                  class="perm-group"
                  v-show="permRegistry.groups[groupKey]?.length"
                >
                  <div class="perm-group__title">{{ t(`admin.perm_group.${groupKey}`) }}</div>
                  <div class="perm-group__list">
                    <label
                      v-for="perm in permRegistry.groups[groupKey]"
                      :key="perm.code"
                      class="perm-check"
                      :title="perm.description"
                    >
                      <input
                        type="checkbox"
                        :value="perm.code"
                        v-model="form.permissions"
                      />
                      <span>{{ t(perm.label_key) || perm.code }}</span>
                    </label>
                  </div>
                </div>
              </div>
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
            <h2>{{ t('admin.roles.confirm_delete_title') }}</h2>
          </div>
          <div class="modal__body">
            <p>{{ t('admin.roles.confirm_delete_msg', { name: deletingRole?.name }) }}</p>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="showDeleteModal = false">
              {{ t('common.cancel') }}
            </button>
            <button class="btn-danger" @click="doDelete" :disabled="submitting">
              {{ submitting ? t('admin.saving') : t('admin.roles.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import { listRoles, createRole, updateRole, deleteRole } from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

const roles = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const showDeleteModal = ref(false)
const editingRole = ref(null)
const deletingRole = ref(null)
const submitting = ref(false)

// W47: perm 列表从后端注册表拉,分 group 渲染
const permRegistry = computed(() => admin.permRegistry || { groups: {}, groups_order: [] })

const form = ref({ name: '', code: '', description: '', permissions: [] })

onMounted(async () => {
  await admin.loadPermRegistry()
  fetchRoles()
})

async function fetchRoles() {
  loading.value = true
  error.value = ''
  try {
    roles.value = await listRoles()
  } catch (e) {
    error.value = e.message || t('admin.error_load')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingRole.value = null
  form.value = { name: '', code: '', description: '', permissions: [] }
  showModal.value = true
}

function openEdit(role) {
  editingRole.value = role
  form.value = {
    name: role.name,
    code: role.code,
    description: role.description || '',
    permissions: [...(role.permissions || [])]
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function submitForm() {
  if (!form.value.name || !form.value.code) return
  submitting.value = true
  try {
    if (editingRole.value) {
      await updateRole(editingRole.value.id, { permissions: form.value.permissions, description: form.value.description })
    } else {
      await createRole({ name: form.value.name, code: form.value.code, description: form.value.description, permissions: form.value.permissions })
    }
    closeModal()
    await fetchRoles()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  } finally {
    submitting.value = false
  }
}

function confirmDelete(role) {
  deletingRole.value = role
  showDeleteModal.value = true
}

async function doDelete() {
  submitting.value = true
  try {
    await deleteRole(deletingRole.value.id)
    showDeleteModal.value = false
    await fetchRoles()
  } catch (e) {
    alert(e.message || t('admin.error_save'))
  } finally {
    submitting.value = false
  }
}

</script>

<style scoped>
.role-list { display: flex; flex-direction: column; gap: 16px; }

.role-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 8px;
  padding: 16px 20px;
}
.role-card--super { border-left: 3px solid #409eff; }

.role-card__header { display: flex; justify-content: space-between; align-items: flex-start; }
.role-card__name { font-size: 16px; font-weight: 600; margin-right: 8px; }
.role-card__code { font-size: 12px; color: #909399; background: #f4f4f5; padding: 1px 6px; border-radius: 4px; }
.role-card__badge { font-size: 11px; color: #409eff; background: #ecf5ff; padding: 1px 6px; border-radius: 4px; margin-left: 6px; }
.role-card__desc { color: #606266; font-size: 14px; margin: 6px 0; }
.role-card__perms { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.role-card__footer { margin-top: 8px; font-size: 12px; color: #909399; }
.role-card__actions { display: flex; gap: 8px; }

.perm-tag { font-size: 12px; background: #f0f9eb; color: #67c23a; padding: 2px 8px; border-radius: 4px; }

.perm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.perm-check { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
.perm-check input { width: auto; }

.perm-groups { display: flex; flex-direction: column; gap: 12px; max-height: 320px; overflow-y: auto; padding-right: 4px; }
.perm-group { background: #f8fafc; border: 1px solid #e4e7ed; border-radius: 6px; padding: 8px 12px; }
.perm-group__title { font-size: 12px; color: #475569; font-weight: 600; margin-bottom: 6px; letter-spacing: .3px; }
.perm-group__list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 12px; }

.btn-primary { background: #409eff; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary { background: #fff; color: #606266; border: 1px solid #dcdfe6; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-danger { background: #f56c6c; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-text { background: none; border: none; color: #409eff; cursor: pointer; font-size: 13px; padding: 0; }
.btn-text--danger { color: #f56c6c; }
.btn-primary:disabled, .btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }

.admin-loading, .admin-error { padding: 20px; text-align: center; color: #909399; }
.admin-error { color: #f56c6c; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 560px; max-width: 90vw; max-height: 85vh; overflow-y: auto; }
.modal--sm { width: 400px; }
.modal__head { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e4e7ed; }
.modal__head h2 { margin: 0; font-size: 16px; }
.modal__close { background: none; border: none; font-size: 20px; cursor: pointer; color: #909399; }
.modal__body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.modal__foot { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px; border-top: 1px solid #e4e7ed; }

.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: 13px; color: #606266; }
.form-input { border: 1px solid #dcdfe6; border-radius: 6px; padding: 7px 12px; font-size: 14px; width: 100%; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: #409eff; }
.form-input:disabled { background: #f5f7fa; }

.admin-main__actions { margin-top: 4px; }
</style>