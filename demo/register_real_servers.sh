#!/usr/bin/env bash
# Register a set of real, GitHub-published MCP servers into the PureCipher
# Registry via the curator flow (resolve -> introspect -> submit -> approve).
#
# Channels exercised: HTTP (https://), npm (npx), PyPI (uvx), Docker (docker run).
# The GitHub channel is reserved/unimplemented in the registry, so each server
# below is referenced by the artifact it actually ships as.
#
# Credential-free servers register unconditionally. Credentialed servers only
# register if the matching token is present in the environment — the registry
# re-introspects on submit and REFUSES any upstream that exposes zero tools
# (which is what an un-authenticated, token-gated server looks like).
#
# Usage:
#   bash demo/register_real_servers.sh
#   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx BRAVE_API_KEY=BSA_xxx bash demo/register_real_servers.sh
#
# Requirements (inside the registry container / host running it):
#   - npx, uvx, and docker on PATH for the npm/PyPI/Docker channels
#   - outbound network for package/image pulls
#   - HOSTING_MODE=proxy (default) makes listings callable through the runtime proxy
set -uo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8001}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
HOSTING_MODE="${HOSTING_MODE:-proxy}"   # "proxy" (callable) or "catalog" (listed only)

echo "=== Health check ==="
# The CLI defaults to port 8001; docker-compose maps to 8000. Probe both so a
# port mismatch produces a useful message instead of a blind login failure.
probe() { curl -s -o /dev/null -w "%{http_code}" "$1/registry/health" 2>/dev/null; }
HEALTH=$(probe "$REGISTRY_URL")
if [ "$HEALTH" != "200" ]; then
  echo "No registry at $REGISTRY_URL (health=$HEALTH)."
  for ALT in "http://localhost:8001" "http://localhost:8000" "http://127.0.0.1:8001" "http://127.0.0.1:8000"; do
    if [ "$ALT" != "$REGISTRY_URL" ] && [ "$(probe "$ALT")" = "200" ]; then
      echo "  → Found a registry at $ALT instead. Re-run with:"
      echo "      REGISTRY_URL=$ALT bash demo/register_real_servers.sh"
      exit 1
    fi
  done
  echo "  Is the registry running? Start it with e.g.:"
  echo "      PURECIPHER_SIGNING_SECRET=dev PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123 \\"
  echo "        uv run purecipher-registry --port 8000"
  exit 1
fi
echo "Registry healthy at $REGISTRY_URL"

echo ""
echo "=== Authenticate ==="
# A non-placeholder header so `-H "$AUTH"` is always valid even when no token
# is needed (auth disabled). Overwritten with a Bearer token when auth is on.
AUTH="X-PureCipher-Demo: 1"
HTTP=$(curl -s -o /tmp/pc_login.json -w "%{http_code}" -X POST "$REGISTRY_URL/registry/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
LOGIN_RESPONSE=$(cat /tmp/pc_login.json 2>/dev/null)

if [ "$HTTP" = "200" ]; then
  TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
  AUTH="Authorization: Bearer $TOKEN"
  echo "Authenticated as $ADMIN_USER at $REGISTRY_URL (hosting_mode=$HOSTING_MODE)"
elif echo "$LOGIN_RESPONSE" | grep -q "auth is disabled"; then
  # Auth off: every route runs without a session/token. Proceed tokenless.
  echo "Registry auth is disabled — proceeding without a token (hosting_mode=$HOSTING_MODE)."
else
  echo "Login failed (HTTP $HTTP) as user '$ADMIN_USER'."
  echo "  Response: $LOGIN_RESPONSE"
  echo ""
  echo "  The admin account only exists if the registry was started with a bootstrap"
  echo "  password. Either restart it with:"
  echo "      PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123 uv run purecipher-registry ..."
  echo "  or complete first-run setup at $REGISTRY_URL/setup (or the console /login),"
  echo "  then re-run with your credentials:"
  echo "      ADMIN_USER=you ADMIN_PASS=secret bash demo/register_real_servers.sh"
  exit 1
fi
echo ""

SUMMARY=()

# register <upstream> <tool_name> <display_name> <description> [env_json]
register() {
  local upstream="$1" tool_name="$2" display_name="$3" description="$4" env_json="${5:-}"
  echo "--- $display_name"
  echo "    upstream: $upstream"

  local body
  body=$(python3 - "$upstream" "$tool_name" "$display_name" "$description" "$HOSTING_MODE" "$env_json" <<'PY'
import json, sys
upstream, tool_name, display_name, description, hosting_mode, env_json = sys.argv[1:7]
payload = {
    "upstream": upstream,
    "hosting_mode": hosting_mode,
    "attestation_kind": "curator",
    "tool_name": tool_name,
    "display_name": display_name,
    "description": description,
    "version": "1.0.0",
}
if env_json:
    try:
        payload["env"] = json.loads(env_json)
    except json.JSONDecodeError:
        pass
print(json.dumps(payload))
PY
)

  local resp
  resp=$(curl -s -X POST "$REGISTRY_URL/registry/curate/submit" \
    -H "Content-Type: application/json" -H "$AUTH" -d "$body")

  local accepted listing_id status err
  accepted=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('accepted',False))" 2>/dev/null || echo "False")
  if [ "$accepted" != "True" ]; then
    err=$(echo "$resp" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error') or d)" 2>/dev/null || echo "$resp")
    echo "    SKIPPED/FAILED: $err"
    SUMMARY+=("✗  $display_name — $err")
    echo ""
    return
  fi

  listing_id=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['listing']['listing_id'])")
  status=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['listing']['status'])")
  echo "    listing_id: $listing_id  (status: $status)"

  if [ "$status" = "pending_review" ]; then
    curl -sf -X POST "$REGISTRY_URL/registry/review/$listing_id/approve" \
      -H "Content-Type: application/json" -H "$AUTH" \
      -d '{"reason":"Real-world MCP server approved for demo."}' > /dev/null \
      && echo "    approved." \
      && status="approved"
  fi

  SUMMARY+=("✓  $display_name — $listing_id — proxy: $REGISTRY_URL/runtime/proxy/$listing_id/mcp")
  echo ""
}

