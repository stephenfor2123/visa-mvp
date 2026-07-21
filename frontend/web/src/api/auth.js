import http from './http'

// B 端真实端点(后端 B 跑起后):
//   POST /api/v2/auth/login          - 密码登录(账户=email/username + password)
//   POST /api/v2/auth/register       - 注册(username + email + password)
//   POST /api/v2/auth/refresh        - 刷新 token
// 当前 W1: 后端未必已就绪 → 前端用 localStorage mock 兜底,跑通流程

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认走 mock

function delay(ms = 250) {
  return new Promise((r) => setTimeout(r, ms))
}

function mockUser(account) {
  // 用 account 的前几位作为昵称后缀
  const suffix = (account.includes('@') ? account.split('@')[0] : account).slice(-6)
  return {
    id: 'u_' + Math.random().toString(36).slice(2, 10),
    username: account.includes('@') ? account.split('@')[0] : account,
    email: account.includes('@') ? account : `${account}@htex.local`,
    nickname: '签证用户_' + suffix,
    languagePref: 'zh-CN',
    status: 'active',
    createdAt: new Date().toISOString()
  }
}

export async function login({ account, password }) {
  if (MOCK_MODE) {
    await delay()
    if (!account || !password) throw new Error('请输入账户和密码')
    if (password.length < 6) throw new Error('密码至少 6 位')
    return {
      user: mockUser(account),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  return http.post('/v2/auth/login', {
    account,
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

export async function register(payload) {
  if (MOCK_MODE) {
    await delay()
    if (!payload.email || !payload.password) throw new Error('请输入邮箱和密码')
    if (!payload.username) throw new Error('请输入用户名')
    return { user: mockUser(payload.email), accessToken: 'mock.access', refreshToken: 'mock.refresh' }
  }
  const envelope = await http.post('/v2/auth/register', {
    username: payload.username,
    email: payload.email,
    password: payload.password,
    nickname: payload.nickname || undefined,
    language_pref: payload.languagePref || 'zh-CN',
    email_code: payload.emailCode || payload.email_code,
    age_confirmed_16: payload.ageConfirmed16 === true || payload.age_confirmed_16 === true,
  })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'Register failed')
  }
  const d = envelope.data || {}
  return {
    user: d.user,
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    tokenType: d.token_type,
    expiresIn: d.expires_in
  }
}

export async function refresh(refreshToken) {
  if (MOCK_MODE) {
    await delay()
    return { accessToken: 'mock.access.' + Date.now(), refreshToken }
  }
  // W37 fix: backend RefreshRequest expects snake_case `refresh_token`
  // (model_config extra="forbid" + required field → camelCase always 422'd).
  // __isRefreshCall marks this so http.js's 401 interceptor doesn't try to
  // refresh-and-retry a failing refresh call itself (would recurse forever).
  return http.post(
    '/v2/auth/refresh',
    { refresh_token: refreshToken },
    { __silent: true, __isRefreshCall: true }
  ).then((env) => {
    if (env.code !== '1000') throw new Error(env.message || 'Refresh failed')
    const d = env.data || {}
    return {
      user: d.user,
      accessToken: d.access_token,
      refreshToken: d.refresh_token,
      expiresIn: d.expires_in
    }
  })
}

export async function loginWithGoogle(credential, { ageConfirmed16 = false } = {}) {
  if (MOCK_MODE) {
    await delay()
    return {
      user: mockUser('google_user@gmail.com'),
      accessToken: 'mock.access.' + Date.now(),
      refreshToken: 'mock.refresh.' + Date.now(),
      expiresIn: 3600
    }
  }
  return http.post('/v2/auth/google', {
    id_token: credential,
    age_confirmed_16: ageConfirmed16 === true,
  }).then((env) => {
    if (env.code !== '1000') throw new Error(env.message || 'Google login failed')
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

export async function requestPasswordReset({ account }) {
  if (MOCK_MODE) {
    await delay()
    if (!account) throw new Error('请输入账号')
    return { message: 'If the account exists, a reset link has been sent' }
  }
  const envelope = await http.post('/v2/auth/password-reset-request', { account })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'Request failed')
  }
  return envelope.data || {}
}

export async function resetPassword({ token, newPassword }) {
  if (MOCK_MODE) {
    await delay()
    if (!newPassword || newPassword.length < 8) throw new Error('密码至少 8 位')
    return { success: true, message: 'Password updated successfully' }
  }
  const envelope = await http.post('/v2/auth/reset-password', {
    token,
    new_password: newPassword
  })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'Reset password failed')
  }
  return { success: true, message: (envelope.data || {}).message || 'Password updated successfully' }
}
