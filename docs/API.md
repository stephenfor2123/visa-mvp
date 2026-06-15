# Visa Helper V2 — API Reference

> 基于 `backend/app/api/v2/` (commit 2026-06-14) 整理，覆盖所有 REST 端点 + WebSocket。
> 对应前端 `frontend/web/src/api/` 模块。

---

## 1. 概述

- **Base URL**：`/api/v2`
- **协议**：REST + JSON
- **开发环境**：Vite 代理 `/api` → `http://127.0.0.1:8000`，无需 CORS 配置
- **Mock 模式**：前端 `VITE_MOCK !== 'false'` 时使用 localStorage mock 数据（Affiliate 除外）
- **支付 / 保险 / RPA**：V2 当前为 Mock-only，V2.1 替换真实渠道适配器即可，无需改动端点

---

## 2. 通用约定

### 2.1 统一响应包装（ApiResponse）

所有端点（无论成功/错误）返回如下包装结构：

```json
{
  "code": "1000",
  "message": "OK",
  "data": { ... }
}
```

- `code === "1000"` 表示成功
- `code !== "1000"` 表示业务错误，具体含义见 [§5 错误码](#5-错误码)
- `data` 在错误时为 `{}`（空对象），具体数据放在 `data` 字段中

### 2.2 分页格式

列表类端点（`list_*`）统一返回：

```json
{
  "items": [...],
  "page": 1,
  "page_size": 20,
  "total": 42,
  "total_pages": 3
}
```

### 2.3 日期时间

- 所有 `*_at` 字段为 **naive UTC**：`"2026-06-14T08:30:00"`
- 金额单位：**分（cents）**，整数，不使用浮点

---

## 3. 认证方式

### 3.1 C 端用户 — JWT Bearer Token

```http
Authorization: Bearer <access_token>
```

- `access_token` 在登录/注册成功后颁发
- 有效期：默认 3600 秒（1 小时）
- Token 存储在前端 `localStorage`：`visa.auth.accessToken`
- 过期后自动 401 → 拦截器弹出"登录已过期，请重新登录"
- 续期：调用 `POST /api/v2/auth/refresh`，携带 `refresh_token`

### 3.2 Admin 端 — 独立 JWT

```http
Authorization: Bearer <admin_access_token>
```

- 独立存储：`localStorage.admin_token`
- 与 C 端 token 完全隔离，不共享
- Admin 登录：`POST /api/v2/admin/login`

### 3.3 内部系统端 — X-System-Key

```http
X-System-Key: <SYSTEM_API_KEY env var>
```

- 仅供内部 cron / scheduler 调用
- 端点：`POST /scheduler/poll-tick`

### 3.4 Partner 端 — X-Partner-Key

```http
X-Partner-Key: <SYSTEM_API_KEY env var>
```

- 端点：`GET /api/v2/affiliate/{partner_id}/stats`

### 3.5 WebSocket — JWT Query Param

```javascript
ws://host/ws/orders/{order_no}?token=<access_token>
```

- `token` 参数传递 access_token

---

## 4. 端点总览

### 4.1 Auth（`/api/v2/auth`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/register` | — | 注册（手机+密码+短信验证码） |
| POST | `/login` | — | 密码登录 |
| POST | `/sms-login` | — | 短信验证码登录（自动注册） |
| POST | `/refresh` | — | 刷新 token |
| POST | `/send-code` | — | 发送短信验证码（Mock: 直接返回 code） |
| POST | `/reset-password` | — | 通过验证码重置密码 |

#### POST `/register`

**Request**
```json
{
  "phone": "13800138000",
  "phone_country": "+86",
  "password": "Test123456",
  "sms_code": "123456",
  "nickname": "张三",
  "language_pref": "zh-CN"
}
```

**Response** `201`
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": 1,
      "uuid": "...",
      "phone": "13800138000",
      "phone_country": "+86",
      "nickname": "张三",
      "language_pref": "zh-CN",
      "status": "active",
      "created_at": "2026-06-14T08:30:00"
    }
  }
}
```

#### POST `/login`

**Request**
```json
{
  "phone": "13800138000",
  "phone_country": "+86",
  "password": "Test123456"
}
```

#### POST `/sms-login`

**Request**
```json
{
  "phone": "13800138000",
  "phone_country": "+86",
  "sms_code": "123456"
}
```

#### POST `/refresh`

**Request**
```json
{
  "refresh_token": "eyJ..."
}
```

#### POST `/send-code`

**Request**
```json
{
  "phone": "13800138000",
  "phone_country": "+86",
  "purpose": "login"
}
```
`purpose` 可选值：`register` | `login` | `reset` | `destroy`

> Mock 模式：验证码直接在响应 `data.code` 中返回，便于测试。

#### POST `/reset-password`

**Request**
```json
{
  "phone": "13800138000",
  "phone_country": "+86",
  "sms_code": "123456",
  "new_password": "NewPass123"
}
```

---

### 4.2 Orders（`/api/v2/orders`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/` | JWT | 创建订单 |
| GET | `/` | JWT | 用户订单列表（分页） |
| GET | `/{order_no}` | JWT | 订单详情 + ETag |
| GET | `/{order_no}/checklist` | JWT | 提交前锁定快照（含 signature） |
| POST | `/{order_no}/cancel` | JWT | 取消订单（仅 created 态） |
| POST | `/{order_no}/submit` | JWT | 提交订单触发 RPA（需 signature） |

