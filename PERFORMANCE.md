# Performance — 性能基线与调优检查表

> 状态: **living document**  
> 适用版本: Visa MVP V2 (FastAPI 0.110+ / SQLAlchemy 2 async / Vue 3 + Vite 5)  
> 最近更新: 2026-06-15 (W16)  
> 维护者: backend + frontend engineer

本文档沉淀当前 API 响应时间基线、已落地的性能基线(W15)与待办调优清单(W16+)。
所有优化动作都需要先在 `qa/` 留 fixture, 再跑对应的 pytest 集成用例, 最后在
`backend/tests/reports/` 与 `frontend/web/dist/` 出 baseline diff。

---

## 1. 当前性能基线 (Performance Baseline)

> **数据来源**: 基于 `backend/tests/integration/` + `unit/` 的测试 wall-time 经验估值,  
> 单 worker FastAPI + SQLite (dev) / PostgreSQL (prod), DSN 通过
> `DATABASE_URL` env 切换.  
> 真实的 percentile 需要从 staging Prometheus 拉 (`http_request_duration_ms` histogram).

### 1.1 API 路由响应时间 (单次请求, p50 估算)

| 路由 | HTTP 方法 | 当前 p50 (估) | 主要耗时来源 | 备注 |
|---|---|---|---|---|
| `/health` | GET | ~5 ms | DB ping (`SELECT 1`) | 健康检查, 不缓存 |
| `/api/v2/destinations` | GET | ~20 ms | 全表读 + JSON 解析 | **首页热点, 无缓存** |
| `/api/v2/auth/login` | POST | ~80 ms | bcrypt verify + JWT 签发 | 慢路径, 60 req/min/IP 限流 |
| `/api/v2/auth/send-code` | POST | ~120 ms | SMS Provider (mock, 真实 Twilio ~250 ms) | 1 req/60s/IP |
| `/api/v2/materials` | GET | ~30 ms | user_id + created_at 索引覆盖 | OK |
| `/api/v2/materials/{id}` | GET | ~15 ms | 主键 | OK |
| `/api/v2/orders` | POST | ~150 ms | 创建 + 状态历史 + 关联 material | 写路径 |
| `/api/v2/orders` | GET (列表) | ~45 ms | `idx_orders_user_created` | OK |
| `/api/v2/orders/{order_no}` | GET | ~60 ms | `selectinload(status_history, messages)` | N+1 已防 |
| `/api/v2/payment/create` | POST | ~200 ms | provider.create_order + DB 写入 | 同步, Mock |
| `/api/v2/payment/notify` | POST | ~180 ms | HMAC 校验 + DB 更新 + WebhookEvent 落库 | **W16 应改异步** |
| `/api/v2/admin/dashboard` | GET | ~80 ms | 7 个 count() + 内存 cache (60s TTL) | 已加 TTL |
| `/api/v2/admin/orders` | GET | ~90 ms | 列表分页 + count | OK |
| `/api/v2/affiliate/...` | POST | ~70 ms | provider.attribute + 事件 hook | W9-3 OMS 事件 |
| `/api/v2/ocr/passport` | POST | ~800 ms | PaddleOCR / mock | 同步, 大 payload |
| `/api/v2/voice/transcribe` | POST | ~1200 ms | ASR provider (mock) | 同步, 应改异步 |
| `/api/v2/rpa/start` | POST | ~100 ms | Celery dispatch + Redis | 已异步 |
| `/scheduler/cron/poll-orders` | POST | ~300 ms | N orders 轮询 | 系统密钥鉴权 |

> **SLO 目标 (待 W17 与 PM 确认)**  
> - 健康检查 / 静态配置: p95 < 50 ms  
> - 用户读路径 (orders/materials/destinations): p95 < 200 ms  
> - 用户写路径 (orders/payment create): p95 < 500 ms  
> - Webhook / OCR / Voice: p95 < 2 s (允许异步化)

### 1.2 Bundle size (frontend, dist 估算)

| Chunk | 体积 (gzipped, 估) | 来源 |
|---|---|---|
| `vue-vendor` | ~28 KB | `vue` + `vue-router` + `pinia` |
| `element-plus` | ~95 KB | Element Plus (按需引入, 通过 `unplugin-vue-components`) |
| `i18n` | ~3 KB × 4 = ~12 KB | vue-i18n + locale (lazy loaded, 首屏只载入 1 个) |
| `axios-vendor` | ~12 KB | axios |
| 业务 views (懒加载) | ~80 KB total | 12+ 个路由级 chunk |

