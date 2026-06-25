# Htex · Web 端 (用户端)

> 签证项目 V2 · W1 交付物 — 用户面向 Web 端 (Vue 3 + Vite + Element Plus)

## 技术栈

- Vue 3 (Composition API)
- Vite 5
- vue-router 4
- Pinia 2
- vue-i18n 9 (zh-CN / en,预留 id/vi 接口)
- Element Plus 2
- Axios
- Sass
- Playwright (E2E 测试 + 截图)

## 启动

```bash
cd frontend/web
npm install          # 装依赖
npm run dev          # 启动 dev server (http://localhost:5173)
npm run build        # 生产构建
npm run preview      # 预览构建产物 (http://localhost:4173)
```

启动后浏览器打开 http://localhost:5173 即可看到首页;访问 http://localhost:5173/register 进入 S1 注册页。

## 目录结构

```
web/
├── public/                  # 静态资源
├── src/
│   ├── api/                 # 后端 API 封装 (auth.js / http.js)
│   ├── components/          # 共用组件 (AppButton/Card/Input/LangSwitch/ToastContainer)
│   ├── composables/         # 组合式 API (useToast)
│   ├── i18n/                # vue-i18n 配置 + locale 切换
│   ├── router/              # vue-router 路由表
│   ├── stores/              # Pinia stores (auth)
│   ├── styles/              # 全局样式 + design tokens
│   ├── views/               # 路由级页面 (Home/Login/Register/Profile/NotFound)
│   ├── App.vue
│   └── main.js
├── tests/e2e/               # Playwright E2E 测试
│   ├── register.spec.js     # S1 注册流程 E2E (3 用例)
│   ├── screenshot.spec.js   # 截图脚本
│   ├── global-setup.cjs     # 自动起 vite dev server
│   └── global-teardown.cjs  # 自动关 vite
├── screenshots/             # Playwright 截图
├── index.html
├── vite.config.js
└── package.json
```

## S1 注册页说明

移植自 V2 原型 `sources/V2_原型_screenshots/02_signup.png` 的 P2 注册页:
- ✅ 手机号 input + 国旗下拉(🇨🇳+86 / 🇮🇩+62 / 🇻🇳+84 / 🇵🇭+63)
- ✅ 验证码 input + "发送验证码"按钮(调后端 send-code + 60s 倒计时)
- ✅ Mock 模式下验证码直接展示在表单下方(测试期便利)
- ✅ 密码 input(8-32 位含字母数字 + 强度提示)
- ✅ 确认密码(防错输)
- ✅ 协议勾选(《用户协议》《隐私政策》)
- ✅ "注册"按钮(调后端 register,成功后跳 /login)
- ✅ 表单验证 + 错误提示(直接显示后端返回的 message)
- ✅ 调后端用 fetch + localStorage 存 JWT
- ✅ 中英 i18n 切换

## Mock / 真实联调切换

- W1 已对接 B 后端 `/api/v2/auth/{send-code,register}`,`VITE_MOCK=false`。
- B 端 FastAPI 在 8000 端口跑着时,`/api` 代理自动转发到 `http://127.0.0.1:8000`,无需 CORS 配置。
- 如需退回 mock,把 `.env` 的 `VITE_MOCK=true`,前端会用 localStorage 兜底跑通流程。

## E2E 跑法

```bash
# 前置:后端在 8000 端口运行 (B Agent 起的 uvicorn)
curl http://localhost:8000/health  # 应返回 {"status":"ok",...}

# 跑全部 E2E
cd frontend/web
npm run test:e2e

# 跑指定文件
npx playwright test tests/e2e/register.spec.js

# 截图模式
npx playwright test tests/e2e/screenshot.spec.js
```

E2E 包含 3 个用例:
1. **happy path** — 填表(印尼 +62 区号 + 时间戳手机号 + 123456 验证码 + Test1234 密码 + 勾协议)→ 调后端 register → 跳 /login → JWT 写入 localStorage
2. **form validation** — 不勾协议提交,显示 `请先勾选用户协议和隐私政策` 错误
3. **password mismatch** — 两次密码不一致,显示 `两次输入的密码不一致` 错误

