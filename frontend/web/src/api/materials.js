// /api/v2/materials 前端 wrapper
//
// B 1.1.1a 端点 (real 模式):
//   POST   /api/v2/materials/upload      - multipart: file + material_type + order_no
//   POST   /api/v2/materials/upload/chunk  - 分片: upload_id + chunk_index + total_chunks + data
//   POST   /api/v2/materials/upload/complete - 合并: upload_id + material_type + order_no
//   GET    /api/v2/materials              - list (?order_no=&material_type=)
//   GET    /api/v2/materials/{id}         - detail
//   GET    /api/v2/materials/{id}/download - 5min signed url
//   DELETE /api/v2/materials/{id}         - soft delete
//   POST   /api/v2/materials/validate     - 调 15+ 规则
//
// 当前 W2: 后端 B 1.1.1a 还在跑,默认走 mock 让 UI 截图能跑通;真后端上线后无需改前端。

import http from './http'
import { useAuthStore } from '@/stores/auth'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

const ACCEPT_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
const MAX_BYTES = 10 * 1024 * 1024

function delay(ms = 280) {
  return new Promise((r) => setTimeout(r, ms))
}

function getAuthToken() {
  try {
    const raw = localStorage.getItem('visa.auth')
    if (raw) {
      const parsed = JSON.parse(raw)
      return parsed.accessToken || null
    }
  } catch (_) {}
  return null
}

function mockId() {
  return 'mat_' + Math.random().toString(36).slice(2, 10)
}

function makeMockMaterial(materialType = 'passport') {
  const id = mockId()
  return {
    material_id: id,
    id,
    material_type: materialType,
    order_no: null,
    user_id: 'u_demo',
    file_name: `${materialType}_${id.slice(-4)}.jpg`,
    file_size: 1024 * (200 + Math.floor(Math.random() * 600)),
    mime_type: 'image/jpeg',
    thumbnail_url: `https://placehold.co/200x240/EAF0FE/2D5BFF?text=${materialType.toUpperCase()}`,
    download_url: null,
    ocr_status: ['pending', 'processing', 'done'][Math.floor(Math.random() * 3)],
    classification: null,
    created_at: new Date().toISOString()
  }
}

// W2 默认 mock 列表(让 UI 跑得起来 + 截图好看)
let MOCK_DB = []

export function getMaterialTypeOptions() {
  return [
    { value: 'passport', label: 'materials.type_passport' },
    { value: 'id_card', label: 'materials.type_id_card' },
    { value: 'household', label: 'materials.type_household' },
    { value: 'enrollment', label: 'materials.type_enrollment' },
    { value: 'bank', label: 'materials.type_bank' },
    { value: 'flight', label: 'materials.type_flight' },
    { value: 'hotel', label: 'materials.type_hotel' },
    { value: 'photo', label: 'materials.type_photo' },
    { value: 'form', label: 'materials.type_form' },
    { value: 'other', label: 'materials.type_other' }
  ]
}

export function getAcceptTypes() {
  return ACCEPT_TYPES
}
export function getMaxBytes() {
  return MAX_BYTES
}

export async function uploadMaterial(file, materialType = 'passport', orderNo = null) {
  if (!file) throw new Error('file is required')

  if (file.size > MAX_BYTES) {
    const err = new Error('file_too_big')
    err.code = 'FILE_TOO_BIG'
    throw err
  }
  if (file.type && !ACCEPT_TYPES.includes(file.type)) {
    const err = new Error('file_type_invalid')
    err.code = 'FILE_TYPE_INVALID'
    throw err
  }

  if (MOCK_MODE) {
    await delay()
    const m = makeMockMaterial(materialType)
    m.file_name = file.name || m.file_name
    m.file_size = file.size
    m.mime_type = file.type || m.mime_type
    MOCK_DB.unshift(m)
    return m
  }

  const form = new FormData()
  form.append('file', file)
  form.append('material_type', materialType)
  if (orderNo) form.append('order_no', orderNo)

  const envelope = await http.post('/v2/materials/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  if (envelope?.code && envelope.code !== '1000') {
    throw new Error(envelope.message || 'upload failed')
  }
  // W19: backend UploadResponse wraps the material in `material` field —
  // unwrap so callers get the MaterialOut directly (matches the GET /{id} shape)
  return envelope?.data?.material || envelope?.data || envelope
}

