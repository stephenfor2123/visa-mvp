# W1 看板 · To Do / In Progress / Done / Blocked

> 状态:`To Do` / `In Progress` / `Done` / `Blocked` · 每日 9:45 站会前更新
> 任务来源:4 agent WORKLOG + WBS W1 · 图例见 `pm/board/board_legend.md`
> 当前日期(占位):2026-06-15 ~ 2026-06-19

---

## 1. To Do(未开始,W1 末目标全部 Done)

| ID    | 任务                                       | Owner      | 计划日   | 关联            |
| ----- | ------------------------------------------ | ---------- | -------- | --------------- |
| T-001 | V2 文档范围评审会                          | PM         | W1-D1    | P1.1            |
| T-002 | FastAPI 0.110 脚手架                       | BE-A       | W1-D1    | B1.1            |
| T-003 | SQLAlchemy 2.0 async + SQLite 引擎         | BE-A       | W1-D1    | B1.2            |
| T-004 | Alembic init + 4 表 migration              | BE-A       | W1-D1    | B1.4            |
| T-005 | Vite + Vue3 + Element Plus init(web)       | FE-A       | W1-D1    | F1.1            |
| T-006 | flutter create --platforms=ios             | FE-B       | W1-D1    | F1.5            |
| T-007 | uni-app x init(小程序)                     | FE-C       | W1-D1    | F1.8            |
| T-008 | pytest + conftest + 1 示例                 | QA-A       | W1-D1    | QD1.1,QD1.2,QD1.3|
| T-009 | ddddocr demo                               | AI-B       | W1-D1    | A1.5            |
| T-010 | 100 张护照样本(占位 0/100)                | AI-A       | W1-D1-D4 | A1.3            |
| T-011 | 校验规则 15 条 JSON 草案                   | AI-A       | W1-D2    | A1.4            |
| T-012 | Dockerfile.ocr                             | AI-A       | W1-D2    | A1.2            |
| T-013 | 5 个 auth 端点                             | BE-A       | W1-D2    | B1.6-B1.10      |
| T-014 | JWT + bcrypt                               | BE-A       | W1-D2    | B1.5            |
| T-015 | 限流 + 日志中间件                          | BE-B       | W1-D2    | B1.11,B1.12     |
| T-016 | vue-i18n + 30 key                          | FE-A       | W1-D2    | F1.3            |
| T-017 | iOS 端 intl + ARB                          | FE-B       | W1-D2    | F1.6            |
| T-018 | 小程序 P3 登录页静态                       | FE-C       | W1-D2    | F1.9            |
| T-019 | 4 端共用组件(Button/Card/Input)            | FE-A       | W1-D2    | F1.12, F2.4     |
| T-020 | test_auth.py 13 个用例                     | QA-A       | W1-D3    | QD1.3           |
| T-021 | 后台 Web 脚手架 + 登录页 + Dashboard       | FE-A       | W1-D3    | F1.10           |
| T-022 | 端到端 demo 联调(Web → BE mock)            | FE + BE    | W1-D4    | E-W1-final-gate |
| T-023 | pytest 覆盖率 ≥ 80%                        | QA-A       | W1-D3-D4 | QD1.6           |
| T-024 | docker-compose(后端 + Redis)               | BE-B       | W1-D3    | B1.13           |
| T-025 | ngrok 临时域名跑通                         | PM         | W1-D2    | D-W1-06         |
| T-026 | V2 文档 W1 末更新纪要 v1.0                 | PM         | W1-D5    | D-W1-05         |
| T-027 | W1 Gate 报告 v1.0                          | PM         | W1-D5    | E-W1-final-gate |
| T-028 | 风险登记 V1 评审(标 W1 触发)               | PM         | W1-D5    | D-W1-03         |
| T-029 | 给 CEO/CTO 的 W1 简报                     | PM         | W1-D5    | D-W1-08         |
| T-030 | 看板关 W1 列起 W2 列                       | PM         | W1-D5    | D-W1-07         |

---

## 2. In Progress(进行中)

| ID    | 任务                                       | Owner      | 开始日   | 进度     | 阻塞 |
| ----- | ------------------------------------------ | ---------- | -------- | -------- | ---- |
| T-031 | pm/ 目录 + WORKLOG + WBS 框架              | PM         | W1-D1    | 100%     | 无   |
| T-032 | 风险登记 12 条入库                         | PM         | W1-D1    | 100%     | 无   |
| T-033 | Standup 模板 + 4 角色 daily                | PM         | W1-D1    | 100%     | 无   |
| T-034 | ngrok + cloudflared 脚本 + plist           | PM         | W1-D1    | 100%     | 无   |
| T-035 | V2 文档版本追踪 + W1 changelog             | PM         | W1-D1    | 100%     | 无   |

