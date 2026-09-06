"""Workspace ownership, persistence, and actual profile MCP boundary tests."""

from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus
from purecipher.workspace import WorkspaceStore
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_purecipher_catalog_query import registry


def login(client, username="alice"):
    assert (
        client.post(
            "/registry/login",
            json={"username": username, "password": "fixture-password"},
        ).status_code
        == 200
    )


def setup(app, client, monkeypatch):
    listing = app._marketplace().publish(
        "server",
        author="alice",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={"introspection": {"tool_names": ["echo"]}},
    )
    monkeypatch.setattr(
        app, "_get_public_listing", lambda name: listing if name == "server" else None
    )
    result = client.post(
        "/registry/workspace/clients",
        json={"display_name": "My laptop", "application": "Claude Desktop"},
    )
    assert result.status_code == 201, result.text
    record = result.json()
    profile = {
        "name": "Research",
        "purpose": "Fixture research",
        "status": "inactive",
        "client_ids": [record["client"]["client_id"]],
        "servers": [{"listing_id": listing.listing_id, "tools": ["echo"]}],
    }
    response = client.post("/registry/workspace/profiles", json=profile)
    assert response.status_code == 200, response.text
    return approve_profile(app, client, response.json()), record


def test_registration_cannot_grant_privileged_roles():
    app = registry()
    with TestClient(app.http_app()) as client:
        result = client.post(
            "/registry/register",
            json={
                "username": "new-user",
                "password": "long-enough-test-password",
                "role": "admin",
            },
        )
        assert result.status_code == 201, result.text
        assert (
            client.post(
                "/registry/login",
                json={"username": "new-user", "password": "long-enough-test-password"},
            ).status_code
            == 200
        )
        assert client.get("/registry/session").json()["session"]["role"] == "viewer"
        assert client.get("/registry/admin/users").status_code == 403
        assert client.get("/registry/workspace").status_code == 200


def test_profile_ownership_revision_and_readiness(monkeypatch):
    app = registry()
    with TestClient(app.http_app()) as client:
        assert client.get("/registry/workspace").status_code == 401
        login(client)
        profile, record = setup(app, client, monkeypatch)
        assert profile["owner"] == "alice"
        url = "/registry/workspace/profiles/" + profile["id"]
        changed = client.put(url, json={**profile, "status": "inactive"}).json()
        assert changed["revision"] == profile["revision"] + 1
        assert client.put(url, json=profile).status_code == 400
        assert (
            client.post(
                "/registry/workspace/profiles",
                json={
                    "name": "Empty",
                    "status": "active",
                    "client_ids": [],
                    "servers": [],
                },
            ).status_code
            == 400
        )
        login(client, "bob")
        assert client.get("/registry/workspace").json()["profiles"] == []
        assert client.put(url, json=changed).status_code == 404
        assert client.delete(url).status_code == 404
        assert (
            client.post(
                "/registry/workspace/profiles", json={**profile, "name": "Steal"}
            ).status_code
            == 400
        )
        login(client)
        assert client.delete(url).status_code == 200
        assert app._workspace.get(record["client"]["client_id"]) is not None


def test_mcp_profile_filters_tools_and_enforces_deactivation(monkeypatch):
    app = registry()

    @app.tool
    def echo() -> str:
        return "allowed"

    @app.tool
    def hidden() -> str:
        return "not allowed"

    with TestClient(app.http_app(stateless_http=True, json_response=True)) as client:
        login(client)
        profile, record = setup(app, client, monkeypatch)
        headers = {
            "Authorization": "Bearer " + record["token"],
            "Accept": "application/json, text/event-stream",
        }
        path = "/mcp/profiles/" + profile["id"]

        def rpc(method, params=None, path_override=None):
            return client.post(
                path_override or path,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params or {},
                },
            )

        response = rpc("tools/list")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert [tool["name"] for tool in payload["result"]["tools"]] == ["echo"], (
            payload
        )
        response = rpc("tools/call", {"name": "hidden", "arguments": {}})
        assert "error" in response.json() or response.json().get("result", {}).get(
            "isError"
        ), response.text
        assert rpc("tools/list", path_override="/mcp").status_code == 403
        inactive = client.put(
            "/registry/workspace/profiles/" + profile["id"],
            json={**profile, "status": "inactive"},
        )
        assert inactive.status_code == 200
        assert rpc("tools/list").status_code == 403
        assert (
            client.post(
                path, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            ).status_code
            == 401
        )


