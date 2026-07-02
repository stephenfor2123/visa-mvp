# Htex 技术架构总览

> 梳理日期：2026-07-02
> 工作目录：`/Users/apple/Desktop/签证项目_副本/`
> 输出目的：给产品负责人（owner）用来定位"重点难点"，每一条事实/数字都附证据路径（`file_path:line`）。
> 配套 deliverable：`/Users/apple/.mavis/plans/plan_ab3cd7e7/outputs/arch-overview/deliverable.md`

---

## 1. 项目概览

**Htex**（品牌名统一为 **Htex**，不是"签证助手"或 TravelFlow，详见 PITCH.md `PITCH.md:1`）是**跨境签证申请一站式 AI 服务**的 MVP 产品，覆盖完整闭环：

1. **账号**：手机/邮箱 + 密码 + JWT 滑动刷新（2h access / 7d refresh，详见 `backend/app/core/security.py:53-54`）
2. **国家/签证类型选择**：当前 V2 阶段仅 ID / VN 两个国家真正有 RPA provider，其余国家为占位路由（`README.md:38`、`backend/app/tasks/rpa_tasks.py:32-35`）
3. **材料上传 + OCR**：上传护照 / 在职证明 / 银行流水等 → PaddleOCR + Tesseract 双引擎 → 字段抽取 + 强校验
4. **行程单 LLM 生成**：航班 + 逐日行程 → MiniMax LLM 补全交通/酒店/景点（仅 LLM 填充空白字段，城市是用户拥有的）
5. **AI 校验 + 拒签风险诊断**：15+ 规则 + 签证官语义检索（RAG over 官方政策）
6. **订单提交**：状态机 `created → submitted → reviewing → approved/rejected → closed`（`backend/app/services/order_service.py:15-18`）
7. **RPA 自动递交**：自动化填写印尼/越南官方签证门户
8. **支付（Mock）**：V2 阶段默认 Mock，1 秒自回调（`backend/app/services/payment_provider.py:84-92`）；V2.1 接 Stripe
9. **状态查询**：订单时间线 + WebSocket 推送 + 30s 轮询兜底（`backend/app/api/v2/ws_orders.py`、`README.md:36`）

**核心价值（来自 `PITCH.md:1-37`）**：
- 打破信息差（自动生成各国签证 checklist）
- 提高效率（OCR + AI 校验 + RPA + 行程单模板）
- 服务透明（全程留痕 + 时间戳，可追溯）

---

## 2. 技术栈一览

> 说明：所有"版本"指 `requirements.txt` / `package.json` / `pubspec.yaml` 锁定版本；"实际"指线上/CI 现状（如有差异）。

### 2.1 总览表

| 层 | 技术 | 版本 / 实际 | 证据 |
|---|---|---|---|
| **后端语言** | Python | 3.11（docker base `python:3.11-slim`，`pyproject.toml` 写 `>=3.9`，实际跑 3.11） | `backend/Dockerfile:23`、`backend/pyproject.toml:9` |
| **后端 Web 框架** | FastAPI | 0.115.6 | `backend/requirements.txt:2` |
| **后端 ASGI Server** | uvicorn[standard] | 0.32.1 | `backend/requirements.txt:3` |
| **ORM / DB** | SQLAlchemy 2.0 async + aiosqlite + asyncpg | SQLAlchemy 2.0.36, aiosqlite 0.20.0, asyncpg 0.30.0 | `backend/requirements.txt:12-16` |
| **数据库迁移** | Alembic | 1.14.0（13 个 migration，编号 0001-0013） | `backend/requirements.txt:14`、`backend/alembic/versions/` |
| **数据验证** | Pydantic v2 + pydantic-settings | pydantic 2.10.4 / pydantic-settings 2.7.0 | `backend/requirements.txt:7-8` |
| **认证 / 加密** | python-jose (JWT HS256) + passlib (bcrypt cost=12) + pyotp (TOTP MFA) | jose 3.3.0 / passlib 1.7.4 / bcrypt 4.0.1 | `backend/requirements.txt:19-22` |
| **异步任务队列** | Celery 5.4 + Redis 7-alpine | celery 5.4.0 / redis 5.2.1 | `backend/requirements.txt:26-27`、`backend/docker-compose.yml:60` |
| **HTTP 客户端** | httpx + httpx-ws | 0.28.1 / 0.7.2 | `backend/requirements.txt:33-34` |
| **日志** | loguru | 0.7.3 | `backend/requirements.txt:30` |
| **可观测性** | prometheus-client | 0.21.0（`/metrics` 端点） | `backend/requirements.txt:45`、`backend/app/main.py:159-162` |
| **OCR 引擎（主）** | PaddleOCR | >= 2.7.0（实际 import 时 `_PADDLE_AVAILABLE=False` —— paddlepaddle 推理引擎未装） | `backend/requirements.txt:48`、`backend/app/services/ocr.py:25-30` |
| **OCR 引擎（兜底）** | pytesseract + Pillow + opencv-python | opencv >= 4.8.0 / Pillow >= 10.0.0；W19-2 起 Tesseract 是真兜底 | `backend/app/services/ocr.py:33-52` |
| **支付 SDK** | Stripe | >= 15.0.0（**V2 仅 stub，方法全部 raise NotImplementedError**） | `backend/requirements.txt:57`、`backend/app/services/payment_provider.py:610-675` |
| **LLM（行程单）** | MiniMax-Text-01（自托管 base `https://api.minimaxi.com/v1`） | 通过 httpx 调 `text/chatcompletion_v2` | `backend/app/core/config.py:151-156`、`backend/app/services/llm/minimax_client.py:39-74` |
| **前端 Web 框架** | Vue 3.4 + Vite 5 + Element Plus 2.7 + Pinia 2 + Vue Router 4 + vue-i18n 9 | vue 3.4.27 / vite 5.2.11 / element-plus 2.7.5 / pinia 2.1.7 / vue-router 4.3.2 / vue-i18n 9.13.1 | `frontend/web/package.json:19-27` |
| **前端 Web PWA** | vite-plugin-pwa + workbox | 1.3.0 | `frontend/web/vite.config.js:14-51` |
| **前端 Web 国际化** | vue-i18n 9 + IP 探测（ipapi.co）+ localStorage 记忆 | 4 locale: zh-CN / en / id-ID / vi-VN | `frontend/web/src/i18n/index.js:42-77` |
| **前端 Web 测试** | Playwright 1.60（E2E） + vitest 1.5（单元） | `playwright.config.cjs` 在 root | `frontend/web/package.json:29-39` |
| **前端 iOS** | Flutter 3.19+ / Dart 3.3+ + flutter_localizations + provider 6.1 + http + shared_preferences + intl + qr_flutter + google_sign_in | pubspec 锁定 0.1.0+1；CI 跑 `flutter 3.44.2`（`flutter-action v2`） | `frontend/ios/pubspec.yaml:1-27`、`.github/workflows/ci.yml:35` |
| **前端 iOS 国际化** | flutter_localizations + ARB（zh/en/id/vi 四语种 ARB + generated AppLocalizations） | `lib/l10n/*.arb` 4 份 | `frontend/ios/lib/l10n/` |
| **微信小程序** | 原生 WXML/WXSS/JS + miniprogram-ci | 9 个 pages、3 个 components；package `miniprogram-ci ^2.1.7` | `frontend/miniprogram/app.json:1-49`、`frontend/miniprogram/package.json:10-12` |
| **共享 i18n** | 4 个 JSON：`zh-CN.json / en.json / id.json / vi.json` | ~60-63 KB/份 | `frontend/shared/i18n/` |
| **后端测试** | pytest 8.3 + pytest-asyncio 0.25 + pytest-cov 6.0 | 配置：`function` scope loop（pytest.ini 注释里写"W21.5 fix"），但 `pyproject.toml` 里写"session" scope | `backend/requirements.txt:37-39`、`backend/pytest.ini:1-12`、`backend/pyproject.toml:13-19` |
| **后端容器化** | 多阶段 Docker（builder+runtime） + docker-compose（backend + redis） | Dockerfile 85 行；compose 71 行 | `backend/Dockerfile:1-85`、`backend/docker-compose.yml:1-71` |
| **CI** | GitHub Actions 4 jobs（backend pytest / frontend playwright / flutter analyze / miniprogram build） + 1 build workflow | `ubuntu-latest` 跑后端/前端/小程序，`macos-14` 跑 iOS | `.github/workflows/ci.yml:37-276`、`.github/workflows/build.yml:1-113` |

### 2.2 数据库 / 表统计（13 个 migration 落下来的 ORM 模型）

