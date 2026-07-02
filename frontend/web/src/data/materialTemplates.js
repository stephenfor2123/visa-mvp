// materialTemplates.js — 材料参考样本数据（多语言）
//
// 3 类核心材料：身份证明 / 财务证明 / 工作证明
// 每类提供中英文对照样本 + 字段占位符 + 各国差异说明
//
// 数据基于 2026-07 公开样本调研：
//   - 中英文在职证明：MBA智库/道客巴巴等多源样本
//   - 中英文银行存款证明：BOC/BoCom 银行官方模板
//   - 户口本/身份证英文翻译：公安局翻译件模板
//   - 申根（德/法/意）vs 英美差异：使领馆官方要求
//
// 字段值用 {{placeholder}} 占位，方便前端高亮显示。

// ---------------------------------------------------------------------------
// 1. 身份证明 — 户口本 / Resident Identity Card / Household Register
// ---------------------------------------------------------------------------
export const IDENTITY_TEMPLATES = {
  zhCN: {
    title: '户口本 / 居民身份证',
    subtitle: '户口本 + 本人页；身份证正反面',
    documentType: '居民身份证 / 户口本',
    samples: [
      {
        name: '居民身份证（正面）',
        fields: [
          { key: '姓名', value: '{{full_name_zh}}' },
          { key: '性别', value: '{{gender_zh}}' },
          { key: '民族', value: '{{ethnicity_zh}}' },
          { key: '出生', value: '{{date_of_birth_zh}}' },
          { key: '住址', value: '{{address_zh}}' },
          { key: '公民身份号码', value: '{{id_number}}' },
        ],
        footer: '签发机关：{{issuing_authority}}  有效期限：{{validity_period}}',
      },
      {
        name: '户口本本人页',
        fields: [
          { key: '姓名', value: '{{full_name_zh}}' },
          { key: '性别', value: '{{gender_zh}}' },
          { key: '出生日期', value: '{{date_of_birth_zh}}' },
          { key: '籍贯', value: '{{place_of_origin}}' },
          { key: '身份证号', value: '{{id_number}}' },
          { key: '与户主关系', value: '{{relationship_to_head}}' },
        ],
        footer: '户主姓名：{{household_head}}  登记日期：{{registration_date}}',
      },
    ],
    tips: [
      '户口本需提供「首页 + 本人页」，集体户可提供户籍证明原件。',
      '身份证需正反面扫描在同一张图，确保四角完整、字迹清晰。',
    ],
  },

  enUS: {
    title: 'Resident Identity Card / Household Register',
    subtitle: 'ID card (both sides) + household register page',
    documentType: "Resident Identity Card / Household Register (Hukou)",
    samples: [
      {
        name: 'Resident Identity Card (Front)',
        fields: [
          { key: 'Name', value: '{{full_name_en}}' },
          { key: 'Sex', value: '{{gender_en}}' },
          { key: 'Nationality', value: '{{ethnicity_en}}' },
          { key: 'Date of Birth', value: '{{date_of_birth_en}}' },
          { key: 'Address', value: '{{address_en}}' },
          { key: 'Citizen Identity Number', value: '{{id_number}}' },
        ],
        footer: 'Issuing Authority: {{issuing_authority_en}}    Period of Validity: {{validity_period_en}}',
      },
      {
        name: 'Household Register (Hukou Ben)',
        fields: [
          { key: 'Name', value: '{{full_name_en}}' },
          { key: 'Sex', value: '{{gender_en}}' },
          { key: 'Date of Birth', value: '{{date_of_birth_en}}' },
          { key: 'Place of Origin', value: '{{place_of_origin_en}}' },
          { key: 'ID Number', value: '{{id_number}}' },
          { key: 'Relationship to Head', value: '{{relationship_to_head_en}}' },
        ],
        footer: 'Household Head: {{household_head_en}}    Registered: {{registration_date_en}}',
      },
    ],
    tips: [
      'Provide the first page of the Hukou Ben (with household head info) plus your own page.',
      'For ID card, scan both sides on one image with all 4 corners visible and text clearly legible.',
    ],
  },
}

