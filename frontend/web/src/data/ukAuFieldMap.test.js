// ukAuFieldMap.test.js — 英/澳字段映射 + 引导单
import { describe, it, expect } from 'vitest'
import { buildApplicantProfile } from '@/composables/useApplicantProfile.js'
import { buildUkGuide } from './ukFieldMap.js'
import { buildAuGuide } from './auFieldMap.js'
import { buildVisaGuide, normalizeDestinationCode } from './visaFieldMaps.js'

const sampleForm = {
  surname: 'NGUYEN',
  given_name: 'VAN AN',
  sex: 'M',
  marital_status: 'single',
  dob: '1992-05-14',
  birth_city: 'Ho Chi Minh',
  birth_country: 'VN',
  nationality: 'VN',
  home_street: '123 Le Loi',
  home_city: 'Ho Chi Minh',
  home_country: 'VN',
  phone: '+84901234567',
  email: 'an@example.vn',
  passport_no: 'B12345678',
  passport_issue_country: 'VN',
  passport_expiry: '2031-03-01',
  visa_type: 'tourism',
  arrival_date: '2026-09-01',
  departure_date: '2026-09-15',
  stay_days: 14,
  hotel_name: 'Premier Inn London',
  occupation: 'Engineer',
  employer_name: 'Acme Co',
  uk_visa_length: '6_months',
  uk_main_reason: 'tourism',
  uk_funds_payer: 'self',
  uk_employment_status: 'employed',
  uk_employment_years: '3',
  uk_funds_balance_bucket: 'above_5w',
  uk_visa_history: 'never',
  au_stream: 'tourist',
  au_reason_for_visit: 'tourism',
  au_employment_status: 'employed',
  au_funds_balance_bucket: 'above_3w',
  au_developed_country_visa: 'none',
}

describe('UK_FIELD_MAP', () => {
  it('完整档案 → 核心 section 无缺失', () => {
    const profile = buildApplicantProfile({ form: sampleForm })
    const g = buildUkGuide(profile)
    const core = ['application', 'personal', 'contact', 'passport', 'travel', 'employment_finance']
    const missing = g.sections
      .filter((s) => core.includes(s.section))
      .flatMap((s) => s.steps.filter((st) => st.missing).map((st) => st.label))
    expect(missing).toEqual([])
    expect(g.meta.country).toBe('GB')
  })

  it('VN 国籍 → VIETNAM', () => {
    const g = buildUkGuide(buildApplicantProfile({ form: { nationality: 'VN' } }))
    const nat = g.sections.find((s) => s.section === 'personal').steps
      .find((st) => st.label === 'Country of nationality')
    expect(nat.value).toBe('VIETNAM')
  })

  it('已婚 → family section 出现', () => {
    const married = buildUkGuide(buildApplicantProfile({
      form: { ...sampleForm, marital_status: 'married', spouse_surname: 'TRAN' },
    }))
    expect(married.sections.find((s) => s.section === 'family')).toBeDefined()
  })
})

describe('AU_FIELD_MAP', () => {
  it('完整档案 → 核心 section 无缺失', () => {
    const profile = buildApplicantProfile({ form: sampleForm })
    const g = buildAuGuide(profile)
    const core = ['application', 'personal', 'passport', 'contact', 'travel', 'employment']
    const missing = g.sections
      .filter((s) => core.includes(s.section))
      .flatMap((s) => s.steps.filter((st) => st.missing).map((st) => st.label))
    expect(missing).toEqual([])
    expect(g.meta.country).toBe('AU')
  })

  it('日期 → DD/MM/YYYY', () => {
    const g = buildAuGuide(buildApplicantProfile({ form: { dob: '1992-05-14' } }))
    const dob = g.sections.find((s) => s.section === 'personal').steps
      .find((st) => st.label === 'Date of birth')
    expect(dob.value).toBe('14/05/1992')
  })
})

describe('visaFieldMaps', () => {
  it('UK 代码归一', () => {
    expect(normalizeDestinationCode('UK')).toBe('GB')
    expect(buildVisaGuide('UK', buildApplicantProfile({ form: sampleForm }))?.meta.country).toBe('GB')
  })

  it('US 走 DS-160', () => {
    const g = buildVisaGuide('US', buildApplicantProfile({ form: sampleForm }))
    expect(g.meta.version).toMatch(/^2026\./)
  })
})
