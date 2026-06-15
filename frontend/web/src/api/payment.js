// /api/v2/payment 前端 wrapper
//
// W14 支付端点:
//   GET  /api/v2/payment/status/{orderId}   - 查询支付状态(轮询用)
//   POST /api/v2/payment/cancel/{orderId}   - 取消未支付订单
//   POST /api/v2/payment/retry/{orderId}    - 失败重试支付
//
// V2 §3.5.6 + W9 Stripe 真接路径:
//   - status:  success | failed | pending | cancelled
//   - amount 单位:分(cents),返回后前端按 currency 格式化
//
// Mock 模式: VITE_MOCK !== 'false' 时使用本地 mock 数据 + localStorage 状态机
//   - 与 W6 stub payment 端点兼容,key = localStorage.visa.payments

import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false'

function delay(ms = 280) {
  return new Promise((r) => setTimeout(r, ms))
}

const STORAGE_KEY = 'visa.payments'

// 合法 payment 状态集(V2 §3.5.6)
const VALID_STATUSES = ['success', 'failed', 'pending', 'cancelled']

function loadMap() {
  try {
    const raw = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)) || '{}'
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function saveMap(map) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
    }
  } catch (_) {}
}

function genMockPayment(orderId, { status = 'pending' } = {}) {
  const now = new Date().toISOString()
  const methodChoices = ['stripe', 'alipay', 'wechat']
  const method = methodChoices[Math.floor(Math.random() * methodChoices.length)]
  const reasonMap = {
    'insufficient_funds': 'insufficient_funds',
    'card_declined': 'card_declined',
    'network_error': 'network_error',
    'expired_session': 'expired_session'
  }
  const reason = status === 'failed'
    ? reasonMap[Object.keys(reasonMap)[Math.floor(Math.random() * 4)]]
    : null
  return {
    order_id: orderId,
    status,
    amount_cents: 9900,
    currency: 'USD',
    method,
    reason,
    reason_message: reason,
    transaction_id: status === 'success' ? 'txn_' + Math.random().toString(36).slice(2, 12) : null,
    estimated_processing_hours: status === 'success' ? 24 : null,
    created_at: now,
    updated_at: now,
    paid_at: status === 'success' ? now : null,
    cancelled_at: status === 'cancelled' ? now : null
  }
}

function readMockPayment(orderId) {
  const map = loadMap()
  if (map[orderId]) return map[orderId]
  // 首次:创建默认 pending 记录
  const created = genMockPayment(orderId, { status: 'pending' })
  map[orderId] = created
  saveMap(map)
  return created
}

function writeMockPayment(orderId, patch) {
  const map = loadMap()
  const cur = map[orderId] || genMockPayment(orderId, { status: 'pending' })
  const next = { ...cur, ...patch, updated_at: new Date().toISOString() }
  map[orderId] = next
  saveMap(map)
  return next
}

// ============== GET /api/v2/payment/status/:orderId ==============
// 用于支付结果页轮询 (默认 30s 一次)
// 返回结构: { order_id, status, amount_cents, currency, method, reason, transaction_id, ... }
// 错误:
//   - 404 → 抛 NOT_FOUND
//   - 401 → 走 http.js 拦截器自动 logout
export async function queryPaymentStatus(orderId) {
  if (!orderId) throw new Error('orderId required')

  if (MOCK_MODE) {
    await delay(180)
    const p = readMockPayment(orderId)
    // 返回 envelope 形状 {code, message, data: payment}
    return {
      code: '1000',
      message: 'ok',
      data: p
    }
  }

  try {
    const resp = await http.get(`/v2/payment/status/${orderId}`, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'query payment status failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const status = err?.response?.status
    const e = new Error(err?.response?.data?.message || err.message || 'query payment status failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = status
    throw e
  }
}

// ============== POST /api/v2/payment/cancel/:orderId ==============
// 取消未支付订单 → 状态翻成 cancelled
export async function cancelPayment(orderId) {
  if (!orderId) throw new Error('orderId required')

  if (MOCK_MODE) {
    await delay(220)
    const cur = readMockPayment(orderId)
    if (cur.status === 'success') {
      // 成功后不允许取消
      const e = new Error('Cannot cancel a successful payment')
      e.code = '4020'
      throw e
    }
    const next = writeMockPayment(orderId, {
      status: 'cancelled',
      cancelled_at: new Date().toISOString()
    })
    return {
      code: '1000',
      message: 'ok',
      data: next
    }
  }

  try {
    const resp = await http.post(`/v2/payment/cancel/${orderId}`, {}, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'cancel payment failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'cancel payment failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== POST /api/v2/payment/retry/:orderId ==============
// 失败重试:返回新的支付链接或 session(V2 §3.5.6),前端可跳回 Stripe / 支付宝
// 简化实现:把状态从 failed 翻回 pending,允许前端重新触发轮询或跳转
export async function retryPayment(orderId) {
  if (!orderId) throw new Error('orderId required')

  if (MOCK_MODE) {
    await delay(220)
    const cur = readMockPayment(orderId)
    if (cur.status !== 'failed' && cur.status !== 'cancelled') {
      const e = new Error('Only failed or cancelled payments can be retried')
      e.code = '4021'
      throw e
    }
    const next = writeMockPayment(orderId, {
      status: 'pending',
      reason: null,
      reason_message: null,
      cancelled_at: null
    })
    return {
      code: '1000',
      message: 'ok',
      data: next
    }
  }

  try {
    const resp = await http.post(`/v2/payment/retry/${orderId}`, {}, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'retry payment failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'retry payment failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== Mock 工具:供截图脚本 / 测试用 ==============
// 强制把某个 orderId 的状态推到目标值
export function setMockPaymentStatus(orderId, status) {
  if (!MOCK_MODE) return false
  if (!VALID_STATUSES.includes(status)) return false
  const map = loadMap()
  const cur = map[orderId] || genMockPayment(orderId, { status: 'pending' })
  const now = new Date().toISOString()
  cur.status = status
  cur.updated_at = now
  if (status === 'success') {
    cur.transaction_id = cur.transaction_id || 'txn_' + Math.random().toString(36).slice(2, 12)
    cur.paid_at = now
    cur.estimated_processing_hours = cur.estimated_processing_hours || 24
  }
  if (status === 'failed' && !cur.reason) {
    cur.reason = 'card_declined'
    cur.reason_message = 'card_declined'
  }
  if (status === 'cancelled') {
    cur.cancelled_at = now
  }
  map[orderId] = cur
  saveMap(map)
  return true
}

export function listMockPayments() {
  try {
    return Object.keys(JSON.parse((typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)) || '{}'))
  } catch {
    return []
  }
}

export function clearMockPayments() {
  try { localStorage.removeItem(STORAGE_KEY) } catch (_) {}
}

export const __PAYMENT_STATUSES__ = VALID_STATUSES.slice()
