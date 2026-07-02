import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, loginWithGoogle as apiLoginWithGoogle, refresh as apiRefresh } from '@/api/auth'

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

  async function loginByPassword({ account, password }) {
    const data = await apiLogin({ account, password })
    user.value = data.user
    accessToken.value = data.accessToken
    refreshToken.value = data.refreshToken
    persist()
    return data
  }

  async function register({ username, email, password, nickname, languagePref }) {
    const data = await apiRegister({
      username,
      email,
      password,
      nickname,
      languagePref
    })
    // 注册成功后跳 /login,不在此处自动登录。
    return data
  }

  async function loginWithGoogle(credential) {
    const data = await apiLoginWithGoogle(credential)
    user.value = data.user
    accessToken.value = data.accessToken
    refreshToken.value = data.refreshToken
    persist()
    return data
  }

  function logout() {
    clear()
  }

  // W37: access token 只有 2h 有效期，之前从没人调用过 refresh_token 去续期——
  // 一过 2h 用户就会被强制踢回登录页。http.js 的 401 拦截器在 logout 之前先
  // 试一次这个，成功就静默续上，用户完全无感。
  async function refreshAccessToken() {
    hydrate()
    if (!refreshToken.value) return false
    try {
      const data = await apiRefresh(refreshToken.value)
      if (data.user) user.value = data.user
      accessToken.value = data.accessToken
      refreshToken.value = data.refreshToken
      persist()
      return true
    } catch {
      clear()
      return false
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isLoggedIn,
    hydrate,
    loginByPassword,
    loginWithGoogle,
    register,
    refreshAccessToken,
    logout
  }
})
