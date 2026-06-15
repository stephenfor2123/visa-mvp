# Stripe 凭据接入准备 (V2.1 阶段)

> **背景**: B-W10-4 producer 报告 "接真 SDK" 但 V2 仍 Mock-only (per Mavis 2026-06-12 10:54 decision: 支付全 Mock, 后期 V2.1 阶段再接)。V2 ships with `Mock` only, V2.1 wires real Stripe SDK。本文档写 V2.1 真接的 3 步走 recipe + macOS Keychain 接入路径。

## 1. 现状 (V2 阶段, B-W11-2 修整后)

`backend/app/core/config.py` 已加 3 个占位字段:
```python
stripe_secret_key: str = ""           # V2 = ""  (V2.1 = "sk_test_xxx")
stripe_webhook_secret: str = ""       # V2 = ""  (V2.1 = "whsec_xxx")
stripe_payout_account_id: str = ""    # V2 = ""  (V2.1 = "acct_xxx")
```

`backend/app/services/payment_provider.py::StripePaymentProvider` 已完整实现 5 个方法 (`create_order` / `query_order` / `handle_notify` / `close_order` / `payout`), 通过 `_require_stripe()` gate:

- **V2 状态 (key 空)**: `self.stripe = None`, 5 个方法均 raise `NotImplementedError("V2.1 阶段接真 SDK")`, **零网络调用**, **零凭据**。
- **V2.1 状态 (key 非空)**: `self.stripe = stripe` (SDK bound), 5 个方法真调 `stripe.PaymentIntent.create_async` / `stripe.Webhook.construct_event` / `stripe.Transfer.create_async` 等。

**B-W11-2 修整 #5** — `_FakeSettings` 修整: W10-4 producer 写完 SDK 调用但 test `test_payment_stripe_stub.py` 的 `_FakeSettings` 只 mock 了 `stripe_secret_key` 1 个字段, 实际 `__init__` 要读 3 个字段。**修整**: test `_FakeSettings` 补齐 `stripe_webhook_secret` + `stripe_payout_account_id` 2 字段 (`1/1 PASS in 0.92s`)。

## 2. V2.1 真接 3 步走

### Step 1 — 申请 Stripe 账号 (test mode 优先)

1. 访问 https://dashboard.stripe.com/register 注册
2. **先用 Test Mode** — 顶部 toggle 切到 "Test mode" (避免真扣款)
3. 拿 3 个 key:
   - `STRIPE_SECRET_KEY` → Developers → API keys → `Secret key` (test mode 下是 `sk_test_xxx`)
   - `STRIPE_WEBHOOK_SECRET` → Developers → Webhooks → Add endpoint → 选 `payment_intent.succeeded` + `payment_intent.payment_failed` events → 拿 `Signing secret` (是 `whsec_xxx`)
   - `STRIPE_PAYOUT_ACCOUNT_ID` → Connect → Accounts → 创建一个 Connected account → 拿 `acct_xxx` (用于 affiliate partner payout)

### Step 2 — 凭据落盘 (3 种方式, 推荐 macOS Keychain)

#### 方式 A — `.env` 文件 (本地 dev 友好, 不推荐 prod)

```bash
# backend/.env (gitignored)
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PAYOUT_ACCOUNT_ID=acct_xxx
```

**警告**: `.env` 进 `.gitignore`, 永不 commit 真 key。CI/CD 用 secret manager (GitHub Actions secrets / GitLab CI variables)。

#### 方式 B — macOS Keychain (推荐, B-W11-2 修整 #4 推荐)

