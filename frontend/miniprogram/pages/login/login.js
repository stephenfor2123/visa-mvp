// pages/login/login.js
const app = getApp()
const api = require('../../utils/api.js')
const { saveSession } = require('../../utils/auth.js')

Page({
  data: {
    // i18n 状态(从 app.globalData.i18n 取)
    t: {},
    locale: 'zh-CN',
    localeLabel: '中',
    // Tab
    activeTab: 'pwd',
    // 国家区号
    countryIdx: 0,
    countries: [
      { code: '+86', flag: '🇨🇳', label: '🇨🇳 +86 中国大陆' },
      { code: '+62', flag: '🇮🇩', label: '🇮🇩 +62 印度尼西亚' },
      { code: '+84', flag: '🇻🇳', label: '🇻🇳 +84 越南' },
      { code: '+63', flag: '🇵🇭', label: '🇵🇭 +63 菲律宾' }
    ],
    // 表单
    phone: '',
    password: '',
    smsCode: '',
    remember: true,
    // 提交状态
    submitting: false,
    sending: false,
    smsCooldown: 0,
    lastSentCode: '',
    // 错误
    errors: { phone: '', password: '', smsCode: '' }
  },

  onLoad() {
    this.refreshI18n()
  },

  onShow() {
    // 每次显示时同步 i18n(用户可能切了语言)
    this.refreshI18n()
  },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const locale = app.globalData.locale
    // 重新构建 t 函数:绑定到当前 i18n 实例
    const tProxy = {}
    // 把页面用到的 key 一次性挂到 tProxy 上,这样 wxml 改 t(...) 不需要重新 setData 整个 i18n
    // (性能权衡:写死 key 列表,简单直观)
    const keys = [
      'common.app_name', 'login.title', 'login.subtitle', 'login.tab_pwd', 'login.tab_sms',
      'login.phone_label', 'login.phone_placeholder', 'login.pwd_label', 'login.pwd_placeholder',
      'login.sms_label', 'login.sms_placeholder', 'login.send_code', 'login.remember',
      'login.forgot', 'login.submit', 'login.no_account', 'login.go_signup'
    ]
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    // 语言 label (顶部显示)
    const localeLabels = { 'zh-CN': '中', 'en': 'EN', 'id': 'ID', 'vi': 'VI' }
    this.setData({ t: tProxy, locale, localeLabel: localeLabels[locale] || '中' })
  },

  onSwitchLang() {
    // 循环切 4 语种
    const order = ['zh-CN', 'en', 'id', 'vi']
    const cur = app.globalData.locale
    const idx = order.indexOf(cur)
    const next = order[(idx + 1) % order.length]
    app.setLocale(next)
    this.refreshI18n()
    wx.showToast({ title: next, icon: 'none', duration: 800 })
  },

  onSwitchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab, errors: { phone: '', password: '', smsCode: '' } })
  },

  onCountryChange(e) {
    this.setData({ countryIdx: e.detail.value })
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value, 'errors.phone': '' })
  },

  onPwdInput(e) {
    // e.detail.value (AppInput trigger 'input' 传 { value })
    const v = (e.detail && e.detail.value) !== undefined ? e.detail.value : e.detail
    this.setData({ password: v, 'errors.password': '' })
  },

  onSmsInput(e) {
    const v = (e.detail && e.detail.value) !== undefined ? e.detail.value : e.detail
    this.setData({ smsCode: v, 'errors.smsCode': '' })
  },

  onToggleRemember() {
    this.setData({ remember: !this.data.remember })
  },

  onForgot() {
    wx.showToast({ title: '密码找回流程 W2 接入', icon: 'none' })
  },

  goSignup() {
    wx.navigateTo({ url: '/pages/register/register' })
  },

  async onSendCode() {
    if (!this.data.phone || this.data.phone.length < 5) {
      this.setData({ 'errors.phone': app.globalData.i18n.t('errors.phone_invalid') })
      return
    }
    this.setData({ sending: true })
    try {
      const res = await api.sendSmsCode({
        phone: this.data.phone,
        phoneCountry: this.data.countries[this.data.countryIdx].code,
        purpose: 'login'
      })
      this.setData({ lastSentCode: res.code || '', smsCooldown: 60 })
      this.startCooldown()
      wx.showToast({
        title: app.globalData.i18n.t('toast.code_send_success') + (res.mock ? ' (mock)' : ''),
        icon: 'none'
      })
    } catch (e) {
      wx.showToast({ title: e.message || app.globalData.i18n.t('errors.network_error'), icon: 'none' })
    } finally {
      this.setData({ sending: false })
    }
  },

  startCooldown() {
    if (this._timer) clearInterval(this._timer)
    this._timer = setInterval(() => {
      const c = this.data.smsCooldown - 1
      if (c <= 0) {
        clearInterval(this._timer)
        this._timer = null
        this.setData({ smsCooldown: 0 })
      } else {
        this.setData({ smsCooldown: c })
      }
    }, 1000)
  },

  async onSubmit() {
    const i18n = app.globalData.i18n
    const errors = { phone: '', password: '', smsCode: '' }
    if (!this.data.phone || this.data.phone.length < 5) {
      errors.phone = i18n.t('errors.phone_invalid')
    }
    if (this.data.activeTab === 'pwd') {
      if (!this.data.password || this.data.password.length < 6) {
        errors.password = i18n.t('errors.pwd_too_short')
      }
    } else {
      if (!/^\d{6}$/.test(this.data.smsCode)) {
        errors.smsCode = i18n.t('errors.code_invalid')
      }
    }
    if (errors.phone || errors.password || errors.smsCode) {
      this.setData({ errors })
      return
    }
    this.setData({ submitting: true })
    try {
      const phoneCountry = this.data.countries[this.data.countryIdx].code
      let result
      if (this.data.activeTab === 'pwd') {
        result = await api.login({
          phone: this.data.phone,
          phoneCountry,
          password: this.data.password
        })
      } else {
        result = await api.smsLogin({
          phone: this.data.phone,
          phoneCountry,
          code: this.data.smsCode
        })
      }
      saveSession(result)
      wx.showToast({ title: i18n.t('toast.login_success'), icon: 'success' })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/profile/profile' })
      }, 600)
    } catch (e) {
      wx.showToast({ title: e.message || i18n.t('toast.login_fail'), icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  async onWechatLogin() {
    if (this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const result = await api.wechatLogin()
      saveSession(result)
      wx.showToast({ title: app.globalData.i18n.t('toast.login_success'), icon: 'success' })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/profile/profile' })
      }, 600)
    } catch (e) {
      wx.showToast({ title: e.message || app.globalData.i18n.t('toast.login_fail'), icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer)
  }
})
