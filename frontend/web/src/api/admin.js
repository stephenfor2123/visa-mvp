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
    // Mock contract: admin / Admin@2024 succeeds
    if (username === 'lockedadmin') {
      throw Object.assign(new Error('账号已被锁定'), { code: 'ACCOUNT_LOCKED' })
    }
    if (username !== 'admin' || password !== 'Admin@2024') {
      throw Object.assign(new Error('账号或密码错误'), { code: 'INVALID_CREDENTIALS' })
    }
    const token = mockToken(username)
    const profile = mockProfile(username)
    persistToken(token)
    persistProfile(profile)
    return { ...token, username, role_name: '超级管理员', permissions: ['dashboard','orders','payments','users','countries','settings'] }
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
      issuedAt: new Date().toISOString(),
      username: data.username || username,
      role_name: data.role_name || '',
      permissions: data.permissions || [],
    }
    persistToken(token)
    persistProfile({ admin_id: 0, username: data.username || username, role: 'admin', display_name: data.username || username })
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
      issuedAt: token.issuedAt,
      username: token.username,
      role_name: token.role_name,
      permissions: token.permissions || [],
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
// Order management (W34)                                                      //
// --------------------------------------------------------------------------- //

/**
 * GET /api/v2/admin/orders — paginated order list.
 * @param {{ page?: number, page_size?: number, status?: string|null,
 *   user_id?: number|null }} params
 * @returns {Promise<{ items, page, page_size, total, total_pages }>}
 */
