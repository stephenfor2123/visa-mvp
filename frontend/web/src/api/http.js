import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

// Empty Vercel envs used to bake "" into the production bundle, which then
// fell through to the SPA `/api` path and caused checklist/analytics 405s.
const configuredBase = String(import.meta.env.VITE_API_BASE || '').trim()
const baseURL = configuredBase || (import.meta.env.PROD ? 'https://api.htexvisa.com/api' : '/api')

const http = axios.create({
  baseURL,
  timeout: 15000
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  auth.hydrate()
  // W37b: 过期 token 不要主动带上 — 401 链路上 refresh 失败会让用户
  // 在登录页也被踢,提示"登录已过期"很迷惑(我压根还没登录呢)。
  // 凡是 401 链路上被标记为"已确认失效"的 token,清掉别再发出去。
  if (auth.accessToken && !auth.__tokenRevoked) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// W37: access token 只有 2h 有效期，之前没有任何代码用 refresh_token 续期，
// 导致任何跑了 2h+ 的会话都会被强制踢出("登录已过期")。这里在真正判定
// "过期"之前先静默试一次 refresh，成功就重放原请求，用户无感；并发多个
// 请求同时 401 时只发一次 refresh 请求，其余排队等它的结果。
let refreshPromise = null

http.interceptors.response.use(
  (resp) => resp.data,
  async (err) => {
    const config = err?.config || {}
    const silent = !!config.__silent // 显式静默:不弹 toast
    const status = err.response?.status
    const code = err.response?.data?.code
    const msg = err.response?.data?.message || err.message || '网络异常'

    // W56: 401 链路 — 不再弹 toast。统一交给 auth store 标记 expired + App.vue 顶部
    // 「会话过期」提示条;catch 分支根据 err.code === '1005' / err.isAuthExpired 渲染页面内错误块。
    if (status === 401 && !config.__isRefreshCall) {
      const auth = useAuthStore()
      // 第一次 401(没 retried 过):尝试 refresh,成功就 retry 原请求,失败就 mark expired
      if (!config._retried && auth.refreshToken) {
        auth.__tokenRevoked = true
        if (!refreshPromise) {
          refreshPromise = auth.refreshAccessToken().finally(() => { refreshPromise = null })
        }
        const refreshed = await refreshPromise
        if (refreshed) {
          auth.__tokenRevoked = false
          config._retried = true
          return http(config)
        }
        // refresh 失败 → auth 已 expired,标在 err 上让 catch 知道,不再弹 toast
      }
      // 没 refreshToken / refresh 失败 / 已经 retried 还 401 → 统一 mark expired
      auth.markAuthExpired()
      const marked = Object.assign(err, { code: code || '1005', isAuthExpired: true })
      return Promise.reject(marked)
    }

    // 429 / 业务码 1009 (后端限流):非 401 仍走 toast,但保留 silent 行为
    if (status === 429) {
      if (!silent) {
        useToast().warning('操作太频繁,请稍后再试')
      }
      return Promise.reject(Object.assign(err, { code }))
    }

    // 业务码 1005 也可能在某些 401 之外(罕见,如 envelope 错)出现 — 走"会话过期"路径
    if (code === '1005' && !silent) {
      const auth = useAuthStore()
      auth.markAuthExpired()
      return Promise.reject(Object.assign(err, { code, isAuthExpired: true }))
    }

    // 其他错误(网络/业务码):保留原 toast 行为(silent 仍然尊重)
    if (!silent) {
      if (/^Request failed with status code \d+/.test(msg) || msg === 'Network Error') {
        useToast().error('网络异常,请稍后再试')
      } else {
        useToast().error(msg)
      }
    }
    return Promise.reject(Object.assign(err, { code }))
  }
)

export default http