// --------------------------------------------------------------------------- //
// Chunked upload — 内部 helpers                                                //
// --------------------------------------------------------------------------- //

const CHUNK_SIZE = 1 * 1024 * 1024   // 1 MB per chunk
const CHUNK_THRESHOLD = 5 * 1024 * 1024  // switch to chunked > 5 MB

/** Split file into 1 MB chunks. Each chunk: { blob, start, end, index, total } */
function splitIntoChunks(file) {
  const total = Math.ceil(file.size / CHUNK_SIZE)
  const chunks = []
  for (let i = 0; i < total; i++) {
    const start = i * CHUNK_SIZE
    const end = Math.min(start + CHUNK_SIZE, file.size)
    chunks.push({
      blob: file.slice(start, end),
      start,
      end,
      index: i,
      total,
    })
  }
  return chunks
}

/**
 * Upload a single chunk via XMLHttpRequest (enables real upload.onprogress).
 * Returns a promise that resolves with the JSON response body.
 */
function uploadChunkXhr(chunk, uploadId, materialType, orderNo, authToken, onChunkProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/v2/materials/upload/chunk')

    // Propagate auth token from caller
    if (authToken) {
      xhr.setRequestHeader('Authorization', `Bearer ${authToken}`)
    }
    xhr.setRequestHeader('X-Upload-ID', uploadId)
    xhr.setRequestHeader('X-Chunk-Index', String(chunk.index))
    xhr.setRequestHeader('X-Total-Chunks', String(chunk.total))
    xhr.setRequestHeader('X-Filename', encodeURIComponent(''))
    xhr.setRequestHeader('X-Material-Type', materialType)
    if (orderNo) xhr.setRequestHeader('X-Order-No', orderNo)
    xhr.setRequestHeader('X-File-Size', String(chunk.end - chunk.start))

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && typeof onChunkProgress === 'function') {
        const fraction = e.loaded / e.total
        const overall = ((chunk.index + fraction) / chunk.total) * 100
        onChunkProgress(overall)
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          resolve({ _raw: xhr.responseText })
        }
      } else {
        reject(new Error(`chunk ${chunk.index} failed: ${xhr.status} ${xhr.responseText}`))
      }
    }
    xhr.onerror = () => reject(new Error(`chunk ${chunk.index} network error`))
    xhr.send(chunk.blob)
  })
}

// W18-followup: 下面这段 (L182-214) 是孤儿代码，原本期望是另一个 uploadChunkXhr
// 但缺少 function 包裹导致 Vite parse error。临时包成 named function 让 build 过。
function uploadChunkXhr_v2_dup_unused(chunk, uploadId, materialType, orderNo) {
  return new Promise((resolve, reject) => {
    if (!chunk) return reject(new Error('chunk required'))
    const _xhr = new XMLHttpRequest()
    _xhr.open('POST', '/api/v2/materials/upload/chunk')
    _xhr.setRequestHeader('X-Upload-ID', uploadId)
    _xhr.setRequestHeader('X-Chunk-Index', String(chunk.index))
    _xhr.setRequestHeader('X-Total-Chunks', String(chunk.total))
    _xhr.setRequestHeader('X-Filename', encodeURIComponent(''))
    _xhr.setRequestHeader('X-Material-Type', materialType)
    if (orderNo) _xhr.setRequestHeader('X-Order-No', orderNo)
    _xhr.setRequestHeader('X-File-Size', String(chunk.end - chunk.start))

    _xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        // per-chunk fractional progress → add to overall base
        const fraction = e.loaded / e.total
        // overall = (chunk_index + fraction) / total_chunks
        const overall = ((chunk.index + fraction) / chunk.total) * 100
        resolve({ _progressSignal: overall })
      }
    }

    _xhr.onload = () => {
      if (_xhr.status >= 200 && _xhr.status < 300) {
        try {
          resolve(JSON.parse(_xhr.responseText))
        } catch {
          resolve({ _raw: _xhr.responseText })
        }
      } else {
        reject(new Error(`chunk ${chunk.index} failed: ${_xhr.status} ${_xhr.responseText}`))
      }
    }
    _xhr.onerror = () => reject(new Error(`chunk ${chunk.index} network error`))
    _xhr.send(chunk.blob)
  })
}

