// background.js — service worker (W48 v0.2)
// ============================================================================
// Four responsibilities:
//   1) Receive a 12-digit code from popup → POST /api/v2/ds160/code/redeem →
//      stash profile + meta in chrome.storage.session.
//   2) Serve profile / meta to content-ds160.js so it can fill forms.
//   3) Open ceac.state.gov in a new tab (UX1: popup → 立刻跳转美签网站).
//   4) Clear on user request.
//
// chrome.storage.session is volatile (closes when the browser closes), so we
// never persist anything to disk.  No PII upload from the extension — the
// backend already has it.
// ============================================================================

const DEFAULT_API_BASE = 'http://localhost:8000'
const DS160_URL = 'https://ceac.state.gov/genniv/'

const PROFILE_KEY = 'htex_profile'      // ApplicantProfile dict
const META_KEY    = 'htex_meta'         // {order_id, fingerprint, mapping_version, mapping_verified_date, profile}
const PROGRESS_KEY = 'htex_ds160_progress'  // {filledSections: []}  (P1: cross-page tracker)
const SUBMITTED_KEY = 'htex_ds160_submitted' // {[order_id]: {submittedAt}} — 用户确认"已提交"的记录
                                             // 只存布尔性质的标记+时间,不存确认码等 PII;
                                             // 用 storage.local 持久化(关浏览器后仍可见)

const API_BASE_KEY = 'htex_api_base'

async function _getApiBase() {
  const r = await chrome.storage.local.get(API_BASE_KEY)
  return (r[API_BASE_KEY] || DEFAULT_API_BASE).replace(/\/$/, '')
}

// ---------- Message dispatcher ----------
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || !msg.type) return false

  switch (msg.type) {
    case 'HTEX_REDEEM_CODE':
      return _redeemCode(msg.code).then(sendResponse), true   // async

    case 'HTEX_GET_META':
      return _getMeta().then(sendResponse), true

    case 'HTEX_CLEAR_PROFILE':
      return _clearProfile().then(sendResponse), true

    case 'HTEX_OPEN_DS160':
      // W48 v0.2 UX1: popup "立刻去 ceac.state.gov" button.
      // New tab so the user keeps the popup open if they want to come back.
      return _openDs160().then(sendResponse), true

    case 'HTEX_SAVE_PROGRESS':
      return _saveProgress(msg.progress).then(sendResponse), true

    case 'HTEX_GET_PROGRESS':
      return _getProgress().then(sendResponse), true

    case 'HTEX_CLEAR_PROGRESS':
      return _clearProgress().then(sendResponse), true

    case 'HTEX_MARK_SUBMITTED':
      return _markSubmitted(msg.orderId).then(sendResponse), true

    case 'HTEX_GET_SUBMITTED':
      return _getSubmitted(msg.orderId).then(sendResponse), true

    case 'HTEX_SET_API_BASE':
      return _setApiBase(msg.apiBase).then(sendResponse), true

    case 'HTEX_GET_API_BASE':
      return _getApiBase().then((base) => sendResponse({ apiBase: base })), true

    default:
      return false
  }
})

// ---------- /redeem ----------
async function _redeemCode(rawCode) {
  const code = _sanitizeCode(rawCode)
  if (!_isValidCode(code)) {
    return { ok: false, code: '11004', message: 'Invalid format' }
  }
  try {
    const apiBase = await _getApiBase()
    const r = await fetch(`${apiBase}/api/v2/ds160/code/redeem`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) {
      // BizException envelope: {code, message, data}
      return {
        ok: false,
        code: body && body.code,
        message: body && body.message,
        data: body && body.data,
      }
    }
    // Success envelope: {code, message, data: {order_id, profile, fingerprint, mapping_version, ...}}
    const data = body.data || {}
    const profile = data.profile || {}
    const meta = {
      order_id: data.order_id,
      code,  // kept in session only — used to sync portal-submitted milestone
      fingerprint: data.fingerprint,
      mapping_version: data.mapping_version,
      mapping_verified_date: data.mapping_verified_date,
      profile,  // cached here for popup display
    }
    await chrome.storage.session.set({
      [PROFILE_KEY]: profile,
      [META_KEY]: meta,
    })
    return { ok: true, meta }
  } catch (err) {
    return { ok: false, code: 'NETWORK', message: String(err && err.message || err) }
  }
}

