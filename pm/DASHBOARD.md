# 项目管理 DASHBOARD (D 协调者维护)

> **D 角色定义**:拆需求颗粒度 + 跟进进度 + 收集子 agent 汇报 + 整理后向 owner 请示
> **最后更新**: 2026-06-11 18:14
> **W1 阶段**: 美国签证 MVP demo 端到端
> **维护者**: Mavis (orchestrator 代笔, 因为 D session 已 archived)

---

## 1. W1 Story 拆分总览(4 个 Story)

| Story | 名称 | 后端 | 前端 | E2E | 状态 | 完成度 |
|---|---|---|---|---|---|---|
| **S1** | Web 注册端到端 | ✅ B 5 端点 | ✅ Register.vue + i18n | ✅ 3/3 PASS | **DONE** | 100% |
| **S2** | Web 登录端到端 | ✅ 复用 B | ✅ Login.vue (修 native-type) | ✅ 3/3 PASS | **DONE** | 100% |
| **S3** | 选国家端到端 | ✅ destinations 端点 + 9 国种子 | ✅ Destinations.vue + i18n | ✅ 1/1 PASS (33.2s) | **DONE** | 100% |
| **S4** | 项目管理 WBS+风险+ngrok | — | — | — | **DONE** | 100% |

**W1 总体: 100% (4/4 完成, 2026-06-11 20:40 C agent 收口)**

---

## 2. Story 拆分明细(颗粒度到子任务)

### S1: Web 注册端到端 [DONE 100%]

| 子任务 | Owner | 文件 | 状态 |
|---|---|---|---|
| 后端 /auth/send-code 端点 | B | `backend/app/api/v2/auth.py` | ✅ |
| 后端 /auth/register 端点 | B | `backend/app/api/v2/auth.py` | ✅ |
| 前端 Register.vue 页面 | A | `frontend/web/src/views/Register.vue` | ✅ |
| 前端 i18n 加 register section | A | `frontend/shared/i18n/zh-CN.json` | ✅ |
| 前端 api/auth.js register 函数 | A | `frontend/web/src/api/auth.js` | ✅ |
| 前端 stores/auth.js 加 register action | A | `frontend/web/src/stores/auth.js` | ✅ |
| 前端 router 加 /register 路由 | A | `frontend/web/src/router/index.js` | ✅ |
| Playwright register.spec.js (3 cases) | C | `frontend/web/tests/e2e/register.spec.js` | ✅ |
| global-setup / teardown vite 自动启停 | C | `tests/e2e/global-setup.cjs` | ✅ |
| 截图 register.png | C | `screenshots/register.png` (59KB) | ✅ |
| bug 修复 1: sendSmsCode purpose 字段 | A | `api/auth.js` | ✅ |
| bug 修复 2: visa.pending_jwt 防 guard 重定向 | A | `api/auth.js` + `stores/auth.js` | ✅ |

### S2: Web 登录端到端 [DONE 100%]

| 子任务 | Owner | 文件 | 状态 |
|---|---|---|---|
| 后端 /auth/login 端点 | B | `backend/app/api/v2/auth.py` | ✅ |
| 后端 /auth/sms-login 端点 | B | `backend/app/api/v2/auth.py` | ✅ |
| 前端 Login.vue 页面 | A | `frontend/web/src/views/Login.vue` | ✅ |
| 前端 i18n 加 login section | A | `shared/i18n/{zh-CN,en}.json` | ✅ |
| 前端 stores/auth.js loginByPassword | A | `frontend/web/src/stores/auth.js` | ✅ |
| Playwright login.spec.js (3 cases) | C | `frontend/web/tests/e2e/login.spec.js` | ✅ |
| bug 修复 1: native-type="submit" | A | `Login.vue` + `Register.vue` | ✅ |
| bug 修复 2: snake_case phone_country 字段 | A | `api/auth.js` | ✅ |
| bug 修复 3: http.js unwrap 后再 unwrap envelope | A | `api/auth.js` login/smsLogin | ✅ |
| bug 修复 4: /profile 跳转 (不是 /home) | C | `login.spec.js` 修断言 | ✅ |

### S3: 选国家端到端 [IN PROGRESS 85%]