## 共用资源

i18n 文案和 design tokens 来自 `frontend/shared/`,通过 vite alias `@shared` 引用:

```js
// vite.config.js
'@shared': path.resolve(__dirname, '../shared')
```

如需新增文案 key,先在 `frontend/shared/i18n/{zh-CN,en}.json` 添加,4 端自动同步。

## 已交付页面清单 (W1)

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/home` | Home.vue | 首页 / 落地页 (Hero + 4 国 + 4 特性) |
| `/login` | Login.vue | P3 登录页 (双 tab + 表单 + Mock 验证码) |
| `/register` | Register.vue | **S1 注册页** (手机号 + 验证码 + 密码 + 协议) |
| `/profile` | Profile.vue | 登录后简单信息卡(W1 占位,W2 接订单) |
| `/*` | NotFound.vue | 404 |

## API 集成

> 完整端点文档见 `docs/API.md`。

### API 模块

| 模块 | 后端域 | 对应端点 | 当前状态 |
|------|--------|----------|----------|
| `src/api/auth.js` | Auth | `/v2/auth/*` | ✅ 已对接（Mock 兜底）|
| `src/api/orders.js` | Orders | `/v2/orders*` | ✅ 已对接（Mock 兜底）|
| `src/api/payment.js` | Payment | `/v2/payment*` | ⚠️ 部分对齐（见下方已知问题）|
| `src/api/materials.js` | Materials | `/v2/materials*` | ✅ 已对接（Mock 兜底）|
| `src/api/destinations.js` | Destinations | `/v2/destinations` | ✅ 已对接（Mock 兜底）|
| `src/api/voice.js` | Voice | `/v2/voice*` | ✅ 已对接（Mock 兜底）|
| `src/api/affiliate.js` | Affiliate | `/v2/affiliate*` | ✅ 已对接（USE_REAL=true）|
| `src/api/rpa.js` | RPA | `/v2/rpa*` | ✅ 已对接（Mock 兜底）|
| `src/api/admin.js` | Admin | `/v2/admin*` | ⚠️ 部分对齐（见下方已知问题）|

### 认证方式

**C 端用户**：JWT Bearer Token，`localStorage.visa.auth.accessToken`
**Admin 端**：`localStorage.admin_token`，独立 Axios 实例，不混入 C 端 token

### 错误码速查（V2 §9.3）

| code | 说明 |
|------|------|
| `1000` | 成功 |
| `1001` | 参数无效 |
| `1004` | 资源不存在 |
| `1005` | 未认证 / Token 过期 |
| `1006` | 无权限 |
| `1009` | 频率限制 |
| `2001` | 账号或密码错误 |
| `2002` | 验证码错误 |
| `4001` | 订单不存在 |
| `4002` | 订单不可取消 |
| `4010` | 订单不可编辑 |
| `4011` | 提交签名不匹配 |

### 已知问题（Pre-existing）

1. **Payment 端点路径不一致**：前端 `payment.js` 调用 `/v2/payment/status/{orderId}` 等，但后端为 `/v2/payment/{order_no}`、`/v2/payment/{order_no}/close`。真后端模式下支付查询/取消/重试会 404。
2. **Admin `/profile` 端点不存在**：前端 `admin.js` 调用 `GET /v2/admin/profile`，但后端无此端点（404）。建议由 login 响应返回 profile，或在后端补充该端点。
3. **RPA `/submit` 请求体不匹配**：前端发送 `{ order_no }`，后端期望 `{ order_id, country_code, visa_type, passport_data }`。

### Mock 模式切换

```bash
VITE_MOCK=false npm run dev   # 真后端联调
VITE_MOCK=true  npm run dev   # Mock 兜底（默认）
```

> `affiliate.js` 中 `USE_REAL = true` 硬编码，忽略 `VITE_MOCK`。

## 截图

- `screenshots/register.png` — Playwright 截取的 S1 注册页 (1440x900)
- 重新截:`npm run test:e2e` (会自动起 vite + 截图)
