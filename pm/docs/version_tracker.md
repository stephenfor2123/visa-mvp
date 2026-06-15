# V2 文档版本追踪

> 主文档:`/Users/stephen/Desktop/签证项目/sources/V2_需求文档.docx` + `.md`
> PM 维护:每次改完,版本号 +1 + 在本表 + `pm/docs/changelog_*.md` 写一条
> 当前版本:**V2.0**(2026-06-11 baseline)

---

## 版本树

```
V0 (2026-05)
  └─ V1 (2026-06-09) - 加入 Atlys 竞品分析 + 18 页 HTML 高保真原型
       └─ V2.0 (2026-06-11) - V0 升级 + V1 UX 沿用 + 11 章完整 + 8 周排期
            ├─ V2.1 (W1 末 2026-06-19 计划) - 支付 mock 决策
            │   └─ 改变:V2 默认 total_amount=0, 支付 disable, SMSChannel + PaymentAdapter 抽象预留
            └─ V2.2 (W1 末 2026-06-19 计划) - iOS 先行 + 后台 Web only
                └─ 改变:V2 不做 Android App, 后台只做 Web 端
```

---

## 修订对照表(滚动)

| 版本 | 日期 | 类型 | 改动摘要 | 触发者 | 影响范围 |
|------|------|------|---------|--------|---------|
| V0 | 2026-05 | baseline | 初版骨架,11 章 | - | 全文 |
| V1 | 2026-06-09 | minor | Atlys 竞品 + 18 页原型 | PM | 全文 + 新增原型 |
| V2.0 | 2026-06-11 | major | V0 升级 + V1 UX 沿用 + 11 章完整 + 8 周排期 | PM | 全文 |
| V2.1 | 2026-06-19 (W1 D5 计划) | minor | 支付 mock 决策: V2 disable, V3+ 接通 | PM + BE | §4.6 支付 / §10.4 R5 |
| V2.2 | 2026-06-19 (W1 D5 计划) | minor | iOS 先行 + 后台 Web only(不做 Android) | PM + FE | §2.1 终端能力 / §10.2 人员 |
| V2.3 | 2026-06-26 (W2 D5 计划) | minor | OpenAPI 契约 v1 锁版 | PM + BE | §9 OpenAPI |
| V2.4 | 2026-07-03 (W3 D5 计划) | minor | OCR 准确率收口(80% → 95%) | PM + AI | §10.1.2 / §10.4 R1 |
| V2.5 | 2026-07-10 (W4 D5 计划) | minor | 校验规则 15 条 V1 锁版 | PM + AI + FE | §3.4 / §4.5 |
| V2.6 | 2026-07-17 (W5 D5 计划) | minor | RPA 5 天稳定性数据 | PM + AI | §3.5 / §10.1.3 / R2/R3 |
| V2.7 | 2026-07-24 (W6 D5 计划) | minor | 性能 P95 + iOS TF 提交 | PM + QA | §10.1.7 / R4/R7 |
| V2.8 | 2026-07-31 (W7 D5 计划) | minor | UAT 验收清单 + 渗透测试 | PM + QA | §10.1 |
| V2.9 | 2026-08-07 (W8 末 计划) | major | 上线前最终版 + Gate 报告 | PM | 全文 |

---

## 当前进行中的变更(W1 末要做)

### V2.1 - 支付 mock 决策
- 章节:§4.6 支付适配器
- 改动:增加 "V2 阶段:支付 disable,total_amount=0,PaymentAdapter 走 mock 实现"
- 落地位置:`backend/app/services/payment.py` 新增 `MockPaymentAdapter` 类
- 验收:curl `POST /api/v2/orders` 不会因为支付失败而 5xx

### V2.2 - iOS 先行 + 后台 Web only
- 章节:§2.1 终端能力矩阵
- 改动:删除 Android 行,只保留 iOS(Flutter);后台只做 Web 端
- 章节:§10.2 人员分工
- 改动:Android 开发从 W1-W8 任务表删除
- 章节:§1.4 红线清单
- 改动:增加"无 Android 端"声明,避免误读
- 验收:V2.2 周五评审后,FE-A 团队释放 0.5 人力去做 iOS + 后台

---

## 文档维护 checklist(每周)

- [ ] 是否改了 §X?改了 → 在版本表 +1
- [ ] 是否新增了端点?新增 → OpenAPI 同步更新
- [ ] 是否改了规则?改了 → 校验规则 JSON 同步
- [ ] 是否新增了页面?新增 → V2 原型 HTML 同步
- [ ] 是否改了风险?改了 → 风险登记 + 紧急度重排
- [ ] changelog 写一行 `[YYYY-MM-DD] Vx.y - 简述`

---

## 维护人

- 主维护:PM (D)
- 评审:CTO + Lead
- 文档源:`/Users/stephen/Desktop/签证项目/sources/V2_需求文档.docx` (.md 是源)
- 修订工具:本表是索引,正文用 docx 编辑(md 是导出)

---

## 修订记录

| 日期       | 变更人 | 变更                                  |
| ---------- | ------ | ------------------------------------- |
| 2026-06-11 | PM     | 初版 V1, 12 周滚动修订计划            |
| W1 D5      | PM     | V2.1 + V2.2 落地                      |
| W2 D5      | PM     | V2.3 OpenAPI 锁版                     |
