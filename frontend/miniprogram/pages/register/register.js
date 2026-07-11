// pages/register/register.js
const app = getApp()
const api = require('../../utils/api.js')

Page({
  data: {
    t: {},
    locale: 'zh-CN',
    localeLabel: '中',
    countryIdx: 0,
    countries: [
      { code: '+86', flag: '🇨🇳', label: '🇨🇳 +86 中国大陆' },
      { code: '+62', flag: '🇮🇩', label: '🇮🇩 +62 印度尼西亚' },
      { code: '+84', flag: '🇻🇳', label: '🇻🇳 +84 越南' },
      { code: '+63', flag: '🇵🇭', label: '🇵🇭 +63 菲律宾' }
    ],
    phone: '',
    smsCode: '',
    password: '',
    confirmPassword: '',
    agreed: false,
    submitting: false,
    sending: false,
    smsCooldown: 0,
    lastSentCode: '',
    pwdHint: '',
    errors: { phone: '', smsCode: '', password: '', confirmPassword: '', agreement: '' }
  },

  onLoad() { this.refreshI18n() },
  onShow() { this.refreshI18n() },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const locale = app.globalData.locale
    const keys = [
      'common.app_name', 'register.title', 'register.subtitle',
      'register.phone_label', 'register.phone_placeholder', 'register.sms_label',
      'register.sms_placeholder', 'register.send_code', 'register.pwd_label',
      'register.pwd_placeholder', 'register.confirm_pwd_label', 'register.confirm_pwd_placeholder',
      'register.agreement_prefix', 'register.agreement_terms', 'register.agreement_and',
      'register.agreement_privacy', 'register.submit', 'register.submitting',
      'register.have_account', 'register.go_login',
      'errors.pwd_too_short', 'errors.pwd_too_long', 'errors.pwd_format', 'errors.pwd_mismatch',
      'errors.code_invalid', 'errors.phone_invalid', 'errors.agreement_required',
      'toast.code_send_success', 'toast.register_success', 'toast.register_fail', 'errors.network_error',
      'errors.user_exists'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    const localeLabels = { 'zh-CN': '中', 'en': 'EN', 'id': 'ID', 'vi': 'VI' }
    this.setData({ t: tProxy, locale, localeLabel: localeLabels[locale] || '中' })
  },

  onSwitchLang() {
    const order = ['zh-CN', 'en', 'id', 'vi']
    const cur = app.globalData.locale
    const next = order[(order.indexOf(cur) + 1) % order.length]
    app.setLocale(next)
    this.refreshI18n()
  },

  onCountryChange(e) { this.setData({ countryIdx: e.detail.value }) },
  onPhoneInput(e) { this.setData({ phone: e.detail.value, 'errors.phone': '' }) },
  onSmsInput(e) {
    const v = (e.detail && e.detail.value) !== undefined ? e.detail.value : e.detail
    this.setData({ smsCode: v, 'errors.smsCode': '' })
  },
  onPwdInput(e) {
    const v = (e.detail && e.detail.value) !== undefined ? e.detail.value : e.detail
    this.setData({ password: v, 'errors.password': '' })
    this.updatePwdHint(v)
  },
  onConfirmPwdInput(e) {
    const v = (e.detail && e.detail.value) !== undefined ? e.detail.value : e.detail
    this.setData({ confirmPassword: v, 'errors.confirmPassword': '' })
  },
  onToggleAgree() { this.setData({ agreed: !this.data.agreed, 'errors.agreement': '' }) },

  updatePwdHint(v) {
    const i18n = app.globalData.i18n
    let hint = ''
    if (!v) { this.setData({ pwdHint: '' }); return }
    if (v.length < 8) hint = i18n.t('validation.pwd_too_short')
    else if (v.length > 32) hint = i18n.t('errors.pwd_too_long')
    else if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) hint = i18n.t('errors.pwd_format')
    this.setData({ pwdHint: hint })
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
        purpose: 'register'
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
        clearInterval(this._timer); this._timer = null
        this.setData({ smsCooldown: 0 })
      } else {
        this.setData({ smsCooldown: c })
      }
    }, 1000)
  },

  validate() {
    const i18n = app.globalData.i18n
    const errors = { phone: '', smsCode: '', password: '', confirmPassword: '', agreement: '' }
    let ok = true
    if (!this.data.phone || this.data.phone.length < 5) {
      errors.phone = i18n.t('errors.phone_invalid'); ok = false
    }
    if (!/^\d{6}$/.test(this.data.smsCode)) {
      errors.smsCode = i18n.t('errors.code_invalid'); ok = false
    }
    if (this.data.password.length < 8) {
      errors.password = i18n.t('validation.pwd_too_short'); ok = false
    } else if (this.data.password.length > 32) {
      errors.password = i18n.t('errors.pwd_too_long'); ok = false
    } else if (!/[A-Za-z]/.test(this.data.password) || !/\d/.test(this.data.password)) {
      errors.password = i18n.t('errors.pwd_format'); ok = false
    }
    if (this.data.password !== this.data.confirmPassword) {
      errors.confirmPassword = i18n.t('errors.pwd_mismatch'); ok = false
    }
    if (!this.data.agreed) {
      errors.agreement = i18n.t('errors.agreement_required'); ok = false
    }
    this.setData({ errors })
    return ok
  },

  async onSubmit() {
    if (!this.validate()) return
    const i18n = app.globalData.i18n
    this.setData({ submitting: true })
    try {
      await api.register({
        phone: this.data.phone,
        phoneCountry: this.data.countries[this.data.countryIdx].code,
        password: this.data.password,
        smsCode: this.data.smsCode,
        languagePref: this.data.locale
      })
      wx.showToast({ title: i18n.t('toast.register_success'), icon: 'success' })
      setTimeout(() => {
        wx.redirectTo({ url: '/pages/login/login' })
      }, 800)
    } catch (e) {
      const msg = e.message || i18n.t('toast.register_fail')
      wx.showToast({ title: msg, icon: 'none' })
      if (/already|已注册|2003/i.test(msg)) {
        this.setData({ 'errors.phone': i18n.t('errors.user_exists') })
      }
    } finally {
      this.setData({ submitting: false })
    }
  },

  goLogin() { wx.redirectTo({ url: '/pages/login/login' }) },

  onUnload() { if (this._timer) clearInterval(this._timer) }
})