def test_workspace_persistence(registry_dsn):
    first = WorkspaceStore(registry_dsn)
    import uuid

    key = str(uuid.uuid4())
    saved = first.save(
        {
            "id": key,
            "kind": "profile",
            "owner": "persistence-fixture",
            "status": "inactive",
        }
    )
    second = WorkspaceStore(registry_dsn)
    assert second.get(key) == saved
    second.delete(saved)


def test_hosted_routes_cannot_bypass_profile(monkeypatch):
    from purecipher.hosted_runtime import build_hosted_registry_app

    app = registry()
    with TestClient(
        build_hosted_registry_app(registry=app, persistence_path=None)
    ) as client:
        login(client)
        profile, record = setup(app, client, monkeypatch)
        headers = {"Authorization": "Bearer " + record["token"]}
        for path in ["/runtime/proxy/anything/mcp", "/mcp/toolsets/anything", "/mcp"]:
            assert client.post(path, headers=headers, json={}).status_code == 403
        assert client.get("/registry/workspace", headers=headers).status_code == 403


def test_profile_tool_call_and_token_revocation(monkeypatch):
    from purecipher import PureCipherRegistry

    app = PureCipherRegistry(
        signing_secret="profile-test-only",
        auth_settings=registry()._auth_settings,
        enable_contracts=True,
        enable_consent=True,
        enable_provenance=False,
        enable_reflexive=False,
    )

    @app.tool
    def echo() -> str:
        return "profile-call-passed"

    with TestClient(app.http_app(stateless_http=True, json_response=True)) as client:
        login(client)
        profile, record = setup(app, client, monkeypatch)
        headers = {
            "Authorization": "Bearer " + record["token"],
            "Accept": "application/json, text/event-stream",
        }
        path = "/mcp/profiles/" + profile["id"]
        response = client.post(
            path,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {}},
            },
        )
        assert "profile-call-passed" in response.text, response.text
        token = app._client_store.list_tokens(record["client"]["client_id"])[0]
        app._client_store.revoke_token(token.token_id)
        assert client.post(path, headers=headers, json={}).status_code == 401


def test_registration_rejects_client_owner_slug_aliases():
    app = registry()
    with TestClient(app.http_app()) as client:
        assert (
            client.post(
                "/registry/register",
                json={"username": "alice-", "password": "long-test-password"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/registry/register",
                json={"username": "alice--", "password": "long-test-password"},
            ).status_code
            == 400
        )


def test_workspace_clients_are_private_in_legacy_governance_and_summaries(monkeypatch):
    app = registry()
    with TestClient(app.http_app()) as client:
        login(client)
        profile, record = setup(app, client, monkeypatch)
        cid = record["client"]["client_id"]
        login(client, "bob")
        assert client.get(f"/registry/clients/{cid}/governance").status_code == 404
        assert client.get("/registry/clients/activity-summary").json()["total"] == 0
        client.post("/registry/logout")
        assert client.get(f"/registry/clients/{cid}/governance").status_code == 404


def test_stateful_session_does_not_keep_access_after_deactivation(monkeypatch):
    app = registry()

    @app.tool
    def echo() -> str:
        return "ok"

    with TestClient(app.http_app(json_response=True)) as client:
        login(client)
        profile, record = setup(app, client, monkeypatch)
        url = "/mcp/profiles/" + profile["id"]
        headers = {
            "Authorization": "Bearer " + record["token"],
            "Accept": "application/json, text/event-stream",
        }
        response = client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "profile-test", "version": "1"},
                },
            },
        )
        assert response.status_code == 200, response.text
        headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
        client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        response = client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert [tool["name"] for tool in response.json()["result"]["tools"]] == ["echo"]
        assert (
            client.put(
                "/registry/workspace/profiles/" + profile["id"],
                json={**profile, "status": "inactive"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            ).status_code
            == 403
        )
