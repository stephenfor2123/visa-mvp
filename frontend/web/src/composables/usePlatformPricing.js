import { ref, computed } from 'vue'
import { getPlatformPricing } from '@/api/pricing'

const cached = ref(null)
const loading = ref(false)
const error = ref('')

export function usePlatformPricing() {
  const pricing = computed(() => cached.value || {
    list_price_usd: 99.9,
    promo_price_usd: 19.9,
    display_price_usd: 19.9,
    currency: 'USD',
    is_promo: false,
    display_price_cents: 1990,
    list_price_cents: 9990,
  })

  const isPromo = computed(() => Boolean(pricing.value.is_promo))
  const displayPrice = computed(() => Number(pricing.value.display_price_usd))
  const listPrice = computed(() => Number(pricing.value.list_price_usd))
  const displayCents = computed(() => pricing.value.display_price_cents || Math.round(displayPrice.value * 100))
  const currency = computed(() => pricing.value.currency || 'USD')
  const symbol = computed(() => (currency.value === 'USD' ? '$' : currency.value + ' '))

  async function load(force = false) {
    if (cached.value && !force) return cached.value
    loading.value = true
    error.value = ''
    try {
      cached.value = await getPlatformPricing()
      return cached.value
    } catch (e) {
      error.value = e?.message || String(e)
      return pricing.value
    } finally {
      loading.value = false
    }
  }

  function formatUsd(n) {
    const v = Number(n)
    if (Number.isNaN(v)) return '—'
    return v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)
  }

  return {
    pricing,
    isPromo,
    displayPrice,
    listPrice,
    displayCents,
    currency,
    symbol,
    loading,
    error,
    load,
    formatUsd,
  }
}
