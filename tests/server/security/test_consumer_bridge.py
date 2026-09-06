import asyncio
import json

import pytest
from starlette.testclient import TestClient

from fastmcp.server.security.outbound import OutboundHTTPResponse
from purecipher import PureCipherRegistry, consumer_bridge, consumer_runtime
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


def protocol(monkeypatch):
    calls = []
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    async def transport(url, *, method, content, headers, **kwargs):
        assert url == "https://upstream.example/mcp"
        assert headers["Authorization"] == "Bearer owner-upstream-token"
        if method == "DELETE":
            return OutboundHTTPResponse(204, {}, b"")
        body = json.loads(content)
        calls.append(body)
        if body["method"] == "notifications/initialized":
            return OutboundHTTPResponse(202, {}, b"")
        if body["method"] == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
        elif body["method"] == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo the supplied text",
                        "inputSchema": schema,
                    }
                ]
            }
        elif body["method"] == "tools/call":
            assert body["params"] == {"name": "echo", "arguments": {"text": "test"}}
            result = {
                "content": [{"type": "text", "text": "upstream result"}],
                "isError": False,
            }
        else:
            raise AssertionError(body["method"])
        return OutboundHTTPResponse(
            200,
            {"content-type": "application/json", "mcp-session-id": "fixture-session"},
            json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode(),
        )

    monkeypatch.setattr(consumer_bridge, "async_secure_outbound_request", transport)
    return calls, schema


@pytest.mark.parametrize("product", sorted(consumer_bridge.PRODUCTS))
def test_upstream_profile_calls_enforce_approved_tools_and_owner(monkeypatch, product):
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

    tool = product.replace("-", "_") + "_call_approved_tool"
    listing = app._marketplace().publish(
        "purecipher-" + product,
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={
            "introspection": {"tool_names": [tool]},
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
        rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": {"tool_name": "echo", "arguments": {"text": "test"}},
            },
        }
        response = client.post(path, headers=headers, json=rpc)
        assert response.status_code == 200 and "upstream result" in response.text, (
            response.text
        )
        assert consumer_runtime._ACCESS.get() is None
        count = sum(c["method"] == "tools/call" for c in calls)
        schema["properties"]["extra"] = {"type": "string"}
        response = client.post(path, headers=headers, json=rpc)
        assert response.json()["result"]["isError"]
        assert sum(c["method"] == "tools/call" for c in calls) == count
        login(client, "bob")
        assert client.post(endpoint + "/verify").status_code == 404
        login(client)
        client.post(endpoint + "/disconnect")
        assert client.post(path, headers=headers, json=rpc).status_code == 403


def test_bridge_rejects_missing_approval_and_external_schema_refs(monkeypatch):
    _, schema = protocol(monkeypatch)
    values = {
        "MCP_ENDPOINT": "https://upstream.example/mcp",
        "MCP_ACCESS_TOKEN": "owner-upstream-token",
        "MCP_ALLOWED_TOOLS": "missing",
    }
    with pytest.raises(ValueError):
        asyncio.run(consumer_bridge.verify(values))
    values["MCP_ALLOWED_TOOLS"] = "echo"
    schema["properties"]["text"] = {"$ref": "http://169.254.169.254/credentials"}
    with pytest.raises(ValueError, match="External schema"):
        asyncio.run(consumer_bridge.verify(values))


def test_bridge_decodes_sse_without_exposing_provider_errors():
    response = OutboundHTTPResponse(
        200,
        {"content-type": "text/event-stream"},
        b'data: {"jsonrpc":"2.0","id":"one","result":{"tools":[]}}\n\n',
    )
    assert consumer_bridge.decode(response, "one") == {"tools": []}
    with pytest.raises(ValueError):
        consumer_bridge.decode(
            OutboundHTTPResponse(401, {}, b"private-provider-error"), "one"
        )
