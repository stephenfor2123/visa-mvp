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
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const config = err?.config || {}
    const silent = !!config.__silent // 显式静默:不弹 toast
    const toast = useToast()
    const status = err.response?.status
    const code = err.response?.data?.code
    const msg = err.response?.data?.message || err.message || '网络异常'
    if (!silent) {
      if (status === 401) {
        const auth = useAuthStore()
        auth.logout()
        toast.error('登录已过期,请重新登录')
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
