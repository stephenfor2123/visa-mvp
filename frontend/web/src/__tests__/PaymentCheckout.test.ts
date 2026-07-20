/**
 * PaymentCheckout.vue — smoke: benefits table + consent gate
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import PaymentCheckout from '@/views/PaymentCheckout.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ hydrate: vi.fn() }),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/composables/usePlatformPricing', () => ({
  usePlatformPricing: () => ({
    listPrice: { value: 99.9 },
    displayCents: { value: 1990 },
    symbol: { value: '$' },
    load: vi.fn().mockResolvedValue({}),
    formatUsd: (n: number) => (Number(n) % 1 === 0 ? Number(n).toFixed(0) : Number(n).toFixed(2)),
  }),
}))

vi.mock('@/api/orders', () => ({
  getOrder: vi.fn().mockResolvedValue({
    order_no: 'V2-20260720-TEST0001',
    total_amount: 19.9,
    currency: 'USD',
  }),
  syncPendingApplicantAfterPayment: vi.fn(),
}))

vi.mock('@/api/payment', () => ({
  getPaymentConfig: vi.fn().mockResolvedValue({ data: { channel: 'mock' } }),
  createPayment: vi.fn(),
  queryPaymentStatus: vi.fn(),
}))

vi.mock('@stripe/stripe-js', () => ({ loadStripe: vi.fn() }))

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      common: { retry: '重试', close: '关闭' },
      home: { pricing: { promo_tag: '限时' } },
      payment: {
        checkout_loading: '加载中',
        checkout_back: '返回',
        checkout_entry_template_title: '解锁正式模板',
        checkout_package_sub: '一次支付',
        checkout_price_hint: '平台服务费',
        checkout_embassy_title: '使馆费',
        checkout_embassy_body: '说明',
        checkout_consent: '同意',
        checkout_data_how: '资料',
        checkout_privacy: '隐私',
        checkout_pay_cta: '支付 {price}',
        checkout_skip: '跳过',
        checkout_foot: '{orderNo}',
        checkout_cmp_title: '对照',
        checkout_cmp_desc: '说明',
        checkout_cmp_aria: '对照表',
        checkout_legend_free: '非会员',
        checkout_legend_paid: '会员',
        checkout_col_feat: '功能',
        checkout_col_free: '非会员',
        checkout_col_paid: '会员',
        checkout_badge_recommended: '推荐',
        checkout_section_basic: '基础',
        checkout_section_paid: '付费',
        checkout_section_browser: '浏览器',
        checkout_feat_checklist: '清单',
        checkout_feat_checklist_hint: '',
        checkout_feat_ocr: 'OCR',
        checkout_feat_ocr_hint: '',
        checkout_feat_assess: '评估',
        checkout_feat_assess_hint: '',
        checkout_feat_template: '模板',
        checkout_feat_template_hint: '',
        checkout_feat_report: '报告',
        checkout_feat_report_hint: '',
        checkout_feat_issues: '问题',
        checkout_feat_issues_hint: '',
        checkout_feat_consistency: '一致',
        checkout_feat_consistency_hint: '',
        checkout_feat_rerun: '重跑',
        checkout_feat_rerun_hint: '',
        checkout_feat_fill: '填写',
        checkout_feat_fill_hint: '',
        checkout_feat_submit: '提交',
        checkout_feat_submit_hint: '',
        checkout_cell_preview: '预览',
        checkout_cell_summary: '摘要',
        checkout_cell_download: '下载',
        checkout_cell_full: '完整',
      },
    },
  },
})

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/payment/:orderNo', name: 'PaymentCheckout', component: PaymentCheckout },
  ],
})

const stubs = {
  AppHeader: { template: '<div />' },
  AppButton: {
    template: '<button :disabled="disabled"><slot /></button>',
    props: ['variant', 'size', 'loading', 'disabled'],
  },
}

describe('PaymentCheckout', () => {
  beforeEach(async () => {
    await router.push('/payment/V2-20260720-TEST0001?from=template')
    await router.isReady()
  })

  it('renders benefits table and disables pay until consent', async () => {
    const wrapper = mount(PaymentCheckout, {
      global: { plugins: [i18n, router], stubs },
    })
    await flushPromises()

    expect(wrapper.find('.benefits__table').exists()).toBe(true)
    expect(wrapper.find('[data-testid="paymentcheckout-pay"]').attributes('disabled')).toBeDefined()

    await wrapper.find('[data-testid="paymentcheckout-consent"]').setValue(true)
    expect(wrapper.find('[data-testid="paymentcheckout-pay"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('$19.9')
  })
})