> **ETag 支持**：GET `/{order_no}` 支持 `If-None-Match` 条件请求，减少无效轮询。

#### POST `/`

**Request**
```json
{
  "destination_id": 1,
  "visa_type": "tourism",
  "material_ids": [101, 102],
  "applicant_data": {
    "surname": "SANTOSO",
    "given_name": "BUDI",
    "dob": "1990-05-12",
    "passport_no": "E12345678"
  },
  "aff_code": "AFF001"
}
```

**Response** `201`
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "order": { ... },
    "order_no": "V2-20260614-000001",
    "status": "created"
  }
}
```

#### GET `/{order_no}` — ETag 示例

```http
GET /api/v2/orders/V2-20260614-000001
If-None-Match: "abc123def..."
```

**304 Not Modified** — 内容未变，复用本地缓存
**200 OK** — 响应头含 `ETag: "..."` 和 `Cache-Control: private, max-age=5`

#### POST `/{order_no}/submit` — signature 流程

1. 调用 `GET /{order_no}/checklist`，获取 `signature`（SHA-256 锁定快照）
2. 调用 `POST /{order_no}/submit`，body 中回传 `signature`

```json
{
  "signature": "a1b2c3...64chars"
}
```

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "order_no": "V2-20260614-000001",
    "status": "submitted",
    "submitted_at": "2026-06-14T09:00:00",
    "rpa_task_id": "..."
  }
}
```

---

### 4.3 Payment（`/api/v2/payment`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/create` | JWT | 创建支付订单（Mock: 1s 后自动变成 paid） |
| POST | `/notify` | — | 支付回调（Mock 自调用；V2.1 是 WxPay/Stripe webhook） |
| GET | `/{order_no}` | JWT | 查询支付状态 |
| POST | `/{order_no}/close` | JWT | 关闭未支付订单（pending→closed） |

#### POST `/create`

**Request**
```json
{
  "order_no": "V2-20260614-000001",
  "amount_cents": 9900,
  "currency": "USD",
  "desc": "Visa Application Fee"
}
```

**Response** `201`
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "order_no": "V2-20260614-000001",
    "trade_no": "MOCK-...",
    "code_url": "weixin://wxpay/bizpayurl?pr=MOCKxxx",
    "prepay_id": "...",
    "expired_at": "2026-06-14T09:30:00",
    "amount_cents": 9900,
    "currency": "USD",
    "auto_notify_in_seconds": 1.0
  }
}
```

#### GET `/{order_no}`

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "order_no": "V2-20260614-000001",
    "trade_no": "MOCK-...",
    "status": "paid",
    "paid_at": "2026-06-14T09:01:00",
    "amount_cents": 9900,
    "currency": "USD"
  }
}
```

`status` 取值：`none` | `pending` | `paid` | `closed` | `failed`

---

