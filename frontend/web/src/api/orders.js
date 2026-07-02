// /api/v2/orders 前端 wrapper
// B 1.2.1a 端点 (real 模式):
//   POST /api/v2/orders             - 创建订单 (返回 order_no + status)
//   GET  /api/v2/orders             - 用户订单列表
//   GET  /api/v2/orders/{order_no}  - 订单详情
//   POST /api/v2/orders/{order_no}/submit - 触发 RPA
//   POST /api/v2/orders/{order_no}/cancel - 取消
//
// 当前 W2 (A 1.2.1b):
//   - B 1.2.1a 还没上线 (POST /api/v2/orders → 404)
//   - 默认走 mock 兜底,UI 跑得起来 + 截图能跑
//   - 真后端上线后无需改前端

import http from './http'
import { listMaterials, getMaterial } from './materials'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

function delay(ms = 320) {
  return new Promise((r) => setTimeout(r, ms))
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function plusDaysIso(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function genOrderNo() {
  // 业务订单号:V2-YYYYMMDD-NNNNNN (对齐 V2 §4.2.2 SQL schema)
  const d = new Date()
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  const seq = String(Math.floor(Math.random() * 1_000_000)).padStart(6, '0')
  return `V2-${ymd}-${seq}`
}

// W36: 材料向导上传时,OCR 抽取的字段存在 localStorage('visa.wizard.ocrCache',
// materialId -> fields),因为后端 Material.ocr_result 目前从不会被异步写回
// (上传时写 ocr_status='pending' 之后没有任何任务/接口会更新它)。这里读出来
// 兜底合并到 material.ocr_result,让下面的 extractApplicantDraft 能拿到数据。
function _wizardOcrCache() {
  try {
    return JSON.parse(localStorage.getItem('visa.wizard.ocrCache') || '{}')
  } catch {
    return {}
  }
}

// ============== 公共:按 ID 列表拉取 materials 详情 ==============
// 用于 OCR 预填:合并 passport 等材料的 ocr_result 字段
export async function fetchMaterialsForForm(materialIds = []) {
  if (!Array.isArray(materialIds) || materialIds.length === 0) return []
  try {
    // list 接口在 B 1.1.1a 之前是空,直接逐个 getMaterial
    const cache = _wizardOcrCache()
    const results = []
    for (const id of materialIds) {
      try {
        const m = await getMaterial(id)
        if (!m.ocr_result && cache[m.id ?? m.material_id ?? id]) {
          m.ocr_result = cache[m.id ?? m.material_id ?? id]
        }
        results.push(m)
      } catch (_) {
        // 单个失败不影响其他
      }
    }
    // mock 模式:若没拿到任何材料(测试/演示场景),塞一份 demo passport
    // 这样 OCR 预填功能在 B 1.1.1a 上线前也能可视化
    if (MOCK_MODE && results.length === 0) {
      return [makeDemoPassportMaterial()]
    }
    return results
  } catch (e) {
    // 兜底:listMaterials 拿一把
    try {
      const all = await listMaterials({})
      if (MOCK_MODE && (!all || all.length === 0)) return [makeDemoPassportMaterial()]
      return all || []
    } catch {
      return MOCK_MODE ? [makeDemoPassportMaterial()] : []
    }
  }
}

// mock 演示护照:含 ocr_result(V2 §5.1.3 字段)
function makeDemoPassportMaterial() {
  return {
    material_id: 'mat_demo_passport',
    id: 'mat_demo_passport',
    material_type: 'passport',
    file_name: 'passport_demo.jpg',
    file_size: 412 * 1024,
    mime_type: 'image/jpeg',
    thumbnail_url: 'https://placehold.co/200x240/EAF0FE/2D5BFF?text=PASSPORT',
    ocr_status: 'done',
    ocr_result: {
      passport_no: 'E12345678',
      surname: 'SANTOSO',
      given_name: 'BUDI',
      sex: 'M',
      dob: '1990-05-12',
      nationality: 'ID',
      expiry: '2031-08-22'
    },
    created_at: new Date(Date.now() - 1000 * 60 * 8).toISOString()
  }
}

// ============== OCR 字段抽取:把 materials 合并成一个 applicant_data 草稿 ==============
// V2 §5.1.3 passport 字段: passport_no / surname / given_name / sex / nationality / dob / expiry
export function extractApplicantDraft(materials = []) {
  const draft = {
    surname: '',
    given_name: '',
    sex: '',
    dob: '',
    nationality: '',
    passport_no: '',
    passport_expiry: ''
  }
  let prefilledCount = 0
  const fieldsToCheck = ['surname', 'given_name', 'sex', 'dob', 'nationality', 'passport_no', 'passport_expiry']
  const initial = fieldsToCheck.filter((k) => !draft[k]).length

  // W47c: OCR 返回的 nationality 经常是 ISO 3166-1 alpha-3 (CHN/USA/VNM)，
  // 但前端 nationalityOptions 用的是 alpha-2 (CN/US/VN)。这里做一次映射，
  // 既保证下拉框能选中，也保证 ocrMarked 标记能被点亮。
  const ISO3_TO_ISO2 = {
    CHN: 'CN', USA: 'US', GBR: 'GB', JPN: 'JP', KOR: 'KR', PRK: 'KP',
    IND: 'IN', IDN: 'ID', VNM: 'VN', PHL: 'PH', THA: 'TH', MYS: 'MY',
    SGP: 'SG', AUS: 'AU', CAN: 'CA', FRA: 'FR', DEU: 'DE', ITA: 'IT',
    ESP: 'ES', RUS: 'RU', NLD: 'NL', BEL: 'BE', CHE: 'CH', AUT: 'AT',
    SWE: 'SE', NOR: 'NO', DNK: 'DK', FIN: 'FI', POL: 'PL', BRA: 'BR',
    ARG: 'AR', MEX: 'MX', ZAF: 'ZA', EGY: 'EG', ARE: 'AE', TUR: 'TR',
    SAU: 'SA', ISR: 'IL', NZL: 'NZ',
  }
  function normalizeNationality(raw) {
    if (!raw) return ''
    const s = String(raw).trim().toUpperCase()
    if (!s) return ''
    // 已是 alpha-2 且在 map 里 (即 2 字母码本身不是 3 字母码的 key)
    if (s.length === 2 && Object.values(ISO3_TO_ISO2).includes(s)) return s
    // 3 字母码 → 2 字母码
    if (s.length === 3 && ISO3_TO_ISO2[s]) return ISO3_TO_ISO2[s]
    // 兜底: 截前 2 位 (e.g. "CHINA" → "CH"，但前端没 CH，留原值让用户手选)
    return s
  }

  for (const m of materials) {
    const ocr = m?.ocr_result || m?.classification || null
    if (!ocr) continue
    // 兼容两种结构:ocr_result 是 dict (来自 §5.1.3) 或 classification.transcript (来自 voice)
    for (const k of fieldsToCheck) {
      if (!draft[k] && ocr[k]) {
        let val = String(ocr[k]).trim()
        if (k === 'nationality') val = normalizeNationality(val)
        if (k === 'sex') val = val.toUpperCase().startsWith('F') ? 'F' : (val.toUpperCase().startsWith('M') ? 'M' : val)
        draft[k] = val
        prefilledCount += 1
      }
    }
    // 兼容 dob/expiry 一些别名
    if (!draft.dob && (ocr.birth_date || ocr.date_of_birth)) {
      draft.dob = ocr.birth_date || ocr.date_of_birth
      prefilledCount += 1
    }
    if (!draft.passport_expiry && ocr.expiry) {
      draft.passport_expiry = ocr.expiry
      prefilledCount += 1
    }
    if (!draft.passport_no && (ocr.passport_number || ocr.passportNo)) {
      draft.passport_no = ocr.passport_number || ocr.passportNo
      prefilledCount += 1
    }
    // W47c: 7 个字段全填了才停 (之前只看 surname+given_name+passport_no 导致 sex/nationality 经常被漏)
    const allFilled = fieldsToCheck.every((k) => draft[k])
    if (allFilled) break
  }
  const percent = initial === 0 ? 0 : Math.round((prefilledCount / initial) * 100)
  return { draft, percent, prefilledCount, total: initial }
}

// ============== POST /api/v2/orders ==============
// A-W9-2 aff_code 字段接入:
//   - aff_code  (optional) — 用户从推广链接 /?aff=AFF001 进来,下单时携带
//   - click_id  (optional) — 配套 click_id,用于后续 attribute(订单创建后绑 click_id)
export async function createOrder({
  destination_id,
  visa_type,
  material_ids = [],
  applicant_data = {},
  aff_code = '',
  click_id = ''
}) {
  if (!destination_id) throw new Error('destination_id required')
  if (!visa_type) throw new Error('visa_type required')
  if (!Array.isArray(material_ids) || material_ids.length === 0) {
    const e = new Error('material_ids required')
    e.code = 'MATERIALS_REQUIRED'
    throw e
  }

  if (MOCK_MODE) {
    await delay(380)
    const order_no = genOrderNo()
    const order = {
      order_no,
      user_id: 'u_demo',
      destination_id,
      visa_type,
      status: 'created',
      total_amount: 0,
      currency: 'USD',
      material_ids,
      applicant_data,
      aff_code: aff_code || null,
      click_id: click_id || null,
      destination_url: null,
      rpa_task_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    // 存到 localStorage 方便 N4 详情页 demo
    try {
      const raw = localStorage.getItem('visa.orders') || '{}'
      const map = JSON.parse(raw)
      map[order_no] = order
      localStorage.setItem('visa.orders', JSON.stringify(map))
    } catch (_) {}
    return order
  }

  // 真实后端:走 ApiResponse envelope {code, message, data:{order_no, ...}}
  // A-W9-2 aff_code/click_id 透传到 order 创建 payload
  const envelope = await http.post('/v2/orders', {
    destination_id,
    visa_type,
    material_ids,
    applicant_data,
    aff_code: aff_code || undefined,
    click_id: click_id || undefined
  })
  if (envelope?.code && envelope.code !== '1000') {
    const e = new Error(envelope.message || 'create order failed')
    e.code = envelope.code
    throw e
  }
  return envelope?.data || envelope
}

// ============== GET /api/v2/orders/{order_no} (W2 占位,详情页 W2-D3 接入) ==============
// 5 态规范(V2 §3.6.1 + §4.2.4):created / submitted / reviewing / approved / rejected
// 扩展态:cancelled / closed / failed / abnormal
const ALL_STATUSES = [
  'created', 'submitted', 'reviewing', 'approved', 'rejected',
  'cancelled', 'closed', 'failed', 'abnormal'
]

function isValidStatus(s) {
  return ALL_STATUSES.includes(s)
}

export async function getOrder(orderNo, { etag } = {}) {
  if (MOCK_MODE) {
    await delay(120)
    let stored = null
    try {
      const raw = localStorage.getItem('visa.orders') || '{}'
      const map = JSON.parse(raw)
      if (map[orderNo]) stored = map[orderNo]
    } catch (_) {}
    // 兜底:本地没缓存就造一份
    const order = stored || {
      order_no: orderNo,
      user_id: 'u_demo',
      destination_id: 1,
      visa_type: 'tourism',
      status: 'created',
      total_amount: 0,
      currency: 'USD',
      material_ids: [],
      applicant_data: {},
      destination_url: null,
      rpa_task_id: null,
      rpa_screenshot_url: null,
      rpa_screenshots: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    return { data: order, etag: null, notModified: false }
  }
  // 真实模式:走 axios,带 If-None-Match 走 ETag
  const headers = etag ? { 'If-None-Match': etag } : {}
  try {
    const resp = await http.get(`/v2/orders/${orderNo}`, {
      headers,
      __silent: true,  // 详情页 304/404 不弹 toast
      validateStatus: (s) => s === 200
    })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'get order failed')
      e.code = resp.code
      throw e
    }
    // axios 自动解 response.data(http.js 拦截器已解 envelope)
    return {
      data: resp?.data?.data || resp?.data || resp,
      etag: resp?.etag || null,
      notModified: false
    }
  } catch (err) {
    if (err?.response?.status === 304) {
      return { data: null, etag, notModified: true }
    }
    // 4010 / 4044 状态冲突或 not found 抛出,但不弹 toast
    const e = new Error(err?.response?.data?.message || err.message || 'get order failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== POST /api/v2/orders/{order_no}/cancel ==============
// V2 §4.2.3:仅 `created` 状态可取消;非 created 返 4010 ORDER_NOT_CANCELLABLE
export async function cancelOrder(orderNo) {
  if (MOCK_MODE) {
    await delay(280)
    try {
      const raw = localStorage.getItem('visa.orders') || '{}'
      const map = JSON.parse(raw)
      if (map[orderNo] && map[orderNo].status === 'created') {
        map[orderNo].status = 'cancelled'
        map[orderNo].updated_at = new Date().toISOString()
        map[orderNo].closed_at = new Date().toISOString()
        localStorage.setItem('visa.orders', JSON.stringify(map))
        return {
          order_no: orderNo,
          status: 'cancelled',
          cancelled_at: new Date().toISOString()
        }
      }
      if (map[orderNo]) {
        // 状态不符,4010
        const e = new Error('Order not cancellable in current state')
        e.code = '4010'
        throw e
      }
    } catch (e) {
      if (e.code === '4010') throw e
    }
    // 兜底:无本地记录,也报状态不符
    const e = new Error('Order not cancellable in current state')
    e.code = '4010'
    throw e
  }
  try {
    const resp = await http.post(`/v2/orders/${orderNo}/cancel`, {}, { __silent: true })
    if (resp?.code && resp.code !== '1000') {
      const e = new Error(resp.message || 'cancel failed')
      e.code = resp.code
      throw e
    }
    return resp?.data || resp
  } catch (err) {
    const e = new Error(err?.response?.data?.message || err.message || 'cancel failed')
    e.code = err?.response?.data?.code || err?.code
    e.status = err?.response?.status
    throw e
  }
}

// ============== Mock 状态机推进(demo / screenshot 用) ==============
// 写一个 setMockStatus(orderNo, status) 帮前端截图工具推到目标状态
export function setMockOrderStatus(orderNo, status) {
  if (!MOCK_MODE) return false
  if (!isValidStatus(status)) return false
  try {
    const raw = localStorage.getItem('visa.orders') || '{}'
    const map = JSON.parse(raw)
    if (!map[orderNo]) return false
    map[orderNo].status = status
    map[orderNo].updated_at = new Date().toISOString()
    if (status === 'cancelled' || status === 'closed') {
      map[orderNo].closed_at = new Date().toISOString()
    }
    if (status === 'approved' && !map[orderNo].visa_pdf_url) {
      map[orderNo].visa_pdf_url = 'https://placehold.co/600x800/EAF0FE/2D5BFF?text=VISA+PDF'
    }
    if (status === 'rejected' && !map[orderNo].rejection_reason) {
      map[orderNo].rejection_reason = {
        zh: '资料不完整:未提供近 6 个月的银行流水',
        en: 'Incomplete documents: missing last 6 months bank statement',
        id: 'Dokumen tidak lengkap: laporan bank 6 bulan terakhir hilang',
        vi: 'Hồ sơ chưa đầy đủ: thiếu sao kê ngân hàng 6 tháng gần nhất'
      }
    }
    if (['submitted', 'reviewing', 'approved', 'rejected'].includes(status) && !map[orderNo].rpa_screenshots) {
      map[orderNo].rpa_screenshots = [
        'https://placehold.co/400x240/EAF0FE/2D5BFF?text=RPA+Step+1',
        'https://placehold.co/400x240/FEF3C7/D97706?text=RPA+Step+2',
        'https://placehold.co/400x240/DCFCE7/16A34A?text=RPA+Step+3'
      ]
    }
    localStorage.setItem('visa.orders', JSON.stringify(map))
    return true
  } catch (_) {
    return false
  }
}

export function listMockOrders() {
  try {
    const raw = localStorage.getItem('visa.orders') || '{}'
    return Object.keys(JSON.parse(raw))
  } catch (_) {
    return []
  }
}

// ============== 5 态时间线 ==============
// V2 §3.6.2 N4 详情页
export const TIMELINE_STEPS = [
  { key: 'created',   label: 'orderdetail.status_created'   },
  { key: 'submitted', label: 'orderdetail.status_submitted' },
  { key: 'reviewing', label: 'orderdetail.status_reviewing' },
  { key: 'approved',  label: 'orderdetail.status_approved'  }
]

// 分支态(独立展示,不进主轴)
export const BRANCH_STEPS = [
  { key: 'rejected',  label: 'orderdetail.status_rejected'  }
]

export function getOrderStatusSet() {
  return ALL_STATUSES.slice()
}

// ============== pollOrderStatus — WebSocket 优先 + polling 兜底 ==============
// V2 §4.2.4:订单状态变更通过 WebSocket 推送;前端 30s polling 兜底
// 入参:
//   orderNo       — 订单号
//   onUpdate      — 状态更新回调 (order, source) => void
//   intervalMs    — 轮询间隔(默认 30000ms)
// 返回:
//   cancelFn() — 清理 WebSocket + setInterval,组件 unmount 必须调
//
// 行为:
//   1) 优先尝试 ws://{host}/ws/orders/{orderNo},3s 内未 onopen 视为不可用
//   2) WS 收到 JSON {type:'status', data:{...}} / {type:'rpa_screenshot', data:{url}} 调 onUpdate
//   3) WS 断开 / 失败 → 启动 30s polling 调 getOrder(带 ETag)
//   4) 终态(approved / rejected / cancelled / closed)停止 polling,避免无效请求
export function pollOrderStatus(orderNo, onUpdate, { intervalMs = 30000, wsTimeoutMs = 3000 } = {}) {
  if (!orderNo || typeof onUpdate !== 'function') {
    return () => {}
  }
  let ws = null
  let timer = null
  let etag = null
  let stopped = false
  let wsResolved = false
  let lastStatus = null
  // 终态集:到达后停止轮询(WS 还会收 1 次推送再停)
  const TERMINAL = new Set(['approved', 'rejected', 'cancelled', 'closed'])

  function isTerminal(status) {
    return TERMINAL.has(status)
  }

  function startPolling() {
    if (timer) return
    const tick = async () => {
      if (stopped) return
      try {
        const r = await getOrder(orderNo, { etag })
        if (r.notModified) return
        if (r.data) {
          etag = r.etag || etag
          if (r.data.status && r.data.status !== lastStatus) {
            lastStatus = r.data.status
            onUpdate(r.data, 'polling')
          } else if (r.data.status === lastStatus) {
            // status 未变但 data 可能有 RPA 截图等更新,仍推
            onUpdate(r.data, 'polling-same')
          }
          if (isTerminal(r.data.status)) {
            stopPolling()
          }
        }
      } catch (e) {
        // 静默:HTTP 拦截器已配置静默(__silent);这里只 console.warn
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[pollOrderStatus] tick failed:', e?.message)
        }
      }
    }
    // 立即跑一次,然后 interval
    tick()
    timer = setInterval(tick, intervalMs)
  }

  function stopPolling() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function stopWs() {
    if (ws) {
      try { ws.close() } catch (_) {}
      ws = null
    }
  }

  function stop() {
    stopped = true
    stopPolling()
    stopWs()
  }

  // ---- WebSocket 探测 ----
  // V2 暂未实装 WS endpoint(由 B 1.2.2c 接管),这里走 mock:Mock 模式直接 502 兜底 polling
  if (MOCK_MODE) {
    // mock 模式不真连 WS,直接走 polling + mock 状态机
    // 给前端 1 个 mock WS 钩子,方便 demo 推到目标状态时 onUpdate 即时收到
    setTimeout(() => { if (!stopped) startPolling() }, 100)
    // 暴露一个 window hook 供 dev 工具 / 截图脚本调用
    if (typeof window !== 'undefined') {
      window.__visaMockPush = (status) => {
        try {
          // 直接更新 localStorage + 触发一次 polling tick
          const raw = localStorage.getItem('visa.orders') || '{}'
          const map = JSON.parse(raw)
          if (map[orderNo]) {
            map[orderNo].status = status
            map[orderNo].updated_at = new Date().toISOString()
            if (status === 'cancelled' || status === 'closed') {
              map[orderNo].closed_at = new Date().toISOString()
            }
            localStorage.setItem('visa.orders', JSON.stringify(map))
            if (lastStatus !== status) {
              lastStatus = status
              onUpdate(map[orderNo], 'ws-mock')
            }
            if (isTerminal(status)) stopPolling()
          }
        } catch (_) {}
      }
    }
    return stop
  }

  // ---- 真实模式:WebSocket 优先 ----
  try {
    // W3 cycle 3 (Story 3.2.1a): WS host now sourced from VITE_WS_URL
    // so the same bundle can talk to dev / staging / prod without
    // rebuilding. Default keeps the legacy "same-origin" behavior so
    // existing Vite proxy setups continue to work.
    const WS_BASE = import.meta.env.VITE_WS_URL
      || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    const url = `${WS_BASE}/ws/orders/${orderNo}`
    ws = new WebSocket(url)

    const wsTimer = setTimeout(() => {
      if (!wsResolved) {
        wsResolved = true
        try { ws.close() } catch (_) {}
        startPolling()
      }
    }, wsTimeoutMs)

    ws.onopen = () => {
      if (wsResolved) return
      wsResolved = true
      clearTimeout(wsTimer)
      onUpdate({ __ws: 'connected' }, 'ws-open')
    }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg?.type === 'status' && msg.data) {
          if (msg.data.status !== lastStatus) {
            lastStatus = msg.data.status
            onUpdate(msg.data, 'ws')
            if (isTerminal(msg.data.status)) stopPolling()
          }
        } else if (msg?.type === 'rpa_screenshot' && msg.data?.url) {
          onUpdate({ rpa_screenshot_url: msg.data.url }, 'ws-screenshot')
        } else if (msg?.type === 'ping') {
          // keep-alive
        }
      } catch (_) {}
    }
    ws.onerror = () => {
      if (wsResolved) return
      wsResolved = true
      clearTimeout(wsTimer)
      onUpdate({ __ws: 'error' }, 'ws-error')
      startPolling()
    }
    ws.onclose = () => {
      if (!wsResolved) return
      onUpdate({ __ws: 'closed' }, 'ws-close')
      // 关闭后兜底 polling
      startPolling()
    }
  } catch (e) {
    if (!wsResolved) {
      wsResolved = true
      startPolling()
    }
  }

  return stop
}

export function clearMockOrders() {
  try { localStorage.removeItem('visa.orders') } catch (_) {}
}

export async function listOrders({ page = 1, pageSize = 20 } = {}) {
  if (MOCK_MODE) {
    await delay()
    // W28 P2 #11: demo 数据用于展示状态时间线 UI
    // 真实接口 /v2/orders 上线后此 fallback 自动失效
    return {
      items: [
        {
          order_no: 'V2-20260620-001024',
          user_id: 'u_demo',
          destination_id: 1,
          country_code: 'US',
          country_name: 'United States',
          visa_type: 'tourism',
          status: 'reviewing',
          total_amount: 18500,
          currency: 'USD',
          eta_label: '01 Jul 2026, 23:59',
          created_at: '2026-06-20T08:24:11Z',
        },
        {
          order_no: 'V2-20260615-000988',
          user_id: 'u_demo',
          destination_id: 3,
          country_code: 'GB',
          country_name: 'United Kingdom',
          visa_type: 'tourism',
          status: 'approved',
          total_amount: 12500,
          currency: 'USD',
          processed_at: '2026-06-18T15:32:00Z',
          created_at: '2026-06-15T10:11:43Z',
        },
      ],
      total: 2, page, pageSize,
    }
  }
  const envelope = await http.get('/v2/orders', { params: { page, page_size: pageSize } })
  if (envelope.code !== '1000') {
    throw new Error(envelope.message || 'listOrders failed')
  }
  return envelope.data || { items: [], total: 0 }
}

export const __test = { genOrderNo, todayIso, plusDaysIso, ALL_STATUSES, isValidStatus }
