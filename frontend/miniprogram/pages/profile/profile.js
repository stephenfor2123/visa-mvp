// pages/profile/profile.js
const app = getApp()
const { clearSession, getUser, isLoggedIn } = require('../../utils/auth.js')

Page({
  data: {
    t: {},
    user: null,
    registerTime: '',
    initial: '',
    isLoggedIn: false
  },

  onLoad() { this.refreshI18n(); this.refreshUser() },
  onShow() { this.refreshI18n(); this.refreshUser() },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'profile.page_title', 'profile.page_subtitle', 'profile.user_id',
      'profile.language_pref', 'profile.register_time', 'profile.status',
      'profile.status_active', 'profile.logged_out', 'profile.go_login',
      'nav.logout', 'toast.logout_success',
      'common.app_name'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  refreshUser() {
    const user = getUser()
    if (user) {
      this.setData({
        user,
        isLoggedIn: true,
        registerTime: user.createdAt ? new Date(user.createdAt).toLocaleString() : '-',
        initial: (user.nickname || user.phone || '?').slice(0, 1).toUpperCase()
      })
    } else {
      this.setData({ user: null, isLoggedIn: false, initial: '?' })
    }
  },

  // W8-2 新增:订单入口
  onGoOrders() {
    if (!isLoggedIn()) { wx.showToast({ title: this.data.t['profile.go_login'] || 'Login first', icon: 'none' }); return }
    wx.navigateTo({ url: '/pages/order/order' })
  },

  // W8-2 新增:找回密码入口
  onGoForgot() {
    wx.navigateTo({ url: '/pages/forgot/forgot' })
  },

  // W8-2 新增:服务协议入口
  onGoAgreement() {
    wx.navigateTo({ url: '/pages/agreement/agreement' })
  },

  onLogout() {
    clearSession()
    wx.showToast({ title: app.globalData.i18n.t('toast.logout_success'), icon: 'success' })
    this.setData({ user: null, isLoggedIn: false, initial: '?' })
  },

  onGoLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  }
})
