// /api/v2/destinations 前端 wrapper
import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

// W37: 收紧到真实产品只在 4 国 + 申根 2 国代表.
// 之前 W57 加了 JP/CA/SG/NZ/VN 是给 Diagnose 页 footer 兜底用的,
// 但一直留在 FALLBACK 里 → /apply 页在 MOCK 模式下也会显示这些国家,
// 用户会误以为是产品实际在做的目的地. 已下架.
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
  return (list || []).map((d) => {
    const cc = String(d.country_code || '').toUpperCase()
    if (cc === 'UK' || cc === 'GB' || cc === 'AU') return { ...d, enabled: true }
    return d
  })
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