> PM 任务在 W1-D1 PM 视角已完成(框架 + 占位数据),W1 实际进度由 D2-D5 滚动更新。

---

## 3. Done(已完成)

| ID    | 任务                                       | Owner | 完成日        | 证据                                  |
| ----- | ------------------------------------------ | ----- | ------------- | ------------------------------------- |
| D-001 | pm/ 7 个子目录建好                         | PM    | 2026-06-11    | `pm/{wbs,risks,standup,docs,infra,board}/` |
| D-002 | WORKLOG.md + WORKLOG.json                  | PM    | 2026-06-11    | `pm/WORKLOG.md` + `.json`             |
| D-003 | WBS 8 周 × 5 角色 V1(50 任务 + 25 每日)   | PM    | 2026-06-11    | `pm/wbs/wbs.md` + `.gantt.mmd` + `dependency_matrix.md` |
| D-004 | 风险登记 12 条(risks.md + risks.json)      | PM    | 2026-06-11    | `pm/risks/`                           |
| D-005 | Standup 模板 + 5 角色 daily                | PM    | 2026-06-11    | `pm/standup/*.md`                     |
| D-006 | V2 文档版本追踪 + W1 changelog 草稿        | PM    | 2026-06-11    | `pm/docs/`                            |
| D-007 | ngrok + cloudflared 方案                   | PM    | 2026-06-11    | `pm/infra/*` (4 脚本 + plist + README) |
| D-008 | W1 看板                                   | PM    | 2026-06-11    | `pm/board/W1_board.md`                |

---

## 4. Blocked(阻塞)

| ID    | 任务                                       | Owner | 阻塞日   | 阻塞源       | 解法                          |
| ----- | ------------------------------------------ | ----- | -------- | ------------ | ----------------------------- |
| B-001 | 端到端 demo(Web → BE)                      | 全员  | W1-D4 计划 | BE 端 5 端点未跑通 | BE 端 W1-D2 末完成,A 端 W1-D3 接 |
| B-002 | 截图 4 端                                  | FE    | W1-D4 计划 | 端到端跑通    | B-001 解了就解                 |
| B-003 | W2 起 DevOps 角色到位                     | PM    | W1 末     | CEO 招聘进度  | R6 风险登记跟进                |

---

## 5. 每日滚动(站会后 PM 更新)

### W1-D1 站会纪要(2026-06-15)
- PM: 5 项 PM 任务已就位(WBS/风险/standup/docs/infra/board)
- 全员:无阻塞,等 W1-D1 末 4 端脚手架起完
- 重点:BE-A 下午跑通 alembic migration,这是后续 5 端点的前提

### W1-D2 站会纪要(2026-06-16,占位)
- 4 端 daily 提交:4/4 ✅
- BE 端 5 auth 端点 D2 末出
- ngrok 临时域名跑通,backend/.env 已更新
- 阻塞:无

### W1-D3 站会纪要(2026-06-17,占位)
- 4 端登录页接后端 mock
- QA 测试用例 13 条全 PASS
- 阻塞:无

### W1-D4 站会纪要(2026-06-18,占位)
- 端到端 demo 跑通
- 截图 4 端收齐
- 阻塞:无

### W1-D5 站会纪要(2026-06-19,W1 收口)
- 风险登记 V1 评审(2 mitigated 维持 + W1 实际进度回填)
- V2 文档更新纪要 v1.0
- W1 Gate 报告 v1.0
- 给 CEO/CTO 简报发出

---

## 6. W1 总结(W1 D5 写)

| 指标         | 目标       | 实际       |
| ------------ | ---------- | ---------- |
| 4 端登录页可跑 | ✅         | 待 W1 末确认 |
| BE 5 端点    | ✅ + 覆盖 ≥ 80% | 待 W1 末确认 |
| QA 13 测试   | ✅         | 待 W1 末确认 |
| 端到端 demo  | ✅         | 待 W1 末确认 |
| 4 端截图     | ✅         | 待 W1 末确认 |
| PM 框架      | ✅         | ✅          |
| 风险登记     | 12 条入库  | ✅ 12 条     |
| ngrok 方案   | 一键启动   | ✅          |
| V2 文档 W1 纪要 | v1.0    | ✅ 草稿,周五定稿 |

---

## 7. 修订记录

| 日期       | 变更人 | 变更                                  |
| ---------- | ------ | ------------------------------------- |
| 2026-06-11 | PM     | 初版 V1,30 任务清单 + 4 状态分区      |
| W1 末      | PM     | W1 实际状态回填                       |