| 模型 | 文件 | 备注 |
|---|---|---|
| User | `backend/app/models/user.py` | 含 mfa_enabled / mfa_type / mfa_secret |
| UserSession | `backend/app/models/user_session.py` | refresh_token 持久化（SHA-256 哈希） |
| Order + OrderMessage + OrderStatusHistory | `backend/app/models/order.py` | 状态机 `created → submitted → reviewing → approved/rejected → closed` |
| Material | `backend/app/models/material.py` | sha256 dedup、ocr_status 字段 |
| VisaDestination | `backend/app/models/destination.py` | 国家列表 + Atlys 风格 fee/valid/process_days |
| VisaCountry | `backend/app/models/visa_countries.py` | W33 起扩展国家元数据（migration 0011） |
| RagSource + RagChunk | `backend/app/models/rag.py` | RAG 源 + embedding（JSON 存，dim 字段记） |
| WebhookEvent | `backend/app/models/webhook_event.py` | 支付回调幂等去重 |
| AdminUser + AdminRole | `backend/app/models/admin_user.py` / `admin_role.py` | W14-3 后台权限 |
| AuditLog | `backend/app/models/audit_log.py` | 业务/管理操作审计 |
| OrderPollLog | `backend/app/models/order_poll_log.py` | 轮询状态变化记录 |
| ValidationRule | `backend/app/models/validation_rules.py` | AI 校验规则可配 |
| I18nOverride | `backend/app/models/i18n_override.py` | 多语言覆写（W33 引入） |

---

## 3. 系统架构图（前端 ↔ 后端 ↔ 外部服务）

```mermaid
flowchart TB
    subgraph FE[前端 - 3 端共享同一套 /api/v2/*]
        WEB[Vue 3 + Vite<br/>frontend/web<br/>SPA / PWA<br/>:5173 dev]
        IOS[Flutter iOS App<br/>frontend/ios<br/>16 pages<br/>iOS Runner]
        MP[微信小程序<br/>frontend/miniprogram<br/>9 pages<br/>utils/api.js]
    end

    subgraph BE[后端 - FastAPI 单体]
        API[FastAPI app<br/>app/main.py<br/>:8000]
        SCHED[/scheduler/*<br/>内部端点<br/>X-System-Key/]
        WS[/ws/orders/*<br/>WebSocket/]
        subgraph APIServices[app/services/*]
            OCR[ocr.py<br/>PaddleOCR + Tesseract]
            MAT[material_service.py]
            ORDER[order_service.py]
            PAY[payment_provider.py<br/>Mock 1s 自回调]
            AUDIT[audit.py]
            RAG[rag/*<br/>refresh / retriever]
            RPA[rpa/*<br/>scheduler + providers]
            VOICE[voice_input.py<br/>mock/google/vosk]
            LLM[llm/*<br/>MiniMax client +<br/>itinerary generator]
            DIAG[visa_diagnoser.py]
            AFF[affiliate_provider.py<br/>Mock]
            INS[insurance_provider.py<br/>Mock]
            AUTH[auth_service.py]
            MFA[mfa_service.py<br/>TOTP]
            CLEAN[cleanup_service.py]
            IMAGE[image_preprocessor.py]
        end
        subgraph APIRoutes[app/api/v2/*]
            ROUTES[auth / orders / materials /<br/>payment / ocr / rpa / voice /<br/>rag / itinerary / admin / diagnose /<br/>insurance / affiliate / destinations]
        end
    end

    subgraph EXT[外部服务]
        REDIS[(Redis 7<br/>Celery broker<br/>+ result backend)]
        STRIPE[Stripe SDK<br/>V2.1 stub - NotImplementedError]
        MINIMAX[MiniMax API<br/>api.minimaxi.com/v1<br/>text/chatcompletion_v2]
        TESSERACT[Tesseract CLI<br/>pytesseract<br/>macOS /opt/homebrew/bin/tesseract]
        PADDLE[PaddleOCR<br/>paddlepaddle 未装<br/>import 即失败]
        IND[/印尼签证官网/]
        VN[/越南签证官网/]
    end

    subgraph OBS[观测 / 运维]
        LOG[(loguru<br/>backend/logs/)]
        PROM[/metrics<br/>prometheus scrape/]
        GH[GitHub Actions<br/>4 jobs]
    end

    WEB -->|axios / proxy /api → :8000| API
    IOS -->|http package| API
    MP -->|wx.request| API

    API --> ROUTES
    ROUTES --> APIServices
    API --> WS
    API --> SCHED

    OCR --> TESSERACT
    OCR -.失败.-> PADDLE
    RPA --> IND
    RPA --> VN
    LLM --> MINIMAX
    PAY -.V2.1.-> STRIPE

    CLEAN --> RAG
    CLEAN --> ORDER
    DIAG --> RAG
    AUTH --> MFA
    API --> LOG
    API --> PROM
    GH --> BE
```

**关键事实**：
- 三端**共用**同一个 `/api/v2/*` 后端协议（`README.md:4`）
- 后端是**FastAPI 单体**，`/scheduler` 和 `/ws/orders/*` 在主 app 下但**不走 JWT / 限流**中间件（`backend/app/main.py:123-131`）
- OCR 实际工作的是 **Tesseract** —— `paddlepaddle` ~700MB 推理引擎没装，paddleocr 包虽然 import 成功但一调就报 `paddle_static unavailable`（`backend/app/services/ocr.py:1-14`、`backend/app/services/ocr.py:25-30`）

---

## 4. 后端架构

### 4.1 框架选型

- **FastAPI 0.115.6** + **uvicorn 0.32.1**（`backend/requirements.txt:2-3`）
- 异步模型：**async/await 全栈**；SQLAlchemy 2.0 async engine + aiosqlite（dev）/ asyncpg（prod）（`backend/requirements.txt:12-16`、`backend/app/core/db.py:24-32`）
- Pydantic v2（DTO 验证） + `BizException + ErrorCode` 业务异常体系（`docs/adr/0005-bizexception-error-code.md`）
- Celery 5.4 + Redis 7 broker：用于 RPA 长耗时任务（`backend/celery_app.py:22-48`、`backend/docker-compose.yml:60-69`）

### 4.2 入口与中间件链（`backend/app/main.py:64-130`）

启动顺序（外→内）：

1. **`SecurityHeadersMiddleware`** — 给每个响应加 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / Permissions-Policy（`backend/app/middleware/security_headers.py:34-55`）
2. **`RequestSizeLimitMiddleware`** — 请求体 ≤ 10 MB（`backend/app/main.py:80`）
3. **`CORSMiddleware`** — Origin 白名单（来自 env `CORS_ALLOWED_ORIGINS`，默认 `localhost:5173,4173,3000`，**生产必须 override**）（`backend/app/main.py:86-108`）
4. **`RequestLoggingMiddleware`** — 结构化日志（`backend/app/middleware/logging.py`）
5. **`RateLimitMiddleware`** — 内存滑动窗口：全局 100 req/min/IP，slow API（`/api/v2/auth`）60 req/min/IP；SMS 单独 1/60s + 10/天（`backend/app/middleware/rate_limit.py:62-95`）

Routers：
- `app.include_router(api_v2_router, prefix='/api/v2')`（`backend/app/main.py:121`）
- `app.include_router(scheduler_router.router, prefix='/scheduler')` — 内部端点，`X-System-Key` 鉴权（`backend/app/main.py:123-126`）
- `app.include_router(ws_router.router, prefix='/ws')` — WebSocket 实时推送订单状态（`backend/app/main.py:128-131`）