// ---------------------------------------------------------------------------
// 2. 财务证明 — 银行存款证明 / Bank Statement / Certificate of Deposit
// ---------------------------------------------------------------------------
export const FINANCIAL_TEMPLATES = {
  zhCN: {
    title: '银行存款证明',
    subtitle: '银行开具的近 6 个月存款证明 + 流水',
    documentType: '银行存款证明 (Certificate of Deposit)',
    samples: [
      {
        name: '银行存款证明（标准版）',
        header: '中国银行 / BANK OF CHINA',
        body: [
          '兹证明 {{applicant_name_zh}} 先生/女士（身份证号 {{id_number}}）',
          '于 {{open_date_zh}} 在我行开户，账号 {{account_no}}。',
          '',
          '截至 {{issue_date_zh}}，账户余额为人民币 {{balance_rmb}} 元（大写：{{balance_zh_words}}）。',
          '此证明有效期：自开具之日起 {{validity_days}} 天。',
        ].join('\n'),
        footer: '银行签章 (Official Seal)        出具日期：{{issue_date_zh}}',
        fields: [
          { key: '申请人', value: '{{applicant_name_zh}}' },
          { key: '账号', value: '{{account_no}}' },
          { key: '账户余额', value: '{{balance_rmb}} 元 / {{balance_usd}} 美元' },
          { key: '出具日期', value: '{{issue_date_zh}}' },
        ],
      },
    ],
    tips: [
      '建议冻结期与行程匹配：美签/申根一般要求覆盖行程全程 + 1 个月缓冲。',
      '余额建议 ≥ 5 万人民币（具体看目的国要求，申根要求较高）。',
      '需打印在银行中英文抬头的信笺纸上，并加盖银行业务章。',
    ],
  },

  enUS: {
    title: 'Bank Statement / Certificate of Deposit Balance',
    subtitle: 'Issued by the bank, last 6 months, with official seal',
    documentType: 'Bank Statement / Certificate of Deposit Balance',
    samples: [
      {
        name: 'Certificate of Deposit Balance (Standard)',
        header: 'BANK OF CHINA',
        body: [
          'CERTIFICATE OF DEPOSIT BALANCE',
          'NO.: {{certificate_no}}',
          'DATE: {{issue_date_en}}',
          '',
          'We hereby certify that, up to {{issue_date_en}} (expiry date),',
          'Mr./Mrs./Ms. {{applicant_name_en}}, holder of ID No. {{id_number}},',
          'has deposit(s) with this bank as the following:',
          '',
          'Account No.: {{account_no}}',
          'Type of Deposit: {{deposit_type_en}}',
          'Currency & Amount: {{currency}} {{balance}}',
          'Deposit Date: {{deposit_date_en}}',
          '',
          'This certificate becomes valid on and after the issuing date and',
          'remains valid until the expiry date. It is issued for the purpose',
          'of verifying the applicant\'s deposit condition for visa application',
          'and not for any other purpose, including but not limited to guarantee.',
        ].join('\n'),
        footer: 'Bank of China, {{branch_name_en}} Branch    (Official Seal)',
        fields: [
          { key: 'Account Holder', value: '{{applicant_name_en}}' },
          { key: 'Account No.', value: '{{account_no}}' },
          { key: 'Balance', value: '{{currency}} {{balance}}' },
          { key: 'Issue Date', value: '{{issue_date_en}}' },
        ],
      },
    ],
    tips: [
      'US / Schengen / UK typically require the deposit to cover the full trip duration plus 1 month buffer.',
      'Recommended balance: ≥ CNY 50,000 (varies by destination; Schengen is stricter).',
      'Must be printed on bank letterhead with both Chinese and English bank names + contact info, with the bank\'s official seal.',
    ],
  },
}