**已做的 lazy load**:
- i18n locale files — `frontend/web/src/i18n/index.js:104-117` 用 `import()` 动态加载, 首屏仅载入检测到的 1 个 locale
- 路由级 code splitting — Vite 默认, 12+ 视图各为独立 chunk
- Element Plus 按需 — `unplugin-vue-components/resolvers/ElementPlusResolver`

---

## 2. 已落地的性能基础设施 (W15)

| 模块 | 文件 | 效果 |
|---|---|---|
| 结构化日志 | `backend/app/core/logging.py` + `middleware/logging.py` | loguru 单行 JSON, 每个请求带 `rid` + `{method} {path} -> {status} {ms}` |
| Prometheus metrics | `backend/app/core/metrics.py` + `/metrics` route | `http_requests_total`, `http_request_duration_ms` histogram (5ms..10s), `app_active_users` gauge; `@timed` 装饰器已挂在 `payment/*` 路由 |
| 错误统一封装 | `backend/app/core/errors.py` + `main.py` exception handlers | BizException / HTTPException / ValidationError / 兜底 Exception → 统一 4 字段 error envelope |
| Bundle i18n lazy load | `frontend/web/src/i18n/index.js` | 4 个 locale 拆 chunk, 首屏 1 个, 切换时按需 fetch |
| Vite chunk split | `frontend/web/vite.config.js` | vue-vendor / element-plus / i18n / axios-vendor 各自长期缓存 |
| PWA runtime cache | `vite.config.js` workbox | Google Fonts CacheFirst 1y, `/api/*` NetworkFirst 5s timeout 1h |
| In-memory dashboard cache | `services/admin_service.py:609-660` | 60 s TTL, 命中返回 `cached=true` |
| Rate limit | `middleware/rate_limit.py` | global 100/min/IP, slow path 60/min/IP, in-memory deque |
| Request size limit | `middleware/request_size_limit.py` | max 10 MB, 防 OOM |
| Security headers | `middleware/security_headers.py` | CSP / X-Frame / X-Content-Type / Permissions-Policy |
| CORS 收紧 | `main.py:78-104` | 显式 allowlist, prod 禁 wildcard |

---

## 3. 调优检查表 (Tuning Checklist)

> 优先级排序: P0 = 影响所有用户的快路径 → P2 = 边缘优化.

### 3.1 DB 索引 (P0)

| 表 | 列 | 当前索引 | 评估 | 行动 |
|---|---|---|---|---|
| `orders` | `user_id`, `created_at` | `idx_orders_user_created` ✅ | 订单列表已覆盖 | 无 |
| `orders` | `order_no` | UNIQUE 隐含索引 ✅ | 主查询路径 | 无 |
| `orders` | `status` | `idx_orders_status_active` ✅ | admin 看板筛选 | 无 |
| `orders` | `rpa_task_id` | `idx_orders_rpa` ✅ | RPA worker 回调 | 无 |
| `orders` | `destination_id` | 普通 index ✅ | OK | 无 |
| `orders` | `aff_code` | 普通 index ✅ | W9-3 affiliate attribution | OK, 多 click 时升级复合索引 |
| `materials` | `user_id`, `created_at` | `idx_materials_user_created` ✅ | 列表已覆盖 | 无 |
| `materials` | `ocr_status` | `idx_materials_ocr_pending` ✅ | "待 OCR" 扫描 | 无 |
| `order_poll_log` | `order_no`, `polled_at` | `idx_order_poll_log_order_polled` ✅ | 防重复轮询 | 无 |
| `order_poll_log` | `poll_source` | `idx_order_poll_log_source` ✅ | 按来源聚合 | 无 |
| `sms_codes` | `phone`, `phone_country`, `purpose` | `ix_sms_codes_phone_purpose` ✅ | 验证码查重 | 无 |
| `webhook_events` | `provider`, `order_no` | `ix_webhook_events_provider_order_no` ✅ | 幂等查重 | 无 |
| `webhook_events` | `processed_at` | `ix_webhook_events_processed_at` ✅ | 时序扫描 | 无 |
| `audit_log` | `actor_type`, `actor_id`, `action` | `ix_audit_log_actor_action` ✅ | admin 审计 | 无 |
| `audit_log` | (另一 index) | ✅ | 路径 2 | 见文件 line 49 |
| `user_sessions` | `user_id`, `token_jti` | 待 verify | JWT 失效列表 | **W16** 加 `token_jti` index |
| `users` | `phone`, `phone_country` | 待 verify | 登录查重 | **W16** 加 unique + index |

