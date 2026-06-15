# W1 总结(PM 视角)

> Story 4 任务 spec 要求的"W1 总结"交付物。配套 `pm/board/W1_board.md`(更细的逐任务看板,To Do / In Progress / Done / Blocked 四列)。
> 维护:PM;更新:W1 D5 末 + W2 滚动。

---

## 1. W1 完成的 4 个 story(脚手架周)

| Story | 范围                                                    | 验收物                                                                                    | 状态 |
| ----- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---- |
| S1    | Web 端注册端到端(前端 + Playwright E2E)                | 4 端登录页 + 后端 Auth 5 端点 + Web E2E 录屏                                             | done |
| S2    | 后端 W1:FastAPI + SQLite + 账号模块跑通                  | `backend/app/` + 5 auth 端点 + pytest 覆盖率 ≥ 80% for auth                              | done |
| S3    | V2 需求文档 markdown 化                                  | `pm/docs/` V2.0 → V2.1 → V2.2 + 评审纪要                                                  | done |
| S4    | 项目管理:WBS + 风险 + ngrok + 文档                       | `pm/wbs/wbs.md`(129 任务) + `pm/risks/risks.md`(12 风险) + `pm/infra/start_ngrok.sh` + 本文档 | done |

> 4 story 全部 done,W1 Gate 通过。

---

## 2. W2 优先级(2026-06-22 ~ 2026-06-26,契约 + 选国 + 设计系统周)

按 M2 里程碑(契约 + 选国 + DEMO)倒推,W2 必须交付:

| 优先级 | 任务(节选自 `pm/wbs/wbs.md` §2)                | Owner | 验收物                              |
| ------ | ----------------------------------------------- | ----- | ----------------------------------- |
| P0     | B2.1 OpenAPI 3.0 YAML 契约(后端先出 v0.5)       | BE-A  | `backend/openapi.yaml` + Swagger UI |
| P0     | F2.1-F2.3 选国页(Web/iOS/小程序 3 端同步)       | FE-A/B/C | 选国页静态 + i18n 9 国        |
| P0     | A2.1-A2.2 RPA 框架骨架 + 第一个 demo              | AI-B  | Playwright 跑通 1 个目标站点 demo   |
| P1     | P2.x 9 国流程梳理(每国关键问题清单)             | PM    | 9 张流程图 + 风险标记              |
| P1     | F2.4-F2.7 共用组件(列表/卡片/校验/状态)         | FE-A  | Storybook / 截图                    |
| P1     | B2.2-B2.4 Materials / Orders 模型 + API         | BE-A  | migration + 端点                   |
| P2     | QD2.x 集成测试 + e2e 接入                       | QA-A  | 集成测试套件 + 录屏                |
| P2     | D-W2-01 ~ D-W2-05(PM 维护:standup/风险/V2/W2 看板) | PM    | `pm/standup/` + `pm/board/W2_*.md` |
| P3     | D-W2-06 ngrok 真实拉一次 + 写 backend/.env      | PM    | 临时域名 + 截图                    |
| P3     | D-W2-07 W2 Gate 报告                          | PM    | `pm/board/W2_gate_report.md`       |

---

## 3. 已知问题(W1 末)

### 3.1 已暴露(W1 内已记录 / 处理中)

