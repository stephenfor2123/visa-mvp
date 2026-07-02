// utils/api.js
// 微信小程序 API wrapper,路径对齐 web 端 /api/v2/...
// 后端 envelope: { code, message, data }
// W6b 期间:VITE_MOCK 等价物 = wx.getStorageSync('mockMode') !== 'false',默认走真接口

const MOCK_MODE = wx.getStorageSync('mockMode') === 'true'  // 默认 false = 走真接口

function getApiBase() {
  const app = getApp()
  return (app && app.globalData && app.globalData.apiBase) || 'https://api.visa-helper.example.com'
}

function getToken() {
  const app = getApp()
  return (app && app.globalData && app.globalData.token) || ''
}

function mockDelay(ms = 250) {
  return new Promise((r) => setTimeout(r, ms))
}

// 解析 envelope:真接口返回 {code, message, data} → 解出 data
// 错误统一抛 { code, message } 让调用方处理
function unwrap(env) {
  if (!env || typeof env !== 'object') {
    throw new Error('Empty response')
  }
  if (env.code && env.code !== '1000') {
    const err = new Error(env.message || 'Request failed')
    err.code = env.code
    err.envelope = env
    throw err
  }
  return env.data || {}
}

function request({ url, method = 'GET', data, header }) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const finalHeader = Object.assign(
      { 'Content-Type': 'application/json' },
      token ? { 'Authorization': 'Bearer ' + token } : {},
      header || {}
    )
    wx.request({
      url: getApiBase() + url,
      method,
      data,
      header: finalHeader,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          // HTTP 层错误:返回 envelope 或裸错误
          const env = res.data || {}
          const err = new Error((env && env.message) || ('HTTP ' + res.statusCode))
          err.code = (env && env.code) || String(res.statusCode)
          err.envelope = env
          reject(err)
        }
      },
      fail: (e) => {
        const err = new Error((e && e.errMsg) || 'Network error')
        err.code = 'NETWORK_ERROR'
        reject(err)
      }
    })
  })
}

// ========== 业务接口(对齐 web 端 /src/api/auth.js + /src/api/destinations.js) ==========

// Mock 用户(仅 mock 模式用)
function mockUser(phone) {
  return {
    id: 'u_' + Math.random().toString(36).slice(2, 10),
    phone: phone,
    phoneCountry: '+86',
    nickname: '签证用户_' + (phone || '').slice(-4),
    languagePref: 'zh-CN',
    status: 'active',
    createdAt: new Date().toISOString()
  }
}

