# LEGAL_REVIEW_NOTES — 法务 Review 提示与待办清单

> **背景**: 需求文档 §1.3 合规约束要求前端展示《用户协议》《隐私政策》(分英语/印尼语/越南语三版本)。
> 当前 4 语种静态协议页 (`frontend/shared/i18n/{zh-CN,en,id,vi}.json` + `frontend/web/src/views/Agreement.vue`) 已落地,
> 但**所有文本均为 AI 自译 / 模板**状态, **未经过法务 review**。
> 本文档列出每一份协议文件的当前状态、需法务 review 的具体点、TODO 标记、优先级, 并提供一份
> launch 前法务必查的 checklist。

> **目标上线日期**: 2026-07-01 (印尼 / 越南 launch 节点)
> **deadline**: 法务 review 完成需在 **2026-06-25** 前到位, 留 5 天修复窗口。

---

## 1. 受影响的协议文件清单

### 1.1 zh-CN (简体中文) — 母版

| # | 文档 | 文件路径 | 当前状态 | 内容来源 | TODO | 优先级 |
|---|------|----------|----------|----------|------|--------|
| 1 | 用户协议 | `frontend/shared/i18n/zh-CN.json` → `agreement.terms_*` (行 553-567) | `自翻译 (AI)` | 模板起草 + 业务草拟 | 法务复核全文 | **P0** |
| 2 | 隐私政策 | `frontend/shared/i18n/zh-CN.json` → `agreement.privacy_*` (行 568-577) | `自翻译 (AI)` | 模板起草 + 业务草拟 | 法务复核全文 | **P0** |
| 3 | 注册勾选文案 | `frontend/shared/i18n/zh-CN.json` → `agreement_prefix / agreement_terms / agreement_and / agreement_privacy / agreement_required` (行 81-84, 102) | `自翻译 (AI)` | 模板起草 | 法务复核勾选提示语 | **P0** |

### 1.2 en (英语) — 印尼 / 越南市场唯一可信母语

| # | 文档 | 文件路径 | 当前状态 | 内容来源 | TODO | 优先级 |
|---|------|----------|----------|----------|------|--------|
| 4 | User Agreement | `frontend/shared/i18n/en.json` → `agreement.terms_*` (行 553-567) | `自翻译 (AI)` | 由 zh-CN 机翻 | 法务 native-speaker 复核 + 适用法律确认 | **P0** |
| 5 | Privacy Policy | `frontend/shared/i18n/en.json` → `agreement.privacy_*` (行 568-577) | `自翻译 (AI)` | 由 zh-CN 机翻 | 法务 native-speaker 复核 + 跨境数据传输条款 (GDPR / PDPA 印尼 / 越南网安法) | **P0** |
| 6 | Consent Checkbox | `frontend/shared/i18n/en.json` → `agreement_prefix / agreement_terms / agreement_and / agreement_privacy / agreement_required` (行 81-84, 102) | `自翻译 (AI)` | 由 zh-CN 机翻 | 法务复核"已阅读并同意"措辞强度 | **P0** |

### 1.3 id (印尼语 / Bahasa Indonesia)

| # | 文档 | 文件路径 | 当前状态 | 内容来源 | TODO | 优先级 |
|---|------|----------|----------|----------|------|--------|
| 7 | Perjanjian Pengguna | `frontend/shared/i18n/id.json` → `agreement.terms_*` (行 553-567) | `自翻译 (AI)` | 由 en 机翻 | 印尼本地律师 native-speaker 复核 + UU PDP 2022 校验 | **P0** |
| 8 | Kebijakan Privasi | `frontend/shared/i18n/id.json` → `agreement.privacy_*` (行 568-577) | `自翻译 (AI)` | 由 en 机翻 | 印尼本地律师 native-speaker 复核 + UU PDP 第 14/16/18 条 (跨境传输 / 用户权利 / 同意) 校验 | **P0** |
| 9 | Persetujuan Checkbox | `frontend/shared/i18n/id.json` → `agreement_prefix / agreement_terms / agreement_and / agreement_privacy / agreement_required` (行 81-84, 102) | `自翻译 (AI)` | 由 en 机翻 | 印尼本地律师复核 "saya telah membaca" 措辞是否构成有效 consent | **P0** |

### 1.4 vi (越南语 / Tiếng Việt)

