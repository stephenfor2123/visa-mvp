/**
 * Product feature flags.
 *
 * Customer market: Vietnam + Indonesia (overseas Web).
 * Visa destinations: US / Schengen / GB / AU — NOT limited here.
 *
 * Override via frontend/web/.env:
 *   VITE_FEATURE_RPA=false
 *   VITE_FEATURE_INSURANCE=false
 */

export const FEATURE_RPA = import.meta.env.VITE_FEATURE_RPA === 'true'
export const FEATURE_INSURANCE = import.meta.env.VITE_FEATURE_INSURANCE === 'true'

export function postPaymentRoute(orderNo) {
  return { name: 'OrderPrecheck', params: { orderNo } }
}