// ---------------------------------------------------------------------------
// 3. 工作证明 — 在职证明 / Employment Certificate / Letter of Employment
// ---------------------------------------------------------------------------
export const EMPLOYMENT_TEMPLATES = {
  zhCN: {
    title: '在职证明 / 工作证明',
    subtitle: '公司抬头纸打印 + 加盖公章 + 领导签字',
    documentType: '在职证明 (Employment Certificate)',
    samples: [
      {
        name: '在职证明（中文标准版）',
        header: '在职证明',
        body: [
          '致：{{embassy_name_zh}}',
          '',
          '兹证明 {{applicant_name_zh}} 先生/女士（身份证号 {{id_number}}，',
          '护照号 {{passport_no}}）自 {{start_date_zh}} 起在我公司工作，',
          '现任 {{department}} {{position_zh}} 职务，月薪人民币 {{monthly_salary_rmb}} 元。',
          '',
          '我公司同意其于 {{depart_date_zh}} 至 {{return_date_zh}} 期间赴 {{destination_country_zh}}',
          '进行 {{visit_purpose_zh}}（共 {{trip_days}} 天），所有费用（包括机票、',
          '住宿、医疗保险及其他费用）由 {{expense_bearer_zh}} 承担。',
          '',
          '我公司保证其在贵国逗留期间遵守当地法律，并按时回国继续任职。',
          '',
          '',
          '{{company_name_zh}}（盖章）',
          '领导签字：{{signer_name_zh}}',
          '签字人职位：{{signer_position_zh}}',
          '电话：{{company_phone}}    传真：{{company_fax}}',
          '地址：{{company_address_zh}}',
          '日期：{{issue_date_zh}}',
        ].join('\n'),
      },
    ],
    tips: [
      '必须用公司正式抬头纸打印，并加盖公司公章（红色圆章）。',
      '签字人不能是申请人本人；最好由 HR 经理或部门负责人签字。',
      '申根签证要求额外附「营业执照副本复印件」加盖公章。',
      '商务签证的访问目的可写 "Business Meeting / Business Cooperation"。',
    ],
  },

  enUS: {
    title: 'Employment Certificate / Letter of Employment',
    subtitle: 'On company letterhead, with company seal and signature',
    documentType: 'Employment Certificate (No Objection Letter)',
    samples: [
      {
        name: 'Employment Certificate (Standard, Schengen / US / UK)',
        header: 'CERTIFICATE',
        body: [
          'Date: {{issue_date_en}}',
          'To: {{embassy_name_en}}',
          '',
          'Dear Sir or Madam,',
          '',
          'This is to certify that Mr./Ms. {{applicant_name_en}}, holder of',
          'China Passport No. {{passport_no}}, has been employed by our company',
          'since {{start_date_en}} as {{position_en}} in the {{department_en}} Department.',
          '',
          'His/Her present monthly salary is RMB {{monthly_salary_rmb}} (approximately',
          'USD {{monthly_salary_usd}}).',
          '',
          'We hereby confirm that the above-mentioned employee will travel to',
          '{{destination_country_en}} from {{depart_date_en}} to {{return_date_en}}',
          '({{trip_days}} days in total) for {{visit_purpose_en}}.',
          '',
          'All costs relating to this trip, including airfare, accommodation,',
          'travel insurance and other personal expenses, will be borne by {{expense_bearer_en}}.',
          '',
          'We guarantee that he/she will abide by the laws and regulations of',
          '{{destination_country_en}} during the stay and will return to China on',
          'schedule. Upon his/her return, we will resume his/her position in our company.',
          '',
          'Your favorable consideration of his/her visa application will be highly',
          'appreciated.',
          '',
          'Yours faithfully,',
          '',
          '{{signer_name_en}}',
          '{{signer_position_en}}',
          '{{company_name_en}}',
          '',
          'Tel: {{company_phone}}    Fax: {{company_fax}}',
          'Address: {{company_address_en}}',
          'Business License No.: {{business_license_no}}',
        ].join('\n'),
      },
    ],
    tips: [
      'Must be printed on company letterhead and stamped with the company\'s red round seal.',
      'The signatory must NOT be the applicant himself/herself; HR Manager or Department Head is preferred.',
      'Schengen visas additionally require a copy of the Business License with company seal.',
      'For business visas, the visit purpose can be "Business Meeting" or "Business Cooperation".',
    ],
  },
}

// ---------------------------------------------------------------------------
// 各国差异说明 — 在面板底部显示
// ---------------------------------------------------------------------------
export const COUNTRY_NOTES = {
  US: {
    name: '美国',
    flag: '🇺🇸',
    notes: [
      '在职证明需写明月薪 + 旅行费用承担方；英文优先，无需公证。',
      '银行存款证明建议 ≥ 5 万人民币，开具日期与面签日 ≤ 1 个月。',
    ],
  },
  UK: {
    name: '英国',
    flag: '🇬🇧',
    notes: [
      '在职证明 + 营业执照副本（中英文版加盖公章）。',
      '银行流水建议近 6 个月，余额稳定 ≥ 5 万人民币。',
    ],
  },
  AU: {
    name: '澳大利亚',
    flag: '🇦🇺',
    notes: [
      '在职证明中需明确职位、年薪、批准假期；建议附公司组织架构。',
      '财务证明：近 3-6 个月银行流水 + 存款证明，余额需覆盖旅行费用。',
    ],
  },
  Schengen: {
    name: '申根（德/法/意/西）',
    flag: '🇪🇺',
    notes: [
      '在职证明要求最严：英文版（如用意大利驻沪总领事馆，需英文；个别国家接受法文/德文）+ 公章 + 签字人职位 + 营业执照号。',
      '准假人不能是申请人本人；建议 HR 经理或副总签字。',
      '存款证明建议冻结 3-6 个月，余额 ≥ 5 万人民币 / 6 个月以上流水。',
    ],
  },
}

// ---------------------------------------------------------------------------
// 大类 → 模板映射（MaterialWizard 用）
// ---------------------------------------------------------------------------
export const TEMPLATE_BY_CATEGORY = {
  identity: IDENTITY_TEMPLATES,
  financial: FINANCIAL_TEMPLATES,
  work: EMPLOYMENT_TEMPLATES,
}

export default {
  IDENTITY_TEMPLATES,
  FINANCIAL_TEMPLATES,
  EMPLOYMENT_TEMPLATES,
  TEMPLATE_BY_CATEGORY,
  COUNTRY_NOTES,
}