| ID    | 问题                                                          | 触发点           | 状态      | 缓释 / 责任         |
| ----- | ------------------------------------------------------------- | ---------------- | --------- | ------------------- |
| K-01  | 端到端 demo(Web → BE)W1-D4 卡 BE 端 5 端点未跑通           | W1-D4 站会       | mitigated | BE-A W1-D2 末完成,Web D3 接 — 实际已通,关闭 |
| K-02  | 4 端登录页截图不齐(等 BE 跑通后补)                          | W1-D4 站会       | resolved  | B-001 解决后已收齐 |
| K-03  | PM 风险登记 R1/R3 未做 W1 实际触发评估                        | W1-D5 self-audit | open      | PM W1-D5 末补评,记入 risks.md "W1 末评审" |
| K-04  | 团队关键岗位(CTO/AI 负责人)招聘未启动                        | W1-D5 站会       | open      | R6 owner = CEO,本周内启动招聘 |
| K-05  | DevOps 角色空缺(无独立 DevOps,R6 风险下游)                  | W1 全周          | open      | 后端兼 DevOps,云资源先不买,本地 docker-compose |
| K-06  | V2 文档 v1.0 缺支付章节细化(V2.1 disable 支付后未回填)        | W1-D5 self-audit | mitigated | V2.2 已声明 "V2 支付 disable,V3+ 接通" |
| K-07  | 小程序类目"工具 vs 金融/移民"待法务签字                        | W1-D5 站会       | mitigated | R12 owner = 产品,本周内完成 |
| K-08  | 100 张护照样本(占位 0/100)实际只有 12 张                      | W1-D5 self-audit | open      | A1.3 owner = AI-A,W2 补到 60,W3 100 |

### 3.2 风险登记联动(详见 `pm/risks/risks.md`)

W1 触发情况 → 风险状态更新:

- R1 PaddleOCR 准确率:未触发(W3 才需要,W1 准备阶段)→ 维持 open
- R2 RPA 反爬:未触发(W5 才需要)→ 维持 open
- R3 ddddocr:已跑通 demo(AI-B 报告)→ 维持 open,W2 准备 200+ 自训数据集
- R4 iOS 审核:W6 才需要 → 维持 open
- R5 支付延期:已 mitigated(V2 disable 支付,V3+ 跟进)
- R6 团队到位:未触发,但 K-04 暴露 → 维持 open,本周内启动招聘
- R7 OCR CPU:未触发(MVP 阶段)→ 维持 open
- R8 加密性能:未触发(B1.x 阶段不涉及)→ 维持 open
- R9 翻译质量:未触发(F1.3 30 key 落地,关键 50 字符串清单 W2 出)→ 维持 open
- R10 UI 一致性:F1.12 design-token JSON W1 完成,降级风险降为低 → 维持 open
- R11 隐私:未触发(W2 起准备)→ 维持 open
- R12 业务方对"无活体"顾虑:已 mitigated(选工具类目,待法务签字)

### 3.3 阻塞 / 风险预告(W2 必须解决)

- **B-W2-01**: OpenAPI 契约若 W2-D2 末未出 v0.5,前端 3 端选国页全部延期 → 倒推 BE-A W2-D1 启动
- **B-W2-02**: RPA 框架骨架若 W2-D4 末不通,RPA W5 跑通目标悬空 → A2.2 必须 W2-D4 末 demo
- **B-W2-03**: 招聘若 W2 末仍无 CTO,4-6 周后(中期 demo)技术决策无人拍板

---

## 4. 关键数字

| 指标                  | 数值  | 备注 |
| --------------------- | ----- | ---- |
| 4 端脚手架            | 4/4   | web / ios / miniprogram / admin 全部就位 |
| 后端 Auth 端点        | 5/5   | register / login / refresh / logout / me |
| pytest 覆盖率(auth)  | ≥ 80% | B1.x 完成 |
| 设计 token            | 1 套  | F1.12 输出,3 端共用 |
| i18n key 数           | 30+   | zh-CN + en 双语 |
| 风险登记条目          | 12    | V2 §10.4 全部录入 |
| WBS 任务数            | 129   | 5 角色 × 8 周 + W1 每日清单 |
| 启动 ngrok 一行命令   | 1 行  | `bash pm/infra/start_ngrok.sh` |

---

## 5. 修订记录

| 日期       | 变更人 | 变更                                                                    |
| ---------- | ------ | ----------------------------------------------------------------------- |
| 2026-06-11 | PM     | 初版 V1,W1 D5 末评估                                                     |
| W2 D5      | PM     | W2 实际进度 + 风险联动,关闭 K-01/K-02,滚动 K-03 ~ K-08                  |
| W3 D5      | PM     | W3 实际进度                                                              |
| ...        | PM     | 每周五滚动                                                              |
