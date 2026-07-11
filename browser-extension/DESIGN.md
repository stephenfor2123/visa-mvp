# Htex DS-160 辅助填充插件 · 设计与实现文档

> 版本:v0.1 草稿(2026-07) · 状态:独立草稿,**未接 web 构建、未提交**
> 适用范围:美签 DS-160 辅助填充 + 美签流程寻路指引

---

## 0. TL;DR

一个 Manifest V3 浏览器扩展,给东南亚/中国用户申请美签提供两类帮助:

1. **辅助填充 DS-160**:把用户在 Htex App 填好的资料,自动填进 `ceac.state.gov` 的 DS-160 表单——**用户只需核对 + 自己点 Next/Submit**。
2. **流程寻路(领路狗)**:美签是跨多站点的迷宫(DS-160 → 交费/预约 → 面签),插件检测用户在哪一步,**把藏很深的入口按钮直接圈出来 + 提示下一步去哪**。

三条设计红线贯穿全局:
- **辅助,不是全自动 RPA** —— 填字段/指路,不替用户点政府站的提交/支付按钮(合规 + 抗脆 + 安全)。
- **数据本地优先** —— 用户资料只在本设备内流转,不经服务器(信任卖点)。
- **锚"用户看得见的东西",不锚会变的 ID/页码** —— 按字段标签、按钮文本定位,官网改版也不易崩、不误导。

---

## 1. 目标与非目标

### 目标
- 大幅减少用户在 DS-160 官网的手工录入(把录入前移到体验更好的 App 手机向导)。
- 帮用户**找到**美签流程里那些藏得很深的入口。
- 一套字段映射,**引导单(App 端照抄单)与插件(自动填)共用**,改一处两处生效。
- 单人先行,数据契约按多申请人前向兼容。

### 非目标(明确不做)
- ❌ 不做无人值守全自动提交(照片、安全问题、CAPTCHA、最终提交都留给用户)。
- ❌ 不替用户在政府站点击"提交/支付"。
- ❌ 不把用户证件/资料上传到我方服务器。

---

## 2. 总体架构

```
┌──────────────────────┐   交接(本地)   ┌───────────────────────────────┐
│  📱/💻 Htex App        │ ─────────────▶ │  🧩 浏览器插件(MV3)             │
│  收集完整档案          │  postMessage    │                                 │
│  ApplicantProfile     │  或 文件导入     │  background(chrome.storage      │
│                       │  (扫码E2E=P2)   │            .session 暂存)        │
└──────────────────────┘                 │        │                        │
                                          │        ├─ ceac.state.gov:        │
                                          │        │   填充引擎 + 填充面板    │
                                          │        │   寻路提示 + 高亮        │
                                          │        └─ 预约站:寻路提示 + 高亮  │
                                          └───────────────────────────────┘
                                                     │ 填 / 指路
                                                     ▼
                                   ceac.state.gov(DS-160) · ustraveldocs / usvisa-info(预约)
```

### 共享契约
`ApplicantProfile`(标准申请人档案)是 **App、终审、规则引擎、引导单、插件** 共用的同一个对象。
DS-160 字段映射是**引导单与插件共用**的唯一数据源。

---

## 3. 数据模型:ApplicantProfile

由 `frontend/web/src/composables/useApplicantProfile.js` 从多来源(OrderNew 表单 + 护照 OCR + travelPlan)合并、日期归一而成。缺的字段留空(引导单/引擎会标"待补")。

```
ApplicantProfile {
  identity   { surname, givenName, nativeName, sex(M/F), maritalStatus,
               dob(ISO), birthCity, birthCountry, nationality, nationalId, hasOtherNationality }
  passport   { type, number, bookNumber, issueCountry, issueCity, issueDate, expiry }
  contact    { street, city, state, postalCode, country, phone, email }
  travel     { purpose, hasPlan, arrivalDate, stayLength, usAddress, payer,
               hasCompanions, companion{...} }
  previous   { hasVisited, lastVisitDate, hasVisa, lastVisaNumber, hasRefused, ... }
  usContact  { personSurname, personGivenName, orgName, relation, street, city, state, zip, phone, email }
  work       { occupation, employer, employer地址/电话, monthlySalary, duties,
               hasEducation, schoolName, courseOfStudy, ... }
  family     { spouse{...}, father{...}, mother{...}, hasUSRelatives, relative{...} }
  security   { acknowledged }
}
```

- **单人**:`Order.applicants = [profile]`,插件填 `applicants[0]`。
- **多人(将来)**:`applicants[]`,插件加"选申请人"下拉,契约不变。
- **日期归一**(`normalizeDate`):`YYYY-MM-DD` / `DD/MM/YYYY`(越/印常见) / `DD MMM YYYY`(护照 MRZ)→ ISO;认不出就留空,不硬塞(防误导)。

---

## 4. 单一数据源:DS-160 字段映射

`frontend/web/src/data/ds160FieldMap.js`(权威源) 与 `browser-extension/src/mapping.js`(插件版)。

