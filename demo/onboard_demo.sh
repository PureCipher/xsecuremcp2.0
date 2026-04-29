#!/usr/bin/env bash
# Onboard the demo MCP server through PureCipher's curator flow,
# register a client identity, and generate Claude Code MCP config.
set -euo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"

echo "=== Step 1: Authenticate ==="
LOGIN_RESPONSE=$(curl -sf -X POST "$REGISTRY_URL/registry/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
AUTH="Authorization: Bearer $TOKEN"
echo "Authenticated as $ADMIN_USER"

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
