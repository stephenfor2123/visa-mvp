# Htex 安全 + 功能 + 文案 完整审计报告

**审计日期：** 2026-07-08
**审计人：** Mavis (自动化)
**审计范围：** 后端 API (130 endpoints) + 前端 i18n 文案 (4 国) + admin + auth + 文件 + 数据
**测试方式：** 仅记录问题，不修改任何代码。所有发现都附可复现的 cURL/Python 命令
**测试原则：** 用户要求"先记录再修" — 文档是事实陈述，修复优先级由用户决定

---

## TL;DR — 一句话总结

**P0 必修 1 个**（无鉴权改密）；**P0 严重 4 个**（错误回显 PII + funnel 500 + 旧 token 不失效 + 文件 magic 未验）；
**P1 必修 7 个**（admin token 信息泄露 + 26 申根国 enabled 错误 + 4 国 i18n 大量漏翻 + 后端 i18n_override Python 3.9 兼容 + admin roles/users 表空 + 系统 key hardcoded + 文件 PII 字段不当明文）；
**P2 优化 11 个**。

---

## 🔴 P0 — 必须立即修复

### P0-1. `/api/v2/auth/reset-password` 无任何鉴权即可改密

**严重性：账号接管（Account Takeover）**

**实测：**
```bash
# 不带任何 token / 不带任何验证码 / 不带任何短信
curl -X POST http://127.0.0.1:8000/api/v2/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"account":"demo138001380001@htex.app","new_password":"hacked999"}'
# → {"code":"1000","message":"OK","data":{"message":"Password updated successfully"}}

# 立即用新密码登录
curl -X POST http://127.0.0.1:8000/api/v2/auth/login \
  -d '{"account":"demo138001380001@htex.app","password":"hacked999"}'
# → 1000 OK + 拿到 access_token
```

**位置：** `backend/app/api/v2/auth.py:73-91` (`reset_password` endpoint)

**代码注释：** "W26 no SMS" — 当初 W26 简化 demo 流程时去掉了 SMS 验证，但忘了加任何替代验证手段（邮件 token / 旧密码校验 / reCAPTCHA）。

**影响：** 任何知道 email 或 username 的人，**可立即接管任意账号**。生产环境**这是灾难性漏洞**。

**修复方向（仅建议，不动手）：**
- A. 临时关闭 endpoint，强迫走邮件验证码流程
- B. 加 `old_password` 字段，要求先验证旧密码
- C. 加 reCAPTCHA 或邮箱验证 token
- 选 A + B 组合最稳。

---

### P0-2. Pydantic 422 错误响应把整个 PII input 回显

**严重性：用户隐私泄露**

**实测：**
```bash
curl -X POST http://127.0.0.1:8000/api/v2/diagnose \
  -H "Authorization: Bearer $TOK1" -H "Content-Type: application/json" \
  -d '{"country_code":"US","marital_status":"single","income_bucket":"medium",
       "applicant":{"surname":"ZHANG","given_name":"SAN","nationality":"CN",
                    "passport_no":"E12345678","birth_date":"1990-01-01",
                    "phone":"+8613800138000","email":"zhang@test.com"},
       "items":[{"category":"passport","file_size":1024,"sha256":"abc"}]}'
```
**响应：**
```json
{
  "code":"1001","message":"Invalid request parameters",
  "data":{"errors":[
    {"type":"missing","loc":["body","travel_history"], "msg":"Field required",
     "input":{
       "country_code":"US", "marital_status":"single", "income_bucket":"medium",
       "applicant":{
         "surname":"ZHANG", "given_name":"SAN", "nationality":"CN",
         "passport_no":"E12345678", "birth_date":"1990-01-01",
         "phone":"+8613800138000", "email":"zhang@test.com"
       },
       "items":[...]}}]}}
```

**问题：** `errors[*].input` 字段把**整个请求体**回显给前端，**包含完整姓名/护照号/手机号/邮箱**。

**影响：**
- 任何前端 console / axios error / 第三方抓包 / 浏览器扩展都能拿到用户完整 PII
- 攻击者只需要用户故意触发一个 422，就能拿到完整数据
- 泄露路径：dev tools → network tab → response body

