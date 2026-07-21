/** Shared sensitive-upload consent (Art.7) — local flag + server sync. */
import { grantConsent } from '@/api/profile'

export const SENSITIVE_CONSENT_KEY = 'htex.sensitive_data_consent_v1'

export function hasLocalSensitiveConsent() {
  try {
    return sessionStorage.getItem(SENSITIVE_CONSENT_KEY) === '1'
  } catch {
    return false
  }
}

export function markLocalSensitiveConsent() {
  try {
    sessionStorage.setItem(SENSITIVE_CONSENT_KEY, '1')
  } catch { /* ignore */ }
}

export function clearLocalSensitiveConsent() {
  try {
    sessionStorage.removeItem(SENSITIVE_CONSENT_KEY)
  } catch { /* ignore */ }
}

/** Persist Art.7 consent server-side when the user already accepted locally. */
export async function syncSensitiveConsentToServer() {
  if (!hasLocalSensitiveConsent()) return false
  try {
    await grantConsent({ purpose: 'sensitive_upload' })
    return true
  } catch {
    return false
  }
}
