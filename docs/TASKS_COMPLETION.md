# 四大任务完成状态与操作指南

> 更新：2026-07-11 · 对应 W74 补充  
> **负责人当前待办（Stripe / Google / 域名 / 邮箱）**: 见 [`PRE_LAUNCH_OWNER_TODO.md`](PRE_LAUNCH_OWNER_TODO.md)

---

## 1. Google 鉴权登录

### 代码完成度：~95%

| 层级 | 状态 | 关键文件 |
|------|------|----------|
| 后端验签 + JWT | ✅ | `backend/app/api/v2/auth.py`, `auth_service.py` |
| Web GIS 按钮 | ✅ | `frontend/web/src/views/Login.vue`, `Register.vue` |
| iOS `google_sign_in` | ✅ | `frontend/ios/lib/pages/login_page.dart` |
| 测试 | ✅ 10+ cases | `backend/tests/test_auth_google.py` |

### 你还需做的（阻塞上线）

1. 打开 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. 创建 **OAuth 2.0 Client ID → Web application**
3. **Authorized JavaScript origins** 添加：
   - `http://localhost:5173`（开发）
   - 你的生产域名
4. 写入两个 env 并重启服务：

```bash
# backend/.env
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com

# frontend/web/.env
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
```

5. 验证：`pytest backend/tests/test_auth_google.py -v`

---

## 2. 支付与管理后台

### 代码完成度：~90%

| 模块 | 状态 | 说明 |
|------|------|------|
| Mock 支付 API | ✅ | `POST/GET /api/v2/payment/*` |
| Web 支付 checkout | ✅ **W74 新增** | `PaymentCheckout.vue` + `/payment/:orderNo` |
| 下单→支付串联 | ✅ **W74 新增** | `OrderNew.vue` 提交后跳转支付页 |
| 管理后台 API | ✅ | `admin.py` ~1183 行 |
| 管理后台 UI | ✅ | 18 个 Vue 页面 `/admin/*` |

### 本地验证

```bash
# 1. 启动后端 + 前端
cd backend && .venv/bin/uvicorn app.main:app --reload
cd frontend/web && npm run dev

# 2. 登录 → 下单 → 提交 → 应跳转到 /payment/V2-xxx
# 3. Mock 通道约 1s 后自动确认 → 跳转 RPA/预审页

# 4. 管理后台
open http://localhost:5173/admin/login
# 默认: admin / admin123 (仅 dev)
```

### 待完善

- 拒签后自动退款（audit 已知 gap）
- 生产环境管理员密码必须从 env 注入

---

## 3. Stripe 打通

### 代码完成度：~85%

| 模块 | 状态 | 说明 |
|------|------|------|
| `StripePaymentProvider` | ✅ | 5 方法全真接 |
| `payment_channel` 开关 | ✅ **W74 新增** | `PAYMENT_CHANNEL=mock\|stripe` |
| Stripe webhook | ✅ | `POST /api/v2/payment/notify` |
| Stripe notify → order.status | ✅ **W74 修复** | `created` → `submitted` |
| 前端 Stripe.js | ✅ **W74 新增** | `PaymentCheckout.vue` + `@stripe/stripe-js` |
| 支付配置 API | ✅ **W74 新增** | `GET /api/v2/payment/config` |

### 启用 Stripe（test mode）

```bash
# backend/.env
PAYMENT_CHANNEL=stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# frontend/web/.env (可选,也可从 /payment/config 读取)
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
```

### Webhook 配置

1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://your-api.com/api/v2/payment/notify`
3. Events: `payment_intent.succeeded`, `payment_intent.payment_failed`
4. 复制 Signing secret → `STRIPE_WEBHOOK_SECRET`

### 本地 webhook 测试

```bash
stripe listen --forward-to localhost:8000/api/v2/payment/notify
```

详细步骤见 [`docs/stripe-credentials-setup.md`](stripe-credentials-setup.md)。

---

## 4. 浏览器插件

### 代码完成度：~90%

| 模块 | 状态 | 说明 |
|------|------|------|
| MV3 扩展骨架 | ✅ | `browser-extension/manifest.json` v0.2 |
| 12 位 code 兑换 | ✅ | popup → `POST /ds160/code/redeem` |
| DS-160 填充引擎 | ✅ | `fillEngine.js` + `mapping.js` |
| 跨页进度追踪 | ✅ **W74 增强** | 进度条 + section 勾选 |
| API 地址可配置 | ✅ **W74 新增** | popup 可设 localhost / 生产 |

### 安装与测试

```bash
# 1. Chrome → chrome://extensions → 开发者模式 → 加载已解压的扩展
#    选择 browser-extension/ 目录

# 2. popup 里 API 地址填 http://localhost:8000

# 3. Htex 订单详情页生成 12 位 code → popup Redeem

# 4. 打开 ceac.state.gov → 登录自己的 DS-160 账号 → 面板自动出现
```

### 待验证（需真机）

- `DS160_MAPPING_VERIFIED_DATE = None` — 字段映射尚未对照真实 CEAC 表单核对
- 多申请人（目前只取 `applicants[0]`）
- 详见 `browser-extension/DS160_VERIFICATION_CHECKLIST.md`

---

## 快速启动检查清单

```
□ GOOGLE_CLIENT_ID + VITE_GOOGLE_CLIENT_ID 已填（如需 Google 登录）
□ PAYMENT_CHANNEL=mock（默认）或 stripe + 3 个 Stripe key
□ 后端 uvicorn 8000 + 前端 vite 5173 已启动
□ 插件 API 地址指向正确后端
□ pytest backend/tests/test_auth_google.py 通过
□ 下单 → 支付 → RPA 全流程走通
```

---

## 本次 W74 代码变更摘要

| 文件 | 变更 |
|------|------|
| `backend/app/core/config.py` | 加 `payment_channel`, `stripe_publishable_key` |
| `backend/app/services/payment_provider.py` | 工厂路由 + Stripe notify 更新 order.status |
| `backend/app/api/v2/payment.py` | `GET /payment/config` + create 返回 provider |
| `frontend/web/src/views/PaymentCheckout.vue` | 新建 Web 支付页 |
| `frontend/web/src/views/OrderNew.vue` | 提交后跳转支付 |
| `browser-extension/` | API 可配置 + 跨页进度条 |
