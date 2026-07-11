// ds160Enums.js — DS-160 表单所有 select 字段的官方枚举值
// ============================================================================
// W48 v0.2 P1: 之前 mapping 里 5 个国家字段没 valueMap, 靠 fillEngine
// "精确优先再子串"匹配; 现在补齐完整枚举.
//
// 来源策略:
//   - 国家枚举: ISO 3166-1 alpha-2 代码 → DS-160 实际使用的全大写英文名
//     (DS-160 的国家下拉就是 ISO 列表, 但用大写 + 部分国家名变种,
//      例如 CHINA-MAINLAND / CHINA, HONG KONG SAR / CHINA, TAIWAN)
//   - 婚姻状态/性别/护照类型等: US Dept of State DS-160 公开文档
//   - Relationship / Status / Payer: 同 DESIGN-v0.2.md §4
//
// ⚠️ P1 待办:
//   - DS-160 国家列表偶尔会调整(加新独立国家), 需要在运营核对时验证
//   - CHINA 在 DS-160 里是 CHINA / CHINA-MAINLAND / HONG KONG SAR 等多个选项,
//     插件按 Htex 用户的 profile.passport.issueCountry 选最接近的
// ============================================================================

// ---- 国家 (按 ISO 3166-1 alpha-2 排序) ----
// DS-160 实际下拉里, 主要国家用 "CHINA, PEOPLE'S REPUBLIC OF" 这种格式,
// 部分小型属地用 "ANGUILLA" 这种单字. 我们用 DS-160 公开版本最常见的写法.
export const DS160_COUNTRIES = {
  // 字母 A
  AF: 'AFGHANISTAN',
  AX: 'ALAND ISLANDS',
  AL: 'ALBANIA',
  DZ: 'ALGERIA',
  AS: 'AMERICAN SAMOA',
  AD: 'ANDORRA',
  AO: 'ANGOLA',
  AI: 'ANGUILLA',
  AQ: 'ANTARCTICA',
  AG: 'ANTIGUA AND BARBUDA',
  AR: 'ARGENTINA',
  AM: 'ARMENIA',
  AW: 'ARUBA',
  AU: 'AUSTRALIA',
  AT: 'AUSTRIA',
  AZ: 'AZERBAIJAN',
  // B
  BS: 'BAHAMAS',
  BH: 'BAHRAIN',
  BD: 'BANGLADESH',
  BB: 'BARBADOS',
  BY: 'BELARUS',
  BE: 'BELGIUM',
  BZ: 'BELIZE',
  BJ: 'BENIN',
  BM: 'BERMUDA',
  BT: 'BHUTAN',
  BO: 'BOLIVIA',
  BA: 'BOSNIA AND HERZEGOVINA',
  BW: 'BOTSWANA',
  BV: 'BOUVET ISLAND',
  BR: 'BRAZIL',
  IO: 'BRITISH INDIAN OCEAN TERRITORY',
  BN: 'BRUNEI DARUSSALAM',
  BG: 'BULGARIA',
  BF: 'BURKINA FASO',
  BI: 'BURUNDI',
  // C
  KH: 'CAMBODIA',
  CM: 'CAMEROON',
  CA: 'CANADA',
  CV: 'CAPE VERDE',
  KY: 'CAYMAN ISLANDS',
  CF: 'CENTRAL AFRICAN REPUBLIC',
  TD: 'CHAD',
  CL: 'CHILE',
  // ⚠️ DS-160 把中国拆成多个选项: CHINA / CHINA-MAINLAND / HONG KONG SAR
  CN: 'CHINA, PEOPLE\'S REPUBLIC OF',
  CN_MAINLAND: 'CHINA-MAINLAND',
  CN_HK: 'CHINA, HONG KONG SAR',
  CN_MACAU: 'CHINA, MACAU SAR',
  CN_TAIWAN: 'CHINA, TAIWAN',
  CX: 'CHRISTMAS ISLAND',
  CC: 'COCOS ISLANDS',
  CO: 'COLOMBIA',
  KM: 'COMOROS',
  CG: 'CONGO',
  CD: 'CONGO, DEMOCRATIC REPUBLIC OF THE',
  CK: 'COOK ISLANDS',
  CR: 'COSTA RICA',
  CI: 'COTE D\'IVOIRE',
  HR: 'CROATIA',
  CU: 'CUBA',
  CY: 'CYPRUS',
  CZ: 'CZECH REPUBLIC',
  // D
  DK: 'DENMARK',
  DJ: 'DJIBOUTI',
  DM: 'DOMINICA',
  DO: 'DOMINICAN REPUBLIC',
  // E
  EC: 'ECUADOR',
  EG: 'EGYPT',
  SV: 'EL SALVADOR',
  GQ: 'EQUATORIAL GUINEA',
  ER: 'ERITREA',
  EE: 'ESTONIA',
  ET: 'ETHIOPIA',
  // F
  FK: 'FALKLAND ISLANDS',
  FO: 'FAROE ISLANDS',
  FJ: 'FIJI',
  FI: 'FINLAND',
  FR: 'FRANCE',
  GF: 'FRENCH GUIANA',
  PF: 'FRENCH POLYNESIA',
  TF: 'FRENCH SOUTHERN TERRITORIES',
  // G
  GA: 'GABON',
  GM: 'GAMBIA',
  GE: 'GEORGIA',
  DE: 'GERMANY',
  GH: 'GHANA',
  GI: 'GIBRALTAR',
  GR: 'GREECE',
  GL: 'GREENLAND',
  GD: 'GRENADA',
  GP: 'GUADELOUPE',
  GU: 'GUAM',
  GT: 'GUATEMALA',
  GG: 'GUERNSEY',
  GN: 'GUINEA',
  GW: 'GUINEA-BISSAU',
  GY: 'GUYANA',
  // H
  HT: 'HAITI',
  HM: 'HEARD ISLAND AND MCDONALD ISLANDS',
  VA: 'HOLY SEE (VATICAN CITY STATE)',
  HN: 'HONDURAS',
  HK: 'HONG KONG',  // 兼容旧版
  HU: 'HUNGARY',
  // I
  IS: 'ICELAND',
  IN: 'INDIA',
  ID: 'INDONESIA',
  IR: 'IRAN, ISLAMIC REPUBLIC OF',
  IQ: 'IRAQ',
  IE: 'IRELAND',
  IM: 'ISLE OF MAN',
  IL: 'ISRAEL',
  IT: 'ITALY',
  // J
  JM: 'JAMAICA',
  JP: 'JAPAN',
  JE: 'JERSEY',
  JO: 'JORDAN',
  // K
  KZ: 'KAZAKHSTAN',
  KE: 'KENYA',
  KI: 'KIRIBATI',
  KP: 'KOREA, DEMOCRATIC PEOPLE\'S REPUBLIC OF',
  KR: 'KOREA, REPUBLIC OF',
  KW: 'KUWAIT',
  KG: 'KYRGYZSTAN',
  // L
  LA: 'LAO PEOPLE\'S DEMOCRATIC REPUBLIC',
  LV: 'LATVIA',
  LB: 'LEBANON',
  LS: 'LESOTHO',
  LR: 'LIBERIA',
  LY: 'LIBYAN ARAB JAMAHIRIYA',
  LI: 'LIECHTENSTEIN',
  LT: 'LITHUANIA',
  LU: 'LUXEMBOURG',
  // M
  MO: 'MACAO',
  MK: 'MACEDONIA, THE FORMER YUGOSLAV REPUBLIC OF',
  MG: 'MADAGASCAR',
  MW: 'MALAWI',
  MY: 'MALAYSIA',
  MV: 'MALDIVES',
  ML: 'MALI',
  MT: 'MALTA',
  MH: 'MARSHALL ISLANDS',
  MQ: 'MARTINIQUE',
  MR: 'MAURITANIA',
  MU: 'MAURITIUS',
  YT: 'MAYOTTE',
  MX: 'MEXICO',
  FM: 'MICRONESIA, FEDERATED STATES OF',
  MD: 'MOLDOVA, REPUBLIC OF',
  MC: 'MONACO',
  MN: 'MONGOLIA',
  ME: 'MONTENEGRO',
  MS: 'MONTSERRAT',
  MA: 'MOROCCO',
  MZ: 'MOZAMBIQUE',
  MM: 'MYANMAR',
  // N
  NA: 'NAMIBIA',
  NR: 'NAURU',
  NP: 'NEPAL',
  NL: 'NETHERLANDS',
  AN: 'NETHERLANDS ANTILLES',
  NC: 'NEW CALEDONIA',
  NZ: 'NEW ZEALAND',
  NI: 'NICARAGUA',
  NE: 'NIGER',
  NG: 'NIGERIA',
  NU: 'NIUE',
  NF: 'NORFOLK ISLAND',
  MK_NORTH: 'NORTH MACEDONIA',
  MP: 'NORTHERN MARIANA ISLANDS',
  NO: 'NORWAY',
  // O
  OM: 'OMAN',
  // P
  PK: 'PAKISTAN',
  PW: 'PALAU',
  PS: 'PALESTINIAN TERRITORY, OCCUPIED',
  PA: 'PANAMA',
  PG: 'PAPUA NEW GUINEA',
  PY: 'PARAGUAY',
  PE: 'PERU',
  PH: 'PHILIPPINES',
  PN: 'PITCAIRN',
  PL: 'POLAND',
  PT: 'PORTUGAL',
  PR: 'PUERTO RICO',
  QA: 'QATAR',
  // R
  RE: 'REUNION',
  RO: 'ROMANIA',
  RU: 'RUSSIAN FEDERATION',
  RW: 'RWANDA',
  // S
  SH: 'SAINT HELENA',
  KN: 'SAINT KITTS AND NEVIS',
  LC: 'SAINT LUCIA',
  PM: 'SAINT PIERRE AND MIQUELON',
  VC: 'SAINT VINCENT AND THE GRENADINES',
  WS: 'SAMOA',
  SM: 'SAN MARINO',
  ST: 'SAO TOME AND PRINCIPE',
  SA: 'SAUDI ARABIA',
  SN: 'SENEGAL',
  RS: 'SERBIA',
  SC: 'SEYCHELLES',
  SL: 'SIERRA LEONE',
  SG: 'SINGAPORE',
  SK: 'SLOVAKIA',
  SI: 'SLOVENIA',
  SB: 'SOLOMON ISLANDS',
  SO: 'SOMALIA',
  ZA: 'SOUTH AFRICA',
  GS: 'SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS',
  ES: 'SPAIN',
  LK: 'SRI LANKA',
  SD: 'SUDAN',
  SR: 'SURINAME',
  SJ: 'SVALBARD AND JAN MAYEN',
  SZ: 'SWAZILAND',
  SE: 'SWEDEN',
  CH: 'SWITZERLAND',
  SY: 'SYRIAN ARAB REPUBLIC',
  // T
  TW: 'TAIWAN',
  TJ: 'TAJIKISTAN',
  TZ: 'TANZANIA, UNITED REPUBLIC OF',
  TH: 'THAILAND',
  TL: 'TIMOR-LESTE',
  TG: 'TOGO',
  TK: 'TOKELAU',
  TO: 'TONGA',
  TT: 'TRINIDAD AND TOBAGO',
  TN: 'TUNISIA',
  TR: 'TURKEY',
  TM: 'TURKMENISTAN',
  TC: 'TURKS AND CAICOS ISLANDS',
  TV: 'TUVALU',
  // U
  UG: 'UGANDA',
  UA: 'UKRAINE',
  AE: 'UNITED ARAB EMIRATES',
  GB: 'UNITED KINGDOM',
  US: 'UNITED STATES',
  UM: 'UNITED STATES MINOR OUTLYING ISLANDS',
  UY: 'URUGUAY',
  UZ: 'UZBEKISTAN',
  // V
  VU: 'VANUATU',
  VE: 'VENEZUELA',
  VN: 'VIETNAM',
  VG: 'VIRGIN ISLANDS, BRITISH',
  VI: 'VIRGIN ISLANDS, U.S.',
  // W
  WF: 'WALLIS AND FUTUNA',
  EH: 'WESTERN SAHARA',
  // Y
  YE: 'YEMEN',
  // Z
  ZM: 'ZAMBIA',
  ZW: 'ZIMBABWE',
  // 特殊: 无国籍 / 难民
  XX: 'STATELESS',  // 不一定 DS-160 支持, 留作占位
}

