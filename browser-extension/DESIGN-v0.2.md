# Htex DS-160 辅助填充插件 · 设计与实现文档 v0.2

> 版本: v0.2(2026-07-09) · 状态:**已拍板, 待实现**
> 适用范围:美签 DS-160 辅助填充 + 美签流程寻路指引
> 上一版: [DESIGN.md](./DESIGN.md) v0.1(同机 postMessage 方案,作废)

---

## 0. TL;DR

一个 Manifest V3 浏览器扩展 + Htex 后端一对 API,给东南亚/中国用户申请美签提供两类帮助:

1. **辅助填充 DS-160** —— 用户在 Htex Web 完成诊断 + 填好档案 → 拿到 **12 位 code** → 在 Chrome 插件里粘贴 code → 插件到 `ceac.state.gov` **辅助填表**(用户只需核对 + 自己点 Next/Submit)。
2. **流程寻路(领路狗)** —— 美签是跨多站点的迷宫(DS-160 → 交费/预约 → 面签),插件检测用户在哪一步,把藏很深的入口按钮直接圈出来 + 提示下一步去哪。

### 三条设计红线(v0.1 立, v0.2 强化)

- **辅助,不是全自动 RPA** —— 填字段/指路/提示登录,**不替用户点政府站的提交/支付/登录**(合规 + 抗脆 + 安全)。
- **Code 是档案指纹,不是鉴权令牌** —— 12 位 code 跟订单档案的内容绑死,档案变 → code 自动换 → 老 code 在插件侧直接失效,**自带版本控制,防"老数据填到新表单"**。
- **数据本地优先** —— 插件只在 `chrome.storage.session` 暂存档案(关浏览器即清),后端不缓存用户档案原文,只存 fingerprint + order_id 反向索引。

---

## 1. 目标与非目标

### 目标

- 大幅减少用户在 DS-160 官网的手工录入(把录入前移到体验更好的 Htex Web)。
- 帮用户**找到**美签流程里那些藏得很深的入口。
- 一套字段映射,**引导单(在 Htex Web 里展示)与插件(在 DS-160 填表)共用**,改一处两处生效(已由 `build-extension-mapping.mjs` 保证)。
- 单人先行,数据契约按多申请人前向兼容。

### 非目标(明确不做)

- ❌ 不做无人值守全自动提交(照片、安全问题、CAPTCHA、最终提交都留给用户)。
- ❌ 不替用户在政府站点击"提交/支付"。
- ❌ 不替用户登录 DS-160(政府站密码不经插件中转,信任边界最清)。
- ❌ 不把用户证件/资料原文上传到我方服务器(后端只存 fingerprint + 反向索引)。

---

## 2. 总体架构(v0.2 重画)

```
┌──────────────────────┐                                                  ┌───────────────────────────────┐
│  💻 Htex Web           │   用户操作                                       │  🧩 浏览器插件(MV3)             │
│                      │ ─────────────▶                                  │                                 │
│  /orders/{id} 详情页  │                                                  │  popup.html (输入 12 位 code)    │
│  "去 DS-160 填表"按钮 │                                                  │      │                          │
│       │              │                                                  │      ▼                          │
│       ▼              │   POST /api/v2/ds160/code                         │  POST /api/v2/ds160/code/redeem │
│  POST /code          │ ──────────────────────────────▶ ┌─────────────┐  │      │                          │
│       │              │ ◀── {code, fingerprint, ts} ───── │             │ ◀────┘                          │
│       ▼              │                                  │  Htex 后端   │  │      ▼                          │
│  展示 code + 复制    │                                  │  (FastAPI)   │  │  校验 fingerprint               │
│  "档案更新会自动换码" │                                  │             │  │      │ 通过                      │
└──────────────────────┘                                  │  ┌──────┐    │  │      ▼                          │
                                                          │  │order │    │  │  chrome.storage.session        │
                                                          │  │表+新 │    │  │  (profile + mapping + meta)    │
                                                          │  │增字段│    │  │      │                          │
                                                          │  └──────┘    │  │      ▼                          │
                                                          │             │  │  ceac.state.gov/genniv:         │
                                                          │             │  │  填充引擎 + 填充面板             │
                                                          │             │  │  寻路提示 + 高亮                 │
                                                          │             │  │      │                          │
                                                          │             │  │      ▼                          │
                                                          │             │  │  预约站:寻路提示 + 高亮          │
                                                          └─────────────┘  └───────────────────────────────┘
                                                                                       │
                                                                       填 / 指路 / 提示登录
                                                                                       ▼
                                                                  ceac.state.gov(DS-160) · ustraveldocs / usvisa-info(预约)
```

