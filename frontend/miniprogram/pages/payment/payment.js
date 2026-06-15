// pages/payment/payment.js
// W8-2 支付页:调 B-W6-2 POST /api/v2/payment/create 拿 code_url,渲染 QR + 1.5s 后台轮询
const app = getApp()
const api = require('../../utils/api.js')

Page({
  data: {
    t: {},
    orderNo: '',
    intentId: '',
    codeUrl: '',
    amount: 0,
    amountYuan: '0.00',
    currency: 'CNY',
    expiresAt: '',
    status: 'pending',   // pending / paid / failed
    countdown: 15,        // minutes
    pollCount: 0,
    pollCountdown: 0,     // seconds
    pollIntervalMs: 1500, // D spec 1.5s
    loading: true,
    paid: false
  },

  onLoad(query) {
    this.refreshI18n()
    this.setData({ orderNo: (query && query.order_no) || '' })
    if (this.data.orderNo) this.createPayment()
  },

  onUnload() {
    this.clearTimers()
  },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'payment.page_title', 'payment.page_subtitle',
      'payment.order_label', 'payment.amount_label',
      'payment.qr_hint', 'payment.qr_loading', 'payment.qr_expired',
      'payment.status_pending', 'payment.status_paid', 'payment.status_failed',
      'payment.polling_label', 'payment.polling_unit', 'payment.poll_now',
      'payment.expire_label', 'payment.expire_unit',
      'payment.back_btn', 'payment.back_success',
      'payment.create_failed', 'payment.poll_failed',
      'common.retry', 'common.cancel'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  async createPayment() {
    this.setData({ loading: true })
    try {
      const res = await api.createPayment({ orderNo: this.data.orderNo, channel: 'wechat_qr' })
      this.setData({
        intentId: res.intentId || res.intent_id,
        codeUrl: res.codeUrl || res.code_url,
        amount: res.amount,
        amountYuan: ((res.amount || 0) / 100).toFixed(2),
        currency: res.currency || 'CNY',
        expiresAt: res.expiresAt || res.expires_at,
        loading: false
      })
      this.startExpireCountdown()
      this.startPolling()
    } catch (e) {
      this.setData({ loading: false })
      wx.showModal({
        title: this.data.t['payment.create_failed'] || 'Create failed',
        content: e.message || '',
        showCancel: false,
        confirmText: this.data.t['common.retry'] || 'Retry',
        success: () => wx.navigateBack()
      })
    }
  },

  // 二维码有效期倒计时(分钟)
  startExpireCountdown() {
    this.setData({ countdown: 15 })
    if (this._expireTimer) clearInterval(this._expireTimer)
    this._expireTimer = setInterval(() => {
      const c = this.data.countdown - 1
      if (c <= 0) {
        clearInterval(this._expireTimer)
        this._expireTimer = null
        this.setData({ countdown: 0, status: 'failed' })
        return
      }
      this.setData({ countdown: c })
    }, 60 * 1000)
  },

  // 1.5s 轮询支付状态
  startPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer)
    if (this._pollCountdownTimer) clearInterval(this._pollCountdownTimer)
    this.setData({ pollCountdown: 2 }) // 第一次等 2s,后续 1.5s
    this._pollCountdownTimer = setInterval(() => {
      const c = this.data.pollCountdown - 1
      if (c <= 0) {
        this.setData({ pollCountdown: Math.ceil(this.data.pollIntervalMs / 1000) })
      } else {
        this.setData({ pollCountdown: c })
      }
    }, 1000)
    this._pollTimer = setInterval(() => {
      if (this.data.paid) return
      this.pollStatus()
    }, this.data.pollIntervalMs)
    // 立即查一次
    setTimeout(() => this.pollStatus(), 200)
  },

  async pollStatus() {
    if (!this.data.intentId) return
    this.setData({ pollCount: this.data.pollCount + 1 })
    try {
      const res = await api.queryPayment(this.data.intentId)
      const status = res.status
      if (status === 'paid' || status === 'succeeded') {
        this.setData({ status: 'paid', paid: true })
        this.clearTimers()
        wx.showToast({ title: this.data.t['payment.status_paid'] || 'Paid', icon: 'success' })
        setTimeout(() => wx.navigateBack(), 1200)
      } else if (status === 'failed' || status === 'expired') {
        this.setData({ status: 'failed' })
        this.clearTimers()
      }
    } catch (e) {
      // 静默失败:不打断用户,继续轮询
    }
  },

  onPollNow() {
    this.pollStatus()
  },

  clearTimers() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
    if (this._pollCountdownTimer) { clearInterval(this._pollCountdownTimer); this._pollCountdownTimer = null }
    if (this._expireTimer) { clearInterval(this._expireTimer); this._expireTimer = null }
  }
})
