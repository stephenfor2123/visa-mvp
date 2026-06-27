import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister } from '@/api/auth'

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
        refreshToken: user.value
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
    register,
    logout
  }
})
