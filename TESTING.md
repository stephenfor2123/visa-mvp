# TESTING — 签证项目测试约定

> 后端 (FastAPI + SQLAlchemy 2.0 + pytest-asyncio) 与前端 (Vue 3 + Playwright) 的统一测试规范。
> 最后更新：2026-06-15

---

## 1. 测试分层

按 **运行速度 × 依赖真实度** 自下而上分三层，每层职责清晰、互不重叠。

### 1.1 `backend/tests/unit/` — 单元测试

- **范围**：单个函数 / 类的纯逻辑（validation、format、parser、state machine）。
- **依赖**：**不依赖 FastAPI app、不依赖 HTTP client、不依赖 live DB**。
- **可选依赖**：可使用 `tmp_db` fixture（独立 sqlite temp file）做 service 层 repo 测试，但**不走 HTTP、不启动 app**。
- **运行**：毫秒级，每个 test 独立。
- **现状**：11 个文件 / 124 collectable tests（去除 collection-error 文件）。
- **示例**：`test_validation.py`、`test_rpa_captcha_solver.py`、`test_rpa_form_filler.py`、`test_rpa_page_parser.py`、`test_rpa_scheduler.py`。

### 1.2 `backend/tests/integration/` — 集成测试

- **范围**：API 端到端走 FastAPI app + DB，验证路由 → service → repo → DB 全链路。
- **依赖**：`tests/conftest.py` 的 `app` + `client` fixture（`httpx.AsyncClient` + `ASGITransport` 内存驱动）+ sqlite temp file DB。
- **运行**：秒级；`tests/conftest.py:_test_env` 已自动关掉 rate-limit / SMS-cooldown / daily-limit，避免噪声。
- **现状**：22 个文件 / 205 collectable tests（去除 collection-error 文件）。
- **示例**：`test_auth.py`、`test_orders.py`、`test_payment.py`、`test_sms.py`、`test_ws_orders.py`。

### 1.3 `frontend/web/tests/e2e/` — E2E 测试（Playwright）

- **范围**：跨浏览器、跨端到端用户旅程（S1 注册 → 登录 → 主页 → 提交订单）。
- **依赖**：起 `vite dev server`（`globalSetup.cjs`）+ 假设后端 FastAPI 在 `http://127.0.0.1:8000` 跑着。
- **运行**：秒级到分钟级，**默认 `workers: 1` + `fullyParallel: false`**（注册流程涉及 DB 状态，串行更稳）。
- **现状**：5 个 spec（`register.spec.js`、`login.spec.js`、`destination.spec.js`、`i18n-full-locale.spec.js`、`screenshot.spec.js`）。
- **配置**：`frontend/web/playwright.config.cjs`。

### 1.4 顶层 root-level 测试（特殊情况）

- `backend/tests/test_auth.py` — 旧 root-level 测试（需评估是否下沉到 `integration/`）。
- `backend/tests/ocr_accuracy_test.py` — OCR 精度专项（独立 fixture，标记为 `slow`）。

---

## 2. 覆盖率目标

| 模块类别 | 目标 line coverage | 说明 |
|---|---|---|
| **核心 services**（`app/services/` 业务逻辑） | **≥ 80%** | 订单/支付/认证/材料/OCR 业务核心 |
| **API 端点**（`app/api/`, `app/routers/`） | **≥ 70%** | FastAPI 路由 + 输入校验 |
| **utils / helpers**（`app/utils/`, 纯函数） | **100%** | 无副作用的小工具函数 |
| **RPA 子系统**（`app/services/rpa/`） | **≥ 60%** | 含 OCR 视觉分支，环境敏感 |
| **DB models**（`app/models/`） | **≥ 50%** | 通常由 integration 覆盖，不强制 |

### 2.1 跑覆盖率

```bash
cd backend
.venv-test/bin/python -m pytest \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=html:tests/reports/coverage_html \
  --cov-fail-under=70
```

报告输出到 `backend/tests/reports/coverage_html/index.html`。

---

## 3. Mock 约定

按依赖类型选择固定 mock 方案，**禁止在测试中真打外部服务**。

### 3.1 DB — sqlite + aiosqlite

- **unit 层**：可选 `tmp_db` fixture（独立 sqlite temp file，per-test drop+create），见 `backend/tests/unit/conftest.py`。
- **integration 层**：`tests/conftest.py:_test_env` session 级设置 `DATABASE_URL=sqlite+aiosqlite:///<tmpdir>/test.db`，配合 `app` fixture 做 `drop_all` + `create_all` 拿到干净 schema。
- **禁止**：连开发 DB（`visa_mvp.db`）或 staging/prod。

### 3.2 SMS — `MockSmsProvider`

