<template>
  <div class="auth-page">
    <AppHeader scope="register" />
    <main class="auth-shell">
      <AppCard class="auth-card">
        <h1 class="auth-title">{{ t('register.title') }}</h1>
        <p class="auth-sub">{{ t('register.subtitle') }}</p>

        <form class="auth-form" @submit.prevent="onSubmit" novalidate>
          <AppInput
            v-model="username"
            :label="t('register.username_label')"
            :placeholder="t('register.username_placeholder')"
            required
            :error="errors.username"
            maxlength="32"
            data-testid="reg-username"
            @blur="errors.username = validateUsername(username) ? t(validateUsername(username)) : ''"
          />

          <AppInput
            v-model="email"
            :label="t('register.email_label')"
            :placeholder="t('register.email_placeholder')"
            type="email"
            required
            :error="errors.email"
            maxlength="120"
            data-testid="reg-email"
            @blur="errors.email = validateEmail(email) ? t(validateEmail(email)) : ''"
          />

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
            @blur="errors.password = validatePassword(password) ? t(validatePassword(password)) : ''"
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
            @blur="errors.confirmPassword = validateConfirmPassword(confirmPassword, password) ? t(validateConfirmPassword(confirmPassword, password)) : ''"
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
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  validateUsername,
  validateEmail,
  validatePassword,
  validateConfirmPassword
} from '@/utils/validation'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const agreed = ref(false)

const submitting = ref(false)
const errors = reactive({
  username: '',
  email: '',
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
  errors.username = validateUsername(username.value) ? t(validateUsername(username.value)) : ''
  errors.email = validateEmail(email.value) ? t(validateEmail(email.value)) : ''
  errors.password = validatePassword(password.value) ? t(validatePassword(password.value)) : ''
  errors.confirmPassword = validateConfirmPassword(confirmPassword.value, password.value)
    ? t(validateConfirmPassword(confirmPassword.value, password.value))
    : ''
  errors.agreement = !agreed.value ? t('errors.agreement_required') : ''
  return !errors.username && !errors.email && !errors.password && !errors.confirmPassword && !errors.agreement
}

async function onSubmit() {
  if (!validate()) return
  submitting.value = true
  try {
    await auth.register({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value
    })
    toast.success(t('toast.register_success'))
    router.push('/login')
  } catch (e) {
    const msg = e?.response?.data?.message || e?.message || t('toast.register_fail')
    toast.error(msg)
    // If duplicate email, highlight the email field
    if (/already|duplicate|exists/i.test(msg)) {
      errors.email = t('errors.user_exists')
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

onUnmounted(() => {})
</script>

<style scoped lang="scss">
.auth-page {
  min-height: 100vh;
  background: #fff;
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
  border: 0;
  box-shadow: none;
  background: #fff;
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