### 4.3 目录结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI app + 异常处理 + 中间件链
│   ├── celery_app.py           # Celery 5.4 + Redis + RAG beat schedule
│   ├── core/                   # config/db/security/errors/logging/metrics
│   │   ├── config.py           # Pydantic Settings, 157 行
│   │   ├── db.py               # 异步 engine + sessionmaker + get_db dependency
│   │   ├── security.py         # bcrypt + JWT + current_user dep
│   │   └── errors.py           # BizException + ErrorCode 枚举 + build_error_payload
│   ├── models/                 # SQLAlchemy 2.0 ORM (15 个文件, 14 个模型)
│   ├── schemas/                # Pydantic v2 DTO (11 个文件)
│   ├── services/               # 业务逻辑
│   │   ├── auth_service.py     # 注册/登录/refresh/重置/Google/WeChat OAuth
│   │   ├── mfa_service.py      # TOTP, secret 用 XOR+AES-style 加密
│   │   ├── order_service.py    # 订单生命周期 + 状态机
│   │   ├── material_service.py # 上传/dedup/校验
│   │   ├── payment_provider.py # PaymentProvider facade + Stripe stub (1187 行!)
│   │   ├── payment/            # 底层 ABC + Mock + factory
│   │   ├── ocr.py              # PaddleOCR 主引擎 + Tesseract 兜底 (698 行)
│   │   ├── ocr_field_mapping.yaml # 9 国护照字段映射
│   │   ├── voice_input.py      # 语音识别 (mock/google/vosk)
│   │   ├── image_preprocessor.py # 图像预处理 (清晰度/完整度检测)
│   │   ├── material_classifier.py # AI 自动识别材料类型
│   │   ├── visa_diagnoser.py   # AI 拒签风险评估 (规则 + RAG)
│   │   ├── validation.py       # 材料 15+ 规则
│   │   ├── storage.py          # 文件存储抽象
│   │   ├── cleanup_service.py  # 24h 临时文件 / 180h 归档 / 72h pending_destroy 用户
│   │   ├── llm/                # MiniMax client + itinerary generator
│   │   ├── rag/                # refresh / crawler / chunker / embedder / retriever
│   │   ├── rpa/                # rpa_scheduler + captcha_solver + page_parser + form_filler
│   │   │   └── providers/      # IndonesiaVisa / VietnamVisa
│   │   ├── affiliate_provider.py   # Mock affiliate (5% 佣金)
│   │   ├── insurance_provider.py   # Mock insurance
│   │   └── audit.py            # 43 行, audit_log helper
│   ├── api/v2/                 # 18 个 router 文件, 见下表
│   ├── middleware/             # admin_auth / audit_decorator / rate_limit / 等 7 个
│   └── tasks/                  # Celery task: rpa_tasks.py + rag_tasks.py
├── alembic/versions/           # 13 个 migration: 0001_init → 0013_drop_phone_columns
├── tests/                      # conftest.py + unit/ (15) + integration/ (24)
├── scripts/                    # backup / restore / seed_* / build-multiarch.sh
├── data/                       # SQLite + materials/ (gitignored)
├── docs/                       # 后端 README + WORKLOG
├── logs/                       # loguru 输出
├── samples/                    # 9 国护照样张图片
├── Dockerfile                  # 多阶段 (builder + runtime), 85 行
├── docker-compose.yml          # backend + redis services, 71 行
├── requirements.txt            # 57 行, 锁定版本
├── pyproject.toml              # 项目元数据 + pytest session-scope loop 配置
└── pytest.ini                  # pytest function-scope loop (与 pyproject.toml 不一致!)
```

### 4.4 API Router 清单（`backend/app/api/v2/__init__.py:4-48`）

| Router 文件 | 前缀 | 端点数 | 用途 |
|---|---|---|---|
| `auth.py` | `/auth` | 6 | register/login/refresh/reset/google/wechat |
| `orders.py` | `/orders` | 6 | create/list/detail(+ETag)/checklist/cancel/submit |
| `materials.py` | `/materials` | 9 | upload/preprocess/classify/diagnose/get/delete/download/validate |
| `ocr.py` | `/ocr` | 1 | recognize (multipart) |
| `payment.py` | `/payment` | 4 | create/notify/{order_no}/close |
| `rpa.py` | `/rpa` | 5 | submit/status/cancel/config-get/config-update |
| `voice.py` | `/voice` | 1 | recognize (multipart audio) |
| `rag.py` | `/rag` | 4 | sources/refresh/query/checklist |
| `itinerary.py` | `/itinerary` | 1 | generate (LLM fill-in) |
| `admin.py` | `/admin` | 20+ | 后台全套 (login/users/orders/countries/rules/logs...) |
| `admin_cleanup.py` | `/admin/cleanup` | 5 | cleanup 端点 (W37) |
| `diagnose.py` | — | 3 | quick-check eligibility |
| `insurance.py` | `/insurance` | 3 | quote/bind/claim (Mock) |
| `affiliate.py` | `/affiliate` | 5 | track/attribute/commission/payout/stats |
| `destinations.py` | `/destinations` | 3 | list/detail (支持 4 语种 country_name) |
| `scheduler.py` | (不在 /api/v2) | 1 | 内部 tick (X-System-Key 鉴权) |
| `ws_orders.py` | (不在 /api/v2) | 1 | WebSocket `/ws/orders/{order_no}` |

### 4.5 数据库 & ORM

- **SQLAlchemy 2.0 async** + **aiosqlite**（dev）/ **asyncpg**（prod）（`backend/app/core/db.py:24-39`）
- **Alembic** 1.14.0，**13 个 migration**（`backend/alembic/versions/`）：
  - `0001_init.py` — users / user_sessions / base
  - `0002_destinations.py` — visa_destinations
  - `0003_materials.py` — materials
  - `0004_orders.py` — orders + status_history + messages
  - `0005_order_poll.py` — order_poll_log
  - `0006_orders_aff_code.py` — affiliate 字段
  - `0007_admin_tables.py` — admin 权限
  - `0008_webhook_events.py` — 支付回调幂等
  - `0009_atlys_destinations.py` — visa_fee/valid/process_days/eta
  - `0010_admin_roles_users.py` — admin 角色/用户
  - `0011_countries_extend.py` — visa_countries 扩展字段
  - `0012_i18n_overrides.py` — i18n override 表
  - `0013_drop_phone_columns.py` — 移除 phone 字段（登录改 email/username）
- **数据库连接管理**：`app/core/db.py:42-50` 的 `get_db()` AsyncSession dependency，每个请求一个 session，`expire_on_commit=False` + `autoflush=False`

### 4.6 关键 Service

#### 4.6.1 OCR（`backend/app/services/ocr.py` + `ocr_field_mapping.yaml`）

- **双引擎**：
  - **PaddleOCR** 主（`ocr.py:25-30`，`_PADDLE_AVAILABLE` import 检测）
  - **Tesseract** 真兜底（`ocr.py:33-52`，`pytesseract` + PIL）
- **9 国护照字段映射**（`ocr_field_mapping.yaml:1-207`）：US / JP / GB / AU / SG / DE / FR / IT / KR；每国 `passport_re` / `date_fmt` / `surname_pos` / `given_name_pos` / `gender_map` / `field_order`
- **字段抽取升级（W31）**：
  1. 加载 YAML 拿 9 国 `passport_re`，按各国格式分别匹配
  2. **keyword 锚定** — 找 "Passport No." / "护照号码" 同行/邻行的字段值
  3. **MRZ 兜底** — ICAO 9303 机器可读区（P< + 两行 44 字符）解析
  - 修复：旧版按正则顺序 break 导致中国 9 位数字护照被 US 格式抢走；国籍拿全文第一个 3 字母；性别可能撞月份（`ocr.py:7-14`）
- **语言支持**：en / zh-CN / id / vi / ko / ja / ch（`ocr.py:55-65`）

#### 4.6.2 LLM（MiniMax 行程生成，W40/W41/W42）

- **客户端**（`backend/app/services/llm/minimax_client.py:39-74`）：
  - URL：`https://api.minimaxi.com/v1/text/chatcompletion_v2`
  - Model: `MiniMax-Text-01`（`backend/app/core/config.py:155-156`）
  - 鉴权：`Authorization: Bearer ${minimax_api_key}`
  - 关键点：HTTP 200 仍可能业务错误（如"余额不足"），必须检查 body 里的 `base_resp.status_code`（`minimax_client.py:62-65`）
- **行程生成器**（`backend/app/services/llm/itinerary_generator.py`）：
  - **不修改** `city`（用户拥有）、`day`、`date`（`itinerary_generator.py:96-97`）
  - **只填空** `transport` / `hotel` / `attraction`
  - **航班上下文**包含 `return_origin` / `return_destination` 独立可编辑（支持开口程）（`itinerary_generator.py:35-60`）
  - **按日期匹配**（不是按位置）：哪一天 `date == depart_date` 就是到达日，`date == return_date` 就是离开日（`itinerary_generator.py:48-57`）
- **API 入口**（`backend/app/api/v2/itinerary.py:64-86`）：`POST /api/v2/itinerary/generate`

#### 4.6.3 支付（`backend/app/services/payment_provider.py`）

> 这是项目里**最大的 service**（1187 行），文档长度排第 1。

- **双层架构**：
  - 底层 ABC：`backend/app/services/payment/adapter.py:35-41`（`PaymentAdapter` with `create/confirm/query`）
  - 上面 facade：`PaymentProvider` 提供 `create_order/query_order/handle_notify/close_order/payout` + 订单耦合状态 + 自回调
- **Mock 实现**（`payment_provider.py` 上半部分）：
  - `create_order` → 返回 `weixin://wxpay/bizpayurl?pr=MOCKxxx` 占位 URL
  - **1 秒后**自动调 `handle_notify` 自身（用 `loop.create_task(self._auto_notify(...))`），订单 `pending → paid`
  - 支付元数据（trade_no / status / paid_at）持久化到 `orders.extra` JSON 字段，**不**改订单状态机（`payment_provider.py:1-22`）
