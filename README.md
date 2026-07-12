# Htex · 跨境签证 AI

> **跨境签证一站式服务 MVP** — 用户提交申请、平台 OCR 识别护照字段、支付闭环、状态可实时查询。
> 三端共享同一套 `/api/v2/*` 后端协议：Web（Vue 3，**主攻越南/印尼海外客户**）+ iOS（Flutter）+ 微信小程序（**暂停**）。

[![Build Status](https://img.shields.io/badge/build-WIP-lightgrey.svg)](#构建状态) [![Tests](https://img.shields.io/badge/tests-122%20passed-blue.svg)](#测试) [![Coverage](https://img.shields.io/badge/coverage-TBD-yellow.svg)](#测试) <!-- TODO: 替换为真实 CI badge -->

---

## 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速启动](#快速启动)
- [测试](#测试)
- [文档索引](#文档索引)
- [MVP 状态](#mvp-状态)
- [贡献](#贡献)
- [许可证](#许可证)
- [截图](#截图-占位待补)

---

## 项目简介

**Htex** 是一款跨境签证申请的 MVP 产品，覆盖以下核心闭环：

1. **账号** — 手机号 + 验证码注册 / 登录，JWT 滑动刷新
2. **申请录入** — 选择目的国 / 签证类型 / 出行日期，填写个人信息
3. **材料上传 + OCR** — 护照 / 证件 PDF/JPG/PNG 自动识别 MRZ 字段
4. **RPA 自动递交** — ⏸ MVP 阶段关闭（`FEATURE_RPA_ENABLED=0`），后期再开
5. **支付（Mock/Stripe）** — V2 阶段默认 Mock 通道，V2.1 切换 Stripe
6. **状态查询** — 订单时间线 + WebSocket 推送 + 30s 轮询

支持 **4 语种**：简体中文（zh-CN）/ 英文（en）/ 印尼语（id）/ 越南语（vi），国际化覆盖登录、订单、支付、RPA、管理后台、合规条款等 6 大 section。

> **业务范围**：主攻**越南、印尼海外客户**，帮其办理**美国、申根、英国、澳大利亚**等签证。RPA / 保险 / 微信小程序暂缓。详见 [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)。
> **合规**：法务 review 框架已搭建（`docs/LEGAL_REVIEW_NOTES.md` 18 项 checklist），deadline 2026-06-25。

---

## 技术栈

| 层 | 技术 | 版本 / 备注 |
|---|---|---|
| **后端语言** | Python | 3.11（3.9+ PEP 604/585 backport） |
| **后端框架** | FastAPI | 0.115 + uvicorn 0.32 |
| **ORM / DB** | SQLAlchemy 2.0 (async) + Alembic | SQLite (dev, aiosqlite) / PostgreSQL (prod) |
| **认证** | python-jose (JWT) + passlib (bcrypt) | 5 端点 + Bearer middleware |
| **异步任务** | Celery + Redis 7 | broker + result backend；RPA 长耗时任务 |
| **支付 SDK** | Stripe (V2.1 接入) | V2 阶段 Mock adapter |
| **OCR** | PaddleOCR + OpenCV + Pillow | 9 国护照字段映射 |
| **前端 Web** | Vue 3 + Vite 5 + Element Plus 2.7 | Composition API + Pinia + Vue Router 4 + vue-i18n 9 |
| **前端 iOS** | Flutter 3.19+ / Dart 3.3+ | http + shared_preferences + provider + intl |
| **微信小程序** | 原生 WXML/WXSS/JS | utils/i18n.js + wx.request |
| **E2E 测试** | Playwright 1.60 | 5 个 spec（注册/登录/目的地/i18n/截图） |
| **单元 / 集成** | pytest 8.3 + pytest-asyncio + pytest-cov | 单元 124 + 集成 205 collectable tests |
| **CI / CD** | GitHub Actions | `.github/workflows/ci.yml` 4 jobs / 35 steps |
| **容器化** | Docker + Docker Compose | backend 镜像 + Redis 服务 |
| **日志 / 观测** | loguru + prometheus-client | 结构化日志 + `/metrics` 端点 |

完整 ADR 决策记录见 [`docs/adr/`](docs/adr/)。

---

## 目录结构

```
签证项目/
├── backend/                       # FastAPI 后端
│   ├── app/
│   │   ├── main.py                # FastAPI app + 异常处理
│   │   ├── core/                  # config / db / security / errors / logging
│   │   ├── models/                # SQLAlchemy 2.0 ORM
│   │   ├── schemas/               # Pydantic v2 DTO
│   │   ├── services/              # 业务逻辑（auth/order/payment/rpa/ocr/...）
│   │   ├── api/v2/                # REST 端点（auth/orders/materials/ocr/rpa/...）
│   │   └── middleware/            # 日志 + 限流 + 鉴权
│   ├── alembic/                   # 数据库迁移
│   ├── tests/                     # unit + integration + e2e
│   ├── data/                      # SQLite (gitignored)
│   ├── scripts/                   # backup.py / restore.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README.md                  # 后端专属 README
│
├── frontend/
│   ├── web/                       # Vue 3 SPA
│   │   ├── src/
│   │   │   ├── views/             # 页面组件
│   │   │   ├── components/        # 通用组件
│   │   │   ├── api/               # 后端 client
│   │   │   ├── i18n/              # i18n lazy load
│   │   │   ├── router/            # Vue Router
│   │   │   ├── stores/            # Pinia stores
│   │   │   └── styles/            # SCSS tokens（含 Dark Mode）
│   │   ├── tests/e2e/             # Playwright
│   │   ├── playwright.config.cjs
│   │   └── package.json
│   │
│   ├── ios/                       # Flutter iOS App
│   │   ├── lib/                   # Dart 源码
│   │   ├── ios/                   # iOS Runner
│   │   ├── test/                  # Flutter unit tests
│   │   └── pubspec.yaml
│   │
│   ├── miniprogram/               # 微信小程序
│   │   ├── pages/                 # 页面（WXML/WXSS/JS）
│   │   ├── components/
│   │   ├── utils/                 # i18n / request
│   │   └── app.js / app.json
│   │
│   └── shared/                    # 三端共享 i18n JSON
│       └── i18n/{zh-CN,en,id,vi}.json
│
├── docs/                          # 项目文档
│   ├── ARCHITECTURE.md            # 系统架构 + 数据流 + 横切关注点
│   ├── API.md                     # REST + WebSocket API 参考
│   ├── LEGAL_REVIEW_NOTES.md      # 18 项法务 review checklist
│   ├── stripe-credentials-setup.md
│   ├── d-verify-runner-recipe.md
│   ├── marker.md
│   ├── deliverable-API-doc.md
│   └── adr/                       # 5 个 ADR（FastAPI/Vue3/Mock Payment/i18n/ErrorCode）
│
├── pm/                            # 项目管理
│   ├── board/                     # Sprint board（W1~W15）
│   ├── wbs/                       # WBS 任务树 + 依赖矩阵
│   ├── risks/risks.md             # 风险登记
│   ├── standup/                   # 每日 standup
│   └── DASHBOARD.md               # PM 仪表盘
│
├── outputs/                       # 各 sprint/task 收口产出
│
├── scripts/                       # 顶层脚本（CI 校验、verify-only 等）
│
├── .github/workflows/ci.yml       # GitHub Actions 4 jobs
├── CHANGELOG.md                   # 版本变更日志（Keep a Changelog）
├── CONTRIBUTING.md                # 贡献指南（PR / 分支策略 / 编码规范）
├── FAQ.md                         # 常见问题
├── MVP-LAUNCH-CHECKLIST.md        # MVP 验收清单（A~F 共 23 项）
├── PERFORMANCE.md                 # 性能基线 + 优化记录
├── RUNBOOK.md                     # 运维 runbook（部署 / 备份 / 故障）
├── SECURITY.md                    # 安全策略 + 漏洞披露
├── TESTING.md                     # 测试分层约定 + 命令
├── A_WORKLOG.md / C_WORKLOG.md    # 工作日志（双轨）
└── board.md                       # 总览 board
```

---

## 快速启动

> **前置**：Python 3.11+ / Node 18+ / Docker (可选) / Flutter 3.19+ (iOS 构建用)。

### 1. 后端（FastAPI）

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 初始化 DB（dev 用 SQLite）
.venv/bin/alembic upgrade head

# 起服务（默认 :8000）
.venv/bin/uvicorn app.main:app --reload --port 8000

# 健康检查
curl http://localhost:8000/health
# => {"status":"ok","app":"Htex API","version":"0.1.0"}
```

**Docker Compose 一键起**（含 Redis）：

```bash
cd backend
cp .env.example .env
docker compose up --build
```

> **测试模式 SMS**：任意 6 位数字都通过；生产改 `SMS_CHANNEL=twilio`。
> 详见 [`backend/README.md`](backend/README.md) §1-§10。

### 2. 前端 Web（Vue 3 + Vite）

```bash
cd frontend/web
npm install
npm run dev            # http://localhost:5173

# 生产构建
npm run build
npm run preview        # :4173 预览 dist/

# 代码质量
npm run lint
```

> **macOS M1 警告**：`npm run build` 在 macOS M 系列可能静默挂起（vite + Element Plus 树摇扫描），优先走 Playwright + Chrome --headless fallback（参见 `RUNBOOK.md` 故障章节）。

### 3. iOS App（Flutter）

```bash
cd frontend/ios
flutter pub get
flutter run -d ios               # iOS 模拟器
flutter build ios --no-codesign  # 产物 build/ios/iphonesimulator/Runner.app
```

### 4. 微信小程序

```bash
cd frontend/miniprogram
npm install                      # 可选，依赖较轻
# 用微信开发者工具导入 miniprogram/ 目录即可
```

### 5. 默认账号

| 用途 | 凭据 |
|---|---|
| C 端测试账号 | 手机号 `13800138000` / 密码 `abc12345` / 验证码任意 6 位 |
| 后台管理员 | 用户名 `admin` / 密码 `admin123`（**仅 dev mock**，生产前必须改密） |

---

## 测试

测试分三层（详见 [`TESTING.md`](TESTING.md)）：

### 5.1 后端单元 + 集成（pytest）

```bash
cd backend
.venv/bin/pytest                                  # 全跑
.venv/bin/pytest tests/unit/                      # 只跑单元
.venv/bin/pytest tests/integration/               # 只跑集成
.venv/bin/pytest --collect-only                   # 先验证 collection 0 error
.venv/bin/pytest --cov=app --cov-report=html:tests/reports/coverage
```

**当前基线**：W14-1 (19/19) + W14-9 (103/115, 12 skipped) = **122 PASS**，0 failed。

### 5.2 前端 E2E（Playwright）

```bash
cd frontend/web

# 前置：先起后端 (http://127.0.0.1:8000)
npx playwright test                       # 全跑 5 个 spec
npx playwright test register.spec.js      # 只跑注册
npx playwright test --headed              # 有头模式（调试用）
npx playwright test --ui                  # UI 模式
```

`globalSetup` 会自动起 `vite dev server` (:5173)，`workers: 1` + `fullyParallel: false` 保证注册流程 DB 状态串行。

### 5.3 前端单元（vitest）

```bash
cd frontend/web
npm run test                # vitest run
npm run test:watch
```

### 5.4 iOS 测试（flutter test）

```bash
cd frontend/ios
flutter test
flutter analyze            # 静态分析
```

---

## 6. Google OAuth 登录（W48）

前端 `Login.vue` / `Register.vue` 在 `VITE_GOOGLE_CLIENT_ID` 非空时,通过 Google Identity Services 渲染 "Continue with Google" 按钮。点击后浏览器拿到 Google `id_token`,POST 到 `POST /api/v2/auth/google`,后端用 `GOOGLE_CLIENT_ID` 验签、签发 JWT pair,并自动注册或关联已有账号(按 `google_sub` / `email` 匹配)。

### 6.1 本地开发 — 不配也能跑

`VITE_GOOGLE_CLIENT_ID` 留空时 `/login` / `/register` 不渲染 Google 按钮,只走邮箱/用户名 + 密码登录(默认行为)。后端 `GOOGLE_CLIENT_ID` 留空时 `/api/v2/auth/google` 返回 500(预期)。

### 6.2 启用 Google 登录(3 步)

1. **创建 OAuth Client**
   - 打开 https://console.cloud.google.com/apis/credentials
   - **Create Credentials → OAuth 2.0 Client IDs → Web application**
   - **Authorized JavaScript origins** 加:
     - `http://localhost:5173`(开发)
     - `https://visa.example.com`(生产,按你真实域名改)
   - 拿到形如 `1234…xyz.apps.googleusercontent.com` 的 client id

2. **写进两个 env**
   ```bash
   # backend/.env
   GOOGLE_CLIENT_ID=1234…xyz.apps.googleusercontent.com

   # frontend/web/.env
   VITE_GOOGLE_CLIENT_ID=1234…xyz.apps.googleusercontent.com
   ```

3. **重启两个服务**(`vite` 启动时读 env,改完必须重启)

刷新 `http://localhost:5173/login`,密码框下方会出现"或"分隔线和 Google 登录按钮。

### 6.3 测试覆盖

| 层级 | 文件 | 覆盖 |
|---|---|---|
| 后端 service | `backend/tests/test_auth_google.py` | 10 cases — happy / returning / email-link / invalid token / wrong audience / not-configured / disabled / no-email / session 落库 / audit log |
| 前端 api | `frontend/web/src/__tests__/api/auth.test.ts` | 4 cases — mock 模式 / 真模式 envelope 解码 / 错误抛出 |
| 前端 UI | `frontend/web/src/__tests__/Login.google.test.ts` | 2 cases — client_id 留空不渲染 / 设值后渲染 + callback 链路 |
| 端到端 | `frontend/web/tests/e2e/google-login.spec.js` | 2 cases — GIS mock + 后端 mock,验证 token 写入 + 跳 `/destinations` |

### 6.4 已知限制

- 不支持同账号从不同 Google 账号绑定切换(目前以首次绑定的 `google_sub` 为准)
- 暂未做撤销流程 — `UserSession.refresh_token_hash` 可以吊销,但 id_token 本身的有效期由 Google 控制(默认 1h)
- 越南/印尼网络偶尔打不通 `accounts.google.com` 时按钮会卡在加载态,后续可加 fallback 提示

---

## 文档索引

| 文档 | 用途 |
|---|---|
| [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md) | **产品范围**（越/印尼客户 × 美/申根/英/澳签证；RPA/保险/小程序开关） |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 系统架构（顶层组件图 / 数据流 / 横切关注点） |
| [`docs/API.md`](docs/API.md) | REST + WebSocket API 参考（942 行） |
| [`docs/LEGAL_REVIEW_NOTES.md`](docs/LEGAL_REVIEW_NOTES.md) | 法务 review 18 项 checklist |
| [`docs/stripe-credentials-setup.md`](docs/stripe-credentials-setup.md) | Stripe 凭据切换（mock → live） |
| [`docs/adr/0001-fastapi-not-django.md`](docs/adr/0001-fastapi-not-django.md) | ADR：为什么选 FastAPI 而非 Django |
| [`docs/adr/0002-vue3-elementplus.md`](docs/adr/0002-vue3-elementplus.md) | ADR：Vue 3 + Element Plus 选型 |
| [`docs/adr/0003-mock-payment-v2.md`](docs/adr/0003-mock-payment-v2.md) | ADR：V2 Mock 支付策略 |
| [`docs/adr/0004-i18n-4-languages.md`](docs/adr/0004-i18n-4-languages.md) | ADR：4 语种国际化架构 |
| [`docs/adr/0005-bizexception-error-code.md`](docs/adr/0005-bizexception-error-code.md) | ADR：业务异常 + 错误码体系 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更日志（Keep a Changelog） |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献指南（分支 / PR / 编码规范） |
| [`FAQ.md`](FAQ.md) | 常见问题 |
| [`TESTING.md`](TESTING.md) | 测试约定 + 命令 |
| [`RUNBOOK.md`](RUNBOOK.md) | 运维 runbook（部署 / 备份 / 故障排查） |
| [`SECURITY.md`](SECURITY.md) | 安全策略 + 漏洞披露流程 |
| [`PERFORMANCE.md`](PERFORMANCE.md) | 性能基线 + 优化记录 |
| [`MVP-LAUNCH-CHECKLIST.md`](MVP-LAUNCH-CHECKLIST.md) | MVP 验收清单（A~F 共 23 项） |
| [`pm/board/W14_gate_report.md`](pm/board/W14_gate_report.md) | W14 sprint gate 报告 |
| [`pm/board/W15_roadmap.md`](pm/board/W15_roadmap.md) | W15 sprint 路线图 |
| [`pm/risks/risks.md`](pm/risks/risks.md) | 风险登记 |
| [`pm/wbs/wbs.md`](pm/wbs/wbs.md) | WBS 任务树 |

---

## MVP 状态

当前状态：**W68–W74 代码已提交 · 法务 v1.1-gdpr-draft 待律师签字 · 负责人待办四项进行中**。

**负责人当前必办**（外部凭据/基础设施，代码无法代劳）→ [`docs/PRE_LAUNCH_OWNER_TODO.md`](docs/PRE_LAUNCH_OWNER_TODO.md)：

| 事项 | 状态 |
|------|------|
| Stripe 凭据 + webhook | ⏳ 待配置 |
| Google OAuth Client ID | ⏳ 待配置 |
| 生产域名 + HTTPS | ⏳ 待定 |
| 企业邮箱 + 事务邮件 SMTP | ⏳ 待配置 |

- ✅ 核心闭环（注册 → 申请 → OCR → 支付 mock → 状态查询）全部跑通
- ✅ 4 语种 i18n baseline 落地（zh-CN / en / id / vi）
- ✅ 后端 **122 PASS**（W14-1 + W14-9 baseline），W15 P0 性能 + 观测性基线已建立
- 🟠 Stripe live 切换 — 阻塞：用户凭据（待提供 `sk_live_xxx`）
- 🟠 iOS / Android 真机发布 — 阻塞：Apple / Google 开发者账号
- 🟠 法务 review sign-off — `docs/LEGAL_REVIEW_NOTES.md` 18 项 checklist，deadline **2026-06-25**
- 🟡 Vite build 缓存 CI 验证 — macOS M-series `vite build` hang，本机走 Playwright fallback；W16 走 GitHub Actions Linux runner 实跑
- 🟡 `tests/conftest.py` fixture 顺序 + `.venv-test` 缺 paddleocr/cv2 — 39 个 RPA/OCR test 失败，W16 P0 必修

完整验收清单（23 项）见 [`MVP-LAUNCH-CHECKLIST.md`](MVP-LAUNCH-CHECKLIST.md)。
当前状态统计：A~F 6 大块 23 项，全部 ⏳ 待验证（W15 收口后逐步勾选）。

**W17+ 路线图（`3.0.0` semver-major）**：

- API v3 introduction（v2 标记 deprecated，并行 6 个月）
- Vue 3.5+ / Element Plus 3.x 升级
- FastAPI 0.110+ + Pydantic v2 强制
- WebSocket realtime push 扩 chat / 客服
- OAuth 2.1 + PKCE（微信 / Apple / Google 登录）
- GDPR / CCPA 合规

详见 [`CHANGELOG.md`](CHANGELOG.md) §3.0.0。

---

## 贡献

欢迎贡献代码 / 文档 / 测试 / bug 反馈。提交前请阅读：

- **[`CONTRIBUTING.md`](CONTRIBUTING.md)** — 分支策略（Git Flow 变体）/ PR 流程 / 编码规范 / commit 格式
- **[`SECURITY.md`](SECURITY.md)** — 漏洞披露流程（**请勿**在公开 Issue 提交安全问题）
- **[`TESTING.md`](TESTING.md)** — 测试分层与覆盖率要求
- **[`docs/adr/`](docs/adr/)** — 重大架构决策的 ADR；新决策请新加 ADR

**快速开始**：

```bash
# 1. fork & clone
git clone <your-fork-url>
cd 签证项目

# 2. 创建 feature 分支（命名：feature/<short-desc> 或 fix/<short-desc>）
git checkout -b feature/my-change

# 3. 提交前跑测试 + lint
cd backend && .venv/bin/pytest
cd ../frontend/web && npm run test && npm run lint

# 4. 推送到 fork + 创建 PR
git push origin feature/my-change
```

---

## 许可证

本项目许可证待定（TBD — 内部 MVP 阶段未发布对外协议）。

内部使用规范：

- 不得将本仓库代码用于商业目的（待最终协议确认）
- 内部 fork 需保留版权声明
- 第三方依赖遵守各自 LICENSE（详见 `requirements.txt` / `package.json` / `pubspec.yaml`）

---

## 截图（占位，待补）

> 待 W16 跑通真实截图后回填：Home / OrderNew / PaymentResult / AdminLogin / AdminDashboard / RateLimit 等关键页面。

<!-- TODO: 替换为真实截图
![Home](docs/screenshots/home.png)
![PaymentResult](docs/screenshots/payment_result.png)
![AdminDashboard](docs/screenshots/admin_dashboard.png)
-->

| 页面 | 截图 | 状态 |
|---|---|---|
| Home | _占位_ | ⏳ 待 W16 补充 |
| OrderNew | _占位_ | ⏳ 待 W16 补充 |
| PaymentResult | _占位_ | ⏳ 待 W16 补充 |
| AdminLogin | _占位_ | ⏳ 待 W16 补充 |
| AdminDashboard | _占位_ | ⏳ 待 W16 补充 |
| RateLimit | _占位_ | ⏳ 待 W16 补充 |

---

## 徽章（占位）

> 待 CI 接入后替换为真实 badge URL：

- **Build**: `![Build](https://img.shields.io/badge/build-WIP-lightgrey.svg)` — 当前 W15 收口；W16 接 GitHub Actions
- **Tests**: `![Tests](https://img.shields.io/badge/tests-122%20passed-blue.svg)` — 122 PASS baseline（W14-1 + W14-9）
- **Coverage**: `![Coverage](https://img.shields.io/badge/coverage-TBD-yellow.svg)` — 覆盖率待补真实数据（建议 W16 跑 `--cov-report=xml` 接 Codecov）

---

<p align="center">
  <sub>Built with ❤️ by the Htex team · Last updated 2026-06-15 (W15 P0 收口)</sub>
</p>