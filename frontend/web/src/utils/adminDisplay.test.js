import { describe, expect, it } from 'vitest'
import { adminMoney, adminRegionFor, supportedAdminVisaTypes } from './adminDisplay'

describe('admin display helpers', () => {
  it('formats money with the actual currency instead of a hard-coded yuan sign', () => {
    expect(adminMoney(1990, 'USD', 'en-US')).toBe('$19.90')
    expect(adminMoney(1990, 'CNY', 'zh-CN')).toContain('19.90')
  })

  it('groups destinations by business region', () => {
    expect(adminRegionFor('US')).toBe('北美')
    expect(adminRegionFor('FR')).toBe('欧洲/申根')
    expect(adminRegionFor('AU')).toBe('大洋洲')
  })

  it('keeps historical visa data untouched while hiding unsupported products', () => {
    const legacy = ['tourism', 'student']
    expect(supportedAdminVisaTypes(legacy)).toEqual(['tourism'])
    expect(legacy).toEqual(['tourism', 'student'])
  })
})
