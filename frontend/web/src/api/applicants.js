// /api/v2/my/applicants 前端 wrapper
// W41: header dropdown 数据源 —— 聚合当前用户历史上出现过的申请人(按姓名+护照号去重)
//
// 端点:
//   GET /api/v2/my/applicants
//   -> { code, message, data: { items: [{ id, name, passport_no, order_count, ... }] } }
//
// 设计:
//   - 真后端在线时走真实接口;mock 模式返回空数组(下拉菜单直接显示空态,无需 demo)
//   - 只读,无 POST/PATCH/DELETE

import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

function delay(ms = 200) {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * Get distinct applicants derived from the current user's orders.
 * Returns a flat array — caller decides how to render it.
 *
 * @returns {Promise<Array<{
 *   id: string,
 *   name: string,
 *   passport_no: string|null,
 *   order_count: number,
 *   latest_country: string|null,
 *   latest_status: string|null,
 *   latest_submitted_at: string|null
 * }>>}
 */
export async function listMyApplicants() {
  if (MOCK_MODE) {
    await delay()
    return []
  }
  const resp = await http.get('/v2/my/applicants')
  if (resp?.code && resp.code !== '1000') {
    throw new Error(resp.message || 'listMyApplicants failed')
  }
  return resp?.data?.items || []
}