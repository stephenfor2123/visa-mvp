# DS-160 真表核对 Checklist (W48 v0.2)

> 用途: 拿着这份 checklist 在真 Chrome 里打开 ceac.state.gov/genniv, 逐项核对字段映射
> 完成后: 把 `frontend/web/src/data/ds160FieldMap.js:24` 的 `DS160_VERIFIED_DATE = null` 改成 `'YYYY-MM-DD'`
> 优先级: **P0** — 上线前必须完成, 不然填的字段可能跟官网对不上

---

## 0. 怎么用这份文档

1. 真 Chrome 加载 `browser-extension/` (chrome://extensions → 开发者模式 → 加载已解压)
2. 打开 `https://ceac.state.gov/genniv/` (你需要先注册个 DS-160 AAID 才能进完整表单; Getting Started 之前用 Htex 拿 code 也行)
3. 走到任一 section 页, 右上角 Htex 面板 + DevTools 一起开
4. 对照下面的每一行:
   - **label** 在官网存在吗? (大小写、空格是否完全一致?)
   - **input type** 对吗? (text / select / radio / date 三连 / textarea)
   - **valueMap** 的值在官网下拉里**确切存在**吗? (MALE / FEMALE 这类)
   - **optional** 判断: 字段为空时, 是否可以勾 "Does Not Apply"?
5. 不一致的: 在 ds160FieldMap.js 直接修, 跑 build script 重生成插件版

---

## 1. 必填字段 (无 optional, 必须有值)

### Personal Information 1

| 字段 (DS160) | Htex profile 路径 | label 是否一致 | input 类型 | valueMap 已知 | 状态 |
|---|---|---|---|---|---|
| Surnames | `identity.surname` | ☐ | text | (upper) | ☐ 通过 |
| Given Names | `identity.givenName` | ☐ | text | (upper) | ☐ 通过 |
| Sex | `identity.sex` | ☐ | select | M→MALE, F→FEMALE | ☐ 通过 |
| Marital Status | `identity.maritalStatus` | ☐ | select | single→SINGLE, married→MARRIED, divorced→DIVORCED, widowed→WIDOWED, separated→SEPARATED | ☐ 通过 |
| Date of Birth | `identity.dob` | ☐ | date 三连 | DD-MMM-YYYY | ☐ 通过 |
| City of Birth | `identity.birthCity` | ☐ | text | — | ☐ 通过 |
| Country/Region of Birth | `identity.birthCountry` | ☐ | select | 国家英文名 (注意是否要"China"而不是"CN") | ☐ 通过 |

### Personal Information 2

| 字段 | Htex 路径 | label | type | valueMap | 状态 |
|---|---|---|---|---|---|
| Country/Region of Origin (Nationality) | `identity.nationality` | ☐ | select | — | ☐ 通过 |
| Do you hold or have you held any nationality other than...? | `identity.hasOtherNationality` | ☐ | radio | true→YES, false→NO | ☐ 通过 |
| National Identification Number | `identity.nationalId` | ☐ | text | — | ☐ 通过 |

### Address and Phone

| 字段 | Htex 路径 | label | type | 状态 |
|---|---|---|---|---|
| Home Address — Street Address | `contact.street` | ☐ | text | ☐ 通过 |
| Home Address — City | `contact.city` | ☐ | text | ☐ 通过 |
| Home Address — Postal Zone/ZIP Code | `contact.postalCode` | ☐ | text | ☐ 通过 |
| Home Address — Country/Region | `contact.country` | ☐ | select | ☐ 通过 |
| Primary Phone Number | `contact.phone` | ☐ | text (带国家码) | ☐ 通过 |
| Email Address | `contact.email` | ☐ | text | ☐ 通过 |

### Passport

| 字段 | Htex 路径 | label | type | valueMap | 状态 |
|---|---|---|---|---|---|
| Passport/Travel Document Type | `passport.type` | ☐ | select | regular→REGULAR, official→OFFICIAL, diplomatic→DIPLOMATIC, service→SERVICE, other→OTHER | ☐ 通过 |
| Passport/Travel Document Number | `passport.number` | ☐ | text (upper) | — | ☐ 通过 |
| Country/Authority that Issued Passport | `passport.issueCountry` | ☐ | select | — | ☐ 通过 |
| City where Issued | `passport.issueCity` | ☐ | text | — | ☐ 通过 |
| Issuance Date | `passport.issueDate` | ☐ | date 三连 | DD-MMM-YYYY | ☐ 通过 |
| Expiration Date | `passport.expiry` | ☐ | date 三连 | DD-MMM-YYYY | ☐ 通过 |

### Travel

| 字段 | Htex 路径 | label | type | valueMap | 状态 |
|---|---|---|---|---|---|
| Purpose of Trip to the U.S. | `travel.purpose` | ☐ | select | tourism/business→TEMP. BUSINESS PLEASURE VISITOR (B), transit→TRANSIT (C), crew→CREW MEMBER (D), student→STUDENT (F), work→TEMPORARY WORKER (H), exchange→EXCHANGE VISITOR (J), fiance→FIANCÉ(E) (K) | ☐ 通过 |
| Have you made specific travel plans? | `travel.hasPlan` | ☐ | radio | true→YES, false→NO | ☐ 通过 |
| Intended Date of Arrival | `travel.arrivalDate` | ☐ | date 三连 | — | ☐ 通过 |
| Intended Length of Stay | `travel.stayLength` | ☐ | text | 必须是 "10 DAYS" 这种格式 | ☐ 通过 |
| Address Where You Will Stay in the U.S. | `travel.usAddress` | ☐ | text | — | ☐ 通过 |
| Person/Entity Paying for Your Trip | `travel.payer` | ☐ | select | self→SELF, other→OTHER, otherPerson→OTHER PERSON, presentEmployer→PRESENT EMPLOYER, preEmployer→PREVIOUS EMPLOYER | ☐ 通过 |

---

## 2. 可选字段 (空 → 自动勾 Does Not Apply)

### Personal Information 1 (条件)

| 字段 | Htex 路径 | label | 备注 |
|---|---|---|---|
| Full Name in Native Alphabet | `identity.nativeName` | ☐ | 没值就勾 Does Not Apply |

### Personal Information 2

| 字段 | Htex 路径 | label | 状态 |
|---|---|---|---|
| Passport Book Number | `passport.bookNumber` | ☐ | ☐ 通过 |
| U.S. Social Security Number | `identity.usSsn` | ☐ | ☐ 通过 |
| U.S. Taxpayer ID Number | `identity.usTaxId` | ☐ | ☐ 通过 |
| Home Address — State/Province | `contact.state` | ☐ | ☐ 通过 |

### Travel Companions (条件: `hasCompanions=true`)

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Companion's Surnames | `travel.companionSurname` | ☐ 通过 |
| Companion's Given Names | `travel.companionGivenName` | ☐ 通过 |
| Companion's Relationship to You | `travel.companionRelation` | ☐ 通过 |

### Previous U.S. Travel (条件: `hasVisited=true`)

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Date of Last Visit | `previous.lastVisitDate` | ☐ 通过 |
| Length of Stay on Last Visit (in days) | `previous.lastVisitStayDays` | ☐ 通过 |

### Previous Visa (条件: `hasVisa=true`)

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Date of Last Visa Issuance | `previous.lastVisaDate` | ☐ 通过 |
| Visa Number | `previous.lastVisaNumber` | ☐ 通过 |

### U.S. Point of Contact

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Organization Name | `usContact.orgName` | ☐ 通过 |
| Relationship to You | `usContact.relation` | ☐ 通过 |
| U.S. Address — State | `usContact.state` | ☐ 通过 |
| U.S. Address — ZIP Code | `usContact.zip` | ☐ 通过 |
| U.S. Phone Number | `usContact.phone` | ☐ 通过 |
| Email Address | `usContact.email` | ☐ 通过 |

### Family — Parents & Children

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Father's Surnames | `family.fatherSurname` | ☐ 通过 |
| Father's Given Names | `family.fatherGivenName` | ☐ 通过 |
| Father's Date of Birth | `family.fatherDob` | ☐ 通过 |
| Is your father in the U.S.? | `family.fatherInUS` | ☐ 通过 |
| Mother's Surnames | `family.motherSurname` | ☐ 通过 |
| Mother's Given Names | `family.motherGivenName` | ☐ 通过 |
| Mother's Date of Birth | `family.motherDob` | ☐ 通过 |
| Is your mother in the U.S.? | `family.motherInUS` | ☐ 通过 |
| Do you have any immediate relatives...? | `family.hasUSRelatives` | ☐ 通过 |

### Family — Relatives (条件: `hasUSRelatives=true`)

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Relative's Surnames | `family.relativeSurname` | ☐ 通过 |
| Relative's Given Names | `family.relativeGivenName` | ☐ 通过 |
| Relative's Relationship to You | `family.relativeRelation` | ☐ 通过 |
| Relative's Status | `family.relativeStatus` | ☐ 通过 |

### Family — Spouse (条件: `maritalStatus='married'`)

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Spouse's Surnames | `family.spouseSurname` | ☐ 通过 |
| Spouse's Given Names | `family.spouseGivenName` | ☐ 通过 |
| Spouse's Date of Birth | `family.spouseDob` | ☐ 通过 |
| Spouse's Nationality | `family.spouseNationality` | ☐ 通过 |

### Work / Education

| 字段 | Htex 路径 | 状态 |
|---|---|---|
| Present Employer or School Name | `work.employer` | ☐ 通过 |
| Employer Address — Street | `work.employerStreet` | ☐ 通过 |
| ... 同 5 个 employer 地址字段 | (略) | ☐ 通过 |
| Employer Phone Number | `work.employerPhone` | ☐ 通过 |
| Monthly Salary in Local Currency | `work.monthlySalary` | ☐ 通过 |
| Briefly describe your duties | `work.duties` | ☐ 通过 |
| Have you attended any educational institutions...? | `work.hasEducation` | ☐ 通过 |
| Name of Institution | `work.schoolName` | ☐ 通过 |
| Course of Study | `work.courseOfStudy` | ☐ 通过 |
| Date of Attendance — From | `work.schoolFrom` | ☐ 通过 |
| Date of Attendance — To | `work.schoolTo` | ☐ 通过 |
| Name of Previous Employer | `work.prevEmployer` | ☐ 通过 |

---

## 3. 手动不代填的 section

| Section | 备注 |
|---|---|
| Security and Background | 5 大类 Yes/No 问题 (Part 1-5), Htex 不代填 |
| Getting Started | 选申请地点 / 创建 AAID / 设安全问题 |
| Photo Upload | 上传符合规格的照片 |
| Review + Sign + Submit | 核对全文 + 电子签名 + 提交 |

这些不在本 checklist 范围, 但**插件必须不替用户做这几步**。

---

## 4. label 匹配细节陷阱

| 陷阱 | 怎么识别 |
|---|---|
| 大小写不一致 (e.g. "Surnames" vs "surnames") | DevTools 直接看 `<label>` 元素的 textContent |
| 多余的空格 (e.g. "Date of  Birth") | copy-paste 进 Notepad 看是否有连续空格 |
| Em-dash vs Hyphen ("Has the U.S. Government ever..." 用 em-dash) | 复制粘贴原始字符, 写 JSON 时保留 |
| Question mark 是否属于 label 的一部分 ("Do you...?:") | 我们的 mapping 通常**包含**问号 (匹配整个问题文本) |
| 子标题 (e.g. "Home Address —" 单独一行) | 通常子标题 + 字段组合在一起, 我们的 anchor 找的是字段前的最近 label |

---

## 5. valueMap 反查流程

如果官网下拉里**找不到** mapping 里写的值:
1. 在官网那个 select 上点开, 截图所有选项
2. 找最接近的英文短语 (e.g. "B-1/B-2" vs "TEMP. BUSINESS PLEASURE VISITOR (B)")
3. 改 `valueMap` 加新键 + 注释指明何时用
4. 跑 `node frontend/web/scripts/build-extension-mapping.mjs` 重生成插件版

---

## 6. 完成后

- [ ] 所有 checkbox 都打了 ✓
- [ ] 改了的 valueMap / label 都同步到 `frontend/web/src/data/ds160FieldMap.js`
- [ ] 跑 `cd frontend/web && node scripts/build-extension-mapping.mjs` 重生成 `browser-extension/src/mapping.js`
- [ ] `DS160_VERIFIED_DATE = 'YYYY-MM-DD'` 改成今天日期
- [ ] commit + push
- [ ] 在测试账号上跑一次完整流程 (注册 → code → redeem → fill → Next × 23)

---

## 7. P1 待办（运营核对中请重点关注）

### 国家下拉 — ✅ **已完成 (W48 v0.2 加)**

`frontend/web/src/data/ds160Enums.js` 新增 `DS160_COUNTRIES` 字典（ISO-2 → DS-160 官方下拉枚举），共 200+ 国家 + 5 个中国变体 (CN / CN_MAINLAND / CN_HK / CN_MACAU / CN_TAIWAN)。

```js
// 已挂到 mapping 里的 6 个 select:
identity.birthCountry, identity.nationality, contact.country,
passport.issueCountry, work.employerCountry, family.spouse.nationality
```

`fillEngine.js` 不变, 走标准 valueMap 精确匹配路径。

⚠️ **运营核对时重点看**：DS-160 公开版本的国家列表偶尔会调整(加新独立国家), 请打开 ceac.state.gov 选 country 字段, 把 ☐ 没出现在我们枚举里的国家告诉我, 我加进去。

### Stay length 大写

已加 `transform: 'upper'`，但**请在 DS-160 上确认**填入 `10 DAYS` 后，DS-160 是否正确识别为 10 天的停留期。某些版本的 DS-160 会要求严格匹配 enum。

### 名拼写有 unicode

`transform: 'upper'` 在 JS 里对越南语 `ễ ẵ ữ ơ ư` / 中文 `王小明` 都是**原样保留**（它们没有 upper/lower 区分），但对德语 `ß` 会**变成 `SS`**（破坏）。**核对时**：如果申请人用德语姓名（极少），这个 transform 会破坏原值 — 我可以加个 `transform: 'ascii_upper'` 选项规避。

### Relationship / Status select 已加 valueMap（刚补）

但**枚举值是否真的存在**在 DS-160 真表上需要核对。DS-160 公开版本可能会加 `NIECE / NEPHEW / UNCLE / AUNT` 等扩展亲属关系，以及 `STUDENT` 这种 status。如果发现对不上，按 §5 加进去。

| profile 存的值 | DS-160 官网下拉值 | 是否能匹配 |
|---|---|---|
| `VN` (ISO 2 字母) | `VIETNAM` | ❌ 不能 |
| `Vietnam` | `VIETNAM` | ✅ 子串匹配 |
| `vietnam` | `VIETNAM` | ✅ (大小写不敏感) |
| `Viet Nam` (有空格) | `VIETNAM` | ✅ 子串 |
| `China` | `CHINA, PEOPLE'S REPUBLIC OF` | ✅ 子串 |

**核对时请确认**：`frontend/web/src/composables/useApplicantProfile.js` 里给这几个字段塞的值是不是国家英文名（`Vietnam` / `China` / `Indonesia`），**不是 ISO 代码 `VN`/`CN`/`ID`**。如果发现是 ISO 代码，告诉我，我加一个完整的 ISO→英文 映射表。

### Stay length 大写

已加 `transform: 'upper'`，但**请在 DS-160 上确认**填入 `10 DAYS` 后，DS-160 是否正确识别为 10 天的停留期。某些版本的 DS-160 会要求严格匹配 enum。

### 名拼写有 unicode

`transform: 'upper'` 在 JS 里对越南语 `ễ ẵ ữ ơ ư` / 中文 `王小明` 都是**原样保留**（它们没有 upper/lower 区分），但对德语 `ß` 会**变成 `SS`**（破坏）。**核对时**：如果申请人用德语姓名（极少），这个 transform 会破坏原值 — 我可以加个 `transform: 'ascii_upper'` 选项规避。

### Relationship / Status select 已加 valueMap（刚补）

但**枚举值是否真的存在**在 DS-160 真表上需要核对。DS-160 公开版本可能会加 `NIECE / NEPHEW / UNCLE / AUNT` 等扩展亲属关系，以及 `STUDENT` 这种 status。如果发现对不上，按 §5 加进去。