echo "=== Credential-free servers (register unconditionally) ==="
echo ""

# HTTP channel — public remote MCP, no auth. Great for a live call.
register "https://mcp.deepwiki.com/mcp" \
  "deepwiki" "DeepWiki (by Devin)" \
  "Ask questions and read docs for any public GitHub repo. Remote HTTP MCP, no auth."

# npm channel — official MCP reference servers (npx).
register "npm:@modelcontextprotocol/server-everything" \
  "mcp-everything" "MCP Everything (reference)" \
  "Reference server exercising every MCP feature: tools, resources, prompts."

register "npm:@modelcontextprotocol/server-memory" \
  "mcp-memory" "MCP Memory" \
  "Knowledge-graph memory server. Persistent entities and relations."

register "npm:@modelcontextprotocol/server-sequential-thinking" \
  "mcp-sequential-thinking" "MCP Sequential Thinking" \
  "Structured, reflective multi-step reasoning as a tool."

# PyPI channel — official reference servers (uvx).
register "pypi:mcp-server-fetch" \
  "mcp-fetch" "MCP Fetch" \
  "Fetch a URL and convert web content to markdown for LLM use."

echo "=== Credentialed servers (register only if token is present) ==="
echo ""

# GitHub is intentionally NOT registered here.
#
# The docker channel can't work in this registry: introspection runs the image
# with no command, but github-mcp-server needs the `stdio` subcommand, so the
# container exits ("McpError: Connection closed"). And proxy hosting wouldn't
# inject the token at call time anyway.
#
# Register GitHub via the local HTTP bridge instead:
#   export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx
#   uv run python demo/github_http_bridge.py          # http://localhost:9100/mcp
#   bash demo/register_github_bridge.sh
echo "--- GitHub: register via the bridge (demo/github_http_bridge.py + demo/register_github_bridge.sh)."
SUMMARY+=("→  GitHub — use the bridge: github_http_bridge.py + register_github_bridge.sh")
echo ""

# npm channel — Brave Search. Needs an API key (pass via the environment).
BRAVE="${BRAVE_API_KEY:-}"
if [ -n "$BRAVE" ]; then
  register "npm:@modelcontextprotocol/server-brave-search" \
    "brave-search" "Brave Search" \
    "Web, local, image, video and news search via the Brave Search API." \
    "{\"BRAVE_API_KEY\":\"$BRAVE\"}"
else
  echo "--- Brave Search: skipped — set BRAVE_API_KEY to register."
  SUMMARY+=("–  Brave Search — skipped (no BRAVE_API_KEY)")
  echo ""
fi

echo "==================== SUMMARY ===================="
for line in ${SUMMARY[@]+"${SUMMARY[@]}"}; do echo "$line"; done
echo ""
echo "Browse the catalog:  http://localhost:3000/registry/servers"
echo "Review queue:        http://localhost:3000/registry/review"
echo "Provenance:          http://localhost:3000/registry/provenance"
echo ""
echo "Note: 'proxy' listings are callable at the proxy URL above once a client"
echo "is registered (see demo/onboard_demo.sh) and granted consent for the tools."