### 4.4 Materials（`/api/v2/materials`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/upload` | JWT | 上传材料（multipart/form-data） |
| GET | `/{material_id}` | JWT | 获取材料详情（含 OCR 结果） |
| GET | `/{material_id}/download` | JWT | 获取 5 分钟有效期下载链接 |
| DELETE | `/{material_id}` | JWT | 软删除 |
| POST | `/validate` | JWT | 运行 15+ 验证规则 |
| GET | `/_local/{token}` | — | 内部：用签名 URL 提供文件（无 Auth） |

#### POST `/upload`

`Content-Type: multipart/form-data`

| 表单字段 | 类型 | 必填 | 说明 |
|----------|------|------|------|
| `file` | File | ✅ | 图片或 PDF |
| `material_type` | string | ✅ | passport / id_card / household / enrollment / photo / form / other |
| `order_no` | string | ❌ | 关联的订单号 |

**Response** `201`
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "material": { "id": 101, "material_type": "passport", ... },
    "deduplicated": false,
    "download_url": "/api/v2/materials/_local/xxx?key=...",
    "thumbnail_url": "/api/v2/materials/_local/yyy?key=..."
  }
}
```

#### POST `/validate`

**Request**
```json
{
  "material_ids": [101, 102],
  "fields": ["passport_no", "surname", "dob"]
}
```

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "overall": "pass",
    "issues": [
      { "material_id": 101, "code": "PASSPORT_NO_FORMAT", "severity": "error", "field": "passport_no" },
      { "material_id": 101, "code": "IMAGE_BLUR", "severity": "warning", "field": "image" }
    ],
    "rule_count": 15,
    "materials_checked": 2,
    "fields_checked": 3
  }
}
```

`overall` 取值：`pass` | `warning` | `error`

---

### 4.5 Destinations（`/api/v2/destinations`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| GET | `/` | — | 国家/地区列表（V2: 仅美国 enabled=true） |

**Query 参数**
- `lang`：返回国家名的语种，`zh-CN` | `en` | `id` | `vi`（默认 `zh-CN`）
- `visa_type`：按签种过滤，`tourism` | `student`

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": [
    {
      "id": 1,
      "country_code": "US",
      "country_name": "美国",
      "visa_types": ["tourism", "student"],
      "image_url": "https://...",
      "enabled": true
    }
  ]
}
```

---

### 4.6 OCR（`/api/v2/ocr`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/recognize` | JWT | OCR 识别（护照字段提取） |

`Content-Type: multipart/form-data`

| 字段 | 说明 |
|------|------|
| `file` | 图片文件（JPG/PNG/WebP/PDF） |
| `lang` | OCR 语言：`en`（默认）\| `zh-CN` \| `id` \| `vi` |

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "items": [{ "text": "...", "bbox": [[x,y],[x,y]...], "confidence": 0.92 }],
    "fields": {
      "passport_no": "E12345678",
      "surname": "SANTOSO",
      "given_name": "BUDI",
      "dob": "1990-05-12",
      "expiry": "2031-08-22"
    },
    "lang": "en"
  }
}
```

---

### 4.7 Voice（`/api/v2/voice`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| GET | `/config` | — | 查询支持语言和音频限制 |
| POST | `/recognize` | JWT | 语音识别 + 结构化字段提取 |

#### GET `/config`

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "supported_langs": ["zh-CN", "en", "id", "vi"],
    "min_audio_bytes": 1024,
    "max_audio_bytes": 5242880,
    "active_engine": "mock"
  }
}
```

#### POST `/recognize`

`Content-Type: multipart/form-data`

| 字段 | 说明 |
|------|------|
| `file` | 音频文件（WAV/MP3/OGG/FLAC/MP4/WebM） |
| `lang` | 识别语言：`en`（默认）\| `zh-CN` \| `id` \| `vi` |

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "name": "John Smith",
    "address": "100 Main Street New York",
    "travel_date": "2026-08-15",
    "raw_text": "My name is John Smith...",
    "lang": "en",
    "confidence": 0.93,
    "engine": "mock",
    "mime_type": "audio/webm",
    "elapsed_ms": 380
  }
}
```

---

### 4.8 Admin（`/api/v2/admin`）

> 全部需要 `Authorization: Bearer <admin_token>`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/login` | Admin 登录 |
| GET | `/users` | 用户列表（分页） |
| GET | `/users/{user_id}` | 用户详情 |
| DELETE | `/users/{user_id}` | 软删除用户 |
| GET | `/orders` | 订单列表（分页，支持 status/user_id 过滤） |
| GET | `/orders/{order_id}` | 订单详情 |
| PUT | `/orders/{order_id}/status` | 修改订单状态 |
| GET | `/config/countries` | 国家配置列表 |
| POST | `/config/countries` | 新增国家 |
| PUT | `/config/countries/{country_id}` | 更新国家 |
| DELETE | `/config/countries/{country_id}` | 下线国家 |
| GET | `/config/validation-rules` | AI 验证规则列表 |
| PUT | `/config/validation-rules` | 更新验证规则 |
| GET | `/config/rpa` | 读取 RPA 配置 |
| PUT | `/config/rpa` | 更新 RPA 配置 |
| GET | `/stats/rpa` | 实时 RPA 统计 |
| GET | `/logs` | 审计日志（分页） |

