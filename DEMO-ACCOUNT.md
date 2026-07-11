# 演示账号说明(DEMO-ACCOUNT) — **DEPRECATED 2026-07-07**

> ⚠️ **本文档已废弃**,W26 (2026-06-25) 之后已迁移到 email/username 登录体系,
> **手机号 + 密码的登录方式不再可用**(`POST /api/v2/auth/login` 只走 email/username 两条分支)。
>
> **请改用 [`TEST-ACCOUNTS.md`](./TEST-ACCOUNTS.md)** — 当前生效的演示账号、密码、
> 银行流水 sample 一站式文档。
>
> 本文件保留下来是因为里面 iOS 入口、Mock 支付测试流程、API 重置命令等历史操作
> 细节仍有参考价值,内容冻结不再更新。账号/密码表格已同步到 8 位新规则,供查阅比对。

## 1. 账号总览(冻结 — 以 TEST-ACCOUNTS.md 为准)

| 角色 | 登录账号 | 密码 | 登录入口 | 用途 |
| --- | --- | --- | --- | --- |
| 普通用户 1(无订单) | `demo138001380001@htex.app` / `demo_user_138001380001` | `Htex@2026` | Web `/login`、iOS Login 页 | 演示"刚注册完成,选国家 → 上传材料"完整流程 |
| 普通用户 2(已下单) | `demo138001380002@htex.app` / `demo_user_138001380002` | `Htex@2026` | Web `/login`、iOS Login 页 | 演示"已申请,未支付"订单状态、取消订单 |
| 普通用户 3(已支付) | `demo138001380003@htex.app` / `demo_user_138001380003` | `Htex@2026` | Web `/login`、iOS Login 页 | 演示"已支付,等待 RPA 出签"状态流转、订单详情 |
| 管理员(admin) | 用户名 `admin` | 密码 `HtexAd@26` | Web `/admin/login`(`http://localhost:5173/admin/login`) | 用户管理 / 订单管理 / 国家配置 / 限流配置 / 审计日志 |

> **密码策略**:`PASSWORD_MIN_LENGTH=8`(`backend/.env.example` 第 24 行)。
> 演示密码 `Htex@2026` / `HtexAd@26` 均为 8 位,**满足**该策略,不再像旧版 `demo1234`
> 那样靠直接写库绕过校验。生产部署仍必须改用强密码,这两个仅用于本地开发与演示。
>
> **admin 密码来源**:`backend/.env` 第 79 行 `ADMIN_PASSWORD_SECRET=HtexAd@26`(生产
> 必须改)。seed 脚本 `--apply-admin-password` 会自动写入并覆盖旧值。

---

## 2. 每个账号的预期状态

### 2.1 普通用户 1(`13800138000`)

| 字段 | 状态 |
| --- | --- |
| 注册状态 | ✅ 已注册(`users.status = active`) |
| 订单数 | 0 |
| 材料 | 0 |
| 适用场景 | 演示空状态 → 选国家 → 上传材料 → 创建订单 |
| Web 入口 | `/destinations` → `/materials` → `/orders/new` |
| iOS 入口 | Home → Destinations tab → 选国家 → 拍照 / 相册上传 |

### 2.2 普通用户 2(`13800138001`)

| 字段 | 状态 |
| --- | --- |
| 注册状态 | ✅ 已注册 |
| 订单数 | 1(状态:`created` / `pending_payment`) |
| 适用场景 | 演示"已下单未支付"状态、取消订单流程、WebSocket 状态轮询 |
| 取消操作 | 订单详情页右下角"取消订单"按钮 → 弹窗确认 |
| 取消后状态 | 订单 `cancelled`、支付 `cancelled`、不可再次取消(再点返 4010 错误码) |

### 2.3 普通用户 3(`13800138002`)

| 字段 | 状态 |
| --- | --- |
| 注册状态 | ✅ 已注册 |
| 订单数 | 1(状态:`paid` / `rpa_processing`) |
| 适用场景 | 演示支付成功 → 等待 RPA → 模拟出签成功 / 失败 |
| 关键路径 | `/orders/:orderNo` → 顶部时间线显示 `paid → rpa_processing → completed` |

