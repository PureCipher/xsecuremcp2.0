import json

import pytest
from starlette.testclient import TestClient

from purecipher import PureCipherRegistry, consumer_runtime
from purecipher.consumer_bridge import PRODUCTS
from purecipher.consumer_bridge_tools import tool_alias
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_consumer_bridge import protocol
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


@pytest.mark.parametrize("product", sorted(PRODUCTS))
def test_individual_upstream_tools_use_profile_schema_and_permissions(
    monkeypatch, product
):
    enabled(monkeypatch)
    app = PureCipherRegistry(
        signing_secret="test-secret",
        auth_settings=registry()._auth_settings,
        enable_contracts=True,
        enable_consent=True,
        enable_provenance=False,
        enable_reflexive=False,
    )
    calls, schema = protocol(monkeypatch)
    from fastmcp.server.security.gateway.tool_marketplace import PublishStatus

    helper = product.replace("-", "_") + "_call_approved_tool"
    tool = tool_alias(
        product,
        "echo",
        {
            "name": "echo",
            "description": "Echo the supplied text",
            "inputSchema": schema,
        },
    )
    listing = app._marketplace().publish(
        "purecipher-" + product,
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={
            "introspection": {"tool_names": [helper]},
            "deployment_ready": True,
            "live_tested": False,
        },
    )
    monkeypatch.setattr(
        app,
        "_get_public_listing",
        lambda name: listing if name == listing.tool_name else None,
    )
    with TestClient(app.http_app(stateless_http=True, json_response=True)) as client:
        login(client)
        conn = add(
            client,
            product,
            {
                "MCP_ENDPOINT": "https://upstream.example/mcp",
                "MCP_ACCESS_TOKEN": "owner-upstream-token",
                "MCP_ALLOWED_TOOLS": "echo",
            },
        )
        endpoint = "/registry/workspace/connections/" + conn["id"]
        result = client.post(endpoint + "/verify")
        assert result.status_code == 200, result.text
        assert (
            result.json()["runtime_ready"] and len(result.json()["upstream_tools"]) == 1
        )
        assert result.json()["upstream_tools"][0]["profile_tool_name"] == tool
        assert "owner-upstream-token" not in result.text
        assert "inputSchema" not in json.dumps(app._workspace.get(conn["id"]))
        entry = client.post(
            "/registry/workspace/clients", json={"display_name": "My client"}
        ).json()
        profile = client.post(
            "/registry/workspace/profiles",
            json={
                "name": "Upstream",
                "status": "inactive",
                "purpose": "Fixture product access",
                "client_ids": [entry["client"]["client_id"]],
                "servers": [
                    {
                        "listing_id": listing.listing_id,
                        "tools": [tool],
                        "connection_id": conn["id"],
                    }
                ],
            },
        ).json()
        assert "id" in profile, profile
        profile = approve_profile(app, client, profile)
        headers = {
            "Authorization": "Bearer " + entry["token"],
            "Accept": "application/json, text/event-stream",
        }
        path = "/mcp/profiles/" + profile["id"]
        discovery = client.post(
            path,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ).json()
        assert "error" not in discovery, discovery
        listed = discovery["result"]["tools"]
        assert len(listed) == 1, listed
        assert listed[0]["name"] == tool
        assert listed[0]["title"] == "echo"
        assert listed[0]["inputSchema"] == schema
        assert listed[0]["annotations"]["destructiveHint"] is True
        assert tool not in getattr(app, "_consumer_tool_products", {})
        rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": {"text": "test"},
            },
        }
        response = client.post(path, headers=headers, json=rpc)
        assert response.status_code == 200 and "upstream result" in response.text, (
            response.text
        )
        assert consumer_runtime._ACCESS.get() is None
        count = sum(c["method"] == "tools/call" for c in calls)
        # A caller cannot switch to another function or bypass its input schema.
        bad = {
            **rpc,
            "params": {
                "name": helper,
                "arguments": {"tool_name": "echo", "arguments": {"text": "test"}},
            },
        }
        denied = client.post(path, headers=headers, json=bad).json()
        assert denied.get("error") or denied.get("result", {}).get("isError"), denied
        bad["params"] = {"name": tool, "arguments": {"text": 42}}
        denied = client.post(path, headers=headers, json=bad).json()
        assert denied.get("error") or denied.get("result", {}).get("isError"), denied
        assert sum(c["method"] == "tools/call" for c in calls) == count
        schema["properties"]["extra"] = {"type": "string"}
        response = client.post(path, headers=headers, json=rpc)
        assert response.json()["result"]["isError"]
        assert sum(c["method"] == "tools/call" for c in calls) == count
        # Reverification cannot silently replace an approved capability's schema.
        changed = client.post(endpoint + "/verify")
        assert changed.status_code == 200
        assert changed.json()["upstream_tools"][0]["profile_tool_name"] != tool
        assert client.post(path, headers=headers, json=rpc).status_code == 403
        login(client, "bob")
        assert client.post(endpoint + "/verify").status_code == 404
        login(client)
        client.post(endpoint + "/disconnect")
        assert client.post(path, headers=headers, json=rpc).status_code == 403
