// /api/v2/admin/* — Admin panel frontend API (W14-11 + W14-6).
//
// Wraps the admin-side endpoints exposed by backend/app/api/v2/admin.py:
//   POST   /api/v2/admin/login           — username + password → access_token
//   GET    /api/v2/admin/profile         — current admin profile (mock fallback when backend lacks endpoint)
//   GET    /api/v2/admin/config/rpa      — read RPA rate-limit config (W14-6)
//   PUT    /api/v2/admin/config/rpa      — update RPA rate-limit config (W14-6)
//   GET    /api/v2/admin/stats/rpa       — realtime RPA pipeline stats (W14-6)
//
// NOTE on auth: this module uses a dedicated axios instance `adminHttp`
// (instead of the shared `http`) so the C-user Bearer token in localStorage
// never bleeds into admin requests. Admin guard checks `admin_token` separately.
//
// Mock mode (VITE_MOCK !== 'false'): returns a synthesized admin token + profile
// so the front-end flow can be demoed before the backend is wired up.

import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE || '/api'
const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false'
const ADMIN_TOKEN_KEY = 'admin_token'
const ADMIN_PROFILE_KEY = 'admin_profile'

function delay(ms = 250) {
  return new Promise((r) => setTimeout(r, ms))
}

// Dedicated axios instance — independent interceptor chain so we don't
// auto-attach the C-user JWT or call the C-user /auth/refresh on 401.
const adminHttp = axios.create({
  baseURL,
  timeout: 15000
})

adminHttp.interceptors.request.use((config) => {
  try {
    const raw = localStorage.getItem(ADMIN_TOKEN_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.accessToken) {
        config.headers.Authorization = `Bearer ${parsed.accessToken}`
      }
    }
  } catch {}
  return config
})

adminHttp.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const status = err.response?.status
    const code = err.response?.data?.code
    const msg = err.response?.data?.message || err.message || '网络异常'
    return Promise.reject(Object.assign(err, { code, status, message: msg }))
  }
)

// Mock helpers ------------------------------------------------------------
function mockToken(username) {
  return {
    accessToken: 'mock.admin.' + username + '.' + Date.now(),
    tokenType: 'Bearer',
    expiresIn: 3600,
    role: 'admin',
    issuedAt: new Date().toISOString()
  }
}

function mockProfile(username) {
  return {
    admin_id: 1,
    username,
    role: 'admin',
    display_name: username === 'admin' ? '超级管理员' : username,
    email: username + '@visa.local',
    last_login: new Date().toISOString()
  }
}

// Error normalization — map backend envelope + axios errors to a stable shape:
//   { code: 'INVALID_CREDENTIALS' | 'ACCOUNT_LOCKED' | 'NETWORK', message: '...' }
function normalizeError(err) {
  const status = err?.status || err?.response?.status
  const backendCode = err?.code || err?.response?.data?.code
  const backendMsg = err?.response?.data?.message || err?.message || ''
  const lower = String(backendMsg).toLowerCase()
  if (!status && !err?.response) {
    return Object.assign(new Error('NETWORK'), { code: 'NETWORK' })
  }
  if (status === 401 || backendCode === 'INVALID_CREDENTIALS' || lower.includes('invalid') || lower.includes('凭证')) {
    return Object.assign(new Error(backendMsg || '账号或密码错误'), { code: 'INVALID_CREDENTIALS' })
  }
  if (status === 423 || backendCode === 'ACCOUNT_LOCKED' || lower.includes('lock')) {
    return Object.assign(new Error(backendMsg || '账号已被锁定'), { code: 'ACCOUNT_LOCKED' })
  }
  return Object.assign(new Error(backendMsg || '登录失败'), { code: backendCode || 'UNKNOWN' })
}

// Public API --------------------------------------------------------------

/**
 * POST /api/v2/admin/login
 * @param {{ username: string, password: string }} credentials
 * @returns {Promise<{ accessToken, tokenType, expiresIn, role }>}
 */