### 与 v0.1 的关键差异

| 项 | v0.1 (作废) | v0.2 (当前) |
|---|---|---|
| 数据交接 | App 页面 `postMessage` 同机直传 + 文件导入兜底 | **后端发 12 位 code + 插件 redeem** |
| 数据所有权 | App 页面推送时本地已存一份 | 后端按需下发,关浏览器即清 |
| 多设备 | 同机 + 计划 P2 扫码 E2E | **默认跨设备**(在 PC 装插件即可),扫码 E2E 仍是 P2 |
| 登录 DS-160 | 未涉及 | **插件只提示, 用户自己登** |
| 档案版本控制 | 无 | **code = fingerprint, 档案变 → code 自动换** |
| Mapping 漂移 | 文档说"必须加构建脚本" | 已实现 (`frontend/web/scripts/build-extension-mapping.mjs`) |

---

## 3. 数据模型

### 3.1 ApplicantProfile(沿用 v0.1)

由 `frontend/web/src/composables/useApplicantProfile.js` 从多来源(OrderNew 表单 + 护照 OCR + travelPlan)合并、日期归一而成。缺的字段留空。

```
ApplicantProfile {
  identity   { surname, givenName, nativeName, sex(M/F), maritalStatus,
               dob(ISO), birthCity, birthCountry, nationality, nationalId,
               hasOtherNationality, usSsn?, usTaxId? }
  passport   { type, number, bookNumber, issueCountry, issueCity, issueDate, expiry }
  contact    { street, city, state, postalCode, country, phone, email }
  travel     { purpose, hasPlan, arrivalDate, stayLength, usAddress, payer,
               hasCompanions, companion{...} }
  previous   { hasVisited, lastVisitDate, lastVisitStayDays, hasVisa, lastVisaNumber,
               lastVisaDate, hasRefused }
  usContact  { personSurname, personGivenName, orgName, relation, street,
               city, state, zip, phone, email }
  work       { occupation, employer, employerStreet/City/State/Postal/Country/Phone,
               monthlySalary, duties, hasEducation, schoolName, courseOfStudy,
               schoolFrom, schoolTo, prevEmployer }
  family     { spouse{...}, father{...}, mother{...}, hasUSRelatives, relative{...} }
  security   { acknowledged }
}
```

### 3.2 Order 表新增字段(v0.2 新增)

```python
# backend/app/models/order.py  (新增字段,不影响现有模型)
class Order(Base):
    __tablename__ = "orders"
    id = ...
    user_id = ...
    # ... 既有字段保持不变

    # === v0.2 新增 (DS-160 插件对接) ===
    ds160_code = Column(String(12), nullable=True, index=True)         # 12 位 code (冗余存一份方便按 code 反查)
    ds160_fingerprint = Column(String(64), nullable=True)              # SHA-256 hex of normalized profile snapshot
    ds160_code_issued_at = Column(DateTime(timezone=True), nullable=True)
    ds160_code_consumed_count = Column(Integer, default=0, nullable=False)  # 累计 redeem 次数(审计)
    ds160_last_redeemed_at = Column(DateTime(timezone=True), nullable=True)
```

**字段语义:**

| 字段 | 含义 |
|---|---|
| `ds160_code` | 当前有效的 12 位 code(代码冗余存,主键是 order.id;code 改了直接覆盖) |
| `ds160_fingerprint` | 当前 code 对应的档案指纹,**是 code 的"含金量"** |
| `ds160_code_issued_at` | 首次签发时间(用户看得到,知道这个 code 多久了) |
| `ds160_code_consumed_count` | 累计被插件 redeem 了几次(0 / 1 / N;不是一次性但失败重试要限频) |
| `ds160_last_redeemed_at` | 最近一次 redeem 时间(限频 / 审计用) |

### 3.3 Fingerprint 算法(关键!)

**目的**:用户改任意字段 → 自动产出不同 fingerprint → 老 code 失效。

