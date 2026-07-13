# Cloudflare · htexvisa.com 生产域名

> 域名 **htexvisa.com** 已在 Cloudflare（NS: `kyrie.ns.cloudflare.com` / `brit.ns.cloudflare.com`）。
> 当前 **无有效 A/CNAME 记录**，站点还不可访问。按下面步骤接上服务即可。

---

## 目标架构

| 域名 | 用途 | 指向 |
|------|------|------|
| `htexvisa.com` | 前端 Web | 静态托管 / Tunnel → localhost:5173 或 dist |
| `www.htexvisa.com` | 同上（重定向） | → `htexvisa.com` |
| `api.htexvisa.com` | FastAPI 后端 | Tunnel → localhost:8000 或 VPS:8000 |

---

## 第一步：Cloudflare Dashboard 基础设置

登录 [Cloudflare Dashboard](https://dash.cloudflare.com) → 选 **htexvisa.com**：

### 1.1 SSL/TLS

- **SSL/TLS → Overview** → 选 **Full (strict)**（有有效证书时）或 **Full**（自签/开发期）
- **Edge Certificates** → 打开 **Always Use HTTPS**
- **Edge Certificates** → 打开 **Automatic HTTPS Rewrites**

### 1.2 www → 根域 301（主用根域 htexvisa.com）

**决策**：主站 = `https://htexvisa.com`，`www` 永久跳转到根域。

Cloudflare 免费版用 **Redirect Rules**：

1. **Rules → Redirect Rules → Create rule**
2. 配置：
   - Rule name: `www to root`
   - When incoming requests match: `Hostname` `equals` `www.htexvisa.com`
   - Then → Type: **Dynamic**
   - Expression: `concat("https://htexvisa.com", http.request.uri.path)`
   - Status code: **301**
   - Preserve query string: ✅
3. Deploy

效果：`www.htexvisa.com/foo?x=1` → `301` → `htexvisa.com/foo?x=1`

> 因为 www 会跳到根域，OAuth / CORS 只需登记根域 `https://htexvisa.com` 即可（登记 www 也无害）。

### 1.3 安全（上线前）

- **Security → Settings** → Bot Fight Mode: 按需
- **Security → WAF** → 免费版有基础规则
- **Speed → Optimization** → Auto Minify（JS/CSS/HTML）可选

---

## 第二步：选部署方案

### 方案 A — Cloudflare Tunnel（推荐：本机 Mac / 无公网 IP）

不需要 VPS、不需要开 80/443 端口。cloudflared 主动连 Cloudflare，流量经 Tunnel 进本机。

```bash
# 1. 安装
brew install cloudflared

# 2. 登录 Cloudflare（浏览器授权）
cloudflared tunnel login

# 3. 一键创建 Tunnel + DNS
bash pm/infra/cloudflare/setup_named_tunnel.sh
```

脚本会：
- 创建名为 `htex-visa` 的 Tunnel
- 写入 `~/.cloudflared/config.yml`
- 在 CF 添加 `htexvisa.com`、`www`、`api` 的 CNAME
- 生成 launchd 自启 plist（可选）

**本机需同时跑：**
```bash
# 终端 1 — 后端
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2 — 前端（开发）
cd frontend/web && npm run dev -- --host 0.0.0.0 --port 5173

# 终端 3 — Tunnel
cloudflared tunnel run htex-visa
```

生产前端建议 `npm run build` 后用静态服务器（见下方「前端静态托管」）。

---

### 方案 B — VPS + DNS A 记录（有固定公网 IP）

1. 在 VPS 上跑 `docker compose up`（见 `backend/docker-compose.yml`）
2. Cloudflare DNS 添加：

| 类型 | 名称 | 内容 | Proxy |
|------|------|------|-------|
| A | `@` | `<VPS_IP>` | 已代理（橙云） |
| A | `www` | `<VPS_IP>` | 已代理 |
| A | `api` | `<VPS_IP>` | 已代理 |

3. VPS 上装 Nginx 反代（80/443 或仅 80，CF 做 SSL 终止时用 Full 模式）

---

### 方案 C — 前端 Cloudflare Pages + 后端 Tunnel

| 组件 | 托管 |
|------|------|
| 前端 `frontend/web/dist` | Cloudflare Pages（连 GitHub 或 `wrangler pages deploy`） |
| 后端 API | Tunnel → `api.htexvisa.com` |

Pages 自定义域：`htexvisa.com` / `www.htexvisa.com`  
构建命令：`cd frontend/web && npm ci && npm run build`  
输出目录：`frontend/web/dist`

---

## 第三步：DNS 记录清单（Tunnel 方案）

setup 脚本会自动创建；手动配置时参考 `dns-records.template.json`。

| 类型 | 名称 | 目标 |
|------|------|------|
| CNAME | `@` | `<TUNNEL_ID>.cfargotunnel.com` |
| CNAME | `www` | `<TUNNEL_ID>.cfargotunnel.com` |
| CNAME | `api` | `<TUNNEL_ID>.cfargotunnel.com` |

> `@` 根域 CNAME 需要 Cloudflare **CNAME flattening**（Pro 以下也支持 flattening）。

---

## 第四步：更新项目环境变量

Tunnel 或 VPS 跑通后，改生产 env：

```bash
# backend/.env（生产）
APP_FRONTEND_BASE=https://htexvisa.com
CORS_ALLOWED_ORIGINS=https://htexvisa.com,https://www.htexvisa.com
PUBLIC_BASE_URL=https://api.htexvisa.com

# frontend/web/.env.production
VITE_API_BASE=https://api.htexvisa.com/api
VITE_WS_URL=wss://api.htexvisa.com
VITE_GOOGLE_CLIENT_ID=<你的>.apps.googleusercontent.com
```

**Google OAuth Console** 加 Authorized origins（主用根域，只需根域即可）：
- `https://htexvisa.com`

**Stripe Webhook**：
- `https://api.htexvisa.com/api/v2/payment/notify`

**Resend 发信域**（`noreply@htexvisa.com`）：
- Cloudflare DNS 加 Resend 提供的 SPF / DKIM TXT（见 Resend Dashboard → Domains）

---

## 第五步：验证

```bash
bash pm/infra/cloudflare/verify_dns.sh
```

期望输出：
```
✓ htexvisa.com      → 200/301
✓ api.htexvisa.com  → 200 /health
```

---

## 邮件 DNS（Resend）

在 Cloudflare → DNS → Records 添加 Resend 给的记录，典型示例：

| 类型 | 名称 | 内容 |
|------|------|------|
| TXT | `@` | `v=spf1 include:amazonses.com ~all` |
| TXT | `resend._domainkey` | `(Resend 提供的 DKIM)` |
| MX | `@` | （若只用 Resend API 发信，通常不需要收信 MX） |

---

## 常见问题

### Q: 访问 htexvisa.com 显示 Error 1033 / 522
- Tunnel 没跑 → `cloudflared tunnel run htex-visa`
- 或 VPS 没监听 / 防火墙拦了

### Q: API CORS 报错
- 确认 `CORS_ALLOWED_ORIGINS` 含 `https://htexvisa.com`
- 重启 backend

### Q: WebSocket 连不上
- Tunnel config 里 `api.htexvisa.com` 需配 `originRequest.noTLSVerify` 等（见 `config.yml.example`）
- 前端 `VITE_WS_URL=wss://api.htexvisa.com`

### Q: 和临时 trycloudflare 的区别
- `start_cloudflared.sh` = 随机临时域名，联调用
- `setup_named_tunnel.sh` = 固定 `htexvisa.com`，生产用

---

## 文件索引

| 文件 | 说明 |
|------|------|
| `setup_named_tunnel.sh` | 创建 Tunnel + DNS + 本地 config |
| `config.yml.example` | Tunnel 路由模板 |
| `verify_dns.sh` | DNS / HTTP 健康检查 |
| `dns-records.template.json` | 手动 DNS 参考 |

---

## Mac 先跑、后面迁云服务器

**可以。** Tunnel 和域名是绑在 Cloudflare 账号上的，不绑死某台机器。

### 现在（Mac 演示 / 开发）

```bash
bash pm/infra/cloudflare/start_mac.sh        # 一键起 backend + frontend + tunnel
bash pm/infra/cloudflare/start_mac.sh --stop # 停止
```

Mac 关机或关 Tunnel → 外网访问会 502，DNS 和证书不受影响。

### 以后迁 VPS 的两种方式

| 方式 | 做法 | 适合 |
|------|------|------|
| **A. 搬 Tunnel** | 把 `~/.cloudflared/`（config + credentials json）拷到 VPS，`cloudflared tunnel run htex-visa` | 不想开 80/443、无固定 IP |
| **B. 改 DNS** | VPS 上 docker compose + Nginx；Cloudflare DNS 把 `@/www/api` 从 CNAME 改成 A 记录指 VPS IP | 正式生产、7×24 |

迁 VPS 时只需改 **origin 地址**（Tunnel config 里的 `localhost:8000` → VPS 内网地址），**域名不用换**。

### 当前 Tunnel 信息

| 项 | 值 |
|----|-----|
| Tunnel 名 | `htex-visa` |
| Tunnel ID | `b65e732f-bff0-4bdf-9dfc-aea8e0362b7a` |
| 配置 | `~/.cloudflared/config.yml` |
| 凭证 | `~/.cloudflared/b65e732f-bff0-4bdf-9dfc-aea8e0362b7a.json`（勿泄露、勿提交 git） |

---

## 修订

| 日期 | 变更 |
|------|------|
| 2026-07-12 | 初版：htexvisa.com 已在 CF，补 Tunnel + DNS 方案 |
