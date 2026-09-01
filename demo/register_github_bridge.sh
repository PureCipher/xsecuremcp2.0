#!/usr/bin/env bash
# Register the local GitHub HTTP bridge as a proxy listing.
#
# Prereq: the bridge is already running (demo/github_http_bridge.py), i.e.
#   export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx
#   uv run python demo/github_http_bridge.py        # serves http://localhost:9100/mcp
#
# Then:
#   REGISTRY_URL=http://localhost:8001 bash demo/register_github_bridge.sh
#
# Env:
#   REGISTRY_URL  registry API (default http://localhost:8000; auto-detects 8001)
#   BRIDGE_URL    bridge MCP URL (default http://localhost:9100/mcp)
#   ADMIN_USER / ADMIN_PASS  admin creds if auth is on (default admin/admin123)
set -uo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8000}"
BRIDGE_URL="${BRIDGE_URL:-http://localhost:9100/mcp}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"

probe() { curl -s -o /dev/null -w "%{http_code}" "$1/registry/health" 2>/dev/null; }
echo "=== Health check ==="
if [ "$(probe "$REGISTRY_URL")" != "200" ]; then
  for ALT in "http://localhost:8001" "http://localhost:8000" "http://127.0.0.1:8001" "http://127.0.0.1:8000"; do
    if [ "$ALT" != "$REGISTRY_URL" ] && [ "$(probe "$ALT")" = "200" ]; then
      echo "  → registry is at $ALT. Re-run: REGISTRY_URL=$ALT bash demo/register_github_bridge.sh"; exit 1
    fi
  done
  echo "No registry at $REGISTRY_URL."; exit 1
fi
echo "Registry healthy at $REGISTRY_URL"

# Is the bridge up? (a 4xx/2xx means something is listening at the MCP path)
BRIDGE_BASE="${BRIDGE_URL%/mcp}"
if [ "$(curl -s -o /dev/null -w '%{http_code}' "$BRIDGE_BASE" 2>/dev/null)" = "000" ] \
   && [ "$(curl -s -o /dev/null -w '%{http_code}' "$BRIDGE_URL" 2>/dev/null)" = "000" ]; then
  echo "WARNING: nothing seems to be listening at $BRIDGE_URL."
  echo "  Start it first:  uv run python demo/github_http_bridge.py"
fi

echo ""
echo "=== Authenticate ==="
AUTH="X-PureCipher-Demo: 1"
HTTP=$(curl -s -o /tmp/pc_login.json -w "%{http_code}" -X POST "$REGISTRY_URL/registry/login" \
  -H "Content-Type: application/json" -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
LOGIN=$(cat /tmp/pc_login.json 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
  AUTH="Authorization: Bearer $TOKEN"; echo "Authenticated as $ADMIN_USER"
elif echo "$LOGIN" | grep -q "auth is disabled"; then
  echo "Registry auth is disabled — proceeding without a token."
else
  echo "Login failed (HTTP $HTTP): $LOGIN"; exit 1
fi

echo ""
echo "=== Submitting GitHub bridge ($BRIDGE_URL) ==="
RESP=$(curl -s -X POST "$REGISTRY_URL/registry/curate/submit" \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d "{\"upstream\":\"$BRIDGE_URL\",\"hosting_mode\":\"proxy\",\"attestation_kind\":\"curator\",
       \"tool_name\":\"github-local\",\"display_name\":\"GitHub (local HTTP)\",
       \"description\":\"GitHub MCP via local HTTP bridge — repos, issues, PRs, code search.\",
       \"version\":\"1.0.0\"}")

ACCEPTED=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('accepted',False))" 2>/dev/null || echo False)
if [ "$ACCEPTED" != "True" ]; then
  ERR=$(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error') or d)" 2>/dev/null || echo "$RESP")
  echo "FAILED: $ERR"
  echo ""
  echo "If this says 'Connection closed' or similar, the bridge isn't serving tools."
  echo "Sanity-check the image + token directly:"
  echo "  docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN=\$GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server stdio"
  echo "  (should start and wait; if it exits immediately, the token is invalid/under-scoped)"
  exit 1
fi

LISTING_ID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['listing']['listing_id'])")
STATUS=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['listing']['status'])")
echo "listing_id: $LISTING_ID  (status: $STATUS)"
if [ "$STATUS" = "pending_review" ]; then
  curl -sf -X POST "$REGISTRY_URL/registry/review/$LISTING_ID/approve" \
    -H "Content-Type: application/json" -H "$AUTH" \
    -d '{"reason":"GitHub bridge approved for demo."}' > /dev/null && echo "approved."
fi

echo ""
echo "✓ GitHub (local HTTP) registered."
echo "  proxy: $REGISTRY_URL/runtime/proxy/$LISTING_ID/mcp"
echo "  In the agent app: Refresh catalog → pick 'GitHub (local HTTP)' → Connect → call e.g."
echo "    search_repositories  {\"query\":\"fastmcp\"}"