async function login({ phone, phoneCountry, password }) {
  if (MOCK_MODE) {
    await mockDelay()
    if (!phone || !password) throw new Error('请输入手机号和密码')
    if (password.length < 6) throw new Error('密码至少 6 位')
    return {
      user: mockUser(phone),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  const env = await request({
    url: '/api/v2/auth/login',
    method: 'POST',
    data: { phone, phone_country: phoneCountry, password }
  })
  const d = unwrap(env)
  return {
    user: d.user,
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    tokenType: d.token_type,
    expiresIn: d.expires_in
  }
}

async function smsLogin({ phone, phoneCountry, code }) {
  if (MOCK_MODE) {
    await mockDelay()
    if (!/^\d{6}$/.test(code || '')) throw new Error('请输入 6 位验证码')
    return {
      user: mockUser(phone),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  const env = await request({
    url: '/api/v2/auth/sms-login',
    method: 'POST',
    data: { phone, phone_country: phoneCountry, code }
  })
  const d = unwrap(env)
  return {
    user: d.user,
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    tokenType: d.token_type,
    expiresIn: d.expires_in
  }
}

async function sendSmsCode({ phone, phoneCountry, purpose }) {
  if (MOCK_MODE) {
    await mockDelay()
    if (!phone) throw new Error('请输入手机号')
    const code = String(Math.floor(100000 + Math.random() * 900000))
    return { sent: true, code, ttl: 300, mock: true }
  }
  const env = await request({
    url: '/api/v2/auth/send-code',
    method: 'POST',
    data: { phone, phone_country: phoneCountry, purpose: purpose || 'login' }
  })
  const d = unwrap(env)
  return {
    sent: true,
    code: d.code,
    ttl: d.expires_in,
    mock: typeof d.channel_txn_id === 'string' && d.channel_txn_id.startsWith('mock_'),
    channelTxnId: d.channel_txn_id
  }
}

async function register({ phone, phoneCountry, password, smsCode, nickname, languagePref }) {
  if (MOCK_MODE) {
    await mockDelay()
    if (!phone || !password) throw new Error('请输入手机号和密码')
    return { user: mockUser(phone), accessToken: 'mock.access', refreshToken: 'mock.refresh' }
  }
  const env = await request({
    url: '/api/v2/auth/register',
    method: 'POST',
    data: {
      phone,
      phone_country: phoneCountry,
      password,
      sms_code: smsCode,
      nickname: nickname || undefined,
      language_pref: languagePref || 'zh-CN'
    }
  })
  const d = unwrap(env)
  return {
    user: d.user,
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    tokenType: d.token_type,
    expiresIn: d.expires_in
  }
}

// V2 首批 9 国(W1 fallback 列表,跟 web 端 src/api/destinations.js 一致)
const FALLBACK_DESTINATIONS = [
  { id: 1, country_code: 'US', country_name: '美国', visa_types: ['tourism', 'student'], enabled: true },
  { id: 2, country_code: 'JP', country_name: '日本', visa_types: ['tourism', 'student'], enabled: false },
  { id: 3, country_code: 'UK', country_name: '英国', visa_types: ['tourism', 'student'], enabled: false },
  { id: 4, country_code: 'AU', country_name: '澳大利亚', visa_types: ['tourism', 'student'], enabled: false },
  { id: 5, country_code: 'CA', country_name: '加拿大', visa_types: ['tourism', 'student'], enabled: false },
  { id: 6, country_code: 'DE', country_name: '德国(申根)', visa_types: ['tourism', 'student'], enabled: false },
  { id: 7, country_code: 'FR', country_name: '法国(申根)', visa_types: ['tourism', 'student'], enabled: false },
  { id: 8, country_code: 'SG', country_name: '新加坡', visa_types: ['tourism', 'student'], enabled: false },
  { id: 9, country_code: 'NZ', country_name: '新西兰', visa_types: ['tourism', 'student'], enabled: false }
]

function localizeName(d, lang) {
  if (lang && lang.startsWith('en')) {
    const enMap = {
      US: 'United States', JP: 'Japan', UK: 'United Kingdom',
      AU: 'Australia', CA: 'Canada', DE: 'Germany (Schengen)',
      FR: 'France (Schengen)', SG: 'Singapore', NZ: 'New Zealand'
    }
    return enMap[d.country_code] || d.country_name
  }
  if (lang && lang.startsWith('id')) {
    const idMap = { US: 'Amerika Serikat', JP: 'Jepang', UK: 'Inggris', AU: 'Australia', CA: 'Kanada', DE: 'Jerman', FR: 'Prancis', SG: 'Singapura', NZ: 'Selandia Baru' }
    return idMap[d.country_code] || d.country_name
  }
  if (lang && lang.startsWith('vi')) {
    const viMap = { US: 'Hoa Kỳ', JP: 'Nhật Bản', UK: 'Vương quốc Anh', AU: 'Úc', CA: 'Canada', DE: 'Đức', FR: 'Pháp', SG: 'Singapore', NZ: 'New Zealand' }
    return viMap[d.country_code] || d.country_name
  }
  return d.country_name
}

async function listDestinations({ lang, visaType } = {}) {
  const useLang = lang || (getApp().globalData.locale)
  if (MOCK_MODE) {
    await mockDelay()
    return FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, useLang) }))
  }
  try {
    const env = await request({
      url: '/api/v2/destinations',
      method: 'GET',
      data: { lang: useLang, visa_type: visaType }
    })
    const d = unwrap(env)
    return d || []
  } catch (e) {
    console.warn('[destinations] real API failed, fallback:', e.message)
    return FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, useLang) }))
  }
}

