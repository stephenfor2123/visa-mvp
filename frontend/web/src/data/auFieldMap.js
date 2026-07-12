// auFieldMap.js — 澳大利亚 Visitor (Subclass 600) 字段映射（ImmiAccount）
// =============================================================================
import { buildVisaGuideFromMap } from './visaFieldMapUtils.js'
import {
  AU_COUNTRIES,
  AU_SEX,
  AU_MARITAL_STATUS,
  AU_STREAM,
  AU_REASON,
  AU_EMPLOYMENT_STATUS,
  AU_DEVELOPED_VISA,
  AU_FUNDS_BUCKET,
  AU_YES_NO,
} from './auVisaEnums.js'

export const AU_FIELD_MAP_VERSION = '2026.1'
export const AU_FIELD_MAP_VERIFIED_DATE = null

export const AU_MANUAL_STEPS = [
  '在 ImmiAccount (online.immi.gov.au) 注册账号',
  '选择 Visitor visa (subclass 600) → Tourist stream（旅游）',
  '在线支付签证申请费（目前境外旅游 stream 约 AUD $190）',
  '如实完成 Health / Character 声明（工具不代填）',
  '按清单上传：护照、在职证明、银行流水、行程等',
  '等待审理；获批后按 grant letter 入境',
]

export const AU_FIELD_MAP = [
  {
    section: 'application',
    officialTitle: 'Application — Visa stream',
    fields: [
      { label: 'Visa stream', profile: 'au.stream', input: 'select', valueMap: AU_STREAM,
        note: '旅游选 Tourist stream' },
      { label: 'Reason for visit', profile: 'au.reasonForVisit', input: 'select', valueMap: AU_REASON },
    ],
  },
  {
    section: 'personal',
    officialTitle: 'Applicant details',
    fields: [
      { label: 'Family name', profile: 'identity.surname', input: 'text', transform: 'upper' },
      { label: 'Given names', profile: 'identity.givenName', input: 'text', transform: 'upper' },
      { label: 'Sex', profile: 'identity.sex', input: 'select', valueMap: AU_SEX },
      { label: 'Date of birth', profile: 'identity.dob', input: 'date', transform: 'immi_date' },
      { label: 'Country of birth', profile: 'identity.birthCountry', input: 'select',
        valueMap: AU_COUNTRIES },
      { label: 'Relationship status', profile: 'identity.maritalStatus', input: 'select',
        valueMap: AU_MARITAL_STATUS },
      { label: 'Country of passport', profile: 'identity.nationality', input: 'select',
        valueMap: AU_COUNTRIES, note: '国籍/护照所属国' },
    ],
  },
  {
    section: 'passport',
    officialTitle: 'Passport details',
    fields: [
      { label: 'Passport number', profile: 'passport.number', input: 'text', transform: 'upper' },
      { label: 'Country of passport', profile: 'passport.issueCountry', input: 'select',
        valueMap: AU_COUNTRIES },
      { label: 'Date of issue', profile: 'passport.issueDate', input: 'date', transform: 'immi_date',
        optional: true },
      { label: 'Date of expiry', profile: 'passport.expiry', input: 'date', transform: 'immi_date' },
    ],
  },
  {
    section: 'contact',
    officialTitle: 'Contact details',
    fields: [
      { label: 'Residential address', profile: 'contact.street', input: 'text' },
      { label: 'Suburb/Town', profile: 'contact.city', input: 'text' },
      { label: 'State/Province', profile: 'contact.state', input: 'text', optional: true },
      { label: 'Postcode', profile: 'contact.postalCode', input: 'text', optional: true },
      { label: 'Country', profile: 'contact.country', input: 'select', valueMap: AU_COUNTRIES },
      { label: 'Mobile/Cell phone', profile: 'contact.phone', input: 'text' },
      { label: 'Email address', profile: 'contact.email', input: 'text' },
    ],
  },
  {
    section: 'travel',
    officialTitle: 'Travel plans',
    fields: [
      { label: 'Intended date of arrival in Australia',
        profile: 'travel.arrivalDate', input: 'date', transform: 'immi_date' },
      { label: 'Intended date of departure from Australia',
        profile: 'travel.departureDate', input: 'date', transform: 'immi_date', optional: true },
      { label: 'Intended length of stay', profile: 'travel.stayLength', input: 'text',
        transform: 'stay_days_text', optional: true },
      { label: 'Places intending to visit', profile: 'travel.usAddress', input: 'text',
        note: '主要城市/酒店，如 Sydney, Melbourne' },
      { label: 'Funds available for your stay in Australia',
        profile: 'au.fundsBalanceBucket', input: 'select', valueMap: AU_FUNDS_BUCKET },
    ],
  },
  {
    section: 'employment',
    officialTitle: 'Employment',
    fields: [
      { label: 'Employment status', profile: 'au.employmentStatus', input: 'select',
        valueMap: AU_EMPLOYMENT_STATUS },
      { label: 'Occupation', profile: 'work.occupation', input: 'text' },
      { label: 'Name of employer', profile: 'work.employer', input: 'text', optional: true },
      { label: 'Length of employment', profile: 'au.employmentYears', input: 'text', optional: true,
        note: '年数' },
      { label: 'Annual income', profile: 'work.monthlySalary', input: 'text', optional: true,
        note: '可填月薪×12 或年薪' },
    ],
  },
  {
    section: 'visa_history',
    officialTitle: 'Visa history',
    fields: [
      { label: 'Have you held a visa for Australia, UK, USA or a Schengen country?',
        profile: 'au.developedCountryVisa', input: 'select', valueMap: AU_DEVELOPED_VISA },
      { label: 'Have you ever had a visa refused or cancelled?',
        profile: 'au.auVisaRefused', input: 'radio', valueMap: AU_YES_NO, optional: true },
    ],
  },
  {
    section: 'family',
    officialTitle: 'Family members (if applicable)',
    when: { eq: ['identity.maritalStatus', 'married'] },
    fields: [
      { label: "Partner's family name", profile: 'family.spouse.surname', input: 'text',
        transform: 'upper', optional: true },
      { label: "Partner's given names", profile: 'family.spouse.givenName', input: 'text',
        transform: 'upper', optional: true },
    ],
  },
  {
    section: 'declarations',
    officialTitle: 'Health and character declarations',
    manual: true,
    note: 'Health / Character 声明须本人在 ImmiAccount 如实勾选。',
    fields: [
      { label: 'Declarations — I understand health and character questions',
        profile: 'security.acknowledged', input: 'radio', valueMap: AU_YES_NO },
    ],
  },
]

export function buildAuGuide(profile = {}) {
  const guide = buildVisaGuideFromMap({
    fieldMap: AU_FIELD_MAP,
    manualSteps: AU_MANUAL_STEPS,
    version: AU_FIELD_MAP_VERSION,
    verifiedDate: AU_FIELD_MAP_VERIFIED_DATE,
  }, profile)
  guide.meta.country = 'AU'
  return guide
}
