// pages/forgot/forgot.js
// W8-2 找回密码:复用 B-W6-1 SMS Mock → 重置密码
const app = getApp()
const api = require('../../utils/api.js')

Page({
  data: {
    t: {},
    countryIdx: 0,
    countries: [
      { code: '+86', label: '🇨🇳 +86' },
      { code: '+62', label: '🇮🇩 +62' },
      { code: '+84', label: '🇻🇳 +84' },
      { code: '+63', label: '🇵🇭 +63' }
    ],
    phone: '',
    smsCode: '',
    newPwd: '',
    confirmPwd: '',
    sending: false,
    smsCooldown: 0,
    submitting: false,
    success: false,
    errors: { phone: '', smsCode: '', newPwd: '', confirmPwd: '' }
  },

  onLoad() { this.refreshI18n() },
  onShow() { this.refreshI18n() },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'forgot.page_title', 'forgot.page_subtitle',
      'forgot.phone_label', 'forgot.phone_placeholder',
      'forgot.sms_label', 'forgot.sms_placeholder',
      'forgot.send_code', 'forgot.resend_code',
      'forgot.new_pwd_label', 'forgot.new_pwd_placeholder',
      'forgot.confirm_pwd_label', 'forgot.confirm_pwd_placeholder',
      'forgot.submit', 'forgot.submitting', 'forgot.back_login',
      'forgot.success_title', 'forgot.success_desc', 'forgot.go_login',
      'errors.phone_invalid', 'errors.code_invalid', 'errors.pwd_too_short',
      'errors.pwd_format', 'errors.pwd_mismatch'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  onCountryChange(e) { this.setData({ countryIdx: e.detail.value }) },

  onPhoneInput(e) { this.setData({ phone: e.detail.value, 'errors.phone': '' }) },
  onSmsInput(e) { this.setData({ smsCode: e.detail.value, 'errors.smsCode': '' }) },
  onNewPwdInput(e) { this.setData({ newPwd: e.detail.value, 'errors.newPwd': '' }) },
  onConfirmPwdInput(e) { this.setData({ confirmPwd: e.detail.value, 'errors.confirmPwd': '' }) },

  async onSendCode() {
    if (!this.data.phone || this.data.phone.length < 5) {
      this.setData({ 'errors.phone': this.data.t['errors.phone_invalid'] })
      return
    }
    this.setData({ sending: true })
    try {
      await api.sendResetCode({ phone: this.data.phone, phoneCountry: this.data.countries[this.data.countryIdx].code })
      this.setData({ smsCooldown: 60 })
      this.startCooldown()
      wx.showToast({ title: '✓ ' + (this.data.t['forgot.send_code'] || 'Sent'), icon: 'success' })
    } catch (e) {
      wx.showToast({ title: e.message || 'Failed', icon: 'none' })
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

  async onSubmit() {
    const t = this.data.t
    const errors = { phone: '', smsCode: '', newPwd: '', confirmPwd: '' }
    if (!this.data.phone || this.data.phone.length < 5) errors.phone = t['errors.phone_invalid']
    if (!/^\d{6}$/.test(this.data.smsCode)) errors.smsCode = t['errors.code_invalid']
    if (!this.data.newPwd || this.data.newPwd.length < 8) errors.newPwd = t['errors.pwd_too_short']
    else if (!/[A-Za-z]/.test(this.data.newPwd) || !/\d/.test(this.data.newPwd)) errors.newPwd = t['errors.pwd_format']
    if (this.data.newPwd !== this.data.confirmPwd) errors.confirmPwd = t['errors.pwd_mismatch']
    if (errors.phone || errors.smsCode || errors.newPwd || errors.confirmPwd) {
      this.setData({ errors })
      return
    }
    this.setData({ submitting: true })
    try {
      await api.resetPassword({
        phone: this.data.phone,
        phoneCountry: this.data.countries[this.data.countryIdx].code,
        smsCode: this.data.smsCode,
        newPassword: this.data.newPwd
      })
      this.setData({ success: true, submitting: false })
    } catch (e) {
      this.setData({ submitting: false })
      wx.showToast({ title: e.message || 'Failed', icon: 'none' })
    }
  },

  onGoLogin() { wx.redirectTo({ url: '/pages/login/login' }) },
  onBackLogin() { wx.redirectTo({ url: '/pages/login/login' }) },

  onUnload() { if (this._timer) clearInterval(this._timer) }
})
