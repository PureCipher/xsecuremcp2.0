#!/usr/bin/env bash
# Deregister registry listings — the inverse of register_real_servers.sh.
#
# Deregister marks a listing removed: proxy-mode endpoints then reject calls
# with HTTP 410, and the listing drops out of the public catalog. It is an
# admin-only moderation action when auth is enabled.
#
# Usage:
#   bash demo/deregister_servers.sh                 # deregister the demo real-server set
#   bash demo/deregister_servers.sh deepwiki github # deregister specific tool names
#   bash demo/deregister_servers.sh --all           # deregister EVERY listing (with confirm)
#
# Env:
#   REGISTRY_URL  (default http://localhost:8000; auto-detects 8001 if down)
#   ADMIN_USER / ADMIN_PASS  (default admin / admin123; ignored if auth disabled)
#   REASON        (default "Removed via demo/deregister_servers.sh")
#   YES=1         skip the --all confirmation prompt
set -uo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
REASON="${REASON:-Removed via demo/deregister_servers.sh}"

# Default set = the servers register_real_servers.sh creates.
DEFAULT_TOOLS=(deepwiki mcp-everything mcp-memory mcp-sequential-thinking mcp-fetch github brave-search)

# ---- Health check (port-aware) ----
probe() { curl -s -o /dev/null -w "%{http_code}" "$1/registry/health" 2>/dev/null; }
echo "=== Health check ==="
if [ "$(probe "$REGISTRY_URL")" != "200" ]; then
  echo "No registry at $REGISTRY_URL."
  for ALT in "http://localhost:8001" "http://localhost:8000" "http://127.0.0.1:8001" "http://127.0.0.1:8000"; do
    if [ "$ALT" != "$REGISTRY_URL" ] && [ "$(probe "$ALT")" = "200" ]; then
      echo "  → Found a registry at $ALT. Re-run with: REGISTRY_URL=$ALT bash demo/deregister_servers.sh $*"
      exit 1
    fi
  done
  echo "  Is the registry running?"
  exit 1
fi
echo "Registry healthy at $REGISTRY_URL"
echo ""

# ---- Auth (optional) ----
echo "=== Authenticate ==="
AUTH="X-PureCipher-Demo: 1"
HTTP=$(curl -s -o /tmp/pc_login.json -w "%{http_code}" -X POST "$REGISTRY_URL/registry/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
LOGIN_RESPONSE=$(cat /tmp/pc_login.json 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
  AUTH="Authorization: Bearer $TOKEN"
  echo "Authenticated as $ADMIN_USER (admin role required for deregister)."
elif echo "$LOGIN_RESPONSE" | grep -q "auth is disabled"; then
  echo "Registry auth is disabled — proceeding without a token."
else
  echo "Login failed (HTTP $HTTP): $LOGIN_RESPONSE"
  echo "  Deregister requires an admin when auth is enabled. Start the registry with"
  echo "  PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123, or pass ADMIN_USER/ADMIN_PASS."
  exit 1
fi
echo ""

# ---- Resolve which tool names to deregister ----
# Built with a read loop (not mapfile — macOS ships Bash 3.2, which lacks it).
TOOLS=()
if [ "${1:-}" = "--all" ]; then
  echo "=== Resolving ALL listings ==="
  while IFS= read -r line; do
    [ -n "$line" ] && TOOLS+=("$line")
  done < <(curl -s "$REGISTRY_URL/registry/tools" -H "$AUTH" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print('\n'.join(t.get('tool_name','') for t in d.get('tools',[]) if t.get('tool_name')))")
  if [ "${#TOOLS[@]}" -eq 0 ]; then
    echo "No listings found — nothing to deregister."
    exit 0
  fi
  if [ "${YES:-}" != "1" ]; then
    echo "About to deregister ${#TOOLS[@]} listing(s): ${TOOLS[*]}"
    read -r -p "Type 'yes' to continue: " confirm
    [ "$confirm" = "yes" ] || { echo "Aborted."; exit 0; }
  fi
elif [ "$#" -gt 0 ]; then
  TOOLS=("$@")
else
  TOOLS=("${DEFAULT_TOOLS[@]}")
fi

echo ""
echo "=== Deregistering ==="
SUMMARY=()
for name in "${TOOLS[@]}"; do
  [ -z "$name" ] && continue
  detail=$(curl -s "$REGISTRY_URL/registry/tools/$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$name")" -H "$AUTH")
  listing_id=$(echo "$detail" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin); print(d.get('listing_id') or '')
except Exception:
    print('')" 2>/dev/null)
  status=$(echo "$detail" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin); print((d.get('status') or '').lower())
except Exception:
    print('')" 2>/dev/null)

  if [ -z "$listing_id" ]; then
    echo "  $name: not found — skipping"
    SUMMARY+=("–  $name — not found")
    continue
  fi
  if [ "$status" = "deregistered" ]; then
    echo "  $name: already deregistered — skipping"
    SUMMARY+=("–  $name — already deregistered")
    continue
  fi

  resp=$(curl -s -o /tmp/pc_dereg.json -w "%{http_code}" \
    -X POST "$REGISTRY_URL/registry/review/$listing_id/deregister" \
    -H "Content-Type: application/json" -H "Accept: application/json" -H "$AUTH" \
    -d "{\"reason\":\"$REASON\"}")
  if [ "$resp" = "200" ]; then
    echo "  $name: deregistered ($listing_id)"
    SUMMARY+=("✓  $name — deregistered")
  else
    err=$(cat /tmp/pc_dereg.json 2>/dev/null)
    echo "  $name: FAILED (HTTP $resp) — $err"
    SUMMARY+=("✗  $name — HTTP $resp")
  fi
done

echo ""
echo "==================== SUMMARY ===================="
for line in ${SUMMARY[@]+"${SUMMARY[@]}"}; do echo "$line"; done
echo ""
echo "Catalog:    http://localhost:3000/registry/servers"
echo "Provenance: http://localhost:3000/registry/provenance  (deregister events are recorded)"
