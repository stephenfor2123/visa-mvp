<template>
  <div class="profile-page">
    <AppHeader scope="profile" />
    <main class="app-container app-page profile-page__main">
      <h1 class="section-title">{{ t('profile.page_title') }}</h1>

      <!-- ============================== Account card ============================== -->
      <AppCard v-if="profile">
        <template #header>
          <div class="profile-page__acct-head">
            <h3 class="profile-page__acct-title">{{ t('profile.account_section') }}</h3>
            <AppButton variant="ghost" size="sm" @click="onLogout">
              {{ t('profile.logout') }}
            </AppButton>
          </div>
        </template>

        <dl class="info-list">
          <div class="info-list__row">
            <dt>{{ t('profile.user_id') }}</dt>
            <dd>{{ profile.id }}</dd>
          </div>

          <!-- Email row — changeable. Shows current + (change) button + pending hint. -->
          <div class="info-list__row info-list__row--email">
            <dt>{{ t('profile.email_label') }}</dt>
            <dd>
              <div class="profile-page__email-block">
                <div class="profile-page__email-current">
                  <span class="profile-page__email-text">{{ profile.email }}</span>
                  <AppButton
                    variant="ghost"
                    size="sm"
                    @click="openEmailDialog"
                    :disabled="!!profile.email_pending"
                  >
                    {{ t('profile.email_change') }}
                  </AppButton>
                </div>
                <div v-if="profile.email_pending" class="profile-page__email-pending">
                  <span class="profile-page__email-pending-dot"></span>
                  <span>
                    {{ t('profile.email_change_pending_hint', { email: profile.email_pending }) }}
                  </span>
                  <button
                    class="profile-page__email-cancel"
                    @click="onCancelEmailChange"
                  >
                    {{ t('profile.email_change_cancel_pending') }}
                  </button>
                </div>
              </div>
            </dd>
          </div>

          <div class="info-list__row">
            <dt>{{ t('profile.registered_at') }}</dt>
            <dd>{{ formatDate(profile.created_at) }}</dd>
          </div>
          <div class="info-list__row">
            <dt>{{ t('profile.status') }}</dt>
            <dd>
              <span class="badge badge--neutral">
                <span class="badge__dot"></span>
                {{ t('profile.active') }}
              </span>
            </dd>
          </div>
        </dl>
      </AppCard>

      <AppCard v-else>
        <p>{{ t('profile.no_user_info') }}</p>
        <AppButton variant="primary" size="md" @click="$router.push('/login')">
          {{ t('profile.go_login') }}
        </AppButton>
      </AppCard>

      <!-- ============================== Local data (browser-only) ============================== -->
      <AppCard v-if="profile" class="profile-page__danger-card">
        <template #header>
          <h3 class="profile-page__danger-title">{{ t('privacy_local.section_title') }}</h3>
        </template>
        <p class="profile-page__danger-desc">{{ t('privacy_local.section_desc') }}</p>
        <AppButton variant="ghost" size="sm" class="profile-page__danger-btn" data-testid="profile-clear-local" @click="clearLocalOpen = true">
          {{ t('privacy_local.clear_btn') }}
        </AppButton>
      </AppCard>

      <!-- ============================== Privacy rights (DSAR) ============================== -->
      <AppCard v-if="profile && profile.status === 'active'" class="profile-page__danger-card">
        <template #header>
          <h3 class="profile-page__danger-title">{{ t('profile.privacy_rights_section') }}</h3>
        </template>
        <p class="profile-page__danger-desc">{{ t('profile.privacy_rights_desc') }}</p>
        <div class="profile-page__privacy-actions">
          <AppButton variant="ghost" size="sm" :loading="exportBusy" data-testid="profile-export-data" @click="onExportData">
            {{ t('profile.export_data_btn') }}
          </AppButton>
          <AppButton
            variant="ghost"
            size="sm"
            :loading="restrictBusy"
            data-testid="profile-toggle-restriction"
            @click="onToggleRestriction"
          >
            {{ profile.processing_restricted ? t('profile.lift_restriction_btn') : t('profile.restrict_processing_btn') }}
          </AppButton>
          <AppButton variant="ghost" size="sm" data-testid="profile-revoke-consent" @click="onRevokeConsent">
            {{ t('profile.revoke_consent_btn') }}
          </AppButton>
        </div>
        <p class="profile-page__danger-hint">{{ t('profile.delete_account_hint', { email: t('agreement.privacy_contact_email') }) }}</p>
      </AppCard>

      <!-- ============================== Delete account ============================== -->
      <AppCard v-if="profile && profile.status === 'active'" class="profile-page__danger-card">
        <template #header>
          <h3 class="profile-page__danger-title">{{ t('profile.delete_account_section') }}</h3>
        </template>
        <p class="profile-page__danger-desc">{{ t('profile.delete_account_desc') }}</p>
        <p class="profile-page__danger-hint">{{ t('profile.delete_account_hint', { email: t('agreement.privacy_contact_email') }) }}</p>
        <AppButton variant="ghost" size="sm" class="profile-page__danger-btn" @click="deleteOpen = true">
          {{ t('profile.delete_account_btn') }}
        </AppButton>
      </AppCard>

      <AppCard v-else-if="profile && profile.status === 'pending_destroy'" class="profile-page__danger-card">
        <p class="profile-page__danger-desc">{{ t('profile.delete_account_pending') }}</p>
        <AppButton variant="primary" size="sm" :loading="cancelDeleteBusy" data-testid="profile-cancel-delete" @click="onCancelDeleteAccount">
          {{ t('profile.cancel_delete_btn') }}
        </AppButton>
      </AppCard>

      <!-- ============================== Documents shortcut card ============================== -->
      <!-- W48: shortcut to the cross-device upload hub. Sits below Account so
           returning users see it without scrolling past applicants. -->
      <AppCard>
        <template #header>
          <div class="profile-page__doc-head">
            <div>
              <h3 class="profile-page__doc-title">{{ t('profile.documents_section') }}</h3>
              <p class="profile-page__doc-sub">{{ t('profile.documents_subtitle') }}</p>
            </div>
            <AppButton
              variant="primary"
              size="sm"
              data-testid="profile-open-documents"
              @click="$router.push('/profile/documents')"
            >
              {{ t('profile.documents_open') }} →
            </AppButton>
          </div>
        </template>
        <div class="profile-page__doc-tips">
          <div class="profile-page__doc-tip">
            <span class="profile-page__doc-tip-icon">📷</span>
            <div>
              <p class="profile-page__doc-tip-t">{{ t('profile.doc_tip_mobile_t') }}</p>
              <p class="profile-page__doc-tip-d">{{ t('profile.doc_tip_mobile_d') }}</p>
            </div>
          </div>
          <div class="profile-page__doc-tip">
            <span class="profile-page__doc-tip-icon">🔁</span>
            <div>
              <p class="profile-page__doc-tip-t">{{ t('profile.doc_tip_reuse_t') }}</p>
              <p class="profile-page__doc-tip-d">{{ t('profile.doc_tip_reuse_d') }}</p>
            </div>
          </div>
        </div>
      </AppCard>

      <!-- ============================== Applicants card ============================== -->
      <AppCard class="profile-page__applicants-card">
        <template #header>
          <div class="profile-page__applicants-head">
            <div>
              <h3 class="profile-page__applicants-title">
                {{ t('profile.applicants_section') }}
              </h3>
              <p class="profile-page__applicants-sub">
                {{ t('profile.applicants_subtitle') }}
              </p>
            </div>
            <AppButton
              variant="primary"
              size="sm"
              :disabled="atLimit"
              @click="openAddDialog"
            >
              + {{ t('profile.add_applicant') }}
            </AppButton>
          </div>
        </template>

        <!-- Empty state -->
        <div v-if="!loading && applicants.length === 0" class="profile-page__empty">
          <div class="profile-page__empty-icon">👤</div>
          <h4 class="profile-page__empty-title">{{ t('profile.no_applicants_title') }}</h4>
          <p class="profile-page__empty-desc">{{ t('profile.no_applicants_desc') }}</p>
          <AppButton variant="primary" size="sm" @click="openAddDialog">
            + {{ t('profile.add_applicant') }}
          </AppButton>
        </div>

        <!-- List -->
        <div v-else class="profile-page__applicants-list">
          <div
            v-for="a in applicants"
            :key="a.id"
            class="applicant-row"
          >
            <div class="applicant-row__avatar">
              {{ avatarLetter(a) }}
            </div>
            <div class="applicant-row__body">
              <div class="applicant-row__name">
                {{ a.display_name }}
                <span v-if="a.is_minor" class="applicant-row__badge">{{ t('profile.applicant_minor_badge') }}</span>
              </div>
              <div class="applicant-row__passport">
                <span class="applicant-row__passport-label">
                  {{ t('profile.applicant_passport_label') }}
                </span>
                <span class="applicant-row__passport-no">{{ a.passport_no }}</span>
              </div>
              <div class="applicant-row__meta">
                {{ t('profile.applicant_updated', { date: formatDate(a.updated_at) }) }}
              </div>
            </div>
            <div class="applicant-row__actions">
              <AppButton variant="ghost" size="sm" @click="openEditDialog(a)">
                {{ t('profile.applicant_edit') }}
              </AppButton>
              <AppButton variant="ghost" size="sm" @click="openDeleteDialog(a)">
                {{ t('profile.applicant_delete') }}
              </AppButton>
            </div>
          </div>
        </div>

        <!-- Limit hint at bottom -->
        <div v-if="profile" class="profile-page__limit-hint">
          {{ t('profile.applicant_limit_hint', { n: profile.applicant_limit }) }}
        </div>
      </AppCard>

      <!-- ============================== Add/Edit dialog ============================== -->
      <div v-if="formOpen" class="profile-page__modal-backdrop" @click.self="closeFormDialog">
        <div class="profile-page__modal" role="dialog" aria-modal="true">
          <h3 class="profile-page__modal-title">
            {{ editingId
              ? t('profile.applicant_edit_dialog_title')
              : t('profile.applicant_add_dialog_title') }}
          </h3>

          <div class="profile-page__modal-body">
            <label class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.applicant_surname') }}
              </span>
              <input
                ref="surnameInput"
                v-model="form.surname"
                class="profile-page__input"
                type="text"
                maxlength="64"
                @input="clearFieldError('surname')"
              />
              <span v-if="errors.surname" class="profile-page__field-err">
                {{ errors.surname }}
              </span>
            </label>

            <label class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.applicant_given_name') }}
              </span>
              <input
                v-model="form.given_name"
                class="profile-page__input"
                type="text"
                maxlength="64"
                @input="clearFieldError('given_name')"
              />
              <span v-if="errors.given_name" class="profile-page__field-err">
                {{ errors.given_name }}
              </span>
            </label>

            <label class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.applicant_passport_label') }}
              </span>
              <input
                v-model="form.passport_no"
                class="profile-page__input profile-page__input--mono"
                type="text"
                maxlength="32"
                @input="clearFieldError('passport_no')"
              />
              <span v-if="errors.passport_no" class="profile-page__field-err">
                {{ errors.passport_no }}
              </span>
              <span v-else class="profile-page__field-hint">
                {{ t('profile.applicant_passport_hint') }}
              </span>
            </label>

            <p class="profile-page__field-hint profile-page__minor-guide">
              {{ t('profile.applicant_minor_guide') }}
            </p>

            <label class="profile-page__check">
              <input
                v-model="form.is_minor"
                type="checkbox"
                data-testid="applicant-is-minor"
              />
              <span>{{ t('profile.applicant_is_minor') }}</span>
            </label>

            <label v-if="form.is_minor" class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.applicant_guardian_relationship') }}
              </span>
              <select
                v-model="form.guardian_relationship"
                class="profile-page__input"
                data-testid="applicant-guardian-rel"
                @change="clearFieldError('guardian_relationship')"
              >
                <option value="">{{ t('profile.applicant_guardian_placeholder') }}</option>
                <option value="parent">{{ t('profile.guardian_parent') }}</option>
                <option value="legal_guardian">{{ t('profile.guardian_legal') }}</option>
                <option value="other">{{ t('profile.guardian_other') }}</option>
              </select>
              <span v-if="errors.guardian_relationship" class="profile-page__field-err">
                {{ errors.guardian_relationship }}
              </span>
            </label>
          </div>

          <div class="profile-page__modal-foot">
            <AppButton variant="ghost" size="md" @click="closeFormDialog" :disabled="saving">
              {{ t('profile.applicant_cancel') }}
            </AppButton>
            <AppButton variant="primary" size="md" @click="onSaveApplicant" :loading="saving">
              {{ t('profile.applicant_save') }}
            </AppButton>
          </div>
        </div>
      </div>

      <!-- ============================== Delete confirm ============================== -->
      <div v-if="deleting" class="profile-page__modal-backdrop" @click.self="deleting = null">
        <div class="profile-page__modal profile-page__modal--sm" role="dialog" aria-modal="true">
          <h3 class="profile-page__modal-title">
            {{ t('profile.applicant_delete_title') }}
          </h3>
          <p class="profile-page__modal-desc">
            {{ t('profile.applicant_delete_desc', { name: deleting.display_name }) }}
          </p>
          <div class="profile-page__modal-foot">
            <AppButton variant="ghost" size="md" @click="deleting = null" :disabled="deletingBusy">
              {{ t('profile.applicant_cancel') }}
            </AppButton>
            <AppButton variant="primary" size="md" @click="onConfirmDelete" :loading="deletingBusy">
              {{ t('profile.applicant_delete_confirm') }}
            </AppButton>
          </div>
        </div>
      </div>

      <!-- ============================== Email change dialog ============================== -->
      <div v-if="emailOpen" class="profile-page__modal-backdrop" @click.self="emailOpen = false">
        <div class="profile-page__modal" role="dialog" aria-modal="true">
          <h3 class="profile-page__modal-title">
            {{ t('profile.email_change_title') }}
          </h3>
          <p class="profile-page__modal-desc">
            {{ t('profile.email_change_subtitle') }}
          </p>

          <div class="profile-page__modal-body">
            <label class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.email_change_new_label') }}
              </span>
              <input
                v-model="emailForm.new_email"
                class="profile-page__input"
                type="email"
                @input="clearEmailError()"
              />
              <span v-if="emailError" class="profile-page__field-err">
                {{ emailError }}
              </span>
            </label>

            <label class="profile-page__field">
              <span class="profile-page__field-label">
                {{ t('profile.email_change_pwd_label') }}
              </span>
              <input
                v-model="emailForm.password"
                class="profile-page__input"
                type="password"
                @input="clearEmailError()"
              />
            </label>
          </div>

          <div class="profile-page__modal-foot">
            <AppButton variant="ghost" size="md" @click="emailOpen = false" :disabled="emailSending">
              {{ t('profile.applicant_cancel') }}
            </AppButton>
            <AppButton
              variant="primary"
              size="md"
              @click="onSendEmailChange"
              :loading="emailSending"
            >
              {{ t('profile.email_change_send') }}
            </AppButton>
          </div>
        </div>
      </div>

      <!-- ============================== Clear local data confirm ============================== -->
      <div v-if="clearLocalOpen" class="profile-page__modal-backdrop" @click.self="clearLocalOpen = false">
        <div class="profile-page__modal profile-page__modal--sm" role="dialog" aria-modal="true">
          <h3 class="profile-page__modal-title">{{ t('privacy_local.clear_confirm_title') }}</h3>
          <p class="profile-page__modal-desc">{{ t('privacy_local.clear_confirm_desc') }}</p>
          <div class="profile-page__modal-foot">
            <AppButton variant="ghost" size="md" @click="clearLocalOpen = false">
              {{ t('profile.applicant_cancel') }}
            </AppButton>
            <AppButton variant="primary" size="md" data-testid="profile-clear-local-confirm" @click="onClearLocalData">
              {{ t('privacy_local.clear_confirm_btn') }}
            </AppButton>
          </div>
        </div>
      </div>

      <!-- ============================== Delete account confirm ============================== -->
      <div v-if="deleteOpen" class="profile-page__modal-backdrop" @click.self="deleteOpen = false">
        <div class="profile-page__modal profile-page__modal--sm" role="dialog" aria-modal="true">
          <h3 class="profile-page__modal-title">{{ t('profile.delete_account_confirm_title') }}</h3>
          <p class="profile-page__modal-desc">{{ t('profile.delete_account_confirm_desc') }}</p>
          <div class="profile-page__modal-body">
            <label v-if="profile?.has_password !== false" class="profile-page__field">
              <span class="profile-page__field-label">{{ t('profile.email_change_pwd_label') }}</span>
              <input
                v-model="deleteForm.password"
                class="profile-page__input"
                type="password"
                @input="deleteError = ''"
              />
              <span v-if="deleteError" class="profile-page__field-err">{{ deleteError }}</span>
            </label>
            <p v-else class="profile-page__modal-desc">{{ t('profile.delete_account_oauth_hint') }}</p>
            <span v-if="deleteError && profile?.has_password === false" class="profile-page__field-err">{{ deleteError }}</span>
          </div>
          <div class="profile-page__modal-foot">
            <AppButton variant="ghost" size="md" @click="deleteOpen = false" :disabled="deleteBusy">
              {{ t('profile.applicant_cancel') }}
            </AppButton>
            <AppButton variant="primary" size="md" :loading="deleteBusy" @click="onConfirmAccountDelete">
              {{ t('profile.delete_account_confirm_btn') }}
            </AppButton>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AppCard from '@/components/AppCard.vue'
