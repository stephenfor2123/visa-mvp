<!--
  PaymentCheckout.vue — Web 支付/checkout 页
  Mock: 创建支付单后 1s 自动回调 → 轮询跳转结果页
  Stripe: Stripe.js Elements 收集卡号 → confirmPayment → 轮询/跳转
-->
<template>
  <div class="paymentcheckout-page">
    <AppHeader scope="payment-checkout" />
    <main class="app-container app-page paymentcheckout-shell">
      <div v-if="loading" class="state-block" data-testid="paymentcheckout-loading">
        <span class="spinner" aria-hidden="true"></span>
        {{ t('payment.checkout_loading') }}
      </div>

      <section v-else-if="loadError" class="state-block state-block--err">
        <p>{{ loadError }}</p>
        <AppButton variant="outline" size="md" @click="initCheckout">{{ t('common.retry') }}</AppButton>
      </section>

      <template v-else>
        <header class="checkout-header">
          <h1>{{ t('payment.checkout_title') }}</h1>
          <p class="checkout-sub">{{ t('payment.checkout_subtitle') }}</p>
        </header>

        <div class="checkout-card">
          <div class="checkout-row">
            <span class="checkout-label">{{ t('payment.order_id') }}</span>
            <span class="checkout-value mono">{{ orderNo }}</span>
          </div>
          <div class="checkout-row">
            <span class="checkout-label">{{ t('payment.amount') }}</span>
            <span class="checkout-value amount">{{ formattedAmount }}</span>
          </div>
          <div class="checkout-row">
            <span class="checkout-label">{{ t('payment.method') }}</span>
            <span class="checkout-value">
              {{ channel === 'stripe' ? t('payment.method_stripe') : t('payment.method_mock') }}
            </span>
          </div>
        </div>

        <!-- Stripe card form -->
        <div v-if="channel === 'stripe' && clientSecret" class="stripe-wrap">
          <div ref="stripeMountRef" class="stripe-element" data-testid="paymentcheckout-stripe-element"></div>
          <p v-if="stripeError" class="stripe-error">{{ stripeError }}</p>
          <AppButton
            variant="primary"
            size="lg"
            style="width: 100%; margin-top: 16px;"
            :loading="paying"
            data-testid="paymentcheckout-stripe-pay"
            @click="onStripePay"
          >{{ t('payment.checkout_pay_now') }}</AppButton>
        </div>

        <!-- Mock: waiting for auto-notify -->
        <div v-else class="mock-wrap">
          <p class="mock-hint">{{ t('payment.checkout_mock_hint') }}</p>
          <div class="polling-bar">
            <span class="polling-dot"></span>
            <span class="polling-dot"></span>
            <span class="polling-dot"></span>
          </div>
        </div>

        <div class="checkout-actions">
          <AppButton variant="ghost" size="md" @click="goBack">{{ t('common.cancel') }}</AppButton>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { loadStripe } from '@stripe/stripe-js'
import AppHeader from '@/components/AppHeader.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { getOrder } from '@/api/orders'
import { createPayment, getPaymentConfig, queryPaymentStatus } from '@/api/payment'
import { FEATURE_RPA, postPaymentRoute } from '@/config/features'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const orderNo = computed(() => route.params.orderNo || route.query.orderNo || '')
const nextRoute = computed(() => route.query.next || '')

const loading = ref(true)
const loadError = ref('')
const paying = ref(false)
const channel = ref('mock')
const amountCents = ref(0)
const currency = ref('USD')
const clientSecret = ref('')
const stripeError = ref('')
const stripeMountRef = ref(null)
let stripeInstance = null
let stripeElements = null
let pollTimer = null

const formattedAmount = computed(() => {
  const cents = amountCents.value || 0
  const cur = (currency.value || 'USD').toUpperCase()
  const val = (cents / 100).toFixed(2)
  const symbols = { USD: '$', CNY: '¥', EUR: '€' }
  return `${symbols[cur] || cur + ' '}${val}`
})

function goBack() {
  router.back()
}

