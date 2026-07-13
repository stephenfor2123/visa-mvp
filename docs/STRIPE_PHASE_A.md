# Stripe Phase A — Test Mode 接通指南

> **目标**: 用 Stripe **Test mode** 跑通「下单 → 填测试卡 → 订单变 paid」。  
> **不是**: Live 收真钱；也不是印尼/越南本地钱包（那是后续阶段）。

**代码已就绪（2026-07-13）**:
- `PAYMENT_CHANNEL=stripe` 路由到 `StripePaymentProvider`
- `POST /api/v2/payment/stripe-webhook`（验签 + 幂等）
- 前端 `PaymentCheckout.vue` Stripe Elements
- 无 webhook 时，`GET /payment/{order_no}` 也会从 Stripe 拉取并同步 paid

---

## 你需要做的（约 10 分钟）

### 1. 注册 / 登录 Stripe

- 注册: https://dashboard.stripe.com/register  
- API Keys（Test）: https://dashboard.stripe.com/test/apikeys  
- 右上角保持 **Test mode**（橙色）

### 2. 复制两个 Key 写入 `backend/.env`

```bash
PAYMENT_CHANNEL=stripe
STRIPE_SECRET_KEY=sk_test_……        # Secret key → Reveal
STRIPE_PUBLISHABLE_KEY=pk_test_……   # Publishable key
# STRIPE_WEBHOOK_SECRET=whsec_……    # 第 4 步再填（可暂空）
```

可选（前端直读公钥）`frontend/web/.env`:

```bash
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_……
```

> **不要把 key 发给任何人 / 不要 commit。** `.env` 已在 `.gitignore`。

### 3. 重启服务

```bash
# 后端
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# 前端
cd frontend/web && npm run dev
```

验证通道：

```bash
curl -s http://127.0.0.1:8000/api/v2/payment/config | python3 -m json.tool
# 期望: "channel": "stripe", "stripe_publishable_key": "pk_test_..."
```

### 4.（推荐）本地 Webhook — Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe
stripe login
stripe listen --forward-to localhost:8000/api/v2/payment/stripe-webhook
```

终端会打印 `whsec_…`，填入 `backend/.env` 的 `STRIPE_WEBHOOK_SECRET` 后重启后端。

Dashboard 永久 webhook（有公网域名后）:
- URL: `https://api.<域名>/api/v2/payment/stripe-webhook`
- Events: `payment_intent.succeeded`, `payment_intent.payment_failed`

### 5. 手测一笔

1. 打开 http://localhost:5173 → 登录 → 新建订单 → 提交  
2. 进入 `/payment/V2-…`，应看到 Stripe 卡表单  
3. 测试卡：

| 卡号 | 结果 |
|------|------|
| `4242 4242 4242 4242` | 成功 |
| 任意未来有效期 + 任意 CVC | |

4. 支付成功后订单应变 `paid` / `submitted`

---

## 完成标准（Phase A ✅）

- [ ] `GET /payment/config` 返回 `channel=stripe`
- [ ] Checkout 页出现 Stripe Elements（不是 Mock 自动确认）
- [ ] 测试卡 `4242…` 支付成功，订单状态更新
- [ ] （可选）`stripe listen` 收到 `payment_intent.succeeded`

---

## 切回 Mock

```bash
# backend/.env
PAYMENT_CHANNEL=mock
# 或留 stripe 但清空 STRIPE_SECRET_KEY → 自动回退 Mock
```

---

## 相关文件

| 文件 | 作用 |
|------|------|
| `backend/app/services/payment_provider.py` | StripePaymentProvider |
| `backend/app/api/v2/payment.py` | create / config / stripe-webhook |
| `frontend/web/src/views/PaymentCheckout.vue` | Stripe.js Elements |
| `docs/PRE_LAUNCH_OWNER_TODO.md` | 负责人总待办 |
| `docs/stripe-credentials-setup.md` | 早期 recipe（部分过时，以本文为准） |
