<!--
  AdminLogin.vue — W14-11
  Admin-side sign-in page. Visually distinct from C-side Login.vue
  (simpler, more formal: centered card, no marketing copy, no SMS tab).

  On success: store admin_token in localStorage and route to ?redirect or /admin/dashboard.
-->
<template>
  <div class="admin-login-page">
    <header class="admin-login-topbar">
      <div class="admin-login-brand">
        <span class="admin-login-mark">A</span>
        <span class="admin-login-brand-text">{{ t('admin.dashboard') }}</span>
      </div>
      <LangSwitch />
    </header>

    <main class="admin-login-shell">
      <AppCard class="admin-login-card" data-testid="admin-login-card">
        <div class="admin-login-header">
          <h1 class="admin-login-title">{{ t('admin.login.title') }}</h1>
          <p class="admin-login-sub">{{ t('admin.login.subtitle') }}</p>
        </div>

        <form class="admin-login-form" @submit.prevent="onSubmit" data-testid="admin-login-form">
          <AppInput
            v-model="username"
            :label="t('admin.login.username_label')"
            :placeholder="t('admin.login.username_placeholder')"
            :error="errors.username"
            required
            autocomplete="username"
            maxlength="64"
            data-testid="admin-login-username"
          />

          <AppInput
            v-model="password"
            :label="t('admin.login.password_label')"
            :placeholder="t('admin.login.password_placeholder')"
            type="password"
            :error="errors.password"
            required
            autocomplete="current-password"
            maxlength="128"
            data-testid="admin-login-password"
          />

          <div v-if="serverError" class="admin-login-server-error" role="alert" data-testid="admin-login-error">
            {{ serverError }}
          </div>

          <AppButton
            native-type="submit"
            variant="primary"
            size="lg"
            :loading="submitting"
            style="width: 100%;"
            data-testid="admin-login-submit"
          >{{ submitting ? t('admin.login.button_submitting') : t('admin.login.button') }}</AppButton>

          <div class="admin-login-row">
            <a href="#" @click.prevent="onForgot">{{ t('admin.login.forgot_password') }}</a>
          </div>

          <p
            v-if="showDemoHint"
            class="admin-login-mock-hint"
            data-testid="admin-login-mock-hint"
          >
            测试账号: admin / HtexAd@26
          </p>
        </form>
      </AppCard>

      <footer class="admin-login-footer">{{ t('admin.login.footer_tip') }}</footer>
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
import LangSwitch from '@/components/LangSwitch.vue'
import { useAdminStore } from '@/stores/admin'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const admin = useAdminStore()

const username = ref('')
const password = ref('')
const submitting = ref(false)
const serverError = ref('')
const errors = reactive({ username: '', password: '' })
const showDemoHint = computed(
  () => import.meta.env.DEV || route.query.demo !== undefined,
)

function clearErrors() {
  errors.username = ''
  errors.password = ''
  serverError.value = ''
}

function validate() {
  clearErrors()
  let ok = true
  if (!username.value || username.value.length < 2) {
    errors.username = t('admin.login.error_required')
    ok = false
  }
  if (!password.value || password.value.length < 1) {
    errors.password = t('admin.login.error_required')
    ok = false
  }
  return ok
}

function errorMessageFor(code, fallback) {
  if (code === 'ACCOUNT_LOCKED') return t('admin.login.error_locked')
  if (code === 'NETWORK') return t('admin.login.error_network')
  if (code === 'INVALID_CREDENTIALS') return t('admin.login.error_invalid')
  if (code === 'REQUIRED') return t('admin.login.error_required')
  return fallback || t('admin.login.error_invalid')
}

async function onSubmit() {
  if (!validate()) return
  submitting.value = true
  try {
    await admin.login({ username: username.value.trim(), password: password.value })
    const redirect = route.query.redirect && String(route.query.redirect).startsWith('/admin')
      ? String(route.query.redirect)
      : '/admin/dashboard'
    router.replace(redirect)
  } catch (err) {
    serverError.value = errorMessageFor(err?.code, err?.message)
  } finally {
    submitting.value = false
  }
}

function onForgot() {
  // W14-11 scope: not building reset flow yet — show toast-equivalent inline.
  serverError.value = ''
  // Visual cue only (no toast component imported to keep this page standalone).
  // Future story: link to /admin/forgot-password once backend exposes it.
  // eslint-disable-next-line no-alert
  alert(t('admin.login.forgot_password'))
}

onMounted(async () => {
  admin.hydrate()
  // 运营后台强制中文，不管浏览器语言
  const { setLocale } = await import('@/i18n')
  await setLocale('zh-CN', { markUser: false })
  // Test/demo mode: pre-fill mock credentials so screenshots show a populated form
  if (route.query.demo !== undefined) {
    username.value = 'admin'
    password.value = 'HtexAd@26'
  }
})
</script>

<style scoped lang="scss">
.admin-login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
  color: var(--ink-1, #0F172A);
  display: flex;
  flex-direction: column;
}

.admin-login-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 28px;
  color: #E2E8F0;
  border-bottom: 1px solid rgba(255, 255, 255, .06);
}

.admin-login-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 16px;
  letter-spacing: .5px;
}

.admin-login-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: #3B6EF5;
  color: #fff;
  border-radius: 6px;
  font-weight: 700;
  font-size: 14px;
}

.admin-login-brand-text { color: #F8FAFC; }

.admin-login-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
}

.admin-login-card {
  width: 100%;
  max-width: 420px;
  padding: 8px;
  background: #fff;
  box-shadow: 0 20px 50px rgba(0, 0, 0, .25);
}

.admin-login-header {
  padding: 24px 24px 8px;
  text-align: center;
  border-bottom: 1px solid var(--border, #E2E8F0);
}

.admin-login-title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink-1, #0F172A);
}

.admin-login-sub {
  margin: 0;
  font-size: 13px;
  color: var(--ink-3, #64748B);
}

.admin-login-form {
  padding: 20px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.admin-login-row {
  display: flex;
  justify-content: flex-end;
  font-size: 13px;
  margin-top: -4px;
}

.admin-login-row a {
  color: var(--el-color-primary, #3B6EF5);
  cursor: pointer;
  text-decoration: none;
}

.admin-login-row a:hover { text-decoration: underline; }

.admin-login-server-error {
  padding: 10px 12px;
  background: #FEF2F2;
  border: 1px solid #FCA5A5;
  border-radius: 8px;
  font-size: 13px;
  color: #B91C1C;
}

.admin-login-mock-hint {
  margin: 4px 0 0;
  padding: 8px 12px;
  background: #F1F5F9;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  text-align: center;
  font-family: var(--font-family-mono, monospace);
}

.admin-login-footer {
  margin-top: 32px;
  font-size: 12px;
  color: rgba(226, 232, 240, .65);
  text-align: center;
  max-width: 420px;
  line-height: 1.5;
}
</style>