#### POST `/login`

**Request**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response**
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

---

### 4.9 Affiliate（`/api/v2/affiliate`）

> 前 4 个端点：JWT；`/{partner_id}/stats`：X-Partner-Key

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/track` | JWT | 记录推广链接点击 |
| POST | `/attribute` | JWT | 将订单绑定到点击 |
| GET | `/commission/{order_id}` | JWT | 查询订单佣金（V2: 5%） |
| POST | `/payout` | JWT | 结算 Partner（管理员操作） |
| GET | `/{partner_id}/stats` | X-Partner-Key | Partner 视角统计 |

#### POST `/track`

**Request**
```json
{
  "aff_code": "AFF001",
  "click_id": "clk_xxx",
  "landing_path": "/register"
}
```

#### GET `/commission/{order_id}`

**Query 参数**：`order_total_cents`（可选，用于重新计算）

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "order_id": "V2-20260614-000001",
    "commission_id": "...",
    "commission_amount_cents": 495,
    "commission_rate": 0.05,
    "currency": "USD",
    "partner_id": "AFF001",
    "computed_at": "2026-06-14T09:00:00"
  }
}
```

---

### 4.10 Insurance（`/api/v2/insurance`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/quote` | JWT | 生成报价（Mock: 5% 保费） |
| POST | `/bind` | JWT | 将报价绑定为保单 |
| POST | `/claim` | JWT | 提交拒签理赔（Mock: 总是 approved） |
| GET | `/{policy_id}` | JWT | 查询保单/理赔状态 |

#### POST `/quote`

**Request**
```json
{
  "order_id": "V2-20260614-000001",
  "applicant_age": 30,
  "destination_country": "US"
}
```

**Response**
```json
{
  "code": "1000",
  "message": "OK",
  "data": {
    "quote_id": "...",
    "policy_no": "INS-MOCK-001",
    "premium_cents": 495,
    "coverage_cents": 9900,
    "currency": "USD",
    "created_at": "2026-06-14T09:00:00"
  }
}
```

---

### 4.11 RPA（`/api/v2/rpa`）

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/submit` | X-User-ID header | 触发 RPA 提交 |
| GET | `/status/{task_id}` | — | 查询任务状态 |
| POST | `/cancel/{task_id}` | — | 取消任务 |
| GET | `/config` | — | 获取 RPA 配置 |
| PUT | `/config` | X-Admin-Token header | 更新 RPA 配置 |
| GET | `/tasks` | X-User-ID header | 任务列表 |

#### POST `/submit`

**Request**
```json
{
  "order_id": "V2-20260614-000001",
  "country_code": "ID",
  "visa_type": "visit_visa",
  "passport_data": {
    "surname": "SANTOSO",
    "given_name": "BUDI",
    "dob": "1990-05-12",
    "passport_no": "E12345678"
  }
}
```

**Response**
```json
{
  "code": "1000",
  "message": "RPA task created",
  "data": {
    "task_id": "rpa_abc123",
    "order_id": "V2-20260614-000001",
    "status": "SUBMITTING",
    "message": "Task queued"
  }
}
```

---

### 4.12 SMS（`/api/v2/sms`）

> Standalone 端点（与 `/api/v2/auth/send-code` 并存），V2.1 接入腾讯云后对前端无感知。

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/send` | — | 发送验证码 |
| POST | `/verify` | — | 验证并返回 JWT |
| GET | `/{message_id}` | — | 查询发送状态 |
| POST | `/template` | — | 注册模板（Mock-only） |

