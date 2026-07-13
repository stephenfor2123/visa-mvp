#!/usr/bin/env bash
# pm/infra/cloudflare/verify_dns.sh — 检查 htexvisa.com DNS 与 HTTP 可达性

set -euo pipefail

DOMAIN="${DOMAIN:-htexvisa.com}"
API_HOST="api.${DOMAIN}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }
info() { echo -e "${YELLOW}→${NC} $*"; }

echo "=== DNS (@1.1.1.1) ==="
for H in "$DOMAIN" "www.$DOMAIN" "$API_HOST"; do
  REC=$(dig @1.1.1.1 +short "$H" CNAME 2>/dev/null | head -1)
  AREC=$(dig @1.1.1.1 +short "$H" A 2>/dev/null | head -1)
  if [ -n "$REC" ]; then
    pass "$H CNAME → $REC"
  elif [ -n "$AREC" ]; then
    pass "$H A → $AREC"
  else
    fail "$H — 无 DNS 记录"
  fi
done

echo ""
echo "=== HTTP ==="
check_url() {
  local url="$1"
  local label="$2"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 -L "$url" 2>/dev/null || echo "000")
  if [[ "$code" =~ ^(200|301|302|307|308)$ ]]; then
    pass "$label → HTTP $code"
  else
    fail "$label → HTTP $code (或超时)"
  fi
}

check_url "https://${DOMAIN}" "https://${DOMAIN}"
check_url "https://${API_HOST}/health" "https://${API_HOST}/health"

echo ""
echo "=== Cloudflare NS ==="
dig +short "$DOMAIN" NS | while read -r ns; do
  info "NS: $ns"
done

echo ""
info "Tunnel 未启动时 api/health 会失败 — 先 cloudflared tunnel run htex-visa"
