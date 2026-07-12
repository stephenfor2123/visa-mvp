// ukFieldMap.js — 英国 Standard Visitor 字段映射（GOV.UK 在线申请）
// =============================================================================
// 锚官网字段标签(label)，profile 路径与 useApplicantProfile.js 嵌套结构一致。
// 用于 Web 引导单；暂无浏览器插件自动填表。
// =============================================================================
import { buildVisaGuideFromMap } from './visaFieldMapUtils.js'
import {
  UK_COUNTRIES,
  UK_SEX,
  UK_MARITAL_STATUS,
  UK_VISA_LENGTH,
  UK_MAIN_REASON,
  UK_FUNDS_PAYER,
  UK_EMPLOYMENT_STATUS,
  UK_VISA_HISTORY,
  UK_YES_NO,
  UK_FUNDS_BUCKET,
} from './ukVisaEnums.js'

export const UK_FIELD_MAP_VERSION = '2026.1'
export const UK_FIELD_MAP_VERIFIED_DATE = null

export const UK_MANUAL_STEPS = [
  '在 GOV.UK 创建申请账号并选择 Standard Visitor visa',
  '如在中国居住满 6 个月：预约英使馆指定医院做 TB 检测并上传证书',
  '在线支付签证费（目前短期 Standard Visitor 约 £135）',
  '预约签证中心（VFS）录指纹 + 递交护照',
  '如实回答品行/移民史声明页（工具不代填）',
  '上传支持性文件：在职证明、银行流水、行程/酒店预订单等',
]

