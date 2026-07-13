# 上线前负责人待办（Owner Action Items）

> **记录日期**: 2026-07-11  
> **状态**: 进行中 — 以下四项为**当前必须由负责人处理**的外部配置，代码侧已就绪，缺凭据/基础设施无法对外发布。

---

## 总览

| # | 事项 | 阻塞功能 | 代码状态 | 负责人动作 |
|---|------|----------|----------|------------|
| 1 | **Stripe** | 真支付（目前仅 Mock） | ✅ 已接 | 申请 test/live keys + webhook |
| 2 | **Google 鉴权** | Google 登录按钮 | ✅ 已接 | 创建 OAuth Client + 填 env |
| 3 | **域名** | 生产访问、OAuth 回调、邮件链接、API/CORS | ⏳ 待定 | 购买/解析域名 + 配 HTTPS |
| 4 | **邮箱** | 注册欢迎信、找回密码、隐私联系 | ⏳ stub | 企业邮箱 + SMTP/Resend + 隐私邮箱 |

---

## 1. Stripe

**阶段**: **A = Test mode 接通**（当前）→ 以后再考虑 Live / 本地钱包

**目标**: 从 `PAYMENT_CHANNEL=mock` 切到 Stripe **Test**（`sk_test_` / `pk_test_`）。

### 待办

- [ ] Stripe Dashboard 注册 + 保持 **Test mode**
- [ ] 获取并填入 `backend/.env`：
  - `PAYMENT_CHANNEL=stripe`
  - `STRIPE_SECRET_KEY`（`sk_test_…`）
  - `STRIPE_PUBLISHABLE_KEY`（`pk_test_…`）
  - `STRIPE_WEBHOOK_SECRET`（`whsec_…`，用 Stripe CLI 拿）
- [ ] Webhook（本地）:
  ```bash
  stripe listen --forward-to localhost:8000/api/v2/payment/stripe-webhook
  ```
- [ ] 手测: 测试卡 `4242 4242 4242 4242` 支付成功

### 参考

- **Phase A 操作指南**: [`docs/STRIPE_PHASE_A.md`](STRIPE_PHASE_A.md)
- 旧 recipe: [`docs/stripe-credentials-setup.md`](stripe-credentials-setup.md)
- 代码: `backend/app/services/payment_provider.py`, `frontend/web/src/views/PaymentCheckout.vue`
- Webhook 路由: `POST /api/v2/payment/stripe-webhook`

---

## 2. Google 鉴权

**目标**: 登录/注册页显示「Continue with Google」并走后端 JWT 流程。

### 待办

- [ ] [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 Client ID → **Web application**
- [ ] **Authorized JavaScript origins** 添加：
  - `http://localhost:5173`（开发）
  - `https://<你的生产域名>`（域名确定后补）
- [ ] **Authorized redirect URIs**（若 GIS 需要）按 Console 提示配置
- [ ] 填入 env 并重启前后端：

```bash
# backend/.env
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com

# frontend/web/.env
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
```

- [ ] 验证: `pytest backend/tests/test_auth_google.py -v`

### 说明

- 两项 env **都留空**时：前端不显示 Google 按钮，后端 `/api/v2/auth/google` 返回错误（预期）
- iOS 另需 Google Cloud 配置 iOS Client ID（上架前）

### 参考

- [`docs/TASKS_COMPLETION.md`](TASKS_COMPLETION.md) §1
- 代码: `backend/app/api/v2/auth.py`, `frontend/web/src/views/Login.vue`

---

## 3. 域名

**目标**: 生产环境统一入口，并解锁 OAuth、邮件链接、Stripe webhook、CORS。

### 待办

- [ ] 确定并注册主域名（例: `htex.app` / `visa.example.com`）
- [ ] DNS 解析：
  - `www` 或 `@` → 前端静态托管 / CDN
  - `api` → 后端 FastAPI（或同域反代 `/api`）
- [ ] HTTPS 证书（Let's Encrypt / 云厂商证书）
- [ ] 更新环境变量：

```bash
# backend/.env
APP_FRONTEND_BASE=https://<你的域名>    # 密码重置邮件里的链接前缀
CORS_ORIGINS=https://<你的域名>         # 若项目有该配置

# frontend/web/.env
VITE_API_BASE=https://api.<你的域名>    # 或同域 /api
```

- [ ] Google OAuth Console 补生产 **Authorized JavaScript origins**
- [ ] Stripe Webhook URL 改为 `https://api.<你的域名>/api/v2/payment/notify`
- [ ] 隐私政策 / 用户协议中的联系域名与实际上线域名一致

### 说明

- 开发阶段可用 `localhost:5173` + `localhost:8000`；**对外发布前域名是硬依赖**
- 临时外网联调可参考 `pm/infra/README.md`（ngrok / cloudflared），不作为生产方案
- **htexvisa.com 已在 Cloudflare**：生产 DNS + Tunnel 见 `pm/infra/cloudflare/README.md`

---

## 4. 邮箱

**目标**: 生产环境真实收发邮件（当前为 `logs/email_outbox/` 落盘 stub）。

### 待办

- [ ] **隐私/法务联系邮箱**（协议已写 `privacy@htex.app`）：
  - 注册域名邮箱或企业邮箱，确保可收信
  - `backend/.env`: `PRIVACY_SUPPORT_EMAIL=privacy@<你的域名>`
- [ ] **事务邮件**（注册欢迎、找回密码）：
  - 选型: SMTP / [Resend](https://resend.com) / Mailgun / 云厂商邮件推送
  - 配置发信域名 SPF / DKIM / DMARC（提高送达率）
  - 实现或接入生产邮件 backend（当前 `email_service.py` 为 outbox stub）
- [ ] **发信地址**（建议）:
  - `noreply@<你的域名>` — 系统通知
  - `privacy@<你的域名>` — 数据权利 / 隐私请求
- [ ] 与 `APP_FRONTEND_BASE` 联动：找回密码邮件中的重置链接须指向生产域名
- [ ] 抽测：注册 → 收欢迎信；忘记密码 → 收 token 邮件 → 重置成功

### 参考

- 代码: `backend/app/services/email_service.py`
- 配置: `backend/.env.example` → `PRIVACY_SUPPORT_EMAIL`, `APP_FRONTEND_BASE`
- 公开接口: `GET /api/v2/auth/public-config` 返回 `privacy_support_email`

---

## 建议处理顺序

```
域名（先定） → 邮箱（隐私邮箱 + SMTP） → Google OAuth（填生产 origin） → Stripe test（webhook 用真实 API 域名）
```

域名不定，后三项的生产配置都无法最终落地。

---

## 完成标准（可打勾上线）

- [ ] Stripe test 支付全流程：下单 → checkout → webhook → 订单 `paid`
- [ ] Google 登录：生产域名下点击按钮 → 拿到 JWT → 进入受保护页
- [ ] 域名 HTTPS 可访问，`/agreement` 与 API 正常
- [ ] 找回密码邮件真实送达，链接可点开重置

---

**相关文档**: [`TASKS_COMPLETION.md`](TASKS_COMPLETION.md) · [`PRIVACY_COMPLIANCE.md`](PRIVACY_COMPLIANCE.md) · [`LEGAL_REVIEW_NOTES.md`](LEGAL_REVIEW_NOTES.md)
