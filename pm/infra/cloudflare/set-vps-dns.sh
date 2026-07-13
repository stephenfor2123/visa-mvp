#!/usr/bin/env bash
# Point api.htexvisa.com (and optionally @/www) to Alibaba VPS via Cloudflare A records.
#
# Prereq: Cloudflare API token with Zone.DNS Edit on htexvisa.com
#   export CF_API_TOKEN=your_token
#
# Usage:
#   CF_API_TOKEN=xxx VPS_IP=47.77.178.213 bash pm/infra/cloudflare/set-vps-dns.sh
#   CF_API_TOKEN=xxx VPS_IP=47.77.178.213 RECORDS=api bash pm/infra/cloudflare/set-vps-dns.sh

set -euo pipefail

DOMAIN="${DOMAIN:-htexvisa.com}"
VPS_IP="${VPS_IP:-47.77.178.213}"
RECORDS="${RECORDS:-api}"   # api | all  (all = @, www, api)
CF_API_TOKEN="${CF_API_TOKEN:-${CLOUDFLARE_API_TOKEN:-}}"

if [ -z "$CF_API_TOKEN" ]; then
  echo "ERROR: set CF_API_TOKEN (Zone.DNS Edit for ${DOMAIN})"
  echo "  Cloudflare Dashboard → My Profile → API Tokens → Create Token"
  echo "  Template: Edit zone DNS → Zone: ${DOMAIN}"
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
[ -n "$ZONE_ID" ] || { echo "zone not found"; exit 1; }

upsert_a() {
  local name="$1"
  local fqdn="${name}"
  [ "$name" = "@" ] && fqdn="${DOMAIN}" || fqdn="${name}.${DOMAIN}"

  echo "→ ${fqdn} → A ${VPS_IP}"
  EXISTING=$(api GET "/zones/${ZONE_ID}/dns_records?type=A&name=${fqdn}")
  RECORD_ID=$(echo "$EXISTING" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['id'] if r else '')")

  PAYLOAD=$(python3 - <<PY
import json
print(json.dumps({
  "type": "A",
  "name": "${name}",
  "content": "${VPS_IP}",
  "proxied": True,
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

if [ "$RECORDS" = "all" ]; then
  upsert_a "@"
  upsert_a "www"
fi
upsert_a "api"

echo ""
echo "Done. Wait ~30s then: curl https://api.${DOMAIN}/health"
