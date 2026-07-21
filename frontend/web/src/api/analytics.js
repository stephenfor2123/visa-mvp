/**
 * Product analytics — fire-and-forget client 埋点.
 * Mirrors affiliate trackClick: never blocks UX, silent on failure.
 */
import http from './http'

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

function mintSessionId() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
  } catch (_) { /* ignore */ }
  return `s_${Date.now()}_${Math.floor(Math.random() * 1e6)}`
}

export function getSessionId() {
  try {
    let id = localStorage.getItem(SESSION_KEY)
    if (!id) {
      id = mintSessionId()
      localStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch (_) {
    return mintSessionId()
  }
}

export function setEntrySource(source) {
  if (!source) return
  try {
    localStorage.setItem(ENTRY_KEY, String(source).slice(0, 64))
  } catch (_) { /* ignore */ }
}

export function getEntrySource() {
  try {
    return localStorage.getItem(ENTRY_KEY) || null
  } catch (_) {
    return null
  }
}

/**
 * Track a product event. Never throws; returns null on failure.
 * @param {string} event
 * @param {Record<string, any>} [props]
 */
export async function track(event, props = {}) {
  if (!event) return null
  // Allow callers that already assembled the API body (utils/analytics).
  const body = typeof event === 'object' && event?.event
    ? {
        ...event,
        session_id: event.session_id || getSessionId(),
        path: event.path || (typeof window !== 'undefined' ? window.location?.pathname : undefined),
        props: {
          entry_source: getEntrySource(),
          ...(event.props || {}),
        },
      }
    : {
        event,
        session_id: getSessionId(),
        country_code: props.country_code || props.countryCode || undefined,
        order_no: props.order_no || props.orderNo || undefined,
        path: props.path || (typeof window !== 'undefined' ? window.location?.pathname : undefined),
        props: {
          entry_source: getEntrySource(),
          ...props,
        },
      }
  try {
    const resp = await http.post('/v2/analytics/track', body, { __silent: true })
    if (resp?.code && resp.code !== '1000') return null
    return resp?.data || resp
  } catch (_) {
    return null
  }
}

/** Alias used by `@/utils/analytics`. */
export const trackEvent = track

export default track
