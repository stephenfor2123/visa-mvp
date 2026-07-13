import { describe, it, expect } from 'vitest'
import { appLocaleToGoogleHl } from '@/composables/useGoogleAuthButton'

describe('appLocaleToGoogleHl', () => {
  it('maps site locales to GIS locale codes', () => {
    expect(appLocaleToGoogleHl('zh-CN')).toBe('zh_CN')
    expect(appLocaleToGoogleHl('en')).toBe('en')
    expect(appLocaleToGoogleHl('id-ID')).toBe('id')
    expect(appLocaleToGoogleHl('vi-VN')).toBe('vi')
  })
})
