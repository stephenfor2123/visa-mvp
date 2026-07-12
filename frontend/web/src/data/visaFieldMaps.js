// visaFieldMaps.js — 按目的国选择字段映射 + 引导单生成
// =============================================================================
import { buildDs160Guide, DS160_VERSION, DS160_VERIFIED_DATE, DS160_MANUAL_STEPS } from './ds160FieldMap.js'
import { buildUkGuide, UK_FIELD_MAP_VERSION, UK_FIELD_MAP_VERIFIED_DATE } from './ukFieldMap.js'
import { buildAuGuide, AU_FIELD_MAP_VERSION, AU_FIELD_MAP_VERIFIED_DATE } from './auFieldMap.js'

/** 归一目的国代码（UK → GB） */
export function normalizeDestinationCode(code) {
  const c = String(code || '').trim().toUpperCase()
  if (c === 'UK') return 'GB'
  return c
}

const _BUILDERS = {
  US: (profile) => {
    const g = buildDs160Guide(profile)
    g.meta.country = 'US'
    return g
  },
  GB: buildUkGuide,
  AU: buildAuGuide,
}

export function getVisaFieldMapMeta(countryCode) {
  const c = normalizeDestinationCode(countryCode)
  switch (c) {
    case 'US':
      return { country: 'US', version: DS160_VERSION, verifiedDate: DS160_VERIFIED_DATE, hasPlugin: true }
    case 'GB':
      return { country: 'GB', version: UK_FIELD_MAP_VERSION, verifiedDate: UK_FIELD_MAP_VERIFIED_DATE, hasPlugin: false }
    case 'AU':
      return { country: 'AU', version: AU_FIELD_MAP_VERSION, verifiedDate: AU_FIELD_MAP_VERIFIED_DATE, hasPlugin: false }
    default:
      return null
  }
}

/** 生成对应目的国的填表引导单；不支持的国家返回 null */
export function buildVisaGuide(countryCode, profile = {}) {
  const c = normalizeDestinationCode(countryCode)
  const fn = _BUILDERS[c]
  return fn ? fn(profile) : null
}

export function supportedVisaGuideCountries() {
  return Object.keys(_BUILDERS)
}

export { buildDs160Guide, buildUkGuide, buildAuGuide, DS160_MANUAL_STEPS }
