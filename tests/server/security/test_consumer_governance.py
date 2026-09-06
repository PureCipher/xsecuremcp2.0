import asyncio
import json
from pathlib import Path

from starlette.testclient import TestClient

from fastmcp.server.security.contracts.schema import (
    ContractNegotiationRequest,
    ContractTerm,
)
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_workspace_profiles import login


def test_full_security_stack_requires_approval_and_runs_after_grants(monkeypatch):
    app = enabled(monkeypatch)
    payload = next(
        p
        for p in json.loads(
            (
                Path(__file__).parents[3]
                / "examples/securemcp/consumer_runtime/submissions.json"
            ).read_text()
        )
        if p["manifest"]["tool_name"] == "purecipher-time"
    )
    result = app.submit_tool(
        app._marketplace()._deserialize_manifest(payload["manifest"]),
        display_name=payload["display_name"],
        metadata=payload["metadata"],
    )
    assert result.accepted
    listing = result.listing
    with TestClient(app.http_app(stateless_http=True, json_response=True)) as c:
        login(c)
        conn = add(c, "time")
        assert c.post(
            "/registry/workspace/connections/" + conn["id"] + "/verify"
        ).json()["runtime_ready"]
        entry = c.post(
            "/registry/workspace/clients", json={"display_name": "Approved client"}
        ).json()
        profile = {
            "name": "Time only",
            "purpose": "Time checks",
            "status": "active",
            "client_ids": [entry["client"]["client_id"]],
            "servers": [
                {
                    "listing_id": listing.listing_id,
                    "tools": ["time_current"],
                    "connection_id": conn["id"],
                }
            ],
        }
        denied = c.post("/registry/workspace/profiles", json=profile)
        assert denied.status_code == 400 and "Security approval" in denied.text
        assert "Security & access" in denied.text
        broker = app._broker_or_none()
        asyncio.run(
            broker.negotiate(
                ContractNegotiationRequest(
                    agent_id=entry["client"]["slug"],
                    proposed_terms=[
                        ContractTerm(
                            description="Unrelated older agreement",
                            constraint={
                                "allowed_actions": ["call_tool"],
                                "allowed_resources": ["unrelated_tool"],
                            },
                        )
                    ],
                )
            )
        )
        response = asyncio.run(
            broker.negotiate(
                ContractNegotiationRequest(
                    agent_id=entry["client"]["slug"],
                    proposed_terms=[
                        ContractTerm(
                            description="Time only",
                            constraint={
                                "allowed_actions": ["call_tool"],
                                "allowed_resources": ["time_current"],
                            },
                        )
                    ],
                )
            )
        )
        assert response.contract.is_valid()
        app._consent_graph_or_none().grant(
            "server",
            entry["client"]["slug"],
            {"execute"},
            granted_by="test-administrator",
        )
        profile = c.post(
            "/registry/workspace/profiles", json={**profile, "status": "inactive"}
        ).json()
        profile = approve_profile(app, c, profile, grant_controls=False)
        assert profile["status"] == "active"
        path = "/mcp/profiles/" + profile["id"]
        headers = {
            "Authorization": "Bearer " + entry["token"],
            "Accept": "application/json, text/event-stream",
        }
        rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "time_current", "arguments": {"timezone": "UTC"}},
        }
        called = c.post(path, headers=headers, json=rpc).json()
        assert (
            not called["result"]["isError"]
            and called["result"]["structuredContent"]["timezone"] == "UTC"
        )
        asyncio.run(
            broker.revoke_contract(response.contract.contract_id, "Test revocation")
        )
        assert c.post(path, headers=headers, json=rpc).status_code == 403
        workspace = c.get("/registry/workspace").json()
        assert any(
            "Security approval" in reason
            for p in workspace["profiles"]
            for reason in p["blockers"]
        )


def test_old_schema_secrets_are_not_exposed_after_schema_change(monkeypatch):
    from purecipher.product_schemas import PRODUCT_SCHEMAS

    app = enabled(monkeypatch)
    current = PRODUCT_SCHEMAS["dynatrace"]
    old = {
        **current,
        "fields": [
            {
                "key": "OAUTH_CLIENT_SECRET",
                "type": "secret",
                "label": "Old app secret",
                "required": True,
            }
        ],
    }
    with TestClient(app.http_app()) as c:
        login(c)
        monkeypatch.setitem(PRODUCT_SCHEMAS, "dynatrace", old)
        conn = add(c, "dynatrace", {"OAUTH_CLIENT_SECRET": "legacy-private-secret"})
        monkeypatch.setitem(PRODUCT_SCHEMAS, "dynatrace", current)
        response = c.get("/registry/workspace/connections")
        assert conn["id"] in response.text
        assert "legacy-private-secret" not in response.text
        assert "OAUTH_CLIENT_SECRET" not in response.text