import AppButton from '@/components/AppButton.vue'
import AppHeader from '@/components/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  cancelDeleteAccount,
  cancelEmailChange,
  createApplicant,
  deleteAccount,
  deleteApplicant,
  exportMyData,
  getProfile,
  listApplicants,
  requestEmailChange,
  revokeConsent,
  setProcessingRestriction,
  updateApplicant,
} from '@/api/profile'
import { clearAllLocalVisaData } from '@/utils/localPrivacyStorage'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
auth.hydrate()
const toast = useToast()

// --------------------------------------------------------------------------- //
// State                                                                       //
// --------------------------------------------------------------------------- //
const profile = ref(null)
const applicants = ref([])
const loading = ref(false)

const formOpen = ref(false)
const editingId = ref(null)
const saving = ref(false)
const surnameInput = ref(null)
const form = reactive({
  surname: '',
  given_name: '',
  passport_no: '',
  is_minor: false,
  guardian_relationship: '',
})
const errors = reactive({
  surname: '',
  given_name: '',
  passport_no: '',
  guardian_relationship: '',
})

const deleting = ref(null)
const deletingBusy = ref(false)

const emailOpen = ref(false)
const emailSending = ref(false)
const emailError = ref('')
const emailForm = reactive({ new_email: '', password: '' })

