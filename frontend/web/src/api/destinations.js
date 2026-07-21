// /api/v2/destinations 前端 wrapper
import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

// 产品口径 docs/PRODUCT_SCOPE.md:
//   客户市场 = 越南 / 印尼护照持有人
//   办理目的地 = 美国 / 英国 / 澳大利亚 / 申根(DE·FR 代表)
// 印尼签证、越南签证、日/加/新/新西兰等都不在业务范围。
export const PRODUCT_COUNTRY_CODES = new Set(['US', 'GB', 'UK', 'AU', 'DE', 'FR'])

function normalizeCountryCode(cc) {
  const c = String(cc || '').toUpperCase()
  return c === 'UK' ? 'GB' : c
}

export function isProductDestination(cc) {
  return PRODUCT_COUNTRY_CODES.has(normalizeCountryCode(cc)) || PRODUCT_COUNTRY_CODES.has(String(cc || '').toUpperCase())
}

// W37: 收紧到真实产品只在 4 国 + 申根 2 国代表.
const FALLBACK_DESTINATIONS = [
  { id: 1,  country_code: 'US', country_name: '美国',      visa_types: ['tourism'], enabled: true },
  { id: 3,  country_code: 'GB', country_name: '英国',      visa_types: ['tourism'], enabled: true },
  { id: 4,  country_code: 'AU', country_name: '澳大利亚', visa_types: ['tourism'], enabled: true },
  { id: 6,  country_code: 'DE', country_name: '德国(申根)', visa_types: ['tourism'], enabled: true },
  { id: 7,  country_code: 'FR', country_name: '法国(申根)', visa_types: ['tourism'], enabled: true },
]

// 翻译国家名(用 lang 切)
function localizeName(d, lang) {
  if (!lang) return d.country_name

  if (lang.startsWith('en')) {
    const enMap = {
      US: 'United States',
      GB: 'United Kingdom',
      AU: 'Australia',
      DE: 'Germany (Schengen)', FR: 'France (Schengen)',
    }
    return enMap[d.country_code] || d.country_name
  }
  if (lang.startsWith('vi')) {
    const viMap = {
      US: 'Hoa Kỳ',
      GB: 'Vương quốc Anh', AU: 'Úc',
      DE: 'Đức (Schengen)', FR: 'Pháp (Schengen)',
    }
    return viMap[d.country_code] || d.country_name
  }
  if (lang.startsWith('id')) {
    const idMap = {
      US: 'Amerika Serikat',
      GB: 'Inggris',
      AU: 'Australia',
      DE: 'Jerman (Schengen)', FR: 'Prancis (Schengen)',
    }
    return idMap[d.country_code] || d.country_name
  }
  return d.country_name
}

function patchProductDestinations(list) {
  // 只保留产品线目的地; 印尼/越南/日/加/新/新西兰等一律剔除。
  // enabled 以接口/后台开关为准，不再强制 true。
  // 历史生产数据仍可能返回 UK；统一成 GB，避免 RAG / 下单按 GB
  // 存储内容时查不到英国资料。规范化后同时去重。
  const byCode = new Map()
  for (const d of (list || [])) {
    if (!isProductDestination(d.country_code) || d.enabled === false) continue
    const countryCode = normalizeCountryCode(d.country_code)
    if (!byCode.has(countryCode)) {
      byCode.set(countryCode, { ...d, country_code: countryCode })
    }
  }
  return [...byCode.values()]
}

export async function listDestinations({ lang = 'zh-CN', visaType } = {}) {
  if (MOCK_MODE) {
    return patchProductDestinations(
      FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, lang) }))
    )
  }
  // 真实模式:失败时降级到 FALLBACK,避免弹 5xx toast
  try {
    const env = await http.get('/v2/destinations', {
      params: { lang, visa_type: visaType },
      __silent: true
    })
    if (env.code !== '1000') throw new Error(env.message || 'destinations fetch failed')
    return patchProductDestinations(env.data || [])
  } catch (e) {
    console.warn('[destinations] real API failed, fallback:', e?.message)
    return patchProductDestinations(
      FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, lang) }))
    )
  }
}
