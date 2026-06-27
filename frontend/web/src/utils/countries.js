// Country grouping utilities
// W27: 把 destinations 列表按"签证体系"分组显示
//   - 国别签证 (National): US / AU / GB — 各自独立的 B1/B2、subclass 600、Standard Visitor
//   - 申根签证 (Schengen): 26 国共用同一签证
//
// 数据来源: backend/app/api/v2/destinations.py 返回的 DestinationOut
// 注意:任何新加的 destination 如果不在 SCHENGEN_CODES 集合里,会归到"国别签证"组;
// 这对长尾国家(日本/韩国/新加坡等)是正确的,符合"按签证类型分"的语义。

/** ISO 3166-1 alpha-2 申根成员国 + 申根候选/关联国 (Iceland/Norway/Liechtenstein/Switzerland 不在 alpha 内但同样共用申根) */
export const SCHENGEN_CODES = new Set([
  'AT', 'BE', 'HR', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
  'HU', 'IS', 'IT', 'LV', 'LI', 'LT', 'LU', 'MT', 'NL', 'NO',
  'PL', 'PT', 'SK', 'SI', 'ES', 'SE', 'CH',
])

/** 返回国家所属签证组 key: 'schengen' | 'national' */
export function countryGroup(countryCode) {
  if (!countryCode) return 'national'
  return SCHENGEN_CODES.has(countryCode) ? 'schengen' : 'national'
}

/**
 * 把 countries 数组按签证体系分组,保持各自内部的相对顺序。
 * @param {Array<{country_code: string}>} countries
 * @returns {{ national: Array, schengen: Array, unknown: Array }}
 *   - unknown 留给任何不识别 code 的兜底,UI 可选显示
 */
export function groupCountriesByVisaType(countries = []) {
  const result = { national: [], schengen: [], unknown: [] }
  for (const c of countries) {
    const cc = c.country_code
    if (SCHENGEN_CODES.has(cc)) {
      result.schengen.push(c)
    } else if (cc) {
      result.national.push(c)
    } else {
      result.unknown.push(c)
    }
  }
  return result
}