// ---------- meta / profile accessors ----------
async function _getMeta() {
  const r = await chrome.storage.session.get(META_KEY)
  return { meta: r[META_KEY] || null }
}

async function _clearProfile() {
  await chrome.storage.session.remove([PROFILE_KEY, META_KEY])
  return { ok: true }
}

// ---------- Open DS-160 in a new tab ----------
async function _openDs160() {
  // New tab → user's existing tabs aren't disturbed.  If they already have a
  // DS-160 tab open, the new one lands at the same starting point; the
  // content script will inject on its own.
  try {
    await chrome.tabs.create({ url: DS160_URL })
    return { ok: true, url: DS160_URL }
  } catch (err) {
    return { ok: false, message: String(err && err.message || err) }
  }
}

// ---------- progress (cross-page tracker; P1) ----------
async function _saveProgress(p) {
  await chrome.storage.session.set({ [PROGRESS_KEY]: p || {} })
  return { ok: true }
}

async function _getProgress() {
  const r = await chrome.storage.session.get(PROGRESS_KEY)
  return { progress: r[PROGRESS_KEY] || {} }
}

async function _clearProgress() {
  await chrome.storage.session.remove(PROGRESS_KEY)
  return { ok: true }
}

// ---------- DS-160 提交确认(用户手动确认,插件不自动点 Submit) ----------
async function _syncPortalSubmitted(code) {
  try {
    const apiBase = await _getApiBase()
    const r = await fetch(`${apiBase}/api/v2/ds160/portal-submitted`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) {
      return {
        ok: false,
        code: body && body.code,
        message: (body && body.message) || `HTTP ${r.status}`,
      }
    }
    const data = body.data || {}
    return {
      ok: true,
      submittedAt: data.ds160_portal_submitted_at || null,
      unchanged: !!data.unchanged,
    }
  } catch (err) {
    return { ok: false, code: 'NETWORK', message: String(err && err.message || err) }
  }
}

async function _markSubmitted(orderId) {
  const key = String(orderId || 'unknown')
  const submittedAt = new Date().toISOString()

  const r = await chrome.storage.local.get(SUBMITTED_KEY)
  const map = r[SUBMITTED_KEY] || {}
  map[key] = { submittedAt, synced: false }
  await chrome.storage.local.set({ [SUBMITTED_KEY]: map })

  const session = await chrome.storage.session.get(META_KEY)
  const code = session[META_KEY] && session[META_KEY].code
  let synced = false
  let syncError = null
  if (code) {
    const sync = await _syncPortalSubmitted(code)
    synced = !!sync.ok
    syncError = sync.ok ? null : (sync.message || sync.code || 'sync failed')
    map[key] = {
      submittedAt: sync.ok && sync.submittedAt ? sync.submittedAt : submittedAt,
      synced,
      syncError,
      unchanged: sync.ok ? !!sync.unchanged : false,
    }
    await chrome.storage.local.set({ [SUBMITTED_KEY]: map })
  } else {
    syncError = 'no code in session — redeem again to sync with Htex'
    map[key].syncError = syncError
    await chrome.storage.local.set({ [SUBMITTED_KEY]: map })
  }

  return {
    ok: true,
    submittedAt: map[key].submittedAt,
    synced,
    syncError,
  }
}

async function _getSubmitted(orderId) {
  const r = await chrome.storage.local.get(SUBMITTED_KEY)
  const map = r[SUBMITTED_KEY] || {}
  const rec = map[String(orderId || 'unknown')] || null
  return {
    submitted: !!rec,
    submittedAt: rec && rec.submittedAt || null,
    synced: !!(rec && rec.synced),
    syncError: rec && rec.syncError || null,
  }
}

async function _setApiBase(apiBase) {
  const base = (apiBase || DEFAULT_API_BASE).replace(/\/$/, '')
  await chrome.storage.local.set({ [API_BASE_KEY]: base })
  return { ok: true, apiBase: base }
}

// ---------- helpers (mirror backend ds160.py validation) ----------
const _CODE_RE = /^[2-9A-HJ-NP-Z]{12}$/
function _sanitizeCode(raw) {
  return (raw || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase()
}
function _isValidCode(code) {
  return !!code && _CODE_RE.test(code)
}