| # | 文档 | 文件路径 | 当前状态 | 内容来源 | TODO | 优先级 |
|---|------|----------|----------|----------|------|--------|
| 10 | Điều khoản Dịch vụ | `frontend/shared/i18n/vi.json` → `agreement.terms_*` (行 553-567) | `自翻译 (AI)` | 由 en 机翻 | 越南本地律师 native-speaker 复核 + Nghị định 13/2023 (PDPD) 校验 | **P0** |
| 11 | Chính sách Bảo mật | `frontend/shared/i18n/vi.json` → `agreement.privacy_*` (行 568-577) | `自翻译 (AI)` | 由 en 机翻 | 越南本地律师 native-speaker 复核 + Nghị định 13/2023 第 9/11/20 条 (数据收集 / 同意 / 跨境) 校验 | **P0** |
| 12 | Đồng ý Checkbox | `frontend/shared/i18n/vi.json` → `agreement_prefix / agreement_terms / agreement_and / agreement_privacy / agreement_required` (行 81-84, 102) | `自翻译 (AI)` | 由 en 机翻 | 越南本地律师复核 "tôi đã đọc" 措辞是否符合电子同意有效要件 | **P0** |

### 1.5 共享页面组件

| # | 组件 | 文件路径 | 当前状态 | TODO | 优先级 |
|---|------|----------|----------|------|--------|
| 13 | Agreement 页面 | `frontend/web/src/views/Agreement.vue` | `已实现 (W12)` | 顶部加 `LEGAL_TODO` 注释, 法务 review 通过前在生产环境加 warning banner | **P1** |

---

## 2. 需要法务 review 的具体点 (按业务风险排序)

### 2.1 【P0】跨境数据传输条款

> **现状**: zh-CN `privacy_section_3_body` 写 "数据加密存储于中国境内的服务器, 使用 HTTPS / TLS 1.3 传输, 任何第三方访问均需经过您的明示授权"。
> 印尼 / 越南用户在本地签约时, **数据出境**需符合当地数据保护法额外要求。

- [ ] zh-CN: 是否需补充"如跨境传输至中国境内, 已通过国家网信部门安全评估"声明?
- [ ] id: UU PDP 2022 第 56 条要求跨境传输需向 Otoritas Pelindungan Data Pessoal (PDP Authority) 报备。需明确:
  - 跨境路径 (印尼 → 中国大陆)
  - 接收方身份
  - 传输目的
  - 用户单独同意
- [ ] vi: Nghị định 13/2023 第 25 条要求跨境传输需经公安部备案 + 越南本地留存副本。需明确:
  - 影响评估 (DPIA) 报告
  - 越南本地存储副本
  - 越南用户可单独撤销跨境同意
- [ ] en: 是否同时满足 GDPR Chapter V (Adequacy decision / SCCs), 印尼 / 越南用户在 EU 旅行时的额外保护

### 2.2 【P0】未成年人保护

> **现状**: 用户协议 / 隐私政策全文**未提及未成年人条款**。

- [ ] 是否需加 4.5 条: 未满 18 岁用户需法定代理人同意?
- [ ] 越南: Nghị định 13/2023 第 15 条 — 处理儿童 (满 7 周岁) 个人数据需监护人同意
- [ ] 印尼: UU PDP 2022 第 25 条 — 处理儿童个人数据需监护人同意
- [ ] 法务确认: 平台是否允许未成年人 (例如 16 岁单独办签) 注册? 需补充年龄门槛声明

### 2.3 【P0】拒签免责声明

> **现状**: zh-CN `terms_section_1_body` 写 "本平台不直接办理签证, 所有签证最终审批结果由各国使领馆决定";
> `terms_section_3_body` 写 "因用户原因导致拒签, 服务费按《拒签险条款》处理"。

- [ ] 法务确认: 拒签险条款 (单独文件) 是否已存在? 是否需在用户协议中明确指向拒签险文件
- [ ] 法务确认: "用户原因" 列举范围 — 虚假材料 / 信息错误 / 使领馆政策变化 / 不可抗力?
- [ ] 印尼 / 越南: 需补充"使领馆政策变化"是否构成"非用户原因"的全额退款条件
- [ ] 跨境消费纠纷: 印尼 Otoritas Jasa Keuangan (OJK) / 越南 VECOM 是否需在协议中列明争议解决机构

### 2.4 【P0】用户权利 (GDPR / PDP 风格)

