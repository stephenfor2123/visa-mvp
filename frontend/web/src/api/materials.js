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

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

const ACCEPT_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
const MAX_BYTES = 10 * 1024 * 1024

function delay(ms = 280) {
  return new Promise((r) => setTimeout(r, ms))
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
  return envelope?.data || envelope
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
function uploadChunkXhr(chunk, uploadId, materialType, orderNo, authToken) {
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
      if (e.lengthComputable) {
        const fraction = e.loaded / e.total
        // overall = (chunk_index + fraction) / total_chunks
        const overall = ((chunk.index + fraction) / chunk.total) * 100
        resolve({ _progressSignal: overall })
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
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/v2/materials/upload')

    const form = new FormData()
    form.append('file', file)
    form.append('material_type', materialType)
    if (orderNo) form.append('order_no', orderNo)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress && onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const env = JSON.parse(xhr.responseText)
          if (env?.code && env.code !== '1000') {
            reject(new Error(env.message || 'upload failed'))
          } else {
            resolve(env?.data || env)
          }
        } catch {
          resolve({ _raw: xhr.responseText })
        }
      } else {
        reject(new Error(`upload failed: ${xhr.status}`))
      }
    }
    xhr.onerror = () => reject(new Error('upload network error'))
    xhr.send(form)
  })
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

  for (const chunk of chunks) {
    try {
      const result = await uploadChunkXhr(chunk, uploadId, materialType, orderNo, null)
      // result may contain _progressSignal if progress fired before resolution
      if (result && typeof result === 'object') {
        const sig = result._progressSignal
        if (typeof sig === 'number') {
          onProgress && onProgress(Math.round(sig))
        }
      }
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
  return env?.data || env
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