```python
# backend/app/core/ds160_fingerprint.py (新增, ~30 行)
import hashlib, json
from datetime import date

# 哪些字段进入 fingerprint (顺序敏感! 顺序定下来就不再变)
# 注意:不包含 'updated_at' / 'created_at' / 任何元数据
_FP_FIELDS = [
    ('identity',   ['surname', 'givenName', 'nativeName', 'sex', 'maritalStatus',
                    'dob', 'birthCity', 'birthCountry', 'nationality', 'nationalId',
                    'hasOtherNationality']),
    ('passport',   ['type', 'number', 'bookNumber', 'issueCountry', 'issueCity',
                    'issueDate', 'expiry']),
    ('contact',    ['street', 'city', 'state', 'postalCode', 'country', 'phone', 'email']),
    ('travel',     ['purpose', 'hasPlan', 'arrivalDate', 'stayLength', 'usAddress',
                    'payer', 'hasCompanions',
                    'companion.surname', 'companion.givenName', 'companion.relation']),
    ('previous',   ['hasVisited', 'lastVisitDate', 'lastVisitStayDays', 'hasVisa',
                    'lastVisaNumber', 'lastVisaDate', 'hasRefused']),
    ('usContact',  ['personSurname', 'personGivenName', 'orgName', 'relation',
                    'street', 'city', 'state', 'zip', 'phone', 'email']),
    ('work',       ['occupation', 'employer', 'employerStreet', 'employerCity',
                    'employerState', 'employerPostal', 'employerCountry', 'employerPhone',
                    'monthlySalary', 'duties', 'hasEducation', 'schoolName',
                    'courseOfStudy', 'schoolFrom', 'schoolTo', 'prevEmployer']),
    ('family',     ['spouse.surname', 'spouse.givenName', 'spouse.dob', 'spouse.nationality',
                    'father.surname', 'father.givenName', 'father.dob', 'father.inUS',
                    'mother.surname', 'mother.givenName', 'mother.dob', 'mother.inUS',
                    'hasUSRelatives', 'relative.surname', 'relative.givenName',
                    'relative.relation', 'relative.status']),
]

def _normalize(v):
    """把值标准化到 fingerprint 可比的形式:
       - string  -> str.strip().lower()
       - bool    -> 'true' / 'false'
       - date    -> ISO 'YYYY-MM-DD'
       - None    -> ''
    """
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (date, datetime)): return v.isoformat()[:10]
    return str(v).strip().lower()

def compute_fingerprint(profile: dict) -> str:
    """基于 profile 的规范化快照算 SHA-256,十六进制前 32 位 (128 bits 熵).
       任何字段变化 -> 整个 hash 雪崩 -> 老 code 立刻失效.
    """
    flat = {}
    for section, paths in _FP_FIELDS:
        sec = profile.get(section) or {}
        for p in paths:
            keys = p.split('.')
            v = sec
            for k in keys:
                v = (v or {}).get(k) if isinstance(v, dict) else None
            flat[f'{section}.{p}'] = _normalize(v)
    payload = json.dumps(flat, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]
```

**为什么 fingerprint 进 schema:**
- 它是 code 的"含金量" —— redeem 时必须重算 + 比对,不然 code 只是个静态字符串,失去版本控制意义
- 存数据库省一次反查 applicant 表(快速路径)
- 它**不**包含任何 PII (已经规范化 + 取 hash),就算泄漏也还原不出原始字段

### 3.4 Code 生成

```python
# backend/app/core/ds160_code.py (新增)
import secrets, string

# base32 (Crockford-like, 去除 0/O/1/I/L/U 这些视觉混淆字符)
_ALPHABET = '23456789ABCDEFGHJKMNPQRSTVWXYZ'  # 30 字符
_CODE_LEN = 12

def generate_code() -> str:
    """12 位 base32,~60 bits 熵, 30^12 ≈ 5.3e17."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
```

---

## 4. 核心数据流

### 4.1 签发 code (Htex Web → 后端)

