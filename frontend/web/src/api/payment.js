// /api/v2/payment 前端 wrapper
//
// V2 §3.5.6 支付端点 (对齐 backend/app/api/v2/payment.py):
//   POST /api/v2/payment/create            - 创建 mock 支付单 (order_no + amount_cents + currency + method)
//   POST /api/v2/payment/notify            - 支付回调 (no auth, mock 自调用)
//   GET  /api/v2/payment/{order_no}        - 查询支付状态 (无 /status/ 前缀)
//   POST /api/v2/payment/{order_no}/close  - 关闭未支付订单 (无 /cancel/ 前缀)
//
// V2 §3.5.6 状态集:
//   - status:  success | failed | pending | cancelled | closed | paid
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

// ============== GET /api/v2/payment/:order_no ==============
// 真实后端路径 (无 /status/ 前缀): GET /api/v2/payment/{order_no}
// 用于支付结果页轮询 (默认 30s 一次)
// 返回结构: { code, message, data: { order_no, status, amount_cents, currency, method, paid_at, ... } }
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
    const resp = await http.get(`/v2/payment/${encodeURIComponent(orderId)}`, { __silent: true })
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

// ============== POST /api/v2/payment/:order_no/close ==============
// 真实后端路径 (无 /cancel/ 前缀): POST /api/v2/payment/{order_no}/close
// 关闭未支付订单 → 状态翻成 closed
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
    const resp = await http.post(`/v2/payment/${encodeURIComponent(orderId)}/close`, {}, { __silent: true })
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

// ============== retryPayment ==============
// 后端 V2 没有专门的 retry 端点 — 失败/取消后要重试得走 create_payment 重新下单
// 这里保留 retryPayment 作为兼容 alias,内部调 createPayment 重新生成 trade_no
// 状态机:failed/cancelled → 重新 create → 拿到新 trade_no + code_url
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

  // 真业务路径: 后端无 retry 端点,统一改走 createPayment 重新下单
  // amount_cents: 兼容旧 mock 默认 9900;真实 UI 应从 order 读 amount
  return await createPayment({
    order_no: orderId,
    amount_cents: 9900,
    currency: 'USD',
    method: 'mock_wechat',
    desc: 'retry'
  })
}

// ============== GET /api/v2/payment/config ==============
export async function getPaymentConfig() {
  try {
    const resp = await http.get('/v2/payment/config', { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'get payment config failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'get payment config failed')
    e.code = err?.response?.data?.code || err?.code
    throw e
  }
}

// ============== POST /api/v2/payment/create ==============
// 真实后端 create 端点: 调 create_payment 后端路由
export async function createPayment({ order_no, amount_cents, currency = 'USD', method = 'mock_wechat', desc = '' }) {
  if (!order_no) throw new Error('order_no required')
  if (!amount_cents || amount_cents <= 0) throw new Error('amount_cents required (>0)')

  try {
    const resp = await http.post('/v2/payment/create', {
      order_no, amount_cents, currency, method, desc
    }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'create payment failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'create payment failed')
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