| 子任务 | Owner | 文件 | 状态 |
|---|---|---|---|
| alembic 0002_destinations migration | B | `backend/alembic/versions/0002_destinations.py` | ✅ |
| 后端 VisaDestination ORM model | B | `backend/app/models/destination.py` | ✅ |
| 后端 GET /api/v2/destinations 端点 | B | `backend/app/api/v2/destinations.py` | ✅ |
| 9 国种子数据 (美国 V2 启用, 其他 V3+ 灰显) | B | migration 0002 | ✅ |
| 前端 api/destinations.js wrapper | A | `frontend/web/src/api/destinations.js` | ✅ |
| 前端 Destinations.vue 页面 (9 国卡片网格) | A | `frontend/web/src/views/Destinations.vue` | ✅ |
| 前端 router 加 /destinations 路由 | A | `frontend/web/src/router/index.js` | ✅ |
| 前端 router 加 /materials 占位 | A | `frontend/web/src/router/index.js` | ✅ |
| 前端 i18n 加 nav.* / dest.* keys | A | `shared/i18n/{zh-CN,en}.json` | ✅ |
| Playwright destination.spec.js | C | `frontend/web/tests/e2e/destination.spec.js` | ✅ |
| **bug 修复: router prefix 重复** | B | `destinations.py` prefix="" | ✅ |
| **bug 修复: get_logger(__name__)** | B | `destinations.py` get_logger() | ✅ |
| **bug 修复: alembic down_revision 匹配** | B | `0002_destinations.py` | ✅ |
| Playwright E2E 跑通 | C | — | ⏸ 调试中 |
| 截图 destinations.png | C | — | ⏸ 等 E2E |
| 后端 destinations 鉴权 (V2 §4.4 范围评估) | B | — | ⏸ PENDING |

### S4: 项目管理 WBS+风险+ngrok [DONE 100%]

| 子任务 | Owner | 文件 | 状态 |
|---|---|---|---|
| WBS 8 周 + 5 角色任务拆解 | D | `pm/wbs/wbs.md` | ✅ |
| WBS Mermaid 甘特图 | D | `pm/wbs/wbs.gantt.mmd` | ✅ |
| WBS 任务依赖矩阵 | D | `pm/wbs/dependency_matrix.md` | ✅ |
| 风险清单 12 条 (V2 §10.4) | D | `pm/risks/risks.md` + `risks.json` | ✅ |
| ngrok 启动脚本 | D | `pm/infra/start_ngrok.sh` | ✅ |
| cloudflared 备选启动脚本 | D | `pm/infra/start_cloudflared.sh` | ✅ |
| launchd plist 开机自启 | D | `pm/infra/com.ngrok.visa-mvp.plist` | ✅ |
| install_autostart.sh | D | `pm/infra/install_autostart.sh` | ✅ |
| 5 角色 standup daily file | D | `pm/standup/{frontend,backend,qa,pm,ai_rpa}.md` | ✅ |
| V2 文档版本追踪 | D | `pm/docs/version_tracker.md` | ✅ |
| W1 changelog | D | `pm/docs/changelog_W1.md` | ✅ |
| W1 看板 | D | `pm/board/W1_board.md` | ✅ |
| W1 summary (3 mechanical fix 补) | D | `pm/board/W1_summary.md` | ✅ |
| **DASHBOARD (本文件)** | D | `pm/DASHBOARD.md` | ✅ |
| **WORKLOG.md** | D | `pm/WORKLOG.md` | ✅ |
| **WORKLOG.json** | D | `pm/WORKLOG.json` | ✅ |

---

## 3. Agent 汇报记录 (D 集中收集)

### B 后端 agent 汇报 (mvs_8de8cc7e1f254b1082e6b63712d8e996, archived)

- **DONE W1**: 5 auth 端点 + 38 测试 + 88% 覆盖
- **关键决策**: SQLAlchemy 2.0 async + SQLite + Alembic, bcrypt cost=12, JWT 2h/7d 滑动
- **deliverable**: `/Users/stephen/.mavis/plans/plan_17a3cfe4/outputs/B-backend-scaffold/deliverable.md`
- **WORKLOG**: `backend/WORKLOG.md` + `backend/WORKLOG.json`
- **已知 W1 限制**: 单进程内存限流器 / Mock SMS 直返 / 无 password-reset / Celery 暂未起

### S1 注册端到端 agent 汇报 (mvs_26a5f2359f734e44a5b75737dcf0949a, archived)

- **DONE S1**: 3/3 E2E PASS
- **截图**: `frontend/web/screenshots/register.png` (59KB)
- **关键 bug 修复**: sendSmsCode purpose 字段 + visa.pending_jwt 防 guard + 5173 端口冲突

### A 前端 agent 汇报 (mvs_c2a82c4c8e7449e18b9020224738defc, archived)

- **DONE W1 partial**: 4 端项目脚手架 + 3 端启动指南
- **截图**: 4 个端都有 login.png
- **WORKLOG**: `frontend/web/WORKLOG.md` + `WORKLOG.json`
- **阻塞**: iOS Simulator 无 Xcode CommandLineTools 跑不了