> **现状**: zh-CN `privacy_section_4_body` 写 "您可随时查看、更正、删除您的个人信息。如需注销账号, 请联系客服"。

- [ ] 法务确认: 注销账号的处理时限 (15 / 30 个工作日?)
- [ ] 印尼 UU PDP 第 6/7/8/9 条: 用户有知情权 / 访问权 / 更正权 / 删除权 — 需逐条落实
- [ ] 越南 Nghị định 13/2023 第 9 条: 同上
- [ ] 是否需提供"数据可携权"导出功能? (GDPR Art.20 / UU PDP 类似条款)
- [ ] 客服响应 SLA 是否要在隐私政策中明确?

### 2.5 【P0】同意 / 勾选文案强度

> **现状**: `agreement_prefix` 写 "我已阅读并同意" / "I have read and agree to" / "Saya telah membaca dan menyetujui" / "Tôi đã đọc và đồng ý với"

- [ ] 法务确认: 单纯"已阅读"是否构成"informed consent"? 是否需追加"我已理解"?
- [ ] GDPR Recital 32: 同意必须是"specific, informed and unambiguous" — 复选框默认勾选 (pre-ticked) 在 EU 不合法
- [ ] 印尼 UU PDP 第 22 条: 同意必须 explicit, 需勾选
- [ ] 越南: 同上, 需勾选
- [ ] 法务确认: 当前 `agreement_required` 文案 "请先勾选用户协议和隐私政策" 在 4 语种下都成立吗?

### 2.6 【P1】生效日期与版本管理

> **现状**: 4 语种都写 "生效日期: 2026-06-01", 但 2026-06-14 仍处于"未生效"灰色状态。

- [ ] 法务确认: 是否采用"注册时同意 + 版本号"机制? 若协议更新, 是否需用户重新勾选?
- [ ] 建议加 `agreement_version: "v1.0-2026-07-01"` 字段, 用于 in-app 强制 re-consent
- [ ] 印尼 UU PDP 第 25 条: 隐私政策变更需 30 天前通知用户

### 2.7 【P1】争议解决与适用法律

> **现状**: 4 语种协议全文**未规定争议解决方式与适用法律**。

- [ ] 法务确认: 适用法律是中国法律? 印尼用户纠纷是否约定雅加达仲裁?
- [ ] 法务确认: 管辖法院
- [ ] 越南用户: 是否约定胡志明市 / 河内仲裁?
- [ ] 在线纠纷解决 (ODR) 链接 — 欧盟 / 印尼 ODR 平台

### 2.8 【P2】联系方式与数据保护官 (DPO)

> **现状**: 隐私政策全文**未提供 DPO / 隐私事务联系人信息**。

- [ ] 法务确认: 是否需指定 DPO? 印尼 UU PDP 要求境外数据控制者指定当地代表
- [ ] 越南 Nghị định 13/2023 第 17 条: 需指定越南本地数据保护负责人
- [ ] 建议加 `privacy_contact_email` / `privacy_contact_dpo` 字段

### 2.9 【P2】Cookie / 本地存储

> **现状**: 隐私政策**未提及 Cookie / localStorage / IndexedDB**。

- [ ] 法务确认: 平台是否使用 cookie? 是否需在隐私政策中披露?
- [ ] 印尼 / 越南: 同 GDPR ePrivacy 指令要求
- [ ] 建议加 `privacy_section_5_title: 5. Cookie 与本地存储`

### 2.10 【P2】第三方共享

> **现状**: zh-CN 写"任何第三方访问均需经过您的明示授权" — 但未列举具体第三方。

- [ ] 法务确认: 需列举:
  - 支付网关 (Stripe)
  - OCR / AI 识别服务 (火山引擎 / 阿里云?)
  - 使领馆 (签证申请材料)
  - 风控服务 (同盾 / 数美?)
- [ ] 印尼 / 越南: 需逐项征得用户单独同意

---

## 3. 法务 Review Checklist (Launch 前必查 18 项)

> **说明**: 每一项需法务在 4 语种下都明确给出 "通过 / 需修改 / 不通过" 结论, 并签字 / 邮件确认。

