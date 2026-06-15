// pages/agreement/agreement.js
// W8-2 服务协议 + 隐私政策(static 4 段 × 2 tab)
const app = getApp()

Page({
  data: {
    t: {},
    activeTab: 'terms'
  },

  onLoad(query) {
    if (query && query.tab) this.setData({ activeTab: query.tab })
    this.refreshI18n()
  },

  onShow() { this.refreshI18n() },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'agreement.page_title', 'agreement.page_subtitle',
      'agreement.tab_terms', 'agreement.tab_privacy',
      'agreement.terms_title', 'agreement.terms_effective',
      'agreement.terms_section_1_title', 'agreement.terms_section_1_body',
      'agreement.terms_section_2_title', 'agreement.terms_section_2_body',
      'agreement.terms_section_3_title', 'agreement.terms_section_3_body',
      'agreement.terms_section_4_title', 'agreement.terms_section_4_body',
      'agreement.privacy_title', 'agreement.privacy_effective',
      'agreement.privacy_section_1_title', 'agreement.privacy_section_1_body',
      'agreement.privacy_section_2_title', 'agreement.privacy_section_2_body',
      'agreement.privacy_section_3_title', 'agreement.privacy_section_3_body',
      'agreement.privacy_section_4_title', 'agreement.privacy_section_4_body'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  onSwitchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab })
  }
})