**结论**: 当前核心索引覆盖良好. **W16 增量**:
- `users(phone, phone_country)` UNIQUE — 防重复注册, 加速 login 查表
- `user_sessions(token_jti)` index — JWT 黑名单扫描

### 3.2 N+1 查询 (P1)

**已防 N+1**:
- `orders/{order_no}` — `services/order_service.py:748-749` 用 `selectinload(status_history, messages)` 一次性加载

**潜在 N+1 风险点**:
| 位置 | 风险描述 | 修复建议 |
|---|---|---|
| `services/admin_service.py:671-697` | Dashboard 一次发 **7 个** `select count()` 查询 | 合并为单个 CTE / subquery, 一次 round-trip 拿 7 个数字 |
| `services/admin_service.py:96-181` (users / orders 列表) | 当前直接 list, 但 page 内若有 lazy ref 会被循环触发 | list 输出已用 Pydantic, 暂时安全; 引入新关系时务必加 `selectinload` |
| `services/order_service.py` 创建订单 | 状态历史/消息用 `relationship(cascade=...)` + ORM, 内部已 batched | OK |
| `api/v2/affiliate.py` 事件回灌 | 若 partner 返回嵌套 click list, 可能隐式循环 | 后续加 selectinload 防御 |

### 3.3 缓存 (P1, Redis 或 in-memory dict + TTL)

| 数据 | 当前 | 建议 |
|---|---|---|
| Admin dashboard stats | in-memory `dict[str, Any]` + 60s TTL ✅ (`admin_service.py:611`) | OK |
| `/api/v2/destinations` | 无缓存 ❌ | **W16**: in-memory TTL 5 min (数据基本静态); Redis 后续 |
| Visa validation rules | DB 查询 (`admin_service.py:425`) | **W16**: process-level lru_cache (基本静态, 全局共享) |
| SMS code 计数 (1/60s + 10/day) | DB 查 (`sms_service.py`) | OK (DB 写入即防滥用) |
| MFA token | JWT 5 min TTL (`mfa_service.py:45`) | OK |
| Payment `MOCK_ORDER_TTL` | 2 h TTL (`payment_provider.py:121`) | OK (MemStore + DB) |

**W16 行动**:
1. 加 `app/core/cache.py` — 统一 `TTLCache` 接口, 默认 in-memory, 预留 Redis backend (`aiocache` 或自写)
2. `/destinations` 命中 5 min cache, 失效靠 admin 改 destination 时主动 invalidate
3. `validation_rules.json` (`core/validation_rules.json`) 启动时 load 一次, lru_cache 装饰 service 方法

### 3.4 Celery 异步任务 (P1)

**已异步 (Celery dispatch)**:
- `rpa_tasks` — `/api/v2/rpa/start` 走 Celery worker (`app/celery_app.py:22`)
- Mock payment auto-notify — `provider.create_order` 后 1 s 异步回调

**应改异步 (W16)**:
| 路由 | 现状 | 改造方案 |
|---|---|---|
| `/api/v2/payment/notify` | 同步处理 HMAC + DB 更新 | Celery task, webhook 路由只做"接收 + 入 webhook_events 表" |
| `/api/v2/voice/transcribe` | 同步 ASR (~1.2 s) | Celery task, 前端轮询 task result 或 WS |
| `/api/v2/ocr/passport` | 同步 PaddleOCR (~0.8 s) | Celery task, 同步返 task_id, 前端 poll |
| `/api/v2/admin/broadcast` | (待确认) | 若有, 走 Celery |
| 邮件/短信发送 | 当前可能同步 | 走 Celery (无 retry / 失败报警) |

