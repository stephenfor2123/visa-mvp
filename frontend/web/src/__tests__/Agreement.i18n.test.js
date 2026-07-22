import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'
import en from '@shared/i18n/en.json'
import zhCN from '@shared/i18n/zh-CN.json'
import idID from '@shared/i18n/id.json'
import viVN from '@shared/i18n/vi.json'

const messages = {
  en,
  'zh-CN': zhCN,
  'id-ID': idID,
  'vi-VN': viVN,
}

describe('Agreement translations', () => {
  it('has matching keys and compiles every message in all supported locales', () => {
    const expectedKeys = Object.keys(en.agreement).sort()
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: false,
      messages,
    })

    for (const [locale, localeMessages] of Object.entries(messages)) {
      expect(Object.keys(localeMessages.agreement).sort()).toEqual(expectedKeys)
      i18n.global.locale.value = locale

      const email = i18n.global.t('agreement.privacy_contact_email')
      expect(email).toBe('support@htexvisa.com')

      for (const key of expectedKeys) {
        expect(() => {
          i18n.global.t(`agreement.${key}`, { email })
        }).not.toThrow()
      }
    }
  })
})
