#!/usr/bin/env bash
# Install cloudflared on Alibaba server and run existing htex-visa tunnel (reuse Mac auth).
# Copies credentials from local ~/.cloudflared — no DNS changes needed.
#
# Run on Mac:
#   bash pm/infra/aliyun/setup-cloudflared-tunnel.sh

set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/htex_aliyun}"
SERVER="${SERVER:-root@47.77.178.213}"
TUNNEL_ID="b65e732f-bff0-4bdf-9dfc-aea8e0362b7a"
LOCAL_CF="$HOME/.cloudflared"
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SERVER" bash -s <<'REMOTE'
set -euo pipefail
if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
  dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
fi
mkdir -p /root/.cloudflared
chmod 700 /root/.cloudflared
REMOTE

scp -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new \
  "$LOCAL_CF/${TUNNEL_ID}.json" \
  "$SERVER:/root/.cloudflared/${TUNNEL_ID}.json"

scp -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new \
  "$REPO_ROOT/pm/infra/aliyun/cloudflared-config.server.yml" \
  "$SERVER:/root/.cloudflared/config.yml"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SERVER" bash -s <<'REMOTE'
set -euo pipefail
chmod 600 /root/.cloudflared/*.json

cat > /etc/systemd/system/cloudflared-htex.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel htex-visa (api.htexvisa.com)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel --config /root/.cloudflared/config.yml run htex-visa
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable cloudflared-htex
systemctl restart cloudflared-htex
sleep 3
systemctl is-active cloudflared-htex
cloudflared tunnel info htex-visa 2>&1 | head -8
REMOTE

echo ""
echo "Done. Test: curl https://api.htexvisa.com/health"
