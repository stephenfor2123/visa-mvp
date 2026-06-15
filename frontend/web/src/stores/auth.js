import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, sendSmsCode as apiSendCode, smsLogin as apiSmsLogin, register as apiRegister } from '@/api/auth'

const STORAGE_KEY = 'visa.auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref('')
  const refreshToken = ref('')

  const isLoggedIn = computed(() => !!accessToken.value && !!user.value)

  function hydrate() {
    if (user.value) return
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      user.value = parsed.user || null
      accessToken.value = parsed.accessToken || ''
      refreshToken.value = parsed.refreshToken || ''
    } catch {
      // ignore
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        user: user.value,
        accessToken: accessToken.value,
        refreshToken: refreshToken.value
      }))
    } catch {}
  }

  function clear() {
    user.value = null
    accessToken.value = ''
    refreshToken.value = ''
    try { localStorage.removeItem(STORAGE_KEY) } catch {}
  }

  async function loginByPassword({ phone, phoneCountry, password }) {
    const data = await apiLogin({ phone, phoneCountry, password })
    user.value = data.user
    accessToken.value = data.accessToken
    refreshToken.value = data.refreshToken
    persist()
    return data
  }

  async function loginBySms({ phone, phoneCountry, code }) {
    const data = await apiSmsLogin({ phone, phoneCountry, code })
    user.value = data.user
    accessToken.value = data.accessToken
    refreshToken.value = data.refreshToken
    persist()
    return data
  }

  async function sendSmsCode({ phone, phoneCountry, purpose }) {
    return apiSendCode({ phone, phoneCountry, purpose })
  }

  async function register({ phone, phoneCountry, password, smsCode, nickname, languagePref }) {
    const data = await apiRegister({
      phone,
      phoneCountry,
      password,
      smsCode,
      nickname,
      languagePref
    })
    // Spec: 注册成功后跳 /login,不在此处自动登录。
    // 不持久化 token,避免 router guard 把 /login 当作"已登录"再重定向回 /home。
    // 真正登录由用户去 /login 页用密码完成。
    return data
  }

  function logout() {
    clear()
  }

  return {
    user,
    accessToken,
    refreshToken,
    isLoggedIn,
    hydrate,
    loginByPassword,
    loginBySms,
    sendSmsCode,
    register,
    logout
  }
})