/**
 * Upload file with real progress events.
 * - ≤5 MB: single POST via XMLHttpRequest (upload.onprogress)
 * - >5 MB: serial chunked POST via XMLHttpRequest (per-chunk progress)
 *
 * @param {File} file
 * @param {string} materialType
 * @param {string|null} orderNo
 * @param {function(number): void} onProgress — 0-100
 * @returns {Promise<object>} material object
 */
export async function uploadMaterialWithProgress(file, materialType = 'passport', orderNo = null, onProgress) {
  if (!file) throw new Error('file is required')

  if (file.size > MAX_BYTES) {
    const err = new Error('file_too_big')
    err.code = 'FILE_TOO_BIG'
    throw err
  }
  if (file.type && !ACCEPT_TYPES.includes(file.type)) {
    const err = new Error('file_type_invalid')
    err.code = 'FILE_TYPE_INVALID'
    throw err
  }

  if (MOCK_MODE) {
    // Simulate real progress for mock
    const totalSteps = 20
    for (let i = 1; i <= totalSteps; i++) {
      await delay(Math.random() * 80 + 40)
      onProgress && onProgress(Math.round((i / totalSteps) * 100))
    }
    const m = makeMockMaterial(materialType)
    m.file_name = file.name || m.file_name
    m.file_size = file.size
    m.mime_type = file.type || m.mime_type
    MOCK_DB.unshift(m)
    onProgress && onProgress(100)
    return m
  }

  // Chunked path for large files
  if (file.size > CHUNK_THRESHOLD) {
    return _uploadChunked(file, materialType, orderNo, onProgress)
  }

  // Small file: single XHR with upload.onprogress
  const form = new FormData()
  form.append('file', file)
  form.append('material_type', materialType)
  if (orderNo) form.append('order_no', orderNo)

  const { status, text } = await _xhrPostMultipartWithRefresh(
    '/api/v2/materials/upload', form, onProgress
  )
  if (status < 200 || status >= 300) {
    throw new Error(`upload failed: ${status}`)
  }
  let env
  try {
    env = JSON.parse(text)
  } catch {
    return { _raw: text }
  }
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'upload failed')
  }
  // W36 fix: real upload response wraps the material under `data.material`
  // (same UploadResponse envelope as uploadMaterial()/_uploadChunked()) —
  // this path was resolving with the whole envelope, leaving callers reading
  // `.id`/`.material_id` with undefined.
  return env?.data?.material || env?.data || env
}