```bash
# 写入 Keychain (一次性)
security add-generic-password -s visa-mvp-stripe \
  -a STRIPE_SECRET_KEY -w 'sk_test_xxx'
security add-generic-password -s visa-mvp-stripe \
  -a STRIPE_WEBHOOK_SECRET -w 'whsec_xxx'
security add-generic-password -s visa-mvp-stripe \
  -a STRIPE_PAYOUT_ACCOUNT_ID -w 'acct_xxx'

# 启动时读取 (写一个 _launch_keychain.sh)
#!/bin/bash
export STRIPE_SECRET_KEY=$(security find-generic-password -s visa-mvp-stripe -a STRIPE_SECRET_KEY -w)
export STRIPE_WEBHOOK_SECRET=$(security find-generic-password -s visa-mvp-stripe -a STRIPE_WEBHOOK_SECRET -w)
export STRIPE_PAYOUT_ACCOUNT_ID=$(security find-generic-password -s visa-mvp-stripe -a STRIPE_PAYOUT_ACCOUNT_ID -w)
.venv/bin/python _launch_uvicorn.py
```

**修整优势**: key 永不落明文磁盘, 仅在 launch 时注入 env, 进程结束清零。MacBook 丢了也安全 (Keychain 需 user 密码或 Touch ID 解锁)。

#### 方式 C — 1Password CLI / Vault (prod 友好)

```bash
# 1Password CLI
op read "op://Vault/visa-mvp-stripe/STRIPE_SECRET_KEY"
```

```bash
# HashiCorp Vault
vault kv get -field=STRIPE_SECRET_KEY secret/visa-mvp/stripe
```

### Step 3 — 切换 channel (V2.1 阶段, W12+ Story)

B-W11-2 修整留 W12+ 实现: 加 `payment_channel: Literal["mock", "stripe"]` 配置, `get_payment_provider()` 根据 channel 返回 Mock 或 Stripe 实例。

```python
# W12+ 实现 sketch
def get_payment_provider() -> PaymentProvider | StripePaymentProvider:
    settings = get_settings()
    if settings.stripe_secret_key and settings.payment_channel == "stripe":
        return StripePaymentProvider()
    return PaymentProvider()  # V2 Mock
```

## 3. Webhook 端点配置 (handle_notify 修整)

Stripe webhook 必须验签 (`Stripe-Signature` header) 否则任何人都可以伪造 paid 事件。V2.1 修整:

```python
# backend/app/api/v2/payment.py (W12+ 加 endpoint)
@router.post("/payment/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = get_settings().stripe_webhook_secret
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    # 调 StripePaymentProvider.handle_notify
    ...
```

`STRIPE_WEBHOOK_SECRET` 修整: V2.1 必填, 空时 V2.1 deployment 启动 fail-fast (建议 `Settings` validator 强制)。

## 4. 修整 V2 验证 (V2 ships credential-free)

B-W11-2 修整 #5 实测:
```bash
$ .venv/bin/pytest tests/integration/test_payment_stripe_stub.py -v
# 1 passed in 0.92s
```

修整 PASS 条件:
- V2 启动时 `get_settings().stripe_secret_key == ""`  (zero creds)
- V2 `StripePaymentProvider()` 构造后 `self.stripe is None`
- V2 调任何 method raise `NotImplementedError("V2.1 阶段接真 SDK")`
- V2.1 配 key 后 `self.stripe` 绑定, `_require_stripe()` 不 raise

## 5. W12+ 修整 (V2.1 真接 checklist)

V2.1 阶段建议拆 3 个 Story:
- **W12-V2.1-A**: 注册 Stripe test account, 拿 3 key, 落 Keychain (用方式 B)
- **W12-V2.1-B**: 加 `payment_channel` config + factory 切换, 修整 webhook 端点 + signature 验签
- **W12-V2.1-C**: E2E testmode — `POST /payment/create` → 拿 `client_secret` → Stripe.js confirm → webhook 验签 → 状态 `paid`

B-W11-2 修整 #4: V2.1 凭据接入准备 recipe 文档化 (本文件), V2 阶段零凭据, 修整 #5 (test 1/1 PASS)。

---

**V2.1 接入判定**: B-W11-2 修整 #4 完成 (recipe 文档 + macOS Keychain 路径), V2 仍 Mock (修整 #5 test PASS), V2.1 真接留 W12+ Story。
