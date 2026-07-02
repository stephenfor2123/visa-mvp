<!--
  AdminCUsers.vue — W36

  C-端用户管理页面（users 权限）。

  - 列表：分页 + status 筛选；展示脱敏邮箱/手机号
  - 行内详情：点击行展开 → 用户统计 + 订单列表（内联表格）+ 三个动作按钮
  - 顶部工具栏：禁用 / 恢复 / 修改资料 / 重置密码 / 删除
  - 双重确认 Modal：
      disable/restore 直接确认
      update 用 modal 收集 nickname / language_pref
      reset-password 弹一次性明文 Modal（含复制按钮）
      delete 二次确认
  - 风格对齐 AdminOrderDetail.vue（sidebar + admin-panel + admin-pill 等）
-->
<template>
<div class="admin-c-users" data-testid="admin-c-users">

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.c_users.page_title') }}</h1>
        <p class="admin-main__sub">{{ t('admin.c_users.page_subtitle') }}</p>
      </header>

      <!-- 状态筛选 -->
      <section class="admin-filter" role="tablist">
        <button
          v-for="f in statusFilters"
          :key="f.value || 'all'"
          class="admin-filter__chip"
          :class="{ 'is-active': statusFilter === f.value }"
          @click="setStatus(f.value)"
          :data-testid="`c-users-filter-${f.value || 'all'}`"
        >
          {{ t(f.labelKey) }}
        </button>
      </section>

      <!-- 列表 -->
      <AppCard class="admin-panel">
        <template #header>
          <h3>{{ t('admin.c_users.table_title') }}</h3>
            <span class="admin-panel__meta">{{ users.length }} / {{ total }}</span>
