#!/usr/bin/env bash
# Onboard the demo MCP server through PureCipher's curator flow,
# register a client identity, and generate Claude Code MCP config.
#
# Recommended: run the registry on :8000 with auth enabled so the full
# governed story works (curation under an admin, agent registration):
#   PURECIPHER_SIGNING_SECRET=dev PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123 \
#     uv run purecipher-registry --port 8000
# The script also works with auth disabled (it proceeds tokenless) and
# auto-detects a registry on :8001 if :8000 is down.
set -uo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"

echo "=== Step 0: Health check ==="
probe() { curl -s -o /dev/null -w "%{http_code}" "$1/registry/health" 2>/dev/null; }
if [ "$(probe "$REGISTRY_URL")" != "200" ]; then
  echo "No registry at $REGISTRY_URL."
  for ALT in "http://localhost:8001" "http://localhost:8000" "http://127.0.0.1:8001" "http://127.0.0.1:8000"; do
    if [ "$ALT" != "$REGISTRY_URL" ] && [ "$(probe "$ALT")" = "200" ]; then
      echo "  → Found a registry at $ALT. Re-run with: REGISTRY_URL=$ALT bash demo/onboard_demo.sh"
      exit 1
    fi
  done
  echo "  Is the registry running?"
  exit 1
fi
echo "Registry healthy at $REGISTRY_URL"

echo ""
echo "=== Step 1: Authenticate ==="
AUTH="X-PureCipher-Demo: 1"
HTTP=$(curl -s -o /tmp/pc_login.json -w "%{http_code}" -X POST "$REGISTRY_URL/registry/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
LOGIN_RESPONSE=$(cat /tmp/pc_login.json 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
  AUTH="Authorization: Bearer $TOKEN"
  echo "Authenticated as $ADMIN_USER"
elif echo "$LOGIN_RESPONSE" | grep -q "auth is disabled"; then
  echo "Registry auth is disabled — proceeding without a token."
else
  echo "Login failed (HTTP $HTTP): $LOGIN_RESPONSE"
  echo "  Start the registry with PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123, or pass ADMIN_USER/ADMIN_PASS."
  exit 1
fi

echo ""
echo "=== Step 2: Submit demo server via curator flow (hosting_mode=proxy) ==="
SUBMIT_RESPONSE=$(curl -sf -X POST "$REGISTRY_URL/registry/curate/submit" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{
    "upstream": "http://demo-mcp-server:9000/mcp",
    "hosting_mode": "proxy",
    "attestation_kind": "curator",
    "tool_name": "demo-tools",
    "display_name": "Demo MCP Tools",
    "description": "Weather, calculator, company lookup, UUID generator, and echo — running through SecureMCP governance.",
    "version": "1.0.0"
  }')

ACCEPTED=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('accepted',False))")
if [ "$ACCEPTED" != "True" ]; then
  echo "Submission failed:"
  echo "$SUBMIT_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SUBMIT_RESPONSE"
  exit 1
fi

LISTING_ID=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['listing']['listing_id'])")
STATUS=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['listing']['status'])")
echo "Listing ID: $LISTING_ID"
echo "Status: $STATUS"

echo ""
echo "=== Step 3: Approve listing ==="
if [ "$STATUS" = "pending_review" ]; then
  curl -sf -X POST "$REGISTRY_URL/registry/review/$LISTING_ID/approve" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d '{"reason": "Demo server approved."}' > /dev/null
  echo "Approved."
else
  echo "Already $STATUS — skipping."
fi

echo ""
echo "=== Step 4: Register MCP client identity ==="
CLIENT_RESPONSE=$(curl -sf -X POST "$REGISTRY_URL/registry/clients" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{
    "display_name": "Claude Code Demo",
    "slug": "claude-code-demo",
    "description": "Claude Code connecting through the PureCipher registry proxy.",
    "intended_use": "Integration testing of the full governance pipeline.",
    "kind": "agent",
    "issue_initial_token": true,
    "token_name": "demo-token"
  }')
CLIENT_SECRET=$(echo "$CLIENT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['secret'])")
echo "Client token: $CLIENT_SECRET"
echo ""
echo "*** Save this token — it is shown only once ***"

PROXY_URL="$REGISTRY_URL/runtime/proxy/$LISTING_ID/mcp"

echo ""
echo "=== Step 5: Connection config ==="
echo ""
echo "Proxy endpoint: $PROXY_URL"
echo ""
echo "Add this to your Claude Code MCP settings:"
echo ""
cat <<EOF
{
  "mcpServers": {
    "demo-tools": {
      "type": "streamable-http",
      "url": "$PROXY_URL",
      "headers": {
        "Authorization": "Bearer $CLIENT_SECRET"
      }
    }
  }
}
EOF

echo ""
echo "=== What gets exercised ==="
echo ""
echo "When Claude calls a tool through this proxy, the registry enforces:"
echo "  1. Allowlist policy — only the 5 curator-observed tools are callable"
echo "  2. Provenance ledger — every call recorded in the Merkle-tree audit log"
echo "  3. Reflexive core — behavioral baselines + anomaly detection per actor"
echo "  4. Consent enforcement — checks the consent graph before execution"
echo "  5. Contract validation — verifies active contracts cover the action"
echo ""
echo "View the results:"
echo "  Provenance: http://localhost:3000/registry/provenance"
echo "  Policy:     http://localhost:3000/registry/policy"
echo "  Reflexive:  http://localhost:3000/registry/reflexive"
echo "  Clients:    http://localhost:3000/registry/clients/claude-code-demo"
