import http from './http'

// B 端真实端点(后端 B 跑起后):
//   POST /api/v2/auth/login          - 密码登录
//   POST /api/v2/auth/sms-login      - 短信快捷登录
//   POST /api/v2/auth/send-code      - 发送验证码 (mock,直接返回 code)
//   POST /api/v2/auth/register       - 注册
//   POST /api/v2/auth/refresh        - 刷新 token
// 当前 W1: 后端未必已就绪 → 前端用 localStorage mock 兜底,跑通流程

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认走 mock

function delay(ms = 250) {
  return new Promise((r) => setTimeout(r, ms))
}

function mockUser(phone) {
  return {
    id: 'u_' + Math.random().toString(36).slice(2, 10),
    phone,
    phoneCountry: '+86',
    nickname: '签证用户_' + phone.slice(-4),
    languagePref: 'zh-CN',
    status: 'active',
    createdAt: new Date().toISOString()
  }
}

export async function login({ phone, phoneCountry, password }) {
  if (MOCK_MODE) {
    await delay()
    if (!phone || !password) throw new Error('请输入手机号和密码')
    if (password.length < 6) throw new Error('密码至少 6 位')
    return {
      user: mockUser(phone),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  return http.post('/v2/auth/login', {
    phone,
    phone_country: phoneCountry,
    password
  }).then((env) => {
    if (env.code !== '1000') throw new Error(env.message || 'Login failed')
    const d = env.data || {}
    return {
      user: d.user,
      accessToken: d.access_token,
      refreshToken: d.refresh_token,
      tokenType: d.token_type,
      expiresIn: d.expires_in
    }
  })
}

export async function smsLogin({ phone, phoneCountry, code }) {
  if (MOCK_MODE) {
    await delay()
    if (!/^\d{6}$/.test(code || '')) throw new Error('请输入 6 位验证码')
    return {
      user: mockUser(phone),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  return http.post('/v2/auth/sms-login', {
    phone,
    phone_country: phoneCountry,
    code
  }).then((env) => {
    if (env.code !== '1000') throw new Error(env.message || 'SMS login failed')
    const d = env.data || {}
    return {
      user: d.user,
      accessToken: d.access_token,
      refreshToken: d.refresh_token,
      tokenType: d.token_type,
      expiresIn: d.expires_in
    }
  })
}

export async function sendSmsCode({ phone, phoneCountry, purpose }) {
  if (MOCK_MODE) {
    await delay()
    if (!phone) throw new Error('请输入手机号')
    // Mock 模式:测试期任何 6 位数字都通过
    const code = String(Math.floor(100000 + Math.random() * 900000))
    return { sent: true, code, ttl: 300, mock: true }
  }
  // Real backend returns ApiResponse envelope: { code, message, data: { phone, ..., code, channel_txn_id, expires_in } }
  const envelope = await http.post('/v2/auth/send-code', {
    phone,
    phone_country: phoneCountry,
    purpose: purpose || 'login'
  })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'send-code failed')
  }
  const d = envelope.data || {}
  return {
    sent: true,
    code: d.code,
    ttl: d.expires_in,
    mock: typeof d.channel_txn_id === 'string' && d.channel_txn_id.startsWith('mock_'),
    channelTxnId: d.channel_txn_id
  }
}

export async function register(payload) {
  if (MOCK_MODE) {
    await delay()
    if (!payload.phone || !payload.password) throw new Error('请输入手机号和密码')
    return { user: mockUser(payload.phone), accessToken: 'mock.access', refreshToken: 'mock.refresh' }
  }
  // Real backend returns ApiResponse envelope: { code, message, data: { access_token, refresh_token, ... user } }
  // http.js already unwraps one level (returns resp.data), so we get { code, message, data: { ... } } here.
  const envelope = await http.post('/v2/auth/register', {
    phone: payload.phone,
    phone_country: payload.phoneCountry,
    password: payload.password,
    sms_code: payload.smsCode,
    nickname: payload.nickname || undefined,
    language_pref: payload.languagePref || 'zh-CN'
  })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'Register failed')
  }
  const d = envelope.data || {}
  const payload_out = {
    user: d.user,
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    tokenType: d.token_type,
    expiresIn: d.expires_in
  }
  // Spec 要求"成功后跳 /login",但任务原文又要求"localStorage 存 JWT"。
  // 直接塞 visa.auth 会让 router guard 把 /login 当作已登录再踢回 /home。
  // 所以存到独立的 visa.pending_jwt key(只对真后端生效),UI 仍走 /login。
  try {
    localStorage.setItem('visa.pending_jwt', JSON.stringify({
      accessToken: payload_out.accessToken,
      refreshToken: payload_out.refreshToken,
      user: payload_out.user,
      savedAt: new Date().toISOString()
    }))
  } catch (_) {}
  return payload_out
}

export async function refresh(refreshToken) {
  if (MOCK_MODE) {
    await delay()
    return { accessToken: 'mock.access.' + Date.now(), refreshToken }
  }
  return http.post('/v2/auth/refresh', { refreshToken })
}

export async function resetPassword({ phone, phoneCountry, smsCode, newPassword }) {
  if (MOCK_MODE) {
    await delay()
    if (!/^\d{6}$/.test(smsCode || '')) throw new Error('请输入 6 位验证码')
    if (!newPassword || newPassword.length < 8) throw new Error('密码至少 8 位')
    return { success: true, message: 'Password updated successfully' }
  }
  const envelope = await http.post('/v2/auth/reset-password', {
    phone,
    phone_country: phoneCountry,
    sms_code: smsCode,
    new_password: newPassword
  })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'Reset password failed')
  }
  return { success: true, message: (envelope.data || {}).message || 'Password updated successfully' }
}