**Celery 调优 (W16)**:
- 加 `app/tasks/payment_webhook.py` 处理 stripe webhook 入库
- 拆 `rpa_tasks.py` (现在仅 1 文件) 为 `payment_webhook`, `ocr_async`, `voice_async`, `notification`
- task 配置: `task_acks_late=True` ✅, `task_reject_on_worker_lost=True` ✅, 已配 Redis broker ✅
- 加 task retry policy: `autoretry_for=(DBError, TimeoutError)`, `retry_backoff=True`, `max_retries=3`

### 3.5 CORS + GZip 压缩 (P1)

| 项 | 状态 | 行动 |
|---|---|---|
| CORS 收紧 (无 wildcard) | ✅ `main.py:82-104` | OK |
| `gzip` 响应压缩 | ❌ **未启用** | **W16**: 加 `from fastapi.middleware.gzip import GZipMiddleware` + `app.add_middleware(GZipMiddleware, minimum_size=500)` |
| `brotli` | ❌ | nginx/CDN 层处理, 应用层不必 |
| response size audit | 部分 (`request_size_limit.py` 仅限制入站) | OK |

**W16 行动**:
```python
# backend/app/main.py 中 SecurityHeadersMiddleware 之后插入
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)  # bytes, 跳过小响应
```
预期收益: 列表类 JSON (orders/materials) 体积降 60-80%, JSON 1 KB → gzip ~250 B.

### 3.6 HTTP Cache Headers (ETag / Last-Modified) (P2)

| 路由 | 当前 | 建议 |
|---|---|---|
| `/api/v2/destinations` | 无 cache header | **W16**: 加 `Cache-Control: public, max-age=300, s-maxage=600` (in-memory TTL 5 min + CDN) |
| `/api/v2/admin/dashboard` | 无 (动态) | `Cache-Control: private, max-age=60` |
| `/api/v2/orders/{no}` | 无 | `Cache-Control: private, no-store` (用户私有) |
| 静态资源 (Vue dist) | 无 (Vite output 文件名带 hash) | nginx 配 `Cache-Control: public, max-age=31536000, immutable` (在 vite `assetsDir` hash 命名已具备) |
| `/api/v2/destinations` ETag | 无 | **W17**: 基于 `display_order + updated_at` 计算 weak ETag |

### 3.7 CDN 静态资源 (P2)

| 资源 | 当前 | 建议 |
|---|---|---|
| `frontend/web/dist/assets/*.js, *.css` | nginx 直接 serve | 生产部署到 CDN (Cloudflare / 阿里云 OSS + CDN) |
| `frontend/web/dist/icons/*.png` | 同上 | CDN |
| `frontend/web/dist/favicon.svg` | 同上 | CDN |
| Google Fonts | VitePWA runtime cache 1y ✅ | OK |
| i18n JSON (lazy) | Vite 已拆 chunk | 加 `Cache-Control: public, max-age=86400` |

**W17 行动**: 部署文档加 CDN 配置段 (origin-pull + immutable for hashed assets).

### 3.8 懒加载 (i18n 已在做) (P2)

| 项 | 当前 | 评估 |
|---|---|---|
| i18n locale lazy | ✅ `frontend/web/src/i18n/index.js:104` | 已做 |
| 路由级 lazy | ✅ Vite 默认 dynamic import | 已做 |
| Element Plus 按需 | ✅ unplugin-vue-components | 已做 |
| 图片 lazy (HTML `loading=lazy`) | 待 verify | **W16**: 列表页加 `<img loading="lazy">` |
| 大组件 (PDF preview / OCR preview) | 直接 import? | **W16**: 用 `defineAsyncComponent` 包裹 |
| `lodash-es` | 若有引入全量 | 用 `lodash-es` 按需 / 换成 native |

---

## 4. 行动优先级总表 (W16 / W17 / 后续)