export async function adminLogin({ username, password }) {
  if (!username || !password) {
    throw Object.assign(new Error('请输入账号和密码'), { code: 'REQUIRED' })
  }

  if (MOCK_MODE) {
    await delay()
    // Mock contract: admin / admin123 succeeds; wrong password triggers INVALID_CREDENTIALS;
    // lockedadmin / any → ACCOUNT_LOCKED.
    if (username === 'lockedadmin') {
      throw Object.assign(new Error('账号已被锁定'), { code: 'ACCOUNT_LOCKED' })
    }
    if (username !== 'admin' || password !== 'admin123') {
      throw Object.assign(new Error('账号或密码错误'), { code: 'INVALID_CREDENTIALS' })
    }
    const token = mockToken(username)
    const profile = mockProfile(username)
    persistToken(token)
    persistProfile(profile)
    return token
  }

  try {
    const envelope = await adminHttp.post('/v2/admin/login', { username, password })
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'Login failed'), { code: envelope.code })
    }
    const data = envelope?.data || {}
    const token = {
      accessToken: data.access_token,
      tokenType: data.token_type || 'Bearer',
      expiresIn: data.expires_in,
      role: 'admin',
      issuedAt: new Date().toISOString()
    }
    persistToken(token)
    // Backend currently doesn't return profile in login response.
    // Build a minimal profile from username so AdminDashboard has something to show.
    persistProfile({ admin_id: 0, username, role: 'admin', display_name: username })
    return token
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/profile
 * @returns {Promise<AdminProfile>}
 */
export async function getAdminProfile() {
  if (MOCK_MODE) {
    await delay(120)
    const profile = readProfile()
    if (!profile) {
      // fabricate from token username if available
      const tok = readToken()
      const username = tok?.username || 'admin'
      return mockProfile(username)
    }
    return profile
  }

  try {
    const envelope = await adminHttp.get('/v2/admin/profile')
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'fetch profile failed'), { code: envelope.code })
    }
    const data = envelope?.data || {}
    const profile = {
      admin_id: data.admin_id ?? data.id,
      username: data.username,
      role: data.role || 'admin',
      display_name: data.display_name || data.username,
      email: data.email,
      last_login: data.last_login
    }
    persistProfile(profile)
    return profile
  } catch (err) {
    // 404 is expected if backend hasn't implemented profile yet — degrade gracefully
    if (err?.status === 404) {
      const cached = readProfile()
      if (cached) return cached
      return mockProfile(readToken()?.username || 'admin')
    }
    throw normalizeError(err)
  }
}

/**
 * Clear admin session — token + profile + role.
 * Does not navigate; caller decides where to redirect.
 */
export function adminLogout() {
  try { localStorage.removeItem(ADMIN_TOKEN_KEY) } catch {}
  try { localStorage.removeItem(ADMIN_PROFILE_KEY) } catch {}
}

