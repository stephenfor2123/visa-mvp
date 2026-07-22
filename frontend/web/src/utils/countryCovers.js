/** Country cover images under /public/countries/ */
export const COUNTRY_COVERS = {
  US: '/countries/us_liberty.jpg',
  AU: '/countries/au_sydney.jpg',
  GB: '/countries/gb_bigben.jpg',
  FR: '/countries/fr_eiffel.jpg',
  DE: '/countries/de_brandenburg.jpg',
  IT: '/countries/it_colosseum.jpg',
  ES: '/countries/es_sagrada.jpg',
  NL: '/countries/nl_tulips.jpg',
  CH: '/countries/ch_matterhorn.jpg',
  SCHENGEN: '/countries/schengen_eiffel.jpg',
}

export function countryCover(code) {
  if (!code) return null
  return COUNTRY_COVERS[String(code).toUpperCase()] || null
}

export function flagEmoji(cc) {
  if (!cc || cc.length !== 2) {
    if (cc === 'SCHENGEN') return '🇪🇺'
    return '🌐'
  }
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}
