/**
 * Map API / XHR failures to stable error codes so UI can show plain i18n text
 * instead of raw strings like "process failed: 401".
 */

export function httpStatusToCode(status) {
  const s = Number(status)
  if (!s || s === 0) return 'NETWORK'
  if (s === 401) return 'UNAUTHORIZED'
  if (s === 403) return 'FORBIDDEN'
  if (s === 413) return 'FILE_TOO_BIG'
  if (s === 429) return 'RATE_LIMITED'
  if (s >= 500) return 'SERVER_ERROR'
  return 'REQUEST_FAILED'
}

export function createHttpError(status, message) {
  const code = httpStatusToCode(status)
  const err = new Error(message || code)
  err.status = Number(status) || 0
  err.code = code
  return err
}

/**
 * @param {unknown} e
 * @param {(key: string, fallback?: string) => string} t
 * @param {string} [ns='wizard'] i18n namespace for err_* keys
 */
export function resolveApiErrorMessage(e, t, ns = 'wizard') {
  const code = e?.code
  const status = e?.status || e?.response?.status
  const raw = String(e?.message || '')

  // Axios often puts HTTP status only on response; normalize before mapping.
  if (!code || code === 'ERR_BAD_REQUEST' || code === 'ERR_BAD_RESPONSE') {
    if (status) {
      const normalized = httpStatusToCode(status)
      const key = {
        UNAUTHORIZED: `${ns}.err_login_required`,
        FORBIDDEN: `${ns}.err_forbidden`,
        FILE_TOO_BIG: `${ns}.err_file_size_generic`,
        RATE_LIMITED: `${ns}.err_rate_limited`,
        SERVER_ERROR: `${ns}.err_server`,
        NETWORK: `${ns}.err_network`,
        REQUEST_FAILED: `${ns}.err_upload_failed`,
      }[normalized]
      if (key) return t(key)
    }
  }

  const keyByCode = {
    UNAUTHORIZED: `${ns}.err_login_required`,
    FORBIDDEN: `${ns}.err_forbidden`,
    FILE_TOO_BIG: `${ns}.err_file_size_generic`,
    FILE_TYPE_INVALID: `${ns}.err_file_type_generic`,
    RATE_LIMITED: `${ns}.err_rate_limited`,
    SERVER_ERROR: `${ns}.err_server`,
    NETWORK: `${ns}.err_network`,
    CONSENT_REQUIRED: `${ns}.err_consent_required`,
    UPLOAD_DISABLED: `${ns}.err_upload_disabled`,
    REQUEST_FAILED: `${ns}.err_upload_failed`,
  }

  if (code && keyByCode[code]) {
    return t(keyByCode[code])
  }

  if (status) {
    return t(keyByCode[httpStatusToCode(status)] || `${ns}.err_upload_failed`)
  }

  // Legacy raw strings from older clients / cached builds
  const m = raw.match(/process failed:\s*(\d+)/i)
    || raw.match(/Request failed with status code\s*(\d+)/i)
    || raw.match(/upload failed:\s*(\d+)/i)
  if (m) {
    return t(keyByCode[httpStatusToCode(m[1])] || `${ns}.err_upload_failed`)
  }
  if (/network|ERR_NETWORK|Failed to fetch/i.test(raw)) {
    return t(`${ns}.err_network`)
  }

  // Never surface opaque technical English to end users
  if (!raw || /process failed|Request failed|HTTP_|\b\d{3}\b/.test(raw)) {
    return t(`${ns}.err_upload_failed`)
  }
  return raw
}
