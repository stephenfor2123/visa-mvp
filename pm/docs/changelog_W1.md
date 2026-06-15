# V2 文档 W1 末更新纪要(草稿,W1 D5 定稿)

> 时间:2026-06-19 (W1 D5) · 主笔:PM (D) · 评审:CTO + Lead
> 目标:V2 → V2.1 + V2.2 双版本同步发布
> 本文件随 W1 实际进度滚动更新,周五定稿后,把改动落到 `sources/V2_需求文档.docx` + `.md`

---

## W1 实际文档变更

### 章节级变更

| 章节 | 原 V2.0 | 改后 V2.1/V2.2 | 原因 | 落地 |
|------|---------|---------------|------|------|
| §2.1 终端能力矩阵 | Android/iOS/Web 三端 | **iOS/Web + 后台 Web(独立)** | V2 不做 Android(W1 决策) | docx + md |
| §2.3 三端数据互通 | 三端数据互通 | **两端数据互通(iOS + Web)** + 后台独立 | Android 删了,后台单列 | docx + md |
| §4.6 支付适配器 | (空) | **新增 V2 阶段:支付 disable,MockPaymentAdapter,total_amount=0** | BD 通道未对接(R5) | docx + md |
| §4.1.5 SMSChannel | (空) | **新增 SMSChannel 抽象 + Mock 实现** | V2 测试模式,任意 6 位数字通过 | docx + md |
| §10.2 人员分工 | 8-10 人(3 FE) | **8-10 人(2.5 FE = web 1 + iOS 1 + 后台 0.5)** | Android 删除,人员重排 | docx + md |
| §10.4 R5 支付延期 | 状态 open | **状态 mitigated**(V2 disable 决策) | 本周已决策 | risks.json |
| §10.4 R12 类目 | 状态 open | **状态 mitigated**(选工具类目) | 本周与法务对齐 | risks.json |
| §10.3 8 周甘特图 | 文字 | **替换为 wbs/wbs.gantt.mmd**(更细) | 与 WBS 同步 | wbs/ |

### 新增文件

| 路径 | 说明 |
|------|------|
| `pm/wbs/wbs.md` | 8 周 × 5 角色 WBS(50 任务 + 25 每日) |
| `pm/wbs/wbs.gantt.mmd` | Mermaid 甘特图源文件 |
| `pm/wbs/dependency_matrix.md` | 任务依赖矩阵 |
| `pm/risks/risks.md` | 12 条风险 + 状态 |
| `pm/risks/risks.json` | 12 条风险(机器可读) |
| `pm/standup/*.md` | Standup 模板 + 4 角色 daily + AI&RPA bonus |
| `pm/infra/*` | ngrok/cloudflared 方案 + launchd plist |
| `pm/board/*` | W1 看板 + 图例 |

### 删除 / 废弃

- 无(没有章节被整章删除,只是细化 / 修改)

---

## W1 关键决策(记录到决策日志)

| 决策 ID | 决策 | 投票人 | 触发 | 落地 |
|---------|------|--------|------|------|
| D-V2-001 | **不做 Android App** | CTO + PM | 8 周不够, V2 范围缩减 | V2.2 章节 + R6 人员风险下降 |
| D-V2-002 | **V2 阶段支付 disable** | CTO + PM + BD | R5 通道对接延期 | V2.1 + MockPaymentAdapter |
| D-V2-003 | **后台 Web only** | CTO + PM | 3 个后台端工程量太大 | V2.2 + 节省 1 人月 |
| D-V2-004 | **iOS 端用 Flutter** | FE Lead | 团队 Flutter 经验比 SwiftUI 多 | FE-B 锁定 Flutter,no android/ |
| D-V2-005 | **W1 demo 范围 = 仅登录页** | PM | 8 周不够,先打 1 步 | 4 端登录页 + 后端 Auth 5 端点 |

---

## W2 计划修订(预告)

W2 主要变更:OpenAPI 3.0 契约 v1 锁版 + 9 国签证流程梳理 + 校验规则 i18n。

预计在 W2 D5 (2026-06-26) 出一份 V2.3 修订纪要。

---

## 评审 checklist(W1 D5 用)

- [ ] V2.1 章节 §4.6 + §4.1.5 内容是否准确?BE-A 验
- [ ] V2.2 章节 §2.1 + §2.3 人员分工表是否对得上?PM + FE Lead 验
- [ ] 风险 R5 + R12 mitigated 状态是否合规?PM 自检
- [ ] 决策日志 D-V2-001 ~ 005 是否有遗漏?全员过一遍
- [ ] docx 和 md 同步?PM 校

---

## 修订记录

| 日期       | 变更人 | 变更                                          |
| ---------- | ------ | --------------------------------------------- |
| 2026-06-11 | PM     | 初版 V0.5(W1 占位)                            |
| W1 D5      | PM     | V1.0 定稿 + docx 同步                          |
| W2 D5      | PM     | V2.3 OpenAPI 锁版更新                          |