const deleteOpen = ref(false)
const clearLocalOpen = ref(false)
const deleteBusy = ref(false)
const cancelDeleteBusy = ref(false)
const exportBusy = ref(false)
const restrictBusy = ref(false)
const deleteError = ref('')
const deleteForm = reactive({ password: '' })

// --------------------------------------------------------------------------- //
// Computed                                                                    //
// --------------------------------------------------------------------------- //
const atLimit = computed(() => {
  if (!profile.value) return false
  return applicants.value.length >= (profile.value.applicant_limit || 10)
})

// --------------------------------------------------------------------------- //
// Data loaders                                                                //
// --------------------------------------------------------------------------- //
async function loadAll() {
  loading.value = true
  try {
    const [p, list] = await Promise.all([getProfile(), listApplicants()])
    profile.value = p
    applicants.value = list
  } catch (e) {
    console.error(e)
    toast.error(t('profile.err_load_failed'))
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

// --------------------------------------------------------------------------- //
// Form helpers                                                                //
// --------------------------------------------------------------------------- //
function clearFieldError(field) {
  errors[field] = ''
}

function avatarLetter(a) {
  // Show first letter of surname; if ASCII word, use initial of given_name.
  const s = (a?.surname || '').trim()
  const g = (a?.given_name || '').trim()
  if (s && /^[A-Za-z]+$/.test(s)) {
    return (g.charAt(0) || s.charAt(0) || '?').toUpperCase()
  }
  return s.charAt(0) || '?'
}

function formatDate(s) {
  if (!s) return '-'
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    return d.toLocaleString()
  } catch {
    return s
  }
}

function validateLocal() {
  let ok = true
  errors.surname = ''
  errors.given_name = ''
  errors.passport_no = ''
  errors.guardian_relationship = ''

  if (!form.surname.trim()) {
    errors.surname = t('profile.err_name_empty')
    ok = false
  }
  if (!form.given_name.trim()) {
    errors.given_name = t('profile.err_name_empty')
    ok = false
  }
  const pp = form.passport_no.trim()
  if (!pp) {
    errors.passport_no = t('profile.err_passport_empty')
    ok = false
  } else if (!/^[A-Za-z0-9 \-]{5,32}$/.test(pp)) {
    errors.passport_no = t('profile.err_passport_format')
    ok = false
  }
  if (form.is_minor && !form.guardian_relationship) {
    errors.guardian_relationship = t('profile.err_guardian_required')
    ok = false
  }
  return ok
}

function openAddDialog() {
  editingId.value = null
  form.surname = ''
  form.given_name = ''
  form.passport_no = ''
  form.is_minor = false
  form.guardian_relationship = ''
  errors.surname = ''
  errors.given_name = ''
  errors.passport_no = ''
  errors.guardian_relationship = ''
  formOpen.value = true
  nextTick(() => surnameInput.value?.focus())
}

function openEditDialog(a) {
  editingId.value = a.id
  form.surname = a.surname
  form.given_name = a.given_name
  form.passport_no = a.passport_no
  form.is_minor = Boolean(a.is_minor)
  form.guardian_relationship = a.guardian_relationship || ''
  errors.surname = ''
  errors.given_name = ''
  errors.passport_no = ''
  errors.guardian_relationship = ''
  formOpen.value = true
  nextTick(() => surnameInput.value?.focus())
}

function closeFormDialog() {
  if (saving.value) return
  formOpen.value = false
}

async function onSaveApplicant() {
  if (!validateLocal()) return
  saving.value = true
  try {
    if (editingId.value) {
      const updated = await updateApplicant(editingId.value, {
        surname: form.surname.trim(),
        given_name: form.given_name.trim(),
        passport_no: form.passport_no.trim(),
        is_minor: form.is_minor,
        guardian_relationship: form.is_minor ? form.guardian_relationship : null,
      })
      const idx = applicants.value.findIndex((a) => a.id === updated.id)
      if (idx >= 0) applicants.value[idx] = updated
      toast.success(t('profile.saved'))
    } else {
      const created = await createApplicant({
        surname: form.surname.trim(),
        given_name: form.given_name.trim(),
        passport_no: form.passport_no.trim(),
        is_minor: form.is_minor,
        guardian_relationship: form.is_minor ? form.guardian_relationship : null,
      })
      applicants.value.unshift(created)
      toast.success(t('profile.saved'))
    }
    formOpen.value = false
  } catch (e) {
    if (e?.code === '9002') {
      errors.surname = t('profile.err_dup_name')
    } else if (e?.code === '9003') {
      errors.passport_no = t('profile.err_dup_passport')
    } else if (e?.code === '9004') {
      toast.error(t('profile.err_limit_reached', { n: profile.value?.applicant_limit || 10 }))
    } else {
      toast.error(t('profile.err_save_failed', { msg: e?.message || '' }))
    }
  } finally {
    saving.value = false
  }
}

function openDeleteDialog(a) {
  deleting.value = a
}

async function onConfirmDelete() {
  if (!deleting.value) return
  deletingBusy.value = true
  const id = deleting.value.id
  try {
    await deleteApplicant(id)
    applicants.value = applicants.value.filter((a) => a.id !== id)
    deleting.value = null
    toast.success(t('profile.deleted'))
  } catch (e) {
    toast.error(t('profile.err_delete_failed', { msg: e?.message || '' }))
  } finally {
    deletingBusy.value = false
  }
}

function onClearLocalData() {
  clearAllLocalVisaData()
  clearLocalOpen.value = false
  toast.success(t('privacy_local.clear_success'))
}

async function onConfirmAccountDelete() {
  deleteError.value = ''
  const needsPwd = profile.value?.has_password !== false
  if (needsPwd && !deleteForm.password) {
    deleteError.value = t('profile.err_pwd_required')
    return
  }
  deleteBusy.value = true
  try {
    await deleteAccount({ password: needsPwd ? deleteForm.password : undefined })
    deleteOpen.value = false
    profile.value = { ...profile.value, status: 'pending_destroy' }
    toast.success(t('profile.delete_account_scheduled'))
    await auth.logout()
    router.push('/login')
  } catch (e) {
    if (e?.code === '2001') {
      deleteError.value = t('profile.err_pwd_wrong')
    } else {
      deleteError.value = e?.message || t('profile.delete_account_failed')
    }
  } finally {
    deleteBusy.value = false
  }
}

async function onCancelDeleteAccount() {
  cancelDeleteBusy.value = true
  try {
    await cancelDeleteAccount()
    profile.value = { ...profile.value, status: 'active' }
    toast.success(t('profile.cancel_delete_success'))
  } catch (e) {
    toast.error(e?.message || t('profile.cancel_delete_failed'))
  } finally {
    cancelDeleteBusy.value = false
  }
}

async function onExportData() {
  exportBusy.value = true
  try {
    const data = await exportMyData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `htex-data-export-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(t('profile.export_data_success'))
  } catch (e) {
    toast.error(e?.message || t('profile.export_data_failed'))
  } finally {
    exportBusy.value = false
  }
}

async function onToggleRestriction() {
  restrictBusy.value = true
  try {
    const next = !profile.value?.processing_restricted
    const res = await setProcessingRestriction(next)
    profile.value = { ...profile.value, processing_restricted: res.processing_restricted }
    toast.success(next ? t('profile.restrict_processing_on') : t('profile.restrict_processing_off'))
  } catch (e) {
    toast.error(e?.message || t('profile.privacy_action_failed'))
  } finally {
    restrictBusy.value = false
  }
}

async function onRevokeConsent() {
  try {
    await revokeConsent({ purpose: 'sensitive_upload' })
    try {
      const { clearLocalSensitiveConsent } = await import('@/utils/sensitiveConsent')
      clearLocalSensitiveConsent()
    } catch { /* ignore */ }
    toast.success(t('profile.revoke_consent_success'))
  } catch (e) {
    toast.error(e?.message || t('profile.privacy_action_failed'))
  }
}

// --------------------------------------------------------------------------- //
// Email change                                                                //
// --------------------------------------------------------------------------- //
function openEmailDialog() {
  emailForm.new_email = ''
  emailForm.password = ''
  emailError.value = ''
  emailOpen.value = true
}

function clearEmailError() {
  emailError.value = ''
}

async function onSendEmailChange() {
  emailError.value = ''
  if (!emailForm.new_email.trim()) {
    emailError.value = t('profile.err_email_invalid')
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailForm.new_email.trim())) {
    emailError.value = t('profile.err_email_invalid')
    return
  }
  if (!emailForm.password) {
    emailError.value = t('profile.err_pwd_required')
    return
  }
  emailSending.value = true
  try {
    const res = await requestEmailChange({
      new_email: emailForm.new_email.trim(),
      password: emailForm.password,
    })
    profile.value = { ...profile.value, email_pending: res.pending_email }
    emailOpen.value = false
    toast.success(t('profile.email_change_sent', { email: res.pending_email }))
  } catch (e) {
    if (e?.code === '2001') emailError.value = t('profile.err_pwd_wrong')
    else if (e?.code === '2003' || e?.code === '10003') emailError.value = t('profile.err_email_taken')
    else emailError.value = e?.message || t('profile.err_save_failed', { msg: '' })
  } finally {
    emailSending.value = false
  }
}

async function onCancelEmailChange() {
  try {
    await cancelEmailChange()
    profile.value = { ...profile.value, email_pending: null }
  } catch (e) {
    toast.error(t('profile.err_save_failed', { msg: e?.message || '' }))
  }
}

// --------------------------------------------------------------------------- //
// Logout                                                                      //
// --------------------------------------------------------------------------- //
function onLogout() {
  auth.logout()
  toast.success(t('toast.logout_success'))
  router.push('/login')
}
</script>

<style scoped lang="scss">
.profile-page__main {
  padding-top: 32px;
  padding-bottom: 64px;
  max-width: 720px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 20px;
  color: var(--ink-1, #1a1a1a);
}

/* ----- Account card head ----- */
.profile-page__acct-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.profile-page__acct-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-1, #1a1a1a);
}

/* ----- Info list (account card) ----- */
.info-list {
  margin: 0;
  padding: 0;
}
.info-list__row {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px dashed var(--border, #e5e7eb);
  font-size: 14px;
}
.info-list__row:last-child {
  border-bottom: none;
}
.info-list__row dt {
  color: var(--ink-3, #6b7280);
  margin: 0;
  line-height: 1.5;
}
.info-list__row dd {
  color: var(--ink-1, #1a1a1a);
  margin: 0;
  font-weight: 500;
  line-height: 1.5;
}
.info-list__row--email dd {
  font-weight: 400;
}

/* ----- Email block ----- */
.profile-page__email-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.profile-page__email-current {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.profile-page__email-text {
  font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 13px;
  color: var(--ink-1, #1a1a1a);
  font-weight: 500;
  background: var(--bg-2, #f9fafb);
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid var(--border, #e5e7eb);
}
.profile-page__email-pending {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-3, #6b7280);
  flex-wrap: wrap;
}
.profile-page__email-pending-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  flex: 0 0 auto;
}
.profile-page__email-cancel {
  background: none;
  border: none;
  padding: 0;
  font-size: 12px;
  color: #2563eb;
  cursor: pointer;
  text-decoration: underline;
}
.profile-page__email-cancel:hover {
  color: #1d4ed8;
}

/* ----- Badge ----- */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}
.badge--neutral {
  background: #f3f4f6;
  color: #374151;
}
.badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

/* ----- Applicants card ----- */
.profile-page__applicants-card {
  margin-top: 20px;
}
.profile-page__applicants-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

/* ====== W48: Documents shortcut card ====== */
.profile-page__doc-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.profile-page__doc-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.profile-page__doc-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748B;
}
.profile-page__doc-tips {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.profile-page__doc-tip {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  background: #F8FAFC;
}
.profile-page__doc-tip-icon {
  font-size: 20px;
  line-height: 1;
}
.profile-page__doc-tip-t {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #0F172A;
}
.profile-page__doc-tip-d {
  margin: 4px 0 0;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}
@media (max-width: 540px) {
  .profile-page__doc-tips {
    grid-template-columns: 1fr;
  }
}
.profile-page__applicants-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-1, #1a1a1a);
}
.profile-page__applicants-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-3, #6b7280);
}
.profile-page__limit-hint {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border, #e5e7eb);
  font-size: 12px;
  color: var(--ink-3, #6b7280);
  text-align: right;
}

/* ----- Empty state ----- */
.profile-page__empty {
  text-align: center;
  padding: 32px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.profile-page__empty-icon {
  font-size: 36px;
  line-height: 1;
  opacity: 0.5;
}
.profile-page__empty-title {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-1, #1a1a1a);
}
.profile-page__empty-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--ink-3, #6b7280);
}

/* ----- Applicant list ----- */
.profile-page__applicants-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.applicant-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 10px;
  background: #fff;
  transition: background-color 0.15s;
}
.applicant-row:hover {
  background: var(--bg-2, #f9fafb);
}
.applicant-row__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--brand, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 16px;
  flex: 0 0 auto;
}
.applicant-row__body {
  flex: 1 1 auto;
  min-width: 0;
}
.applicant-row__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-1, #1a1a1a);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.applicant-row__badge {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-2, #f3f4f6);
  color: var(--ink-3, #6b7280);
}
.applicant-row__passport {
  margin-top: 2px;
  font-size: 12px;
  color: var(--ink-3, #6b7280);
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.applicant-row__passport-label {
  font-size: 11px;
  color: var(--ink-3, #6b7280);
}
.applicant-row__passport-no {
  font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  color: var(--ink-1, #1a1a1a);
  font-weight: 500;
  font-size: 13px;
}
.applicant-row__meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--ink-3, #6b7280);
}
.applicant-row__actions {
  display: flex;
  gap: 4px;
  flex: 0 0 auto;
}

.profile-page__danger-card {
  border: 1px solid #fecaca;
  background: #fffafa;
}
.profile-page__danger-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #b91c1c;
}
.profile-page__danger-desc,
.profile-page__danger-hint {
  margin: 0 0 8px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}
.profile-page__danger-btn {
  color: #b91c1c !important;
  margin-top: 8px;
}
.profile-page__privacy-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

/* ----- Modal ----- */
.profile-page__modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.profile-page__modal {
  background: #fff;
  border-radius: 12px;
  width: 100%;
  max-width: 440px;
  padding: 20px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
}
.profile-page__modal--sm {
  max-width: 360px;
}
.profile-page__modal-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
  color: var(--ink-1, #1a1a1a);
}
.profile-page__modal-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--ink-3, #6b7280);
  line-height: 1.5;
}
.profile-page__modal-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 16px;
}
.profile-page__modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ----- Form field ----- */
.profile-page__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.profile-page__field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-1, #1a1a1a);
}
.profile-page__input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  color: var(--ink-1, #1a1a1a);
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}
.profile-page__input:focus {
  border-color: var(--brand, #2563eb);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.profile-page__input--mono {
  font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  letter-spacing: 0.5px;
}
.profile-page__field-err {
  font-size: 12px;
  color: #dc2626;
}
.profile-page__field-hint {
  font-size: 12px;
  color: var(--ink-3, #6b7280);
}
.profile-page__minor-guide {
  margin: 0 0 4px;
  line-height: 1.45;
}
.profile-page__check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-2, #374151);
  cursor: pointer;
  user-select: none;
  margin-bottom: 4px;
}
.profile-page__check input {
  margin-top: 2px;
  flex-shrink: 0;
}
</style>