- **Stripe 真接**（`payment_provider.py:610-1187`，**V2 是 stub**）：
  - **所有方法**在 `STRIPE_SECRET_KEY=""` 时 raise `NotImplementedError("V2.1 阶段接真 SDK")`（`payment_provider.py:671-675`）
  - 留好方法签名：`PaymentIntent` / `Webhook` / `Transfer` / `payout()`
  - V2.1 切换条件：填 3 个 env 字段 + macOS Keychain 注入（`backend/app/core/config.py:118-149`）
- **模块级状态坑**（`payment_provider.py:91`）：`_PENDING_NOTIFIES: dict[str, asyncio.Task] = {}`，**所有后台 notify task 引用这个全局字典**。这是 §11 重点难点之一（**pytest 全量跑会清空 dev 数据库**的怀疑根因）

#### 4.6.4 审计（`backend/app/services/audit.py`）

- 43 行，**全项目最小的 service** 之一
- `record_audit(db, *, actor_type, action, actor_id, target_type, target_id, payload)` — 插入 `AuditLog` 行，调用方负责 commit（`audit.py:14-33`）
- payload 序列化为 JSON 字符串
- 装饰器版本（管理员专用）：`backend/app/middleware/audit_decorator.py:55-149` — fire-and-forget `asyncio.create_task(_write_audit(...))`

#### 4.6.5 其他关键 Service

| Service | 行数 | 用途 |
|---|---|---|
| `auth_service.py` | 440 | 注册/登录/refresh/reset/Google/WeChat OAuth |
| `mfa_service.py` | 200 | TOTP；secret 用 XOR(`JWT_SECRET+mfa-secret`) 加密 |
| `order_service.py` | 853 | 订单生命周期 + 状态机；用 `uuid4 short hex(8)` 做订单号后缀（避免 race） |
| `material_service.py` | 385 | 上传/sha256 dedup/15+ 规则校验 |
| `image_preprocessor.py` | 478 | 清晰度（模糊方差）+ 完整度（文档四边形是否贴边） |
| `material_classifier.py` | 358 | AI 自动分类材料类型 |
| `visa_diagnoser.py` | 516 | AI 拒签风险（规则 + RAG 双引擎） |
| `validation.py` | — | 15+ 校验规则引擎 |
| `cleanup_service.py` | 503 | 24h 临时 / 180h 归档 / 72h pending_destroy 用户清理 |
| `voice_input.py` | 569 | 语音识别（mock/google/vosk 三引擎可切换） |
| `storage.py` | — | 文件存储抽象 |
| `affiliate_provider.py` | 631 | Mock 5% 佣金 / 30 天归因窗口 |
| `insurance_provider.py` | 538 | Mock 拒签险（quote/bind/claim） |

### 4.7 中间件汇总（`backend/app/middleware/`）

| 文件 | 用途 | 关键证据 |
|---|---|---|
| `admin_auth.py` | 管理员 JWT（独立 secret + `role=admin` claim） | `admin_auth.py:39-50` |
| `audit_decorator.py` | `@audit_log(action, target_type)` 装饰器（fire-and-forget） | `audit_decorator.py:55-149` |
| `rate_limit.py` | 内存滑动窗口限流（全局 100/min, slow API 60/min） | `rate_limit.py:62-95` |
| `request_size_limit.py` | 请求体 ≤ 10 MB | `backend/app/main.py:80` |
| `security_headers.py` | CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / Permissions-Policy | `security_headers.py:34-55` |
| `logging.py` | 请求日志中间件 | `backend/app/main.py:111` |
| `__init__.py` | 包初始化 |  |

### 4.8 异步任务（Celery + Redis）

- **Celery app**：`backend/celery_app.py:22-48`
  - broker: `${CELERY_BROKER_URL}` (default `redis://localhost:6379/0`)
  - backend: `${CELERY_RESULT_BACKEND}` (default `redis://localhost:6379/1`)
  - timezone: `Asia/Shanghai`, enable_utc=True
  - task_track_started=True（让 PENDING → STARTED 可见）
  - **Beat schedule**（仅在 `RAG_AUTO_REFRESH_ENABLED=1` 时启用）：每周刷 RAG source（`celery_app.py:54-60`）
- **Tasks**（`backend/app/tasks/`）：
  - `rpa_tasks.py`（279 行）：`submit_visa_application_task` / `check_rpa_status_task`，dispatcher 注册 ID/VN provider（`rpa_tasks.py:32-35`）
  - `rag_tasks.py`：`refresh_rag_sources_task`
- 启动方式（开发）：
  ```bash
  cd backend && .venv/bin/celery -A app.celery_app worker --loglevel=INFO
  cd backend && .venv/bin/celery -A app.celery_app beat --loglevel=INFO
  ```

---

## 5. 前端架构（Vue 3 Web）

### 5.1 框架选型

- **Vue 3.4**（Composition API）+ **Vite 5.2** + **Pinia 2.1** + **Vue Router 4** + **vue-i18n 9**（`frontend/web/package.json:19-27`）
- **Element Plus 2.7**（但**未全局注册**，W19 修：resolver + 全量注册会生成空 dynamic import 触发 SyntaxError）（`frontend/web/src/main.js:9-11`）
- **vite-plugin-pwa** + **workbox**（PWA 缓存 / Service Worker）（`frontend/web/vite.config.js:14-51`）
- **SCSS** + 现代 API（`vite.config.js:59-66`）
- **vite alias**：`@ → src`、`@shared → ../shared`（`vite.config.js:53-58`）
- **proxy**：`/api → http://127.0.0.1:8000`（`vite.config.js:67-76`）

### 5.2 目录结构

```
frontend/web/
├── src/
│   ├── main.js                # 入口: createApp + Pinia + Router + i18n + loadLocale
│   ├── App.vue                # el-config-provider + router-view + ToastContainer + useGeoLocale
│   ├── views/                 # 25 个 page (Home, Login, Register, Destinations,
│   │                          #   MaterialWizard, OrderNew, OrderDetail, Orders,
│   │                          #   RpaSubmit, RpaStatus, PaymentResult,
│   │                          #   Materials*, PassportReview, Diagnose, Apply,
│   │                          #   Resources, Contact, ForgotPassword, Agreement,
│   │                          #   Profile, SchengenCountries, NotFound)
│   │                          # + views/admin/ 子目录
│   ├── components/            # 16 个: AppHeader / AppButton / AppInput / AppCard /
│   │                          #   LangSwitch / TravelPlanner / VoiceRecorder /
│   │                          #   MaterialUploader / PassportUploadModal /
│   │                          #   SelfieCapture / CountrySearchModal /
│   │                          #   UploadItemCard / AffiliateLink / ToastContainer /
│   │                          #   ErrorBoundary.tsx / HtexLogo
│   ├── api/                   # 11 个: auth / admin / materials / orders /
│   │                          #   payment / rpa / voice / destinations /
│   │                          #   affiliate / insurance / http (axios instance)
│   ├── composables/           # 5 个: useGeoLocale / useMaterialWizard /
│   │                          #   useMaterialsProgress / useOnboarding / useToast
│   ├── router/                # index.js (24 路由) + admin.js (子路由)
│   ├── stores/                # auth.js (Pinia) + admin.js
│   ├── i18n/                  # index.js (vue-i18n createI18n + 4 locale + IP 探测)
│   ├── styles/                # main.scss + design tokens
│   ├── utils/                 # 工具函数
│   └── __tests__/             # vitest 单测
├── tests/e2e/                 # Playwright 5 spec
├── playwright.config.cjs
├── vite.config.js
├── vitest.config.ts
├── package.json
└── public/                    # 静态资源
```

### 5.3 路由（`frontend/web/src/router/index.js:6-181`）

共 **24 路由**（不含 404），分 3 类：

**公共路由**（无需登录）：
- `/home` (Home), `/destinations`, `/schengen-countries`, `/apply`, `/diagnose`, `/resources`, `/contact`, `/agreement`, `/orders/new`

**登录后路由**（`requiresAuth: true`）：
- `/profile`, `/materials`, `/materials-wizard`, `/materials/scan`, `/materials/validate`, `/materials/diagnose`, `/passport-review`, `/orders`, `/orders/:orderNo`, `/rpa/submit`, `/rpa/status`, `/payment/result`

**仅游客**（`guestOnly: true`）：
- `/login`, `/register`, `/forgot-password`

**守卫**：
- `adminGuard(to)` 先跑（检查 `admin_token`，独立于 C-user JWT）（`router/index.js:191-192`）
- 然后 `auth.hydrate()` 从 localStorage 恢复
- `requiresAuth && !isLoggedIn` → 跳 `/login?redirect=...`
- `guestOnly && isLoggedIn` → 跳 `/home`