export function readToken() {
  try {
    const raw = localStorage.getItem(ADMIN_TOKEN_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function readProfile() {
  try {
    const raw = localStorage.getItem(ADMIN_PROFILE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persistToken(token) {
  try {
    localStorage.setItem(ADMIN_TOKEN_KEY, JSON.stringify({
      accessToken: token.accessToken,
      tokenType: token.tokenType,
      expiresIn: token.expiresIn,
      role: token.role,
      issuedAt: token.issuedAt
    }))
  } catch {}
}

function persistProfile(profile) {
  try {
    localStorage.setItem(ADMIN_PROFILE_KEY, JSON.stringify(profile))
  } catch {}
}

export const ADMIN_STORAGE_KEYS = {
  TOKEN: ADMIN_TOKEN_KEY,
  PROFILE: ADMIN_PROFILE_KEY
}

// --------------------------------------------------------------------------- //
// RPA rate-limit config + realtime stats (W14-6)
// --------------------------------------------------------------------------- //

/**
 * Default rate-limit values — used as a mock fallback when the backend has
 * no rpa_config.yaml yet, so the UI still renders sensible defaults.
 */
export const RPA_DEFAULT_CONFIG = Object.freeze({
  ip_per_day: 50,
  account_interval_minutes: 30,
  off_peak_start: '00:00',
  off_peak_end: '06:00',
  rate_key: 'ip'
})

/**
 * GET /api/v2/admin/config/rpa — read the current rate-limit config.
 * @returns {Promise<{ rate_limits: { ip_per_day, account_interval_minutes,
 *   off_peak_start, off_peak_end, max_concurrent_tasks }, timeouts, retry,
 *   captcha, session, countries, mock_mode }>}
 */
export async function getRpaConfig() {
  if (MOCK_MODE) {
    await delay(120)
    return {
      rate_limits: {
        ip_per_day: 50,
        account_interval_minutes: 30,
        off_peak_start: '00:00',
        off_peak_end: '06:00',
        max_concurrent_tasks: 2
      },
      timeouts: { http_timeout: 30, captcha_timeout: 20, submit_timeout: 60, page_load_timeout: 45 },
      retry: { captcha_max_retries: 3, page_max_retries: 2, backoff_multiplier: 2, initial_backoff: 1 },
      captcha: { engine: 'pytesseract', preprocess: true, min_confidence: 0.6, api_url: '', api_key: '' },
      session: { ttl_minutes: 120, user_agent: 'Mozilla/5.0' },
      countries: {},
      mock_mode: true
    }
  }

  try {
    const envelope = await adminHttp.get('/v2/admin/config/rpa')
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'fetch rpa config failed'), { code: envelope.code })
    }
    return envelope?.data || {}
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * PUT /api/v2/admin/config/rpa — persist rate-limit updates.
 * Only sends the `rate_limits` slice — the rest of the YAML is left untouched.
 * @param {{ ip_per_day?: number, account_interval_minutes?: number,
 *   off_peak_start?: string, off_peak_end?: string, max_concurrent_tasks?: number }} rateLimits
 * @returns {Promise<FullRpaConfig>}
 */
export async function updateRpaConfig(rateLimits) {
  if (!rateLimits || typeof rateLimits !== 'object') {
    throw Object.assign(new Error('rateLimits must be an object'), { code: 'REQUIRED' })
  }

  if (MOCK_MODE) {
    await delay(180)
    return {
      rate_limits: {
        ip_per_day: rateLimits.ip_per_day ?? 50,
        account_interval_minutes: rateLimits.account_interval_minutes ?? 30,
        off_peak_start: rateLimits.off_peak_start ?? '00:00',
        off_peak_end: rateLimits.off_peak_end ?? '06:00',
        max_concurrent_tasks: rateLimits.max_concurrent_tasks ?? 2
      },
      mock_mode: true
    }
  }

  try {
    const envelope = await adminHttp.put('/v2/admin/config/rpa', {
      rate_limits: rateLimits
    })
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'update rpa config failed'), { code: envelope.code })
    }
    return envelope?.data || {}
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/stats/rpa — realtime pipeline stats.
 * @returns {Promise<{ today_visits, queued_tasks, failure_rate_24h,
 *   success_count_24h, failed_count_24h, total_count_24h, active_accounts,
 *   sample_window_seconds, generated_at }>}
 */
export async function getRpaStats() {
  if (MOCK_MODE) {
    await delay(100)
    // Synthesize a stable but plausible snapshot for demos.
    const total = 47
    const failed = 6
    return {
      today_visits: 128,
      queued_tasks: 3,
      failure_rate_24h: Number((failed / total).toFixed(4)),
      success_count_24h: total - failed,
      failed_count_24h: failed,
      total_count_24h: total,
      active_accounts: 5,
      sample_window_seconds: 86400,
      generated_at: new Date().toISOString()
    }
  }

  try {
    const envelope = await adminHttp.get('/v2/admin/stats/rpa')
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'fetch rpa stats failed'), { code: envelope.code })
    }
    return envelope?.data || {}
  } catch (err) {
    throw normalizeError(err)
  }
}

export default {
  adminLogin,
  adminLogout,
  getAdminProfile,
  readToken,
  readProfile,
  ADMIN_STORAGE_KEYS,
  getRpaConfig,
  updateRpaConfig,
  getRpaStats,
  RPA_DEFAULT_CONFIG
}