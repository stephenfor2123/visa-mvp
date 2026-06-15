# Visa MVP — Backend (W1)

[![Security Policy](../../SECURITY.md)](../../SECURITY.md) [![Supported: v2.x](../../SECURITY.md#1-supported-versions)](../../SECURITY.md#1-supported-versions) [![Report Vulnerability](../../SECURITY.md#2-reporting-a-vulnerability)](../../SECURITY.md#2-reporting-a-vulnerability)

FastAPI 0.115 + SQLAlchemy 2.0(async) + SQLite + Alembic + JWT.
账号模块 5 端点 + 中间件 + 测试。

> Found a security issue? See [`SECURITY.md`](../../SECURITY.md) — please **do not** open a public Issue.

---

## 1. 快速开始(本地 venv)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 1) 初始化数据库(开发)
.venv/bin/alembic upgrade head

# 2) 起服务
.venv/bin/uvicorn app.main:app --reload --port 8000

# 3) 健康检查
curl http://localhost:8000/health
# => {"status":"ok","app":"Visa MVP API","version":"0.1.0"}
```

> **测试模式 SMS 验证码:** 任意 6 位数字都通过(便于联调)
> **生产模式:** 把 `SMS_CHANNEL=twilio` 切换,后端会自动用 Twilio adapter

---

## 2. 快速开始(Docker Compose)

```bash
cd backend
cp .env.example .env       # 按需改 JWT_SECRET 等
docker compose up --build

# 4 端点就绪在 http://localhost:8000
# Redis 在 localhost:6379 (供 W2+ Celery worker 用)
```

容器启动时会自动跑 `alembic upgrade head`。
数据落在 `./.data/visa_mvp.db`,日志在 `./.logs/`。

---

## 3. 5 个账号端点

| Method | Path | 说明 | 状态码 |
|---|---|---|---|
| POST | `/api/v2/auth/register` | 手机号+验证码+密码注册,返回 JWT | 201 |
| POST | `/api/v2/auth/login` | 账号密码登录 | 200 |
| POST | `/api/v2/auth/sms-login` | 短信快捷登录(测试模式:任意 6 位数字) | 200 |
| POST | `/api/v2/auth/refresh` | 滑动刷新 access + refresh | 200 |
| POST | `/api/v2/auth/send-code` | Mock SMS 验证码(返回 `code` 字段) | 200 / 429 |

### 3.1 错误码(V2 §9.3 1xxx-7xxx)

| 段位 | 域 | 例子 |
|---|---|---|
| 1xxx | 通用 | 1001 INVALID_PARAMS, 1009 RATE_LIMIT, 1010 SERVER_ERROR |
| 2xxx | Auth | 2001 INVALID_CREDENTIALS, 2002 SMS_CODE_INVALID, 2003 USER_ALREADY_EXISTS, 2004 PASSWORD_TOO_WEAK, 2005 ACCOUNT_DISABLED, 2006 REFRESH_TOKEN_INVALID, 2010 SMS_RATE_LIMIT |
| 3xxx | User | 3001 USER_NOT_FOUND |
| 7xxx | 第三方 | 7001 SMS_GATEWAY_DOWN |

### 3.2 curl 示例

```bash
# 注册
curl -X POST http://localhost:8000/api/v2/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "phone":"13800138000",
    "phone_country":"+86",
    "password":"abc12345",
    "sms_code":"123456",
    "nickname":"alice"
  }'

# 拿验证码(mock 模式直接返回 code)
curl -X POST http://localhost:8000/api/v2/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138001","phone_country":"+86","purpose":"login"}'

# 短信登录(mock 模式 6 位数都通过)
curl -X POST http://localhost:8000/api/v2/auth/sms-login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","phone_country":"+86","sms_code":"000000"}'

# 密码登录
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","phone_country":"+86","password":"abc12345"}'

# 刷新
curl -X POST http://localhost:8000/api/v2/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REFRESH>"}'
```

---

## 4. 项目结构

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + exception handlers
│   ├── core/                    # config / db / security / errors / logging
│   ├── models/                  # SQLAlchemy 2.0 ORM (4 张表)
│   ├── schemas/                 # Pydantic v2 request/response DTO
│   ├── services/
│   │   ├── auth_service.py      # register / login / sms-login / refresh
│   │   ├── sms_service.py       # code gen + rate-limit + verify
│   │   ├── audit.py             # 审计日志
│   │   ├── sms/                 # SMSChannel 抽象 + Mock + Twilio stub
│   │   └── payment/             # PaymentAdapter 抽象 + Mock
│   ├── api/v2/auth.py           # 5 个 auth 端点
│   └── middleware/              # logging + rate-limit
├── alembic/                     # 数据库迁移
│   └── versions/0001_init.py    # 4 张表
├── tests/test_auth.py           # 30+ 用例
├── data/                        # SQLite (gitignored)
├── logs/                        # 日志 (gitignored)
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 5. 数据库迁移

```bash
# 应用所有未跑的迁移
.venv/bin/alembic upgrade head

# 降级到 base
.venv/bin/alembic downgrade base

# 重新生成(改了 model 之后)
.venv/bin/alembic revision --autogenerate -m "describe change"
```

初始 4 张表(详见 `alembic/versions/0001_init.py`):
- `users` — phone / phone_country / password_hash / nickname / language_pref / status
- `user_sessions` — refresh_token_hash / device_fingerprint / ip / expires_at / revoked_at
- `sms_codes` — phone / code_hash / purpose / expires_at / used_at
- `audit_log` — actor_type / actor_id / action / target_type / target_id / payload

唯一约束:`(phone_country, phone)` 在 users 上;`code_hash` 在 sms_codes 上无唯一(可重发)。

---

## 6. 中间件

| Middleware | 说明 |
|---|---|
| `RequestLoggingMiddleware` | loguru 一行/请求,带 rid / 耗时 / 状态码 |
| `RateLimitMiddleware` | 全局 100 req/min/IP,auth 路由 60 req/min/IP(可配) |
| `CORS` | 开发期放开 `*`,生产收紧 |
| `get_current_user` (Depends) | Bearer JWT 解析 → User |

限流命中返回 `429 + {code: 1009, message: "Rate limit exceeded"}`。

---

## 7. 测试

```bash
# 全跑
.venv/bin/pytest

# 单文件
.venv/bin/pytest tests/test_auth.py -v

# 覆盖率
.venv/bin/pytest tests/test_auth.py \
  --cov=app.api.v2.auth \
  --cov=app.services.auth_service \
  --cov=app.services.sms_service \
  --cov-report=html:tests/reports/coverage
# HTML 报告: tests/reports/coverage/index.html
```

测试覆盖(`app/api/v2/auth/`) **88%**(目标 ≥ 80%,PASS)。
所有 38 个用例全 PASS。

### 7.1 测试夹具

- `_test_env` — 切换临时 SQLite + 关掉限流噪声(session 级)
- `app` — 每次 fresh,自动 drop_all + create_all
- `client` — `httpx.AsyncClient` over `ASGITransport`

---

## 8. SMS / Payment 接口预留(V2 §4.1.5 / §4.6)

- **SMSChannel** 抽象:`app/services/sms/base.py`
  - `MockSMSChannel` — V2 默认,写 `logs/sms.log` + 返 `mock_xxx` txn id
  - `TwilioSMSChannel` — V3+ 占位
  - `get_sms_channel()` — 按 `SMS_CHANNEL` env 选
- **PaymentAdapter** 抽象:`app/services/payment/adapter.py`
  - `MockPaymentAdapter` — W1 占位,create/confirm/query 永远 succeed
  - W2 接真实通道时新加 `StripePaymentAdapter` / `AlipayPaymentAdapter`,工厂切换

切换只改 env,业务代码 0 改动。

---

## 9. 已知限制(W1)

- 单进程内存限流器(W2 用 Redis 集群版替换)
- Mock SMS 直接返回 `code` 字段给前端(开发期),生产去掉
- 没有 password reset / logout 端点(W2)
- 没有 user profile 端点(W2)
- 没有 rate limit 的 IP 白名单(W2)
- Celery worker 暂未起(W2 接 destroy 异步任务时再起)

---

## 10. 常用命令

```bash
# 启动
.venv/bin/uvicorn app.main:app --port 8000 --reload

# 跑迁移
.venv/bin/alembic upgrade head

# 跑测试
.venv/bin/pytest

# 看 SQLite schema
sqlite3 data/visa_mvp.db ".schema"

# Docker
docker compose up --build
docker compose exec backend alembic downgrade base
docker compose logs -f backend
```

---

详细错误码 / 业务规则参考 V2 需求文档 §1.5 / §4.1 / §9.3。
