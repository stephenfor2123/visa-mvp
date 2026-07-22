export function adminRegionFor(code) {
  const value = String(code || '').toUpperCase()
  if (['US', 'CA', 'MX'].includes(value)) return '北美'
  if (['GB', 'IE'].includes(value)) return '英国及爱尔兰'
  if (['AU', 'NZ'].includes(value)) return '大洋洲'
  if (['JP', 'KR', 'CN'].includes(value)) return '东亚'
  if (['SG', 'ID', 'VN', 'TH', 'MY', 'PH'].includes(value)) return '东南亚'
  if (['FR', 'DE', 'IT', 'ES', 'NL', 'BE', 'AT', 'CH', 'PT', 'GR'].includes(value)) return '欧洲/申根'
  return '其他'
}

export function adminMoney(cents, currency = 'USD', locale) {
  if (cents == null) return '—'
  const amount = Number(cents) / 100
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${amount.toFixed(2)}`
  }
}

export function supportedAdminVisaTypes(types) {
  return (types || []).filter(type => type === 'tourism')
}
