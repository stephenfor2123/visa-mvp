// /api/v2/affiliate 前端 wrapper
// B-W8-4 (Affiliate 系统收口) 5 端点 (real 模式):
//   POST /api/v2/affiliate/track                    (JWT)  record a click
//   POST /api/v2/affiliate/attribute                (JWT)  bind order → click
//   GET  /api/v2/affiliate/commission/{order_id}    (JWT)  compute commission
//   POST /api/v2/affiliate/payout                   (JWT)  settle partner
//   GET  /api/v2/affiliate/{partner_id}/stats       (X-Partner-Key)
//
// A-W9-2 OMS aff_code 字段接入 (前端缺口补):
//   - trackClick      用户点推广链接时,后端记 click_id (aff_code + landing_path)
//   - attributeOrder  订单创建后,把 click_id 绑到 order_id (写订单时调用)
//   - getCommission   详情页查佣金数据
//   - getPartnerStats partner 端 (partner-key auth) — 暂未用,V2.1 接入
//
// 当前 W9 (A-W9-2):
//   - 5 端点后端已实装 (B-W8-4 收口)
//   - 前端之前 0 接入 (W8 仅在 B 端打通),本任务补前端 wrapper + 2 view 字段 + 1 组件
//   - 默认走真后端 (VITE_MOCK=true 仍走真后端,affiliate 是 V2 全新能力,Mock 不存在)

import http from './http'

const USE_REAL = true  // affiliate 是 V2 新服务,MOCK 不存在,默认真后端

function delay(ms = 240) {
  return new Promise((r) => setTimeout(r, ms))
}

// ============== POST /api/v2/affiliate/track ==============
// 记录一次推广链接点击 — 推广链接 /?aff=AFF001 落地时自动调
// 入参: { aff_code, click_id?, landing_path? }
// 返: { click_id, aff_code, partner_id, tracked_at }
export async function trackClick({ aff_code, click_id = null, landing_path = '/' }) {
  if (!aff_code) throw new Error('aff_code required')
  if (USE_REAL) {
    try {
      const resp = await http.post('/v2/affiliate/track', {
        aff_code,
        click_id,
        landing_path
      }, { __silent: true })
      if (resp?.code && resp.code !== '1000') {
        const e = new Error(resp.message || 'track failed')
        e.code = resp.code
        throw e
      }
      return resp?.data || resp
    } catch (err) {
      // track 失败不阻塞主流程(主流程:用户继续下单),静默降级到 localStorage
      try {
        const raw = localStorage.getItem('visa.aff.pending') || '{}'
        const map = JSON.parse(raw)
        const cid = click_id || `local_${Date.now()}_${Math.floor(Math.random() * 1000)}`
        map[cid] = { aff_code, landing_path, ts: Date.now() }
        localStorage.setItem('visa.aff.pending', JSON.stringify(map))
        return { click_id: cid, aff_code, partner_id: aff_code, tracked_at: new Date().toISOString(), _local: true }
      } catch (_) {
        return { click_id: click_id || `local_${Date.now()}`, aff_code, partner_id: aff_code, tracked_at: new Date().toISOString(), _local: true }
      }
    }
  }
  await delay(160)
  const cid = click_id || `mock_${Date.now()}`
  return { click_id: cid, aff_code, partner_id: aff_code, tracked_at: new Date().toISOString() }
}

// ============== POST /api/v2/affiliate/attribute ==============
// 把 click_id 绑到 order_id — 订单创建成功后调
// 入参: { order_id, click_id }
// 返: { order_id, click_id, aff_code, partner_id, attributed, attributed_at }
export async function attributeOrder({ order_id, click_id }) {
  if (!order_id) throw new Error('order_id required')
  if (!click_id) throw new Error('click_id required')
  if (USE_REAL) {
    const resp = await http.post('/v2/affiliate/attribute', {
      order_id,
      click_id
    }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'attribute failed')
      e.code = resp.code
      throw e
    }
    return resp?.data || resp
  }
  await delay(160)
  return { order_id, click_id, aff_code: 'MOCK_AFF', partner_id: 'MOCK_PARTNER', attributed: true, attributed_at: new Date().toISOString() }
}

// ============== GET /api/v2/affiliate/commission/{order_id} ==============
// 查订单佣金 — 详情页展示"推广来源: PARTNER001 (5% 佣金)"
// 入参: order_id, order_total_cents? (可选,后端可重新计算)
// 返: { order_id, commission_id, commission_amount_cents, commission_rate, currency, partner_id, computed_at }
export async function getCommission(orderId, orderTotalCents = null) {
  if (!orderId) return null
  if (USE_REAL) {
    try {
      const qs = orderTotalCents != null ? `?order_total_cents=${orderTotalCents}` : ''
      const resp = await http.get(`/v2/affiliate/commission/${orderId}${qs}`, { __silent: true })
      if (resp?.code && resp.code !== '1000') {
        // 404 (no aff record) → 静默返 null
        if (resp.code === '4004' || resp.code === '404') return null
        const e = new Error(resp.message || 'commission failed')
        e.code = resp.code
        throw e
      }
      return resp?.data || resp
    } catch (err) {
      // 详情页不强依赖:佣金查不到就当无推广来源,不弹 toast
      return null
    }
  }
  await delay(160)
  return null
}

// ============== POST /api/v2/affiliate/payout ==============
// 结算 partner — partner 端用,V2 暂未实装前端
export async function settlePayout({ partner_id, period }) {
  if (!partner_id) throw new Error('partner_id required')
  if (!period) throw new Error('period required')
  if (USE_REAL) {
    const resp = await http.post('/v2/affiliate/payout', { partner_id, period }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'payout failed')
      e.code = resp.code
      throw e
    }
    return resp?.data || resp
  }
  await delay(160)
  return { payout_id: 'mock_payout', partner_id, period, total_amount_cents: 0, currency: 'USD', status: 'paid', paid_at: new Date().toISOString() }
}

// ============== localStorage 推广点击持久化 ==============
// 用户从推广链接 /?aff=AFF001 落地 → 写入 LS,后续下单时自动读
const PENDING_KEY = 'visa.aff.pending'
const CLICK_KEY = 'visa.aff.last_click'

export function savePendingClick({ click_id, aff_code, landing_path }) {
  try {
    if (click_id) {
      const raw = localStorage.getItem(PENDING_KEY) || '{}'
      const map = JSON.parse(raw)
      map[click_id] = { aff_code, landing_path: landing_path || '/', ts: Date.now() }
      localStorage.setItem(PENDING_KEY, JSON.stringify(map))
      localStorage.setItem(CLICK_KEY, JSON.stringify({ click_id, aff_code, ts: Date.now() }))
    } else if (aff_code) {
      // 只有 aff_code 没 click_id,只记 last_click(配合自动 mint)
      localStorage.setItem(CLICK_KEY, JSON.stringify({ aff_code, ts: Date.now() }))
    }
  } catch (_) {}
}

export function loadPendingClick() {
  try {
    const raw = localStorage.getItem(CLICK_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    // 30 天过期清理
    if (Date.now() - (data.ts || 0) > 30 * 86400000) {
      localStorage.removeItem(CLICK_KEY)
      return null
    }
    return data
  } catch (_) {
    return null
  }
}

export function clearPendingClick() {
  try {
    localStorage.removeItem(CLICK_KEY)
  } catch (_) {}
}

export function listPendingClicks() {
  try {
    const raw = localStorage.getItem(PENDING_KEY) || '{}'
    return JSON.parse(raw)
  } catch (_) {
    return {}
  }
}

export const __test = { PENDING_KEY, CLICK_KEY }