// ========== 订单 / 支付 / 找回密码 (W8-2 新增) ==========

// 订单状态机映射(对齐 web 端 src/api/orders.js)
const ORDER_STATUS = {
  PENDING_PAYMENT: 'pending_payment',
  PAID: 'paid',
  REVIEWING: 'reviewing',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  CANCELLED: 'cancelled'
}

const ORDER_STATUS_LABEL = {
  pending_payment: { 'zh-CN': '待付款', 'en': 'Pending Payment', 'id': 'Menunggu Pembayaran', 'vi': 'Chờ thanh toán' },
  paid:            { 'zh-CN': '已付款', 'en': 'Paid', 'id': 'Sudah Dibayar', 'vi': 'Đã thanh toán' },
  reviewing:       { 'zh-CN': '审核中', 'en': 'Under Review', 'id': 'Sedang Ditinjau', 'vi': 'Đang xét duyệt' },
  approved:        { 'zh-CN': '已通过', 'en': 'Approved', 'id': 'Disetujui', 'vi': 'Đã phê duyệt' },
  rejected:        { 'zh-CN': '已拒签', 'en': 'Rejected', 'id': 'Ditolak', 'vi': 'Bị từ chối' },
  cancelled:       { 'zh-CN': '已取消', 'en': 'Cancelled', 'id': 'Dibatalkan', 'vi': 'Đã hủy' }
}

// Mock 订单数据(5 单,覆盖 5 个状态 — 跟 W6-1 SMS Mock + W6-2 支付集成对齐)
const MOCK_ORDERS = [
  { id: 'O-2026-0001', order_no: 'O-2026-0001', country_code: 'US', country_name: '美国', visa_type: 'tourism', amount: 59900, currency: 'CNY', status: 'pending_payment', created_at: '2026-06-10 14:23:00' },
  { id: 'O-2026-0002', order_no: 'O-2026-0002', country_code: 'JP', country_name: '日本', visa_type: 'student', amount: 79900, currency: 'CNY', status: 'paid', created_at: '2026-06-08 09:15:00' },
  { id: 'O-2026-0003', order_no: 'O-2026-0003', country_code: 'DE', country_name: '德国(申根)', visa_type: 'tourism', amount: 89900, currency: 'CNY', status: 'reviewing', created_at: '2026-06-05 16:42:00' },
  { id: 'O-2026-0004', order_no: 'O-2026-0004', country_code: 'SG', country_name: '新加坡', visa_type: 'tourism', amount: 49900, currency: 'CNY', status: 'approved', created_at: '2026-05-28 11:05:00' },
  { id: 'O-2026-0005', order_no: 'O-2026-0005', country_code: 'FR', country_name: '法国(申根)', visa_type: 'student', amount: 99900, currency: 'CNY', status: 'rejected', created_at: '2026-05-20 13:30:00', reject_reason: '材料不完整,缺银行流水' }
]

async function orderList({ status, page = 1, pageSize = 10 } = {}) {
  if (MOCK_MODE) {
    await mockDelay(180)
    let list = MOCK_ORDERS
    if (status) list = list.filter(o => o.status === status)
    return { list, total: list.length, page, pageSize }
  }
  try {
    const env = await request({
      url: '/api/v2/orders',
      method: 'GET',
      data: { status, page, page_size: pageSize }
    })
    const d = unwrap(env)
    return d || { list: [], total: 0, page: 1, pageSize }
  } catch (e) {
    console.warn('[orders] real API failed, fallback mock:', e.message)
    let list = MOCK_ORDERS
    if (status) list = list.filter(o => o.status === status)
    return { list, total: list.length, page, pageSize }
  }
}

async function orderDetail(orderNo) {
  if (MOCK_MODE) {
    await mockDelay(150)
    const o = MOCK_ORDERS.find(x => x.order_no === orderNo)
    if (!o) throw new Error('订单不存在')
    return o
  }
  const env = await request({ url: '/api/v2/orders/' + orderNo, method: 'GET' })
  return unwrap(env)
}