**涉及端点：** 全部接收敏感 PII 的 POST 接口（diagnose / materials/diagnose / materials/validate / applicants POST / profile/email/change-request 等）

**修复方向：**
- 在 pydantic ValidationError handler 里把 `input` 字段截断到类型描述（如 `"<surname: str>"`）或不回显
- 或全局配置 `RequestValidationError` 自定义 handler

---

### P0-3. `/admin/stats/dashboard/funnel?range=7d|30d` 稳定 500

**严重性：admin dashboard 核心指标直接挂**

**实测：**
```bash
curl "http://127.0.0.1:8000/api/v2/admin/stats/dashboard/funnel?range=7d" \
  -H "Authorization: Bearer $ATOK"
# → {"code":"1010","message":"Internal server error","data":{}}
```

**根因：** service 用 `register`(User 表) 和 `create`(Order 表) 分别计数，第 2 步 conversion = order/user × 100%，但 user 表 5 行 + order 表 7 行 → 140% > 100 → schema 限 `le=100.0` → ValidationError → 500

**位置：** `backend/app/services/admin_dashboard_service.py:280-285`

**修复方向：**
```python
# 兜底 min(100, pct)
s["conversion_pct"] = min(100.0, round((s["count"]/prev*100.0), 2)) if prev>0 else 0.0
```
或重构 4 步都用同源数据。

---

### P0-4. JWT 旧 token 在密码重置后仍有效

**严重性：会话劫持窗口期**

**实测：**
```bash
# admin 重置 demo1 密码为新密码
NEW_PW=$(curl -sS -X POST http://127.0.0.1:8000/api/v2/admin/users/5/reset-password \
  -H "Authorization: Bearer $ATOK" -H "Content-Type: application/json" -d '{}' | jq -r '.data.new_password')

# demo1 重置前拿的 token ($TOK1) 仍然能调用 profile
curl http://127.0.0.1:8000/api/v2/profile -H "Authorization: Bearer $TOK1"
# → 200 OK (依然能访问受害者账号)
```

**根因：** JWT 是 stateless 的，密码重置/账号 disable 后**不会**让旧 token 失效。

**影响场景：**
- 用户改密 → 旧设备/旧浏览器未退出 → 仍可访问
- admin 重置用户密码 → 用户已登录的浏览器仍可用 → 直到 2h 后 access_token 自然过期
- 用户被 disable → 旧 token 仍能用 2h

**修复方向：**
- 给 user 加 `password_changed_at` 时间戳，token 校验时比对
- 或维护 token 黑名单（Redis set，按 jti 存）
- 或 access_token 有效期缩短到 15min + 强制 refresh

---

### P0-5. 文件上传不做 magic bytes 校验

**严重性：伪装文件攻击 + 内容污染**

**实测：**
```bash
# 上传 .exe 内容 (MZtest)，但伪装成 png
echo "MZtest" > /tmp/evil.exe
curl -X POST http://127.0.0.1:8000/api/v2/materials/upload \
  -H "Authorization: Bearer $TOK1" \
  -F "file=@/tmp/evil.exe;type=image/png;filename=evil.png" \
  -F "material_type=passport"
# → 1000 OK，material 创建成功 (mime_type='image/png', file_size=7)
```

**位置：** `backend/app/api/v2/materials.py` (或 services)

**影响：**
- 上传任意内容当作 PNG/JPG/PDF，污染 OCR 训练数据
- 上传 10MB 内的恶意文件
- 后续 OCR/preprocess 流程可能因 magic bytes 错误产生奇怪行为
- 已上传的 `evil.png` 实际是 `MZtest\n`（7 字节）

**修复方向：**
- 上传时用 `python-magic` 或 `filetype` 校验 magic bytes
- 不匹配 mime 就 415 拒绝

---

## 🟠 P1 — 上线前应修

### P1-1. `/destinations` 返 29 国全 enabled，不符产品规格

**实测：**
```bash
curl http://127.0.0.1:8000/api/v2/destinations | jq '.data | length'
# → 29
# 全部 enabled=true (26 申根国 + US/GB/AU/FR)
```

