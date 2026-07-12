// ds160FieldMap.js — DS-160 字段映射(单一权威源)
// =============================================================================
// 这份映射是"引导式填写单"和"浏览器插件"共用的唯一数据源。
// 官网改版时，只改这一份 → 两处同时更新(构建脚本 build-extension-mapping.js
// 把这份转成 browser-extension/src/mapping.js 的 IIFE classic script)。
//
// 设计铁律:
//   1. 锚"字段标签"(label)，不锚页码 —— 官网挪动字段也不误导。
//   2. 带 DS160_VERSION + VERIFIED_DATE —— 透明，用户知道对应哪版、何时核对。
//   3. 条件字段用 `when` —— 只对符合条件的用户展示(单身不出现配偶栏)。
//      when 是声明式 DSL,见 ds160When.js。web 端用 evaluateWhen,
//      插件端在构建时编译成函数(compileWhenToFn)。
//   4. 可选字段用 `optional` —— 空值时提示"勾 Does Not Apply"，不算缺失。
//   5. 必填字段值缺失时，生成器标"待补"，绝不瞎填。
//   6. 门户语言: DS-160 官网是英文 — label/valueMap 的值必须是 ceac 下拉里的英文文案;
//      Htex App 的 i18n(中/越/印尼)只用于 UI 提示(note)，绝不直接写入官网表单。
//      select/radio 若 valueMap 无法解析档案值 → 标待补,不 pass-through 原始文本。
//
// ⚠️ v0 草稿:下面的字段标签/下拉值是按公开 DS-160 结构整理的**初稿**，
//    正式启用前必须对着 ceac.state.gov 真表逐条核对一遍(这正是签证工具
//    的固有维护成本)。核对完更新 VERIFIED_DATE。
// =============================================================================

import { evaluateWhen } from './ds160When.js'
import {
  DS160_COUNTRIES,
  DS160_MARITAL_STATUS,
  DS160_SEX,
  DS160_PASSPORT_TYPE,
  DS160_TRAVEL_PURPOSE,
  DS160_PAYER,
  DS160_RELATION,
  DS160_RELATIVE_STATUS,
  DS160_YES_NO,
} from './ds160Enums.js'

export const DS160_VERSION = '2026.3'
export const DS160_VERIFIED_DATE = null // ⚠️ 尚未对真表核对；核对通过后填日期(如 '2026-07-03')