// W37: 走原生 XHR 的上传（为了拿 upload.onprogress 真实进度）完全绕开了
// http.js 里的 axios 拦截器，所以 access token 过期时不会自动 refresh——
// 之前上传大概率会 401 失败，用户会被莫名其妙地弹"登录已过期"。这里补一次
// "401 → 刷新 → 重放同一个 form" 的重试，跟 http.js 的行为对齐。
async function _xhrPostMultipart(url, form, onProgress) {
  const authToken = getAuthToken()
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    if (authToken) xhr.setRequestHeader('Authorization', `Bearer ${authToken}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress && onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => resolve({ status: xhr.status, text: xhr.responseText })
    xhr.onerror = () => reject(new Error('upload network error'))
    xhr.send(form)
  })
}

async function _xhrPostMultipartWithRefresh(url, form, onProgress) {
  let result = await _xhrPostMultipart(url, form, onProgress)
  if (result.status === 401) {
    const auth = useAuthStore()
    const refreshed = await auth.refreshAccessToken()
    if (refreshed) {
      result = await _xhrPostMultipart(url, form, onProgress)
    }
  }
  return result
}

/**
 * Chunked upload (serial POST per 1 MB chunk).
 * @param {File} file
 * @param {string} materialType
 * @param {string|null} orderNo
 * @param {function(number): void} onProgress
 */
async function _uploadChunked(file, materialType, orderNo, onProgress) {
  const chunks = splitIntoChunks(file)
  const uploadId = 'up_' + Math.random().toString(36).slice(2, 14)
  const authToken = getAuthToken()

  for (const chunk of chunks) {
    try {
      await uploadChunkXhr(chunk, uploadId, materialType, orderNo, authToken, (overall) => {
        onProgress && onProgress(Math.round(overall))
      })
      // Update progress after chunk completes (covers cases where onprogress didn't fire)
      const chunkFraction = (chunk.index + 1) / chunk.total
      onProgress && onProgress(Math.round(chunkFraction * 100))
    } catch (err) {
      // Abort the upload session on any chunk failure
      try {
        await http.post(`/v2/materials/upload/abort`, { upload_id: uploadId }, { __silent: true })
      } catch {
        // best-effort abort
      }
      throw err
    }
  }

  // Merge chunks into final material
  const env = await http.post('/v2/materials/upload/complete', {
    upload_id: uploadId,
    material_type: materialType,
    order_no: orderNo,
    filename: file.name,
    file_size: file.size,
    mime_type: file.type || 'application/octet-stream',
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'upload merge failed')
  }
  onProgress && onProgress(100)
  // W19: unwrap `material` from UploadResponse envelope
  return env?.data?.material || env?.data || env
}

export async function listMaterials({ orderNo, materialType } = {}) {
  if (MOCK_MODE) {
    await delay()
    let list = [...MOCK_DB]
    if (orderNo) list = list.filter((m) => m.order_no === orderNo)
    if (materialType) list = list.filter((m) => m.material_type === materialType)
    return list
  }
  const env = await http.get('/v2/materials', {
    params: {
      order_no: orderNo || undefined,
      material_type: materialType || undefined
    }
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'list materials failed')
  }
  return env?.data?.items || env?.data || []
}

export async function getMaterial(materialId) {
  if (MOCK_MODE) {
    await delay(120)
    const m = MOCK_DB.find((x) => x.id === materialId || x.material_id === materialId)
    if (!m) throw new Error('material not found')
    return m
  }
  const env = await http.get(`/v2/materials/${materialId}`)
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'get material failed')
  }
  return env?.data || env
}

export async function deleteMaterial(materialId) {
  if (MOCK_MODE) {
    await delay(120)
    MOCK_DB = MOCK_DB.filter((x) => x.id !== materialId && x.material_id !== materialId)
    return { ok: true }
  }
  const env = await http.delete(`/v2/materials/${materialId}`)
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'delete failed')
  }
  return env?.data || { ok: true }
}

export async function getDownloadUrl(materialId) {
  if (MOCK_MODE) {
    await delay(80)
    return { url: `https://example.com/mock-download/${materialId}?ttl=300`, ttl: 300 }
  }
  const env = await http.get(`/v2/materials/${materialId}/download`)
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'download url failed')
  }
  return env?.data || env
}

export async function validateMaterials(materialIds) {
  // 契约: 入参必须是 material_id 数组(后端 B 1.1.1a 端点接受 material_ids: string[])
  if (!Array.isArray(materialIds) || materialIds.length === 0) {
    throw new Error('materialIds must be a non-empty array')
  }
  if (MOCK_MODE) {
    await delay()
    // W2 mock — 给 UI 三档 severity 都有,避免 v-if dead code:
    //   i=0: 护照号格式不对 → error(灰显继续按钮 / 显示整改指引)
    //   i=1: 护照有效期不足 6m → error
    //   i=2: 图像模糊 → warning(yellow 卡)
    //   i>=3: 全部通过 → pass
    const errorRules = [
      { code: 'PASSPORT_NO_FORMAT',   severity: 'error',   message_key: 'validation.passport.no_format',  field: 'passport_no',        details: { value: 'A1234' } },
      { code: 'PASSPORT_EXPIRY_6M',   severity: 'error',   message_key: 'validation.passport.expiry_min_6m', field: 'passport_expiry', details: { value: '2026-09-12', months_remaining: 3 } },
      { code: 'IMAGE_BLUR',           severity: 'warning', message_key: 'validation.image.blur',         field: 'image',              details: { confidence: 0.62 } }
    ]
    const results = materialIds.map((id, i) => {
      if (i < errorRules.length) {
        return { material_id: id, ...errorRules[i] }
      }
      return {
        material_id: id,
        code: 'PASSPORT_OK',
        severity: 'pass',
        message_key: 'validation.pass.ok',
        details: {}
      }
    })
    const summary = {
      pass: results.filter((r) => r.severity === 'pass').length,
      warning: results.filter((r) => r.severity === 'warning').length,
      error: results.filter((r) => r.severity === 'error').length
    }
    return { summary, results }
  }
  const env = await http.post('/v2/materials/validate', { material_ids: materialIds })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'validate failed')
  }
  return env?.data || env
}

