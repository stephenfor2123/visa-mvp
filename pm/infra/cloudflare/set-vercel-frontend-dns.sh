#!/usr/bin/env bash
# Point @ and www to Vercel via Cloudflare API. Leaves api.* (Tunnel) untouched.
#
# Prereq: API token with Zone.DNS Edit on htexvisa.com
#   https://dash.cloudflare.com/profile/api-tokens → Edit zone DNS
#
# Usage:
#   CF_API_TOKEN=xxx bash pm/infra/cloudflare/set-vercel-frontend-dns.sh

set -euo pipefail

DOMAIN="${DOMAIN:-htexvisa.com}"
VERCEL_APEX_IP="${VERCEL_APEX_IP:-76.76.21.21}"
VERCEL_WWW_CNAME="${VERCEL_WWW_CNAME:-cname.vercel-dns.com}"
PROXIED="${PROXIED:-false}"   # grey cloud recommended for Vercel
CF_API_TOKEN="${CF_API_TOKEN:-${CLOUDFLARE_API_TOKEN:-}}"

if [ -z "$CF_API_TOKEN" ]; then
  echo "ERROR: CF_API_TOKEN not set."
  echo ""
  echo "本机 ~/.cloudflared/cert.pem 是 Tunnel 授权，不能改 DNS。"
  echo "需要单独创建 API Token："
  echo "  Dashboard → My Profile → API Tokens → Edit zone DNS → Zone: ${DOMAIN}"
  echo ""
  echo "然后运行："
  echo "  CF_API_TOKEN=你的token bash pm/infra/cloudflare/set-vercel-frontend-dns.sh"
  exit 1
fi

api() {
  curl -fsS -X "$1" "https://api.cloudflare.com/client/v4$2" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    "${@:3}"
}

echo "→ zone ${DOMAIN}"
ZONE_JSON=$(api GET "/zones?name=${DOMAIN}")
ZONE_ID=$(echo "$ZONE_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')")
[ -n "$ZONE_ID" ] || { echo "zone not found or token lacks permission"; exit 1; }

upsert_record() {
  local rtype="$1"
  local name="$2"
  local content="$3"
  local fqdn="${name}"
  [ "$name" = "@" ] && fqdn="${DOMAIN}" || fqdn="${name}.${DOMAIN}"

  echo "→ ${fqdn} ${rtype} ${content}"
  EXISTING=$(api GET "/zones/${ZONE_ID}/dns_records?type=${rtype}&name=${fqdn}")
  RECORD_ID=$(echo "$EXISTING" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['id'] if r else '')")

  PAYLOAD=$(python3 - <<PY
import json
proxied = "${PROXIED}" in ("true", "True", "1")
print(json.dumps({
  "type": "${rtype}",
  "name": "${name}",
  "content": "${content}",
  "proxied": proxied,
  "ttl": 1,
}))
PY
)
  if [ -n "$RECORD_ID" ]; then
    api PUT "/zones/${ZONE_ID}/dns_records/${RECORD_ID}" --data "$PAYLOAD" >/dev/null
    echo "  updated"
  else
    api POST "/zones/${ZONE_ID}/dns_records" --data "$PAYLOAD" >/dev/null
    echo "  created"
  fi
}

# Remove stale Tunnel CNAME on apex/www if present (Vercel needs A + CNAME, not tunnel)
delete_tunnel_cname() {
  local name="$1"
  local fqdn="${name}"
  [ "$name" = "@" ] && fqdn="${DOMAIN}" || fqdn="${name}.${DOMAIN}"

  EXISTING=$(api GET "/zones/${ZONE_ID}/dns_records?type=CNAME&name=${fqdn}" || true)
  RECORD_ID=$(echo "$EXISTING" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['id'] if r else '')" 2>/dev/null || true)
  CONTENT=$(echo "$EXISTING" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0].get('content','') if r else '')" 2>/dev/null || true)
  if [ -n "$RECORD_ID" ] && echo "$CONTENT" | grep -q 'cfargotunnel.com'; then
    api DELETE "/zones/${ZONE_ID}/dns_records/${RECORD_ID}" >/dev/null
    echo "  deleted old Tunnel CNAME for ${fqdn}"
  fi
}

delete_tunnel_cname "@"
delete_tunnel_cname "www"
upsert_record "A" "@" "${VERCEL_APEX_IP}"
upsert_record "CNAME" "www" "${VERCEL_WWW_CNAME}"

echo ""
echo "Done (api.* untouched). Wait ~1 min then:"
echo "  curl -I https://${DOMAIN}"
echo "  curl -I https://www.${DOMAIN}"
echo "  curl https://api.${DOMAIN}/health"
