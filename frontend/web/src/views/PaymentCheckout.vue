<!--
  PaymentCheckout.vue — 完整申请服务包支付页
  展示非会员/会员权益对照 + 平台定价 + 隐私同意 → Mock 轮询 / Stripe Elements
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
        <AppButton variant="outline" size="md" @click="prepareCheckout">{{ t('common.retry') }}</AppButton>
      </section>

      <template v-else>
        <button type="button" class="checkout-back" @click="goBack">{{ t('payment.checkout_back') }}</button>

        <header class="checkout-header">
          <h1>{{ pageTitle }}</h1>
          <p class="checkout-sub" v-html="t('payment.checkout_package_sub')"></p>
        </header>

        <PaymentBenefitsCompare />

        <div class="price-bar">
          <span v-if="showStrike" class="price-list">{{ symbol }}{{ formatUsd(listPrice) }}</span>
          <span class="price-now">{{ symbol }}{{ formatUsd(chargeUsd) }}</span>
          <span v-if="showStrike" class="price-tag">{{ t('home.pricing.promo_tag') }}</span>
        </div>
        <p class="price-hint">{{ t('payment.checkout_price_hint') }}</p>

        <div class="note note--embassy">
          <p>
            <strong>{{ t('payment.checkout_embassy_title') }}</strong>
            {{ t('payment.checkout_embassy_body') }}
          </p>
        </div>

        <label class="consent">
          <input v-model="consentChecked" type="checkbox" data-testid="paymentcheckout-consent" />
          <span>{{ t('payment.checkout_consent') }}</span>
        </label>
        <div class="consent-links">
          <button type="button" class="link-btn" @click="dataModalOpen = true">{{ t('payment.checkout_data_how') }}</button>
          <span>·</span>
          <router-link to="/privacy" target="_blank">{{ t('payment.checkout_privacy') }}</router-link>
        </div>

        <div v-if="channel === 'stripe' && paymentStarted && clientSecret" class="stripe-wrap">
          <div ref="stripeMountRef" class="stripe-element" data-testid="paymentcheckout-stripe-element"></div>
          <p v-if="stripeError" class="stripe-error">{{ stripeError }}</p>
        </div>

        <div v-if="paying && channel !== 'stripe'" class="mock-wrap">
          <p class="mock-hint">{{ t('payment.checkout_mock_hint') }}</p>
          <div class="polling-bar" aria-hidden="true">
            <span class="polling-dot"></span>
            <span class="polling-dot"></span>
            <span class="polling-dot"></span>
          </div>
        </div>

        <AppButton
          v-if="channel !== 'stripe' || !paymentStarted"
          variant="primary"
          size="lg"
          style="width: 100%;"
          :loading="paying"
          :disabled="!consentChecked || paying"
          data-testid="paymentcheckout-pay"
          @click="onPayClick"
        >{{ payButtonLabel }}</AppButton>

        <AppButton
          v-else
          variant="primary"
          size="lg"
          style="width: 100%; margin-top: 16px;"
          :loading="paying"
          :disabled="!consentChecked || paying"
          data-testid="paymentcheckout-stripe-pay"
          @click="onStripePay"
        >{{ t('payment.checkout_pay_now') }}</AppButton>

        <button type="button" class="btn-cancel" @click="goBack">{{ t('payment.checkout_skip') }}</button>
        <p class="checkout-foot">{{ t('payment.checkout_foot', { orderNo }) }}</p>
      </template>
    </main>

    <div v-if="dataModalOpen" class="modal-mask" @click.self="dataModalOpen = false">
      <div class="modal" role="dialog" aria-modal="true" :aria-label="t('payment.checkout_data_modal_title')">
        <h3>{{ t('payment.checkout_data_modal_title') }}</h3>
        <p>{{ t('payment.checkout_data_modal_p1') }}</p>
        <p>{{ t('payment.checkout_data_modal_p2') }}</p>
        <p>{{ t('payment.checkout_data_modal_p3') }}</p>
        <AppButton variant="outline" size="md" @click="dataModalOpen = false">{{ t('common.close') }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { loadStripe } from '@stripe/stripe-js'
import AppHeader from '@/components/AppHeader.vue'
import AppButton from '@/components/AppButton.vue'
import PaymentBenefitsCompare from '@/components/PaymentBenefitsCompare.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { usePlatformPricing } from '@/composables/usePlatformPricing'
import { getOrder, syncPendingApplicantAfterPayment } from '@/api/orders'
import { createPayment, getPaymentConfig, queryPaymentStatus } from '@/api/payment'
import { FEATURE_RPA, postPaymentRoute } from '@/config/features'
import { track, Events } from '@/api/analytics'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()
const {
  listPrice,
  displayCents,
  symbol,
  load: loadPricing,
  formatUsd,
} = usePlatformPricing()

const orderNo = computed(() => route.params.orderNo || route.query.orderNo || '')
const nextRoute = computed(() => route.query.next || '')
const entryFrom = computed(() => {
  const raw = String(route.query.from || '').toLowerCase()
  return raw === 'diagnosis' ? 'diagnosis' : 'template'
})

const pageTitle = computed(() => (
  entryFrom.value === 'diagnosis'
    ? t('payment.checkout_entry_diagnosis_title')
    : t('payment.checkout_entry_template_title')
))

const payButtonLabel = computed(() => (
  t('payment.checkout_pay_cta', { price: `${symbol.value}${formatUsd(chargeUsd.value)}` })
))

const chargeUsd = ref(0)
const showStrike = computed(() => {
  const list = Number(listPrice.value)
  return list > 0 && chargeUsd.value > 0 && chargeUsd.value < list
})

const loading = ref(true)
const loadError = ref('')
const paying = ref(false)
const paymentStarted = ref(false)
const consentChecked = ref(false)
const dataModalOpen = ref(false)
const channel = ref('mock')
const amountCents = ref(0)
const currency = ref('USD')
const clientSecret = ref('')
const stripeError = ref('')
const stripeMountRef = ref(null)
let stripeInstance = null
let stripeElements = null
let pollTimer = null
let stripePublishableKey = ''

function goBack() {
  router.back()
}

async function goNext() {
  try {
    await syncPendingApplicantAfterPayment(orderNo.value)
  } catch (e) {
    console.warn('[payment] sync applicant_data failed', e)
  }
  const q = { orderId: orderNo.value }
  if (nextRoute.value === 'employment-export') {
    const { countryCode, visaType } = route.query
    router.push({
      name: 'MaterialWizard',
      query: {
        country: countryCode,
        visa_type: visaType || 'tourism',
        intent: 'export_employment',
        orderNo: orderNo.value,
      },
    }).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  if (!FEATURE_RPA || nextRoute.value === 'detail') {
    const dest = postPaymentRoute(orderNo.value)
    router.push(dest).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  if (nextRoute.value === 'rpa') {
    const { countryCode, visaType } = route.query
    router.push({
      name: 'RpaSubmit',
      query: { orderNo: orderNo.value, countryCode, visaType },
    }).catch(() => router.push({ name: 'PaymentResult', query: q }))
    return
  }
  if (nextRoute.value === 'precheck') {
    router.push({
      name: 'OrderPrecheck',
      params: { orderNo: orderNo.value },
      query: route.query,
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
  try {
    const first = await queryPaymentStatus(orderNo.value)
    const st0 = first?.data?.status
    if (st0 === 'paid' || st0 === 'success') return true
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

async function mountStripe() {
  if (!stripePublishableKey || !clientSecret.value || !stripeMountRef.value) return
  stripeInstance = await loadStripe(stripePublishableKey)
  if (!stripeInstance) {
    stripeError.value = t('payment.checkout_stripe_load_fail')
    return
  }
  stripeElements = stripeInstance.elements({ clientSecret: clientSecret.value })
  const paymentElement = stripeElements.create('payment')
  paymentElement.mount(stripeMountRef.value)
}

async function createCheckoutPayment() {
  const payResp = await createPayment({
    order_no: orderNo.value,
    amount_cents: amountCents.value,
    currency: currency.value,
    desc: `Visa order ${orderNo.value}`,
  })
  const data = payResp?.data || {}
  clientSecret.value = data.client_secret || data.prepay_id || ''
  if (data.provider) channel.value = data.provider
  paymentStarted.value = true
  if (channel.value === 'stripe' && clientSecret.value) {
    await nextTick()
    await mountStripe()
  }
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
      redirect: 'if_required',
    })
    if (error) {
      stripeError.value = error.message || t('payment.failed_reason_unknown')
      return
    }
    const paid = await pollUntilPaid()
    if (!paid) {
      stripeError.value = t('payment.pending_message')
      return
    }
    toast.success(t('payment.success_title'))
    goNext()
  } catch (e) {
    stripeError.value = e?.message || t('payment.failed_reason_unknown')
  } finally {
    paying.value = false
  }
}

async function onPayClick() {
  if (!consentChecked.value || paying.value) return
  track(Events.CHECKOUT_STARTED, {
    order_no: orderNo.value,
    country_code: route.query.countryCode?.toString() || undefined,
    visa_type: route.query.visaType?.toString() || undefined,
    channel: channel.value,
  })
  paying.value = true
  stripeError.value = ''
  try {
    if (!paymentStarted.value) {
      await createCheckoutPayment()
    }
    if (channel.value === 'stripe') {
      paying.value = false
      return
    }
    const paid = await pollUntilPaid()
    if (paid) {
      toast.success(t('payment.success_title'))
      goNext()
    } else {
      toast.error(t('payment.pending_message'))
    }
  } catch (e) {
    loadError.value = e?.message || t('payment.load_failed')
  } finally {
    paying.value = false
  }
}

async function prepareCheckout() {
  if (!orderNo.value) {
    loadError.value = t('payment.not_found_message', { orderId: '—' })
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const order = await getOrder(orderNo.value)
    const countryCode = order?.country_code || route.query.countryCode?.toString() || undefined
    const visaType = order?.visa_type || route.query.visaType?.toString() || undefined
    const [configResp] = await Promise.all([
      getPaymentConfig(),
      loadPricing({ country_code: countryCode, visa_type: visaType, force: true }),
    ])
    channel.value = configResp?.data?.channel || 'mock'
    stripePublishableKey = configResp?.data?.stripe_publishable_key
      || import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY
      || ''

    const orderCents = Math.round(Number(order?.total_amount || 0) * 100)
    amountCents.value = orderCents > 0 ? orderCents : displayCents.value
    chargeUsd.value = amountCents.value / 100
    currency.value = order?.currency || 'USD'
  } catch (e) {
    loadError.value = e?.message || t('payment.load_failed')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  auth.hydrate()
  track(Events.CHECKOUT_VIEWED, {
    order_no: orderNo.value,
    country_code: route.query.countryCode?.toString() || undefined,
    visa_type: route.query.visaType?.toString() || undefined,
  })
  await prepareCheckout()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped lang="scss">
.paymentcheckout-page { min-height: 100vh; background: #fff; }
.paymentcheckout-shell { max-width: 600px; margin: 0 auto; padding: 28px 20px 64px; }

.checkout-back {
  border: 0;
  background: none;
  padding: 0;
  font-size: 13px;
  color: #3b6ef5;
  font-weight: 600;
  cursor: pointer;
}
.checkout-back:hover { text-decoration: underline; }

.checkout-header {
  margin: 16px 0;
  h1 { font-size: 22px; margin: 0 0 6px; color: #0f172a; font-weight: 700; }
}
.checkout-sub {
  color: #64748b;
  margin: 0;
  font-size: 14px;
  :deep(strong) { color: #0f172a; }
}

.price-bar {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 8px;
}
.price-list {
  color: #94a3b8;
  text-decoration: line-through;
  font-size: 16px;
  font-weight: 600;
}
.price-now {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
}
.price-tag {
  font-size: 11px;
  font-weight: 700;
  color: #1d4ed8;
  background: #eaf0fe;
  padding: 2px 8px;
  border-radius: 4px;
}
.price-hint { margin: 0 0 16px; font-size: 13px; color: #64748b; }

.note--embassy {
  margin: 0 0 12px;
  padding: 14px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  color: #78350f;
  p { margin: 0; line-height: 1.55; }
  strong { color: #92400e; }
}

.consent {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 16px 0;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
  input {
    margin-top: 2px;
    width: 16px;
    height: 16px;
    accent-color: #3b6ef5;
    flex-shrink: 0;
  }
}
.consent-links {
  margin: -8px 0 16px;
  font-size: 13px;
  a, .link-btn {
    color: #3b6ef5;
    font-weight: 600;
    background: none;
    border: 0;
    padding: 0;
    font: inherit;
    cursor: pointer;
    text-decoration: none;
  }
  a:hover, .link-btn:hover { text-decoration: underline; }
  span { color: #cbd5e1; margin: 0 8px; }
}

.stripe-wrap { margin-bottom: 16px; }
.stripe-element {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}
.stripe-error { color: #dc2626; font-size: 0.9rem; margin-top: 8px; }

.mock-wrap { text-align: center; padding: 16px 0; }
.mock-hint { color: #64748b; margin-bottom: 12px; }
.polling-bar { display: flex; gap: 8px; justify-content: center; }
.polling-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #3b6ef5;
  animation: pulse 1.2s ease-in-out infinite;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.btn-cancel {
  display: block;
  width: 100%;
  margin-top: 10px;
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  padding: 10px;
  cursor: pointer;
}
.checkout-foot {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 30;
}
.modal {
  background: #fff;
  border-radius: 12px;
  max-width: 440px;
  width: 100%;
  max-height: 80vh;
  overflow: auto;
  padding: 20px;
  h3 { margin: 0 0 12px; font-size: 16px; }
  p { margin: 0 0 10px; font-size: 13px; color: #475569; }
}

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