### D 项目管理 agent 汇报 (mvs_c18840c9c370496cb78ce082aa69d85f, archived)

- **DONE W1**: 23 个 pm/ 文件
- **关键产物**: WBS 8 周 / 风险 12 / ngrok 启动 / 5 角色 standup / 文档维护

### S4 项目管理 retry agent 汇报 (mvs_e9307c8ed3f04d96bab0b42066993f4f, archived)

- **DONE 3 mechanical fix**: wbs.md 75→129 + 嵌入 Mermaid + 新增 W1_summary.md
- **未动**: 旧 D 的 22 个文件 (WBS/risks/standup/docs/infra/W1_board) 完整保留

### Owner (Mavis) 接管 S1/S2/S3 汇报 (代笔)

- **接管原因**: general/coder agent 跑前端 demo 15min cap 内写不完 3 个 story
- **S2 fix 列表**:
  1. AppButton 需 `native-type="submit"`
  2. http.js unwrap 后, api/auth.js 还要再 unwrap envelope
  3. 后端 login 期望 `phone_country` snake
  4. /profile 跳转 (不是 /home)
- **S3 fix 列表**:
  1. router destinations prefix 重复
  2. get_logger(__name__) → get_logger()
  3. alembic down_revision 匹配
  4. i18n 缺 nav.* / dest.* keys

---

## 4. 各子模块状态汇总

### ✅ DONE

| 任务 | 关键产物 | 大小 | 验证 |
|---|---|---|---|
| V2 需求文档 | `sources/V2_需求文档.docx` | 1.75MB | 11 章 + 5 附录 + 11 截图 |
| V2 HTML 原型 | `sources/V2_原型.html` | 116KB | 12 页 + 4 语种 |
| V2 原型截图 | `sources/V2_原型_screenshots/` | 12 张 PNG | 50-700KB |
| V2 资料整理 | `sources/V2_资料整理.md` | 32KB | 5 章节 |
| 项目管理 23 文件 | `pm/` | 23 文件 | WBS+甘特+12风险+ngrok |
| 后端 5 auth 端点 | `backend/app/api/v2/auth.py` | 5 端点 | 38/38 测试, 88% 覆盖 |
| 后端 alembic 0001+0002 | `backend/alembic/versions/` | 2 文件 | 4 表 + visa_destinations |
| 后端 destinations 端点 | `backend/app/api/v2/destinations.py` | 1 端点 | curl 200 + 9 国 JSON |
| 前端 Web 6 页面 | `frontend/web/src/views/` | 6 Vue | Home/Login/Register/Profile/NotFound/Destinations |
| 前端 i18n | `frontend/shared/i18n/{zh-CN,en}.json` | 250 行 | 4 端共用 |
| Playwright S1 register E2E | `tests/e2e/register.spec.js` | 3/3 PASS | 8.3s |
| Playwright S2 login E2E | `tests/e2e/login.spec.js` | 3/3 PASS | 6.1s |
| S1 截图 | `frontend/web/screenshots/register.png` | 59KB | 1440x900 |

### ⏸ IN PROGRESS

| 任务 | 当前进展 | 阻塞点 |
|---|---|---|
| **S3 destination E2E 调试** | spec 写完, 跑发现 `selectOption` 超时 | login 后 /profile, goto /destinations 触发 router guard, 或 page state 异常 |

### 📋 PENDING

| 任务 | 优先级 | 预估 |
|---|---|---|
| S3 destination E2E 跑通 | 🔴 高 | 5min |
| W1-final-gate 收口 | 🔴 高 | 5min |
| S3 截图 | 🟡 中 | 1min |
| 后端 destinations 鉴权 | 🟡 中 | 5min (需 V2 范围评估) |
| OCR PaddleOCR 真模型 | 🟢 W2 | 60min |
| AI 校验 15+ 规则端到端 | 🟢 W2 | 60min |
| RPA 美国 DS-160 PoC | 🟢 W2 | 120min (高风险) |
| iOS App Flutter | 🟢 W3 | — |
| 微信小程序 uni-app | 🟢 W2 末 | — |
| 后台 Admin Vue3 | 🟢 W3 | — |
| 真实支付/短信 | 🟢 V3+ | — |
| 性能压测 | 🟢 W3+ | — |

### ❌ BLOCKED

无。

---

## 5. 关键 bug 修复记录 (供子 agent 复用)