```
[用户:订单详情页] "去 DS-160 填表"按钮
    ↓ click
[Htex 前端]
    POST /api/v2/ds160/code { order_id }
    headers: Authorization: Bearer <session>
    ↓
[Htex 后端]
    1. auth: 当前用户必须拥有该订单 (order.user_id == session.user_id)
    2. 从 order.applicants 加载 profile (复用现有 ApplicantProfile 合成逻辑)
    3. fp_new = compute_fingerprint(profile)
    4. if order.ds160_code and order.ds160_fingerprint == fp_new:
         # 档案没变 → 返回旧 code (幂等)
         return { code, fingerprint, issued_at, unchanged: true }
       else:
         # 档案变了 或 第一次签发 → 生成新 code
         new_code = generate_code()
         order.ds160_code = new_code
         order.ds160_fingerprint = fp_new
         order.ds160_code_issued_at = now()
         order.ds160_code_consumed_count = 0  # 重置 (新 code)
         db.commit()
         return { code, fingerprint, issued_at, unchanged: false }
    ↓
[Htex 前端]
    展示 "12 位 code: ABCD-EFGH-JKLM  [复制]"
    "此 code 对应你当前档案;若在 Htex 修改档案, code 会自动变化"
    "提示用户去 Chrome 插件粘贴"
```

### 4.2 Redeem code (浏览器插件 → 后端)

```
[用户:Chrome 插件 popup] 输入 12 位 code → 点 "Redeem"
    ↓
[插件 popup.js]
    POST /api/v2/ds160/code/redeem { code }
    ↓
[Htex 后端]
    1. 查 order by ds160_code = code
       - 找不到 → 404 CODE_NOT_FOUND
    2. 加载该 order 当前 profile, 重算 fp_now = compute_fingerprint(profile)
       限频: 同一 order 60 秒内最多 5 次 redeem (防爆破)
    3. if order.ds160_fingerprint != fp_now:
         # 用户改了档案但插件拿着老 code
         return 409 ARCHIVE_CHANGED
         body: {
           current_fingerprint: fp_now,
           issued_fingerprint: order.ds160_fingerprint,
           hint: '档案已更新,请回 Htex 拿新 code'
         }
    4. 通过 → 返回:
         {
           order_id,
           profile,                    # 当前档案 (用户回填所需)
           fingerprint: fp_now,         # 插件侧存, 后续可校验
           mapping_version: DS160_VERSION,
           mapping_verified_date: DS160_VERIFIED_DATE,  # 透明
         }
    5. 审计:
       order.ds160_code_consumed_count += 1
       order.ds160_last_redeemed_at = now()
       db.commit()
    ↓
[插件 background.js]
    chrome.storage.session.set({
      htex_profile: profile,
      htex_order_id: order_id,
      htex_fingerprint: fp_now,
      htex_mapping_version: mapping_version,
    })
    ↓
[插件 popup]
    "✅ 已就绪: <申请人姓名>"
    引导用户去 DS-160 官网
```

### 4.3 在 DS-160 页填表(沿用 v0.1 引擎)

```
[用户在 DS-160 官网]
    - 插件 content-ds160.js 注入, 顶部出现填充面板
    - 面板读 chrome.storage.session.profile
    - 用户自己登录 (插件高亮 login form + "用你的 DS-160 账号登录"提示)
    - 用户进任一页 → 面板按 section 填, 绿框高亮已填, 报告待补字段
    - 用户核对 → 自己点 Next
```

---

## 5. API 接口契约(详见 backend-ds160-code-api.md)

| 方法 | 路径 | 调用方 | 鉴权 | 备注 |
|---|---|---|---|---|
| POST | `/api/v2/ds160/code` | Htex Web | Session(用户登录) | 签发/复用 code |
| POST | `/api/v2/ds160/code/redeem` | 浏览器插件 | **无鉴权**(code 即凭据) | 兑换档案 |

详细 schema / 错误码 / 限频 见 [`backend-ds160-code-api.md`](./backend-ds160-code-api.md)。

---

## 6. 组件清单与注入矩阵

### 6.1 v0.2 改动分类