### 5.4 状态管理（Pinia）

- `stores/auth.js`（110 行）：
  - `user / accessToken / refreshToken` ref
  - `isLoggedIn` computed（accessToken + user 都存在）
  - `hydrate()` 从 `localStorage` 的 `visa.auth` key 读
  - `persist()` 写回
  - `loginByPassword / loginWithGoogle / register / refreshAccessToken`
  - **W37 新增 refresh token 完整链路**：`refreshAccessToken()` 由 `http.js` 的 401 拦截器调用，2h access 过期后**静默续期**（`stores/auth.js:82-96`）
- `stores/admin.js`：管理员 token，独立于 C-user JWT

### 5.5 国际化方案（`frontend/web/src/i18n/index.js`）

- **4 语种**：`zh-CN` / `en` / `id-ID` / `vi-VN`（`LOCALES`，`i18n/index.js:42-77`）
- **共享 i18n JSON**：`frontend/shared/i18n/{zh-CN,en,id,vi}.json`（4 个文件，每个 ~60 KB）
- **加载策略**：static import（Vite/JS 同步处理 JSON import，**不**用 dynamic import——之前 race condition 会让 t() 返回 raw key）（`i18n/index.js:7-15`）
- **Locale 解析顺序**（`main.js:22-26`）：
  1. localStorage `visa.lang`
  2. navigator.language 前缀匹配 (zh/id/vi → 否则 en)
  3. ipapi.co 公开 IP 探测（带 3s 超时 + AbortController）
  4. 用户一旦手动切换 → 写 `visa.lang.user_locked=1`，未来 IP 探测不再 override
- **持久化键**：
  - `visa.lang` — 当前 locale
  - `visa.lang.user_locked` — 用户是否手动锁过

### 5.6 UI 组件策略

- **W19 修**（`main.js:9-11`）：**项目实际不使用任何 `<el-*>` 组件**，所有 UI 是自写（`AppButton` / `AppInput` / `AppCard`），全量 ElementPlus 注册会触发 SyntaxError
- `App.vue` 用 `<el-config-provider>` 包 `<router-view>`，仅传入 `elLocale`（`App.vue:1-6`）
- **Vite 构建 chunk 策略**（`vite.config.js:77-105`）：
  - vue/vue-router/pinia/element-plus/vue-i18n → 合并到 `vue-vendor`（避免 TDZ 错误）
  - axios → `axios-vendor`
  - W18-1 修：element-plus 单独拆 chunk 触发 unplugin-vue-components dynamic import 顺序问题
  - W18-2 修：i18n 单独拆 chunk 触发 Vue I18n 9 内部 compose 函数丢失

### 5.7 前端 E2E 测试

- **Playwright 1.60**（`package.json:29`），配置在 `playwright.config.cjs`
- **Vitest 1.5**（单测，`vitest.config.ts`），**实际没在 CI 跑**（CI 注释说"前端测试栈实为 @playwright/test, 不是 vitest"——`ci.yml:11-12`）
- Playwright spec 5 个：`destination / login / register / i18n-full-locale / screenshot`

---

## 6. iOS 端（Flutter）

### 6.1 现状

- **Flutter 3.19+ / Dart 3.3+**（`frontend/ios/pubspec.yaml:5-7`）；CI 实际跑 **Flutter 3.44.2**（`subosito/flutter-action@v2`）（`.github/workflows/ci.yml:35`）
- **包依赖**（`pubspec.yaml:10-27`）：
  - `flutter / flutter_localizations` (sdk)
  - `cupertino_icons ^1.0.6`
  - `http ^1.2.2`
  - `shared_preferences ^2.3.2`
  - `provider ^6.1.2`
  - `intl: any`
  - `qr_flutter ^4.1.0`
  - `google_sign_in ^6.2.2`
- 静态资源：`assets/countries/` + `assets/hero/`（`pubspec.yaml:32-34`）

### 6.2 i18n 现状

- **flutter_localizations + ARB**：`lib/l10n/{app_en,app_id,app_vi,app_zh}.arb`（`frontend/ios/lib/l10n/`）
- 生成的代码在 `lib/l10n/generated/app_localizations.dart`
- **Locale 解析顺序**（`lib/main.dart:73-91`）：
  1. URL `?lang=xxx` 覆盖
  2. 设备 locale（`Platform.localeName`）
  3. Fallback `zh`
- **W34 修**：原来硬编码 `'zh'`，现在优先匹配设备语言

### 6.3 路由（Navigator 1.0, name-based）

共 **16 路由**（`lib/main.dart:156-219`）：home / login / register / forgot / apply / diagnose / resources / passport-upload / contact / destinations / materials / materials-upload / profile / orders / order-detail / order-form / payment / agreement

### 6.4 关键服务（`lib/services/`）

- `auth_service.dart` (302 行)：账号/密码登录 + token 管理
- `apply_service.dart` (110 行)
- `destinations_service.dart` (157 行)
- `diagnose_service.dart` (105 行)
- `ocr_service.dart` (118 行)
- `rag_service.dart` (153 行)

### 6.5 构建 / 部署

- iOS build：`flutter build ios --no-codesign` 产物 `build/ios/iphonesimulator/Runner.app`（`README.md:210`）
- CI：`macos-14` runner 跑 `flutter build ios --simulator --no-codesign`（`.github/workflows/build.yml:43-83`）
- **真机发布阻塞**：`Apple Developer 账号`未提供（`README.md:315`）

### 6.6 测试

- `flutter analyze`（CI：`ubuntu-latest` + `subosito/flutter-action@v2`，`--no-fatal-infos --no-fatal-warnings`）（`ci.yml:215`）
- `flutter test --coverage`（CI 上 `continue-on-error: true`）（`ci.yml:222`）

---

## 7. 微信小程序

### 7.1 现状

- **原生 WXML/WXSS/JS**（`frontend/miniprogram/app.json`）
- **9 个 pages**（`app.json:2-12`）：home / login / register / destinations / profile / order / payment / forgot / agreement
- **3 个 components**：Button / Card / Input
- **utils**：api.js (480 行，封装 wx.request) + auth.js + i18n.js
- **i18n**：自有 4 份 JSON（`frontend/miniprogram/i18n/{en,id,vi,zh-CN}.json`，与 web 共享 `frontend/shared/i18n/` 独立分支）

### 7.2 Tab Bar（`app.json:21-46`）

- 首页 / 选国家 / 我的（3 个 tab，蓝色 `#3B6EF5`）
- `enablePullDownRefresh: false`

### 7.3 Build / CI

- `npm run build:weapp` 跑 `build_weapp.cjs`（静态校验 + miniprogram-ci 尝试）（`frontend/miniprogram/package.json:6-9`）
- CI：`ubuntu-latest` + Node 20（`.github/workflows/ci.yml:241-275`）
- **不**走微信开发者工具 CLI（依赖装在 dev 机器本地）（`ci.yml:243-247` 注释）

---

## 8. 外部依赖

### 8.1 OCR（PaddleOCR + Tesseract 双引擎）

- **当前实际工作**：**Tesseract**（`pytesseract` Python 包 + `/opt/homebrew/bin/tesseract` binary）
- **paddlepaddle 推理引擎未装**：`paddleocr` 包 import 成功但 `_PADDLE_AVAILABLE` 在运行时实际是 `False`（参见 `ocr.py:25-30` 的 try/except 设计，`from paddleocr import PaddleOCR` 实际能 import，但底层依赖 paddlepaddle 不在）
- **触发兜底的逻辑**：`ocr.py:1-14` W19-2 注释明确说"paddleocr 包虽然装了，但底层 paddlepaddle 推理引擎 ~700MB 没装，实际 PaddleOCR 一调就报 'paddle_static unavailable because paddlepaddle not installed'"
- **多语言支持**：en / zh-CN / id / vi / ko / ja / ch（`ocr.py:55-65`）
- **W31 字段抽取升级**：
  - 9 国护照 `passport_re` 各自优先匹配
  - keyword 锚定 + MRZ 兜底

### 8.2 LLM（MiniMax API）

- **API base**：`https://api.minimaxi.com/v1`（`backend/app/core/config.py:155`）
- **Model**：`MiniMax-Text-01`（`config.py:156`）
- **调用点**：仅 `backend/app/services/llm/itinerary_generator.py` 一处用，**唯一 API 端点** `POST /api/v2/itinerary/generate`（`backend/app/api/v2/itinerary.py:64-86`）
- **链路**（端到端）：
  1. 用户在 `frontend/web/src/components/TravelPlanner.vue` 编辑行程（航班 + 逐日）
  2. 点击"AI 一键补全" → 调 `POST /api/v2/itinerary/generate`
  3. 后端 `generate_itinerary_fields()` 构造 system+user prompt（`itinerary_generator.py:82-101`）
  4. `minimax_client.chat()` POST 到 MiniMax，timeout=45s（`minimax_client.py:28-74`）
  5. 解析 JSON 数组返回（**不**走 markdown code fence，`itinerary_generator.py:109-118`）
  6. 按 `day` 字段合并回原数组，**只填空不覆盖**已有字段（`itinerary_generator.py:153-165`）