**问题：** 产品规格说"美国 enabled=true，其他 8 国 enabled=false"，但 API 把 26 个被 seed_schengen_26.py 标记为 enabled 的申根国也全开了。

**影响：**
- alerts 接口报"28 个启用的目的地 24h 零订单" — 噪声
- dashboard funnel 第 2 步 conversion 100%+
- 前端 Apply.vue 在过滤，但 API 直接暴露了不该展示的

**修复方向：** seed 脚本改 26 申根国 enabled=False 或 API 加 `?enabled=true` 参数。

---

### P1-2. i18n_override 模型用 PEP 604 语法不兼容 Python 3.9

**位置：** `backend/app/models/i18n_override.py:21`

**症状：** `Mapped[str | None]` 语法需 Python ≥ 3.10

**实测触发：** 当前进程已规避；如果未来 reload 触发 I18nOverride 重新 import，会再炸

**修复方向：** 改 `Optional[str] = mapped_column(...)` 或升级 Python ≥ 3.10。

---

### P1-3. AdminUser/AdminRoles 表 0 行 — 全靠 env admin fallback

**实测：**
```bash
curl http://127.0.0.1:8000/api/v2/admin/admin-users -H "Authorization: Bearer $ATOK"
# → {"items":[],"total":0}
curl http://127.0.0.1:8000/api/v2/admin/roles -H "Authorization: Bearer $ATOK"
# → []
```

**JWT 解析 admin token：**
```json
{"sub":"0","type":"admin_access","role":"admin","username":"admin", ...}
```

**影响：**
- audit_log 所有 admin 操作记录 actor_id=0，无法区分是哪个 admin 做的
- 未来多 admin 必然撞坑（所有 admin 操作追溯都是 actor=0，分不开谁做的）
- admin/roles、admin/admin-users 接口空响应（前端无意义）

**修复方向：** 给 env admin 分配 stable 负数 ID（如 -1）明确"system admin"，并文档化；或 seed 一个 admin_users 行。

---

### P1-4. SYSTEM_API_KEY 默认值是 hardcoded

**位置：** `backend/app/core/config.py`
```python
system_api_key: str = "dev-system-key-change-me-in-prod-visa-mvp-2026"
```

**实测：** 用这个 key 能调 `/scheduler/poll-tick`、`/scheduler/rag-refresh-tick` 等。

**风险：** 注释说 prod 必须改 env，但默认值这么明显，**如果运维忘了改 env = 后门**。

**修复方向：** 强制 env=prod 时 startup 校验 key 不能等于默认值；或要求启动时通过 secret manager 注入。

---

### P1-5. Admin token payload 含 username（比 user token 长 53 字节）

**对比：**
- User access token: `{"sub":"5","type":"access","iat":...,"exp":...,"jti":...}` — 196 字节
- Admin access token: `{"sub":"0","type":"admin_access","role":"admin","username":"admin","iat":...,"exp":...,"jti":...}` — 249 字节

**问题：** admin token 多了 `username` 字段。**为什么 admin token 要暴露 username？** 这不是漏洞，但属于"按需最小披露原则"违背 —— user token 都不带 username，admin 凭什么带？

**建议：** admin token 去掉 username 字段，前端从 `/admin/profile` 单独拿。

---

### P1-6. Admin `/orders/{id}` applicant_data 字段含明文护照号

**实测：**
```bash
curl http://127.0.0.1:8000/api/v2/admin/orders/7 -H "Authorization: Bearer $ATOK" | jq '.data.applicant_data'
# → "{\"full_name\":\"Demo Applicant\",\"nationality\":\"CN\",\"passport_no\":\"E12345678\",\"birth_date\":\"1990-01-01\"}"
```

**问题：** applicant_data 是 JSON 字符串直接返，**含明文护照号 + 出生日期**。

**影响：**
- 业务上 admin 需要看材料，但 admin 角色权限分级没做
- 一旦 admin token 泄露，攻击者能拿到所有用户完整材料信息

**修复方向：**
- admin 端加 RBAC（admin_viewer / admin_operator / admin_super）
- viewer 角色看 applicant_data 时护照号脱敏 `E1***78`
- 或拆字段为 `applicant_summary` + `applicant_full` 两个接口