| 文件 | v0.1 | v0.2 | 改动理由 |
|---|---|---|---|
| `src/background.js` | 接 HTEX_SAVE_PROFILE (postMessage 来源) | **新增** HTEX_REDEEM_CODE / HTEX_GET_META | code → profile 走 background 中转 |
| `src/content-app.js` | 接收 htexvisa.com postMessage | **删除整个文件 + manifest 移除 htexvisa.com 注入** | 不再需要同机直传 |
| `popup.html` / `popup.js` | 状态 + 文件导入 | **改为** 12 位 code 输入框 + Redeem 按钮 | 新主路径 |
| `manifest.json` | 注入 htexvisa.com | **移除** htexvisa.com 注入;**新增** htex 后端 host (用于 fetch /redeem) | 新主路径 |
| `src/mapping.js` | (自动生成) | **保留** (已经是 web 端 ds160FieldMap.js 构建产出) | 已通过 build script 防漂移 |
| `src/fillEngine.js` | 锚 label 填表 | **保留** | 不变 |
| `src/wayfinder.js` | 定位 + 高亮 | **保留** | 不变 |
| `src/journey.js` | 流程配置 | **保留** | URL 待核实(各国) |
| `src/content-ds160.js` | DS-160 填充面板 | **保留** + 微调 (读 htex_order_id / htex_fingerprint 用于报告页) | 加 meta 输出 |
| `src/content-journey.js` | 寻路条 | **保留** | 不变 |
| `test/mock-ds160.html` | 手动测试页 | **保留** + 加 "粘贴 code 模拟 redeem" 按钮 | 测试更完整 |

### 6.2 注入矩阵(v0.2)

| 站点 | 注入脚本 |
|---|---|
| `ceac.state.gov/genniv/*` | mapping → fillEngine → journey → wayfinder → content-ds160 → content-journey |
| `*.ustraveldocs.com` / `*.usvisa-info.com` | journey → wayfinder → content-journey(**只寻路**) |
| `htexvisa.com` / localhost | **无注入**(不再需要 postMessage) |
| Htex 后端 API | 不注入;插件 popup 用 `fetch()` 直接调 |

### 6.3 host_permissions(v0.2)

```json
{
  "host_permissions": [
    "https://ceac.state.gov/*",
    "https://*.ustraveldocs.com/*",
    "https://*.usvisa-info.com/*",
    "https://api.htexvisa.com/*",
    "http://localhost:8000/*"
  ]
}
```

---

## 7. 字段映射(沿用 v0.1,补 v0.2 改动)

权威源: `frontend/web/src/data/ds160FieldMap.js` (332 行, 10 个 section, 含 `security_background` manual 段)。

构建产物: `browser-extension/src/mapping.js` (974 行, classic IIFE)。
构建脚本: `frontend/web/scripts/build-extension-mapping.mjs`。

### v0.2 改动点

| 字段/段 | 改动 |
|---|---|
| `family.father.*` / `family.mother.*` | 已存在(v0.1 已覆盖) |
| `work.hasEducation` 子链 | 已存在(学校名 / 专业 / 起止 / prevEmployer) |
| **新增 (建议)** | `family.hasUSRelatives` + `family.relative.*` (子条件链) — 已在 v0.1 |
| **新增 (建议)** | `previous.lastVisitStayDays` (上次停留天数) — 已在 v0.1 |
| **新增 (建议)** | `contact.country` / `passport.issueCountry` 国家下拉值映射 (按申请人 nationality 反查护照签发国) | P1 待办 |
| **新增 (建议)** | `travel.companion.*` 当 `hasCompanions=true` 时的具体字段 | v0.1 已实现 `when` 条件 |

### 字段映射五条铁律(沿用 v0.1)

1. **锚字段标签,不锚页码** —— 官网挪动字段也不误导。
2. **带 `DS160_VERSION` + `DS160_VERIFIED_DATE`** —— 透明;`VERIFIED_DATE=null` 逼对真表核对后才敢标日期。
3. **`when` 条件字段** —— 只对符合条件的用户展示(单身不出现配偶栏)。
4. **`optional` 可选栏** —— 空 → Does Not Apply,不误报缺失。
5. **必填缺值 → 标"待补",绝不瞎填。**

---

## 8. 填充引擎(`src/fillEngine.js`)— 沿用 v0.1

核心:**按 label 定位控件 → 按类型填值 → 派发 input/change 事件 → 返回逐项报告**。

v0.2 引擎**完全沿用**, 不变。**新增**两点元数据展示:

| 项 | v0.1 | v0.2 |
|---|---|---|
| 报告字段 | `{label, status, value/reason}` | 加 `order_id` + `fingerprint` 在面板顶部("本次填表对应订单 #123 / 档案指纹 xxxx") |
| 进度 | 无 | 加 "已填 X / 23 页" 徽标(基于 chrome.storage.session.htex_ds160_progress) |