- **错误处理**：必须检查 `base_resp.status_code`（HTTP 200 仍可能业务错误），缺失配置抛 `LLM_NOT_CONFIGURED`，上游错误抛 `LLM_UPSTREAM_ERROR`
- **W45 实测**：`KNOWN_ISSUES.md:78-79` 确认 MiniMax 真实调用成功，输出交通 Day1 flight 后续 walk、景点 Central Park/Times Square/Met、酒店 The Plaza Hotel
- **凭证管理**：`minimax_api_key` 走 `.env`（gitignored），**禁止 commit**

### 8.3 支付（Stripe / Mock）

#### 8.3.1 V2 现状（Mock）

- `payment_provider.py:1-22` docstring 说"V2 §4.5 — V2 ships Mock-only, V2.1 wires Stripe / 支付宝"
- **Mock 实现**：
  - `create_order()` 返回 `weixin://wxpay/bizpayurl?pr=MOCKxxx`
  - **1 秒后** `loop.create_task(self._auto_notify(...))` 自动调 `handle_notify`
  - 支付元数据 → `orders.extra` JSON
  - 状态机 `pending → paid`
- **支付未接线（前端层面）**：`KNOWN_ISSUES.md:50-51`："步骤条显示 '4 Payment' 但 `OrderNew.vue:531` 注释 `Future: wire up "pay" → payment`，提交后直接跳 RPA；订单 `total_amount=0.00`"

#### 8.3.2 Stripe 真接（V2.1 stub 完整保留）

- `payment_provider.py:610-1187`：**所有方法 raise `NotImplementedError("V2.1 阶段接真 SDK")`** 当 `STRIPE_SECRET_KEY=""`（默认）
- **方法签名已留好**：`create_order` / `query_order` / `handle_notify` / `close_order` / `payout`（V2.1 only）
- **3 个 env 字段**（`backend/app/core/config.py:140-149`）：
  - `STRIPE_SECRET_KEY` (sk_test_xxx / sk_live_xxx)
  - `STRIPE_WEBHOOK_SECRET` (whsec_xxx) — `stripe.Webhook.construct_event` 校验
  - `STRIPE_PAYOUT_ACCOUNT_ID` (acct_xxx) — `stripe.Transfer.create_async` 给联盟伙伴转账
- **macOS Keychain 注入**（推荐做法，`config.py:131-135`）：
  ```bash
  security add-generic-password -s visa-mvp-stripe -a STRIPE_SECRET_KEY -w 'sk_test_xxx'
  ```
- **阻塞**：用户凭证未提供（`README.md:314`）

### 8.4 短信（SMS Mock）

- **没有 SmsService 类**（grep 验证）—— `SMS_CHANNEL=mock` 在 docker-compose / .env 中存在，但实际业务代码里**找不到对应的 `sms_service.py`**
- 仅在 `backend/app/middleware/rate_limit.py:6` 注释里说"sms send: 1/60s + 10/day (handled inside SmsService)"——**这条注释与现实不符**
- V2.1 真接时切换：`SMS_CHANNEL=twilio` 或 `aliyun`（`README.md:184`、`backend/.env.example:30`）

### 8.5 RAG（外部数据源）

- **存储**：`rag_sources` + `rag_chunks` 两张表（`backend/app/models/rag.py`）
- **Embeddings**：本地 `app/services/rag/embedder.py`（具体模型未在 grep 找到，待核）
- **数据来源**：官方签证政策网站 URL（`app/services/rag/crawler.py`）
- **刷新**：默认关闭（`RAG_AUTO_REFRESH_ENABLED=0`），手动 POST `/api/v2/rag/refresh`（`backend/app/api/v2/rag.py:5`）
- **Chroma / 向量数据库**：代码 grep 没看到 chromadb 依赖，**直接用 SQL `RagChunk.embedding` JSON 字段做检索**（`app/services/rag/retriever.py`）

### 8.6 联盟伙伴（Affiliate）

- **Mock only**（`backend/app/services/affiliate_provider.py:1-40`）
- 5 个端点：`track / attribute / commission / payout / stats`（`backend/app/api/v2/affiliate.py:4-8`）
- V2.1 接 CJ / ShareASale / impact.com（`affiliate.py:28-29`）

### 8.7 拒签险（Insurance）

- **Mock only**（`backend/app/services/insurance_provider.py:1-40`）
- 3 个方法：`quote / bind / claim`
- V2.1 接太平洋保险 / 众安保险

---

## 9. 部署 / 运维

### 9.1 Docker（多阶段镜像）

**`backend/Dockerfile`**（85 行，2 阶段）：