| # | 类别 | Checklist 项 | 责任方 | 状态 | 截止日 |
|---|------|-------------|--------|------|--------|
| 1 | 跨境传输 | zh-CN `privacy_section_3_body` 跨境传输声明是否包含"已通过网信办评估"陈述 | 法务 + 数据合规 | ⬜ | 2026-06-25 |
| 2 | 跨境传输 | id `privacy_section_3_body` 是否符合 UU PDP 2022 第 56 条 (跨境传输报备) | 印尼本地律师 | ⬜ | 2026-06-25 |
| 3 | 跨境传输 | vi `privacy_section_3_body` 是否符合 Nghị định 13/2023 第 25 条 (越南本地留存 + DPIA) | 越南本地律师 | ⬜ | 2026-06-25 |
| 4 | 未成年人 | 4 语种用户协议是否加"未满 18 周岁需法定代理人同意"条款 | 法务 | ⬜ | 2026-06-25 |
| 5 | 拒签免责 | zh-CN `terms_section_3_body` 拒签险条款指向是否清晰, 拒签险文件是否已生效 | 法务 + 业务 | ⬜ | 2026-06-25 |
| 6 | 拒签免责 | id / vi 版本"使领馆政策变化"是否构成非用户原因, 是否需全额退款 | 印尼 / 越南本地律师 | ⬜ | 2026-06-25 |
| 7 | 用户权利 | 4 语种 `privacy_section_4_body` 是否落实 UU PDP / Nghị định 13 第 6-9 条 8 项用户权利 | 法务 + 印尼 / 越南律师 | ⬜ | 2026-06-25 |
| 8 | 用户权利 | 注销账号处理时限是否明确 (建议 15 工作日) | 法务 | ⬜ | 2026-06-25 |
| 9 | 同意文案 | 4 语种 `agreement_prefix` "已阅读并同意" 是否构成 GDPR / UU PDP / Nghị định 13 要求的"explicit consent" | 法务 | ⬜ | 2026-06-25 |
| 10 | 同意文案 | 注册页勾选框是否默认未勾选 (pre-ticked 违规) | 前端 + 法务 | ⬜ | 2026-06-25 |
| 11 | 适用法律 | 4 语种用户协议是否约定适用法律 + 争议解决机构 + 管辖法院 | 法务 | ⬜ | 2026-06-25 |
| 12 | DPO | 4 语种隐私政策是否提供 DPO / 隐私事务联系人 + 邮箱 | 法务 | ⬜ | 2026-06-25 |
| 13 | 第三方 | zh-CN `privacy_section_3_body` 是否列举具体第三方 (支付 / OCR / 风控) | 法务 | ⬜ | 2026-06-25 |
| 14 | 第三方 | id / vi 是否就第三方共享征得用户单独同意 | 印尼 / 越南律师 | ⬜ | 2026-06-25 |
| 15 | Cookie | 4 语种隐私政策是否披露 cookie / localStorage 使用 | 法务 | ⬜ | 2026-06-25 |
| 16 | 版本管理 | `agreement_version` 字段是否加, 协议更新是否触发 in-app re-consent | 前端 + 法务 | ⬜ | 2026-06-25 |
| 17 | 文案校对 | 印尼本地 native-speaker 校对 id.json 全文 (拼写 / 术语 / 礼节) | 印尼本地律师 | ⬜ | 2026-06-25 |
| 18 | 文案校对 | 越南本地 native-speaker 校对 vi.json 全文 (拼写 / 术语 / 礼节) | 越南本地律师 | ⬜ | 2026-06-25 |

---

## 4. Review 完成后的状态变更流程

```
P0/AI 自译 ──法务 review──> P1/法务待核 ──法务签字──> P2/法务已核 ──launch──> 生产生效
                                                       (移除 WARNING banner)
```

- **法务已核** 状态: 在 4 语种 i18n 文件中删除 `__legal_review_pending__` 标记;
  在 `Agreement.vue` 中删除 `LEGAL_TODO` 注释; 在 `front/index.html` 移除 WARNING banner
- **拒绝** 状态: 法务出 review notes, 业务 / 前端修改 → 重新进入 review 循环

---

## 5. 相关链接

- 需求文档: `AI 签证需求文档V0.docx` §1.3 合规约束
- i18n 文件: `frontend/shared/i18n/{zh-CN,en,id,vi}.json`
- 协议页面: `frontend/web/src/views/Agreement.vue`
- 类似交付: `docs/d-verify-runner-recipe.md` (W11-2 修整文档化模板)

---

**Maintainer**: frontend coder (W14-8)
**Last updated**: 2026-06-14
**Status**: 待法务 review (Launch 倒计时 ~17 天)
