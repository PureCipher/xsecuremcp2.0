"""Seed governance control planes with demo data.

Run inside the registry container:
    docker exec xsecuremcp20-purecipher-registry-1 \
        uv run --no-sync python /app/demo/seed_governance.py
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone

REGISTRY = "http://127.0.0.1:8000"
CLIENT_SLUG = "claude-code-demo"
TOOLS = ["get_weather", "calculate", "lookup_company", "generate_uuid", "echo"]


def api(method: str, path: str, body: dict | None = None, token: str = "") -> dict:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{REGISTRY}{path}", data=data, headers=headers, method=method)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300], "status": e.code}


def seed_consent_graph() -> None:
    print("\n=== Consent Graph ===")
    from fastmcp.server.security.consent.graph import ConsentGraph, ConsentNode, NodeType

    graph = ConsentGraph(graph_id="purecipher-registry")
    graph.add_node(ConsentNode(node_id=CLIENT_SLUG, node_type=NodeType.AGENT,
                               metadata={"kind": "agent", "display_name": "Claude Code Demo"}))
    for tool in TOOLS:
        graph.add_node(ConsentNode(node_id=tool, node_type=NodeType.RESOURCE, metadata={"kind": "tool"}))
        graph.grant(source_id=tool, target_id=CLIENT_SLUG, scopes={"execute", "read"},
                    granted_by="admin", metadata={"reason": "Demo access"},
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        print(f"  Granted: {tool} → {CLIENT_SLUG}")
    print(f"  Graph: {graph.node_count} nodes, {graph.edge_count} edges")


def seed_contracts() -> None:
    print("\n=== Contract Broker ===")
    from fastmcp.server.security.contracts.broker import ContextBroker
    from fastmcp.server.security.contracts.schema import ContractNegotiationRequest, ContractTerm

    broker = ContextBroker(server_id="purecipher-registry")
    request = ContractNegotiationRequest(
        agent_id=CLIENT_SLUG,
        proposed_terms=[
            ContractTerm(term_id="tool-access",
                         description=f"Agent may call: {', '.join(TOOLS)}",
                         constraint={"allowed_tools": TOOLS}),
            ContractTerm(term_id="provenance",
                         description="All calls recorded in ledger",
                         constraint={"provenance_required": True}),
            ContractTerm(term_id="rate-limit",
                         description="100 calls/minute",
                         constraint={"max_calls_per_minute": 100}),
        ],
    )
    response = asyncio.get_event_loop().run_until_complete(broker.negotiate(request))
    print(f"  Session: {response.session_id}")
    print(f"  Status: {response.status}")
    if response.contract:
        print(f"  Contract: {response.contract.contract_id} status={response.contract.status}")
    else:
        # Continue negotiation — accept terms
        accept_req = ContractNegotiationRequest(
            session_id=response.session_id,
            agent_id=CLIENT_SLUG,
            proposed_terms=request.proposed_terms,
            context={"action": "accept"},
        )
        resp2 = asyncio.get_event_loop().run_until_complete(broker.negotiate(accept_req))
        print(f"  Round 2 status: {resp2.status}")
        if resp2.contract:
            print(f"  Contract: {resp2.contract.contract_id}")


def seed_policy_evaluations(token: str) -> None:
    print("\n=== Policy Evaluations ===")
    for tool in TOOLS:
        resp = api("POST", f"/registry/clients/{CLIENT_SLUG}/simulate", {
            "action": "tool_call",
            "resource_id": tool,
            "metadata": {"demo": True},
        }, token=token)
        decision = resp.get("policy", {}).get("decision", "?")
        verdict = resp.get("verdict", "?")
        blockers = len(resp.get("blockers", []))
        print(f"  {tool:20s} policy={decision:8s} verdict={verdict} blockers={blockers}")

    state = api("GET", "/security/policy")
    print(f"  Total evaluations: {state.get('evaluation_count', 0)}")


def generate_tool_calls() -> None:
    print("\n=== Generating tool calls ===")
    from fastmcp import Client
    from fastmcp.client.auth import BearerAuth

    async def run():
        auth = BearerAuth("pcc_g9j9CxSfwM7llr")
        async with Client(
            "http://127.0.0.1:8000/runtime/proxy/3be0c478-23f5-4fce-bd12-770a0fda4185/mcp",
            auth=auth,
        ) as client:
            for city in ["Amsterdam", "Stockholm", "Bangkok", "Toronto", "Nairobi"]:
                await client.call_tool("get_weather", {"city": city})
            await client.call_tool("calculate", {"expression": "3.14 * 100"})
            await client.call_tool("lookup_company", {"name": "PureCipher"})
            print(f"  7 tool calls made")

    asyncio.run(run())


def main() -> None:
    login = api("POST", "/registry/login", {"username": "admin", "password": "admin123"})
    token = login["token"]
    print("Authenticated")

    seed_consent_graph()
    seed_contracts()
    seed_policy_evaluations(token)
    generate_tool_calls()

    print("\n=== Final State ===")
    gov = api("GET", f"/registry/clients/{CLIENT_SLUG}/governance", token=token)
    lg = gov.get("ledger", {}).get("ledger", {})
    rp = gov.get("policy", {}).get("registry_policy", {})
    an = gov.get("reflexive", {}).get("analyzer", {})
    cn = gov.get("consent", {}).get("consent_graph", {})
    ct = gov.get("contracts", {}).get("broker", {})
    print(f"  Ledger:     {lg.get('record_count', 0)} records")
    print(f"  Policy:     {rp.get('evaluation_count', 0)} evals, {rp.get('deny_count', 0)} denies")
    print(f"  Reflexive:  {an.get('monitored_actor_count', 0)} actors")
    print(f"  Consent:    {cn.get('edge_count', 0)} edges")
    print(f"  Contracts:  {ct.get('active_contract_count', 0)} active")

    print("\nDashboards:")
    print("  http://localhost:3000/registry/provenance")
    print("  http://localhost:3000/registry/policy")
    print("  http://localhost:3000/registry/reflexive")
    print("  http://localhost:3000/registry/consent")
    print("  http://localhost:3000/registry/contracts")
    print("  http://localhost:3000/registry/clients/claude-code-demo")


if __name__ == "__main__":
    main()
