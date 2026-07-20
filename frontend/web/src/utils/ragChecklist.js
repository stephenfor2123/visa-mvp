/** Detect whether a resources hot-question should use the structured checklist API. */
export function isMaterialsChecklistQuery(query = '', tag = '') {
  const text = `${query} ${tag}`.toLowerCase()
  return /材料清单|所需材料|required\s*documents|materials?\s*checklist|dokumen|persyaratan|hồ\s*sơ|giấy\s*tờ/.test(text)
}

/** Map wiki/UI country keys (schengen) to checklist API country codes. */
export function resolveChecklistCountry(code) {
  const c = String(code || '').toUpperCase()
  if (c === 'SCHENGEN' || c === 'EU') return 'FR'
  return c
}
