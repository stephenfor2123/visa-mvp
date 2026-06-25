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
      <AppCard class="auth-card">
        <h1 class="auth-title">{{ t('register.title') }}</h1>
        <p class="auth-sub">{{ t('register.subtitle') }}</p>

        <form class="auth-form" @submit.prevent="onSubmit" novalidate>
          <AppInput
            v-model="phone"
            :label="t('register.phone_label')"
            :placeholder="t('register.phone_placeholder')"
            required
            :error="errors.phone"
            inputmode="numeric"
            maxlength="20"
            data-testid="reg-phone"
            @blur="errors.phone = validatePhone(phone) ? t(validatePhone(phone)) : ''"
          >
            <template #prefix>
              <select v-model="phoneCountry" class="phone-country" data-testid="reg-country">
                <option v-for="c in countries" :key="c.code" :value="c.code">
                  {{ c.flag }} {{ c.code }}
                </option>
              </select>
            </template>
          </AppInput>

          <AppInput
            v-model="smsCode"
            :label="t('register.sms_label')"
            :placeholder="t('register.sms_placeholder')"
            inputmode="numeric"
            maxlength="6"
            required
            :error="errors.smsCode"
            data-testid="reg-sms"
            @blur="errors.smsCode = validateSmsCode(smsCode) ? t(validateSmsCode(smsCode)) : ''"
          >
            <template #suffix>
              <AppButton
                variant="outline"
                size="sm"
                :disabled="smsCooldown > 0 || sending"
                @click="onSendCode"
                data-testid="reg-send-code"
              >
                {{ smsCooldown > 0 ? `${smsCooldown}s` : (sending ? '...' : t('register.send_code')) }}
              </AppButton>
            </template>
          </AppInput>

          <p v-if="lastSentCode" class="mock-hint">
            {{ t('login.mock_code_hint', { code: lastSentCode }) }}
          </p>

          <AppInput
            v-model="password"
            :label="t('register.pwd_label')"
            :placeholder="t('register.pwd_placeholder')"
            type="password"
            required
            :error="errors.password"
            :hint="pwdHint"
            maxlength="32"
            data-testid="reg-password"
          />

          <AppInput
            v-model="confirmPassword"
            :label="t('register.confirm_pwd_label')"
            :placeholder="t('register.confirm_pwd_placeholder')"
            type="password"
            required
            :error="errors.confirmPassword"
            maxlength="32"
            data-testid="reg-confirm-password"
          />

          <label class="agreement" :class="{ 'is-error': errors.agreement }">
            <input
              v-model="agreed"
              type="checkbox"
              data-testid="reg-agreement"
            />
            <span class="agreement__text">
              {{ t('register.agreement_prefix') }}
              <a href="#" @click.prevent="onOpenTerms">{{ t('register.agreement_terms') }}</a>
              {{ t('register.agreement_and') }}
              <a href="#" @click.prevent="onOpenPrivacy">{{ t('register.agreement_privacy') }}</a>
            </span>
          </label>
          <span v-if="errors.agreement" class="agreement__error">{{ errors.agreement }}</span>

          <AppButton
            native-type="submit"
            variant="primary"
            size="lg"
            :loading="submitting"
            style="width: 100%;"
            data-testid="reg-submit"
          >{{ submitting ? t('register.submitting') : t('register.submit') }}</AppButton>
        </form>

        <div class="auth-foot">
          <span>{{ t('register.have_account') }}</span>
          <a href="#" @click.prevent="goLogin">{{ t('register.go_login') }}</a>
        </div>
      </AppCard>

      <footer class="auth-footer">{{ t('common.auth_footer') }}</footer>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted } from 'vue'
import HtexLogo from '@/components/HtexLogo.vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  validatePhone,
  validateSmsCode,
  validatePassword,
  validateConfirmPassword
} from '@/utils/validation'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const countries = [
  { code: '+86', flag: '🇨🇳' },
  { code: '+62', flag: '🇮🇩' },
  { code: '+84', flag: '🇻🇳' },
  { code: '+63', flag: '🇵🇭' }
]
const phoneCountry = ref('+86')
const phone = ref('')
const smsCode = ref('')
const password = ref('')
const confirmPassword = ref('')
const agreed = ref(false)
const lastSentCode = ref('')

const submitting = ref(false)
const sending = ref(false)
const smsCooldown = ref(0)
let timer = null