### 字段属性
| 属性 | 含义 |
|---|---|
| `label` | 官网那个框的**英文标签**(定位锚点) |
| `profile` | 档案取值路径(点分,如 `passport.number`) |
| `input` | `text` / `select` / `date`(日-月-年) / `radio` / `textarea` |
| `transform` | `upper`(全大写) / `date`(转 `DD-MMM-YYYY`) |
| `valueMap` | 档案值 → 官网下拉的确切文案(如 `M→MALE`、`tourism→TEMP. BUSINESS PLEASURE VISITOR (B)`) |
| `optional` | 可空;空时提示"勾 Does Not Apply",不计"待补" |
| `when(profile)` | 条件展示(单身不出现配偶栏 → 防误导) |

### 五条设计铁律
1. **锚字段标签,不锚页码** —— 官网挪动字段也不误导。
2. **带 `VERSION` + `VERIFIED_DATE`** —— 透明;`VERIFIED_DATE=null` 逼你对真表核对后才敢标日期。
3. **`when` 条件字段** —— 只对符合条件的用户展示。
4. **`optional` 可选栏** —— 空 → Does Not Apply,不误报缺失。
5. **必填缺值 → 标"待补",绝不瞎填。**

### ⚠️ 已知债:两份映射会漂移
权威源(web)已覆盖 ~10 段(含 Travel Companions / Previous Travel / US Contact / Work / Family 父母),
插件版 `mapping.js` 目前是**手抄的子集**。**必须加构建步骤**:以 web 那份为唯一源自动生成插件版。
建议先把 `when` 函数改成声明式(如 `whenEq:{'identity.maritalStatus':'married'}`)以便序列化。

---

## 5. 填充引擎(`src/fillEngine.js`)

核心:**按 label 定位控件 → 按类型填值 → 派发 input/change 事件 → 返回逐项报告。**

### 5.1 定位策略(`findControl`,从强到弱)
1. `<label for=id>` 文本匹配 → `#id`。
2. 含该文本的单元格/元素 → 同 `<tr>` 行内的表单控件。
3. 含该文本元素之后最近的表单控件。
> 找不到 → 标 `not_found`,交面板提示手填,**绝不乱填别的框**。

### 5.2 按类型填值
- **text/textarea**:原生 setter 设值 + 派发 `input`/`change`。
- **select**:选项匹配**先精确、再子串**(避免 `MALE` 被 `FEMALE` 子串误配)。
- **radio/checkbox**:同名组里按 label/value 精确→子串匹配。
- **date(三连下拉)**:`fillDate` 把 `DD-MMM-YYYY` 拆成日/月/年,**按内容**识别 Month(含 JAN..DEC)、Day(数字 select)、Year(文本框/年 select)分别填。
- **Does Not Apply**:可选栏为空 → 找该字段行内 label 含 "Does Not Apply" 的复选框勾上。

### 5.3 自动跟填(postback 联动)`autoFill`
DS-160 里选某些下拉会 postback、动态冒出新字段。`autoFill`:
1. 先填一遍。
2. `MutationObserver` 监听 `childList/subtree/attributes(style,class,hidden)`。
3. 新字段出现 → 把之前 `not_found` 的 step 再补填(250ms 防抖)。
4. 全填上或超时(5s)后停止。面板有"自动跟填"开关(默认开)。

### 5.4 逐项报告
`{ label, status, value/reason }`,status ∈ `filled` / `na` / `not_found` / `manual(待补)`。
成功项页面上加**绿框高亮**;需人工的列在面板里。

---

## 6. 寻路指引(领路狗)

### 6.1 旅程配置 `src/journey.js`
数据驱动的三步流程,预约站**按国家(VN/ID/CN)**给对应链接:
```
① DS-160(ceac.state.gov/genniv) → ② 交 MRV 费 + 约面签(预约站,按国家) → ③ 面签
```
每步:`title` / `hint`(该做啥) / `locate`(要高亮的按钮候选) / `nextId`。
> 预约站 URL 现为 `verified:false` **待核实**(各国用 ustraveldocs 还是 usvisa-info 会变)。

### 6.2 寻路模块 `src/wayfinder.js`
- `locate(hints)`:按 `{text}`/`{href}`/`{selector}` 找元素;文本匹配偏好**最短文本**(贴近按钮,不是大容器)。
- `highlight(el, msg)`:`scrollIntoView` + 橙色 outline + 👉 浮标,把埋深按钮**指给用户看**;返回 `dispose()`。
- `detectStep(journey, url, cc)`:按 URL(和按国家的预约站)判断当前在哪一步。

### 6.3 编排 `src/content-journey.js`
取暂存档案的国籍 → 检测步骤 → 底部提示条(带"带我去下一步:预约站(某国)"按钮)→ 高亮本页关键入口。
**只指路,不替用户点政府站按钮。**

---

## 7. 数据交接(本地优先)