定位策略 / 类型填值 / autoFill (MutationObserver) / 逐项报告 全部沿用, 见 [DESIGN.md §5](./DESIGN.md#5-填充引擎srcfillenginejs)。

---

## 9. 寻路指引(领路狗) — 沿用 v0.1

数据驱动的三步流程:DS-160 → 交费/预约 → 面签。预约站按国家 (VN/ID/CN) 配对应链接。

**v0.2 改动:**

- `journey.js` 加 `cc()` 取档案里的 nationality → 预约站 URL 按国家取(已在 v0.1 实现)
- `content-journey.js` 加 "📌 档案指纹" 展示(让用户看到此次旅程关联哪个 code)

---

## 10. 安全与合规

| 风险 | v0.2 防御 |
|---|---|
| 插件代用户登录政府站 | **不做**(B 决定);插件只提示,用户自己登 |
| 插件替用户提交/支付 | **不做**(红线);用户自己点 |
| 用户改了档案但插件拿老 code 去填 | **后端 redeem 时比对 fingerprint, 不一致返 409 ARCHIVE_CHANGED**(用户必须回 Htex 拿新 code) |
| Code 暴力枚举 | 12 位 base30 ≈ 60 bits 熵;**限频** 同 code 60s 内最多 5 次;同 IP 失败 N 次后封禁 |
| Code 泄漏给第三方 | **code 是一次/多次消费的鉴权令牌**,拿到 code 的人能拉档案 → **HTTPS-only + 后端 audit log + 用户可主动 rotate**(在订单详情页 "重置 code" 按钮) |
| 浏览器历史/CSP 泄漏 | 档案只在 `chrome.storage.session`(关浏览器即清),不上传;manifest CSP 限制 |
| 官网改版误导 | 锚字段标签 + `DS160_VERIFIED_DATE=null` 提示 + `valueMap` 精确优先 (MALE ≠ FEMALE) |
| Mapping 漂移 | 已由 `build-extension-mapping.mjs` 解决 + CI check(待加) |

### 主动 rotate(用户侧防御)

```
[用户:订单详情页]
    "重置 DS-160 code" 按钮
    ↓
    POST /api/v2/ds160/code { order_id, force_rotate: true }
    ↓
    后端: 不管 fingerprint 一律生成新 code + 旧的进黑名单(不允许 redeem)
```

### 后端不存 PII (零知识)

- `ds160_fingerprint` = SHA-256 hex(规范化后的字段值),**不可逆**
- `ds160_code` 是随机码,跟档案没关系(只是 lookup key)
- 真正的 PII 仍然只存在 `order.applicants` 表里,该表本来就有(沿用)
- **后端 redeem 时必须 JOIN order 取 applicants 才能返回 profile**——这意味着 fingerprint 泄漏 + code 泄漏 才能拿到档案,**两层独立因素**

---

## 11. 验证现状 / 待办

| 项 | 方式 | 状态 |
|---|---|---|
| 填充引擎 (text/select/date-split/na/not_found) | jsdom + 真实文件 | ✅ v0.1 已通过 |
| select 精确匹配 (MALE≠FEMALE) | jsdom | ✅ |
| autoFill (postback 后动态字段) | jsdom + MutationObserver | ✅ |
| 寻路 locate/detect/highlight | jsdom | ✅ |
| 档案转换器 (多源合并 + MRZ 日期归一) | node | ✅ |
| **fingerprint 算法** (改字段 → 雪崩) | **新增单测** | ⏳ 待补 |
| **code 生成** (base30 + secrets.choice) | **新增单测** | ⏳ 待补 |
| **API: /code 幂等 (档案不变返旧 code)** | **新增 pytest** | ⏳ 待补 |
| **API: /redeem ARCHIVE_CHANGED 409** | **新增 pytest** | ⏳ 待补 |
| **API: 限频** (60s/5 次) | **新增 pytest** | ⏳ 待补 |
| **插件 popup 新交互** (code 输入) | **手测** | ⏳ 待补 |
| **真 Chrome 加载 + 真官网** | README 有步骤 | ⏳ 需人工 |

---

## 12. 已知限制与维护成本

| 编号 | 限制 | 影响 | 优先级 |
|---|---|---|---|
| L1 | 字段映射未对真表核对 (`DS160_VERIFIED_DATE=null`) | 上线前必须逐条核 | **P0** |
| L2 | 预约站 URL 待核实 (各国 ustraveldocs/usvisa-info) | 寻路可能给错链接 | P1 |
| L3 | iframe / DS-160 会话超时 (20 分钟) | 续填要重新 redeem + 重填 | P1 |
| L4 | 跨页累计进度未做 | 用户看不到"我填到第几页了" | P1 |
| L5 | 跨设备扫码 E2E | 默认跨设备(PC 装插件),扫码 E2E 不再必要 | P2 (降级) |
| L6 | CI check build-extension-mapping 防漂移 | 漂移会突然塞错字段 | **P0** |
| L7 | Mapping 单测 (web 端 ds160FieldMap.test.js 已存在) 与插件端共享测试用例 | 避免两套测试 | P1 |

---

## 13. 路线图

### v0.2 (本轮)

- [x] 重写 DESIGN.md 为 v0.2
- [ ] 实现 `compute_fingerprint` + 单测
- [ ] 实现 `generate_code` + 单测
- [ ] 后端 `/api/v2/ds160/code` + 单测
- [ ] 后端 `/api/v2/ds160/code/redeem` + 单测
- [ ] 插件 popup 重写 (code 输入)
- [ ] 插件 background 重写 (新增 HTEX_REDEEM_CODE 等)
- [ ] manifest.json 更新 (移除 htexvisa.com 注入, 加 api host)
- [ ] 删除 content-app.js (不再需要)
- [ ] Htex 前端 订单详情页 加 "去 DS-160 填表" 按钮 + code 展示

### v0.3 (P0-P1)

- [ ] 字段映射对真表核对 (`DS160_VERIFIED_DATE` 填日期)
- [ ] CI check: build-extension-mapping 漂移检测
- [ ] 跨页累计进度 (`chrome.storage.session.htex_ds160_progress`)
- [ ] iframe 注入支持 (DS-160 部分页用 frame)
- [ ] 用户主动 rotate code 按钮
- [ ] L7: 共享单测

### v0.4 (P2)

- [ ] 跨设备扫码 E2E (按需; 当前已跨设备,优先级降低)
- [ ] 多申请人选择器 (`applicants[]` 全填)
- [ ] DS-160 会话超时自动续填

---

## 14. 快速上手(更新版)

### 后端

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/migrate_ds160_code_fields.py   # 加 5 个新列
PYTHONPATH=. .venv/bin/pytest tests/unit/test_ds160_code.py -v       # 跑新单测
PYTHONPATH=. .venv/bin/pytest tests/api/test_ds160_api.py -v        # 跑 API 集成
```

### 插件

```bash
cd browser-extension
node ../frontend/web/scripts/build-extension-mapping.mjs   # 同步 mapping
Chrome → 扩展 → 开发者模式 → 加载已解压 → 选 browser-extension/
```

### 端到端(用真 Chrome)

1. 在 Htex Web 完成订单 → 进订单详情 → 点 "去 DS-160 填表" → 复制 12 位 code
2. 点 Chrome 工具栏 Htex 插件图标 → 粘贴 code → 点 Redeem
3. 打开 `ceac.state.gov/genniv/` → 自己登录(插件高亮 login form) → 进任一页 → 面板显示 "待填 X 字段" → 点 "填充本页" → 核对 → 自己点 Next

### 不连官网的引擎验证

```bash
# 真 Chrome 直接打开
open browser-extension/test/mock-ds160.html
# 点 "用示例档案填充" → 看仿真表单被填好
```

---

## 附录 A:关键决策日志

| 决定 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 登录方式 | 自动填凭据 / 只提示 / 续填 AAID | **只提示** | 政府站密码不经插件,信任边界最清 |
| Code 语义 | 短码一次性 / 会话语柄 / 档案指纹 | **档案指纹** | 自带版本控制, 防"老数据填新表单" |
| Code 有效期 | 30 分钟即焚 / 长期 | **长期** | 用户随时可拿, 改档案自动换 |
| Code 绑定粒度 | 订单 / 申请人 / (用户+目的地) / (申请人+目的地) | **订单** | 当前业务"一申请人 + 一国家 = 一订单" |
| Mapping 来源 | 复用 web / 插件独立 / 后端下发 | **复用 web** | 已由 build script 防漂移 |
| 交付形式 | 设计 + API + 原型 + 流程图 | **设计 + API + 流程图** | 设计 = 骨架, API = 手脚, 流程图 = 对齐 |
| Rotate 入口 | 用户主动 / 自动 | **用户主动** | 控制权在用户;泄漏/换设备时手动按 |