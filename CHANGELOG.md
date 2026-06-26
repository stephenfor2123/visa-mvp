# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Project**: visa-mvp — multi-platform visa application MVP
> **Components**: `backend/` (FastAPI + SQLAlchemy 2.0), `frontend/web/` (Vue 3 + Vite), `frontend/ios/` (Flutter), `frontend/miniprogram/` (WeChat)
> **Tag convention**: `<package>-<semver>` — backend uses `visa-mvp-backend`, web uses `visa-mvp-web`
> **Sprint ledger**: `pm/board/` (W1 ~ W15) — gate reports, summaries, roadmap
> **Date convention**: YYYY-MM-DD (Asia/Shanghai)

---

## [Unreleased]

> Reserved for W16+ in-flight work. Each entry added below as the corresponding task lands.
> See `pm/board/W15_summary.md` (W15 收口报告) and `pm/board/W16_roadmap.md` (W16 路线图) when published.

### Planned
- Stripe live integration (`sk_test_xxx` → `sk_live_xxx`) — blocked on user-supplied credentials
- iOS / Android TestFlight + Google Play internal-track release — blocked on Apple/Google developer accounts
- Full legal review sign-off — `docs/LEGAL_REVIEW_NOTES.md` 18-item checklist, deadline 2026-06-25
- Vite build cache validation on Linux CI runner (macOS M-series `vite build` hang — known pre-existing issue)

### Added
- **frontend/web Dark Mode support** (W16-P0-Dark-Mode) — `data-theme` token switch in `src/styles/tokens.scss`, `useTheme()` composable with `localStorage` persistence (key: `visa-theme`), `<ThemeToggle />` Sun/Moon icon button mounted in Home header. Light/dark token sets cover `--ink-1/2/3`, `--bg`, `--bg-alt`, `--bg-card`, `--border`, `--primary-bg`, and Element Plus `--el-color-*`.

### Changed
- **Home / 4 大签证目的地 色彩鲜艳度** (W29) — `.country-card__media::after` 冷蓝 overlay `opacity: .55 → .35`；`.country-card__img` 滤镜 `saturate(.85) → 1.3` / `contrast(1.05) → 1.08`。设计参考图存档到 `sources/design-references/destinations-hero-vibrant.png` (v1)。

### Fixed
- **`useTheme.js` runtime crash** — TypeScript syntax (`as const`, `: Theme`) in a `.js` file caused `SyntaxError` on import, breaking any page that pulled in the theme system. Removed TS annotations, added try/catch around `localStorage`, renamed storage key from `visa_theme` to spec's `visa-theme`.

---

## [2.0.0] — 2026-06-14

> **Sprint coverage**: W14 (Sprint 收口) + W15 P0 (关键 bug + 性能/可观测性基线)
> **Verdict**: 🟢 PASS — 8/8 W14 task 收口，3 项 W15 P0 落地
> **Gate evidence**: `pm/board/W14_gate_report.md` (66 lines), `pm/board/W14_summary.md` (292 lines)
> **Git anchors** (HEAD):
> - `c94b566` feat: full project source (backend + frontend/ios + web + miniprogram)
> - `ff90756` ci: add GitHub Actions workflow (Flutter iOS/web + miniprogram)
>
> **Headline numbers**
> - 11 W14 task — 4 verifier PASS + 7 code-on-disk (verify-only retry)
> - pytest 实测：W14-1 (19/19) + W14-9 (103/115, 12 skipped, 0 failed) = **122 PASS** baseline
> - 4 语种 i18n：zh-CN / en / id / vi，已统一 envelope + 39+48+44+16+39 keys
> - Vue 主包 baseline：1,410 kB raw / 459 kB gzip（target < 250 kB — W15-P0 partial fix landed）

### Added