---

### P1-7. 前端 i18n 漏翻严重（admin namespace 61% 缺）

**实测统计：**
| 语言 | 总 keys | 缺失 (相对 zh-CN 2093) |
|---|---|---|
| zh-CN | 2093 | 0 (基准) |
| en | 2074 | -19 (缺 onboarding + theme + 3 admin) |
| **id** | **1767** | **-326** |
| **vi** | **1767** | **-326** |

**namespace 分布：**
- `admin.*`: 缺 **308/508 (61%)** — admin 后台印尼语/越南语大面积显示原始 key 名
- `onboarding.*`: 缺 **16/16 (100%)** — 新用户引导流程在 id/vi 下完全不显示
- 其他 namespace 极少量缺

**示例（admin 后台 id/vi 下显示效果）：**
- 应该显示"用户管理" → 实际显示 `admin.c_users.title` 原始 key
- 应该显示"启用"按钮 → 实际显示 `admin.c_users.action_disable`

**修复方向：** 用 `_build_curated_payloads.py` 同款脚本批量补 admin namespace 的 id/vi 翻译；onboarding 整个 namespace 一次性补。

---

## 🟢 P2 — 可优化

### P2-1. 后端文案 1978 行中文 hardcoded

**分布：**
```
223 lines: app/services/visa_diagnoser.py
191 lines: app/services/bank_statement_parser.py
120 lines: app/api/v2/rag.py
115 lines: app/services/admin_service.py
 99 lines: app/services/rag/refresh.py
 96 lines: app/services/material_group.py
 79 lines: app/schemas/admin.py
...
```

**问题：** 后端返给前端的中文文案（issue title/detail/fix）前端要靠 `title_key/detail_key/fix_key` 双轨翻译。如果前端路由表没覆盖该 code，就显示后端原始中文。

**实测：** `/api/v2/materials/diagnose` 返回的 issue 全是中文 hardcoded，没有 `*_key` 字段（不像 visa_diagnoser 有），前端拿到直接显示中文。

**修复：** 后端 issue 全部加 `*_key` 双轨；或后端按 `Accept-Language` / `lang` 参数返回翻译版。

---

### P2-2. 前端 121 处 hardcoded 中文 fallback 模式 `t(key) || '中文'`

**示例：**
```js
// web/src/views/MaterialWizard.vue:1520
it.error = t('wizard.err_material_deleted') || '该材料已失效,请重新上传'

// web/src/views/Login.vue:15
{{ t('login.hint_needed') || '登录后即可完成订单提交,你填的资料已自动保存' }}
```

**风险：** 当 i18n JSON 漏翻某个 key 时（前面 P1-7 大量漏），直接给用户看 fallback 中文。

**修复：** 删 hardcoded fallback，让 `t(key)` 找不到时返回 key 字符串（至少能看出问题），并补 4 国翻译。

---

### P2-3. OpenAPI `/docs` + `/openapi.json` 生产环境应关闭

**实测：**
```bash
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
# → 200
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/openapi.json
# → 200
```

**泄露内容：**
- 130 个端点的完整 path + method + parameters
- 29 个 admin schema 的字段定义（含 passport_no / applicant_data）
- RegisterRequest/ResetPasswordRequest 的字段约束

**风险：** 给攻击者一份完整的攻击面地图，包括哪些字段是 PII、哪些字段允许注入。

**修复：** prod env 加 env check，`env != "dev"` 时返回 404。

---

### P2-4. Rate limit 配置跟 dashboard 场景不匹配

**实测：**
- Global: **100 req/min/IP**
- 触发 429 实测约 25-30 个 req（比预期低，说明实际阈值更严）
- dashboard 一次性并发 5-8 个 + 用户浏览 = 极容易 429

**影响：** 真实用户频繁刷 dashboard 被 429 限流，体验差。

**修复：** dashboard 拆出独立 bucket（`dashboard_per_ip_per_min=600`）。

---

### P2-5. X-Forwarded-For 头完全没被读取

