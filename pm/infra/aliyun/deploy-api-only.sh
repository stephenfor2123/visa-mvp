#!/usr/bin/env bash
# pm/infra/aliyun/deploy-api-only.sh
# Backend-only deploy: FastAPI + Redis + Nginx (api.htexvisa.com)
# Frontend is hosted on Vercel — do NOT build/serve static files here.
#
# Usage on server:
#   bash /opt/visa-mvp/pm/infra/aliyun/deploy-api-only.sh

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/visa-mvp}"
BACKEND_DIR="$REPO_ROOT/backend"
NGINX_SITE="/etc/nginx/sites-available/htex-api"

log() { echo "[deploy-api] $*"; }
die() { echo "[deploy-api] ERROR: $*" >&2; exit 1; }

[ -d "$BACKEND_DIR" ] || die "missing $BACKEND_DIR"
[ -f "$BACKEND_DIR/.env" ] || die "missing $BACKEND_DIR/.env"

if [ "${SKIP_APT:-0}" != "1" ]; then
  log "installing packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq curl nginx ufw ca-certificates gnupg

  if ! command -v docker >/dev/null 2>&1; then
    log "installing docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
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

log "starting backend..."
cd "$BACKEND_DIR"
docker compose up -d --build
sleep 8
curl -fsS "http://127.0.0.1:8000/health" >/dev/null || die "health check failed — docker compose logs backend"

log "configuring nginx (api only)..."
cat > "$NGINX_SITE" <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name api.htexvisa.com;
    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
NGINX

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/htex-api
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

log "done."
echo ""
echo "  curl http://127.0.0.1:8000/health"
echo "  Cloudflare DNS: A api -> $(curl -fsS --max-time 5 ifconfig.me 2>/dev/null || echo '47.77.178.213')"
echo "  Frontend: deploy frontend/web on Vercel, point htexvisa.com there"