</template>

        <div v-if="loading" class="admin-panel__placeholder">{{ t('admin.orders.loading') }}</div>
        <div v-else-if="loadError" class="admin-panel__placeholder admin-panel__placeholder--err">{{ loadError }}</div>
        <div v-else-if="!users.length" class="admin-panel__placeholder">{{ t('admin.c_users.empty') }}</div>
        <table v-else class="admin-table">
          <thead>
            <tr>
              <th>{{ t('admin.c_users.col_id') }}</th>
              <th>{{ t('admin.c_users.col_email') }}</th>
              <th>{{ t('admin.c_users.col_phone') }}</th>
              <th>{{ t('admin.c_users.col_nickname') }}</th>
              <th>{{ t('admin.c_users.col_lang') }}</th>
              <th>{{ t('admin.c_users.col_status') }}</th>
              <th>{{ t('admin.c_users.col_created') }}</th>
              <th>{{ t('admin.c_users.col_action') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="u in users" :key="u.id">
              <tr
                :class="['admin-table__row', { 'is-expanded': expandedId === u.id }]"
                @click="toggleExpand(u)"
                :data-testid="`c-users-row-${u.id}`"
              >
                <td class="admin-table__mono">#{{ u.id }}</td>
                <td>{{ u.email || '—' }}</td>
                <td class="admin-table__mono">{{ u.phone || '—' }}</td>
                <td>{{ u.nickname || u.username || '—' }}</td>
                <td>
                  <span class="admin-lang-tag">{{ t(`admin.c_users.lang_${u.language_pref || 'zh-CN'}`) }}</span>
                </td>
                <td>
                  <span class="admin-pill" :class="`admin-pill--status-${u.status}`">
                    {{ t(`admin.c_users.status_${u.status}`) }}
                  </span>
                </td>
                <td class="admin-table__muted">{{ formatTime(u.created_at) }}</td>
                <td @click.stop>
                  <button class="btn-text" @click="openEdit(u)" :data-testid="`c-users-edit-${u.id}`">
                    {{ t('admin.c_users.action_edit') }}
                  </button>
                  <button
                    class="btn-text"
                    v-if="u.status === 'active'"
                    @click="askDisable(u)"
                    :data-testid="`c-users-disable-${u.id}`"
                  >
                    {{ t('admin.c_users.action_disable') }}
                  </button>
                  <button
                    class="btn-text"
                    v-else-if="u.status === 'disabled'"
                    @click="askRestore(u)"
                    :data-testid="`c-users-restore-${u.id}`"
                  >
                    {{ t('admin.c_users.action_restore') }}
                  </button>
                  <button
                    class="btn-text"
                    @click="askResetPassword(u)"
                    :data-testid="`c-users-reset-${u.id}`"
                  >
                    {{ t('admin.c_users.action_reset_pwd') }}
                  </button>
                  <button
                    class="btn-text btn-text--danger"
                    v-if="u.status !== 'pending_destroy' && u.status !== 'destroyed'"
                    @click="askDelete(u)"
                    :data-testid="`c-users-delete-${u.id}`"
                  >
                    {{ t('admin.c_users.action_delete') }}
                  </button>
                </td>
              </tr>

              <!-- 行内详情面板 -->
              <tr v-if="expandedId === u.id" class="admin-table__detail-row">
                <td :colspan="8">
                  <div v-if="detailLoading" class="admin-panel__placeholder">{{ t('admin.orders.loading') }}</div>
                  <div v-else-if="detailError" class="admin-panel__placeholder admin-panel__placeholder--err">{{ detailError }}</div>
                  <div v-else-if="detail" class="admin-inline-detail">
                    <!-- 基础信息 -->
                    <dl class="admin-dl admin-dl--inline">
                      <dt>{{ t('admin.c_users.detail_user_id') }}</dt>
                      <dd>#{{ detail.id }}</dd>
                      <dt>{{ t('admin.c_users.detail_uuid') }}</dt>
                      <dd class="admin-mono">{{ detail.uuid }}</dd>
                      <dt>{{ t('admin.c_users.detail_username') }}</dt>
                      <dd>{{ detail.username || '—' }}</dd>
                      <dt>{{ t('admin.c_users.detail_mfa') }}</dt>
                      <dd>{{ detail.mfa_enabled ? t('common.yes') : t('common.no') }}</dd>
                      <dt>{{ t('admin.c_users.detail_last_login') }}</dt>
                      <dd>{{ detail.last_login_at ? formatTime(detail.last_login_at) : '—' }}</dd>
                      <dt>{{ t('admin.c_users.detail_last_ip') }}</dt>
                      <dd class="admin-mono">{{ detail.last_login_ip || '—' }}</dd>
                      <dt>{{ t('admin.c_users.detail_order_count') }}</dt>
                      <dd class="admin-mono">{{ detail.order_count }}</dd>
                      <dt>{{ t('admin.c_users.detail_material_count') }}</dt>
                      <dd class="admin-mono">{{ detail.material_count }}</dd>
                      <dt>{{ t('admin.c_users.detail_avatar') }}</dt>
                      <dd class="admin-mono">
                        <span v-if="detail.avatar_url">
                          <a :href="detail.avatar_url" target="_blank">{{ detail.avatar_url }}</a>
                        </span>
                        <span v-else>—</span>
                      </dd>
                    </dl>

                    <!-- 订单列表（行内） -->
                    <div class="admin-inline-detail__sub">
                      <h4>{{ t('admin.c_users.detail_orders_title') }}</h4>
                      <table v-if="userOrders.length" class="admin-table admin-table--nested">
                        <thead>
                          <tr>
                            <th>{{ t('admin.c_users.detail_order_no') }}</th>
                            <th>{{ t('admin.c_users.detail_order_type') }}</th>
                            <th>{{ t('admin.c_users.detail_order_status') }}</th>
                            <th>{{ t('admin.c_users.detail_order_amount') }}</th>
                            <th>{{ t('admin.c_users.detail_order_created') }}</th>
                            <th>{{ t('admin.c_users.col_action') }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="o in userOrders" :key="o.id">
                            <td class="admin-table__mono">
                              <router-link :to="`/admin/orders/${o.id}`" @click.stop>
                                {{ o.order_no }}
                              </router-link>
                            </td>
                            <td>{{ t(`admin.order_detail.visa_type_${o.visa_type}`) }}</td>
                            <td>
                              <span class="admin-pill" :class="`admin-pill--${o.status}`">
                                {{ t(`admin.order_detail.status_${o.status}`) }}
                              </span>
                            </td>
                            <td>{{ formatAmount(o.total_amount, o.currency) }}</td>
                            <td class="admin-table__muted">{{ formatTime(o.created_at) }}</td>
                            <td>
                              <router-link :to="`/admin/orders/${o.id}`" class="btn-text" @click.stop>
                                {{ t('admin.c_users.detail_view_order') }}
                              </router-link>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      <div v-else class="admin-panel__placeholder">{{ t('admin.c_users.detail_no_orders') }}</div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- 分页 -->
        <div v-if="totalPages > 1" class="admin-pagination">
          <button class="admin-page-btn" :disabled="page <= 1" @click="page--">
            {{ t('admin.payments.prev') }}
          </button>
          <span class="admin-page-info">{{ page }} / {{ totalPages }}</span>
          <button class="admin-page-btn" :disabled="page >= totalPages" @click="page++">
            {{ t('admin.payments.next') }}
          </button>
        </div>
      </AppCard>

      <p v-if="actionMessage" class="admin-actions__msg" :class="actionOk ? 'is-ok' : 'is-err'">
        {{ actionMessage }}
      </p>
    </main>

    <!-- 编辑 Modal (nickname / language_pref / avatar_url) -->
    <div v-if="editTarget" class="admin-modal-mask" @click.self="cancelEdit">
      <div class="admin-modal" data-testid="c-users-edit-modal">
        <div class="admin-modal__head">
          <h3>{{ t('admin.c_users.modal_edit_title') }}</h3>
          <button class="admin-modal__close" @click="cancelEdit">×</button>
        </div>
        <div class="admin-modal__body">
          <p class="admin-modal__hint">
            {{ t('admin.c_users.modal_edit_hint', { id: editTarget.id }) }}
          </p>
          <label class="admin-modal__label">{{ t('admin.c_users.form_nickname') }}</label>
          <input v-model="editForm.nickname" class="admin-modal__input" maxlength="64" />
          <label class="admin-modal__label">{{ t('admin.c_users.form_lang') }}</label>
          <select v-model="editForm.language_pref" class="admin-modal__input">
            <option value="zh-CN">简体中文</option>
            <option value="en">English</option>
            <option value="id-ID">Bahasa Indonesia</option>
            <option value="vi-VN">Tiếng Việt</option>
          </select>
          <label class="admin-modal__label">{{ t('admin.c_users.form_avatar') }}</label>
          <input
            v-model="editForm.avatar_url"
            class="admin-modal__input"
            maxlength="512"
            :placeholder="t('admin.c_users.form_avatar_placeholder')"
          />
        </div>
        <div class="admin-modal__actions">
          <button class="admin-modal__btn" @click="cancelEdit">
            {{ t('common.cancel') }}
          </button>
          <button
            class="admin-modal__btn admin-modal__btn--primary"
            :disabled="submitting"
            @click="submitEdit"
            data-testid="c-users-edit-submit"
          >
            {{ submitting ? t('admin.saving') : t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 二次确认 Modal: disable / restore / delete -->
    <div v-if="confirmTarget" class="admin-modal-mask" @click.self="cancelConfirm">
      <div class="admin-modal" data-testid="c-users-confirm-modal">
        <div class="admin-modal__head">
          <h3>{{ confirmTitle }}</h3>
        </div>
        <div class="admin-modal__body">
          <p>{{ confirmMessage }}</p>
        </div>
        <div class="admin-modal__actions">
          <button class="admin-modal__btn" @click="cancelConfirm">
            {{ t('common.cancel') }}
          </button>
          <button
            :class="['admin-modal__btn', confirmDanger ? 'admin-modal__btn--danger' : 'admin-modal__btn--primary']"
            :disabled="submitting"
            @click="submitConfirm"
            data-testid="c-users-confirm-submit"
          >
            {{ submitting ? t('admin.saving') : t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 重置密码 Modal：一次性展示明文 + copy -->
    <div v-if="resetResult" class="admin-modal-mask" @click.self="closeReset">
      <div class="admin-modal" data-testid="c-users-reset-modal">
        <div class="admin-modal__head">
          <h3>{{ t('admin.c_users.reset_title') }}</h3>
          <button class="admin-modal__close" @click="closeReset">×</button>
        </div>
        <div class="admin-modal__body">
          <p class="admin-modal__hint admin-modal__hint--warn">
            {{ t('admin.c_users.reset_warn') }}
          </p>
          <label class="admin-modal__label">{{ t('admin.c_users.reset_user') }}</label>
          <input :value="resetResult.username || `#${resetResult.user_id}`" class="admin-modal__input" readonly />
          <label class="admin-modal__label">{{ t('admin.c_users.reset_new_pwd') }}</label>
          <div class="admin-pwd-display">
            <input
              ref="pwdInputRef"
              :value="resetResult.new_password"
              class="admin-modal__input admin-modal__input--pwd"
              readonly
              data-testid="c-users-reset-pwd"
            />
            <button class="admin-modal__btn" @click="copyPwd" data-testid="c-users-reset-copy">
              {{ copied ? t('admin.c_users.reset_copied') : t('admin.c_users.reset_copy') }}
            </button>
          </div>
          <p class="admin-modal__hint">
            {{ t('admin.c_users.reset_at', { time: formatTime(resetResult.reset_at) }) }}
          </p>
        </div>
        <div class="admin-modal__actions">
          <button class="admin-modal__btn admin-modal__btn--primary" @click="closeReset">
            {{ t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'
import {
  listCUsers,
  getCUser,
  listUserOrders,
  disableUser,
  restoreUser,
  updateCUser,
  resetUserPassword,
  deleteCUser,
} from '@/api/admin'

const { t } = useI18n()
const admin = useAdminStore()

// ---- 列表状态 ----
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const loadError = ref('')
const statusFilter = ref('')

const totalPages = computed(() => Math.ceil(total.value / pageSize))

const statusFilters = [
  { value: '',           labelKey: 'admin.c_users.filter_all' },
  { value: 'active',     labelKey: 'admin.c_users.status_active' },
  { value: 'disabled',   labelKey: 'admin.c_users.status_disabled' },
  { value: 'pending_destroy', labelKey: 'admin.c_users.status_pending_destroy' },
  { value: 'destroyed',  labelKey: 'admin.c_users.status_destroyed' },
]

// ---- 行内详情 ----
const expandedId = ref(null)
const detail = ref(null)
const userOrders = ref([])
const detailLoading = ref(false)
const detailError = ref('')

// ---- Modal: edit ----
const editTarget = ref(null)
const editForm = ref({ nickname: '', language_pref: 'zh-CN', avatar_url: '' })

// ---- Modal: confirm (disable/restore/delete) ----
const confirmTarget = ref(null)
const confirmAction = ref('')  // 'disable' | 'restore' | 'delete'
const submitting = ref(false)

// ---- Modal: reset password ----
const resetResult = ref(null)
const pwdInputRef = ref(null)
const copied = ref(false)

// ---- toast ----
const actionMessage = ref('')
const actionOk = ref(true)

const confirmTitle = computed(() => {
  if (confirmAction.value === 'disable') return t('admin.c_users.confirm_disable_title')
  if (confirmAction.value === 'restore') return t('admin.c_users.confirm_restore_title')
  if (confirmAction.value === 'delete') return t('admin.c_users.confirm_delete_title')
  return ''
})

const confirmMessage = computed(() => {
  if (!confirmTarget.value) return ''
  const name = confirmTarget.value.nickname || confirmTarget.value.username || `#${confirmTarget.value.id}`
  if (confirmAction.value === 'disable') return t('admin.c_users.confirm_disable_msg', { name })
  if (confirmAction.value === 'restore') return t('admin.c_users.confirm_restore_msg', { name })
  if (confirmAction.value === 'delete') return t('admin.c_users.confirm_delete_msg', { name })
  return ''
})

const confirmDanger = computed(() => confirmAction.value === 'delete')

// ---- 生命周期 ----
onMounted(async () => {
  await fetchList()
})

watch(page, () => fetchList())

async function fetchList() {
  loading.value = true
  loadError.value = ''
  try {
    const out = await listCUsers({
      page: page.value,
      page_size: pageSize,
      status: statusFilter.value || null,
    })
    users.value = out.items
    total.value = out.total
  } catch (err) {
    loadError.value = err?.message || String(err)
    users.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function setStatus(v) {
  statusFilter.value = v
  page.value = 1
  expandedId.value = null
  detail.value = null
  userOrders.value = []
  fetchList()
}

async function toggleExpand(u) {
  if (expandedId.value === u.id) {
    expandedId.value = null
    detail.value = null
    userOrders.value = []
    return
  }
  expandedId.value = u.id
  detail.value = null
  userOrders.value = []
  detailError.value = ''
  detailLoading.value = true
  try {
    const [d, orders] = await Promise.all([
      getCUser(u.id),
      listUserOrders(u.id, { page: 1, page_size: 20 }),
    ])
    detail.value = d
    userOrders.value = orders.items || []
  } catch (err) {
    detailError.value = err?.message || String(err)
  } finally {
    detailLoading.value = false
  }
}

// ---- 动作：edit ----
function openEdit(u) {
  editTarget.value = u
  editForm.value = {
    nickname: u.nickname || '',
    language_pref: u.language_pref || 'zh-CN',
    avatar_url: u.avatar_url || '',
  }
}
function cancelEdit() {
  editTarget.value = null
}
async function submitEdit() {
  if (!editTarget.value) return
  submitting.value = true
  actionMessage.value = ''
  try {
    const body = {}
    if (editForm.value.nickname != null) body.nickname = editForm.value.nickname
    if (editForm.value.language_pref) body.language_pref = editForm.value.language_pref
    if (editForm.value.avatar_url !== '') body.avatar_url = editForm.value.avatar_url
    if (!Object.keys(body).length) {
      cancelEdit()
      return
    }
    await updateCUser(editTarget.value.id, body)
    editTarget.value = null
    actionOk.value = true
    actionMessage.value = t('admin.c_users.toast_update_ok')
    await fetchList()
    // 同步展开的 detail
    if (expandedId.value === editTarget.value?.id) {
      // 没有引用会变 null，跳过
    }
  } catch (err) {
    actionOk.value = false
    actionMessage.value = t('admin.c_users.toast_update_fail') + ': ' + (err?.message || err)
  } finally {
    submitting.value = false
  }
}

// ---- 动作：confirm (disable / restore / delete) ----
function askDisable(u) {
  confirmTarget.value = u
  confirmAction.value = 'disable'
}
function askRestore(u) {
  confirmTarget.value = u
  confirmAction.value = 'restore'
}
function askDelete(u) {
  confirmTarget.value = u
  confirmAction.value = 'delete'
}
function cancelConfirm() {
  confirmTarget.value = null
  confirmAction.value = ''
}

async function submitConfirm() {
  if (!confirmTarget.value || !confirmAction.value) return
  const action = confirmAction.value
  const target = confirmTarget.value
  submitting.value = true
  actionMessage.value = ''
  try {
    if (action === 'disable') {
      await disableUser(target.id)
      actionOk.value = true
      actionMessage.value = t('admin.c_users.toast_disable_ok')
    } else if (action === 'restore') {
      await restoreUser(target.id)
      actionOk.value = true
      actionMessage.value = t('admin.c_users.toast_restore_ok')
    } else if (action === 'delete') {
      await deleteCUser(target.id)
      actionOk.value = true
      actionMessage.value = t('admin.c_users.toast_delete_ok')
    }
    confirmTarget.value = null
    confirmAction.value = ''
    await fetchList()
  } catch (err) {
    actionOk.value = false
    actionMessage.value = t('admin.error_save') + ': ' + (err?.message || err)
  } finally {
    submitting.value = false
  }
}

// ---- 动作：reset password ----
function askResetPassword(u) {
  resetResult.value = null
  copied.value = false
  submitting.value = true
  actionMessage.value = ''
  resetUserPassword(u.id)
    .then((res) => {
      resetResult.value = res
      nextTick(() => {
        if (pwdInputRef.value && pwdInputRef.value.select) {
          pwdInputRef.value.select()
        }
      })
    })
    .catch((err) => {
      actionOk.value = false
      actionMessage.value = t('admin.c_users.toast_reset_fail') + ': ' + (err?.message || err)
    })
    .finally(() => {
      submitting.value = false
    })
}

function closeReset() {
  resetResult.value = null
  copied.value = false
}

async function copyPwd() {
  if (!resetResult.value?.new_password) return
  try {
    await navigator.clipboard.writeText(resetResult.value.new_password)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2500)
  } catch {
    // fallback: select the input
    if (pwdInputRef.value && pwdInputRef.value.select) {
      pwdInputRef.value.select()
      try { document.execCommand('copy'); copied.value = true } catch {}
    }
  }
}

// ---- 工具 ----
function formatTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}
function formatAmount(v, currency) {
  if (v == null) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return `${n.toFixed(2)}${currency ? ' ' + currency : ''}`
}

</script>

<style scoped lang="scss">

.admin-main { padding: 28px 32px; min-width: 0; }
.admin-main__head { margin-bottom: 16px; }
.admin-main__head h1 { font-size: 22px; font-weight: 700; color: #0F172A; margin: 0 0 4px; }
.admin-main__sub { font-size: 13px; color: #64748B; margin: 0; }

.admin-filter { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.admin-filter__chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: #fff; color: #475569;
  border: 1px solid #E2E8F0; border-radius: 999px;
  padding: 6px 14px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background .15s, border-color .15s, color .15s;
}
.admin-filter__chip:hover { border-color: #94A3B8; color: #0F172A; }
.admin-filter__chip.is-active { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }

.admin-panel { margin-bottom: 0; }
.admin-panel__head { display: flex; justify-content: space-between; align-items: center; }
.admin-panel__meta { font-size: 12px; color: #94A3B8; font-weight: 600; }
.admin-panel__placeholder { padding: 32px 0; text-align: center; color: #94A3B8; font-size: 13px; }
.admin-panel__placeholder--err { color: #DC2626; }

.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th {
  text-align: left; font-weight: 600; color: #475569;
  font-size: 12px; letter-spacing: .03em; text-transform: uppercase;
  padding: 10px 12px; border-bottom: 1px solid #E2E8F0; background: #F8FAFC;
}
.admin-table td { padding: 11px 12px; border-bottom: 1px solid #F1F5F9; color: #0F172A; }
.admin-table__row { cursor: pointer; transition: background .1s; }
.admin-table__row:hover td { background: #F8FAFC; }
.admin-table__row.is-expanded td { background: #F1F5F9; }
.admin-table__detail-row td { background: #F8FAFC; padding: 0; }
.admin-table__mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }
.admin-table__muted { color: #94A3B8; font-size: 12px; }
.admin-table--nested { margin: 0; }
.admin-table--nested th { font-size: 11px; padding: 8px 12px; }

.btn-text {
  background: none; border: none; color: #3B6EF5; cursor: pointer;
  font-size: 13px; padding: 2px 6px; font-weight: 600;
}
.btn-text:hover { text-decoration: underline; }
.btn-text--danger { color: #DC2626; }

.admin-lang-tag {
  display: inline-block;
  font-size: 11px; font-weight: 600;
  background: #F1F5F9; color: #475569;
  padding: 1px 8px; border-radius: 999px;
}

.admin-pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: .03em;
  background: #F1F5F9; color: #475569;
}
.admin-pill--status-active         { background: #D1FAE5; color: #047857; }
.admin-pill--status-pending_destroy{ background: #FEF3C7; color: #B45309; }
.admin-pill--status-destroyed      { background: #E2E8F0; color: #475569; }
.admin-pill--status-disabled       { background: #FEE2E2; color: #B91C1C; }
.admin-pill--created   { background: #E0E7FF; color: #4338CA; }
.admin-pill--submitted { background: #DBEAFE; color: #1D4ED8; }
.admin-pill--reviewing { background: #FEF3C7; color: #B45309; }
.admin-pill--approved  { background: #D1FAE5; color: #047857; }
.admin-pill--rejected  { background: #FEE2E2; color: #B91C1C; }
.admin-pill--closed    { background: #E2E8F0; color: #475569; }
.admin-pill--abnormal  { background: #FCE7F3; color: #9D174D; }
.admin-pill--failed    { background: #FECACA; color: #991B1B; }

.admin-inline-detail { padding: 18px 24px; }
.admin-inline-detail__sub { margin-top: 18px; }
.admin-inline-detail__sub h4 {
  margin: 0 0 8px; font-size: 13px; color: #0F172A;
  text-transform: uppercase; letter-spacing: .05em;
}
.admin-dl { display: grid; grid-template-columns: 160px 1fr; gap: 6px 16px; margin: 0; font-size: 13px; }
.admin-dl--inline { grid-template-columns: 160px 1fr 160px 1fr; }
.admin-dl dt { color: #94A3B8; font-weight: 600; }
.admin-dl dd { margin: 0; color: #0F172A; }
.admin-mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }

.admin-pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
.admin-page-btn {
  background: #fff; color: #475569; border: 1px solid #E2E8F0;
  border-radius: 6px; padding: 7px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background .15s;
}
.admin-page-btn:hover { background: #F8FAFC; }
.admin-page-btn:disabled { opacity: .5; cursor: not-allowed; }
.admin-page-info { font-size: 13px; color: #64748B; font-weight: 600; }

.admin-actions__msg { margin-top: 12px; font-size: 13px; }
.admin-actions__msg.is-ok { color: #047857; }
.admin-actions__msg.is-err { color: #B91C1C; }

.admin-modal-mask {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .45);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.admin-modal {
  background: #fff; border-radius: 12px;
  padding: 0;
  width: 100%; max-width: 480px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, .25);
  overflow: hidden;
}
.admin-modal__head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 22px; border-bottom: 1px solid #E2E8F0;
}
.admin-modal__head h3 { margin: 0; font-size: 15px; font-weight: 600; color: #0F172A; }
.admin-modal__close {
  background: none; border: none; font-size: 22px;
  color: #94A3B8; cursor: pointer; line-height: 1;
}
.admin-modal__body { padding: 18px 22px; display: flex; flex-direction: column; gap: 10px; }
.admin-modal__hint { margin: 0; font-size: 13px; color: #64748B; }
.admin-modal__hint--warn { color: #B45309; }
.admin-modal__label {
  font-size: 12px; color: #64748B; font-weight: 600;
}
.admin-modal__input {
  width: 100%; box-sizing: border-box;
  border: 1px solid #E2E8F0; border-radius: 6px;
  padding: 8px 12px; font-size: 13px; font-family: inherit;
  background: #fff;
}
.admin-modal__input:focus {
  outline: none; border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59, 110, 245, .15);
}
.admin-modal__input--pwd {
  font-family: 'SF Mono', Menlo, monospace; letter-spacing: .04em;
}
.admin-pwd-display { display: flex; gap: 8px; }
.admin-pwd-display .admin-modal__input { flex: 1; }

.admin-modal__actions {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 22px; border-top: 1px solid #E2E8F0;
  background: #F8FAFC;
}
.admin-modal__btn {
  background: #fff; color: #475569;
  border: 1px solid #E2E8F0; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.admin-modal__btn:hover { background: #F1F5F9; }
.admin-modal__btn--primary { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.admin-modal__btn--primary:hover { background: #2563EB; border-color: #2563EB; }
.admin-modal__btn--primary:disabled { opacity: .6; cursor: not-allowed; }
.admin-modal__btn--danger { background: #DC2626; color: #fff; border-color: #DC2626; }
.admin-modal__btn--danger:hover { background: #B91C1C; border-color: #B91C1C; }
</style>
