<template>
  <div class="auth-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
      </div>
    </header>

    <main class="auth-shell">
      <AppCard class="auth-card">
        <h1 class="auth-title">{{ t('login.title') }}</h1>
        <p class="auth-sub">{{ t('login.subtitle') }}</p>

<div class="auth-tabs" role="tablist" aria-label="Login method">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="auth-tab"
            :class="{ on: activeTab === tab.key }"
            role="tab"
            :id="`auth-tab-${tab.key}`"
            :aria-selected="activeTab === tab.key"
            :aria-controls="activeTab === tab.key ? `auth-panel-${tab.key}` : undefined"
            :tabindex="activeTab === tab.key ? 0 : -1"
            @click="activeTab = tab.key"
            @keydown="onTabKeydown"
          >{{ t(tab.label) }}</button>
        </div>

        <!-- Password login -->
        <form v-if="activeTab === 'pwd'" class="auth-form" :id="`auth-panel-pwd`" role="tabpanel" :aria-labelledby="`auth-tab-pwd`" @submit.prevent="onPwdSubmit">
          <AppInput
            v-model="phone"
            :label="t('login.phone_label')"
            :placeholder="t('login.phone_placeholder')"
            required
            :error="errors.phone"
            inputmode="numeric"
            maxlength="20"
            input-id="login-phone"
            data-testid="login-phone"
          >
            <template #prefix>
              <label for="login-country" class="sr-only">{{ t('login.country_label') || 'Country code' }}</label>
              <select id="login-country" v-model="phoneCountry" class="phone-country" data-testid="login-country" aria-label="Country code">
                <option v-for="c in countries" :key="c.code" :value="c.code">
                  {{ c.flag }} {{ c.code }}
                </option>
              </select>
            </template>
          </AppInput>

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

        <!-- SMS login -->
        <form v-else class="auth-form" :id="`auth-panel-sms`" role="tabpanel" :aria-labelledby="`auth-tab-sms`" @submit.prevent="onSmsSubmit">
          <AppInput
            v-model="phone"
            :label="t('login.phone_label')"
            :placeholder="t('login.phone_placeholder')"
            required
            :error="errors.phone"
            inputmode="numeric"
            maxlength="20"
            input-id="login-phone-sms"
            data-testid="login-phone"
          >
            <template #prefix>
              <label for="login-country-sms" class="sr-only">{{ t('login.country_label') || 'Country code' }}</label>
              <select id="login-country-sms" v-model="phoneCountry" class="phone-country" data-testid="login-country" aria-label="Country code">
                <option v-for="c in countries" :key="c.code" :value="c.code">
                  {{ c.flag }} {{ c.code }}
                </option>
              </select>
            </template>
          </AppInput>

          <AppInput
            v-model="password"
            :label="t('login.pwd_label')"
            :placeholder="t('login.pwd_placeholder')"
            type="password"
            required
            :error="errors.password"
            :hint="pwdStrengthHint"
            maxlength="64"
            data-testid="login-password"
            @blur="errors.password = validatePassword(password) || ''"
          />

          <div class="auth-row">
            <label class="remember">
              <input v-model="remember" type="checkbox" />
              <span>{{ t('login.remember') }}</span>
            </label>
            <a href="#" @click.prevent="onForgot">{{ t('login.forgot') }}</a>
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

        <!-- SMS login -->
        <form v-if="activeTab === 'sms'" class="auth-form" @submit.prevent="onSmsSubmit">
          <AppInput
            v-model="phone"
            :label="t('login.phone_label')"
            :placeholder="t('login.phone_placeholder')"
            required
            :error="errors.phone"
            inputmode="numeric"
            maxlength="20"
            data-testid="login-phone"
            @blur="errors.phone = validatePhone(phone) || ''"
          >
            <template #prefix>
              <select v-model="phoneCountry" class="phone-country" data-testid="login-country">
                <option v-for="c in countries" :key="c.code" :value="c.code">
                  {{ c.flag }} {{ c.code }}
                </option>
              </select>
            </template>
          </AppInput>

<AppInput
            v-model="smsCode"
            :label="t('login.sms_label')"
            :placeholder="t('login.sms_placeholder')"
            inputmode="numeric"
            maxlength="6"
            required
            :error="errors.smsCode"
            input-id="login-sms"
            data-testid="login-sms"
          >
            <template #suffix>
              <AppButton
                variant="outline"
                size="sm"
                :disabled="smsCooldown > 0 || sending"
                :aria-label="smsCooldown > 0 ? `${smsCooldown}s ${t('login.send_code')}` : t('login.send_code')"
                @click="onSendCode"
                data-testid="login-send-code"
              >
                {{ smsCooldown > 0 ? `${smsCooldown}s` : (sending ? '...' : t('login.send_code')) }}
              </AppButton>
            </template>
          </AppInput>

          <p v-if="lastSentCode" class="mock-hint" role="status" aria-live="polite">
            {{ t('login.mock_code_hint', { code: lastSentCode }) }}
          </p>

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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { validatePhone, validateSmsCode, validatePassword } from '@/utils/validation'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