export const UK_FIELD_MAP = [
  {
    section: 'application',
    officialTitle: 'Application — Visa type',
    fields: [
      { label: 'Visa length', profile: 'uk.visaLength', input: 'select',
        valueMap: UK_VISA_LENGTH, note: '多数旅游选 Up to 6 months' },
      { label: 'What is the main reason for your visit to the UK?',
        profile: 'uk.mainReason', input: 'select', valueMap: UK_MAIN_REASON },
    ],
  },
  {
    section: 'personal',
    officialTitle: 'Personal details',
    fields: [
      { label: 'Family name', profile: 'identity.surname', input: 'text', transform: 'upper',
        note: '护照姓（拼音大写）' },
      { label: 'Given names', profile: 'identity.givenName', input: 'text', transform: 'upper' },
      { label: 'Sex', profile: 'identity.sex', input: 'select', valueMap: UK_SEX },
      { label: 'Relationship status', profile: 'identity.maritalStatus', input: 'select',
        valueMap: UK_MARITAL_STATUS },
      { label: 'Date of birth', profile: 'identity.dob', input: 'date', transform: 'govuk_date' },
      { label: 'Country of birth', profile: 'identity.birthCountry', input: 'select',
        valueMap: UK_COUNTRIES },
      { label: 'Place of birth', profile: 'identity.birthCity', input: 'text', optional: true },
      { label: 'Country of nationality', profile: 'identity.nationality', input: 'select',
        valueMap: UK_COUNTRIES },
      { label: 'National Insurance number', profile: 'identity.nationalId', input: 'text',
        optional: true, note: '中国公民通常选 Not applicable' },
    ],
  },
  {
    section: 'contact',
    officialTitle: 'Contact details',
    fields: [
      { label: 'Address line 1', profile: 'contact.street', input: 'text' },
      { label: 'Town/City', profile: 'contact.city', input: 'text' },
      { label: 'Province/State', profile: 'contact.state', input: 'text', optional: true },
      { label: 'Postal code', profile: 'contact.postalCode', input: 'text', optional: true },
      { label: 'Country', profile: 'contact.country', input: 'select', valueMap: UK_COUNTRIES },
      { label: 'Telephone number', profile: 'contact.phone', input: 'text',
        note: '带国家码，如 +86...' },
      { label: 'Email address', profile: 'contact.email', input: 'text' },
    ],
  },
  {
    section: 'passport',
    officialTitle: 'Passport details',
    fields: [
      { label: 'Passport number', profile: 'passport.number', input: 'text', transform: 'upper' },
      { label: 'Issuing authority', profile: 'passport.issueCountry', input: 'select',
        valueMap: UK_COUNTRIES, note: '护照签发国' },
      { label: 'Place of issue', profile: 'passport.issueCity', input: 'text', optional: true },
      { label: 'Date of issue', profile: 'passport.issueDate', input: 'date', transform: 'govuk_date',
        optional: true },
      { label: 'Expiry date', profile: 'passport.expiry', input: 'date', transform: 'govuk_date',
        note: '建议剩余 ≥6 个月' },
    ],
  },
  {
    section: 'travel',
    officialTitle: 'Your plans in the UK',
    fields: [
      { label: 'When do you plan to arrive in the UK?',
        profile: 'travel.arrivalDate', input: 'date', transform: 'govuk_date' },
      { label: 'When do you plan to leave the UK?',
        profile: 'travel.departureDate', input: 'date', transform: 'govuk_date', optional: true,
        note: '可与返程机票日期一致' },
      { label: 'How long do you plan to stay in the UK?',
        profile: 'travel.stayLength', input: 'text', transform: 'stay_days_text', optional: true },
      { label: 'Where do you plan to stay in the UK?',
        profile: 'travel.usAddress', input: 'text', note: '酒店名 + 地址（英国境内）' },
      { label: 'Who will pay for your visit?',
        profile: 'uk.fundsPayer', input: 'select', valueMap: UK_FUNDS_PAYER },
    ],
  },
  {
    section: 'employment_finance',
    officialTitle: 'Employment and finances',
    fields: [
      { label: 'What is your employment status?',
        profile: 'uk.employmentStatus', input: 'select', valueMap: UK_EMPLOYMENT_STATUS },
      { label: 'Employer name', profile: 'work.employer', input: 'text', optional: true },
      { label: 'Job title / occupation', profile: 'work.occupation', input: 'text' },
      { label: 'How long have you worked for this employer?',
        profile: 'uk.employmentYears', input: 'text', optional: true,
        note: '年数，如 3 years' },
      { label: 'Monthly income after tax', profile: 'work.monthlySalary', input: 'text', optional: true },
      { label: 'How much money do you have available for your trip?',
        profile: 'uk.fundsBalanceBucket', input: 'select', valueMap: UK_FUNDS_BUCKET,
        note: '与银行流水余额对应' },
    ],
  },
  {
    section: 'uk_history',
    officialTitle: 'Immigration history — UK',
    fields: [
      { label: 'Have you been issued a UK visa before?',
        profile: 'uk.visaHistory', input: 'select', valueMap: UK_VISA_HISTORY },
      { label: 'Have you ever been refused a UK visa?',
        profile: 'uk.ukVisaRefused', input: 'radio', valueMap: UK_YES_NO, optional: true },
      { label: 'Have you ever been refused a visa for any other country?',
        profile: 'uk.otherVisaRefused', input: 'radio', valueMap: UK_YES_NO, optional: true },
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
      { label: "Partner's date of birth", profile: 'family.spouse.dob', input: 'date',
        transform: 'govuk_date', optional: true },
    ],
  },
  {
    section: 'declarations',
    officialTitle: 'Declarations',
    manual: true,
    note: '品行/移民史 Yes/No 声明须本人如实勾选，Htex 不代填。',
    fields: [
      { label: 'Declarations — I have read and will answer truthfully',
        profile: 'security.acknowledged', input: 'radio', valueMap: UK_YES_NO,
        note: '含犯罪记录、移民违规、拒签史等' },
    ],
  },
]

export function buildUkGuide(profile = {}) {
  const guide = buildVisaGuideFromMap({
    fieldMap: UK_FIELD_MAP,
    manualSteps: UK_MANUAL_STEPS,
    version: UK_FIELD_MAP_VERSION,
    verifiedDate: UK_FIELD_MAP_VERIFIED_DATE,
  }, profile)
  guide.meta.country = 'GB'
  return guide
}