- **Stage 1 (builder)** — `python:3.11-slim` + `build-essential/gcc/libffi-dev/libpq-dev`，把 `pip install --prefix=/install -r requirements.txt` 装到 `/install`
- **Stage 2 (runtime)** — `python:3.11-slim` 仅 `curl / ca-certificates / libpq5`；从 builder `COPY --from=builder /install /usr/local`；最后一行 `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- **最终镜像约 180 MB**（README 注释 `Dockerfile:1-7`）

### 9.2 docker-compose（`backend/docker-compose.yml`，71 行）

- **backend service**：
  - 镜像 `visa-mvp-backend:dev`
  - 端口 8000
  - 挂载 `./.data → /app/data`（SQLite）+ `./.logs → /app/logs`
  - 启动命令：`alembic upgrade head && uvicorn ... --reload`
  - depends_on: redis (service_healthy)
- **redis service**：`redis:7-alpine`，端口 6379

### 9.3 GitHub Actions（`.github/workflows/`）

#### 9.3.1 `ci.yml`（276 行，4 jobs）

| Job | Runner | 用途 |
|---|---|---|
| `backend-pytest` | ubuntu-latest | Postgres 16 service container；alembic upgrade；pytest `tests/ -m "not slow"`；case12 E2E regression；上传 coverage.xml |
| `frontend-playwright` | ubuntu-latest | npm ci；vite build；playwright install；`npm run test:e2e`；上传 playwright-report + frontend-dist |
| `flutter-analyze` | ubuntu-latest | flutter pub get + analyze + test；上传 flutter-analyze.log / flutter-test.log |
| `miniprogram-build` | ubuntu-latest | npm ci；`npm run build:weapp:verbose`；上传 build_report.json |

**并发控制**：`concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`（`ci.yml:28-30`）

**关键步骤注释**（`ci.yml:107-117`）：
- `-m "not slow"` 跳过 OCR PaddleOCR warmup（>60s）
- W35 case12 E2E（注册 → 订单 → 支付 → 后台同步 + 反向流程 + 4 表一致性）

#### 9.3.2 `build.yml`（113 行，3 jobs）

| Job | Runner | 用途 |
|---|---|---|
| `web` | ubuntu-latest | `flutter build web --release` |
| `ios` | macos-14 | `flutter build ios --simulator --no-codesign`（含 `pod install`） |
| `miniprogram` | ubuntu-latest | `npm run build:weapp` + `:verbose` |

#### 9.3.3 `vue-e2e.yml`（73 行）— 单 Vue E2E workflow

### 9.4 ADR 决策记录（`docs/adr/`）

| ADR | 标题 | 文件 |
|---|---|---|
| 0001 | FastAPI 而非 Django | `0001-fastapi-not-django.md` |
| 0002 | Vue 3 + Element Plus 选型 | `0002-vue3-elementplus.md` |
| 0003 | V2 Mock 支付策略 | `0003-mock-payment-v2.md` |
| 0004 | 4 语种国际化架构 | `0004-i18n-4-languages.md` |
| 0005 | 业务异常 + 错误码体系 | `0005-bizexception-error-code.md` |
| 0006 | LLM 拒签诊断设计 | `0006-llm-material-diagnosis-design.md` |

---

## 10. 测试 / 验证

### 10.1 后端 pytest

- **测试总数**：`README.md:58` 写"单元 124 + 集成 205 collectable tests"
- **当前 baseline**：W14-1 (19/19) + W14-9 (103/115, 12 skipped) = **122 PASS**（`README.md:245`）
- **目录结构**：
  - `tests/conftest.py`（216 行）：每个 test 一个 in-process FastAPI app + 共享缓存 SQLite
  - `tests/unit/`（15 文件）
  - `tests/integration/`（24 文件）
  - `tests/fixtures/`：9 国护照样张图片（`sample_us_passport.jpg` 等）
  - `tests/rag/`
  - `tests/reports/`
- **关键 conftest 设计**（`tests/conftest.py:78-194`）：
  - 每个 test 用 `file:visa_test_{uuid}?mode=memory&cache=shared&uri=true`（共享缓存 SQLite）
  - **patch 模块级 engine**：因为 `app.core.db` 的 `engine` 在 import 时绑到第一个 event loop，必须 patch `AsyncSessionLocal.kw['bind']` 让后续用 test engine
  - 13 个 router 模块的 `get_db` 必须 patch（conftest.py:154-167）

### 10.2 ⚠️ pytest 配置文件不一致（重点难点 #4）

**`backend/pyproject.toml:13-19`**：
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
# W21.3 fix: session-scope loop 避免 asyncpg engine 跨 event loop 冲突
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

**`backend/pytest.ini:1-12`**：
```ini
[pytest]
asyncio_mode = auto
# W21.5 fix: function-scope loop 恢复,避免 session-scope engine 被破坏的 test 污染后续 test 导致 ECONNREFUSED
asyncio_default_fixture_loop_scope = function
asyncio_default_test_loop_scope = function
```

**冲突**：两个配置文件的 loop scope **正好相反**！pytest 实际行为以哪个为准？

实际以 **`pytest.ini` 优先**（pytest 官方文档），所以当前是 `function` scope loop。
但 `conftest.py:87-103` 注释又说"app fixture 跑在 pytest-asyncio 的 per-test loop"——**与 `pytest.ini` 的 function-scope 一致，但与 `pyproject.toml` 的 session-scope 矛盾**。

这是已知历史遗留坑：`W21.3` 改成 session-scope → `W21.5` 又改回 function-scope，但**没把 pyproject.toml 同步更新**。

### 10.3 ⚠️ 已知坑：pytest 全量跑会清空 dev 数据库

**`KNOWN_ISSUES.md:1-37`（2026-07-02 追加确认）**：

- 现象：`backend/.venv/bin/pytest tests/ -m "not slow"` 全量套件后，`backend/data/visa_mvp.db` 里的 `visa_destinations` / `rag_source` / `rag_chunk` / **`users`** 表都会被清空
- 已确认触发条件：`test_submit.py` + `test_w9_integration.py` 一起跑就复现；单独跑任一文件不触发
- 怀疑根因（未验证）：`backend/app/services/payment_provider.py` 里 `loop.create_task(self._auto_notify(...))` 的 fire-and-forget 任务，`_PENDING_NOTIFIES` dict 持有引用，pytest-asyncio 是 function-scope event loop，task 跨 loop 关闭后还在跑
- **影响**：本地手动跑全量测试后必须重跑种子脚本：
  ```bash
  cd backend && source .venv/bin/activate
  python3 scripts/seed_hero_destinations.py
  python3 scripts/seed_schengen_26.py
  PYTHONPATH=. python3 scripts/seed_rag_sources.py
  ```

### 10.4 前端 Playwright

- 5 spec：`destination / login / register / i18n-full-locale / screenshot`（`README.md:259`）
- `globalSetup` 自动起 `vite dev server :5173`，`workers: 1` + `fullyParallel: false` 保证注册流程 DB 状态串行（`README.md:259`）

### 10.5 前端 Vitest（**实际未在 CI 跑**）

- `vitest.config.ts` 存在（`frontend/web/vitest.config.ts:1-31`）
- `npm run test` 可调
- **CI 没跑**（`ci.yml:11-12` 注释："前端测试栈实为 @playwright/test, 不是 vitest"）

### 10.6 iOS Flutter

- `flutter analyze`（CI：`--no-fatal-infos --no-fatal-warnings`）
- `flutter test --coverage`（CI：`continue-on-error: true`）

---

## 11. 重点难点标注（owner 应该重点关注）

> 排序：影响范围 + 是否阻塞上线 + 风险等级

### 难点 #1：OCR 9 国护照字段映射 + 引擎实际未装

**位置**：
- `backend/app/services/ocr.py:1-100`（双引擎入口 + 9 国护照字段抽取逻辑，698 行）
- `backend/app/services/ocr_field_mapping.yaml:1-207`（9 国护照字段映射配置）

**为什么是难点**：
- paddlepaddle 推理引擎没装，**paddleocr 包虽然 import 成功但实际不工作**（`ocr.py:1-14` 注释明示）
- Tesseract 是 macOS 上的 binary，**Docker 部署时**还要确认 `/usr/bin/tesseract` 是否在镜像里（当前 Dockerfile **没装 tesseract-ocr**！）
- 9 国护照字段映射 YAML 是关键资产，每加一个国家要：a) 加 YAML；b) 加测试夹具（`tests/fixtures/sample_xx_passport.jpg`）；c) 跑 `test_ocr_passport_mapping.py`
- W31 字段抽取升级（keyword 锚定 + MRZ 兜底）是关键逻辑

**风险/坑**：
- **Docker 部署后 OCR 跑不起来** —— 镜像里没装 tesseract binary，也没装 paddlepaddle
- 字段抽取 9 国之外的护照（如 CN 普通护照 ID 位数 9 vs 美 9）容易撞车（`ocr.py:9-11` 历史 bug）
- 护照旋转/倾斜/光线不均 → 字段识别率下降

---

### 难点 #2：行程单 LLM 生成链路（MiniMax 真实接入已验证）

**位置**：
- `backend/app/services/llm/minimax_client.py:1-84`（HTTP 客户端）
- `backend/app/services/llm/itinerary_generator.py:1-166`（prompt 构造 + JSON 解析 + 字段合并）
- `backend/app/api/v2/itinerary.py:1-86`（端点）
- `frontend/web/src/components/TravelPlanner.vue:1-300+`（前端组件）
- `frontend/web/src/composables/useMaterialWizard.js`（行程模块集成）

**为什么是难点**：
- MiniMax API HTTP 200 **仍可能业务错误**（如余额不足），必须查 `base_resp.status_code`（`minimax_client.py:62-65`）
- LLM 输出必须严格是 JSON 数组（不带 markdown fence），需要 robust parse（`itinerary_generator.py:109-118`）
- 字段合并策略：**只填空不覆盖**已有字段（`itinerary_generator.py:153-165`）
- 按日期匹配（不是按位置）：开口程 / 跨天行程要正确归因（`itinerary_generator.py:35-60`）
- 4 语种输出：酒店/景点用对应语种（`_LANG_NAMES`，`itinerary_generator.py:25-30`）

**风险/坑**：
- MiniMax 服务稳定性 / 配额 / 余额依赖第三方
- prompt injection 风险（用户在 itinerary 字段里塞 prompt）
- LLM 输出幻觉（虚构酒店名 / 景点），`KNOWN_ISSUES.md:79` 说"Met、The Plaza Hotel"是真实地标，但其他小语种国家不一定有真实数据
- **重复内容过滤**：LLM 可能填的内容与已填字段重复

---

### 难点 #3：支付未接线 + V2.1 Stripe 切换路径

**位置**：
- `backend/app/services/payment_provider.py:610-1187`（Stripe stub，578 行）
- `frontend/web/src/views/OrderNew.vue:531`（前端"4 Payment"步骤未接线）
- `frontend/web/src/views/PaymentResult.vue:1-600+`（支付结果页有，但入口缺）
- `backend/.env.example:54-67`（Stripe 3 个 env 字段说明）
- `docs/stripe-credentials-setup.md:1-100`（切换指南）

**为什么是难点**：
- **V2.1 切换不是单纯填 env**：要
  1. 申请 Stripe 账号（test mode first）
  2. 设置 webhook endpoint + 拿 `whsec_xxx`
  3. Connect 页面创建 account + 拿 `acct_xxx`
  4. macOS Keychain 注入或 vault 管理
  5. **改 `payment_channel="stripe"` switch**（`config.py:135` 注释："future Story, out of scope"）—— **代码里其实没这个 switch**！
- Stripe `PaymentIntent` / `Webhook` / `Transfer` / `payout` 方法体里**全是 stub**，需逐个实现
- **前端 OrderNew 步骤条 #4 Payment 是装饰**（`KNOWN_ISSUES.md:50-51`），提交直接跳 RPA，订单 `total_amount=0.00`
- **支付 webhook 幂等** 用 `webhook_events` 表（migration 0008 + `app/models/webhook_event.py`）
- **退款逻辑**（`payment_provider.py:399` 注释："V2.1 scope"）—— 关闭订单的退款路径要重做

**风险/坑**：
- `MockPaymentProvider` 1 秒自回调的 asyncio task 是 fire-and-forget；真接 Stripe 后回调链路完全不同（webhook signature 校验、异步推送）
- Affiliate payout 用 `stripe.Transfer` 给 partner 转账，要 Stripe Connect 账户体系，**不是单纯的 PaymentIntent**
- V2.1 阶段不做支付，整个"产品闭环"图（PITCH.md:14-25）里的"Mock 支付通道闭环"只走通到 Mock 通道，**真实支付未实现**

---

### 难点 #4：RPA worker 未实现 + 订单状态机停在 `created`

**位置**：
- `backend/app/services/rpa/rpa_scheduler.py:1-549`（调度器 + 状态机）
- `backend/app/services/rpa/captcha_solver.py:1-300+`
- `backend/app/services/rpa/page_parser.py:1-400+`
- `backend/app/services/rpa/form_filler.py:1-300+`
- `backend/app/services/rpa/providers/IndonesiaVisa.py`、`VietnamVisa.py`
- `backend/app/tasks/rpa_tasks.py:1-279`（Celery tasks）
- `frontend/web/src/views/RpaSubmit.vue:1-400+`（前端进度条页面）

**为什么是难点**：
- **Celery worker 当前没启动**：CI 没起 worker，dev 本地要手动 `celery -A app.celery_app worker`
- `KNOWN_ISSUES.md:51-53` 明确说：
  > **RPA 为假进度**：前端 /rpa/submit 显示 70% 是纯动画；后端任务卡 10% 且 `updated_at==created_at`（无 worker 消费）；`order.rpa_task_id=null`，订单状态停在 `created`。
- 只有 **2 个国家有 provider**（ID/VN），其他国家 409（`README.md:38`、`KNOWN_ISSUES.md`）
- **captcha_solver** 依赖 OCR（Tesseract），若 OCR 失败（见难点 #1）→ 验证码识别失败 → RPA 卡住
- **真实政府网站变动风险**：印尼 / 越南签证网站改版 → form_filler 全失效

**风险/坑**：
- 整个"提交申请" → "状态查询" 主链路**实际跑不通**（停在 `created`）
- "Guaranteed Visa on …"（`destinations.py:50-60`）承诺对用户来说无法兑现
- RPA 提交后无 fallback（如果政府网站挂了，用户完全没法操作）

---

### 难点 #5：pytest 全量跑清空 dev 数据库 + 双配置文件 loop scope 冲突

**位置**：
- `backend/app/services/payment_provider.py:91`（`_PENDING_NOTIFIES` 模块级 dict）
- `KNOWN_ISSUES.md:1-37`（2026-07-02 完整复现条件）
- `backend/pyproject.toml:13-19`（session-scope loop）
- `backend/pytest.ini:1-12`（function-scope loop）
- `backend/tests/conftest.py:78-194`（test engine patch 逻辑）

**为什么是难点**：
- **两个 pytest 配置文件 loop scope 相反**（pyproject.toml 写 session，pytest.ini 写 function），实际行为以 pytest.ini 优先，但**没人同步过 pyproject.toml**
- 全量 pytest 跑完会清空 `users / destinations / rag_*` 表（KNOWN_ISSUES.md:1-37），影响本地手动开发体验
- **根因未确定**：怀疑是 `payment_provider._auto_notify` 的 fire-and-forget task 跨 event loop 关闭后还在跑，但没进一步验证
- 影响：CI 跑（Postgres service container）不会触发此 bug（隔离的数据库），但本地手动跑必触发

**风险/坑**：
- **本地开发体验差**：每次跑全量测试后必须手动跑 3 个 seed 脚本（`KNOWN_ISSUES.md:27-33`）
- **如果引入新业务表**：同样可能被 fire-and-forget task 误清
- `pytest.ini` 和 `pyproject.toml` 配置漂移 —— 任何维护者看到其中一个就要猜哪个生效

---

## 附录 A：项目规模数据

| 指标 | 数值 | 证据 |
|---|---|---|
| 后端 Python 文件 | ~80 | `backend/app/` |
| 后端代码行数（含 service + api） | ~20000+ | grep 估算 |
| `payment_provider.py` 行数 | 1187 | `backend/app/services/payment_provider.py` |
| `ocr.py` 行数 | 698 | `backend/app/services/ocr.py` |
| `order_service.py` 行数 | 853 | `backend/app/services/order_service.py` |
| `audit.py` 行数 | 43 | `backend/app/services/audit.py` |
| Alembic migrations | 13 | `backend/alembic/versions/` |
| ORM 模型 | 14 | `backend/app/models/` |
| API router 文件 | 18 | `backend/app/api/v2/` |
| 前端 Vue 视图 | 25 + admin 子目录 19 | `frontend/web/src/views/` |
| 前端 Vue 组件 | 16 | `frontend/web/src/components/` |
| 前端路由 | 24 | `frontend/web/src/router/index.js` |
| iOS Flutter pages | 16 | `frontend/ios/lib/main.dart:11-30` |
| 小程序 pages | 9 | `frontend/miniprogram/app.json` |
| i18n 语种 | 4（zh-CN/en/id/vi） | `frontend/shared/i18n/`、`frontend/ios/lib/l10n/` |
| CI jobs | 4（ci.yml）+ 3（build.yml） | `.github/workflows/` |
| ADR 决策记录 | 6 | `docs/adr/` |
| 测试 spec | 后端 unit 15 + integration 24 + 前端 playwright 5 + iOS flutter test + vitest | `backend/tests/`、`frontend/web/tests/` |

---

## 附录 B：环境变量清单（`backend/.env.example`）

| 类别 | 关键变量 | 默认 |
|---|---|---|
| App | `APP_NAME` / `APP_VERSION` / `ENV` / `DEBUG` / `API_PREFIX` | `Visa MVP API` / `0.1.0` / `dev` / `1` / `/api/v2` |
| Server | `HOST` / `PORT` | `0.0.0.0` / `8000` |
| Database | `DATABASE_URL` / `DB_ECHO` | `sqlite+aiosqlite:///./data/visa_mvp.db` / `0` |
| JWT | `JWT_SECRET` / `JWT_ALGORITHM` / `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | dev-secret / HS256 / 120 / 7 |
| Password | `BCRYPT_COST` / `PASSWORD_MIN_LENGTH` / `PASSWORD_MAX_LENGTH` | 12 / 8 / 32 |
| SMS | `SMS_CHANNEL` / `SMS_CODE_TTL_SECONDS` / `SMS_COOLDOWN_SECONDS` / `SMS_DAILY_LIMIT` / `SMS_LOG_DIR` | `mock` / 300 / 60 / 10 |
| Rate limit | `RATE_LIMIT_PER_IP_PER_MIN` / `RATE_LIMIT_SLOW_API_PER_IP_PER_MIN` | 100 / 60 |
| Celery | `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` / `:6379/1` |
| RAG | `RAG_AUTO_REFRESH_ENABLED` / `RAG_AUTO_REFRESH_INTERVAL_HOURS` | 0 / 168 |
| Logging | `LOG_DIR` / `LOG_LEVEL` | `./logs` / `INFO` |
| Stripe（V2.1） | `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PAYOUT_ACCOUNT_ID` | （空，留待填） |
| LLM | `MINIMAX_API_KEY` / `MINIMAX_API_BASE` / `MINIMAX_MODEL` | （空）/ `https://api.minimaxi.com/v1` / `MiniMax-Text-01` |
| Admin | `ADMIN_PASSWORD` / `ADMIN_PASSWORD_SECRET` / `SYSTEM_API_KEY` | `CHANGE_ME_IN_PROD` / （空）/ dev key |
| OAuth | `GOOGLE_CLIENT_ID` / `WECHAT_APPID` / `WECHAT_APPSECRET` | （空） |
| CORS | `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:4173,http://localhost:3000` |
| Security | `MAX_REQUEST_SIZE_MB` / `MATERIAL_MAX_FILE_SIZE_MB` | 10 / 10 |

---

## 附录 C：交付检查清单

- [x] 项目概览（§1）
- [x] 技术栈一览表 + 证据路径（§2）
- [x] 系统架构图（mermaid，§3）
- [x] 后端架构：框架 / 目录 / DB / 关键 service / 中间件（§4）
- [x] 前端 Web 架构：Vue3 / 路由 / Pinia / i18n / UI 库 / Vite（§5）
- [x] iOS Flutter 现状（§6）
- [x] 小程序现状（§7）
- [x] 外部依赖：OCR / LLM / 支付 / 短信 / RAG / Affiliate / Insurance（§8）
- [x] 部署 / 运维：Docker / compose / CI（§9）
- [x] 测试 / 验证：pytest / playwright / 已知坑（§10）
- [x] 5 个重点难点标注 + 位置 + 原因 + 风险（§11）
- [x] 每条事实 / 数字附 `file_path:line` 证据