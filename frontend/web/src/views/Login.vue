<template>
  <div class="auth-page">
    <AppHeader scope="login" />
    <main class="auth-shell">
      <AppCard class="auth-card">
        <h1 class="auth-title">{{ t('login.title') }}</h1>
        <p class="auth-sub">{{ t('login.subtitle') }}</p>

        <!-- W29: 从下单页被登录墙推过来时,显示提示让用户知道为什么需要登录 -->
        <div v-if="route.query.hint === 'login_needed'" class="auth-hint-banner" data-testid="login-hint-banner">
          <svg class="auth-hint-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.6"/>
            <path d="M12 8v4M12 16h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <span>{{ t('login.hint_needed') || '登录后即可完成订单提交,你填的资料已自动保存' }}</span>
        </div>

        <!-- 密码登录:账户(邮箱/用户名) + 密码 -->
        <form class="auth-form" @submit.prevent="onPwdSubmit">
          <AppInput
            v-model="account"
            :label="t('login.account_label')"
            :placeholder="t('login.account_placeholder')"
            required
            :error="errors.account"
            maxlength="120"
            input-id="login-account"
            data-testid="login-account"
            @blur="errors.account = validateAccount(account) ? t(validateAccount(account)) : ''"
          />

          <AppInput
            v-model="password"
            :label="t('login.pwd_label')"
            :placeholder="t('login.pwd_placeholder')"
            type="password"
            required
            :error="errors.password"
            maxlength="64"
            input-id="login-password"
            autocomplete="current-password"
            password-toggle
            data-testid="login-password"
            @blur="errors.password = validatePassword(password) ? t(validatePassword(password)) : ''"
          />

          <div class="auth-row">
            <label class="remember" for="login-remember">
              <input id="login-remember" v-model="remember" type="checkbox" />
              <span>{{ t('login.remember') }}</span>
            </label>
            <a href="#" @click.prevent="onForgot" :aria-label="t('login.forgot')">{{ t('login.forgot') }}</a>
          </div>

          <AppButton
            native-type="submit"
            variant="primary"
            size="lg"
            :loading="submitting"
            style="width: 100%;"
            data-testid="login-submit"
          >{{ t('login.submit') }}</AppButton>
        </form>

        <div class="auth-foot">
          <span>{{ t('login.no_account') }}</span>
          <a href="#" @click.prevent="goSignup" :aria-label="t('login.go_signup')">{{ t('login.go_signup') }}</a>
        </div>

        <template v-if="googleEnabled">
          <div class="auth-divider"><span>{{ t('common.or') || '或' }}</span></div>
          <div ref="googleBtnRef" class="google-btn-wrap"></div>
        </template>
      </AppCard>

      <footer class="auth-footer">{{ t('common.auth_footer') }}</footer>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { validateAccount, validatePassword } from '@/utils/validation'
import AppHeader from '@/components/AppHeader.vue'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

const account = ref('')
const password = ref('')
const remember = ref(true)

const submitting = ref(false)
const errors = reactive({ account: '', password: '' })

const googleEnabled = !!GOOGLE_CLIENT_ID
const googleBtnRef = ref(null)
const googleLoading = ref(false)

function validatePwd() {
  errors.account = validateAccount(account.value) ? t(validateAccount(account.value)) : ''
  errors.password = validatePassword(password.value) ? t(validatePassword(password.value)) : ''
  return !errors.account && !errors.password
}

async function onPwdSubmit() {
  if (!validatePwd()) return
  submitting.value = true
  try {
    await auth.loginByPassword({ account: account.value.trim(), password: password.value })
    toast.success(t('toast.login_success'))
    const redirect = route.query.redirect || '/destinations'
    router.push(redirect)
  } catch (e) {
    // 不暴露 axios 默认的 "Request failed with status code XXX",换成中文友好提示
    const status = e?.response?.status
    let msg = e?.message || t('toast.login_fail')
    if (status === 401) msg = t('login.error_invalid_credentials') || '账号或密码错误'
    else if (status === 429) msg = t('login.error_too_many') || '尝试次数过多,请稍后再试'
    else if (status >= 500) msg = t('login.error_server') || '服务暂时不可用,请稍后重试'
    else if (msg && /^Request failed with status code \d+/.test(msg)) msg = t('login.error_invalid_credentials') || '账号或密码错误'
    toast.error(msg)
  } finally {
    submitting.value = false
  }
}

function onForgot() {
  router.push('/forgot-password')
}

function goSignup() {
  router.push('/register')
}

async function handleGoogleCredential(response) {
  googleLoading.value = true
  try {
    await auth.loginWithGoogle(response.credential)
    toast.success(t('toast.login_success'))
    const redirect = route.query.redirect || '/destinations'
    router.push(redirect)
  } catch (e) {
    toast.error(e?.message || t('toast.login_fail'))
  } finally {
    googleLoading.value = false
  }
}

function initGoogleAuth() {
  if (!window.google) return
  window.google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
    auto_select: false,
  })
  if (googleBtnRef.value) {
    window.google.accounts.id.renderButton(googleBtnRef.value, {
      type: 'standard',
      shape: 'rectangular',
      theme: 'outline',
      text: 'signin_with',
      size: 'large',
      width: '340',
    })
  }
}

onMounted(() => {
  auth.hydrate()
  if (route.query.demo !== undefined) {
    account.value = 'demo138001380001@htex.app'
    password.value = 'Htex@2026'
  }
  if (googleEnabled) {
    if (window.google) {
      initGoogleAuth()
    } else {
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = initGoogleAuth
      document.head.appendChild(script)
    }
  }
})
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
  max-width: 420px;
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
/* W29: 登录墙提示 banner(从下单页跳过来时显示) */
.auth-hint-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 20px;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(59,110,245,.08), rgba(110,89,240,.06));
  border: 1px solid rgba(59,110,245,.2);
  border-radius: 10px;
  color: #1e3a8a;
  font-size: 13px;
  line-height: 1.4;
}
.auth-hint-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: #3B6EF5;
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.auth-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--ink-3);
  margin-top: -4px;
}
.remember {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--ink-2);
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
.auth-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0 16px;
  color: var(--ink-4, #bbb);
  font-size: 12px;
  &::before, &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border, #e5e7eb);
  }
}
.google-btn-wrap {
  display: flex;
  justify-content: center;
  min-height: 40px;
}
</style>