---

### 4.13 WebSocket（`/ws/orders/{order_no}`）

- **认证**：`?token=<access_token>` query 参数
- **心跳**：服务器每 30s 发送 `{"type":"ping","ts":...}`；60s 无响应则关闭
- **推送消息类型**：
  - `{"type":"ready","data":{"order_no":"..."}}` — 连接成功时立即发送
  - `{"type":"status","data":{...order object...}}` — 状态变更
  - `{"type":"rpa_screenshot","data":{"url":"..."}}` — RPA 截图推送
  - `{"type":"ping","ts":...}` — 心跳

**前端接入示例**（`frontend/web/src/api/orders.js` 中 `pollOrderStatus` 函数）：

```javascript
const WS_BASE = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
const url = `${WS_BASE}/ws/orders/${orderNo}?token=${accessToken}`
const ws = new WebSocket(url)
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.type === 'status') onUpdate(msg.data, 'ws')
}
```

---

## 5. 错误码

| code | HTTP 状态 | 说明 |
|------|----------|------|
| `1000` | 200 | 成功 |
| `1001` | 400 | 参数无效 |
| `1002` | 400 | 缺少必填字段 |
| `1003` | 400 | 格式错误 |
| `1004` | 404 | 资源不存在 |
| `1005` | 401 | 未认证 / token 无效 |
| `1006` | 403 | 无权限 |
| `1007` | 409 | 冲突（如手机号已注册） |
| `1009` | 429 | 频率限制 |
| `1010` | 500 | 服务器内部错误 |
| `2001` | 401 | 账号或密码错误 |
| `2002` | 422 | 验证码错误 |
| `2003` | 409 | 用户已存在 |
| `2004` | 422 | 密码强度不足 |
| `2005` | 403 | 账号已禁用 |
| `2006` | 401 | refresh_token 无效 |
| `2007` | 401 | refresh_token 过期 |
| `2008` | 422 | 验证码已过期 |
| `2009` | 422 | 验证码已使用 |
| `2010` | 429 | 短信频率限制 |
| `3001` | 404 | 用户不存在 |
| `3002` | 409 | 昵称已被占用 |
| `4001` | 404 | 订单不存在 |
| `4002` | 409 | 订单不可取消（状态非 created） |
| `4003` | 400 | 签种无效 |
| `4004` | 400 | 目的地未开放 |
| `4005` | 400 | 材料不存在 |
| `4006` | 403 | 无权访问该材料 |
| `4007` | 409 | 订单已存在 |
| `4008` | 409 | 订单状态无效 |
| `4009` | 500 | 创建订单失败 |
| `4010` | 409 | 订单不可编辑（状态非 created） |
| `4011` | 400 | 提交签名不匹配 |
| `4012` | 404 | 支付记录不存在 |
| `4013` | 409 | 支付已完成，不可关闭 |
| `4014` | 400 | 支付金额必须 > 0 |
| `7001` | 502 | SMS 网关不可用 |
| `2003` | 400 | 语音音频格式错误（VOICE_AUDIO_FORMAT）|
| `2004` | 422 | 语音识别失败（VOICE_RECOGNIZE_FAILED）|
| `2005` | 504 | 语音超时（VOICE_TIMEOUT）|

---

## 6. 前端集成指南

### 6.1 HTTP 层

`src/api/http.js` 配置 Axios 实例：

- **Base URL**：`/api`（Vite 开发代理 → 后端 8000 端口）
- **超时**：15000ms
- **请求拦截器**：自动附加 `Authorization: Bearer <access_token>`
- **响应拦截器**：返回 `resp.data`（解一层包装）；401 → 自动 logout

### 6.2 API 模块对照

| 前端模块 | 后端域 | 端点 |
|----------|--------|------|
| `src/api/auth.js` | Auth | `/v2/auth/*` |
| `src/api/orders.js` | Orders | `/v2/orders*` |
| `src/api/payment.js` | Payment | `/v2/payment*` |
| `src/api/materials.js` | Materials | `/v2/materials*` |
| `src/api/destinations.js` | Destinations | `/v2/destinations` |
| `src/api/voice.js` | Voice | `/v2/voice*` |
| `src/api/affiliate.js` | Affiliate | `/v2/affiliate*` |
| `src/api/rpa.js` | RPA | `/v2/rpa*` |
| `src/api/admin.js` | Admin | `/v2/admin*` |