- 已落地：`app/services/sms_provider.py` 提供 `MockSmsProvider` 单例 + `reset_sms_provider_for_tests()`。
- 集成测试 `_isolate_provider` fixture 自动 reset（参考 `test_sms.py`）。
- 行为：内存 store、`code_length`/`ttl_seconds` 参数校验、抛 `CodeExpired`/`CodeMismatch`/`NoCodeOnFile`。
- **禁止**：使用真短信网关或在测试中断言"短信已发出"。

### 3.3 Payment — Stripe stub

- 已落地：`tests/integration/test_payment_stripe_stub.py` 走内存 stub。
- 真 Stripe 测试用 `stripe listen --forward-to localhost:8000/api/v2/webhooks/stripe` + test API keys；CI 跳过。
- **禁止**：在单测/integration 中打 `api.stripe.com`。

### 3.4 外部 HTTP — `httpx` mock（推荐 `respx`）

- 推荐库：`respx`（httpx 官方 mock 库，与 ASGITransport 同生态）。
- 用法：
  ```python
  import respx
  from httpx import Response

  @respx.mock
  async def test_external_call(client):
      respx.post("https://api.example.com/notify").mock(
          return_value=Response(200, json={"ok": True})
      )
      ...
  ```
- **禁止**：在测试中打真 HTTP endpoint（`requests.get("https://...")` / `httpx.AsyncClient().get(...)` 直连）。

### 3.5 Redis — `fakeredis`

- 推荐库：`fakeredis>=2.0`（兼容 `redis.asyncio` API）。
- 用法：
  ```python
  import fakeredis.aioredis

  @pytest.fixture
  def fake_redis(monkeypatch):
      r = fakeredis.aioredis.FakeRedis()
      monkeypatch.setattr("app.core.cache._redis", r)
      yield r
  ```
- **禁止**：测试连真 Redis（6379）。

### 3.6 其他常见 mock

| 目标 | 推荐 |
|---|---|
| 时间 / 时钟 | `freezegun` 或 `unittest.mock.patch("time.time", ...)` |
| 文件 IO | `tmp_path` fixture（pytest 内建） |
| subprocess / shell | `unittest.mock.AsyncMock` / `MagicMock` |
| 环境变量 | `monkeypatch.setenv()` |

---

## 4. 运行约定

### 4.1 后端测试

```bash
cd backend

# 全跑（默认 -v --tb=short）
.venv-test/bin/python -m pytest

# 只跑 unit
.venv-test/bin/python -m pytest tests/unit/

# 只跑 integration
.venv-test/bin/python -m pytest tests/integration/

# 跳慢速
.venv-test/bin/python -m pytest -m "not slow"

# 跑单个文件
.venv-test/bin/python -m pytest tests/unit/test_validation.py

# 看收集（不执行）
.venv-test/bin/python -m pytest --co -q
```

### 4.2 前端 E2E

```bash
cd frontend/web
# 假设后端已起在 :8000
npx playwright test
npx playwright test register.spec.js
npx playwright test --headed
```

### 4.3 CI 跑法（推荐）

```bash
cd backend
.venv-test/bin/python -m pytest --cov=app --cov-fail-under=70 --junitxml=tests/reports/junit.xml
```

---

## 5. 命名 & 组织约定

### 5.1 文件命名

- 后端：`test_<module>.py` 或 `test_<feature>_<scenario>.py`。
- 前端：`<feature>.spec.js`（Playwright 约定）。

### 5.2 类 / 函数命名

- 类：`Test<Feature>` 或 `Test<Feature><Scenario>`（如 `TestSendCodeMock`）。
- 函数：`test_<expected_behavior>`（如 `test_factory_returns_mock_singleton`）。

### 5.3 标记（markers）

- `@pytest.mark.slow` — OCR / 大 fixture / 视觉识别测试（`-m "not slow"` 跳过）。
- 自定义 marker 需在 `pytest.ini` 注册。

---

## 6. 已知问题 & 故障排查

| 现象 | 根因 | 解决 |
|---|---|---|
| `sqlalchemy.exc.ArgumentError: Could not ...` | ORM model 与 sqlite 类型不兼容（如 `JSONB`、`UUID`） | 跳过该文件或用 PG test DB；本项目部分文件已 collection-error，见 baseline |
| `no such table: sms_codes` | `app.models` 未在 fixture 早期 import | `tests/conftest.py:app` 已显式 `import app.models` |
| `RuntimeError: Event loop is closed` | session-scoped fixture 跨 loop | 见 `tests/unit/conftest.py:_tmp_engine_and_factory` 自行创建 loop |
| vite dev hang on macOS M | Element Plus tree-shake scan 死锁 | E2E 走 `vite preview` 或绕开（见 `W14-11` 经验） |

---

## 7. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-06-15 | 初版：分层 / 覆盖率目标 / mock 约定落地。Baseline = 454 tests collected (6 collection errors). |