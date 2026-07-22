// /api/v2/profile/* 前端 wrapper — W1 applicant library + email change flow.
//
// 端点:
//   GET    /api/v2/profile                       — current user summary
//   GET    /api/v2/profile/applicants            — list applicants
//   POST   /api/v2/profile/applicants            — add applicant
//   PATCH  /api/v2/profile/applicants/{id}       — edit applicant
//   DELETE /api/v2/profile/applicants/{id}       — remove applicant
//   POST   /api/v2/profile/email/change-request  — start email change
//   POST   /api/v2/profile/email/change-confirm  — confirm with token
//   POST   /api/v2/profile/email/change-cancel   — cancel pending change
//
// 设计:
//   - 真后端在线时走真实接口; mock 模式返回本地内存数据,
//     保证前端 e2e 演示时不会因为后端未启而白屏。
//   - 不混入 my/applicants —— 那个是 W41 header 下拉菜单的派生聚合。

import http from './http'
import { isApiMockMode } from '@/utils/mockMode'

const MOCK_MODE = isApiMockMode()

function delay(ms = 200) {
  return new Promise((r) => setTimeout(r, ms))
}

// In-memory mock store. Persists for the page session.
let _mockApplicants = []
let _mockIdSeq = 1
let _mockProfile = null

function _resetMock() {
  _mockApplicants = []
  _mockIdSeq = 1
  _mockProfile = null
}

function _ensureMockProfile() {
  if (_mockProfile) return _mockProfile
  // Read user from localStorage (auth store) to populate.
  let user = { id: 1, email: 'demo@htex.local', email_pending: null, status: 'active', created_at: new Date().toISOString(), language_pref: 'zh-CN' }
  try {
    const raw = localStorage.getItem('visa.auth')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed.user) user = { ...user, ...parsed.user, email_pending: null }
    }
  } catch {}
  _mockProfile = { ...user, applicant_limit: 10 }
  return _mockProfile
}

/* ----------------------------------------------------------------------- *
 * Profile summary
 * ----------------------------------------------------------------------- */
export async function getProfile() {
  if (MOCK_MODE) {
    await delay()
    return _ensureMockProfile()
  }
  const resp = await http.get('/v2/profile')
  if (resp?.code && resp.code !== '1000') {
    throw new Error(resp.message || 'getProfile failed')
  }
  return resp.data
}

/* ----------------------------------------------------------------------- *
 * Applicant CRUD
 * ----------------------------------------------------------------------- */
export async function listApplicants() {
  if (MOCK_MODE) {
    await delay()
    return [..._mockApplicants].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }
  const resp = await http.get('/v2/profile/applicants')
  if (resp?.code && resp.code !== '1000') {
    throw new Error(resp.message || 'listApplicants failed')
  }
  return resp?.data?.items || []
}

export async function createApplicant({
  surname,
  given_name,
  passport_no,
  is_minor = false,
  guardian_relationship = null,
}) {
  if (MOCK_MODE) {
    await delay()
    // duplicate name check
    if (_mockApplicants.some((a) => a.surname === surname && a.given_name === given_name)) {
      const e = new Error('duplicate name')
      e.code = '9002'
      throw e
    }
    if (_mockApplicants.some((a) => a.passport_no === passport_no.toUpperCase().replace(' ', ''))) {
      const e = new Error('duplicate passport')
      e.code = '9003'
      throw e
    }
    const a = {
      id: _mockIdSeq++,
      surname,
      given_name,
      display_name: _smartJoin(surname, given_name),
      passport_no: passport_no.toUpperCase().replace(' ', ''),
      is_minor: Boolean(is_minor),
      guardian_relationship: is_minor ? guardian_relationship : null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    _mockApplicants.push(a)
    return a
  }
  const resp = await http.post('/v2/profile/applicants', {
    surname,
    given_name,
    passport_no,
    is_minor: Boolean(is_minor),
    guardian_relationship: is_minor ? guardian_relationship : null,
  })
  if (resp?.code !== '1000') {
    const e = new Error(resp.message || 'createApplicant failed')
    e.code = resp?.code
    throw e
  }
  return resp.data.applicant
}

export async function updateApplicant(id, patch) {
  if (MOCK_MODE) {
    await delay()
    const idx = _mockApplicants.findIndex((a) => a.id === id)
    if (idx < 0) throw new Error('not found')
    const merged = { ..._mockApplicants[idx], ...patch, updated_at: new Date().toISOString() }
    merged.display_name = _smartJoin(merged.surname, merged.given_name)
    _mockApplicants[idx] = merged
    return merged
  }
  const resp = await http.patch(`/v2/profile/applicants/${id}`, patch)
  if (resp?.code !== '1000') {
    const e = new Error(resp.message || 'updateApplicant failed')
    e.code = resp?.code
    throw e
  }
  return resp.data.applicant
}

export async function deleteApplicant(id) {
  if (MOCK_MODE) {
    await delay()
    const idx = _mockApplicants.findIndex((a) => a.id === id)
    if (idx < 0) throw new Error('not found')
    _mockApplicants.splice(idx, 1)
    return { deleted: id }
  }
  const resp = await http.delete(`/v2/profile/applicants/${id}`)
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'deleteApplicant failed')
  }
  return resp.data
}

