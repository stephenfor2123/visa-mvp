/**
 * src/__tests__/PaymentResult.test.ts
 * Unit tests for PaymentResult.vue view.
 *
 * Coverage: renders 4 states (success/failed/pending/cancelled),
 *           order summary card, network error handling, not-found state.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import PaymentResult from '@/views/PaymentResult.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hydrate: vi.fn(),
    logout: vi.fn()
  })
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() })
}))

const mockQueryStatus = vi.fn()
const mockCancel = vi.fn()
const mockRetry = vi.fn()
vi.mock('@/api/payment', () => ({
  queryPaymentStatus: (...args: unknown[]) => mockQueryStatus(...args),
  cancelPayment: (...args: unknown[]) => mockCancel(...args),
  retryPayment: (...args: unknown[]) => mockRetry(...args)
}))

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      common: { app_name: 'Visa', cancel: 'Cancel', loading: 'Loading' },
      orderdetail: { logout_btn: 'Logout' },
      payment: {
        loading_state: 'Loading...', not_found_title: 'Order not found',
        not_found_message: 'Order not found', back_to_orders: 'Back to orders',
        retry_load: 'Retry', pending_title: 'Payment pending', pending_message: 'Waiting...',
        pending_wait_hint: 'Please wait', pending_refresh_now: 'Refresh now',
        pending_polling_label: 'Next refresh in {sec}s',
        icon_pending: '⏳', icon_success: '✓', icon_failed: '✗', icon_cancelled: '—',
        success_title: 'Payment successful', success_message: 'Your payment is confirmed',
        success_next: 'View order', estimated_processing: 'Est. {hours}h',
        failed_title: 'Payment failed', failed_reason_unknown: 'Unknown error',
        retry_button: 'Retry', cancelled_title: 'Payment cancelled',
        cancelled_message: 'Payment was cancelled', cancelled_continue_button: 'Continue',
        order_id: 'Order ID', amount: 'Amount', method: 'Method', transaction_id: 'Txn ID',
        load_failed: 'Failed to load payment'
      }
    }
  }
})

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/payment/result' },
    { path: '/home', component: { template: '<div />' } },
    { path: '/payment/result', component: PaymentResult },
    { path: '/orders', component: { template: '<div />' } },
    { path: '/orders/:id', component: { template: '<div />' } },
    { path: '/login', component: { template: '<div />' } }
  ]
})

// AppButton stub that exposes setOnTrigger for PaymentResult.injectTriggers()
const makeAppButtonStub = () => ({
  template: '<button class="stub-btn"><slot /></button>',
  methods: {
    setOnTrigger() {},
    trigger() {}
  }
})

const mountPaymentResult = async (query: Record<string, string> = {}) => {
  // Push query params onto router so PaymentResult's route.query.orderId resolves
  if (Object.keys(query).length > 0) {
    await router.push({ path: '/payment/result', query })
  } else {
    await router.push('/payment/result')
  }
  return mount(PaymentResult, {
    global: {
      plugins: [router, i18n],
      stubs: {
        AppButton: makeAppButtonStub(),
        LangSwitch: { template: '<span class="stub-lang" />' }
      },
      config: { warnHandler: () => {} }
    }
  })
}

describe('PaymentResult', () => {
  beforeEach(() => {
    router.push('/payment/result')
    mockQueryStatus.mockReset()
    mockCancel.mockReset()
    mockRetry.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('not-found state', () => {
    it('shows not-found block when no orderId is provided', async () => {
      mockQueryStatus.mockResolvedValue({ data: null })
      const wrapper = await mountPaymentResult({})
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-not-found"]').exists()).toBe(true)
    })
  })

  describe('success state', () => {
    it('shows success status card when payment status=success', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD001', status: 'success', amount_cents: 9900,
          currency: 'USD', estimated_processing_hours: 24, method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD001' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-status-success"]').exists()).toBe(true)
    })

    it('shows estimated processing hours in success state', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD001', status: 'success', amount_cents: 9900,
          currency: 'USD', estimated_processing_hours: 24, method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD001' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-eta"]').exists()).toBe(true)
    })
  })

  describe('failed state', () => {
    it('shows failed status card when payment status=failed', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD002', status: 'failed', reason: 'insufficient_balance',
          amount_cents: 9900, currency: 'USD', method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD002' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-status-failed"]').exists()).toBe(true)
    })
  })

  describe('pending state', () => {
    it('shows pending status card when payment status=pending', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD003', status: 'pending', amount_cents: 9900,
          currency: 'USD', method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD003' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-status-pending"]').exists()).toBe(true)
    })

    it('shows countdown polling label in pending state', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD003', status: 'pending', amount_cents: 9900,
          currency: 'USD', method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD003' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-polling-label"]').exists()).toBe(true)
    })
  })

  describe('cancelled state', () => {
    it('shows cancelled status card when payment status=cancelled', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD004', status: 'cancelled', amount_cents: 9900,
          currency: 'USD', method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD004' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-status-cancelled"]').exists()).toBe(true)
    })
  })

  describe('order summary', () => {
    it('shows summary card with order id when payment exists', async () => {
      mockQueryStatus.mockResolvedValue({
        data: {
          order_id: 'ORD001', status: 'success', amount_cents: 9900,
          currency: 'USD', method: 'card'
        }
      })
      const wrapper = await mountPaymentResult({ orderId: 'ORD001' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-summary"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="paymentresult-order-id"]').text()).toBe('ORD001')
    })
  })

  describe('network error handling', () => {
    it('shows error block when API throws', async () => {
      mockQueryStatus.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountPaymentResult({ orderId: 'ORD005' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-error"]').exists()).toBe(true)
    })

    it('shows retry load button on API error', async () => {
      mockQueryStatus.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountPaymentResult({ orderId: 'ORD005' })
      await flushPromises()
      await nextTick()
      expect(wrapper.find('[data-testid="paymentresult-retry-load"]').exists()).toBe(true)
    })
  })
})