### 2.4 admin(`admin` / `admin123`)

| 字段 | 状态 |
| --- | --- |
| 角色 | `admin`(`admin_id = 0`,由后端硬编码) |
| 密码来源 | `backend/.env` 第 70 行 `ADMIN_PASSWORD_SECRET=CHANGE_ME_IN_PROD`(生产必须改) |
| 权限 | 全量:`users` / `orders` / `config/countries` / `config/validation-rules` / `config/rpa` / `stats/rpa` / `logs` |
| 适用场景 | 演示后台管理流程、配置变更、审计追溯 |

> **特别账号**:`lockedadmin` —— admin 登录页会返 `ACCOUNT_LOCKED`,演示锁定态 UI(密码任意)。

---

## 3. 登录入口

### 3.1 Web 端(浏览器)

| 入口 | URL | 说明 |
| --- | --- | --- |
| 普通用户登录 | `http://localhost:4173/login` | Vue Router 路由,密码登录 / 短信登录双 tab |
| 普通用户登录(预填 demo) | `http://localhost:4173/login?demo=1` | URL 加 `?demo=1` 自动填 `13800138000 / demo1234`(参考 `Login.vue:362-367`) |
| 管理员登录 | `http://localhost:4173/admin/login` | 独立路由,独立 token(`admin.*.*` 前缀) |
| 管理员登录(预填) | `http://localhost:4173/admin/login?demo=1` | 自动填 `admin / admin123`(`AdminLogin.vue:156`) |
| Home | `http://localhost:4173/` | 公开页,无需登录 |
| 支付结果 | `http://localhost:4173/payment/result?order=...` | 30s 轮询,支持 `success` / `failed` / `pending` 3 态 |

> 端口说明:Web 端默认 4173(`vite.config.js`);后端 API 默认 8000。前端通过 `VITE_API_BASE_URL` 指向后端。

### 3.2 API 路径(curl / Postman)

| 端点 | Method | 用途 |
| --- | --- | --- |
| `/api/v2/auth/send-code` | POST | 发送短信验证码(mock 模式直接返回 `code` 字段) |
| `/api/v2/auth/login` | POST | 用户名 + 密码登录 |
| `/api/v2/auth/sms-login` | POST | 手机号 + 验证码登录 |
| `/api/v2/auth/register` | POST | 注册新用户(需要 `phone` + `sms_code`) |
| `/api/v2/auth/refresh` | POST | 刷新 access token |
| `/api/v2/admin/login` | POST | 管理员登录(`admin / admin123`) |
| `/api/v2/admin/users` | GET | 管理员查询用户列表 |
| `/api/v2/admin/orders` | GET | 管理员查询订单列表 |
| `/api/v2/payment/status/{orderId}` | GET | 支付状态轮询 |
| `/api/v2/payment/cancel/{orderId}` | POST | 取消未支付订单 |
| `/api/v2/payment/retry/{orderId}` | POST | 失败重试支付 |

完整 API 文档见 `docs/API.md`(942 行)。

#### 管理员登录 curl 示例

```bash
curl -s -X POST http://localhost:8000/api/v2/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

返回:

```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "role": "admin"
  }
}
```

#### 普通用户登录 curl 示例

```bash
# 1. 发送验证码(mobile 模式直接返回 code)
curl -s -X POST http://localhost:8000/api/v2/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","phone_country":"+86","purpose":"login"}'

