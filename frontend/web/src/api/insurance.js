// /api/v2/insurance 前端 wrapper
//
// V2 §4.4 拒签险 (mock, no creds):
//   POST /api/v2/insurance/quote      - 报价 (order_id + applicant_age + destination_country)
//   POST /api/v2/insurance/bind       - 绑定报价到订单 (order_id + quote_id)
//   POST /api/v2/insurance/claim       - 拒签理赔 (order_id + rejection_reason)
//   GET  /api/v2/insurance/{policy_id} - 查询保单状态 (无 /policy/ 前缀)

import http from './http'

// ============== POST /api/v2/insurance/quote ==============
// Body: { order_id, applicant_age, destination_country }
// Resp: { code, message, data: { quote_id, premium_cents, coverage_cents, currency, ... } }
export async function getInsuranceQuote({ order_id, applicant_age, destination_country }) {
  if (!order_id) throw new Error('order_id required')
  if (!applicant_age || applicant_age < 0) throw new Error('applicant_age required')
  if (!destination_country) throw new Error('destination_country required')

  try {
    const resp = await http.post('/v2/insurance/quote', {
      order_id,
      applicant_age,
      destination_country
    }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'quote failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'quote failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== POST /api/v2/insurance/bind ==============
// Body: { order_id, quote_id }
// Resp: { code, message, data: { policy_id, policy_no, status, bound_at, premium_cents, ... } }
export async function bindInsurance({ order_id, quote_id }) {
  if (!order_id) throw new Error('order_id required')
  if (!quote_id) throw new Error('quote_id required')

  try {
    const resp = await http.post('/v2/insurance/bind', { order_id, quote_id }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'bind failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'bind failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== POST /api/v2/insurance/claim ==============
// Body: { order_id, rejection_reason }  (NOT policy_id; ClaimRequest.extra='forbid')
// Resp: { code, message, data: { claim_id, policy_id, status: 'approved'|'rejected', payout_cents, ... } }
export async function fileInsuranceClaim({ order_id, rejection_reason }) {
  if (!order_id) throw new Error('order_id required')
  if (!rejection_reason || rejection_reason.length < 2) throw new Error('rejection_reason required (min 2 chars)')

  try {
    const resp = await http.post('/v2/insurance/claim', {
      order_id,
      rejection_reason
    }, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'claim failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'claim failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== GET /api/v2/insurance/{policy_id} ==============
// (no /policy/ prefix in path — see backend route /{policy_id})
// Resp: { code, message, data: { policy_id, policy_no, status, premium_cents, claim_id, claim_status, payout_cents, ... } }
export async function getInsurancePolicy(policy_id) {
  if (!policy_id) throw new Error('policy_id required')

  try {
    const resp = await http.get(`/v2/insurance/${encodeURIComponent(policy_id)}`, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'query policy failed')
      e.code = resp.code
      throw e
    }
    return resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'query policy failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}
