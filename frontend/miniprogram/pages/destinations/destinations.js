// pages/destinations/destinations.js
const app = getApp()
const api = require('../../utils/api.js')

Page({
  data: {
    t: {},
    destinations: [],
    loading: false,
    error: ''
  },

  onLoad() {
    this.refreshI18n()
    this.load()
  },

  onShow() { this.refreshI18n() },
  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'common.loading', 'dest.title', 'dest.subtitle',
      'dest.tourism', 'dest.student', 'dest.coming_soon', 'dest.apply_now',
      'common.network_error'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  async load() {
    const i18n = app.globalData.i18n
    this.setData({ loading: true, error: '' })
    try {
      const list = await api.listDestinations({ lang: app.globalData.locale })
      // 加 flag emoji + 本地化
      const enriched = list.map((d) => ({
        ...d,
        flag: flagEmoji(d.country_code)
      }))
      this.setData({ destinations: enriched })
    } catch (e) {
      this.setData({ error: e.message || i18n.t('common.network_error') })
    } finally {
      this.setData({ loading: false })
    }
  },

  onTapCard(e) {
    const { country, enabled } = e.currentTarget.dataset
    if (!enabled) {
      wx.showToast({ title: app.globalData.i18n.t('dest.coming_soon'), icon: 'none' })
    }
  },

  onApply(e) {
    // e.detail 来自 AppButton 的 trigger event
    const country = e.currentTarget.dataset.country
    wx.showToast({
      title: country + ' — ' + app.globalData.i18n.t('dest.apply_now'),
      icon: 'none'
    })
    // 真实场景:wx.navigateTo 到 materials 扫描页(V2.1 接入)
  }
})

function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}