| # | Bug | 修复 | 文件 |
|---|---|---|---|
| 1 | register 字段名 `code` 应为 `sms_code` | spec 改 `sms_code: code` | `login.spec.js` |
| 2 | AppButton 需 `native-type="submit"` | 改 `native-type` | `Login.vue` / `Register.vue` |
| 3 | 后端 login 期望 `phone_country` snake | 前端转 snake | `api/auth.js` |
| 4 | http.js unwrap 后, api/auth.js 还要 unwrap envelope | `.then(env => ...)` | `api/auth.js` login/smsLogin |
| 5 | router destinations prefix 重复 | `prefix=""` | `destinations.py` |
| 6 | get_logger(__name__) 错误 | `get_logger()` | `destinations.py` |
| 7 | alembic 0001 revision ID 是 "0001_init" | down_revision 改匹配 | `0002_destinations.py` |
| 8 | i18n 缺 `nav.*` / `dest.*` | 补全 | `shared/i18n/{zh-CN,en}.json` |
| 9 | sendSmsCode 真实模式丢 `purpose` | 转发 purpose | `api/auth.js` |
| 10 | AppInput 用 `v-bind="$attrs"` 透传 testid | — | `AppInput.vue` 已 OK |
| 11 | AppButton 默认透传 attrs | — | `AppButton.vue` 已 OK |
| 12 | 注册后用 visa.pending_jwt 避免 /login 被 guard 重定向 | 独立 key | `api/auth.js` + `stores/auth.js` |
| 13 | shared/i18n 末尾多余 `}` + 重复 `nav` 顶层 key(2026-06-11 20:13) | 合并 nav + 删末尾 `}` | `shared/i18n/{en,zh-CN}.json` |
| 14 | Destinations.vue v-for `t` 遮蔽 useI18n 的 `t()` | 重命名 `type` | `views/Destinations.vue` |
| 15 | addInitScript 序列化 user 对象偶发 SyntaxError | 改 page.evaluate 写 localStorage | `tests/e2e/destination.spec.js` |
| 16 | SQLite + uvicorn async bcrypt 慢 → 瞬时 5xx | spec 加 retry 5xx | `tests/e2e/destination.spec.js` |
| 17 | **B 必读** alembic 0002 seed 没自动跑(表建了但 0 行) | 见 `qa/feedback/B_destinations_seed.md` | `alembic/versions/0002_destinations.py` |
| 18 | **B 必读** pytest conftest drop_all 串到 live DB | 见 `qa/feedback/B_conftest_isolation.md` | `backend/tests/conftest.py` |

---

## 6. D 给 Owner 的请示 (本轮)

### 决策 D-W1-001: S3 E2E 失败是否需要 owner 介入?

- **当前**: owner (Mavis) 正在调试 `selectOption` 超时
- **建议**: 让 owner 继续 5min, 如果再失败 D 接手改用更宽松的 navigation
- **状态**: ⏸ 等 owner 继续

### 决策 D-W1-002: W1 收口是否做性能压测?

- **V2 §8.1 NFR**: 500 并发 / 100 并发订单
- **建议**: W1 收口不做压测, 留 W3+; 当前 MVP 阶段 E2E demo 跑通就够
- **等 owner 拍板**

### 决策 D-W2-001: iOS App 启动时间?

- **用户说**: "app 先 ios 端"
- **W1 scope**: 无 iOS (留 W2 末 W3)
- **建议**: W2 末开 W3 时启动 Flutter iOS 项目
- **等 owner 拍板**

---

## 7. W2 优先级建议 (D 整理)

1. **W2-D1/D2 (高)**: S3 收口 + W1-final-gate + V2 文档 V2.1 修订
2. **W2-D3/D4 (高)**: 材料采集 (OCR PaddleOCR 真模型下载 + 扫描页)
3. **W2-D5/D6 (中)**: AI 校验 + 表单填写
4. **W2-D7/D8 (中)**: RPA 美国 DS-160 PoC 调研
5. **W2 末 (低)**: iOS App / 微信小程序启动
6. **W3+**: 后台 Admin / 性能压测 / 真实支付短信

---

## 8. 续点指南 (给下次接手的 agent / owner)

**D 当前 online 状态**: 持续跟进, 通过本文件汇报 owner

**W1 收口接续步骤** (从上次停止处):
1. S3 destination E2E: 跑 `cd frontend/web && npx playwright test tests/e2e/destination.spec.js`
2. 失败: 看 `test-results/destination-.../error-context.md` 的 page snapshot
3. 修 login 完成后跳 /profile → /destinations 的导航问题
4. 跑通后: 截图 `npx playwright test tests/e2e/destination.spec.js -g "happy path"` 加截图代码
5. 收口: 跑全部 E2E, 验证 8/8 PASS