# 2. 用验证码登录
curl -s -X POST http://localhost:8000/api/v2/auth/sms-login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","phone_country":"+86","code":"demo1234"}'
```

---

## 4. 重置 demo 数据

### 4.1 标准重置命令(推荐)

```bash
cd /Users/apple/Desktop/签证项目
python scripts/seed_demo_data.py --reset
```

脚本将:

1. 删除 SQLite 数据库文件 `backend/data/visa_mvp.db`(如不存在则跳过)
2. 重新运行 `alembic upgrade head` 应用所有迁移
3. 重新创建 9 国基础数据(`visa_destinations` 表,`backend/scripts/seed_countries.py` 等价逻辑)
4. 重新创建 3 个 demo 用户 + 1 个 admin(脚本内置硬编码,见下表)
5. 为用户 2 / 用户 3 各创建 1 个示范订单(状态分别为 `pending_payment` / `paid`)

| 用户 | 手机号 | 密码 | 状态 |
| --- | --- | --- | --- |
| demo_user_1 | `+86 13800138000` | `demo1234` | active,0 订单 |
| demo_user_2 | `+86 13800138001` | `demo1234` | active,1 订单 `pending_payment` |
| demo_user_3 | `+86 13800138002` | `demo1234` | active,1 订单 `paid` |
| admin | `admin` | `admin123` | 来自 `ADMIN_PASSWORD_SECRET` |

### 4.2 手工重置(脚本未实现时的 fallback)

```bash
# 1. 停后端
pkill -f "uvicorn app.main" 2>/dev/null

# 2. 删 DB
rm -f backend/data/visa_mvp.db

# 3. 重新初始化
cd backend
.venv/bin/alembic upgrade head

# 4. 注册 3 个 demo 用户(走 API)
curl -X POST http://localhost:8000/api/v2/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","phone_country":"+86","purpose":"register"}'
# 取返回的 code,再调 register 接口

# 5. 启动后端
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4.3 前端 mock 数据重置(Web 端)

Web 端本地 mock 数据存在 `localStorage`,在 DevTools Console 跑:

```javascript
// 清空所有 mock 数据
Object.keys(localStorage).filter(k => k.startsWith('visa.')).forEach(k => localStorage.removeItem(k))
location.reload()
```

会清除 `visa.auth`(登录态)、`visa.lang`(语言)、`visa.payments`(支付 mock)、`visa.materials`(材料 mock)等所有 `visa.*` 前缀的 key。

---

## 5. Mock 支付测试流程

> 本节演示如何不接 Stripe 即可跑通完整"创建订单 → 支付 → webhook 回调 → 状态更新"链路。

### 5.1 前置条件

- 前端 `VITE_MOCK !== 'false'`(默认即为 mock,见 `payment.js:17`)
- 后端 `SMS_CHANNEL=mock`(默认,`backend/.env.example` 第 29 行)
- 已用普通用户 1(`13800138000 / demo1234`)登录

### 5.2 完整流程

```text
┌──────────┐   1. POST /v2/orders       ┌──────────┐
│  Browser │ ─────────────────────────► │  Backend │
│  (Web)   │                            │  FastAPI │
└──────────┘                            └──────────┘
     │                                        │
     │  2. 返回 order_no = ORD-XXX            │
     │ ◄──────────────────────────────────────┤
     │                                        │
     │  3. POST /v2/payment/status/ORD-XXX    │
     │     (前端自动轮询)                     │
     │ ──────────────────────────────────────►│
     │                                        │
     │  4. status = pending,amount = 9900 cents│
     │ ◄──────────────────────────────────────┤
     │                                        │
     │  5. 【手动】用 setMockPaymentStatus     │
     │     推到 success                        │
     │     (DevTools Console)                 │
     │                                        │
     │  6. 前端轮询返 success                  │
     │     → 跳 /payment/result?order=ORD-XXX │
     │     → 顶部显示绿色 ✓ + 交易号           │
     ▼                                        ▼
```

#### 步骤 1:创建订单

Web 端:`登录 → /destinations → 选 US → /materials → 上传护照 → /orders/new → 填表 → 提交`
iOS 端:同上,Flutter UI。

提交成功后页面跳到 `/orders/:orderNo`,看到 `created` 状态时间线。

#### 步骤 2:查询支付状态

前端订单详情页会自动调 `GET /api/v2/payment/status/{orderId}`,30s 一次(轮询逻辑见 `PaymentResult.vue`)。

