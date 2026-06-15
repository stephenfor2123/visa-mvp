// pages/order/order.js
// W8-2 订单列表页:5 个状态 tab 切换 + 状态机渲染 + 跳转支付
const app = getApp()
const api = require('../../utils/api.js')
const { isLoggedIn } = require('../../utils/auth.js')

Page({
  data: {
    t: {},
    isLoggedIn: false,
    activeTab: 'all',
    tabs: [
      { key: 'all', labelKey: 'order.tab_all' },
      { key: 'pending_payment', labelKey: 'order.tab_pending_payment' },
      { key: 'paid', labelKey: 'order.tab_paid' },
      { key: 'reviewing', labelKey: 'order.tab_reviewing' },
      { key: 'approved', labelKey: 'order.tab_approved' },
      { key: 'rejected', labelKey: 'order.tab_rejected' }
    ],
    list: [],
    loading: true,
    empty: false
  },

  onLoad() {
    this.refreshI18n()
  },

  onShow() {
    this.refreshI18n()
    if (isLoggedIn()) {
      this.setData({ isLoggedIn: true })
      this.loadList()
    } else {
      this.setData({ isLoggedIn: false, list: [], empty: false, loading: false })
    }
  },

  onPullDownRefresh() {
    this.loadList().then(() => wx.stopPullDownRefresh())
  },

  refreshI18n() {
    const i18n = app.globalData.i18n
    const keys = [
      'order.page_title', 'order.page_subtitle', 'order.tab_all',
      'order.tab_pending_payment', 'order.tab_paid', 'order.tab_reviewing',
      'order.tab_approved', 'order.tab_rejected', 'order.loading',
      'order.empty_title', 'order.empty_desc', 'order.empty_action',
      'order.item_amount', 'order.item_visa_type', 'order.item_visa_tourism',
      'order.item_visa_student', 'order.item_created', 'order.item_pay_now',
      'order.item_view_detail', 'order.reject_reason_label', 'order.load_failed',
      'order.not_logged_in', 'order.go_login',
      'common.retry', 'common.cancel'
    ]
    const tProxy = {}
    keys.forEach((k) => { tProxy[k] = i18n.t(k) })
    this.setData({ t: tProxy })
  },

  async loadList() {
    this.setData({ loading: true })
    try {
      const status = this.data.activeTab === 'all' ? undefined : this.data.activeTab
      const res = await api.orderList({ status })
      const list = (res.list || []).map((o) => this.enrichOrder(o))
      this.setData({ list, empty: list.length === 0, loading: false })
    } catch (e) {
      this.setData({ loading: false, empty: true })
      wx.showToast({ title: this.data.t['order.load_failed'] || 'Load failed', icon: 'none' })
    }
  },

  // 给订单附加 i18n 状态 label (status → 当前语种 label)
  enrichOrder(o) {
    const locale = app.globalData.locale
    const statusLabelMap = api.ORDER_STATUS_LABEL[o.status] || {}
    return {
      ...o,
      statusLabel: statusLabelMap[locale] || o.status,
      amountYuan: (o.amount / 100).toFixed(2),
      // 状态色:待付款橙 / 已付款蓝 / 审核中黄 / 通过绿 / 拒签红 / 取消灰
      statusClass: this.statusClass(o.status)
    }
  },

  statusClass(s) {
    return {
      pending_payment: 'status-pending',
      paid: 'status-paid',
      reviewing: 'status-reviewing',
      approved: 'status-approved',
      rejected: 'status-rejected',
      cancelled: 'status-cancelled'
    }[s] || 'status-default'
  },

  onSwitchTab(e) {
    const k = e.currentTarget.dataset.key
    if (k === this.data.activeTab) return
    this.setData({ activeTab: k })
    this.loadList()
  },

  onPayNow(e) {
    const orderNo = e.currentTarget.dataset.no
    wx.navigateTo({ url: '/pages/payment/payment?order_no=' + orderNo })
  },

  onViewDetail(e) {
    const orderNo = e.currentTarget.dataset.no
    wx.showToast({ title: '订单详情: ' + orderNo, icon: 'none' })
  },

  onGoLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  onGoDest() {
    wx.switchTab({ url: '/pages/destinations/destinations' })
  }
})