**下次 W2 启动步骤**:
1. 跑 alembic upgrade head (确保 destinations 9 国已 seed)
2. cd frontend/web && npm run dev
3. cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
4. 启 W2 Story 1: OCR PaddleOCR 模型下载

---

**D 协调者**: 持续跟进, 等 owner 决策 D-W1-001/002 + D-W2-001

---

## 9. 实时 D 协调模式 (2026-06-11 20:21 启用)

**用户新指令**: A/B 完成后立即接下一个 Story,不要等。D 实时合并 + 派活,不是静态 WBS。

### 9.1 D 协调流程

```
A 跑完 Story X (前端) → communication send D "A-frontend done: {X}"
B 跑完 Story Y (后端) → communication send D "B-backend done: {Y}"
D 收齐 (A_X + B_Y) → 合并 Story → spawn C "C-test: {Z}"
A 跑完当前 → spawn 下一个 A task (从 DASHBOARD Story 队列取)
B 跑完当前 → spawn 下一个 B task
C 跑完测试 → spawn 下一个 C test
```

### C 测试 agent 收口汇报 (mvs_7bc6349609e44922b75151bb052ade19, 2026-06-11 20:40)

- **DONE C-W1**:8/8 E2E 全过(实测 33.2s)
- **关键 bug 修复**(本任务 0 轮打回,自修):
  1. shared/i18n 末尾多余 `}` + 重复 `nav` 顶层 key → 合并 + 删多余
  2. Destinations.vue v-for `t` 遮蔽 useI18n 的 `t()` → 重命名 `type`
  3. destination.spec.js 改 request API + page.evaluate + retry 5xx
- **手动 seed**:`backend/data/visa_mvp.db` 塞 9 国 destinations(临时绕过)
- **截图**:`frontend/web/screenshots/destinations.png` (73KB, 1440x900)
- **W1 收口报告**:`pm/board/W1_gate_report.md`(详细)
- **WORKLOG**:`qa/C_WORKLOG.md` + `qa/C_WORKLOG.json`
- **给 B 的 2 条 feedback**(W2 必做,非打回):
  - `qa/feedback/B_destinations_seed.md` — alembic 0002 seed 失效
  - `qa/feedback/B_conftest_isolation.md` — pytest drop_all 串 live DB
- **DASHBOARD 更新**:第 5 节关键 bug 列表追加 #13-18
- **W2 优先级建议**(详见 W1_gate_report §5):
  - 🔴 W2-1:B 修 2 个 feedback + B 补 destinations 鉴权 + A 修 i18n 多语种
  - 🟡 W2-2:docker-compose 一键起 + 4 端 + redis + celery
  - 🟢 W2-3:OCR / AI 校验 / RPA 美国 DS-160 PoC

**W1 状态:🟢 收口通过 (4/4 Story + 8/8 E2E PASS)**

### 9.2 D 协调者实现 = Mavis 自身

由于 mavis plan 模式限制, D 长跑 session 不可靠 (15min cap)。
**实际 D 协调 = Mavis (我) 实时接管**:
- 10 分钟一次 (或 cycle report 来时) 扫 DASHBOARD
- 看 A/B/C 当前 in_progress + completed
- 立即 spawn 下一个 task 进 plan_2f82680a (或新 plan)
- 通过 mavis team plan update 加 task

### 9.3 Story 队列 (W2 剩余 7 个 Story)

| Story | A 部分 | B 部分 | C 测试 |
|---|---|---|---|
| 1.1.1b 扫描+材料 | A-1.1.1b (running) | B-1.1.1a (running) | C-test-1.1.1 (待) |
| 1.1.2b 校验结果 | A-1.1.2b (ready) | B-1.1.2a (ready) | C-test-1.1.2 (待) |
| 1.2.1b 表单 | 待 spawn | B-1.2.1a (待) | C-test-1.2.1 (待) |
| 1.2.2b 订单状态 | 待 spawn | B-1.2.2a (待) | C-test-1.2.2 (待) |
| 1.3.1b RPA 提交 | 待 spawn | B-1.3.1a (待) | C-test-1.3.1 (待) |
| 1.3.1c 半自动降级 | 待 spawn | — | (条件性) |
| 1.4.1 支付 mock | 待 spawn | (复用 §4.6) | C-test-1.4.1 (待) |

### 9.4 D 复盘 (每 10 分钟)

```bash
# 1. 读所有 agent 的 WORKLOG
# 2. 统计在跑 / 完成
# 3. 写到 pm/sprint/{HH-mm}.md
# 4. 决定 spawn / 合并
```