const errors = reactive({
  phone: '',
  smsCode: '',
  password: '',
  confirmPassword: '',
  agreement: ''
})

// Same rules as backend pydantic validator: 8-32 chars, must contain letter + digit.
const pwdHint = computed(() => {
  const v = password.value
  if (!v) return ''
  if (v.length < 8) return t('errors.pwd_too_short')
  if (v.length > 32) return t('errors.pwd_too_long')
  if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return t('errors.pwd_format')
  return ''
})

function validate() {
  errors.phone = validatePhone(phone.value) ? t(validatePhone(phone.value)) : ''
  errors.smsCode = validateSmsCode(smsCode.value) ? t(validateSmsCode(smsCode.value)) : ''
  errors.password = validatePassword(password.value) ? t(validatePassword(password.value)) : ''
  errors.confirmPassword = validateConfirmPassword(confirmPassword.value, password.value)
    ? t(validateConfirmPassword(confirmPassword.value, password.value))
    : ''
  errors.agreement = !agreed.value ? t('errors.agreement_required') : ''
  return !errors.phone && !errors.smsCode && !errors.password && !errors.confirmPassword && !errors.agreement
}

async function onSendCode() {
  if (!phone.value || phone.value.length < 5) {
    errors.phone = t('errors.phone_invalid')
    return
  }
  sending.value = true
  try {
    const res = await auth.sendSmsCode({
      phone: phone.value,
      phoneCountry: phoneCountry.value,
      purpose: 'register'
    })
    lastSentCode.value = res.code || ''
    toast.success(t('toast.code_send_success') + (res.mock ? ' (mock)' : ''))
    smsCooldown.value = 60
    if (timer) clearInterval(timer)
    timer = setInterval(() => {
      smsCooldown.value -= 1
      if (smsCooldown.value <= 0) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    toast.error(e?.message || t('errors.network_error'))
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  if (!validate()) return
  submitting.value = true
  try {
    await auth.register({
      phone: phone.value,
      phoneCountry: phoneCountry.value,
      password: password.value,
      smsCode: smsCode.value
    })
    toast.success(t('toast.register_success'))
    router.push('/login')
  } catch (e) {
    const msg = e?.response?.data?.message || e?.message || t('toast.register_fail')
    toast.error(msg)
    // If duplicate phone, highlight the phone field
    if (/already|2003/i.test(msg)) {
      errors.phone = t('errors.user_exists')
    }
  } finally {
    submitting.value = false
  }
}

function onOpenTerms() {
  toast.info(t('common.w2_coming_soon', { feature: t('register.agreement_terms') }))
}
function onOpenPrivacy() {
  toast.info(t('common.w2_coming_soon', { feature: t('register.agreement_privacy') }))
}
function goLogin() {
  router.push('/login')
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.auth-page {
  min-height: 100vh;
  background: var(--bg-alt);
  display: flex;
  flex-direction: column;
}
.auth-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}
.auth-card {
  width: 100%;
  max-width: 440px;
}
.auth-title {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: var(--ink-1);
}
.auth-sub {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--ink-3);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.phone-country {
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--ink-2);
  padding: 0 4px;
  cursor: pointer;
}
.mock-hint {
  margin: -6px 0 0;
  padding: 10px 12px;
  background: #FFFBEB;
  border: 1px solid #FCD34D;
  border-radius: 8px;
  font-size: 12px;
  color: #92400E;
  b { color: #78350F; font-family: var(--font-family-mono, monospace); }
}
.agreement {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.5;
  cursor: pointer;
  user-select: none;
}
.agreement input[type="checkbox"] {
  margin-top: 3px;
  cursor: pointer;
  flex-shrink: 0;
}
.agreement__text { flex: 1; }
.agreement a {
  color: var(--el-color-primary, #3B6EF5);
  text-decoration: none;
  margin: 0 2px;
}
.agreement a:hover { text-decoration: underline; }
.agreement.is-error .agreement__text { color: var(--el-color-danger, #DC2626); }
.agreement__error {
  margin-top: -8px;
  font-size: 12px;
  color: var(--el-color-danger, #DC2626);
}
.auth-foot {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}
.auth-foot a { margin-left: 4px; font-weight: 500; }
.auth-footer {
  margin-top: 32px;
  font-size: 12px;
  color: var(--muted);
}
</style>