export function clearMockDb() {
  MOCK_DB = []
}

// --------------------------------------------------------------------------- //
// V2 §4.3.3 — 图片预处理 (auto-scan + 透视变换 + 降噪)                         //
// --------------------------------------------------------------------------- //

/**
 * Run the document-scan preprocessing pipeline on an image.
 * Returns { image_base64, meta: { width, height, confidence, corrected, ... } }
 */
export async function preprocessImage(file, { applyBinarize = false, forceGrayscale = false } = {}) {
  if (MOCK_MODE) {
    await delay()
    // Mock: just return the file as base64
    const dataUrl = await new Promise((res) => {
      const r = new FileReader()
      r.onload = () => res(r.result)
      r.readAsDataURL(file)
    })
    return {
      image_base64: dataUrl.split(',')[1],
      meta: {
        width: 1200,
        height: 800,
        size_bytes: file.size,
        mime_type: file.type || 'image/jpeg',
        confidence: 0.85,
        corrected: true,
        corners: [[0, 0], [1200, 0], [1200, 800], [0, 800]],
        stages: ['decoded', 'edge_detect', 'perspective_corrected', 'contrast_enhanced', 'resized'],
        warnings: [],
      },
    }
  }
  const form = new FormData()
  form.append('file', file)
  form.append('apply_binarize', String(applyBinarize))
  form.append('force_grayscale', String(forceGrayscale))
  const env = await http.post('/v2/materials/preprocess', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'preprocess failed')
  }
  return env?.data || env
}

// --------------------------------------------------------------------------- //
// V2 §4.3.4 — 自动分类                                                          //
// --------------------------------------------------------------------------- //

/**
 * Auto-classify a material by filename + mime (fast path) or by material_id
 * (server fetches stored OCR result).
 *
 * @param {{ filename?: string, mime_type?: string, material_id?: number|File }} args
 * @returns { predicted_type, confidence, candidates, hints }
 */
export async function classifyMaterial(args = {}) {
  if (MOCK_MODE) {
    await delay(150)
    const fname = (args.filename || '').toLowerCase()
    let predicted = 'other'
    if (/passport|护照/.test(fname)) predicted = 'passport'
    else if (/身份证|id_card|sfz/.test(fname)) predicted = 'id_card'
    else if (/户口|hukou|household/.test(fname)) predicted = 'household'
    else if (/学生|student|enrollment|在学/.test(fname)) predicted = 'enrollment'
    else if (/photo|照片|2寸/.test(fname)) predicted = 'photo'
    else if (/ds-?160|form|申请表|签证表/.test(fname)) predicted = 'form'
    return {
      predicted_type: predicted,
      confidence: predicted === 'other' ? 0.0 : 0.9,
      candidates: [{ material_type: predicted, score: 3.0, reasons: [`mock: filename contains '${predicted}'`] }],
      hints: [],
    }
  }

  let form
  if (args.file) {
    form = new FormData()
    form.append('file', args.file)
    if (args.filename) form.append('filename', args.filename)
    if (args.mime_type) form.append('mime_type', args.mime_type)
  } else {
    form = new FormData()
    if (args.filename) form.append('filename', args.filename)
    if (args.mime_type) form.append('mime_type', args.mime_type)
    if (args.material_id != null) form.append('material_id', String(args.material_id))
  }
  const env = await http.post('/v2/materials/classify', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'classify failed')
  }
  return env?.data || env
}

/**
 * Confirm or correct the AI's classification guess.
 * @param {number} materialId
 * @param {string} materialType
 * @param {boolean} confirmed  true=user accepts, false=user corrected
 */
export async function confirmClassification(materialId, materialType, confirmed = true) {
  if (MOCK_MODE) {
    await delay(80)
    return { id: materialId, material_type: materialType, classification_corrected: confirmed ? null : materialType }
  }
  const env = await http.post(`/v2/materials/${materialId}/classification`, {
    material_type: materialType,
    confirmed,
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'confirm classification failed')
  }
  return env?.data?.material || env?.data || env
}