**实测：**
```bash
# 用 30 个不同 XFF，0 个 429（说明没基于 XFF 限流）
for i in $(seq 1 30); do
  curl -X POST http://127.0.0.1:8000/api/v2/auth/login \
    -H "X-Forwarded-For: 192.168.$((RANDOM%255)).$((RANDOM%255))" \
    -d '{"account":"x","password":"y"}'
done
# 全部 400，没 1 个 429
```

**风险：** 这是"防伪造"好事，但**生产部署在反向代理后**，真实 client IP 取不到。

**修复：** 在 trust proxy 模式下读 `X-Forwarded-For` 第一段；非 proxy 模式忽略。

---

### P2-6. `access_control_allow_credentials: true` 在恶意 origin 下也返回

**实测：**
```bash
curl -i http://127.0.0.1:8000/api/v2/profile \
  -H "Origin: https://evil.com" -H "Authorization: Bearer $TOK1" | grep -i access-control
# → access-control-allow-credentials: true
# (没有 access-control-allow-origin: https://evil.com)
```

**影响：** 浏览器会拒（因为 allow-origin 不匹配 evil.com），所以**实际无害**。但形式上不规范 —— 应该只在 origin 白名单匹配时才返 `allow_credentials: true`。

**修复：** middleware 加 origin 白名单判断后再决定是否返 allow-credentials。

---

### P2-7. CORS preflight 用 `Access-Control-Request-Method: GET` 返 400

**实测：**
```bash
curl -i -X OPTIONS http://127.0.0.1:8000/api/v2/profile \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: GET"
# → HTTP/1.1 400 Bad Request
```

**问题：** OPTIONS preflight 期望返 200 而不是 400。虽然 `allow-headers/methods/max-age` 都正确返回，但状态码 400 会让某些浏览器跳过。

**修复：** middleware 对 OPTIONS 显式返 200。

---

### P2-8. 文件下载 `_local` 路径全 403

**实测：**
```bash
# 带正确 token + 自己的 storage_key 也 403
curl -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:8000/api/v2/materials/_local/x?key=5/2026/07/5ec53d418ee64a4c98fbc277dc113913.png" \
  -H "Authorization: Bearer $TOK1"
# → 403

# /materials/{id}/download 用合法 token + 自己的材料 id → 200 OK
# 但 /admin/materials/{id}/download 用 admin token → 401 (Wrong token type)
```

**问题：** admin 完全无法下载用户上传的材料 —— **合规审计场景 admin 需要看原始材料**。

**修复：** admin 端加 admin 专属 materials download endpoint（不走 user token 校验）。

---

### P2-9. `/orders/{no}` GET 单订单稳定 500

**实测：**
```bash
# 创建订单
ORD=$(curl -X POST http://127.0.0.1:8000/api/v2/orders \
  -H "Authorization: Bearer $TOK1" -H "Content-Type: application/json" \
  -d '{"destination_id":1,"visa_type":"tourism","material_ids":[4]}' | jq -r '.data.order_no')
# → V2-20260707-23BC2566

# 列表能看到
curl "http://127.0.0.1:8000/api/v2/orders" -H "Authorization: Bearer $TOK1" | jq '.data.items[0].country_code'
# → "US"

# 单订单 GET
curl "http://127.0.0.1:8000/api/v2/orders/$ORD" -H "Authorization: Bearer $TOK1"
# → {"code":"1010","message":"Internal server error","data":{}}
```

**问题：** 单订单端点 100% 复现 500。订单创建时 country_code 是空，列表端补全 country_code="US"，但单订单端 join 出错。

**影响：** **用户点了订单详情页就 500**，核心流程断裂。

**修复：** 看后端 stack trace —— 单订单 join 时 destination 表的外键关联可能是 N+1 或 ORM 错配。

---

### P2-10. `/api/v2/diagnose` 全部 4 国稳定 500

**实测：**
```bash
curl -X POST http://127.0.0.1:8000/api/v2/diagnose \
  -H "Authorization: Bearer $TOK1" -H "Content-Type: application/json" \
  -d '{"country_code":"US","marital_status":"single","income_bucket":"medium",
       "travel_history":"JP,TH","visa_history":"none","employment":"employed",
       "items":[{"category":"passport","file_size":102400,"sha256":"abc"}]}'
# → {"code":"1010","message":"Internal server error","data":{}}  # 4 国都 500
```

