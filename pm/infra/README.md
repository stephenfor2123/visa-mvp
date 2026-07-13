# pm/infra · 临时域名方案

> 让本机 backend (localhost:8000) 暴露到公网, 给前端 / 真机 / 协作者用.
> 两个方案: **ngrok(推荐)** + **cloudflared(零配置备选)**

---

## 0. 快速决定:用哪个?

| 维度 | ngrok | cloudflared |
|------|-------|-------------|
| 注册账号 | 必需(免费层 OK) | **不需要** |
| 启动速度 | ~1-2s | ~3-5s |
| 域名稳定性 | 免费层每次随机 | 每次随机(quick tunnel) |
| 持久域名 | 付费($8/月起) | 需绑 CF 账号(免费) |
| Web UI 调试 | **http://127.0.0.1:4040**(看流量)| 无 |
| 自动重连 | KeepAlive plist | 内置 |
| macOS 安装 | `brew install ngrok` 或官网 | `brew install cloudflared` |
| 配置文件 | `~/.config/ngrok/ngrok.yml` | 无 |

**推荐**:
- 日常联调 → **ngrok**(有 Web UI 调试,体验好)
- 临时分享 / 不想注册 → **cloudflared**(零摩擦)
- 团队稳定域名 → ngrok 付费 或 cloudflared 绑 CF 账号
- **生产固定域名 (htexvisa.com)** → 见 [`cloudflare/README.md`](cloudflare/README.md)

---

## 1. ngrok(推荐)

### 1.1 一次性安装

```bash
# 1. 安装
brew install ngrok

# 2. 注册拿 token: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken 2_xxxxxxxxxxxxxxxxxxxxxx

# 3. 验证
ngrok version
```

### 1.2 一键启动

```bash
# 默认端口 8000
bash pm/infra/start_ngrok.sh

# 自定义端口
PORT=8080 bash pm/infra/start_ngrok.sh
```

执行效果:
```
[ngrok] 启动 ngrok http 8000 ...
[ngrok] 临时域名: https://a1b2c3d4.ngrok-free.app
[ngrok] 已写入 backend/.env
═══════════════════════════════════════════════════════
  ngrok 临时域名: https://a1b2c3d4.ngrok-free.app
  backend/.env   : /Users/.../backend/.env
  ngrok Web UI   : http://127.0.0.1:4040
═══════════════════════════════════════════════════════
```

### 1.3 开机自启(Mac)

```bash
# 装 launchd plist
bash pm/infra/install_autostart.sh

# 验证
launchctl list | grep visa-mvp

# 卸载
bash pm/infra/install_autostart.sh --uninstall
```

启动后,ngrok 域名会出现在 `backend/.env`,后端读这个值给前端用。

### 1.4 停掉

```bash
kill $(cat pm/infra/.ngrok.pid)
```

### 1.5 Web UI 调试

浏览器开 **http://127.0.0.1:4040**:
- 看每个请求的 Header / Body / 响应
- replay 请求
- 看 status code 统计
- 排查 CORS / Auth 头问题特别好用

---

## 2. cloudflared(备选,零配置)

### 2.1 安装

```bash
brew install cloudflared
```

### 2.2 一键启动

```bash
bash pm/infra/start_cloudflared.sh

# 端口自定义
PORT=8080 bash pm/infra/start_cloudflared.sh
```

执行效果:
```
[cloudflared] 启动 cloudflared tunnel --url http://localhost:8000 ...
[cloudflared] 临时域名: https://xxxx-yyyy.trycloudflare.com
[cloudflared] 已写入 backend/.env
```

### 2.3 停掉

```bash
kill $(cat pm/infra/.cloudflared.pid)
```

### 2.4 没有 Web UI

需要看请求时: `tail -f pm/infra/.cloudflared.log`

---

## 3. 完整启动顺序(W1 demo 联调用)

```bash
# 终端 1: 起 ngrok
bash pm/infra/start_ngrok.sh
# 复制输出的临时域名,例如: https://a1b2c3d4.ngrok-free.app

# 终端 2: 起后端
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 3: 起前端 Web
cd frontend/web
npm run dev

# 浏览器开前端: http://localhost:5173
# 登录页 API base 改成: https://a1b2c3d4.ngrok-free.app/api/v2
# (从 import.meta.env.VITE_API_BASE_URL 读,或者硬编码)
```

---

## 4. 配置文件优先级

| 来源 | 优先级 | 说明 |
|------|--------|------|
| 环境变量 `NGROK_TOKEN` | 1 | 最高, 临时用 |
| `~/.config/ngrok/ngrok.yml` | 2 | `ngrok config add-authtoken` 写的 |
| plist 里 `<key>NGROK_TOKEN</key>` | 3 | 启动 launchd 时用 |

**生产建议**:把 token 放在 macOS 钥匙串,不进代码不进 plist。

```bash
# 存钥匙串
security add-generic-password -a "ngrok" -s "ngrok-token" -w "2_xxxxxx"

# 读出来跑
NGROK_TOKEN=$(security find-generic-password -a "ngrok" -s "ngrok-token" -w) bash pm/infra/start_ngrok.sh
```

---

## 5. 常见问题

### 5.1 ngrok 启动后访问域名,提示 "Visit Site"
- 正常!免费版需要点一下"Visit Site"按钮才能进,付费版不会.
- 多次访问后,ngrok 会自动通过.

### 5.2 域名变化了,前端没更新
- 域名是动态的(每次启动都变),前端最好从 `import.meta.env.VITE_PUBLIC_BASE_URL` 读
- 后端起的时候确保 backend/.env 的 `PUBLIC_BASE_URL` 跟前端的一致

### 5.3 ngrok quota 用完了
- 免费版: 1 GB / 月,40 req/min
- 超了 → 换 cloudflared 备选,或买付费

### 5.4 cloudflared "too many connections"
- quick tunnel 有连接数限制
- 多人联调时建议绑 CF 账号建 named tunnel

### 5.5 后端 CORS 没配临时域名
- backend/.env 的 `CORS_ORIGINS` 加 `https://*.ngrok-free.app,https://*.trycloudflare.com`
- 重启后端生效

---

## 6. 决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-06-11 | 默认推荐 ngrok | Web UI 调试好 + 团队熟悉 |
| 2026-06-11 | cloudflared 备选 | 零账号 + 兜底 |
| 2026-06-11 | token 放钥匙串 | 团队安全规范 |

---

## 7. 修订记录

| 日期 | 变更人 | 变更 |
|------|--------|------|
| 2026-06-11 | PM | 初版 |