Mock 模式首次调:会在 `localStorage.visa.payments` 创建一条 `pending` 记录,`amount_cents = 9900`,`currency = USD`,`method` 随机 `stripe` / `alipay` / `wechat`(`payment.js:45-72`)。

#### 步骤 3:Mock 支付触发

在浏览器 DevTools Console 执行:

```javascript
// 推当前订单到 success
const { setMockPaymentStatus } = await import('/src/api/payment.js')
setMockPaymentStatus('ORD-XXX', 'success')

// 也可直接推 failed / cancelled
setMockPaymentStatus('ORD-XXX', 'failed')      // 返 4020/4021
setMockPaymentStatus('ORD-XXX', 'cancelled')   // 取消
```

或者手工改 `localStorage`:

```javascript
// 直接覆写
const map = JSON.parse(localStorage.getItem('visa.payments') || '{}')
map['ORD-XXX'] = {
  ...map['ORD-XXX'],
  status: 'success',
  transaction_id: 'txn_demo_001',
  paid_at: new Date().toISOString(),
  estimated_processing_hours: 24
}
localStorage.setItem('visa.payments', JSON.stringify(map))
location.reload()  // 触发重新拉取
```

#### 步骤 4:Webhook 回调(后端集成测试用)

生产 / 集成测试场景,Stripe → 后端 webhook:

```bash
# Stripe 真接时(V2.1 阶段):
#   1. Stripe Dashboard 创建 webhook:https://dashboard.stripe.com/test/webhooks
#   2. URL 填:http://<your-host>/api/v2/payment/webhook
#   3. 监听事件:payment_intent.succeeded / payment_intent.payment_failed
#   4. 填 STRIPE_WEBHOOK_SECRET 到 backend/.env

# Dev 模式 mock:不需要 webhook,前端 setMockPaymentStatus 即模拟回调结果
```

后端 webhook 端点:`POST /api/v2/payment/webhook`(V2 §3.5.6),签名校验用 `STRIPE_WEBHOOK_SECRET`。

#### 步骤 5:状态更新

前端轮询拿到 `success` 后:

1. 跳 `/payment/result?order=ORD-XXX`(`PaymentResult.vue`)
2. 顶部显示绿色 ✓ 大圈 + "支付成功"
3. 下方显示 `transaction_id`(如 `txn_demo_001`)、`amount = $99.00`、`estimated_processing_hours = 24h`
4. 30s 后订单状态自动从 `paid` 推到 `rpa_processing`(`RpaSubmit.vue` 启动 RPA mock 任务)
5. 24h(实际 1-2min)后 RPA 任务完成,推到 `completed`

> 截图示例:`frontend/web/screenshots/payment_result_success.png` / `_failed.png` / `_pending.png`(W14-10 交付,3 张 PNG sha256 distinct 校验通过)

### 5.3 测试用例

| 场景 | Mock 操作 | 预期 |
| --- | --- | --- |
| 支付成功 | `setMockPaymentStatus(orderId, 'success')` | 跳 success 页,显示 txn_xxx |
| 支付失败 | `setMockPaymentStatus(orderId, 'failed')` | 跳 failed 页,显示 reason(`card_declined` / `insufficient_funds` / `network_error` / `expired_session`) |
| 支付取消 | `setMockPaymentStatus(orderId, 'cancelled')` | 跳 failed 页显示 "订单已取消" |
| 失败重试 | 跳 failed 页后点 "重试支付" → 调 `retryPayment` → 状态回 `pending` | 跳回 pending 页,继续轮询 |
| 取消后取消 | `cancelled` 状态再调 `cancelPayment` | 返 4020 错误码 |

---

## 6. iOS 端测试账号

> iOS 端走同后端 API(`http://127.0.0.1:8000`),账号与 Web 端完全互通。**iOS 没有 admin 端**(W6b 仅移植了 F1.7 login 页),所有 3 个普通用户 demo 账号同步使用。

