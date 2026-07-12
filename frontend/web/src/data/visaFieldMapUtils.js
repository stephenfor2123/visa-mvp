// visaFieldMapUtils.js — 各国官网填表字段映射共用工具
// =============================================================================
import { evaluateWhen } from './ds160When.js'

export function profileGet(o, p) {
  return String(p).split('.').reduce((a, k) => (a == null ? undefined : a[k]), o)
}

export function isProfileEmpty(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'boolean') return false
  return String(v).trim() === ''
}

function coerceBoolForValueMap(raw) {
  if (raw === true || raw === false) return raw
  const s = String(raw).trim().toLowerCase()
  if (s === 'true' || s === 'yes' || s === 'y' || s === '1') return true
  if (s === 'false' || s === 'no' || s === 'n' || s === '0') return false
  return raw
}

export function resolveValueMap(raw, valueMap) {
  if (!valueMap || isProfileEmpty(raw)) return raw
  if (valueMap[raw] !== undefined) return valueMap[raw]
  if (valueMap[String(raw)] !== undefined) return valueMap[String(raw)]
  const coerced = coerceBoolForValueMap(raw)
  if (coerced !== raw && valueMap[coerced] !== undefined) return valueMap[coerced]
  const up = String(raw).trim().toUpperCase()
  for (const v of Object.values(valueMap)) {
    if (String(v).toUpperCase() === up) return v
  }
  for (const v of Object.values(valueMap)) {
    const vu = String(v).toUpperCase()
    if (vu.includes(up) || up.includes(vu)) return v
  }
  return raw
}

/** select/radio: 档案值必须能映射到官网枚举(防 App i18n 文案写入门户) */
export function isPortalEnumResolved(raw, valueMap) {
  if (!valueMap || isProfileEmpty(raw)) return true
  if (valueMap[raw] !== undefined) return true
  if (valueMap[String(raw)] !== undefined) return true
  const coerced = coerceBoolForValueMap(raw)
  if (coerced !== raw && valueMap[coerced] !== undefined) return true
  const up = String(raw).trim().toUpperCase()
  for (const v of Object.values(valueMap)) {
    if (String(v).toUpperCase() === up) return true
  }
  for (const v of Object.values(valueMap)) {
    const vu = String(v).toUpperCase()
    if (vu.includes(up) || up.includes(vu)) return true
  }
  return false
}

const MONTHS_EN = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

export function toGovUkDate(raw) {
  const m = String(raw).trim().match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
  if (!m) return String(raw)
  const mon = MONTHS_EN[+m[2] - 1]
  if (!mon) return String(raw)
  return `${String(+m[3]).padStart(2, '0')} ${mon} ${m[1]}`
}

export function toImmiDate(raw) {
  const m = String(raw).trim().match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
  if (!m) return String(raw)
  return `${String(+m[3]).padStart(2, '0')}/${String(+m[2]).padStart(2, '0')}/${m[1]}`
}

export function resolveVisaField(f, profile) {
  const raw = profileGet(profile, f.profile)
  if (isProfileEmpty(raw)) {
    if (f.optional) {
      return {
        label: f.label,
        profile: f.profile,
        input: f.input,
        action: 'na',
        value: f.whenEmpty || 'Not applicable',
        missing: false,
        optional: true,
        note: f.note,
      }
    }
    return {
      label: f.label,
      profile: f.profile,
      input: f.input,
      action: 'todo',
      value: null,
      missing: true,
      optional: false,
      note: f.note,
    }
  }
  let value = resolveValueMap(raw, f.valueMap)
  if (f.valueMap && (f.input === 'select' || f.input === 'radio') && !isPortalEnumResolved(raw, f.valueMap)) {
    return {
      label: f.label,
      profile: f.profile,
      input: f.input,
      action: 'todo',
      value: null,
      missing: true,
      optional: false,
      note: f.note,
    }
  }
  if (f.transform === 'upper') value = String(value).toUpperCase()
  else if (f.transform === 'govuk_date') value = toGovUkDate(value)
  else if (f.transform === 'immi_date') value = toImmiDate(value)
  else if (f.transform === 'stay_days_text') {
    const n = String(value).replace(/\D/g, '')
    value = n ? `${n} days` : String(value)
  }
  return {
    label: f.label,
    profile: f.profile,
    input: f.input,
    action: 'fill',
    value,
    missing: false,
    optional: !!f.optional,
    note: f.note,
  }
}

export function buildVisaGuideFromMap({ fieldMap, manualSteps, version, verifiedDate }, profile = {}) {
  let missingCount = 0
  const sections = fieldMap
    .filter((sec) => !sec.manual && (!sec.when || evaluateWhen(sec.when, profile)))
    .map((sec) => {
      const steps = sec.fields
        .filter((f) => !f.when || evaluateWhen(f.when, profile))
        .map((f) => {
          const step = resolveVisaField(f, profile)
          if (step.missing) missingCount += 1
          return step
        })
      return {
        section: sec.section,
        officialTitle: sec.officialTitle,
        manual: !!sec.manual,
        steps,
      }
    })
  return {
    meta: { version, verifiedDate, country: null },
    sections,
    manualSteps: manualSteps || [],
    missingCount,
  }
}

/** 渲染引导单为纯文本（复制 / 导出用） */
export function renderVisaGuideText(guide, { title = 'Visa application guide' } = {}) {
  if (!guide) return ''
  const lines = []
  lines.push(title)
  const verified = guide.meta?.verifiedDate || 'draft (not verified against live portal)'
  const ver = guide.meta?.version || '?'
  const cc = guide.meta?.country || ''
  lines.push(`Map v${ver}${cc ? ` · ${cc}` : ''} · verified ${verified}`)
  if (guide.missingCount > 0) {
    lines.push(`⚠ ${guide.missingCount} field(s) still missing — complete your profile in Htex first`)
  }
  lines.push('')
  for (const sec of guide.sections || []) {
    lines.push(`[${sec.officialTitle}]`)
    for (const s of sec.steps || []) {
      const val = s.missing ? '⚠ TODO' : (s.value ?? s.whenEmpty ?? '—')
      lines.push(`  ${s.label}: ${val}${s.note ? ` (${s.note})` : ''}`)
    }
    lines.push('')
  }
  if (guide.manualSteps?.length) {
    lines.push('Manual steps (complete yourself on the official site):')
    for (const m of guide.manualSteps) lines.push(`  · ${m}`)
  }
  return lines.join('\n')
}
