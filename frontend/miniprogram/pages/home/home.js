// pages/home/home.js
const app = getApp()

Page({
  data: {
    t: {},
    heroCountries: [
      { code: 'TH', flag: '🇹🇭', name: 'Thailand' },
      { code: 'VN', flag: '🇻🇳', name: 'Vietnam' },
      { code: 'ID', flag: '🇮🇩', name: 'Indonesia' },
      { code: 'PH', flag: '🇵🇭', name: 'Philippines' },
      { code: 'MY', flag: '🇲🇾', name: 'Malaysia' },
      { code: 'SG', flag: '🇸🇬', name: 'Singapore' }
    ],
    features: []
  },

  onLoad() { this.refreshI18n() },
  onShow() { this.refreshI18n() },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'home.hero_title', 'home.hero_sub', 'home.hero_login', 'home.hero_explore',
      'home.section_features', 'home.section_features_sub',
      'home.feature_1_title', 'home.feature_1_desc',
      'home.feature_2_title', 'home.feature_2_desc',
      'home.feature_3_title', 'home.feature_3_desc',
      'home.feature_4_title', 'home.feature_4_desc',
      'toast.login_success', 'toast.logout_success'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    const features = [
      { title: tProxy['home.feature_1_title'], desc: tProxy['home.feature_1_desc'] },
      { title: tProxy['home.feature_2_title'], desc: tProxy['home.feature_2_desc'] },
      { title: tProxy['home.feature_3_title'], desc: tProxy['home.feature_3_desc'] },
      { title: tProxy['home.feature_4_title'], desc: tProxy['home.feature_4_desc'] }
    ]
    this.setData({ t: tProxy, features })
  },

  onLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  onExplore() {
    wx.switchTab({ url: '/pages/destinations/destinations' })
  }
})
