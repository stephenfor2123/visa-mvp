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
            @blur="errors.account = validateAccount(account) || ''"
          />

          <AppInput
            v-model="password"
            :label="t('login.pwd_label')"
            :placeholder="t('login.pwd_placeholder')"
            type="password"
            required
            :error="errors.password"
            :hint="pwdStrengthHint"
            maxlength="64"
            input-id="login-password"
            data-testid="login-password"
            @blur="errors.password = validatePassword(password) || ''"
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
      </AppCard>

      <footer class="auth-footer">{{ t('common.auth_footer') }}</footer>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { validateAccount, validatePassword } from '@/utils/validation'
import AppHeader from '@/components/AppHeader.vue'

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

const pwdStrengthHint = computed(() => {
  const v = password.value
  if (!v) return ''
  if (v.length < 6) return t('errors.pwd_too_short')
  if (v.length >= 12 && /[A-Z]/.test(v) && /\d/.test(v) && /[^A-Za-z0-9]/.test(v)) {
    return t('validation.pwd_strength_strong')
  }
  if (v.length >= 8 && /\d/.test(v)) return t('validation.pwd_strength_mid')
  return t('validation.pwd_strength_weak')
})

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
    toast.error(e?.message || t('toast.login_fail'))
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

onMounted(() => {
  auth.hydrate()
  // Test mode: pre-fill demo account for screenshots
  // 用真实 seed 出的账号(参见 backend/scripts/seed_demo_data.py + TEST-ACCOUNTS.md)
  if (route.query.demo !== undefined) {
    account.value = 'demo138001380001@htex.app'
    password.value = '123456'
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
</style>
