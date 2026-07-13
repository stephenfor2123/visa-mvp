#!/usr/bin/env bash
# pm/infra/cloudflare/start_mac.sh
# Mac 本地 + Cloudflare Tunnel 一键启动（开发/演示用）
#
# 用法:
#   bash pm/infra/cloudflare/start_mac.sh          # 启动 backend + frontend + tunnel
#   bash pm/infra/cloudflare/start_mac.sh --stop   # 停止全部

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend/web"
PID_DIR="$SCRIPT_DIR/.pids"
TUNNEL_NAME="${TUNNEL_NAME:-htex-visa}"

mkdir -p "$PID_DIR"

stop_all() {
  for f in tunnel frontend backend; do
    pf="$PID_DIR/$f.pid"
    if [ -f "$pf" ]; then
      pid=$(cat "$pf" 2>/dev/null || true)
      if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        echo "stopped $f (pid $pid)"
      fi
      rm -f "$pf"
    fi
  done
}

if [ "${1:-}" = "--stop" ]; then
  stop_all
  exit 0
fi

stop_all

echo "→ backend :8000"
cd "$BACKEND_DIR"
nohup .venv/bin/python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
  > "$PID_DIR/backend.log" 2>&1 &
echo $! > "$PID_DIR/backend.pid"

echo "→ frontend :5173"
cd "$FRONTEND_DIR"
nohup npm run dev -- --host 0.0.0.0 --port 5173 \
  > "$PID_DIR/frontend.log" 2>&1 &
echo $! > "$PID_DIR/frontend.pid"

sleep 3

echo "→ cloudflared tunnel $TUNNEL_NAME"
nohup cloudflared tunnel run "$TUNNEL_NAME" \
  > "$PID_DIR/tunnel.log" 2>&1 &
echo $! > "$PID_DIR/tunnel.pid"

sleep 2
echo ""
echo "══════════════════════════════════════════"
echo "  https://htexvisa.com"
echo "  https://api.htexvisa.com/health"
echo ""
echo "  日志: $PID_DIR/*.log"
echo "  停止: bash pm/infra/cloudflare/start_mac.sh --stop"
echo "══════════════════════════════════════════"