#### Backend (FastAPI + SQLAlchemy 2.0)
- **OCR pipeline** (W14-1) — `backend/data/passport_field_mapping.yaml` covers 9 国家 (CN / ID / VN / PH / TH / MY / SG / JP / KR), 19 unit tests, `backend/tests/unit/test_ocr_passport_mapping.py`
- **RPA core** (W14-2) — captcha solver / page parser / form filler / scheduler (4 modules, 52 tests); submit/status/cancel/config 4 端点 in `backend/app/api/v2/rpa.py`; `backend/data/rpa_config.yaml` (限流配置)
- **Admin backend** (W14-3) — `app/api/v2/admin.py` (login / users / orders / config / logs 6 类端点); JWT + role=admin middleware (`middleware/admin_auth.py`); `app/services/admin_service.py` business logic; `alembic/versions/0007_admin_tables.py` 可逆 migration
- **Voice input** (W14-5) — `app/services/voice_input.py` (4 语种 ASR，50+ tests)；`POST /api/v2/voice/recognize`
- **Structured logging** (W15-P0) — loguru `app.log` rotation (10 MB × 14 days); `event_type` 业务事件埋点覆盖: `user.register / user.login / user.sms_login / user.refresh / order.create / order.submit / payment.create / payment.notify`
- **Error code registry** (W15-API-ERR) — 5xxx Materials domain (`MATERIAL_NOT_FOUND / MATERIAL_STORAGE_ERROR / MATERIAL_SIGNED_URL_INVALID`) + 6xxx Voice/ASR domain (`VOICE_AUDIO_FORMAT / VOICE_RECOGNIZE_FAILED / VOICE_TIMEOUT`)
- **HTTP exception fallback handler** — `app/main.py` 全局兜底，统一 `{code, message, data}` envelope

#### Frontend web (Vue 3 + Vite + Element Plus)
- **RPA submit/status 页面** (W14-4) — `views/RpaSubmit.vue` (14094 B) + `views/RpaStatus.vue` (12956 B) + `api/rpa.js` (4 API); 4 语种 rpa section (48 keys)
- **Payment result page** (W14-10) — `views/PaymentResult.vue` (21262 B, 4 状态: success / failed / pending / cancelled + 30s polling); `api/payment.js` (query/cancel/retry); 4 语种 payment section (39 keys)
- **Admin login + dashboard** (W14-11) — `views/admin/AdminLogin.vue` (7579 B, 居中卡片 + localStorage token); `views/admin/RateLimit.vue` (25236 B, 4 字段配置 + 实时统计卡); `api/admin.js` (12.5 kB, login/logout/getProfile + getRpaConfig/updateRpaConfig/getRpaStats)
- **i18n lazy loading** (W15-P0) — `src/i18n/index.js` 4 个 locale JSON 从静态 import 改为 `() => import('@shared/i18n/xx.json')` 动态加载；首屏仅加载用户 locale，预计节省 ~85 kB gzip
- **4 语种 i18n baseline** — `frontend/shared/i18n/{zh-CN,en,id,vi}.json` 全栈覆盖（auth / order / payment / rpa / admin / materials / agreement sections）

#### Legal / compliance
- **法务 review 框架** (W14-8 / W14-9-legal) — `docs/LEGAL_REVIEW_NOTES.md` (211 行, 18 项 checklist)；4 语种 `agreement.*` 加 `__legal_review_pending__` marker；`frontend/web/src/views/Agreement.vue` 加 5 行 `LEGAL_TODO` 注释
- **3 层 placeholder 体系** — i18n JSON marker + Vue 组件 LEGAL_TODO 注释 + docs/LEGAL_REVIEW_NOTES.md 三处冗余记录（避免单点遗漏）

#### DevOps / CI
- **GitHub Actions workflow** (W14-9) — `.github/workflows/ci.yml` 4 jobs / 35 steps: backend pytest (Python 3.11) + frontend-web vitest + miniprogram build + Flutter iOS/web analyze
- **Local CI fallback** — `validate_ci_yml.py` PyYAML 静态 lint；本地 pytest 实战 103/115 PASS (sqlite + `--noconftest`)
- **Dockerfile** (backend) — Python 3.11-slim base, requirements.txt pinned, 健康检查 endpoint
- **`.gitignore` 强化** — 新增 `*.bak` / `*.md.bak` / `*.md~` glob 排除备份文件

### Changed