**问题：** `diagnose`（注意不是 `materials/diagnose`）整条链挂。

**影响：** 前端如果有"完整 AI 拒签风险诊断"功能页面，**直接白屏**。

**修复：** 看 visa_diagnoser.py 的 stack trace。

---

### P2-11. `/api/v2/admin/rag/sources` 和 `/admin/rag/refresh` 500

**实测：**
```bash
curl "http://127.0.0.1:8000/api/v2/admin/rag/sources" -H "Authorization: Bearer $ATOK"
# → 1010
curl -X POST "http://127.0.0.1:8000/api/v2/admin/rag/refresh" -H "Authorization: Bearer $ATOK"
# → 1010
curl -X POST "http://127.0.0.1:8000/scheduler/rag-refresh-tick" \
  -H "X-System-Key: dev-system-key-change-me-in-prod-visa-mvp-2026"
# → 1010
```

**问题：** RAG admin 管理端点全挂，scheduler 端点也挂。**RAG 内容刷新机制完全 broken**。

**影响：** RAG chunk 不会自动更新，靠人工重新 seed。`/admin/rag/translation-stats` 已暴露真相：zh-CN / id / vi 翻译覆盖率 0%，仅 en 100%。

**修复：** 看 refresh.py 和 rag.py 的 stack trace。

---

## ✅ 通过的测试（无问题或低风险）