export async function listAdminOrders(params = {}) {
  if (MOCK_MODE) {
    await delay(150)
    // Synthesize a small but realistic set covering the full state machine.
    const all = [
      { id: 1042, order_no: 'V2-20260629-000042', user_id: 17, destination_id: 1, visa_type: 'tourism',
        status: 'submitted', total_amount: 18500, currency: 'USD', aff_code: null,
        created_at: '2026-06-29T08:14:00Z', updated_at: '2026-06-29T08:15:00Z' },
      { id: 1041, order_no: 'V2-20260629-000041', user_id: 12, destination_id: 1, visa_type: 'tourism',
        status: 'reviewing', total_amount: 18500, currency: 'USD', aff_code: 'SUMMER10',
        created_at: '2026-06-29T07:42:00Z', updated_at: '2026-06-29T08:55:00Z' },
      { id: 1040, order_no: 'V2-20260628-000128', user_id: 8, destination_id: 2, visa_type: 'student',
        status: 'approved', total_amount: 14500, currency: 'USD', aff_code: null,
        created_at: '2026-06-28T22:10:00Z', updated_at: '2026-06-29T03:20:00Z' },
      { id: 1039, order_no: 'V2-20260628-000127', user_id: 22, destination_id: 1, visa_type: 'tourism',
        status: 'rejected', total_amount: 18500, currency: 'USD', aff_code: null,
        created_at: '2026-06-28T20:01:00Z', updated_at: '2026-06-29T02:00:00Z' },
      { id: 1038, order_no: 'V2-20260628-000126', user_id: 5, destination_id: 1, visa_type: 'tourism',
        status: 'closed', total_amount: 18500, currency: 'USD', aff_code: null,
        created_at: '2026-06-28T18:33:00Z', updated_at: '2026-06-28T19:00:00Z' },
      { id: 1037, order_no: 'V2-20260628-000125', user_id: 9, destination_id: 1, visa_type: 'tourism',
        status: 'created', total_amount: 18500, currency: 'USD', aff_code: null,
        created_at: '2026-06-28T15:21:00Z', updated_at: '2026-06-28T15:21:00Z' },
      { id: 1036, order_no: 'V2-20260627-000089', user_id: 14, destination_id: 3, visa_type: 'tourism',
        status: 'submitted', total_amount: 12500, currency: 'USD', aff_code: null,
        created_at: '2026-06-27T11:45:00Z', updated_at: '2026-06-27T12:30:00Z' },
    ]
    const filtered = params.status ? all.filter(o => o.status === params.status) : all
    return {
      items: filtered,
      page: 1,
      page_size: 20,
      total: filtered.length,
      total_pages: 1,
    }
  }

  try {
    const qp = new URLSearchParams()
    if (params.page) qp.set('page', params.page)
    if (params.page_size) qp.set('page_size', params.page_size)
    if (params.status) qp.set('status', params.status)
    if (params.user_id) qp.set('user_id', params.user_id)
    const qs = qp.toString() ? `?${qp.toString()}` : ''
    const envelope = await adminHttp.get(`/v2/admin/orders${qs}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list orders failed'), { code: envelope.code })
    }
    return envelope?.data || { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/orders/{order_id} — full detail incl. status history.
 * @param {number} orderId
 * @returns {Promise<{ id, order_no, status, status_history, allowed_next_statuses, ... }>}
 */
export async function getAdminOrder(orderId) {
  if (MOCK_MODE) {
    await delay(120)
    return {
      id: orderId,
      uuid: `mock-uuid-${orderId}`,
      order_no: `V2-20260629-${String(orderId).padStart(6, '0')}`,
      user_id: 17,
      destination_id: 1,
      visa_type: 'tourism',
      status: 'reviewing',
      total_amount: 18500,
      currency: 'USD',
      rpa_task_id: '00000000-0000-4000-8000-000000000042',
      aff_code: 'SUMMER10',
      created_at: '2026-06-29T08:14:00Z',
      updated_at: '2026-06-29T08:55:00Z',
      submitted_at: '2026-06-29T08:15:00Z',
      reviewed_at: null,
      closed_at: null,
      applicant_data: JSON.stringify({
        surname: 'ZHANG', given_name: 'Wei',
        sex: 'M', dob: '1992-04-12', nationality: 'CHN',
        passport_no: 'E12345678', passport_expiry: '2030-08-15',
        arrival_date: '2026-08-10', departure_date: '2026-08-20', stay_days: 10,
        emergency_contact: { name: 'ZHANG Mei', phone: '+86 138 0000 0000', relation: 'spouse' },
      }, null, 2),
      material_ids: JSON.stringify([101, 102, 103]),
      destination_url: 'https://example.gov/visa/apply',
      status_history: [
        { from_status: null,       to_status: 'created',   source: 'user', note: 'order created',          created_at: '2026-06-29T08:14:00Z' },
        { from_status: 'created',   to_status: 'submitted', source: 'user', note: 'order submitted to RPA', created_at: '2026-06-29T08:15:00Z' },
        { from_status: 'submitted', to_status: 'reviewing', source: 'rpa',  note: 'rpa picked up',          created_at: '2026-06-29T08:30:00Z' },
      ],
      allowed_next_statuses: ['approved', 'rejected', 'closed', 'abnormal', 'failed'],
      payment: {
        trade_no: 'mock_trade_20260629000042',
        status: 'paid',
        paid_at: '2026-06-29T08:16:00Z',
        amount_cents: 18500,
        currency: 'USD',
        code_url: null,
        expired_at: null,
      },
      audit_logs: [
        { id: 1, actor_type: 'user', actor_id: 17, action: 'order.create', payload: null, created_at: '2026-06-29T08:14:00Z' },
        { id: 2, actor_type: 'user', actor_id: 17, action: 'payment.create', payload: '{"trade_no":"mock_trade_20260629000042"}', created_at: '2026-06-29T08:15:00Z' },
        { id: 3, actor_type: 'system', actor_id: 0, action: 'payment.notify', payload: '{"status":"paid"}', created_at: '2026-06-29T08:16:00Z' },
        { id: 4, actor_type: 'rpa', actor_id: 0, action: 'rpa.start', payload: '{"task_id":"00000000-0000-4000-8000-000000000042"}', created_at: '2026-06-29T08:30:00Z' },
        { id: 5, actor_type: 'admin', actor_id: 0, action: 'admin.login', payload: null, created_at: '2026-06-29T09:00:00Z' },
      ],
    }
  }

  try {
    const envelope = await adminHttp.get(`/v2/admin/orders/${orderId}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'get order failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * PUT /api/v2/admin/orders/{order_id}/status — override status.
 * Server validates against VALID_TRANSITIONS and returns 4012 on illegal.
 * @param {number} orderId
 * @param {{ status: string, note?: string }} body
 * @returns {Promise<{ id, order_no, status, from_status, to_status }>}
 */
export async function updateAdminOrderStatus(orderId, body) {
  if (!body || !body.status) {
    throw Object.assign(new Error('status is required'), { code: 'REQUIRED' })
  }
  if (MOCK_MODE) {
    await delay(180)
    return { id: orderId, order_no: `V2-MOCK-${orderId}`, status: body.status, note: body.note || '' }
  }
  try {
    const envelope = await adminHttp.put(`/v2/admin/orders/${orderId}/status`, body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'update status failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/stats/dashboard — aggregated metrics.
 * @returns {Promise<{ today_new_orders, week_new_orders, pending_orders,
 *   completed_orders, payment_success_rate, generated_at, cached }>}
 */
export async function getDashboardStats() {
  if (MOCK_MODE) {
    await delay(120)
    return {
      today_new_orders: 7,
      week_new_orders: 42,
      pending_orders: 11,
      completed_orders: 158,
      payment_success_rate: 0.872,
      generated_at: new Date().toISOString(),
      cached: false,
    }
  }
  try {
    const envelope = await adminHttp.get('/v2/admin/stats/dashboard')
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'fetch stats failed'), { code: envelope.code })
    }
    return envelope?.data || {}
  } catch (err) {
    throw normalizeError(err)
  }
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
/**
 * GET /api/v2/admin/payments — paginated payment flow list (资金流).
 * @param {{ page?: number, page_size?: number, status?: string|null }} params
 * @returns {Promise<{ items, page, page_size, total, total_pages }>}
 */
export async function listPayments(params = {}) {
  if (MOCK_MODE) {
    await delay(150)
    const all = [
      { order_id: 1042, order_no: 'V2-20260629-000042', user_id: 17,
        trade_no: 'MOCK_A1B2C3D4E5F6', status: 'paid',
        amount_cents: 18500, currency: 'USD',
        paid_at: '2026-06-29T08:16:00Z', created_at: '2026-06-29T08:14:00Z', updated_at: '2026-06-29T08:16:00Z' },
      { order_id: 1041, order_no: 'V2-20260629-000041', user_id: 12,
        trade_no: 'MOCK_F7E8D9C0B1A2', status: 'paid',
        amount_cents: 18500, currency: 'USD',
        paid_at: '2026-06-29T08:02:00Z', created_at: '2026-06-29T07:42:00Z', updated_at: '2026-06-29T08:02:00Z' },
      { order_id: 1040, order_no: 'V2-20260628-000128', user_id: 8,
        trade_no: 'MOCK_1A2B3C4D5E6F', status: 'paid',
        amount_cents: 14500, currency: 'USD',
        paid_at: '2026-06-28T22:30:00Z', created_at: '2026-06-28T22:10:00Z', updated_at: '2026-06-28T22:30:00Z' },
      { order_id: 1039, order_no: 'V2-20260628-000127', user_id: 22,
        trade_no: null, status: 'failed',
        amount_cents: 18500, currency: 'USD',
        paid_at: null, created_at: '2026-06-28T20:01:00Z', updated_at: '2026-06-28T20:02:00Z' },
      { order_id: 1037, order_no: 'V2-20260628-000125', user_id: 9,
        trade_no: 'MOCK_9F8E7D6C5B4A', status: 'pending',
        amount_cents: 18500, currency: 'USD',
        paid_at: null, created_at: '2026-06-28T15:21:00Z', updated_at: '2026-06-28T15:21:00Z' },
      { order_id: 1036, order_no: 'V2-20260627-000089', user_id: 14,
        trade_no: 'MOCK_ABCDEF123456', status: 'closed',
        amount_cents: 12500, currency: 'USD',
        paid_at: '2026-06-27T12:00:00Z', created_at: '2026-06-27T11:45:00Z', updated_at: '2026-06-27T13:00:00Z' },
    ]
    const filtered = params.status ? all.filter(p => p.status === params.status) : all
    return { items: filtered, page: 1, page_size: 20, total: filtered.length, total_pages: 1 }
  }
  try {
    const qp = new URLSearchParams()
    if (params.page) qp.set('page', params.page)
    if (params.page_size) qp.set('page_size', params.page_size)
    if (params.status) qp.set('status', params.status)
    const qs = qp.toString() ? `?${qp.toString()}` : ''
    const envelope = await adminHttp.get(`/v2/admin/payments${qs}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list payments failed'), { code: envelope.code })
    }
    return envelope?.data || { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
  } catch (err) {
    throw normalizeError(err)
  }
}

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

// --------------------------------------------------------------------------- //
// Role & Admin User management (W34)                                           //
// --------------------------------------------------------------------------- //

/**
 * GET /api/v2/admin/roles — list all roles.
 * @returns {Promise<Array<{ id, name, code, permissions, description, is_active }>>}
 */
export async function listRoles() {
  if (MOCK_MODE) {
    await delay(120)
    return [
      { id: 1, name: '超级管理员', code: 'super_admin', permissions: ['dashboard','orders','payments','users','countries','settings'], description: '拥有全部权限', is_active: true },
      { id: 2, name: '员工', code: 'staff', permissions: ['dashboard','orders','payments'], description: '日常运营人员', is_active: true },
    ]
  }
  try {
    const envelope = await adminHttp.get('/v2/admin/roles')
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list roles failed'), { code: envelope.code })
    }
    return envelope?.data || []
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * POST /api/v2/admin/roles — create a new role.
 * @param {{ name: string, code: string, description?: string, permissions: string[] }} body
 */
export async function createRole(body) {
  if (!body?.name || !body?.code) {
    throw Object.assign(new Error('name and code are required'), { code: 'REQUIRED' })
  }
  try {
    const envelope = await adminHttp.post('/v2/admin/roles', body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'create role failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * PUT /api/v2/admin/roles/{id} — update a role.
 * @param {number} id
 * @param {{ description?: string, permissions: string[], is_active?: boolean }} body
 */
export async function updateRole(id, body) {
  try {
    const envelope = await adminHttp.put(`/v2/admin/roles/${id}`, body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'update role failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * DELETE /api/v2/admin/roles/{id} — soft-delete (deactivate) a role.
 * @param {number} id
 */
export async function deleteRole(id) {
  try {
    const envelope = await adminHttp.delete(`/v2/admin/roles/${id}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'delete role failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/admin-users — paginated admin user list.
 * @param {{ page?: number, page_size?: number }} params
 */
export async function listAdminUsers(params = {}) {
  if (MOCK_MODE) {
    await delay(120)
    return {
      items: [
        { id: 1, username: 'admin', role_id: 1, role_name: '超级管理员', is_active: true, created_at: '2026-06-01T00:00:00Z', last_login: '2026-06-29T08:00:00Z' },
        { id: 2, username: 'operator1', role_id: 2, role_name: '员工', is_active: true, created_at: '2026-06-15T00:00:00Z', last_login: '2026-06-28T10:00:00Z' },
      ],
      page: 1, page_size: 20, total: 2, total_pages: 1,
    }
  }
  try {
    const qp = new URLSearchParams()
    if (params.page) qp.set('page', params.page)
    if (params.page_size) qp.set('page_size', params.page_size)
    const qs = qp.toString() ? `?${qp.toString()}` : ''
    const envelope = await adminHttp.get(`/v2/admin/admin-users${qs}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list admin users failed'), { code: envelope.code })
    }
    return envelope?.data || { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * POST /api/v2/admin/admin-users — create admin user.
 * @param {{ username: string, password: string, role_id: number }} body
 */
export async function createAdminUser(body) {
  if (!body?.username || !body?.password || !body?.role_id) {
    throw Object.assign(new Error('username, password and role_id are required'), { code: 'REQUIRED' })
  }
  try {
    const envelope = await adminHttp.post('/v2/admin/admin-users', body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'create admin user failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * PUT /api/v2/admin/admin-users/{id} — update admin user.
 * @param {number} id
 * @param {{ password?: string, role_id?: number, is_active?: boolean }} body
 */
export async function updateAdminUser(id, body) {
  try {
    const envelope = await adminHttp.put(`/v2/admin/admin-users/${id}`, body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'update admin user failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * DELETE /api/v2/admin/admin-users/{id} — soft-delete (deactivate) admin user.
 * @param {number} id
 */
export async function deleteAdminUser(id) {
  try {
    const envelope = await adminHttp.delete(`/v2/admin/admin-users/${id}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'delete admin user failed'), { code: envelope.code })
    }
    return envelope?.data
  } catch (err) {
    throw normalizeError(err)
  }
}

// --------------------------------------------------------------------------- //
// C-端用户管理 (W36)                                                           //
// --------------------------------------------------------------------------- //

/**
 * GET /api/v2/admin/users — paginated C-side user list (masked).
 * @param {{ page?: number, page_size?: number, status?: string|null }} params
 */
export async function listCUsers(params = {}) {
  if (MOCK_MODE) {
    await delay(150)
    const all = [
      { id: 17, uuid: 'u-0017', email: 'zhang***@gmail.com', username: 'zhang_wei',
        phone: '****5678', phone_country: '+86', nickname: '小张',
        avatar_url: null, language_pref: 'zh-CN', status: 'active',
        mfa_enabled: false, last_login_at: '2026-06-29T08:14:00Z', last_login_ip: '203.0.113.5',
        created_at: '2026-04-15T10:00:00Z', updated_at: '2026-06-29T08:14:00Z' },
      { id: 12, uuid: 'u-0012', email: 'li***@163.com', username: 'li_na',
        phone: '****1234', phone_country: '+86', nickname: '李娜',
        avatar_url: null, language_pref: 'zh-CN', status: 'active',
        mfa_enabled: true, last_login_at: '2026-06-29T07:30:00Z', last_login_ip: '203.0.113.8',
        created_at: '2026-03-20T09:00:00Z', updated_at: '2026-06-29T07:30:00Z' },
      { id: 8, uuid: 'u-0008', email: 'wanger****@outlook.com', username: 'wang_er',
        phone: '****9012', phone_country: '+86', nickname: '王二',
        avatar_url: null, language_pref: 'en', status: 'active',
        mfa_enabled: false, last_login_at: '2026-06-28T22:00:00Z', last_login_ip: '198.51.100.3',
        created_at: '2026-02-01T12:00:00Z', updated_at: '2026-06-29T03:20:00Z' },
      { id: 22, uuid: 'u-0022', email: 'ma***@qq.com', username: null,
        phone: '****3456', phone_country: '+86', nickname: '马同学',
        avatar_url: null, language_pref: 'zh-CN', status: 'disabled',
        mfa_enabled: false, last_login_at: '2026-06-26T11:00:00Z', last_login_ip: '203.0.113.99',
        created_at: '2026-05-10T12:00:00Z', updated_at: '2026-06-28T20:02:00Z' },
      { id: 9, uuid: 'u-0009', email: 'che***@yahoo.com', username: 'chen_jj',
        phone: '****7890', phone_country: '+86', nickname: null,
        avatar_url: null, language_pref: 'id-ID', status: 'active',
        mfa_enabled: false, last_login_at: '2026-06-28T15:00:00Z', last_login_ip: '198.51.100.10',
        created_at: '2026-01-15T08:00:00Z', updated_at: '2026-06-28T15:21:00Z' },
      { id: 14, uuid: 'u-0014', email: 'liu***@gmail.com', username: 'liu_x',
        phone: '****2345', phone_country: '+86', nickname: 'Liu',
        avatar_url: null, language_pref: 'vi-VN', status: 'pending_destroy',
        mfa_enabled: false, last_login_at: '2026-06-25T09:00:00Z', last_login_ip: '203.0.113.20',
        created_at: '2026-04-01T10:00:00Z', updated_at: '2026-06-27T18:00:00Z' },
    ]
    const filtered = params.status ? all.filter(u => u.status === params.status) : all
    return {
      items: filtered,
      page: 1,
      page_size: params.page_size || 20,
      total: filtered.length,
      total_pages: 1,
    }
  }
  try {
    const qp = new URLSearchParams()
    if (params.page) qp.set('page', params.page)
    if (params.page_size) qp.set('page_size', params.page_size)
    if (params.status) qp.set('status', params.status)
    const qs = qp.toString() ? `?${qp.toString()}` : ''
    const envelope = await adminHttp.get(`/v2/admin/users${qs}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list users failed'), { code: envelope.code })
    }
    return envelope?.data || { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/users/{id} — C-side user detail (with order/material counts).
 * @param {number} userId
 */
export async function getCUser(userId) {
  if (MOCK_MODE) {
    await delay(120)
    return {
      id: userId, uuid: `u-${userId}`,
      email: 'zhang***@gmail.com', username: 'zhang_wei',
      phone: '****5678', phone_country: '+86', nickname: '小张',
      avatar_url: null, language_pref: 'zh-CN', status: 'active',
      mfa_enabled: false,
      last_login_at: '2026-06-29T08:14:00Z', last_login_ip: '203.0.113.5',
      created_at: '2026-04-15T10:00:00Z', updated_at: '2026-06-29T08:14:00Z',
      order_count: 2, material_count: 5,
    }
  }
  try {
    const envelope = await adminHttp.get(`/v2/admin/users/${userId}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'get user failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * GET /api/v2/admin/users/{id}/orders — paginated order list for a single C-user.
 * @param {number} userId
 * @param {{ page?: number, page_size?: number }} [params]
 */
export async function listUserOrders(userId, params = {}) {
  if (MOCK_MODE) {
    await delay(150)
    const all = [
      { id: 1042, order_no: 'V2-20260629-000042', visa_type: 'tourism',
        status: 'submitted', total_amount: 18500, currency: 'USD',
        destination_id: 1, created_at: '2026-06-29T08:14:00Z', updated_at: '2026-06-29T08:15:00Z' },
      { id: 1015, order_no: 'V2-20260601-000020', visa_type: 'business',
        status: 'closed', total_amount: 22000, currency: 'USD',
        destination_id: 1, created_at: '2026-06-01T09:00:00Z', updated_at: '2026-06-10T14:00:00Z' },
    ]
    return {
      items: all, page: 1, page_size: params.page_size || 20,
      total: all.length, total_pages: 1,
    }
  }
  try {
    const qp = new URLSearchParams()
    if (params.page) qp.set('page', params.page)
    if (params.page_size) qp.set('page_size', params.page_size)
    const qs = qp.toString() ? `?${qp.toString()}` : ''
    const envelope = await adminHttp.get(`/v2/admin/users/${userId}/orders${qs}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'list user orders failed'), { code: envelope.code })
    }
    return envelope?.data || { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * DELETE /api/v2/admin/users/{id} — soft-delete (set status=pending_destroy).
 * Distinct from /disable which sets status=disabled.
 * @param {number} userId
 */
export async function deleteCUser(userId) {
  if (MOCK_MODE) {
    await delay(150)
    return { message: 'User soft-deleted' }
  }
  try {
    const envelope = await adminHttp.delete(`/v2/admin/users/${userId}`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'delete user failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * POST /api/v2/admin/users/{id}/disable — disable C-side account.
 * Idempotent: returns the current user record if already disabled.
 * @param {number} userId
 */
export async function disableUser(userId) {
  if (MOCK_MODE) {
    await delay(140)
    return { user_id: userId, status: 'disabled', message: '账号已禁用' }
  }
  try {
    const envelope = await adminHttp.post(`/v2/admin/users/${userId}/disable`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'disable user failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * POST /api/v2/admin/users/{id}/restore — restore a disabled account to active.
 * Server-side rejects if current status !== 'disabled'.
 * @param {number} userId
 */
export async function restoreUser(userId) {
  if (MOCK_MODE) {
    await delay(140)
    return { user_id: userId, status: 'active', message: '账号已恢复' }
  }
  try {
    const envelope = await adminHttp.post(`/v2/admin/users/${userId}/restore`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'restore user failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * PUT /api/v2/admin/users/{id} — update C-side profile (nickname / language_pref / avatar_url).
 * @param {number} userId
 * @param {{ nickname?: string|null, language_pref?: string|null,
 *   avatar_url?: string|null }} body
 */
export async function updateCUser(userId, body) {
  if (MOCK_MODE) {
    await delay(180)
    return { id: userId, nickname: body.nickname, language_pref: body.language_pref }
  }
  try {
    const envelope = await adminHttp.put(`/v2/admin/users/${userId}`, body)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'update user failed'), { code: envelope.code })
    }
    return envelope?.data || null
  } catch (err) {
    throw normalizeError(err)
  }
}

/**
 * POST /api/v2/admin/users/{id}/reset-password — generate a 12-char random pwd.
 * Server returns the plaintext ONCE; the UI must copy it.
 * @param {number} userId
 * @returns {Promise<{ user_id, username, new_password, reset_at }>}
 */
export async function resetUserPassword(userId) {
  if (MOCK_MODE) {
    await delay(180)
    return {
      user_id: userId,
      username: 'zhang_wei',
      new_password: 'Aa1!Aa1!Aa1!',
      reset_at: new Date().toISOString(),
    }
  }
  try {
    const envelope = await adminHttp.post(`/v2/admin/users/${userId}/reset-password`)
    if (envelope?.code && envelope.code !== '1000') {
      throw Object.assign(new Error(envelope.message || 'reset password failed'), { code: envelope.code })
    }
    return envelope?.data || null
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
  RPA_DEFAULT_CONFIG,
  listAdminOrders,
  getAdminOrder,
  updateAdminOrderStatus,
  getDashboardStats,
  listPayments,
  // W34
  listRoles,
  createRole,
  updateRole,
  deleteRole,
  listAdminUsers,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
  // W36 — C-side user management
  listCUsers,
  getCUser,
  listUserOrders,
  deleteCUser,
  disableUser,
  restoreUser,
  updateCUser,
  resetUserPassword,
}