- **Backend error responses** — 所有 endpoint 错误响应统一为 `{code, message, data}` envelope；`BizException` 自动按 `ErrorCode.HTTP_STATUS_MAP` 返回正确 HTTP 状态码；`voice.py` 6 处错误 `return ApiResponse` → `raise BizException`
- **Auth service logging** — 5 处 plain `_log.info()` 升级为结构化 `extra={user_id, event_type, duration_ms, status}` 格式
- **Materials API error paths** — 3 处 `raise HTTPException(...)` → `raise BizException(MATERIAL_*, ...)`，HMAC signed URL 验证失败现在返回 `5003` (403) 而非通用 403
- **i18n index.js** — 移除 4 个 JSON 静态 import，引入 `loadLocale()` 动态加载 + `vue-i18n` `setLocaleMessage` 缓存
- **WORKLOG 历史占位** — 5 个 worklog 文件 (`A_WORKLOG / C_WORKLOG / backend-WORKLOG / frontend-WORKLOG / outputs-C-W11R-3-deliverable`) 共清理 106 处历史占位；保留 `.md.bak` 备份 + `.gitignore` 排除
- **`admin.py` import block** — 合并重复的 `from app.schemas.admin import (...)` 块

### Deprecated

- 无（本版本无计划弃用项；W16+ 可能 deprecate legacy `ApiResponse(code="2003", ...)` 风格错误返回）

### Removed

- 无（本版本未删除任何 public API）

### Fixed

- **i18n id.json 末尾孤立 `}`** (P0, 印尼语页面空白) — 修污染清理过程中新发现的 pre-existing bug，记入 W15-2 必修清单
- **`/payment/notify` 完全无日志** — `payment.py` 无 logger 导入，W15-P0 新增 `payment.create` + `payment.notify` 结构化埋点
- **`materials.py` HMAC signed URL 错误码含糊** — 之前 403 通用 `invalid_or_expired_token`，现区分 `MATERIAL_SIGNED_URL_INVALID` (5003/403) vs `MATERIAL_NOT_FOUND` (5001/404)
- **`voice.py` 错误路径返回 200 + 非 1000 code** — 之前 6 处异常返回 HTTP 200 + code=2003/2004/2005，违反 RESTful；现统一 `raise BizException` 返回正确 HTTP 4xx/5xx
- **WORKLOG 修污染** — 106 处 sed in-place 替换（`修整实战 → 实战` 等长链先替换），保留 `.md.bak` 备份回滚

### Security