const tabs = [
  { key: 'pwd', label: 'login.tab_pwd' },
  { key: 'sms', label: 'login.tab_sms' }
]
const activeTab = ref('pwd')

const countries = [
  { code: '+86', flag: '🇨🇳' },
  { code: '+62', flag: '🇮🇩' },
  { code: '+84', flag: '🇻🇳' },
  { code: '+63', flag: '🇵🇭' }
]
const phoneCountry = ref('+86')
const phone = ref('')
const password = ref('')
const smsCode = ref('')
const remember = ref(true)

const submitting = ref(false)
const sending = ref(false)
const smsCooldown = ref(0)
let timer = null
const lastSentCode = ref('')

const errors = reactive({ phone: '', password: '', smsCode: '' })

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
  errors.phone = validatePhone(phone.value) ? t(validatePhone(phone.value)) : ''
  errors.password = validatePassword(password.value) ? t(validatePassword(password.value)) : ''
  return !errors.phone && !errors.password
}

function validateSms() {
  errors.phone = validatePhone(phone.value) ? t(validatePhone(phone.value)) : ''
  errors.smsCode = validateSmsCode(smsCode.value) ? t(validateSmsCode(smsCode.value)) : ''
  return !errors.phone && !errors.smsCode
}

async function onPwdSubmit() {
  if (!validatePwd()) return
  submitting.value = true
  try {
    await auth.loginByPassword({ phone: phone.value, phoneCountry: phoneCountry.value, password: password.value })
    toast.success(t('toast.login_success'))
    const redirect = route.query.redirect || '/destinations'
    router.push(redirect)
  } catch (e) {
    toast.error(e?.message || t('toast.login_fail'))
  } finally {
    submitting.value = false
  }
}

async function onSmsSubmit() {
  if (!validateSms()) return
  submitting.value = true
  try {
    await auth.loginBySms({ phone: phone.value, phoneCountry: phoneCountry.value, code: smsCode.value })
    toast.success(t('toast.login_success'))
    const redirect = route.query.redirect || '/destinations'
    router.push(redirect)
  } catch (e) {
    toast.error(e?.message || t('toast.login_fail'))
  } finally {
    submitting.value = false
  }
}

async function onSendCode() {
  const phoneErr = validatePhone(phone.value)
  if (phoneErr) {
    errors.phone = t(phoneErr)
    return
  }
  sending.value = true
  try {
    const res = await auth.sendSmsCode({ phone: phone.value, phoneCountry: phoneCountry.value })
    lastSentCode.value = res.code || ''
    toast.success(t('toast.code_send_success') + (res.mock ? ' (mock)' : ''))
    smsCooldown.value = 60
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

function onForgot() {
  router.push('/forgot-password')
}

function goSignup() {
  router.push('/register')
}

function onTabKeydown(e) {
  const keys = ['ArrowLeft', 'ArrowRight']
  if (!keys.includes(e.key)) return
  e.preventDefault()
  const idx = tabs.findIndex((t) => t.key === activeTab.value)
  const next = e.key === 'ArrowRight'
    ? Math.min(idx + 1, tabs.length - 1)
    : Math.max(idx - 1, 0)
  activeTab.value = tabs[next].key
  // Focus the new tab button
  nextTick(() => {
    document.getElementById(`auth-tab-${tabs[next].key}`)?.focus()
  })
}

onMounted(() => {
  auth.hydrate()
  // Test mode: pre-fill demo account for screenshots
  if (route.query.demo !== undefined) {
    phone.value = '13800138000'
    password.value = 'demo1234'
    activeTab.value = 'pwd'
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
// Screen-reader only utility
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
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
  max-width: 420px;
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
.auth-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg-alt);
  border-radius: 10px;
  padding: 4px;
  margin-bottom: 22px;
}
.auth-tab {
  flex: 1;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--ink-3);
  border-radius: 8px;
  cursor: pointer;
  transition: all .15s;
}
.auth-tab.on {
  background: #fff;
  color: var(--el-color-primary);
  box-shadow: 0 1px 3px rgba(15,23,42,.08);
  font-weight: 600;
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.phone-country {
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--ink-2);
  padding: 0 4px;
  cursor: pointer;
  min-width: 48px;
  max-width: 72px;
  width: auto;
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