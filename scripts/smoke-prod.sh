#!/usr/bin/env bash
# Post-deploy smoke checks against production (or override hosts).
# Usage:
#   bash scripts/smoke-prod.sh
#   FRONTEND_URL=https://htexvisa.com API_URL=https://api.htexvisa.com bash scripts/smoke-prod.sh
set -euo pipefail

FRONTEND_URL="${FRONTEND_URL:-https://htexvisa.com}"
API_URL="${API_URL:-https://api.htexvisa.com}"

fail=0
ok() { echo "  OK  $*"; }
bad() { echo "  FAIL $*"; fail=1; }

echo "smoke-prod"
echo "  frontend: $FRONTEND_URL"
echo "  api:      $API_URL"

# 1) API health
code=$(curl -sS -o /tmp/smoke-health.json -w "%{http_code}" "$API_URL/health" || true)
if [ "$code" = "200" ] && grep -q '"status":"ok"' /tmp/smoke-health.json; then
  ok "GET /health → 200 ok"
else
  bad "GET /health → $code $(cat /tmp/smoke-health.json 2>/dev/null | head -c 120)"
fi

# 2) Admin login must not 500 (401/2001 = app alive)
code=$(curl -sS -o /tmp/smoke-admin.json -w "%{http_code}" \
  -X POST "$API_URL/api/v2/admin/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"smoke","password":"invalid"}' || true)
if [ "$code" = "500" ]; then
  bad "POST /admin/login → 500 (Pydantic/env regression?)"
elif [ "$code" = "000" ]; then
  bad "POST /admin/login → unreachable"
else
  ok "POST /admin/login → $code (not 500)"
fi

# 3) Consent route exists (401 without auth is fine; 404/405 means routing broken)
code=$(curl -sS -o /tmp/smoke-consent.json -w "%{http_code}" \
  -X POST "$API_URL/api/v2/profile/consents" \
  -H 'Content-Type: application/json' \
  -d '{"purpose":"sensitive_upload","version":"v1"}' || true)
case "$code" in
  401|403) ok "POST /profile/consents → $code (auth required, route live)" ;;
  404|405) bad "POST /profile/consents → $code (route missing/wrong method)" ;;
  500) bad "POST /profile/consents → 500" ;;
  000) bad "POST /profile/consents → unreachable" ;;
  *) ok "POST /profile/consents → $code" ;;
esac

# 4) Frontend login page loads
code=$(curl -sS -o /tmp/smoke-login.html -w "%{http_code}" "$FRONTEND_URL/login" || true)
if [ "$code" != "200" ]; then
  bad "GET /login → $code"
else
  ok "GET /login → 200"
fi

# 5) Google client id baked into assets (button visibility)
index_js=$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' /tmp/smoke-login.html | head -1 || true)
if [ -z "$index_js" ]; then
  # SPA may only reference from / 
  curl -sS -o /tmp/smoke-home.html "$FRONTEND_URL/" || true
  index_js=$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' /tmp/smoke-home.html | head -1 || true)
fi
if [ -n "$index_js" ]; then
  curl -sS -o /tmp/smoke-index.js "$FRONTEND_URL/$index_js" || true
  gchunk=$(grep -oE 'assets/useGoogleAuthButton-[A-Za-z0-9_-]+\.js' /tmp/smoke-index.js | head -1 || true)
  if [ -n "$gchunk" ]; then
    curl -sS -o /tmp/smoke-google.js "$FRONTEND_URL/$gchunk" || true
    if grep -q 'apps.googleusercontent.com' /tmp/smoke-google.js && grep -q 'googleEnabled:!0\|googleEnabled: !0\|googleEnabled:!0' /tmp/smoke-google.js; then
      ok "Google GIS client id present (googleEnabled true)"
    elif grep -q 'apps.googleusercontent.com' /tmp/smoke-google.js; then
      ok "Google GIS client id present in bundle"
    else
      bad "Google chunk missing client id — button will hide"
    fi
  else
    # client id may be inlined in index
    if grep -q 'apps.googleusercontent.com' /tmp/smoke-index.js; then
      ok "Google client id found in index bundle"
    else
      bad "no useGoogleAuthButton chunk / client id in index"
    fi
  fi
else
  bad "could not find index-*.js on login/home"
fi

# 6) SEO assets not swallowed by SPA
for path in sitemap.xml robots.txt ai-index.json; do
  code=$(curl -sS -o /tmp/smoke-seo -w "%{http_code}" "$FRONTEND_URL/$path" || true)
  ctype=$(file -b --mime-type /tmp/smoke-seo 2>/dev/null || true)
  if [ "$code" != "200" ]; then
    bad "GET /$path → $code"
  elif grep -qi '<html\|<!doctype html' /tmp/smoke-seo; then
    bad "GET /$path returned HTML (SPA rewrite bug)"
  else
    ok "GET /$path → 200 (not SPA html)"
  fi
done

echo
if [ "$fail" -ne 0 ]; then
  echo "smoke-prod FAILED"
  exit 1
fi
echo "smoke-prod passed"