### 6.3 Mock 切换

```bash
# 真后端联调
VITE_MOCK=false npm run dev

# Mock 模式（默认）
VITE_MOCK=true npm run dev
```

> **注意**：`src/api/affiliate.js` 中 `USE_REAL = true` 硬编码，忽略 `VITE_MOCK`，因为 Affiliate 是 V2 新服务，Mock 数据不存在。

### 6.4 前端调用示例

```javascript
import http from '@/api/http'
import { useAuthStore } from '@/stores/auth'

// 登录
const { data } = await http.post('/v2/auth/login', {
  phone: '13800138000',
  phone_country: '+86',
  password: 'Test123456'
})
// http.js 拦截器已解包 → data = { code, message, data: TokenPair }
const { access_token, refresh_token } = data.data
useAuthStore().setToken(access_token, refresh_token)

// 查询订单
const env = await http.get('/v2/orders/V2-20260614-000001')
const order = env.data

// 条件 GET（ETag）
const resp = await http.get(`/v2/orders/${orderNo}`, {
  headers: { 'If-None-Match': currentEtag },
  __silent: true  // 不弹 toast
})

// 上传文件
const form = new FormData()
form.append('file', file)
form.append('material_type', 'passport')
const { data: uploadResult } = await http.post('/v2/materials/upload', form, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
```

### 6.5 订单状态 WebSocket 订阅

```javascript
import { pollOrderStatus } from '@/api/orders'

const stop = pollOrderStatus(orderNo, (order, source) => {
  // source = 'ws' | 'ws-screenshot' | 'polling' | 'polling-same' | 'ws-mock'
  console.log(`[${source}] order status:`, order.status)
}, { intervalMs: 30000 })

// 组件卸载时必须调用
onUnmounted(stop)
```

---

## 7. Pre-existing Issues（已知问题）

> 以下问题在本次文档整理中发现，记录于此，不在本任务范围内修复。

### 7.1 Payment 端点路径不一致（前端 vs 后端）

**现象**：`src/api/payment.js` 调用：
- `GET /v2/payment/status/{orderId}` — 前端
- `POST /v2/payment/cancel/{orderId}` — 前端
- `POST /v2/payment/retry/{orderId}` — 前端

**实际后端**：
- `POST /v2/payment/create` — 创建支付
- `GET /v2/payment/{order_no}` — 查询状态
- `POST /v2/payment/{order_no}/close` — 关闭订单

**影响**：真后端模式下支付相关功能（轮询结果页、重试、取消）会 404。

**建议**：`payment.js` 中的 `queryPaymentStatus` / `cancelPayment` / `retryPayment` 路径需对齐后端（`{order_no}` 而非 `{orderId}`，`/close` 而非 `/cancel/{orderId}`）。

### 7.2 Admin `/profile` 端点不存在

**现象**：`src/api/admin.js` 调用 `GET /v2/admin/profile`，但 `backend/app/api/v2/admin.py` 中无此端点。

**影响**：真后端模式下获取 Admin 个人信息会 404。

**建议**：在 `admin.py` 补充 `GET /admin/profile` 端点，或由 `adminLogin` 返回完整 profile 数据。

### 7.3 RPA `/submit` 请求体不匹配

**现象**：前端 `src/api/rpa.js` 发送 `{ order_no: orderNo }`，后端 `rpa.py` 期望 `{ order_id, country_code, visa_type, passport_data }`。

**影响**：真后端模式下 RPA 提交会因缺少必填字段而失败（4001/1002）。

### 7.4 Affiliate mock 硬编码

**现象**：`src/api/affiliate.js` 第 22 行 `const USE_REAL = true` 硬编码，忽略 `VITE_MOCK` 环境变量。

**影响**：Mock 模式下 Affiliate 仍走真后端请求（网络错误时静默降级到 localStorage）。

---

## 8. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE` | API Base URL | `/api` |
| `VITE_MOCK` | Mock 模式开关 | `true` |
| `VITE_WS_URL` | WebSocket Base URL（可选） | 同源（`ws://host`）|
