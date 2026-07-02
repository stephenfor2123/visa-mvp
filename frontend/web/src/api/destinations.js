// /api/v2/destinations 前端 wrapper
import http from './http'

const MOCK_MODE = import.meta.env.VITE_MOCK !== 'false' // 默认 mock

// V2 首批 9 国(W1 已落库,B 端 destinations 端点暂未上线时用)
const FALLBACK_DESTINATIONS = [
  { id: 1, country_code: 'US', country_name: '美国', visa_types: ['tourism'], enabled: true },
  { id: 2, country_code: 'JP', country_name: '日本', visa_types: ['tourism'], enabled: false },
  { id: 3, country_code: 'UK', country_name: '英国', visa_types: ['tourism'], enabled: false },
  { id: 4, country_code: 'AU', country_name: '澳大利亚', visa_types: ['tourism'], enabled: false },
  { id: 5, country_code: 'CA', country_name: '加拿大', visa_types: ['tourism'], enabled: false },
  { id: 6, country_code: 'DE', country_name: '德国(申根)', visa_types: ['tourism'], enabled: false },
  { id: 7, country_code: 'FR', country_name: '法国(申根)', visa_types: ['tourism'], enabled: false },
  { id: 8, country_code: 'SG', country_name: '新加坡', visa_types: ['tourism'], enabled: false },
  { id: 9, country_code: 'NZ', country_name: '新西兰', visa_types: ['tourism'], enabled: false }
]

// 翻译国家名(用 lang 切)
function localizeName(d, lang) {
  if (lang && lang.startsWith('en')) {
    const enMap = {
      US: 'United States', JP: 'Japan', UK: 'United Kingdom',
      AU: 'Australia', CA: 'Canada', DE: 'Germany (Schengen)',
      FR: 'France (Schengen)', SG: 'Singapore', NZ: 'New Zealand'
    }
    return enMap[d.country_code] || d.country_name
  }
  if (lang && lang.startsWith('id')) {
    const idMap = { US: 'Amerika Serikat', JP: 'Jepang', UK: 'Inggris', AU: 'Australia', CA: 'Kanada', DE: 'Jerman', FR: 'Prancis', SG: 'Singapura', NZ: 'Selandia Baru' }
    return idMap[d.country_code] || d.country_name
  }
  return d.country_name
}

export async function listDestinations({ lang = 'zh-CN', visaType } = {}) {
  if (MOCK_MODE) {
    return FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, lang) }))
  }
  // 真实模式:失败时降级到 FALLBACK,避免弹 5xx toast
  try {
    const env = await http.get('/v2/destinations', {
      params: { lang, visa_type: visaType },
      __silent: true
    })
    if (env.code !== '1000') throw new Error(env.message || 'destinations fetch failed')
    return env.data || []
  } catch (e) {
    console.warn('[destinations] real API failed, fallback:', e?.message)
    return FALLBACK_DESTINATIONS.map((d) => ({ ...d, country_name: localizeName(d, lang) }))
  }
}
