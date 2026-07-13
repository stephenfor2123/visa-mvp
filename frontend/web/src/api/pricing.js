/** GET /api/v2/pricing/current — resolved platform service fee */
import http from '@/api/http'

const MOCK = import.meta.env.VITE_MOCK_API === 'true'

const DEFAULT = {
  list_price_usd: 99.9,
  promo_price_usd: 19.9,
  display_price_usd: 19.9,
  currency: 'USD',
  is_promo: true,
  promo_enabled: true,
  promo_starts_at: '2026-07-15T00:00:00Z',
  promo_ends_at: '2026-08-15T23:59:59Z',
  display_price_cents: 1990,
  list_price_cents: 9990,
}

export async function getPlatformPricing() {
  if (MOCK) {
    return { ...DEFAULT }
  }
  const envelope = await http.get('/v2/pricing/current')
  if (envelope?.code && envelope.code !== '1000') {
    throw new Error(envelope.message || 'pricing fetch failed')
  }
  return envelope?.data || DEFAULT
}