### 6.1 入口与配置

| 项 | 值 |
| --- | --- |
| App 默认后端地址 | `http://127.0.0.1:8000`(`auth_service.dart:42`) |
| 自定义后端地址 | 启动时加 `--dart-define=API_BASE_URL=http://192.168.x.x:8000` |
| 模拟器 → 本机后端 | 用 `http://127.0.0.1:8000` 或 `http://localhost:8000` |
| 真机 → 本机后端 | 用 Mac IP,如 `http://192.168.1.100:8000`(Mac 防火墙需放行 8000 端口) |

### 6.2 测试流程

1. 启动后端:`cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. 启动 iOS 模拟器:`open -a Simulator && flutter run`
3. 在 Login 页填入 demo 账号(如 `13800138000 / demo1234`)
4. 跑完"选国家 → 拍照 → 创建订单 → 支付"完整流程
5. 用 Web 端 admin 账号登录后台,可看到 iOS 提交的订单

### 6.3 iOS 特有 mock

- 验证码 mock:任意 6 位数字都通过(参考 `Login.vue` mock 逻辑,iOS 端走相同后端)
- 支付 mock:Web 端 `setMockPaymentStatus` 不影响 iOS,iOS 端需用 `localStorage` 之外的等价机制(目前 iOS 未实现支付 mock 状态切换,演示需重新登录后从 0 开始)

---

## 7. 常见问题(FAQ)

### Q1. admin 登录失败,提示 "账号或密码错误"?

**A**:检查 3 处:

1. 后端 `.env` 第 70 行 `ADMIN_PASSWORD_SECRET` 是否为 `admin123`(本地 dev 默认值)
2. 前端是否走了 mock(`VITE_MOCK=true` 时前端硬编码 `admin/admin123`,不走后端)
3. 后端是否启动:`curl http://localhost:8000/api/v2/health` 返 200?

参考 `backend/app/services/admin_service.py:60-72`,逻辑:`admin_password_secret` > `admin_password` > `CHANGE_ME_IN_PROD`。**生产环境必须改 `ADMIN_PASSWORD_SECRET`**,否则任何人都能用 `CHANGE_ME_IN_PROD` 登录。

### Q2. token 过期怎么办?

**A**:

- **access token 过期**:`access_token` 默认 TTL 120 分钟(`backend/.env.example:19`)。前端 `http.js` 拦截器自动调 `/api/v2/auth/refresh` 拿新 token,无感刷新。
- **refresh token 过期**:`refresh_token` 默认 7 天。过期后前端自动 `logout()`,跳回 `/login`。
- **管理员 token 过期**:admin 独立 token(`create_admin_token`),目前**不支持 refresh**,过期后需重新登录(`/admin/login`)。

清 token:DevTools Console `localStorage.removeItem('visa.auth')` / `localStorage.removeItem('visa.admin.token')`。

### Q3. Mock 支付未触发 / 状态卡在 pending?

**A**:

1. **确认 mock 模式开启**:`VITE_MOCK !== 'false'`(默认就是 mock,见 `payment.js:17`)。如显式设 `VITE_MOCK=false`,需真实后端 + 真实支付渠道。
2. **检查 localStorage**:DevTools → Application → Local Storage → 看 `visa.payments` 是否有当前 `orderId` 的记录。
3. **手动触发**:

```javascript
// 拿 setMockPaymentStatus
const m = await import('/src/api/payment.js')
m.setMockPaymentStatus('ORD-XXX', 'success')
location.reload()
```

4. **iOS 端无 mock 工具**:iOS 没有等价 `setMockPaymentStatus`,需后端直接改 DB(`UPDATE orders SET status='paid' WHERE order_no='ORD-XXX'`)。

### Q4. 短信验证码收不到?

**A**:Mock 模式(`SMS_CHANNEL=mock`,默认)下,验证码直接返在 API 响应 `data.code` 字段,不真发短信。生产改 Twilio / 阿里云时参考 `backend/.env.example:28-35`。

