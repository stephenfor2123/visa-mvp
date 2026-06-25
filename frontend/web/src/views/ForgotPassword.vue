<!-- ForgotPassword.vue — W12 Story: 忘记密码页 -->
<template>
  <div class="auth-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <HtexLogo :size="28" />
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
      </div>
    </header>

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

      <!-- Form -->
      <AppCard v-else class="auth-card">
        <h1 class="auth-title">{{ t('forgot.page_title') }}</h1>
        <p class="auth-sub">{{ t('forgot.page_subtitle') }}</p>

        <form class="auth-form" @submit.prevent="onSubmit" novalidate>
          <!-- Phone -->
          <AppInput
            v-model="phone"
            :label="t('forgot.phone_label')"
            :placeholder="t('forgot.phone_placeholder')"
            inputmode="numeric"
            maxlength="20"
            required
            :error="errors.phone"
            data-testid="forgot-phone"
          >
            <template #prefix>
              <select v-model="phoneCountry" class="phone-country" data-testid="forgot-country">
                <option v-for="c in countries" :key="c.code" :value="c.code">
                  {{ c.flag }} {{ c.code }}
                </option>
              </select>
            </template>
          </AppInput>

          <!-- SMS Code -->
          <AppInput
            v-model="smsCode"
            :label="t('forgot.sms_label')"
            :placeholder="t('forgot.sms_placeholder')"
            inputmode="numeric"
            maxlength="6"
            required
            :error="errors.smsCode"
            data-testid="forgot-sms"
          >
            <template #suffix>
              <AppButton
                variant="outline"
                size="sm"
                :disabled="sending || smsCooldown > 0"
                @click.prevent="onSendCode"
                data-testid="forgot-send-code"
              >
                {{ smsCooldown > 0 ? `${smsCooldown}s` : t('forgot.send_code') }}
              </AppButton>
            </template>
          </AppInput>

          <!-- New Password -->
          <AppInput
            v-model="newPwd"
            type="password"
            :label="t('forgot.new_pwd_label')"
            :placeholder="t('forgot.new_pwd_placeholder')"
            required
            :error="errors.newPwd"
            data-testid="forgot-new-pwd"
          />

          <!-- Confirm Password -->
          <AppInput
            v-model="confirmPwd"
            type="password"
            :label="t('forgot.confirm_pwd_label')"
            :placeholder="t('forgot.confirm_pwd_placeholder')"
            required
            :error="errors.confirmPwd"
            data-testid="forgot-confirm-pwd"
          />

          <!-- Global error -->
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

        <div class="auth-footer">
          <router-link to="/login" class="auth-footer__link">
            ← {{ t('forgot.back_login') }}
          </router-link>
        </div>
      </AppCard>
    </main>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import HtexLogo from '@/components/HtexLogo.vue'
import { useI18n } from 'vue-i18n'
import { sendSmsCode, resetPassword } from '@/api/auth'
import LangSwitch from '@/components/LangSwitch.vue'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'

const { t } = useI18n()

const countries = [
  { code: '+86', flag: '🇨🇳' },
  { code: '+62', flag: '🇮🇩' },
  { code: '+84', flag: '🇻🇳' },
  { code: '+63', flag: '🇵🇭' }
]

const phone = ref('')
const phoneCountry = ref('+86')
const smsCode = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const errors = ref({ phone: '', smsCode: '', newPwd: '', confirmPwd: '' })
const globalError = ref('')
const sending = ref(false)
const submitting = ref(false)
const smsCooldown = ref(0)
const success = ref(false)
let cooldownTimer = null

function validateForm() {
  const e = { phone: '', smsCode: '', newPwd: '', confirmPwd: '' }
  if (!phone.value || phone.value.length < 5) e.phone = t('errors.phone_invalid')
  if (!/^\d{6}$/.test(smsCode.value)) e.smsCode = t('errors.code_invalid')
  if (!newPwd.value || newPwd.value.length < 8) e.newPwd = t('errors.pwd_too_short')
  if (!/[A-Za-z]/.test(newPwd.value) || !/\d/.test(newPwd.value)) e.newPwd = t('errors.pwd_format')
  if (newPwd.value !== confirmPwd.value) e.confirmPwd = t('errors.pwd_mismatch')
  errors.value = e
  return !e.phone && !e.smsCode && !e.newPwd && !e.confirmPwd
}

async function onSendCode() {
  if (!phone.value || phone.value.length < 5) {
    errors.value.phone = t('errors.phone_invalid')
    return
  }
  sending.value = true
  globalError.value = ''
  try {
    await sendSmsCode({ phone: phone.value, phoneCountry: phoneCountry.value, purpose: 'reset' })
    smsCooldown.value = 60
    startCooldown()
  } catch (e) {
    globalError.value = e.message || 'Failed to send code'
  } finally {
    sending.value = false
  }
}

function startCooldown() {
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    smsCooldown.value = Math.max(0, smsCooldown.value - 1)
    if (smsCooldown.value === 0) clearInterval(cooldownTimer)
  }, 1000)
}

async function onSubmit() {
  globalError.value = ''
  if (!validateForm()) return
  submitting.value = true
  try {
    await resetPassword({
      phone: phone.value,
      phoneCountry: phoneCountry.value,
      smsCode: smsCode.value,
      newPassword: newPwd.value
    })
    success.value = true
  } catch (e) {
    globalError.value = e.message || 'Reset failed'
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})
</script>

<style scoped>
.auth-page { min-height: 100vh; background: var(--bg-page, #f5f7fa); }
.auth-shell { display: flex; justify-content: center; align-items: flex-start; padding: 32px 16px; }
.auth-card { width: 100%; max-width: 440px; }
.auth-title { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0 0 6px; }
.auth-sub { font-size: 14px; color: #6b7280; margin: 0 0 24px; }
.auth-form { display: flex; flex-direction: column; gap: 16px; }
.auth-submit { width: 100%; margin-top: 8px; }
.auth-footer { margin-top: 20px; text-align: center; }
.auth-footer__link { font-size: 14px; color: var(--color-primary, #3b6ef5); text-decoration: none; }
.form-error { font-size: 13px; color: #ef4444; margin: 0; text-align: center; }
.success-panel { text-align: center; padding: 24px 0; }
.success-panel__icon { font-size: 48px; margin: 0 0 16px; }
.success-panel__title { font-size: 20px; font-weight: 700; color: #1a1a2e; margin: 0 0 8px; }
.success-panel__desc { font-size: 14px; color: #6b7280; margin: 0 0 24px; }
.phone-country { border: none; background: transparent; font-size: 14px; color: #6b7280; cursor: pointer; padding-right: 4px; }
</style>