async function createPayment({ orderNo, channel = 'wechat_qr', amount, currency = 'CNY' } = {}) {
  if (MOCK_MODE) {
    await mockDelay(220)
    if (!orderNo) throw new Error('订单号必填')
    return {
      intent_id: 'pi_mock_' + Date.now(),
      order_no: orderNo,
      channel,
      code_url: 'weixin://wxpay/bizpayurl?pr=mock_' + (orderNo || 'X') + '_' + Math.random().toString(36).slice(2, 10),
      amount: amount || 59900,
      currency,
      expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      mock: true
    }
  }
  const env = await request({
    url: '/api/v2/payment/create',
    method: 'POST',
    data: { order_no: orderNo, channel, amount, currency }
  })
  const d = unwrap(env)
  return {
    intentId: d.intent_id,
    orderNo: d.order_no,
    channel: d.channel,
    codeUrl: d.code_url,
    amount: d.amount,
    currency: d.currency,
    expiresAt: d.expires_at,
    mock: !!d.mock
  }
}

async function queryPayment(intentId) {
  if (MOCK_MODE) {
    await mockDelay(80)
    // Mock: 第二次查变 paid
    if (!this._payMockState) this._payMockState = {}
    this._payMockState[intentId] = (this._payMockState[intentId] || 0) + 1
    const paid = this._payMockState[intentId] >= 2
    return { intent_id: intentId, status: paid ? 'paid' : 'pending', paid_at: paid ? new Date().toISOString() : null }
  }
  const env = await request({ url: '/api/v2/payment/' + intentId + '/status', method: 'GET' })
  return unwrap(env)
}

async function sendResetCode({ phone, phoneCountry }) {
  if (MOCK_MODE) {
    await mockDelay(150)
    if (!phone) throw new Error('请输入手机号')
    const code = String(Math.floor(100000 + Math.random() * 900000))
    return { sent: true, code, ttl: 300, mock: true }
  }
  const env = await request({
    url: '/api/v2/auth/send-code',
    method: 'POST',
    data: { phone, phone_country: phoneCountry, purpose: 'reset_password' }
  })
  const d = unwrap(env)
  return { sent: true, code: d.code, ttl: d.expires_in, mock: !!d.channel_txn_id && d.channel_txn_id.startsWith('mock_') }
}

async function wechatLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: async (res) => {
        if (!res.code) {
          reject(new Error('微信登录失败:未获取到 code'))
          return
        }
        try {
          const env = await request({
            url: '/api/v2/auth/wechat',
            method: 'POST',
            data: { code: res.code }
          })
          const d = unwrap(env)
          resolve({
            user: d.user,
            accessToken: d.access_token,
            refreshToken: d.refresh_token,
            tokenType: d.token_type,
            expiresIn: d.expires_in
          })
        } catch (e) {
          reject(e)
        }
      },
      fail: (err) => {
        reject(new Error((err && err.errMsg) || 'wx.login failed'))
      }
    })
  })
}

async function resetPassword({ phone, phoneCountry, smsCode, newPassword }) {
  if (MOCK_MODE) {
    await mockDelay(200)
    if (!/^\d{6}$/.test(smsCode || '')) throw new Error('验证码格式错误')
    if (!newPassword || newPassword.length < 8) throw new Error('新密码至少 8 位')
    if (!/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) throw new Error('密码必须包含字母和数字')
    return { ok: true, resetAt: new Date().toISOString() }
  }
  const env = await request({
    url: '/api/v2/auth/reset-password',
    method: 'POST',
    data: { phone, phone_country: phoneCountry, sms_code: smsCode, new_password: newPassword }
  })
  return unwrap(env)
}

module.exports = {
  request,
  login,
  smsLogin,
  sendSmsCode,
  register,
  wechatLogin,
  listDestinations,
  orderList,
  orderDetail,
  createPayment,
  queryPayment,
  sendResetCode,
  resetPassword,
  ORDER_STATUS,
  ORDER_STATUS_LABEL,
  FALLBACK_DESTINATIONS
}
