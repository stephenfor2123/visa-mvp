<!-- ForgotPassword.vue — 邮箱验证链接重置密码 -->
<template>
  <div class="auth-page">
    <AppHeader scope="forgot-password" />
    <main class="auth-shell">
      <!-- Success State -->
      <AppCard v-if="success" class="auth-card">
        <div class="success-panel">
          <p class="success-panel__icon">✅</p>
          <h2 class="success-panel__title">{{ t('forgot.success_title') }}</h2>
          <p class="success-panel__desc">{{ t('forgot.success_desc') }}</p>
          <AppButton variant="primary" size="lg" @click="$router.push('/login')">
            {{ t('forgot.go_login') }}
          </AppButton>
        </div>
      </AppCard>

      <!-- Email sent (step 1 done) -->
      <AppCard v-else-if="emailSent" class="auth-card">
        <div class="success-panel">
          <p class="success-panel__icon">📧</p>
          <h2 class="success-panel__title">{{ t('forgot.email_sent_title') }}</h2>
          <p class="success-panel__desc">{{ t('forgot.email_sent_desc') }}</p>
          <AppButton variant="ghost" size="md" @click="$router.push('/login')">
            {{ t('forgot.back_login') }}
          </AppButton>
        </div>
      </AppCard>

      <!-- Step 2: set new password (token from email link) -->
      <AppCard v-else-if="hasToken" class="auth-card">
        <h1 class="auth-title">{{ t('forgot.set_pwd_title') }}</h1>
        <p class="auth-sub">{{ t('forgot.set_pwd_subtitle') }}</p>

        <form class="auth-form" @submit.prevent="onSubmitReset" novalidate>
          <AppInput
            v-model="newPwd"
            type="password"
            :label="t('forgot.new_pwd_label')"
            :placeholder="t('forgot.new_pwd_placeholder')"
            required
            :error="errors.newPwd"
            :hint="pwdHint"
            autocomplete="new-password"
            password-toggle
            data-testid="forgot-new-pwd"
            @blur="errors.newPwd = validatePassword(newPwd) ? t(validatePassword(newPwd)) : ''"
          />

          <AppInput
            v-model="confirmPwd"
            type="password"
            :label="t('forgot.confirm_pwd_label')"
            :placeholder="t('forgot.confirm_pwd_placeholder')"
            required
            :error="errors.confirmPwd"
            autocomplete="new-password"
            password-toggle
            data-testid="forgot-confirm-pwd"
            @blur="errors.confirmPwd = validateConfirmPassword(confirmPwd, newPwd) ? t(validateConfirmPassword(confirmPwd, newPwd)) : ''"
          />

          <p v-if="globalError" class="form-error" data-testid="forgot-global-error">
            ❌ {{ globalError }}
          </p>

          <AppButton
            type="submit"
            variant="primary"
            size="lg"
            :loading="submitting"
            :disabled="submitting"
            class="auth-submit"
            data-testid="forgot-submit"
          >
            {{ submitting ? t('forgot.submitting') : t('forgot.submit') }}
          </AppButton>
        </form>
      </AppCard>

      <!-- Step 1: request reset link -->
      <AppCard v-else class="auth-card">
        <h1 class="auth-title">{{ t('forgot.page_title') }}</h1>
        <p class="auth-sub">{{ t('forgot.page_subtitle') }}</p>

        <form class="auth-form" @submit.prevent="onSubmitRequest" novalidate>
          <AppInput
            v-model="account"
            :label="t('forgot.account_label')"
            :placeholder="t('forgot.account_placeholder')"
            maxlength="120"
            required
            :error="errors.account"
            data-testid="forgot-account"
            @blur="errors.account = validateAccount(account) ? t(validateAccount(account)) : ''"
          />

          <p v-if="globalError" class="form-error" data-testid="forgot-global-error">
            ❌ {{ globalError }}
          </p>

          <AppButton
            type="submit"
            variant="primary"
            size="lg"
            :loading="submitting"
            :disabled="submitting"
            class="auth-submit"
            data-testid="forgot-request"
          >
            {{ submitting ? t('forgot.requesting') : t('forgot.request_link') }}
          </AppButton>
        </form>

        <div class="auth-foot">
          <router-link to="/login" class="auth-foot__link">
            ← {{ t('forgot.back_login') }}
          </router-link>
        </div>
      </AppCard>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { requestPasswordReset, resetPassword } from '@/api/auth'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import AppHeader from '@/components/AppHeader.vue'
import { validateAccount, validatePassword, validateConfirmPassword } from '@/utils/validation'

const { t } = useI18n()
const route = useRoute()

const account = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const resetToken = ref('')
const errors = ref({ account: '', newPwd: '', confirmPwd: '' })
const globalError = ref('')
const submitting = ref(false)
const success = ref(false)
const emailSent = ref(false)

const hasToken = computed(() => !!resetToken.value)

const pwdHint = computed(() => {
  const v = newPwd.value
  if (!v) return ''
  if (v.length < 8) return t('validation.pwd_too_short')
  if (v.length > 32) return t('errors.pwd_too_long')
  if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return t('errors.pwd_format')
  return ''
})

onMounted(() => {
  const token = route.query.token
  if (typeof token === 'string' && token.length > 10) {
    resetToken.value = token
  }
})

function validateRequestForm() {
  const e = { account: '', newPwd: '', confirmPwd: '' }
  const accErr = validateAccount(account.value)
  if (accErr) e.account = t(accErr)
  errors.value = e
  return !e.account
}

function validateResetForm() {
  const e = { account: '', newPwd: '', confirmPwd: '' }
  const pwdErr = validatePassword(newPwd.value)
  if (pwdErr) e.newPwd = t(pwdErr)
  const cErr = validateConfirmPassword(confirmPwd.value, newPwd.value)
  if (cErr) e.confirmPwd = t(cErr)
  errors.value = e
  return !e.newPwd && !e.confirmPwd
}

async function onSubmitRequest() {
  globalError.value = ''
  if (!validateRequestForm()) return
  submitting.value = true
  try {
    await requestPasswordReset({ account: account.value.trim() })
    emailSent.value = true
  } catch (e) {
    globalError.value = e.message || 'Request failed'
  } finally {
    submitting.value = false
  }
}

async function onSubmitReset() {
  globalError.value = ''
  if (!validateResetForm()) return
  submitting.value = true
  try {
    await resetPassword({ token: resetToken.value, newPassword: newPwd.value })
    success.value = true
  } catch (e) {
    globalError.value = e.message || 'Reset failed'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-page { min-height: 100vh; background: #fff; }
.auth-shell { display: flex; justify-content: center; align-items: flex-start; padding: 32px 16px; }
.auth-card { width: 100%; max-width: 440px; border: 0; box-shadow: none; background: #fff; }
.auth-title { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0 0 6px; }
.auth-sub { font-size: 14px; color: #6b7280; margin: 0 0 24px; }
.auth-form { display: flex; flex-direction: column; gap: 16px; }
.auth-submit { width: 100%; margin-top: 8px; }
.auth-foot { margin-top: 20px; text-align: center; }
.auth-foot__link { font-size: 14px; color: var(--color-primary, #3b6ef5); text-decoration: none; }
.form-error { font-size: 13px; color: #ef4444; margin: 0; text-align: center; }
.success-panel { text-align: center; padding: 24px 0; }
.success-panel__icon { font-size: 48px; margin: 0 0 16px; }
.success-panel__title { font-size: 20px; font-weight: 700; color: #1a1a2e; margin: 0 0 8px; }
.success-panel__desc { font-size: 14px; color: #6b7280; margin: 0 0 24px; }
</style>