| Sprint | 优先级 | 任务 | 预期收益 | 风险/前置 |
|---|---|---|---|---|
| W16 | P0 | `app/core/cache.py` + destinations 5 min TTL | destinations p50 20ms → ~3ms | 失效需 invalidate hook |
| W16 | P0 | Dashboard 7 个 count → 单 CTE | dashboard p50 80ms → ~30ms | SQL 兼容 (SQLite + PG) |
| W16 | P0 | GZipMiddleware | JSON 体积 -70% | CPU 微涨, 可接受 |
| W16 | P0 | `/payment/notify` 改 Celery async | webhook p95 < 50ms | task retry / dead-letter |
| W16 | P0 | `users(phone, phone_country)` UNIQUE index | 防重 + login 加速 | data migration (重复数据需先清洗) |
| W16 | P1 | `validation_rules.json` lru_cache | 启动加载, 命中 0 ms | 数据变更需重启 (接受) |
| W16 | P1 | `user_sessions(token_jti)` index | JWT 黑名单扫描加速 | 小流量, 收益有限 |
| W16 | P1 | `/voice/transcribe` + `/ocr/passport` async | 长请求不再占 worker | 前端改 polling/WS |
| W16 | P2 | `<img loading="lazy">` | 首屏 / 列表渲染加速 | 兼容性 OK |
| W16 | P2 | destinations ETag + Cache-Control | CDN 命中 +304 | 计算 ETag 简单 |
| W17 | P1 | Celery task retry policy + dead-letter | 失败可观测 | 新增 `app/tasks/dlq.py` |
| W17 | P2 | Redis cache backend (替换 in-memory dict) | 多 worker 共享 | 部署 Redis, 配置 TTL eviction |
| W17 | P2 | CDN 静态资源 origin-pull | 静态资源 RTT ↓ | DNS / TLS 配置 |
| W17 | P3 | Real percentile from staging | 把估算表换成实测 | 需 Prometheus + Grafana |
| W17+ | P3 | HTTP/2 + HTTP/3 (QUIC) | 移动端弱网提升 | nginx + Alt-Svc header |
| W17+ | P3 | DB read replica | 读多写少场景 | 部署双 PG |

---

## 5. 验证方法 (How to verify)

### 5.1 后端 (FastAPI)

```bash
cd /Users/apple/Desktop/签证项目/backend

# 1. 单元 + 集成测试 (CI 必跑)
.venv/bin/pytest tests/unit -q --tb=short
.venv/bin/pytest tests/integration -q --tb=short

# 2. 性能基线录制 (新)
.venv/bin/python scripts/bench_api.py \
  --endpoint /api/v2/destinations \
  --warmup 10 --iter 100 \
  --output ../qa/perf_destinations_$(date +%Y%m%d).json

# 3. Prometheus metrics 拉取
curl http://localhost:8000/metrics | grep http_request_duration_ms
```

### 5.2 前端 (Vite)

```bash
cd /Users/apple/Desktop/签证项目/frontend/web

# 1. Bundle size 检查
npm run build 2>&1 | tee ../qa/perf_bundle_$(date +%Y%m%d).log

# 2. Lighthouse (本地)
npx lighthouse http://localhost:4173 --output json --output-path ../qa/perf_lh.json

# 3. 路由级 chunk 体积
ls -lh dist/assets/*.js | awk '{print $5, $NF}'
```

### 5.3 CI 集成 (待 W17 接入 GH Actions)

```yaml
# .github/workflows/perf.yml
- name: API benchmark
  run: pytest tests/integration --benchmark-only
- name: Bundle size budget
  run: |
    SIZE=$(stat -c %s dist/assets/index-*.js)
    if [ "$SIZE" -gt 200000 ]; then echo "JS too big: $SIZE bytes"; exit 1; fi
```

---

## 6. 不做清单 (Out of scope, 显式拒绝)

- ❌ 应用层 brotli 压缩 — nginx/CDN 层处理更高效
- ❌ 引入 GraphQL — REST + 强缓存 + 已知契约, 收益不抵复杂度
- ❌ 实时推送 (WebSocket 全站化) — 仅 `/ws/orders/{no}` 一处, 其他用 polling
- ❌ 微服务拆分 — V2 阶段单 FastAPI 进程足以支撑 < 10K MAU
- ❌ 预编译 SQL — 当前 ORM 已带 prepared statement, 额外优化收益微小
- ❌ CDN 自建 — 用 Cloudflare / 阿里云即可, 不重复造轮

---

## 7. 参考 (References)

- FastAPI 性能文档: <https://fastapi.tiangolo.com/advanced/middleware/>
- SQLAlchemy 2 async 性能: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- Prometheus Python client: <https://github.com/prometheus/client_python>
- Web Vitals (前端感知): <https://web.dev/vitals/>
- 项目内: `backend/app/core/metrics.py`, `backend/app/middleware/rate_limit.py`,
  `frontend/web/vite.config.js`, `frontend/web/src/i18n/index.js`
</content>
</invoke>