/* ----------------------------------------------------------------------- *
 * Email change flow
 * ----------------------------------------------------------------------- */
export async function requestEmailChange({ new_email, password }) {
  if (MOCK_MODE) {
    await delay()
    if (password !== 'Htex@2026' && password !== 'password') {
      const e = new Error('wrong password')
      e.code = '2001'
      throw e
    }
    _ensureMockProfile().email_pending = new_email
    return { message: 'Verification link sent', pending_email: new_email }
  }
  const resp = await http.post('/v2/profile/email/change-request', { new_email, password })
  if (resp?.code !== '1000') {
    const e = new Error(resp.message || 'requestEmailChange failed')
    e.code = resp?.code
    throw e
  }
  return resp.data
}

export async function confirmEmailChange(token) {
  if (MOCK_MODE) {
    await delay()
    _ensureMockProfile().email_pending = null
    return { message: 'Email updated', pending_email: null }
  }
  const resp = await http.post('/v2/profile/email/change-confirm', { token })
  if (resp?.code !== '1000') {
    const e = new Error(resp.message || 'confirmEmailChange failed')
    e.code = resp?.code
    throw e
  }
  return resp.data
}

export async function cancelEmailChange() {
  if (MOCK_MODE) {
    await delay()
    _ensureMockProfile().email_pending = null
    return { message: 'Cancelled', pending_email: null }
  }
  const resp = await http.post('/v2/profile/email/change-cancel', {})
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'cancelEmailChange failed')
  }
  return resp.data
}

export async function deleteAccount({ password, confirm = true } = {}) {
  if (MOCK_MODE) {
    await delay()
    if (password && password !== 'Htex@2026' && password !== 'password') {
      const e = new Error('wrong password')
      e.code = '2001'
      throw e
    }
    return { message: 'Account scheduled for deletion', status: 'pending_destroy' }
  }
  const body = { confirm: confirm !== false }
  if (password) body.password = password
  const resp = await http.post('/v2/profile/delete-account', body)
  if (resp?.code !== '1000') {
    const e = new Error(resp.message || 'deleteAccount failed')
    e.code = resp?.code
    throw e
  }
  return resp.data
}

export async function cancelDeleteAccount() {
  if (MOCK_MODE) {
    await delay()
    return { message: 'Account deletion cancelled', status: 'active' }
  }
  const resp = await http.post('/v2/profile/cancel-delete-account', {})
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'cancelDeleteAccount failed')
  }
  return resp.data
}

export async function grantConsent({ purpose = 'sensitive_upload', version = 'v1' } = {}) {
  if (MOCK_MODE) {
    await delay()
    return { purpose, version, active: true }
  }
  const resp = await http.post('/v2/profile/consents', { purpose, version })
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'grantConsent failed')
  }
  return resp.data
}

export async function revokeConsent({ purpose = 'sensitive_upload', version = 'v1' } = {}) {
  if (MOCK_MODE) {
    await delay()
    return { purpose, revoked: true }
  }
  const resp = await http.post('/v2/profile/consents/revoke', { purpose, version })
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'revokeConsent failed')
  }
  return resp.data
}

export async function setProcessingRestriction(restricted) {
  if (MOCK_MODE) {
    await delay()
    return { processing_restricted: !!restricted }
  }
  const resp = await http.post('/v2/profile/processing-restriction', {
    restricted: !!restricted,
  })
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'setProcessingRestriction failed')
  }
  return resp.data
}

export async function exportMyData() {
  if (MOCK_MODE) {
    await delay()
    return { exported_at: new Date().toISOString(), user: {}, applicants: [], orders: [], consents: [] }
  }
  const resp = await http.get('/v2/profile/data-export')
  if (resp?.code !== '1000') {
    throw new Error(resp.message || 'exportMyData failed')
  }
  return resp.data
}

/* ----------------------------------------------------------------------- *
 * helpers
 * ----------------------------------------------------------------------- */
function _smartJoin(surname, given_name) {
  const s = (surname || '').trim()
  const g = (given_name || '').trim()
  if (s && /^[A-Za-z]+$/.test(s)) return `${s} ${g}`.trim()
  return `${s}${g}`
}

export const __test__ = { _resetMock }