// 字段属性:
//   label      官网那个框的英文标签(锚点)
//   profile    档案里的取值路径(点分)
//   input      text(输入) / select(下拉) / date(日-月-年) / radio(单选) / textarea
//   transform  upper(转全大写) / date(转官网 DD-MMM-YYYY)
//   valueMap   档案值 → 官网下拉/单选的确切文案
//   note       给用户的提示(常见坑)
//   optional   true=此栏可为空；空时提示 whenEmpty，且不计入"待补"
//   whenEmpty  可选栏为空时的提示文案(默认 'Does Not Apply')
//   when       声明式 DSL(见 ds160When.js)。不写=总是展示
//   manual     true=此 section 不代填,仅在引导单里提示
export const DS160_FIELD_MAP = [
  {
    section: 'personal1',
    officialTitle: 'Personal Information 1',
    fields: [
      { label: 'Surnames', profile: 'identity.surname', input: 'text', transform: 'upper', note: '护照上的姓(拼音全大写)' },
      { label: 'Given Names', profile: 'identity.givenName', input: 'text', transform: 'upper', note: '护照上的名(拼音全大写)' },
      { label: 'Full Name in Native Alphabet', profile: 'identity.nativeName', input: 'text', optional: true,
        note: '中文/越南语/印尼语原名；确实没有则勾 "Does Not Apply"' },
      { label: 'Sex', profile: 'identity.sex', input: 'select',
        valueMap: { M: 'MALE', F: 'FEMALE' } },
      { label: 'Marital Status', profile: 'identity.maritalStatus', input: 'select',
        valueMap: { single: 'SINGLE', married: 'MARRIED', divorced: 'DIVORCED', widowed: 'WIDOWED', separated: 'SEPARATED' },
        note: 'SEPARATED(分居)也在选项里' },
      { label: 'Date of Birth', profile: 'identity.dob', input: 'date', transform: 'date', note: '官网格式 日-月缩写-年' },
      { label: 'City of Birth', profile: 'identity.birthCity', input: 'text' },
      { label: 'Country/Region of Birth', profile: 'identity.birthCountry', input: 'select',
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 (VN/ID/CN/...) → DS-160 官方下拉枚举' },
    ],
  },
  {
    section: 'personal2',
    officialTitle: 'Personal Information 2',
    fields: [
      { label: 'Country/Region of Origin (Nationality)', profile: 'identity.nationality', input: 'select',
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 → DS-160 官方下拉枚举' },
      { label: 'Do you hold or have you held any nationality other than the one indicated above?',
        profile: 'identity.hasOtherNationality', input: 'radio', valueMap: { true: 'YES', false: 'NO' } },
      { label: 'National Identification Number', profile: 'identity.nationalId', input: 'text', optional: true,
        note: '身份证号/公民号；没有则勾 "Does Not Apply"' },
      { label: 'U.S. Social Security Number', profile: 'identity.usSsn', input: 'text', optional: true },
      { label: 'U.S. Taxpayer ID Number', profile: 'identity.usTaxId', input: 'text', optional: true },
    ],
  },
  {
    section: 'address_phone',
    officialTitle: 'Address and Phone',
    fields: [
      { label: 'Home Address — Street Address', profile: 'contact.street', input: 'text' },
      { label: 'Home Address — City', profile: 'contact.city', input: 'text' },
      { label: 'Home Address — State/Province', profile: 'contact.state', input: 'text', optional: true },
      { label: 'Home Address — Postal Zone/ZIP Code', profile: 'contact.postalCode', input: 'text', optional: true },
      { label: 'Home Address — Country/Region', profile: 'contact.country', input: 'select',
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 → DS-160 官方下拉枚举' },
      { label: 'Primary Phone Number', profile: 'contact.phone', input: 'text', note: '带国家码，如 +84... +62... +86...' },
      { label: 'Email Address', profile: 'contact.email', input: 'text' },
    ],
  },
  {
    section: 'passport',
    officialTitle: 'Passport',
    fields: [
      { label: 'Passport/Travel Document Type', profile: 'passport.type', input: 'select',
        valueMap: { regular: 'REGULAR', official: 'OFFICIAL', diplomatic: 'DIPLOMATIC', service: 'SERVICE', other: 'OTHER' },
        note: '普通因私护照选 REGULAR' },
      { label: 'Passport/Travel Document Number', profile: 'passport.number', input: 'text', transform: 'upper' },
      { label: 'Passport Book Number', profile: 'passport.bookNumber', input: 'text', optional: true,
        note: '多数护照没有此号 → 勾 "Does Not Apply"' },
      { label: 'Country/Authority that Issued Passport', profile: 'passport.issueCountry', input: 'select',
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 → DS-160 官方下拉枚举' },
      { label: 'City where Issued', profile: 'passport.issueCity', input: 'text' },
      { label: 'Issuance Date', profile: 'passport.issueDate', input: 'date', transform: 'date' },
      { label: 'Expiration Date', profile: 'passport.expiry', input: 'date', transform: 'date', note: '需距行程 ≥6 个月' },
    ],
  },
  {
    section: 'travel',
    officialTitle: 'Travel',
    fields: [
      { label: 'Purpose of Trip to the U.S.', profile: 'travel.purpose', input: 'select',
        valueMap: {
          tourism: 'TEMP. BUSINESS PLEASURE VISITOR (B)',
          business: 'TEMP. BUSINESS PLEASURE VISITOR (B)',
          transit: 'TRANSIT (C)',
          crew: 'CREW MEMBER (D)',
          student: 'STUDENT (F)',
          work: 'TEMPORARY WORKER (H)',
          exchange: 'EXCHANGE VISITOR (J)',
          fiance: 'FIANCÉ(E) (K)',
        },
        note: '旅游/商务短期访问选 B 类；选完后会冒 sub-question 选具体子项(代填只到这一层)' },
      { label: 'Have you made specific travel plans?', profile: 'travel.hasPlan', input: 'radio',
        valueMap: { true: 'YES', false: 'NO' }, note: '已订机票酒店选 YES' },
      { label: 'Intended Date of Arrival', profile: 'travel.arrivalDate', input: 'date', transform: 'date' },
      { label: 'Intended Length of Stay', profile: 'travel.stayLength', input: 'text', transform: 'upper', note: '如 10 DAYS(纯数字 + DAYS,大写)' },
      { label: 'Address Where You Will Stay in the U.S.', profile: 'travel.usAddress', input: 'text', note: '酒店名 + 地址' },
      { label: 'Person/Entity Paying for Your Trip', profile: 'travel.payer', input: 'select',
        valueMap: { self: 'SELF', other: 'OTHER', otherPerson: 'OTHER PERSON', presentEmployer: 'PRESENT EMPLOYER', preEmployer: 'PREVIOUS EMPLOYER' },
        note: '自费选 SELF' },
    ],
  },
  {
    // 条件页:只有已婚才出现(避免给单身用户填配偶信息 → 防误导)
    section: 'family_spouse',
    officialTitle: 'Family — Spouse',
    when: { eq: ['identity.maritalStatus', 'married'] },
    fields: [
      { label: "Spouse's Surnames", profile: 'family.spouse.surname', input: 'text', transform: 'upper' },
      { label: "Spouse's Given Names", profile: 'family.spouse.givenName', input: 'text', transform: 'upper' },
      { label: "Spouse's Date of Birth", profile: 'family.spouse.dob', input: 'date', transform: 'date' },
      { label: "Spouse's Nationality", profile: 'family.spouse.nationality', input: 'select',
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 → DS-160 官方下拉枚举' },
    ],
  },
  {
    // 5. Travel Companions — 同行人
    section: 'travel_companions',
    officialTitle: 'Travel Companions',
    fields: [
      { label: 'Are there any other persons traveling with you?',
        profile: 'travel.hasCompanions', input: 'radio', valueMap: { true: 'YES', false: 'NO' },
        note: '勾 NO 可直接跳过同行人姓名/关系字段' },
      { label: "Companion's Surnames", profile: 'travel.companion.surname', input: 'text', transform: 'upper', optional: true,
        when: { eq: ['travel.hasCompanions', true] } },
      { label: "Companion's Given Names", profile: 'travel.companion.givenName', input: 'text', transform: 'upper', optional: true,
        when: { eq: ['travel.hasCompanions', true] } },
      { label: "Companion's Relationship to You", profile: 'travel.companion.relation', input: 'select', optional: true,
        when: { eq: ['travel.hasCompanions', true] },
        valueMap: {
          spouse: 'SPOUSE',
          parent: 'PARENT',
          child: 'CHILD',
          sibling: 'SIBLING',
          otherRelative: 'OTHER RELATIVE',
          friend: 'FRIEND',
          businessAssociate: 'BUSINESS ASSOCIATE',
          employer: 'EMPLOYER',
          other: 'OTHER',
        },
        note: 'DS-160 官方枚举: SPOUSE / PARENT / CHILD / SIBLING / OTHER RELATIVE / FRIEND / BUSINESS ASSOCIATE / EMPLOYER / OTHER' },
    ],
  },
  {
    // 6. Previous U.S. Travel — 5 年内访美历史
    section: 'previous_us_travel',
    officialTitle: 'Previous U.S. Travel',
    fields: [
      { label: 'Have you ever been in the U.S.?',
        profile: 'previous.hasVisited', input: 'radio', valueMap: { true: 'YES', false: 'NO' },
        note: '5 年内或一生中任意一次入境都要填' },
      { label: 'Date of Last Visit', profile: 'previous.lastVisitDate', input: 'date', transform: 'date', optional: true,
        when: { eq: ['previous.hasVisited', true] } },
      { label: 'Length of Stay on Last Visit (in days)', profile: 'previous.lastVisitStayDays', input: 'text', optional: true,
        when: { eq: ['previous.hasVisited', true] }, note: '纯数字,例如 10' },
      { label: 'Have you ever been issued a U.S. Visa?',
        profile: 'previous.hasVisa', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true },
      { label: 'Date of Last Visa Issuance', profile: 'previous.lastVisaDate', input: 'date', transform: 'date', optional: true,
        when: { eq: ['previous.hasVisa', true] } },
      { label: 'Visa Number', profile: 'previous.lastVisaNumber', input: 'text', transform: 'upper', optional: true,
        when: { eq: ['previous.hasVisa', true] },
        note: '8 位红色数字,旧签证右下角' },
      { label: 'Have you ever been refused a U.S. Visa or refused admission to the U.S.?',
        profile: 'previous.hasRefused', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true,
        note: '如实填写,后续解释说明在 Security/Background' },
    ],
  },
  {
    // 7. U.S. Point of Contact — 美国联系人/邀请方
    section: 'us_contact',
    officialTitle: 'U.S. Point of Contact',
    fields: [
      { label: 'Contact Person Surnames', profile: 'usContact.personSurname', input: 'text', transform: 'upper' },
      { label: 'Contact Person Given Names', profile: 'usContact.personGivenName', input: 'text', transform: 'upper' },
      { label: 'Organization Name', profile: 'usContact.orgName', input: 'text', optional: true,
        note: '如酒店名称 / 邀请公司 / 学校' },
      { label: 'Relationship to You', profile: 'usContact.relation', input: 'select', optional: true,
        valueMap: {
          spouse: 'SPOUSE',
          parent: 'PARENT',
          child: 'CHILD',
          sibling: 'SIBLING',
          otherRelative: 'OTHER RELATIVE',
          friend: 'FRIEND',
          businessAssociate: 'BUSINESS ASSOCIATE',
          employer: 'EMPLOYER',
          hotel: 'HOTEL',
          other: 'OTHER',
        },
        note: 'DS-160 官方枚举: 同 Companion 的 Relationship, 多 HOTEL (美国联系人是酒店时)' },
      { label: 'U.S. Address — Street Address', profile: 'usContact.street', input: 'text' },
      { label: 'U.S. Address — City', profile: 'usContact.city', input: 'text' },
      { label: 'U.S. Address — State', profile: 'usContact.state', input: 'text', optional: true,
        note: '华盛顿特区 / 州代码两字母' },
      { label: 'U.S. Address — ZIP Code', profile: 'usContact.zip', input: 'text', optional: true },
      { label: 'U.S. Phone Number', profile: 'usContact.phone', input: 'text',
        note: '带国家码 +1' },
      { label: 'Email Address', profile: 'usContact.email', input: 'text', optional: true },
    ],
  },
  {
    // 8. Family — 父母 + 子女(除配偶外)
    section: 'family_parents_children',
    officialTitle: 'Family — Parents & Children',
    fields: [
      { label: "Father's Surnames", profile: 'family.father.surname', input: 'text', transform: 'upper', optional: true,
        note: '不知道填 "Does Not Apply"' },
      { label: "Father's Given Names", profile: 'family.father.givenName', input: 'text', transform: 'upper', optional: true },
      { label: "Father's Date of Birth", profile: 'family.father.dob', input: 'date', transform: 'date', optional: true },
      { label: 'Is your father in the U.S.?',
        profile: 'family.father.inUS', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true },
      { label: "Mother's Surnames", profile: 'family.mother.surname', input: 'text', transform: 'upper', optional: true },
      { label: "Mother's Given Names", profile: 'family.mother.givenName', input: 'text', transform: 'upper', optional: true },
      { label: "Mother's Date of Birth", profile: 'family.mother.dob', input: 'date', transform: 'date', optional: true },
      { label: 'Is your mother in the U.S.?',
        profile: 'family.mother.inUS', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true },
      { label: 'Do you have any immediate relatives (other than spouse) in the U.S.?',
        profile: 'family.hasUSRelatives', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true,
        note: '父母/子女/兄弟姐妹 等直系亲属' },
      { label: "Relative's Surnames", profile: 'family.relative.surname', input: 'text', transform: 'upper', optional: true,
        when: { eq: ['family.hasUSRelatives', true] } },
      { label: "Relative's Given Names", profile: 'family.relative.givenName', input: 'text', transform: 'upper', optional: true,
        when: { eq: ['family.hasUSRelatives', true] } },
      { label: "Relative's Relationship to You", profile: 'family.relative.relation', input: 'select', optional: true,
        when: { eq: ['family.hasUSRelatives', true] },
        valueMap: {
          spouse: 'SPOUSE',
          parent: 'PARENT',
          child: 'CHILD',
          sibling: 'SIBLING',
          otherRelative: 'OTHER RELATIVE',
        },
        note: 'DS-160 官方枚举: 直系亲属 (父母/配偶/子女/兄弟姐妹) + OTHER RELATIVE' },
      { label: "Relative's Status (e.g., U.S. Citizen, LPR)", profile: 'family.relative.status', input: 'select', optional: true,
        when: { eq: ['family.hasUSRelatives', true] },
        valueMap: {
          usCitizen: 'U.S. CITIZEN',
          lpr: 'U.S. LEGAL PERMANENT RESIDENT (LPR)',
          nonImmigrant: 'U.S. NON-IMMIGRANT',
          other: 'OTHER',
        },
        note: 'DS-160 官方枚举: U.S. CITIZEN / U.S. LEGAL PERMANENT RESIDENT (LPR) / U.S. NON-IMMIGRANT / OTHER' },
    ],
  },
  {
    // 9. Work / Education / Training — 职业与教育背景
    section: 'work_education',
    officialTitle: 'Work / Education / Training',
    fields: [
      { label: 'Primary Occupation', profile: 'work.occupation', input: 'text',
        note: '学生/教师/工程师/医生/无业 等' },
      { label: 'Present Employer or School Name', profile: 'work.employer', input: 'text', optional: true,
        note: '无业/退休 填 "Does Not Apply"' },
      { label: 'Employer Address — Street', profile: 'work.employerStreet', input: 'text', optional: true },
      { label: 'Employer Address — City', profile: 'work.employerCity', input: 'text', optional: true },
      { label: 'Employer Address — State/Province', profile: 'work.employerState', input: 'text', optional: true },
      { label: 'Employer Address — Postal Zone', profile: 'work.employerPostal', input: 'text', optional: true },
      { label: 'Employer Address — Country/Region', profile: 'work.employerCountry', input: 'select', optional: true,
        valueMap: DS160_COUNTRIES, note: 'ISO-2 代码 → DS-160 官方下拉枚举' },
      { label: 'Employer Phone Number', profile: 'work.employerPhone', input: 'text', optional: true },
      { label: 'Monthly Salary in Local Currency (if employed)', profile: 'work.monthlySalary', input: 'text', optional: true },
      { label: 'Briefly describe your duties', profile: 'work.duties', input: 'textarea', optional: true,
        note: '一两句中文/英文都可' },
      { label: 'Have you attended any educational institutions at a secondary level or above?',
        profile: 'work.hasEducation', input: 'radio', valueMap: { true: 'YES', false: 'NO' }, optional: true },
      { label: 'Name of Institution', profile: 'work.schoolName', input: 'text', optional: true,
        when: { eq: ['work.hasEducation', true] } },
      { label: 'Course of Study', profile: 'work.courseOfStudy', input: 'text', optional: true,
        when: { eq: ['work.hasEducation', true] } },
      { label: 'Date of Attendance — From', profile: 'work.schoolFrom', input: 'date', transform: 'date', optional: true,
        when: { eq: ['work.hasEducation', true] } },
      { label: 'Date of Attendance — To', profile: 'work.schoolTo', input: 'date', transform: 'date', optional: true,
        when: { eq: ['work.hasEducation', true] } },
      { label: 'Name of Previous Employer (if applicable)', profile: 'work.prevEmployer', input: 'text', optional: true },
    ],
  },
  {
    // 10. Security and Background — 1, 2, 3, 4, 5 五大块 Yes/No(共 30+ 题)
    // 这是 Htex **不代填**的 section — 用户必须自己如实回答。
    // 字段只做"是否愿意在线预览"勾选,具体题引导用户去 ceac.state.gov 答。
    section: 'security_background',
    officialTitle: 'Security and Background',
    manual: true,
    note: '此 section 涉及法律/健康/犯罪/移民历史等问题,必须由申请人本人在 ceac.state.gov 上如实回答。Htex 仅做"已读/确认"标记,不做代填。',
    fields: [
      { label: 'Security & Background — 已阅读并理解所有 5 大类问题',
        profile: 'security.acknowledged', input: 'radio', valueMap: { true: 'YES', false: 'NO' },
        note: 'Part 1: Disease / Health / Addictive; Part 2: Criminal / Security; Part 3: Immigration / Visa fraud; Part 4: Public benefit / Removable; Part 5: Misc. 详见 DS-160 官方源。' },
    ],
  },
]

// 官网天然做不了 / 必须用户本人完成的部分 —— 引导单末尾提示，不代填
export const DS160_MANUAL_STEPS = [
  'Getting Started 页:选申请地点、创建 Application ID、设置安全问题(请自己记牢)',
  'U.S. Point of Contact 页:填美国联系人/单位(如酒店或邀请方)',
  'Work/Education 页:填职业、雇主/学校信息',
  'Security and Background 页:一系列 Yes/No 背景问题(必须本人如实回答)',
  '上传符合规格的照片',
  '核对全部内容 → 电子签名 → 提交',
]

// =============================================================================
// 生成引导单 — web 端专用
// 把声明式 when 评估后,产出"用户在引导单里看到什么"的结构
// =============================================================================
const MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']

function _get(o, p) { return p.split('.').reduce((a, k) => a == null ? undefined : a[k], o) }
function _isEmpty(v) {
  if (v === undefined || v === null) return true
  if (typeof v === 'boolean') return false
  return String(v).trim() === ''
}

function _coerceBoolForValueMap(raw) {
  if (raw === true || raw === false) return raw
  const s = String(raw).trim().toLowerCase()
  if (s === 'true' || s === 'yes' || s === 'y' || s === '1') return true
  if (s === 'false' || s === 'no' || s === 'n' || s === '0') return false
  return raw
}

/** ISO-2 / 英文名 / 已是 DS-160 枚举 → 下拉可匹配的文案 */
function _resolveValueMap(raw, valueMap) {
  if (!valueMap || _isEmpty(raw)) return raw
  if (valueMap[raw] !== undefined) return valueMap[raw]
  if (valueMap[String(raw)] !== undefined) return valueMap[String(raw)]
  const coerced = _coerceBoolForValueMap(raw)
  if (coerced !== raw && valueMap[coerced] !== undefined) return valueMap[coerced]
  const up = String(raw).trim().toUpperCase()
  for (const v of Object.values(valueMap)) {
    if (String(v).toUpperCase() === up) return v
  }
  for (const v of Object.values(valueMap)) {
    if (String(v).toUpperCase().includes(up) || up.includes(String(v).toUpperCase())) return v
  }
  return raw
}

/** select/radio 的 valueMap 是否成功解析为官网枚举(防 i18n/脏值 pass-through) */
function _isPortalEnumResolved(raw, valueMap) {
  if (!valueMap || _isEmpty(raw)) return true
  if (valueMap[raw] !== undefined) return true
  if (valueMap[String(raw)] !== undefined) return true
  const coerced = _coerceBoolForValueMap(raw)
  if (coerced !== raw && valueMap[coerced] !== undefined) return true
  const up = String(raw).trim().toUpperCase()
  for (const v of Object.values(valueMap)) {
    if (String(v).toUpperCase() === up) return true
  }
  for (const v of Object.values(valueMap)) {
    const vu = String(v).toUpperCase()
    if (vu.includes(up) || up.includes(vu)) return true
  }
  return false
}

function _toDs160Date(raw) {
  const m = String(raw).trim().match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
  if (!m) return String(raw)
  const mon = MONTHS[+m[2] - 1]
  if (!mon) return String(raw)
  return String(+m[3]).padStart(2, '0') + '-' + mon + '-' + m[1]
}

function _resolveField(f, profile) {
  const raw = _get(profile, f.profile)
  if (_isEmpty(raw)) {
    if (f.optional) return { label: f.label, profile: f.profile, input: f.input, action: 'na', value: 'Does Not Apply', missing: false, optional: true, note: f.note }
    return { label: f.label, profile: f.profile, input: f.input, action: 'todo', value: null, missing: true, optional: false, note: f.note }
  }
  let value = _resolveValueMap(raw, f.valueMap)
  if (f.valueMap && (f.input === 'select' || f.input === 'radio') && !_isPortalEnumResolved(raw, f.valueMap)) {
    return {
      label: f.label, profile: f.profile, input: f.input, action: 'todo', value: null,
      missing: true, optional: false, note: f.note,
    }
  }
  if (f.transform === 'upper') value = String(value).toUpperCase()
  else if (f.transform === 'date') value = _toDs160Date(value)
  return { label: f.label, profile: f.profile, input: f.input, action: 'fill', value, missing: false, optional: !!f.optional, note: f.note }
}

export function buildDs160Guide(profile = {}) {
  let missingCount = 0
  const sections = DS160_FIELD_MAP
    .filter(sec => !sec.manual && (!sec.when || evaluateWhen(sec.when, profile)))
    .map(sec => {
      const steps = sec.fields
        .filter(f => !f.when || evaluateWhen(f.when, profile))
        .map(f => {
          const s = _resolveField(f, profile)
          if (s.missing) missingCount++
          return s
        })
      return { section: sec.section, officialTitle: sec.officialTitle, manual: !!sec.manual, steps }
    })
  return {
    meta: { version: DS160_VERSION, verifiedDate: DS160_VERIFIED_DATE },
    sections,
    missingCount,
  }
}