/**
 * Shared validation helpers — aligned with backend pydantic validators.
 *
 * Rule reference (backend source of truth):
 *   auth.py   — phone 6-15 digits (\d{6,15}), sms_code \d{6}, password 8-32 chars + letter + digit
 *   order.py  — aff_code 4-32 [A-Za-z0-9_-]
 *
 * These functions return an empty string when valid, or an i18n key when invalid.
 * The component passes the key through t() to show the localised error message.
 */

/** Phone: 6–15 digits, no country code (country code is a separate field). */
export function validatePhone(value: string): string {
  if (!value) return 'errors.phone_required'
  if (!/^\d{6,15}$/.test(value.trim())) return 'errors.phone_invalid'
  return ''
}

/** Emergency contact phone: 6–15 digits (with optional leading + stripped server-side). */
export function validateEmergencyPhone(value: string): string {
  if (!value) return 'errors.phone_required'
  const stripped = value.replace(/^\+/, '').replace(/\s/g, '')
  if (!/^\d{6,15}$/.test(stripped)) return 'errors.phone_invalid'
  return ''
}

/** Account (login field): accept email or username, length 3-120. */
export function validateAccount(value: string): string {
  if (!value || !value.trim()) return 'errors.account_required'
  const v = value.trim()
  if (v.length < 3) return 'errors.account_too_short'
  if (v.length > 120) return 'errors.account_too_long'
  // 至少是 email 或 username 之一
  const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
  const isUsername = /^[A-Za-z0-9_.-]{3,32}$/.test(v)
  if (!isEmail && !isUsername) return 'errors.account_invalid'
  return ''
}

/** Username (register): 3-32 chars, [A-Za-z0-9_.-], must start with letter/digit. */
export function validateUsername(value: string): string {
  if (!value || !value.trim()) return 'errors.username_required'
  const v = value.trim()
  if (v.length < 3) return 'errors.username_too_short'
  if (v.length > 32) return 'errors.username_too_long'
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$/.test(v)) return 'errors.username_format'
  return ''
}

/** Email (register): standard email format, max 120 chars. */
export function validateEmail(value: string): string {
  if (!value || !value.trim()) return 'errors.email_required'
  const v = value.trim()
  if (v.length > 120) return 'errors.email_too_long'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return 'errors.email_format'
  return ''
}

/**
 * Password: 8–32 chars, must contain at least one letter AND one digit.
 * Matches backend RegisterRequest / ResetPasswordRequest complexity rule.
 */
export function validatePassword(value: string): string {
  if (!value) return 'errors.pwd_required'
  if (value.length < 8) return 'errors.pwd_too_short'
  if (value.length > 32) return 'errors.pwd_too_long'
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) return 'errors.pwd_format'
  return ''
}

/** Confirm password: must match original. */
export function validateConfirmPassword(value: string, original: string): string {
  if (!value) return 'errors.pwd_required'
  if (value !== original) return 'errors.pwd_mismatch'
  return ''
}

/** Passport number (CN format): 1 uppercase letter + 8 digits. */
export function validatePassportCN(value: string): string {
  if (!value) return 'errors.passport_required'
  if (!/^[A-Z][0-9]{8}$/.test(value.trim().toUpperCase())) return 'errors.passport_format'
  return ''
}

/** Affiliate code: 4–32 chars [A-Za-z0-9_-]. */
export function validateAffCode(value: string): string {
  if (!value) return '' // optional field
  if (!/^[A-Za-z0-9_-]{4,32}$/.test(value.trim())) return 'affiliate.err_format'
  return ''
}

/** Generic required field. */
export function validateRequired(value: unknown, key = 'errors.required'): string {
  if (!value || (typeof value === 'string' && !value.trim())) return key
  return ''
}