- **Admin auth middleware** — JWT + role=admin 守卫覆盖 admin/* 全端点；`ADMIN_PASSWORD=visa-admin-2024` 默认值写入 `.env`（⚠️ P1 遗留 — 生产环境必须迁 secret manager，见 [Known issues](#known-issues)）
- **Materials HMAC signed URL** — `MATERIAL_SIGNED_URL_INVALID` (5003/403) 区分无效/过期 token vs 文件不存在 (5001/404)，降低信息泄漏
- **Rate limiting** — `app/middleware/rate_limit.py`（限流中间件）+ admin UI 可视化配置 (W14-6 `RateLimit.vue` 4 字段实时调整)
- **Audit logging** — `app/services/audit.py::record_audit` + `app/models/audit_log.py` (44B model)；admin 操作 / 订单状态变更 / 支付回调落 audit_log

---

## [2.1.0] — Template (W16)

> **Status**: 📋 planned (W16 sprint scope, blocked on W15 收口 + user-supplied 凭据)
> **Target window**: 2026-06-21 ~ 2026-06-27
> **Source roadmap**: `pm/board/W15_roadmap.md` §6.2 (W16+ outline)

### Planned — Added

- Stripe live integration — replace `payment_provider.py` mock with real Stripe SDK (`sk_live_xxx`)
- iOS TestFlight build — flutter `ios/Runner.xcworkspace` archive + upload (blocked on Apple developer account)
- Google Play internal track — flutter `android/app/build.gradle` AAB + Play Console upload (blocked on Google Play Console)
- Real passport sample data — extend OCR `passport_field_mapping.yaml` to cover 9-digit pure numeric samples (CN/ID real-world gap)
- Admin login real-world test — uvicorn live server + curl `POST /api/v2/admin/login` E2E

### Planned — Changed

- Vite build cache + manualChunks — `element-plus / vue-vendor / i18n / axios-vendor` split (target: index.js < 200 kB gzip)
- PayPal / Apple Pay / Google Pay — third channel adapter alongside Stripe
- `documents/LEGAL_REVIEW_NOTES.md` 行数偏差 — 当前 claim 246 行 / 实测 211 行，需统一 metric

### Planned — Fixed

- `frontend/shared/i18n/id.json` 末尾孤立 `}` (P0) — 第 631 行删 `}` + 4 语种 `json.load` 全 PASS
- `tests/conftest.py` fixture 顺序 + `.venv-test` 缺 `paddleocr` / `cv2` — 影响 39 个 RPA/OCR 测试失败；W16 P0 必修
- `ci.yml` 注释残留 `修` 占位 — 替换为正常中/英文说明
- macOS M-series `vite build` hang — 已在 W14/W15 旁路 (AST + JSON + Playwright headless)；W16 走 GitHub Actions Linux runner 真实 build 验证

### Planned — Removed

- `voice_input.py::map_voice_error_to_envelope()` (only used by `api/v2/voice.py`) — 已迁 `raise BizException`，可移除（保留供其他调用方使用，待 audit）

### Planned — Security

- `ADMIN_PASSWORD` 默认值 — 移除 `.env` 硬编码 `visa-admin-2024`，改 secret manager / vault (HashiCorp Vault / AWS Secrets Manager / 阿里云 KMS)
- 第三方 SDK 声明落地 — Stripe / 火山引擎 OCR / 阿里云 / PaddleOCR / 同盾 / 数美 / 微信支付 等 6 项 SDK 风险披露（分 4 语种），签字页独立 section

---

## [3.0.0] — Template (W17+)

> **Status**: 📋 planned (跨 sprint 大版本，依赖 W16 上线稳定运行)
> **Target window**: 2026-06-28 ~ 2026-07-15 (法务 review deadline 2026-06-25, launch 2026-07-01)
> **Breaking-change risk**: 🟠 HIGH — 涉及支付渠道切换 / i18n 重构 / API v3 introduction

### Planned — Breaking changes (semver-major)

- **API v3 introduction** — 当前 `/api/v2/*` 标记 deprecated，并行 `/api/v3/*` 6 个月；v3 统一 envelope (`{code, message, data}`)、统一 pagination (`{items, total, page, page_size}`)、统一 timestamp (ISO 8601 UTC)
- **Frontend Vue 3 → Vue 3.5+ + Element Plus 3.x** — Composition API 全量迁移 + `<script setup>` 统一
- **Backend FastAPI 0.110+** — Pydantic v2 强制 (`model_dump()` 替代 `dict()`)；`Annotated[..., Depends(...)]` 注入统一
- **i18n key 命名重构** — 从 dot.notation (`payment.status.success`) 改 nested object (`payment.status.success` → `payment.statusSuccess` 或 split per namespace)；需 4 语种同步迁移 + 翻译 review

### Planned — Added

- **WebSocket realtime push** — 订单状态 / 支付回调 / RPA 进度推送；当前 `app/api/v2/ws_orders.py` 137 行已存在，W17 扩 chat / customer-support channel
- **OpenAPI 3.1 schema** — `app/main.py` 自动生成，CI 校验 breaking change
- **Multi-tenant** — agency / B2B partner API key 体系
- **CI/CD 多环境** — dev / staging / production 三套 GitHub Actions environment + manual approval

### Planned — Removed (W17)

- `/api/v1/*` (若有) — 完全移除，强制 v3
- 旧的 `ApiResponse` ad-hoc 返回 — 强制 `BizException`
- 旧的 `app/services/legacy_*` 文件夹 (如有) — 完全移除

### Planned — Security (W17)

- 全站 HTTPS + HSTS + CSP strict policy
- OAuth 2.1 + PKCE — 第三方登录 (WeChat / Apple / Google)
- GDPR / CCPA 合规 — 数据导出 (Subject Access Request) + 账号删除 (Right to be Forgotten) 端点
- 渗透测试报告 + Bug Bounty 上线 (launch 后 30 天)

---

## Known issues (跨版本遗留)

> 以下为 2.0.0 阶段尚未关闭的 known issues，按优先级排序。

| # | 严重度 | 描述 | 影响 | 跟踪 |
|---|--------|------|------|------|
| 1 | 🔴 P0 | `frontend/shared/i18n/id.json` 末尾孤立 `}` | 印尼语页面空白，阻断 1/4 用户 | W15-2 / F9 in `pm/board/W14_summary.md` |
| 2 | 🔴 P0 | `backend/.venv/bin/python3` symlink 链到 system Python | 8+ pytest 全 hang (W14-3/4/5/6 触发) | W15-1 / F1 |
| 3 | 🟠 P1 | `ADMIN_PASSWORD=visa-admin-2024` 硬编码 `.env` | 生产部署前必修 | W16 / F18 |
| 4 | 🟠 P1 | Stripe live integration 未真接 (mock provider) | 真实支付不可用 | W16 / F14 (待凭据) |
| 5 | 🟠 P1 | 主包 gzip 459 kB 超阈值 (target < 250 kB) | 移动端首屏慢 | W16 / F15 |
| 6 | 🟡 P2 | `tests/conftest.py` fixture 顺序 + `.venv-test` 缺 paddleocr/cv2 | 39 RPA/OCR test 失败 | W16 |
| 7 | 🟡 P2 | macOS M-series `vite build` hang | 本机无法实跑 npm build | W16 / F7 (CI runner) |
| 8 | 🟡 P2 | `ci.yml` 注释残留 `修` 占位 | 阅读体验脏 | W15-8 |
| 9 | 🟡 P2 | 全项目剩余 202 行 `修` 污染 (`.mavis/plans/*.yaml` 128 + docs/ 39 + frontend/{web,ios}/A_WORKLOG 20) | 视觉脏 | W14-9 cleanup-residual |
| 10 | 🟡 P2 | OCR regex 不覆盖 9 位纯数字护照 (CN/ID 真实样本) | 业务 gap | W15 后端 / F17 |
| 11 | 🟡 P2 | `documents/LEGAL_REVIEW_NOTES.md` 行数 claim 偏差 (246 vs 211) | 文档 metric 不一致 | W15-9 |
| 12 | 🟡 P2 | 6 个 W14 verify-only task 仍缺独立 `deliverable.md` (RPA / admin / 前端 RPA / voice / ratelimit / payment / admin login) | verifier 验证链断 | W15-3 ~ W15-7 |

---

## How to read this changelog

- **Major version (x.0.0)** — breaking changes (API v3, schema 重构, 框架升级)
- **Minor version (2.x.0)** — 新功能 (新端点 / 新页面 / 新 SDK 集成)
- **Patch version (2.0.x)** — bug fix + 安全补丁
- 每个 sprint 收口产出 1 个 minor 版本；W14 + W15 P0 合并为 2.0.0
- Keep a Changelog 6 类别 (Added / Changed / Deprecated / Removed / Fixed / Security) 必须按出现顺序排列
- Unreleased 段持续累积，sprint 收口时剪到新版本段

---

## References

- **Keep a Changelog**: https://keepachangelog.com/en/1.1.0/
- **Semantic Versioning**: https://semver.org/spec/v2.0.0.html
- **W14 gate report**: `pm/board/W14_gate_report.md`
- **W14 summary**: `pm/board/W14_summary.md`
- **W15 roadmap**: `pm/board/W15_roadmap.md`
- **WORKLOG** (按需引用): `backend/WORKLOG.json`, `frontend/web/A_WORKLOG.md` 等
- **风险登记**: `pm/risks/risks.md`
- **WBS**: `pm/wbs/wbs.md` (W1 ~ W8 原始任务树)

---

*Last updated: 2026-06-15 (W15 P0 收口 + CHANGELOG 初始化)*