import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, loginWithGoogle as apiLoginWithGoogle, refresh as apiRefresh } from '@/api/auth'
import { clearAllLocalVisaData } from '@/utils/localPrivacyStorage'

const STORAGE_KEY = 'visa.auth'

// 全局事件总线:token 失效 / 退出登录时派发,App.vue 监听后弹「会话过期」非阻塞提示条,
// 各页面通过 useAuthExpired() 拿到响应式状态,在 catch 里把 401 走"页面内错误块"分支而不弹 toast。
function emitAuthExpired() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('htex:auth-expired'))
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref('')
  const refreshToken = ref('')

  // 响应式:401 链路上被标记为"已确认失效",request interceptor 据此不发旧 token;
  // 页面级错误态根据这个值决定渲染"会话过期"块,而不是 generic "加载失败"。
  const isAuthExpired = ref(false)
  // W37b 内部:避免并发 401 雪崩式 retry(给 request interceptor 用,响应式意义不大,但保留在这里方便排错)
  const __tokenRevoked = ref(false)

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

  // W56: 401 链路 — 由 http.js 在 refresh 失败 / refresh 不可用时调用,只清 token + 派发事件,
  // 不再弹 toast(顶部"会话过期"提示条统一由 App.vue 渲染,避免在每个 catch 里散落 toast 调用)。
  function markAuthExpired() {
    if (isAuthExpired.value) return
    isAuthExpired.value = true
    __tokenRevoked.value = true
    user.value = null
    accessToken.value = ''
    refreshToken.value = ''
    try { localStorage.removeItem(STORAGE_KEY) } catch {}
    emitAuthExpired()
  }

  // 用户主动登出(从 AppHeader / Profile) — 不标记 expired,只清数据 + 不派发 expired 事件
  function clear() {
    user.value = null
    accessToken.value = ''
    refreshToken.value = ''
    isAuthExpired.value = false
    __tokenRevoked.value = false
    try { localStorage.removeItem(STORAGE_KEY) } catch {}
  }

  async function loginByPassword({ account, password }) {
    const data = await apiLogin({ account, password })
    user.value = data.user
    accessToken.value = data.accessToken
    refreshToken.value = data.refreshToken
    isAuthExpired.value = false
    __tokenRevoked.value = false
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
    isAuthExpired.value = false
    __tokenRevoked.value = false
    persist()
    return data
  }

  function logout() {
    // A-07: clear local drafts / OCR / previews on logout
    try { clearAllLocalVisaData() } catch { /* ignore */ }
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
      isAuthExpired.value = false
      __tokenRevoked.value = false
      persist()
      return true
    } catch {
      // refresh 失败 → 标记 expired(不调 clear(),避免和"主动登出"语义混淆;
      // markAuthExpired 内部会清 localStorage 并派发事件)
      markAuthExpired()
      return false
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isLoggedIn,
    isAuthExpired,
    hydrate,
    loginByPassword,
    loginWithGoogle,
    register,
    refreshAccessToken,
    logout,
    markAuthExpired
  }
})
