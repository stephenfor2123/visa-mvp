// /api/v2/transfer wrapper — W48 cross-device QR upload from phone
//
// Flow:
//   PC端 (登录态):
//     createSession()  -> { sid, qr_payload, expires_at }       全局轮询 SSE 用 sid
//     getSession(sid)   -> { file_count, files[], close_reason }
//     closeSession(sid) -> abort
//
//   手机端 (从 QR 拿到 sid + token):
//     claimSession(sid, token)        -> 标记 sid 已认领, 返回 expires_at
//     uploadTransferFile(sid, token, file) -> 上传一张图 (走服务端 → 上传到 PC 的 user_id)
//     leaveSession(sid, token)        -> 主动关掉 (PC 上 closed 事件触发)
//
// 注意: SSE 不能用 axios (browser 自动 reconnect 不友好),直接用原生 EventSource。
//
// 这套接口的成功/失败语义:
//
//   PC create_session -> 201 + sid / qr_payload
//   PC SSE -> "claimed" -> "file_received" -> "closed" 事件链
//   phone claim -> 200,或 404 (session 已 purge) / 410 (session 过期/close) / 403 (token 错)

import http from './http'

/**
 * PC: 创建一个 transfer session。
 * 返回 { sid, qr_payload, expires_at }。
 * qr_payload 是绝对 URL（手机扫码直接进 /transfer?sid=...&t=...）。
 */
export async function createTransferSession() {
  const env = await http.post('/v2/transfer/sessions', {}, { __silent: true })
  return env?.data || env
}

/**
 * PC: 拉一次 session 状态 (SSE 失败的兜底轮询)。
 */
export async function getTransferSession(sid) {
  if (!sid) throw new Error('sid is required')
  const env = await http.get(`/v2/transfer/sessions/${encodeURIComponent(sid)}`, null, { __silent: true })
  return env?.data || env
}

/**
 * PC: 关掉 session (用户中途取消)。
 */
export async function closeTransferSession(sid) {
  if (!sid) return
  try {
    await http.post(`/v2/transfer/sessions/${encodeURIComponent(sid)}/close`, {}, { __silent: true })
  } catch (_) {
    // 静默 — close 不是关键路径
  }
}

/**
 * Phone: 认领 session (QR 进 H5 后第一件事)。
 * Token 走 X-Transfer-Token header (不进 access log)。
 */
export async function claimTransferSession(sid, token) {
  const r = await fetch(`/api/v2/transfer/sessions/${encodeURIComponent(sid)}/claim`, {
    method: 'POST',
    headers: { 'X-Transfer-Token': token },
  })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    const err = new Error(`claim failed: ${r.status} ${text}`)
    err.status = r.status
    throw err
  }
  return r.json()
}

/**
 * Phone: 上传一张图 (FormData)。
 * 服务端把图片写到 *PC user* 的 user_id 下,所以 PC 端 inspect 直接看见。
 */
export async function uploadTransferFile(sid, token, file, materialType = 'other') {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('material_type', materialType)
  const r = await fetch(`/api/v2/transfer/sessions/${encodeURIComponent(sid)}/files`, {
    method: 'POST',
    headers: { 'X-Transfer-Token': token },
    body: fd,
  })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    const err = new Error(`upload failed: ${r.status} ${text}`)
    err.status = r.status
    throw err
  }
  return r.json()
}

/**
 * Phone: 主动离开。
 */
export async function leaveTransferSession(sid, token) {
  try {
    await fetch(`/api/v2/transfer/sessions/${encodeURIComponent(sid)}/leave`, {
      method: 'POST',
      headers: { 'X-Transfer-Token': token },
    })
  } catch (_) {
    // H5 unload 时调用,失败无所谓
  }
}

/**
 * PC: 打开 SSE 流听 session 事件。
 * 返回一个 EventSource 实例 — 监听 'hello' / 'claimed' / 'file_received' / 'closed' 事件。
 * 调用方负责在 unmount 时 source.close()。
 *
 * axios 的 SSE 不靠谱 (它默认 JSON parse 整个 body), 所以直接用浏览器原生 EventSource。
 * 鉴权: PC 端是登录态,auth header 必须 — 用 polyfill / query token 都不优雅,所以走 token: 复用
 *   Bearer token 作为 query (`?t=`),服务端允许短时查询参数等价于 header。简单做法是把 sid
 *   作为路径绑 session owner,而让 server 识别 PC:这是 PC → server 的连接,通过 sid 隐式
 *   鉴权 (因为只有 owner 能创建 sid,创建时即绑定 user_id,本 endpoint 不需要再要 token)。
 */
export function openTransferEvents(sid) {
  // 注意:EventSource 默认没法自定义 header,但我们的 /events endpoint 走的是 PC cookie/JWT
  // auth (Bearer via httpOnly cookie... no — 我们的 auth 是 localStorage + Authorization header)
  // EventSource 不支持自定义 header,所以这里需要一种折中:把 JWT 放在 query 里。
  //
  // 简化做法:server 在 claim 阶段已经把 PC user_id 写到 session 里,我们靠 *sid* 的不可猜
  // 性 (64-bit entropy + 校验 user_id) 替代显式 header auth。前面 get_session 已经走
  // http (Authorization header) 验证过 owner,这里首次 get 时把 sid + owner 已 cache。
  // 对于 SSE 偷听,如果攻击者拿到 sid,他就能听 — 但 session 2 分钟过期 + 一旦文件上传完成
  // 就关掉,接受这个风险。
  return new EventSource(`/api/v2/transfer/sessions/${encodeURIComponent(sid)}/events`, {
    withCredentials: false,
  })
}