function goNext() {
  const q = { orderId: orderNo.value }
  if (!FEATURE_RPA || nextRoute.value === 'detail') {
    const dest = postPaymentRoute(orderNo.value)
    router.push(dest).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  if (nextRoute.value === 'rpa') {
    const { countryCode, visaType } = route.query
    router.push({
      name: 'RpaSubmit',
      query: { orderNo: orderNo.value, countryCode, visaType }
    }).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  if (nextRoute.value === 'precheck') {
    router.push({
      name: 'OrderPrecheck',
      params: { orderNo: orderNo.value },
      query: route.query
    }).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  router.push({ name: 'PaymentResult', query: { ...q, status: 'success' } })
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollUntilPaid() {
  stopPolling()
  // Immediate sync attempt (Stripe may already show succeeded)
  try {
    const first = await queryPaymentStatus(orderNo.value)
    const st0 = first?.data?.status
    if (st0 === 'paid' || st0 === 'success') {
      return true
    }
  } catch (_) { /* keep polling */ }

  return await new Promise((resolve) => {
    let ticks = 0
    pollTimer = setInterval(async () => {
      ticks += 1
      try {
        const resp = await queryPaymentStatus(orderNo.value)
        const st = resp?.data?.status
        if (st === 'paid' || st === 'success') {
          stopPolling()
          resolve(true)
          return
        }
      } catch (_) { /* keep polling */ }
      if (ticks >= 20) {
        stopPolling()
        resolve(false)
      }
    }, 1500)
  })
}

async function mountStripe(publishableKey) {
  if (!publishableKey || !clientSecret.value || !stripeMountRef.value) return
  stripeInstance = await loadStripe(publishableKey)
  if (!stripeInstance) {
    stripeError.value = t('payment.checkout_stripe_load_fail')
    return
  }
  stripeElements = stripeInstance.elements({ clientSecret: clientSecret.value })
  const paymentElement = stripeElements.create('payment')
  paymentElement.mount(stripeMountRef.value)
}

async function onStripePay() {
  if (!stripeInstance || !stripeElements || !clientSecret.value) return
  paying.value = true
  stripeError.value = ''
  try {
    const returnUrl = `${window.location.origin}/payment/result?orderId=${encodeURIComponent(orderNo.value)}`
    const { error } = await stripeInstance.confirmPayment({
      elements: stripeElements,
      confirmParams: { return_url: returnUrl },
      redirect: 'if_required'
    })
    if (error) {
      stripeError.value = error.message || t('payment.failed_reason_unknown')
      return
    }
    // Confirm ok → poll once so backend can sync PaymentIntent → paid
    await pollUntilPaid()
    toast.success(t('payment.success_title'))
    goNext()
  } catch (e) {
    stripeError.value = e?.message || t('payment.failed_reason_unknown')
  } finally {
    paying.value = false
  }
}

async function initCheckout() {
  if (!orderNo.value) {
    loadError.value = t('payment.not_found_message', { orderId: '—' })
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const [configResp, order] = await Promise.all([
      getPaymentConfig(),
      getOrder(orderNo.value)
    ])
    channel.value = configResp?.data?.channel || 'mock'
    const total = Number(order?.total_amount || 0)
    amountCents.value = total > 0 ? Math.round(total) : 9900
    currency.value = order?.currency || 'USD'

    const payResp = await createPayment({
      order_no: orderNo.value,
      amount_cents: amountCents.value,
      currency: currency.value,
      desc: `Visa order ${orderNo.value}`
    })
    const data = payResp?.data || {}
    clientSecret.value = data.client_secret || data.prepay_id || ''
    if (data.provider) channel.value = data.provider

    loading.value = false
    if (channel.value === 'stripe' && clientSecret.value) {
      const pk = configResp?.data?.stripe_publishable_key
        || import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY
      await mountStripe(pk)
    } else {
      const paid = await pollUntilPaid()
      if (paid) {
        toast.success(t('payment.success_title'))
        goNext()
      }
    }
  } catch (e) {
    loadError.value = e?.message || t('payment.load_failed')
    loading.value = false
  }
}

onMounted(async () => {
  auth.hydrate()
  await initCheckout()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped lang="scss">
.paymentcheckout-page { min-height: 100vh; background: #fff; }
.paymentcheckout-shell { max-width: 560px; margin: 0 auto; padding: 28px 20px 60px; }

.checkout-header {
  margin-bottom: 20px;
  h1 { font-size: 1.5rem; margin: 0 0 6px; color: #0f172a; }
}
.checkout-sub { color: #64748b; margin: 0; font-size: 0.95rem; }

.checkout-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 20px;
  background: #f8fafc;
}
.checkout-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  &:not(:last-child) { border-bottom: 1px dashed #e2e8f0; }
}
.checkout-label { color: #64748b; font-size: 0.9rem; }
.checkout-value { font-weight: 600; color: #0f172a; }
.checkout-value.mono { font-family: ui-monospace, monospace; font-size: 0.85rem; }
.checkout-value.amount { font-size: 1.25rem; color: #16a34a; }

.stripe-wrap { margin-bottom: 16px; }
.stripe-element {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}
.stripe-error { color: #dc2626; font-size: 0.9rem; margin-top: 8px; }

.mock-wrap { text-align: center; padding: 24px 0; }
.mock-hint { color: #64748b; margin-bottom: 16px; }

.polling-bar { display: flex; gap: 8px; justify-content: center; }
.polling-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #d97706;
  animation: pulse 1.2s ease-in-out infinite;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.checkout-actions { margin-top: 20px; text-align: center; }

.state-block {
  text-align: center;
  padding: 48px 20px;
  color: #64748b;
}
.state-block--err { color: #dc2626; }
.spinner {
  display: inline-block;
  width: 18px; height: 18px;
  border: 2px solid #e2e8f0;
  border-top-color: #0f172a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
