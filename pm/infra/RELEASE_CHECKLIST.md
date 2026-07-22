# Htex 发版检查清单（前后端分开部署时必看）

> 完整 DevOps 方案见 [`DEVOPS.md`](./DEVOPS.md)。  
> 目标：避免再出现「Google 按钮消失 / 管理端 500 / 上传全挂」这类发完才发现的问题。

发版后必跑：

```bash
bash scripts/smoke-prod.sh
```

## 0. 铁律

1. **有后端契约变更时，前后端必须同窗口发布**（例如 consent 门槛、年龄确认字段）。只发一端会直接断链路。
2. **前端生产构建必须带齐 `VITE_*`**。`vercel build --prod` 只读 Vercel 云端环境变量；本地 `.env.production` 不会自动进云端构建。
3. **生产 `ENV=prod` 必须有 `MATERIAL_ENCRYPTION_KEY`**，否则材料上传会直接 500。

## 1. 前端（Vercel）

```bash
cd frontend/web
npm run preflight:prod          # 缺 Google Client ID / API Base 会直接失败
# 推荐本地可复现构建：
DISABLE_PWA=1 npm run build:prod
npm run verify:prod-bundle      # 确认 Client ID 已打进包
DISABLE_PWA=1 npx vercel build --prod   # 若走 vercel build，先保证云端 env 齐全
npx vercel deploy --prebuilt --prod --yes
```

### Vercel Production 必备环境变量

| 变量 | 不设后果 |
|------|----------|
| `VITE_API_BASE=https://api.htexvisa.com/api` | `/api` 打到 SPA → 405 |
| `VITE_GOOGLE_CLIENT_ID=…apps.googleusercontent.com` | Google 登录按钮消失 |
| `VITE_WS_URL=wss://api.htexvisa.com` | 订单实时推送异常 |
| `VITE_MOCK=false` | 线上走到 mock 数据 |
| `VITE_APP_ENV=production` | 环境判断错乱 |

发版后硬刷新验收：`/login` 有 Google 按钮；Network 里 API 打到 `api.htexvisa.com`。

## 2. 后端（阿里云 Docker）

```bash
cd backend
python scripts/preflight_prod.py --strict   # OpenAPI + typing + 加密密钥
# 同步代码后：
bash /opt/visa-mvp/pm/infra/aliyun/deploy-api-only.sh
# 或：
docker compose up -d --build
docker compose exec backend alembic current   # 必须显示 (head)
curl -fsS https://api.htexvisa.com/health
```

### 生产 `.env` 必备

| 变量 | 不设后果 |
|------|----------|
| `ENV=prod` | 行为像开发环境 |
| `MATERIAL_ENCRYPTION_KEY` | 上传/读材料 500 |
| `JWT_SECRET` | 鉴权异常 |
| `APP_FRONTEND_BASE` / CORS | 浏览器跨域失败 |

新增 Alembic 迁移后：**先确认线上当前 revision，再 upgrade**；禁止多 head。

## 3. 常见回归对照

| 现象 | 优先查 |
|------|--------|
| Google 按钮没了 | `VITE_GOOGLE_CLIENT_ID` 是否打进包 |
| 管理端 / 任意接口 500 + PydanticUserError | `Optional` 等 typing 未导入（跑 `preflight_prod.py`） |
| 上传 403 Consent required | 前端未发或未弹同意；或只发了后端 |
| 上传 500 + encryption | 缺 `MATERIAL_ENCRYPTION_KEY` |
| checklist / analytics 405 | `VITE_API_BASE` 空，请求打到 Vercel |

## 4. 发版顺序（有契约变更时）

1. 跑前后端 preflight  
2. **先发后端**（迁移 + 健康检查）  
3. **再发前端**（bundle verify）  
4. 无痕窗口走：登录（含 Google）→ 同意上传 → 管理端登录
