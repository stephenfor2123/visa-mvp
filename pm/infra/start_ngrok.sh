#!/usr/bin/env bash
# pm/infra/start_ngrok.sh
# 用途: 一键起 ngrok http 8000, 自动读临时域名, 写 backend/.env 的 PUBLIC_BASE_URL
# 依赖: ngrok (https://ngrok.com/download) + jq + 有效 authtoken
# 备选: 没 ngrok 时自动降级到 cloudflared(看 start_cloudflared.sh)

set -euo pipefail

# ---------- 配色 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[ngrok]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[ngrok]${NC} $*" >&2; }
err()  { echo -e "${RED}[ngrok]${NC} $*" >&2; }
ok()   { echo -e "${GREEN}[ngrok]${NC} $*" >&2; }

# ---------- 路径(相对调用者) ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
BACKEND_ENV="$BACKEND_DIR/.env"
NGROK_LOG="$PROJECT_ROOT/pm/infra/.ngrok.log"
NGROK_API_LOG="$PROJECT_ROOT/pm/infra/.ngrok-api.log"
PID_FILE="$PROJECT_ROOT/pm/infra/.ngrok.pid"

# ---------- 端口 ----------
PORT="${PORT:-8000}"

# ---------- 检查工具 ----------
require() {
  command -v "$1" >/dev/null 2>&1 || {
    err "需要 $1,但未安装"
    return 1
  }
}

require jq || { err "请先 brew install jq"; exit 1; }

# ---------- ngrok 安装检查 ----------
if ! command -v ngrok >/dev/null 2>&1; then
  warn "ngrok 未安装,自动降级到 cloudflared"
  exec "$SCRIPT_DIR/start_cloudflared.sh" "$@"
fi

# ---------- authtoken 检查 ----------
NGROK_TOKEN="${NGROK_TOKEN:-}"
NGROK_CONFIG="${NGROK_CONFIG:-$HOME/.config/ngrok/ngrok.yml}"

if [ -z "$NGROK_TOKEN" ]; then
  # 尝试从配置文件读
  if [ -f "$NGROK_CONFIG" ]; then
    NGROK_TOKEN=$(grep -E "^authtoken:" "$NGROK_CONFIG" 2>/dev/null | awk '{print $2}' | head -1 || true)
  fi
fi

if [ -z "$NGROK_TOKEN" ]; then
  err "未找到 NGROK_TOKEN"
  echo "请先:"
  echo "  1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken 注册/登录拿 token"
  echo "  2. 跑 ngrok config add-authtoken <TOKEN>"
  echo "  3. 或 export NGROK_TOKEN=<TOKEN> 后重跑"
  exit 1
fi

# ---------- 后端检查 ----------
if [ ! -d "$BACKEND_DIR" ]; then
  err "backend 目录不存在: $BACKEND_DIR"
  exit 1
fi

# ---------- 已有进程清理 ----------
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    warn "已有 ngrok 进程 PID=$OLD_PID, 正在 kill..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

# ---------- 起 ngrok(后台) ----------
log "启动 ngrok http $PORT ..."
nohup ngrok http "$PORT" --authtoken "$NGROK_TOKEN" --log "$NGROK_LOG" > "$NGROK_API_LOG" 2>&1 &
NGROK_PID=$!
echo "$NGROK_PID" > "$PID_FILE"
ok "ngrok PID=$NGROK_PID, 日志: $NGROK_LOG"

# ---------- 等 API 就绪 ----------
log "等待 ngrok API 就绪(最多 15s)..."
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:4040/api/tunnels >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# ---------- 读临时域名 ----------
PUBLIC_URL=""
for i in $(seq 1 10); do
  TUNNELS_JSON=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null || true)
  if [ -n "$TUNNELS_JSON" ]; then
    PUBLIC_URL=$(echo "$TUNNELS_JSON" | jq -r '.tunnels[]? | select(.proto=="https") | .public_url' 2>/dev/null | head -1)
    if [ -z "$PUBLIC_URL" ]; then
      PUBLIC_URL=$(echo "$TUNNELS_JSON" | jq -r '.tunnels[]? | .public_url' 2>/dev/null | head -1)
    fi
    if [ -n "$PUBLIC_URL" ] && [ "$PUBLIC_URL" != "null" ]; then
      break
    fi
  fi
  sleep 0.5
done

if [ -z "$PUBLIC_URL" ] || [ "$PUBLIC_URL" = "null" ]; then
  err "没拿到临时域名,看日志: $NGROK_LOG"
  exit 1
fi

ok "临时域名: $PUBLIC_URL"

# ---------- 写 backend/.env ----------
mkdir -p "$BACKEND_DIR"
touch "$BACKEND_ENV"

# 用 sed 替换或追加 PUBLIC_BASE_URL
if grep -qE "^PUBLIC_BASE_URL=" "$BACKEND_ENV"; then
  # macOS/BSD sed 兼容写法
  sed -i.bak "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$PUBLIC_URL|" "$BACKEND_ENV"
  rm -f "$BACKEND_ENV.bak"
  log "更新 PUBLIC_BASE_URL"
else
  echo "PUBLIC_BASE_URL=$PUBLIC_URL" >> "$BACKEND_ENV"
  log "追加 PUBLIC_BASE_URL"
fi

ok "已写入 $BACKEND_ENV"
echo ""
echo "════════════════════════════════════════════════════════"
echo "  ngrok 临时域名: $PUBLIC_URL"
echo "  backend/.env   : $BACKEND_ENV"
echo "  ngrok Web UI   : http://127.0.0.1:4040"
echo "  PID            : $NGROK_PID"
echo "════════════════════════════════════════════════════════"
echo ""
echo "接下来:"
echo "  1. 起后端: cd $BACKEND_DIR && uvicorn app.main:app --reload --port $PORT"
echo "  2. 前端调用: 登录页的 API base 改 \$PUBLIC_BASE_URL/api/v2"
echo "  3. 停 ngrok: kill \$(cat $PID_FILE)"
echo "  4. 装开机自启: bash $SCRIPT_DIR/install_autostart.sh"