// ---- 婚姻状态 ----
export const DS160_MARITAL_STATUS = {
  single: 'SINGLE',
  married: 'MARRIED',
  divorced: 'DIVORCED',
  widowed: 'WIDOWED',
  separated: 'SEPARATED',
}

// ---- 性别 ----
export const DS160_SEX = {
  M: 'MALE',
  F: 'FEMALE',
}

// ---- 护照/旅行证件类型 ----
export const DS160_PASSPORT_TYPE = {
  regular: 'REGULAR',
  official: 'OFFICIAL',
  diplomatic: 'DIPLOMATIC',
  service: 'SERVICE',
  other: 'OTHER',
}

// ---- 旅行目的 (B/C/D/F/H/J/K 类) ----
export const DS160_TRAVEL_PURPOSE = {
  tourism: 'TEMP. BUSINESS PLEASURE VISITOR (B)',
  business: 'TEMP. BUSINESS PLEASURE VISITOR (B)',
  transit: 'TRANSIT (C)',
  crew: 'CREW MEMBER (D)',
  student: 'STUDENT (F)',
  work: 'TEMPORARY WORKER (H)',
  exchange: 'EXCHANGE VISITOR (J)',
  fiance: 'FIANCÉ(E) (K)',
}

// ---- 旅行付款人 ----
export const DS160_PAYER = {
  self: 'SELF',
  other: 'OTHER',
  otherPerson: 'OTHER PERSON',
  presentEmployer: 'PRESENT EMPLOYER',
  preEmployer: 'PREVIOUS EMPLOYER',
}