// --------------------------------------------------------------------------- //
// V2 §4.3.5 — AI 拒签风险诊断                                                    //
// --------------------------------------------------------------------------- //

/**
 * Diagnose the refusal risk of an application.
 * @param {{ material_ids: number[], country_code: string, visa_type?: string, fields?: object }} args
 * @returns { overall_risk, risk_score, summary, issues, positives, policy_refs, rule_count }
 */
export async function diagnoseMaterials(args) {
  if (MOCK_MODE) {
    await delay(500)
    const materialCount = args.material_ids?.length || 0
    const hasExpiryIssue = Math.random() > 0.5
    const issues = []
    const positives = []
    if (materialCount >= 1) positives.push('护照号已成功识别')
    if (hasExpiryIssue) {
      issues.push({
        code: 'passport.expiry_short',
        severity: 'critical',
        title: '护照有效期不足 6 个月',
        detail: '剩余约 3 个月,大多数国家要求 ≥6 个月',
        fix_suggestion: '出发前必须续期护照,否则会被直接拒签。',
        related_material_id: args.material_ids[0],
      })
    } else {
      positives.push('护照有效期充足')
    }
    if (materialCount < 3) {
      issues.push({
        code: 'checklist.incomplete',
        severity: 'warning',
        title: '材料不完整',
        detail: '建议补充签证照片和申请表',
        fix_suggestion: '请上传白底照片 + 填写完整的申请表',
      })
    }
    return {
      overall_risk: hasExpiryIssue ? 'critical' : 'low',
      risk_score: hasExpiryIssue ? 0.65 : 0.05,
      summary: hasExpiryIssue
        ? `${args.country_code || '目标国'}申请存在关键问题,直接提交大概率被拒签。`
        : `${args.country_code || '目标国'}申请材料看起来很完整,可以提交。`,
      issues,
      positives,
      policy_refs: [],
      rule_count: 8,
    }
  }
  const env = await http.post('/v2/materials/diagnose', {
    material_ids: args.material_ids,
    country_code: args.country_code,
    visa_type: args.visa_type,
    fields: args.fields || {},
  })
  if (env?.code && env.code !== '1000') {
    throw new Error(env.message || 'diagnose failed')
  }
  return env?.data || env
}

// W40/W41: LLM 补全行程单里空白的 transport/hotel/attraction 字段
// （city 永远是用户自己填的，不自动生成）；flight 是航班上下文，帮 LLM 判断
// 第一天/最后一天的交通方式。
export async function generateItineraryAttractions({ countryName, lang, days, flight }) {
  if (MOCK_MODE) {
    await delay(600)
    return {
      days: days.map((d, i) => ({
        ...d,
        transport: d.transport || (i === 0 || i === days.length - 1 ? 'flight' : 'walk'),
        hotel: d.hotel || `Hotel ${d.city || countryName || ''}`.trim(),
        attraction: d.attraction || `${d.city || countryName || ''} · 自由行`.trim(),
      })),
    }
  }
  try {
    // W40 fix: MiniMax 实测响应经常要 10-16 秒（天数越多越慢），比 http.js 里
    // 15s 的全局默认超时还慢，所以单独给这个接口更长的超时（要比后端
    // MiniMaxClient 自己的 45s 超时更长，让后端的超时先触发、报出干净的错误，
    // 而不是前端先放弃、白白扔掉一个其实会成功的请求）。
    const env = await http.post('/v2/itinerary/generate', {
      country_name: countryName || '',
      lang: lang || 'zh-CN',
      days,
      flight: flight || null,
    }, { timeout: 50000 })
    if (env?.code && env.code !== '1000') {
      throw new Error(env.message || 'itinerary generate failed')
    }
    return env?.data || env
  } catch (e) {
    // http.js 的拦截器 reject 的是原始 axios error，message 是通用的 HTTP 状态文案，
    // 真正的后端错误信息（比如 "MiniMax error 1008: insufficient balance"）在
    // response.data.message 里，这里取出来重新抛，调用方才能拿到有意义的文案。
    const backendMsg = e?.response?.data?.message
    throw new Error(backendMsg || e?.message || 'itinerary generate failed')
  }
}