// utils/auth.js
// Token + User 持久化(对齐 web 端 localStorage visa.auth/visa.pending_jwt)
const TOKEN_KEY = 'visa.auth.token'
const USER_KEY = 'visa.auth.user'
const REFRESH_KEY = 'visa.auth.refresh'

function saveSession({ accessToken, refreshToken, user, expiresIn }) {
  const app = getApp()
  if (app && app.globalData) {
    app.globalData.token = accessToken || ''
    app.globalData.user = user || null
  }
  try {
    if (accessToken) wx.setStorageSync(TOKEN_KEY, accessToken)
    if (refreshToken) wx.setStorageSync(REFRESH_KEY, refreshToken)
    if (user) wx.setStorageSync(USER_KEY, JSON.stringify(user))
  } catch (_) {}
}

function clearSession() {
  const app = getApp()
  if (app && app.globalData) {
    app.globalData.token = ''
    app.globalData.user = null
  }
  try {
    wx.removeStorageSync(TOKEN_KEY)
    wx.removeStorageSync(REFRESH_KEY)
    wx.removeStorageSync(USER_KEY)
  } catch (_) {}
}

function getToken() {
  const app = getApp()
  return (app && app.globalData && app.globalData.token) || (wx.getStorageSync(TOKEN_KEY) || '')
}

function getUser() {
  const app = getApp()
  if (app && app.globalData && app.globalData.user) return app.globalData.user
  try {
    const s = wx.getStorageSync(USER_KEY)
    return s ? JSON.parse(s) : null
  } catch (_) { return null }
}

function isLoggedIn() {
  return !!getToken()
}

module.exports = {
  TOKEN_KEY,
  USER_KEY,
  saveSession,
  clearSession,
  getToken,
  getUser,
  isLoggedIn
}
