/**
 * Product analytics (埋点) — thin client wrapper.
 *
 * Usage:
 *   import { track, Events } from '@/utils/analytics'
 *   track(Events.COUNTRY_SELECTED, { country_code: 'US', entry_source: 'home' })
 *
 * Never throws. Queues while offline / before session ready.
 */

import { trackEvent } from '@/api/analytics'
import { useAuthStore } from '@/stores/auth'

export const Events = Object.freeze({
  PAGE_VIEW: 'page_view',
  COUNTRY_SELECTED: 'country_selected',
  WIZARD_STARTED: 'wizard_started',
  FORM_COMPLETED: 'form_completed',
  LOGIN_WALL_SHOWN: 'login_wall_shown',
  AUTH_SUCCEEDED: 'auth_succeeded',
  ORDER_CREATED: 'order_created',
  CHECKOUT_VIEWED: 'checkout_viewed',
  CHECKOUT_STARTED: 'checkout_started',
  PAYMENT_SUCCEEDED: 'payment_succeeded',
  PAYMENT_FAILED: 'payment_failed',
  ORDER_DETAIL_VIEWED: 'order_detail_viewed',
})

const SESSION_KEY = 'visa.analytics.session_id'
const ENTRY_KEY = 'visa.analytics.entry_source'

function _uuid() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  } catch (_) { /* ignore */ }
  return `s_${Date.now()}_${Math.floor(Math.random() * 1e6)}`
}

export function getSessionId() {
  try {
    let id = sessionStorage.getItem(SESSION_KEY)
    if (!id) {
      id = _uuid()
      sessionStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch (_) {
    return _uuid()
  }
}

export function setEntrySource(source) {
  if (!source) return
  try {
    sessionStorage.setItem(ENTRY_KEY, String(source).slice(0, 64))
  } catch (_) { /* ignore */ }
}

export function getEntrySource() {
  try {
    return sessionStorage.getItem(ENTRY_KEY) || undefined
  } catch (_) {
    return undefined
  }
}

/**
 * Fire a product event. Safe to call from anywhere.
 * @param {string} event
 * @param {Record<string, any>} [props]
 */
export function track(event, props = {}) {
  if (!event) return
  const payload = { ...(props || {}) }
  if (!payload.entry_source) {
    const entry = getEntrySource()
    if (entry) payload.entry_source = entry
  }

  let userId
  try {
    const auth = useAuthStore()
    auth.hydrate?.()
    userId = auth.user?.id
  } catch (_) { /* pinia not ready */ }

  if (userId != null) payload.user_id = userId

  const body = {
    event,
    session_id: getSessionId(),
    country_code: payload.country_code,
    order_no: payload.order_no,
    path: payload.path || (typeof window !== 'undefined' ? window.location?.pathname : undefined),
    props: payload,
  }

  // Fire-and-forget
  Promise.resolve(trackEvent(body)).catch(() => {})
}
