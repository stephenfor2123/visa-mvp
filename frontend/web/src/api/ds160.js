// /api/v2/ds160 前端 wrapper (W48 v0.2)
//
// Two endpoints the Htex Web uses:
//   POST /api/v2/ds160/code          — issue / refresh a 12-char code
//   POST /api/v2/ds160/code/rotate   — force-rotate (blacklist old code)
//
// The /redeem endpoint is called by the browser extension only (no auth).
//
// All endpoints return the standard envelope `{code, message, data}`. We unwrap
// here so callers get the payload directly; errors propagate as AxiosError
// with the error code in `.code` (via http.js interceptor).
import http from './http'

/**
 * Issue a 12-digit DS-160 code for an order.
 * Returns { code, fingerprint, issued_at, unchanged }.
 * Idempotent — same archive → same code unless `force_rotate: true`.
 */
export async function issueDs160Code(orderId, { forceRotate = false } = {}) {
  const resp = await http.post('/v2/ds160/code', {
    order_id: orderId,
    force_rotate: forceRotate,
  })
  return resp && resp.data ? resp.data : resp
}

/**
 * Convenience: format a 12-char code as "XXXX-XXXX-XXXX" for readability.
 * Does NOT validate — just visual.
 */
export function formatDs160Code(code) {
  if (!code) return ''
  const clean = String(code).replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 12)
  if (clean.length <= 4) return clean
  if (clean.length <= 8) return `${clean.slice(0, 4)}-${clean.slice(4)}`
  return `${clean.slice(0, 4)}-${clean.slice(4, 8)}-${clean.slice(8)}`
}

/**
 * Error-code → human-friendly message map.  Mirrors the popup's mapping
 * so the UX stays consistent across surfaces.
 */
export const DS160_ERROR_MESSAGES = {
  1006: '权限不足,该订单不属于当前用户',
  11001: 'code 不存在, 请检查是否拼错',
  11002: 'code 已被撤销, 请重新生成',
  11003: '档案已更新, 请重新生成 code',
  11004: 'code 格式不正确 (12 位 base30 字符)',
  11005: '档案字段不完整, 请先在向导里补完资料',
  11006: '订单状态不允许生成 code',
  1009: '操作太频繁, 请稍后再试',
}

export function describeDs160Error(code) {
  return DS160_ERROR_MESSAGES[code] || `操作失败 (${code || 'unknown'})`
}