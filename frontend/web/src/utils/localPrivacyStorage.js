/**
 * Browser-local visa data — wizard drafts, OCR cache, local document previews.
 * Nothing here is synced to the server (privacy-first architecture).
 */

export const WIZARD_TTL_MS = 7 * 24 * 60 * 60 * 1000
export const LOCAL_DOCS_KEY = 'visa.local.docs'
export const OCR_CACHE_KEY = 'visa.wizard.ocrCache'
export const TRAVEL_PLAN_KEY = 'visa.wizard.travelPlan'
export const WIZARD_PREFIX = 'visa.wizard.'

const ITEM_KEY_TYPE = {
  passport_scan: 'passport',
  id_card_scan: 'id_card',
  household_scan: 'household',
  bank_statement: 'bank',
  employment_letter: 'other',
  visa_photo: 'photo',
  flight_booking: 'flight',
  hotel_booking: 'hotel',
}

export function inferMaterialType(itemKey = '') {
  if (ITEM_KEY_TYPE[itemKey]) return ITEM_KEY_TYPE[itemKey]
  const k = (itemKey || '').toLowerCase()
  if (k.includes('passport')) return 'passport'
  if (k.includes('bank')) return 'bank'
  if (k.includes('photo')) return 'photo'
  return 'other'
}

export function wrapWithExpiry(data) {
  return { _savedAt: Date.now(), data }
}

export function loadWithExpiry(key, fallback, ttl = WIZARD_TTL_MS) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed._savedAt === 'number') {
      if (Date.now() - parsed._savedAt > ttl) {
        localStorage.removeItem(key)
        return fallback
      }
      return parsed.data !== undefined ? parsed.data : fallback
    }
    return parsed ?? fallback
  } catch {
    return fallback
  }
}

export function saveWithExpiry(key, data, ttl = WIZARD_TTL_MS) {
  void ttl
  try {
    localStorage.setItem(key, JSON.stringify(wrapWithExpiry(data)))
  } catch { /* quota */ }
}

function readOcrCache() {
  return loadWithExpiry(OCR_CACHE_KEY, {})
}

export function buildDiagnosableSnapshotFromOcrCache() {
  const cache = readOcrCache()
  return Object.entries(cache).map(([localId, ocr_result]) => {
    const item_key = localId.includes(':') ? localId.split(':').slice(1).join(':') : localId
    return {
      item_key,
      material_type: inferMaterialType(item_key),
      ocr_result: ocr_result || {},
    }
  })
}

export function savePrecheckSnapshot(orderNo, snapshot) {
  if (!orderNo || !Array.isArray(snapshot)) return
  try {
    sessionStorage.setItem(`precheck_snapshot_${orderNo}`, JSON.stringify(snapshot))
  } catch { /* ignore */ }
}

export function loadPrecheckSnapshot(orderNo) {
  if (!orderNo) return []
  try {
    const raw = sessionStorage.getItem(`precheck_snapshot_${orderNo}`)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export async function fileToDataUrl(file) {
  return new Promise((resolve) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => resolve(null)
    r.readAsDataURL(file)
  })
}

export function listLocalDocuments() {
  return loadWithExpiry(LOCAL_DOCS_KEY, [])
}

export function addLocalDocument(doc) {
  const list = listLocalDocuments()
  const entry = {
    localId: doc.localId || `doc_${Date.now()}`,
    material_id: doc.localId || doc.material_id,
    id: doc.localId || doc.id,
    file_name: doc.file_name || doc.fileName || 'file',
    file_size: doc.file_size || doc.fileSize || 0,
    material_type: doc.material_type || doc.materialType || 'other',
    thumbnail_url: doc.thumbnail_url || doc.thumbUrl || '',
    download_url: doc.download_url || doc.fileUrl || doc.thumbUrl || '',
    ocr_result: doc.ocr_result || doc.ocrResult || {},
    item_key: doc.item_key || doc.itemKey || doc.localId,
    saved_at: Date.now(),
    ephemeral: !!doc.ephemeral,
  }
  const next = [entry, ...list.filter((x) => x.localId !== entry.localId)].slice(0, 50)
  saveWithExpiry(LOCAL_DOCS_KEY, next)
  return entry
}

export function listDiagnosableMaterials() {
  const seen = new Set()
  const items = []

  for (const d of listLocalDocuments()) {
    const id = d.localId || d.id
    if (!id || seen.has(id)) continue
    seen.add(id)
    items.push({
      localId: id,
      id,
      material_id: id,
      file_name: d.file_name,
      material_type: d.material_type,
      ocr_result: d.ocr_result || {},
      item_key: d.item_key || id,
    })
  }

  for (const snap of buildDiagnosableSnapshotFromOcrCache()) {
    const id = snap.item_key
    if (seen.has(id)) continue
    seen.add(id)
    items.push({
      localId: id,
      id,
      material_id: id,
      file_name: snap.item_key,
      material_type: snap.material_type,
      ocr_result: snap.ocr_result,
      item_key: snap.item_key,
    })
  }

  return items
}

/** Remove all browser-local visa drafts, OCR cache, and previews. */
export function clearAllLocalVisaData() {
  const lsKeys = []
  for (let i = 0; i < localStorage.length; i += 1) {
    const k = localStorage.key(i)
    if (
      k &&
      (k.startsWith('visa.') ||
        k.startsWith('wizard.orderForm.') ||
        k === 'ordernew_draft')
    ) {
      lsKeys.push(k)
    }
  }
  lsKeys.forEach((k) => {
    try { localStorage.removeItem(k) } catch { /* ignore */ }
  })

  const ssKeys = []
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const k = sessionStorage.key(i)
    if (k && (k.startsWith('precheck_') || k.startsWith('rpa_passport_'))) {
      ssKeys.push(k)
    }
  }
  ssKeys.forEach((k) => {
    try { sessionStorage.removeItem(k) } catch { /* ignore */ }
  })
}
