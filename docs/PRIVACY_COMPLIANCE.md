# 隐私与合规 — 自助合规清单

**更新日期:** 2026-07-11  
**适用范围:** Htex Web 产品，目标用户市场越南 & 印尼，签证目的地 US/Schengen/GB/AU

本文档区分两类工作：**代码/产品层（已在本次实现）** 与 **系统/法务/运营层（需你或团队决策）**。

---

## 一、本次已在代码中完成的自助合规项

| 项目 | 说明 |
|------|------|
| 协议页可读 | `/agreement` 展示用户协议与隐私政策；注册页链接可跳转 |
| 隐私文案诚实化 | 移除 RPA/拒签险误导；说明第三方(Stripe/Google/OCR)；数据托管地区「待定」 |
| 敏感数据上传同意 | 护照/证件照/银行流水上传前弹窗明示同意 |
| 密码重置安全 | 关闭「仅凭账号改密」；改为邮件 token 两步流程 |
| 422 错误去 PII | 校验失败不再回显用户提交的 passport/email 等 |
| 账号注销入口 | 个人中心 → 申请注销 → `pending_destroy` → 72h 后清理 |
| 隐私联系邮箱 | 默认 `privacy@htex.app`，可通过 `PRIVACY_SUPPORT_EMAIL` 配置 |

---

## 二、仍需系统层面决策/落地的事项

以下**无法仅靠改代码完成**，上线越南/印尼前建议逐项确认。

### 1. 数据托管与跨境传输（P0 商业决策）

- **决定生产环境服务器所在司法管辖区**（如新加坡、印尼本地、越南本地、或其他）
- 在隐私政策中**写明最终托管地区**（当前文案为「待定」）
- **印尼 (UU PDP 2022):** 评估是否需要向 PDP 机构登记、跨境传输机制（SCC/合同约束）、本地代表
- **越南 (NĐ 13/2023):** 完成 DPIA/影响评估、跨境传输申报或本地化方案
- 与云厂商签署 DPA（数据处理协议）

### 2. 组织与流程（P0 运营）

- 指定 **DPO / 隐私负责人** 及对外联系邮箱（配置真实可收信的 `privacy@htex.app` 或企业邮箱）
- 建立 **数据主体权利请求** 处理流程（访问、更正、删除、撤回同意）
- 建立 **数据泄露通知** 流程（72h 内通知监管/用户的预案）
- Cookie/追踪技术说明（若后续加 Google Analytics 等需更新政策与 banner）

### 3. 第三方合同（P1）

- **Stripe:** 商户协议、PCI 责任划分、隐私政策链接
- **Google OAuth:** Google API Services User Data Policy 合规
- **OCR/LLM 供应商:** 确认是否将护照图像传到境外 API；签署 DPA；必要时做数据脱敏/区域 endpoint
- **邮件服务:** 生产 SMTP/Resend 配置（当前为 outbox 落盘，仅开发用）

### 4. 安全加固（P1，审计报告其余项）

| 项 | 状态 | 说明 |
|----|------|------|
| 无鉴权改密 | ✅ 已修 | 邮件 token |
| 422 回显 PII | ✅ 已修 | 去掉 `input` 字段 |
| 旧 JWT 不失效 | ⏳ 待做 | 改密/注销后应吊销 refresh token |
| 文件 magic 未验 | ⏳ 待做 | 上传时校验真实 MIME，不仅看扩展名 |
| Admin token 泄露等 | ⏳ 待做 | 见 `audit-2026-07-08/SECURITY-AUDIT.md` |

### 5. 法务审核（建议在规模化前）

- 四语种协议/隐私政策当前为 **v1.1-gdpr-draft**（产品按 GDPR Ch.V / Art.8 自助起草）
- **正式发布前须经当地律师审阅并签字** — 见 `docs/LEGAL_REVIEW_NOTES.md` §0（产品负责人不能自签代替法务）
- 平台定位声明：非律所、非使馆代理，避免无证法律服务的监管风险
- 支付与退款条款与当地消费者保护法对齐
- 仍待业务拍板：生产数据托管地区、适用法律/管辖法院、Cookie 专节（若上追踪）

---

## 三、环境变量

```bash
# backend/.env
PRIVACY_SUPPORT_EMAIL=privacy@htex.app   # 隐私/Data Subject 请求邮箱
APP_FRONTEND_BASE=https://your-domain.com  # 密码重置邮件链接前缀
```

公开接口：`GET /api/v2/auth/public-config` 返回 `privacy_support_email`。

---

## 四、用户可见流程速查

1. **注册** → 勾选协议（未预勾选）→ 可打开 `/agreement?tab=terms|privacy`
2. **上传护照/照片/流水** → 首次弹敏感数据同意
3. **忘记密码** → 输入账号 → 收邮件 → 链接带 token 设新密码
4. **注销** → 个人中心 → 输入密码确认 → 72h 后永久删除

---

## 五、相关文件

- 协议 UI: `frontend/web/src/views/Agreement.vue`
- 文案: `frontend/shared/i18n/{zh-CN,en,id,vi}.json` → `agreement.*`, `privacy_consent.*`
- 后端: `backend/app/api/v2/auth.py`, `profile.py`, `main.py`
- 法务待办: `docs/LEGAL_REVIEW_NOTES.md`
- 安全审计: `audit-2026-07-08/SECURITY-AUDIT.md`