### 7.1 同机:App → 插件(已实现)
```
App 页面(htexvisa.com)  window.postMessage({source:'htex-app', type:'HTEX_DS160_EXPORT', profile})
   → content-app.js(仅注入本域,校验 origin) → background → chrome.storage.session(关浏览器即清)
   → content-ds160.js 取用
```
安全:content script 只注入在 htexvisa.com;校验 `origin`;不主动抓 localStorage,必须 App 用户点击导出。

### 7.2 兜底:文件导入(已实现)
App 导出档案 JSON → 插件 popup 导入。

### 7.3 跨设备扫码 E2E(P2,未实现)
手机填、电脑填 DS-160 的场景:**二维码由电脑插件显示、手机扫**,二维码只装 `{sessionId, 一次性密钥K}`;
手机用 K 加密档案 → 密文经临时中转(TTL 2 分钟、读一次即焚)→ 电脑解密。**中转只见密文,后端解不开。**
更硬核备选:WebRTC 纯 P2P(二维码传信令)。

---

## 8. 组件清单与注入矩阵

| 文件 | 职责 |
|---|---|
| `manifest.json` | MV3;权限 storage/scripting/activeTab;host 见下 |
| `src/mapping.js` | 字段映射 + 引导单生成(插件版,与 web 同源) |
| `src/fillEngine.js` | 填充引擎(定位/填值/date-split/autoFill) |
| `src/journey.js` | 旅程配置(寻路) |
| `src/wayfinder.js` | 定位 + 高亮 + 步骤检测 |
| `src/content-ds160.js` | DS-160 页填充面板 |
| `src/content-journey.js` | 寻路提示条 + 高亮 |
| `src/content-app.js` | 接收 App 导出的档案 |
| `src/background.js` | `chrome.storage.session` 暂存 |
| `popup.html` / `popup.js` | 状态 + 文件导入兜底 + 清除 |
| `test/mock-ds160.html` | 不依赖官网的手动测试页 |

### 注入矩阵
| 站点 | 注入脚本 |
|---|---|
| `ceac.state.gov/genniv/*` | mapping → fillEngine → journey → wayfinder → content-ds160 → content-journey |
| `*.ustraveldocs.com` / `*.usvisa-info.com` | journey → wayfinder → content-journey(**只寻路,不填表**) |
| `htexvisa.com` / localhost | content-app(接收档案) |

---

## 9. 安全与合规

- **辅助非自动**:填字段/指路,不替用户点政府站提交/支付。用户始终在环内。
- **本地数据**:`chrome.storage.session`(关浏览器即清、不落盘、不上传);跨设备走 E2E 加密。
- **最小权限**:host 只限 CEAC / 预约站 / 本 App 域。
- **不误导**:锚标签、缺值标"待补"不瞎填、`VERIFIED_DATE=null` 提示"未核对,以官网为准"。

---

## 10. 验证现状

| 项 | 方式 | 结果 |
|---|---|---|
| 填充引擎(text/select/date-split/na/not_found) | jsdom + 真实文件 | ✅ 读回 DOM 确认 |
| select 精确匹配(MALE≠FEMALE) | jsdom | ✅ |
| 档案转换器(多源合并 + MRZ 日期归一) | node | ✅ |
| autoFill(postback 后动态字段) | jsdom + MutationObserver | ✅ 断言通过 |
| 寻路 locate/detect/highlight | jsdom(干扰链接中精准定位) | ✅ 断言通过 |
| manifest / 全 JS 语法 | node --check | ✅ |
| **真 Chrome 加载 + 真官网** | — | ⏳ 需人工(README 有步骤 + mock 测试页) |

---

## 11. 已知限制与维护成本

1. **字段映射未对真表核对**(`VERIFIED_DATE=null`)——上线前必须逐条核。
2. **两份 mapping 会漂移**——需构建步骤自动同步(web 为源)。
3. **预约站 URL 待核实**(`verified:false`)——各国核对。
4. **跨页累计进度**未做;整页刷新式跨页靠每页重注入。
5. **iframe / 会话超时(20 分钟)**:部分 gov 页用 frame,复杂表要注意速度。
6. **扫码 E2E 交接**未实现(P2)。

---

## 12. 路线图

- **P0**:App 采集扩容到 DS-160 完整字段 + 引导单/插件填 Personal/Passport/Travel + 同机交接。
- **P1**:字段映射对真表核对 + 构建同步 + 全数据页映射 + 寻路 URL 核实 + 跨页进度。
- **P2**:扫码 E2E 交接 + WebRTC + 多申请人选择器 + 会话超时/断点续填。

---

## 13. 快速上手

```
# 加载
Chrome → 扩展 → 开发者模式 → 加载已解压 → 选 browser-extension/

# 只验证引擎(不连官网)
真 Chrome 打开 browser-extension/test/mock-ds160.html → 点"用示例档案填充"

# 真流程
DS-160 官网 ceac.state.gov/genniv → 右上填充面板 + 底部寻路条 → 核对后自己点 Next
```