调用 `POST /api/v2/auth/send-code` 看返回:

```json
{
  "code": "1000",
  "data": {
    "phone": "13800138000",
    "code": "482910",       ← mock 模式下这就是验证码
    "channel_txn_id": "mock_...",
    "expires_in": 300
  }
}
```

### Q5. 重置后 admin 登录 401?

**A**:重置 demo 数据**不会**改 admin 密码(密码在 `.env` 里,不在 DB)。如重置脚本误删了 `.env`,从 `.env.example` 重新复制,确认 `ADMIN_PASSWORD_SECRET=admin123`。

### Q6. 前端报错 "Network Error" / 后端 500?

**A**:

1. **后端没启动**:`lsof -i :8000` 看端口占用,启动 `uvicorn app.main:app --port 8000`
2. **数据库没初始化**:`rm -f backend/data/visa_mvp.db && cd backend && alembic upgrade head`
3. **CORS 问题**:dev 模式默认放行 `localhost:4173` / `localhost:4174` 等端口,如改端口需看 `app/main.py` 的 CORS 配置

### Q7. 截图 / 演示时如何快速到"已支付"状态?

**A**:用 admin 账号登录 → 用户管理 → 找到 demo_user_3 → 查看订单详情。demo_user_3(`13800138002`)的订单默认就是 `paid` 状态。或者重置后用 demo_user_3 登录,直接到 `/orders/:orderNo` 看完整时间线。

### Q8. iOS 端如何测"已支付"状态?

**A**:

1. 用 demo_user_3(`13800138002 / demo1234`)登录
2. iOS 端无 mock 支付,需后端直接改订单状态:

```sql
-- sqlite
sqlite3 backend/data/visa_mvp.db
UPDATE orders SET status = 'paid', paid_at = datetime('now') WHERE order_no = 'ORD-XXX';
```

3. 重启 iOS app,刷订单详情页

### Q9. 后端集成测试如何 mock 用户?

**A**:用 `backend/tests/conftest.py` 的 `app` fixture(自动建临时 sqlite + 跑 `create_all`)+ `client` fixture(httpx AsyncClient)。具体用例参考 `backend/tests/integration/test_w7_integration.py:159`(`phone = "13800138001"`)。

---

## 8. 附录:相关文件位置

| 文件 | 用途 |
| --- | --- |
| `backend/.env` | 后端环境变量,含 `ADMIN_PASSWORD_SECRET` |
| `backend/.env.example` | 环境变量模板 |
| `backend/app/services/admin_service.py` | admin 登录逻辑(60-103 行) |
| `backend/app/services/auth_service.py` | 普通用户注册 / 登录 |
| `backend/app/services/sms_service.py` | 短信发送(mock 模式直接返 code) |
| `backend/app/api/v2/admin.py` | admin API 端点(84-452 行) |
| `backend/app/api/v2/auth.py` | 用户 auth API 端点 |
| `backend/app/api/v2/payment.py` | 支付 API 端点(status / cancel / retry) |
| `frontend/web/src/api/admin.js` | 前端 admin API wrapper + mock |
| `frontend/web/src/api/auth.js` | 前端用户 auth API wrapper + mock |
| `frontend/web/src/api/payment.js` | 前端支付 API wrapper + mock(254 行) |
| `frontend/web/src/views/admin/AdminLogin.vue` | admin 登录页(预填 demo 在 156 行) |
| `frontend/web/src/views/Login.vue` | 用户登录页(预填 demo 在 362-367 行) |
| `frontend/web/src/views/PaymentResult.vue` | 支付结果页(648 行,4 态 + 30s 轮询) |
| `frontend/ios/lib/services/auth_service.dart` | iOS auth service |
| `docs/API.md` | 完整 API 文档(942 行) |
| `frontend/web/screenshots/payment_result_*.png` | 支付结果 3 态截图(W14-10) |

---

## 9. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-06-15 | 首次创建,汇总 W14-10 / W14-11 / W15-P0 demo 账号清单 |
