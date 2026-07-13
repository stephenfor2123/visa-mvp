#!/usr/bin/env bash
# pm/infra/aliyun/deploy-htexvisa.sh
# One-shot deploy on a fresh Ubuntu 24.04 VPS (Alibaba Cloud etc.)
#
# Prereqs on server:
#   - /opt/visa-mvp exists (git clone or rsync from dev machine)
#   - backend/.env present with prod secrets (see backend/.env.example)
#
# Usage (on server as root):
#   bash /opt/visa-mvp/pm/infra/aliyun/deploy-htexvisa.sh
#
# Optional env:
#   SKIP_APT=1          skip apt install (re-run)
#   SKIP_FRONTEND_BUILD=1   use existing /var/www/htexvisa

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/visa-mvp}"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend/web"
WEB_ROOT="/var/www/htexvisa"
NGINX_SITE="/etc/nginx/sites-available/htexvisa"

log() { echo "[deploy] $*"; }
die() { echo "[deploy] ERROR: $*" >&2; exit 1; }

[ -d "$BACKEND_DIR" ] || die "missing $BACKEND_DIR — clone repo to /opt/visa-mvp first"
[ -f "$BACKEND_DIR/.env" ] || die "missing $BACKEND_DIR/.env — copy from dev machine first"

if [ "${SKIP_APT:-0}" != "1" ]; then
  log "installing packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get upgrade -y -qq
  apt-get install -y -qq git curl nginx ufw ca-certificates gnupg

  if ! command -v docker >/dev/null 2>&1; then
    log "installing docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
  fi

  if ! command -v node >/dev/null 2>&1 || ! node -v | grep -qE '^v20'; then
    log "installing node 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
  fi

  ufw allow 22/tcp || true
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
  ufw --force enable || true
fi

log "patching docker-compose for production..."
COMPOSE="$BACKEND_DIR/docker-compose.yml"
if grep -q '\-\-reload' "$COMPOSE"; then
  sed -i 's/ --reload//' "$COMPOSE"
fi
if ! grep -q 'env_file:' "$COMPOSE"; then
  sed -i '/container_name: visa-mvp-backend/a\    env_file:\n      - .env' "$COMPOSE"
fi
sed -i '/^      ENV: dev$/d' "$COMPOSE" || true

log "starting backend (docker compose)..."
cd "$BACKEND_DIR"
docker compose up -d --build
sleep 5
curl -fsS "http://127.0.0.1:8000/health" >/dev/null || die "backend health check failed — run: docker compose logs backend"

if [ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]; then
  log "building frontend..."
  cd "$FRONTEND_DIR"
  if [ -f .env.production ] && [ ! -f .env ]; then
    cp .env.production .env
  fi
  npm ci --silent
  npm run build
  mkdir -p "$WEB_ROOT"
  rm -rf "${WEB_ROOT:?}/"*
  cp -r dist/* "$WEB_ROOT/"
fi

log "configuring nginx..."
cat > "$NGINX_SITE" <<'NGINX'
server {
    listen 80;
    server_name htexvisa.com www.htexvisa.com;
    root /var/www/htexvisa;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name api.htexvisa.com;
    client_max_body_size 20m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
NGINX

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/htexvisa
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

log "done."
echo ""
echo "  Local checks:"
echo "    curl http://127.0.0.1:8000/health"
echo "    curl -I http://127.0.0.1/"
echo ""
echo "  Cloudflare DNS (orange proxy):"
echo "    A  @   -> $(curl -fsS ifconfig.me 2>/dev/null || echo '<VPS_IP>')"
echo "    A  www -> same"
echo "    A  api -> same"
echo ""
echo "  Then open: https://htexvisa.com"
