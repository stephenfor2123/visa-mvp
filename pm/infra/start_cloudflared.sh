#!/usr/bin/env bash
# pm/infra/start_cloudflared.sh
# 备选方案: 用 cloudflared 暴露 8000, 不需要注册账号
# 比 ngrok 慢一点点启动, 但零配置

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[cloudflared]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[cloudflared]${NC} $*" >&2; }
err()  { echo -e "${RED}[cloudflared]${NC} $*" >&2; }
ok()   { echo -e "${GREEN}[cloudflared]${NC} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
BACKEND_ENV="$BACKEND_DIR/.env"
CF_LOG="$PROJECT_ROOT/pm/infra/.cloudflared.log"
PID_FILE="$PROJECT_ROOT/pm/infra/.cloudflared.pid"

PORT="${PORT:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
  err "cloudflared 未安装"
  echo "安装: brew install cloudflared"
  exit 1
fi

# ---------- 清理旧进程 ----------
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    warn "已有 cloudflared PID=$OLD_PID, kill..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

# ---------- 起 cloudflared(后台,quick tunnel 免账号) ----------
log "启动 cloudflared tunnel --url http://localhost:$PORT ..."
nohup cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate > "$CF_LOG" 2>&1 &
CF_PID=$!
echo "$CF_PID" > "$PID_FILE"
ok "cloudflared PID=$CF_PID, 日志: $CF_LOG"

# ---------- 等就绪(从 log 里 parse URL) ----------
log "等待 URL 出现(最多 30s)..."
PUBLIC_URL=""
for i in $(seq 1 60); do
  if [ -f "$CF_LOG" ]; then
    PUBLIC_URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$CF_LOG" 2>/dev/null | head -1 || true)
    if [ -n "$PUBLIC_URL" ]; then
      break
    fi
  fi
  sleep 0.5
done

if [ -z "$PUBLIC_URL" ]; then
  err "没拿到 trycloudflare URL, 看日志: $CF_LOG"
  exit 1
fi

ok "临时域名: $PUBLIC_URL"

# ---------- 写 backend/.env ----------
mkdir -p "$BACKEND_DIR"
touch "$BACKEND_ENV"
if grep -qE "^PUBLIC_BASE_URL=" "$BACKEND_ENV"; then
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
echo "  cloudflared 临时域名: $PUBLIC_URL"
echo "  backend/.env        : $BACKEND_ENV"
echo "  PID                  : $CF_PID"
echo "════════════════════════════════════════════════════════"
echo ""
echo "接下来:"
echo "  1. 起后端: cd $BACKEND_DIR && uvicorn app.main:app --reload --port $PORT"
echo "  2. 停 cloudflared: kill \$(cat $PID_FILE)"
