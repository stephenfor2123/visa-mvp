import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const baseURL = import.meta.env.VITE_API_BASE || '/api'

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

    if (status === 401 && !config.__isRefreshCall && !config._retried) {
      const auth = useAuthStore()
      // W37b: refresh 之前先标"该 token 失效",这样并行/排队的请求
      // 不会再拿同一个烂 token 去打后端,避免雪崩式 401 toast。
      auth.__tokenRevoked = true
      if (auth.refreshToken) {
        if (!refreshPromise) {
          refreshPromise = auth.refreshAccessToken().finally(() => { refreshPromise = null })
        }
        const refreshed = await refreshPromise
        if (refreshed) {
          auth.__tokenRevoked = false
          config._retried = true
          return http(config)
        }
      }
    }

    const toast = useToast()
    if (!silent) {
      if (status === 401) {
        const auth = useAuthStore()
        auth.logout()
        // W37b: 已经在登录页就别再弹"登录已过期"了,提示毫无意义还挡住界面。
        if (!window.location.pathname.startsWith('/login')) {
          toast.error('登录已过期,请重新登录')
        }
      } else if (status === 429) {
        // 后端限流(V2 §9.4: 100次/分钟 全局, 60次/分钟 慢速接口)
        toast.warning('操作太频繁,请稍后再试')
      } else {
        toast.error(msg)
      }
    }
    return Promise.reject(Object.assign(err, { code }))
  }
)

export default http
