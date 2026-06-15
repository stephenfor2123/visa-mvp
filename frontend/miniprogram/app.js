// app.js
// 微信小程序入口:全局状态 + 启动初始化
// V2 W6b:微信小程序端启动(独立 scaffold,移植 web 端 4-6 页核心流程)
const { I18n } = require('./utils/i18n.js')
const { TOKEN_KEY, USER_KEY } = require('./utils/auth.js')

App({
  globalData: {
    // API base: 跟 web 端对齐(/api/v2/...),可用 wx.setStorageSync('apiBase', ...) 覆盖
    apiBase: 'https://api.visa-helper.example.com',
    // 当前语言(从 storage 读,fallback 系统语言,再 fallback zh-CN)
    locale: 'zh-CN',
    // 全局 i18n 实例
    i18n: null,
    // 业务状态
    token: '',
    user: null
  },

  onLaunch() {
    // 启动时初始化 i18n
    const stored = wx.getStorageSync('locale')
    const sysInfo = wx.getSystemInfoSync()
    const sysLang = (sysInfo && sysInfo.language) || 'zh-CN'
    const locale = stored || sysLang
    this.globalData.locale = locale
    this.globalData.i18n = new I18n(locale)
    // 恢复 token / user
    this.globalData.token = wx.getStorageSync(TOKEN_KEY) || ''
    const userStr = wx.getStorageSync(USER_KEY)
    if (userStr) {
      try { this.globalData.user = JSON.parse(userStr) } catch (_) {}
    }
    // 输出启动日志(便于真机调试)
    console.log('[visa-mp] launched, locale=', locale, 'token?', !!this.globalData.token)
  },

  // 全局切换语言
  setLocale(locale) {
    this.globalData.locale = locale
    this.globalData.i18n = new I18n(locale)
    wx.setStorageSync('locale', locale)
  },

  // 业务工具便捷调用
  t(key) {
    return this.globalData.i18n ? this.globalData.i18n.t(key) : key
  }
})