| 测试项 | 结果 |
|---|---|
| 无 token admin 全 401 | ✓ 49/49 端点 |
| 伪造 token (HS256 invalid) | ✓ 401 |
| alg=none 算法攻击 | ✓ 401 |
| 越权访问他人订单 `/orders/{other_user_id}` | ✓ 4001 not_found（不泄露存在性） |
| 越权访问他人材料 ID | ✓ 1004 |
| 跨用户材料写（OCR / classify / download） | ✓ 1004 |
| 路径注入 `../../../etc/passwd` 文件名 | ✓ 服务端 sanitization（存 hash） |
| 路径注入 `_local?key=../../../etc/passwd` | ✓ 403 |
| 邮箱 SQL 注入 `' OR 1=1--` | ✓ 422 (pydantic) |
| 弱密码 < 8 chars | ✓ 422 |
| 重复注册 (email) | ✓ 2003 |
| 重复注册 (username) | ✓ 2003 |
| Username 含特殊字符 `../../etc` | ✓ 422 |
| Login → Create Order 整链路 | ✓ 通过 |
| Admin token 不能调 user 接口（type 不对） | ✓ 1005 Wrong token type |
| User token 不能调 admin 接口 | ✓ 403 |
| 跨域 OPTIONS 攻击 | ✓ 严格 origin 白名单 |
| 文件下载路径遍历 | ✓ 403 |
| 大文件 50MB | ✓ 413 PAYLOAD_TOO_LARGE (10MB cap) |
| 巨大/负 page 参数 | ✓ 400 |
| CORS x-content-type-options / x-frame-options / CSP / Permissions-Policy | ✓ 全部正确 |
| 密码策略 8 字符 min | ✓ |
| 系统响应时间（batched dashboard 9-16ms） | ✓ 抗压优秀 |
| Login audit log 不含 password/email | ✓ 只记 IP + UA |
| v-html 使用 (8 处) 数据源审查 | ✓ 全部先 escape 或自生成 |
| CSP `script-src 'self'` 无 unsafe-inline | ✓ 严格 |
| XSS payload `<script>alert(1)</script>` 在 material_type | ✓ 422 拒绝 |
| 后端 /health 不被限流 | ✓ 白名单生效 |
| 60s 缓存命中 (get_summary 第二次 9ms) | ✓ |
| 4 国 destinations id/vi 翻译 GB/US/AU | ✓ 正确 |
| 申根国 country_name 在 vi/id 下 | ✓ 已本地化 |
| 前端 refresh token 流程 | ✓ 401 后自动 refresh + retry |
| /admin/config/countries reorder/toggle 鉴权 | ✓ admin only |
| /admin/cleanup/* 鉴权 | ✓ admin only |
| audit_log payload 不含敏感字段 | ✓ |

---

## 📊 风险分布统计

| 等级 | 数量 | 影响面 |
|---|---|---|
| P0 必须立即修 | 5 | 安全漏洞 + 核心功能挂 |
| P1 上线前应修 | 7 | 数据不一致 + admin 功能缺 + i18n 漏翻 |
| P2 可优化 | 11 | 体验 + 配置 + 文档 |
| ✅ 通过 | 35+ | 功能正确 + 防护到位 |

---

## 🧪 测试覆盖明细

### 信息安全（已覆盖）
- Token 安全：无/伪造/篡改/类型错/算法攻击/admin vs user 隔离
- IDOR 横向越权：订单/材料/材料操作/订单列表 query
- 越权访问：admin 调 user 接口 / user 调 admin 接口
- 字段泄露：applicant_data / email / phone / token
- 日志泄露：login log payload
- 错误信息泄露：422 input 回显 / 500 错误统一
- CORS：origin 白名单 / preflight / credentials
- 文件上传：magic bytes / 路径穿越 / mime 注入 / 文件大小
- 文件下载：路径遍历 / 跨用户 / admin token
- Rate limit：触发阈值 / X-Forwarded-For 绕过
- 系统 key：默认值泄露风险 / scheduler 端点
- OpenAPI 暴露：docs/openapi.json

### 功能完整性（已覆盖）
- 130 个端点中 smoke test ~70 个
- 关键流程：注册 / 登录 / refresh / 选国家 / 上传材料 / 创建订单 / 支付 / 诊断 / 检查清单 / 保险 / 行程 / 邮件验证 / admin 用户管理 / admin 订单管理 / admin 仪表盘
- 边界输入：负 page / 巨大 page_size / 空 token / 不存在资源

### 文案/i18n（已覆盖）
- 4 国 destinations 翻译对齐
- 4 国 RAG checklist 数量对比（zh 8 vs en 5 不一致）
- 4 国后端 API 返 issue title 翻译（多数 hardcoded 中文）
- 前端 4 国 i18n JSON keys 数对齐（2093 vs 1767 vs 1767）
- 前端 121 处 hardcoded 中文 fallback 模式
- 前端 134 文件 2861 行中文 hardcoded
- 后端 63 文件 1978 行中文 hardcoded
- v-html 数据源审查（8 处）
- 错误响应文案 4 国一致性

---

## 📋 修复建议优先级（按工作量 / 价值比排序）

| # | 项 | 工作量 | 价值 |
|---|---|---|---|
| 1 | P0-1 关 reset-password / 加 SMS 验证 | 2h | 救账号接管 |
| 2 | P0-2 关 Pydantic input 回显 | 30min | 救 PII 泄露 |
| 3 | P0-3 funnel 加 min(100) 兜底 | 5min | 救 dashboard |
| 4 | P0-4 旧 token 失效 (Redis 黑名单) | 4h | 救会话劫持 |
| 5 | P0-5 文件 magic 校验 | 2h | 救文件污染 |
| 6 | P1-1 26 申根国 enabled=False | 10min | 修数据 |
| 7 | P1-3 admin env stable id | 1h | 修追溯 |
| 8 | P1-7 id/vi admin 翻译补齐 | 8h | 修多语言 |
| 9 | P2-9 单订单 500 修 | 2h | 救核心流程 |
| 10 | P2-10 diagnose 500 修 | 2h | 救 AI 诊断 |
| 11 | P2-11 RAG admin 500 修 | 4h | 救 RAG |

合计 P0/P1 紧急修复 **约 17.5h 工作量**。

---

## 📝 备注

- 所有测试均通过 `http://127.0.0.1:8000` 实际接口执行
- 测试 token 均为本地 seed 的 demo 账号，未影响真实数据
- 测试结束后所有 demo 账号密码已恢复到 `Htex@2026`
- 测试过程中创建的 applicant / material / order 等资源**保留**在测试库中（如要清理跑 `cleanup_service`）
- 部分测试间接触发了 scheduler tick（DEMO-20260615-SUBMITTED-002 状态自动从 submitted → reviewing）—— 属于预期行为