// ---- 同行人关系 (Companion / US Contact / Relative) ----
export const DS160_RELATION = {
  spouse: 'SPOUSE',
  parent: 'PARENT',
  child: 'CHILD',
  sibling: 'SIBLING',
  otherRelative: 'OTHER RELATIVE',
  friend: 'FRIEND',
  businessAssociate: 'BUSINESS ASSOCIATE',
  employer: 'EMPLOYER',
  hotel: 'HOTEL',  // 仅 US Contact 用
  other: 'OTHER',
}

// ---- 美国亲属身份 ----
export const DS160_RELATIVE_STATUS = {
  usCitizen: 'U.S. CITIZEN',
  lpr: 'U.S. LEGAL PERMANENT RESIDENT (LPR)',
  nonImmigrant: 'U.S. NON-IMMIGRANT',
  other: 'OTHER',
}

// ---- Yes/No radio (True/False boolean) ----
export const DS160_YES_NO = { true: 'YES', false: 'NO' }

// ---- 收集所有 enum 方便批量 import ----
export const DS160_ENUMS = {
  COUNTRIES: DS160_COUNTRIES,
  MARITAL_STATUS: DS160_MARITAL_STATUS,
  SEX: DS160_SEX,
  PASSPORT_TYPE: DS160_PASSPORT_TYPE,
  TRAVEL_PURPOSE: DS160_TRAVEL_PURPOSE,
  PAYER: DS160_PAYER,
  RELATION: DS160_RELATION,
  RELATIVE_STATUS: DS160_RELATIVE_STATUS,
  YES_NO: DS160_YES_NO,
}