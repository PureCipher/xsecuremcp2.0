"""Consumer runtime boundaries and complete mocked OAuth code exchange."""

import asyncio
import time
from urllib.parse import parse_qs, urlsplit

from starlette.testclient import TestClient

from purecipher import PureCipherRegistry, consumer_oauth, consumer_runtime
from purecipher.product_schemas import PRODUCT_SCHEMAS
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


def enabled(monkeypatch):
    monkeypatch.setenv("PURECIPHER_CONSUMER_RUNTIME_ENABLED", "true")
    return registry()


def config(monkeypatch):
    monkeypatch.setenv("PURECIPHER_GOOGLE_CLIENT_ID", "fixture-client")
    monkeypatch.setenv("PURECIPHER_GOOGLE_CLIENT_SECRET", "fixture-app-secret")
    monkeypatch.setenv(
        "PURECIPHER_CONSUMER_OAUTH_REDIRECT_URI",
        "https://registry.example/api/workspace/oauth/callback",
    )


def add(client, product, values=None):
    response = client.post(
        "/registry/workspace/connections",
        json={"product": product, "name": "My account", "values": values or {}},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_oauth_roundtrip_is_single_use_owner_bound_and_redacted(monkeypatch):
    app = enabled(monkeypatch)
    config(monkeypatch)
    exchanges = []

    async def exchange(data):
        exchanges.append(data)
        return {
            "access_token": "private-access",
            "refresh_token": "private-refresh",
            "expires_at": time.time() + 3600,
            "scope": " ".join(PRODUCT_SCHEMAS["google-gmail"]["scopes"]),
        }

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        url = "/registry/workspace/connections/" + item["id"]
        response = client.post(url + "/authorize")
        assert response.status_code == 200, response.text
        params = parse_qs(urlsplit(response.json()["authorization_url"]).query)
        state = params["state"][0]
        assert params["code_challenge_method"] == ["S256"]
        callback = (
            "/registry/workspace/oauth/callback?state=" + state + "&code=fixture-code"
        )
        login(client, "bob")
        assert (
            "failed" in client.get(callback, follow_redirects=False).headers["location"]
        )
        assert not exchanges
        login(client)
        assert (
            "success"
            in client.get(callback, follow_redirects=False).headers["location"]
        )
        assert exchanges[0]["code_verifier"] and exchanges[0][
            "redirect_uri"
        ].startswith("https://registry.example/")
        assert (
            "failed" in client.get(callback, follow_redirects=False).headers["location"]
        )
        assert len(exchanges) == 1
        response = client.get("/registry/workspace/connections")
        assert (
            "private-access" not in response.text
            and "private-refresh" not in response.text
        )
        assert response.json()["connections"][0]["runtime_ready"]
        assert "private-access" not in str(app._workspace.get(item["id"]))
        assert client.post(url + "/disconnect").json()["runtime_ready"] is False
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None


def test_oauth_changes_and_missing_permissions_fail_closed(monkeypatch):
    app = enabled(monkeypatch)
    config(monkeypatch)

    async def exchange(data):
        return {
            "access_token": "private",
            "expires_at": time.time() + 3600,
            "scope": "unrelated",
        }

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-docs")
        url = "/registry/workspace/connections/" + item["id"]
        for changed in [False, True]:
            auth = client.post(url + "/authorize").json()
            state = parse_qs(urlsplit(auth["authorization_url"]).query)["state"][0]
            if changed:
                client.put(url, json={**item, "name": "Changed", "values": {}})
            assert (
                "failed"
                in client.get(
                    "/registry/workspace/oauth/callback?state="
                    + state
                    + "&code=fixture",
                    follow_redirects=False,
                ).headers["location"]
            )
        assert not client.get("/registry/workspace/connections").json()["connections"][
            0
        ]["runtime_ready"]


def test_expired_grant_refresh_and_concurrent_disconnect(monkeypatch):
    app = enabled(monkeypatch)
    config(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-tasks")
        row = app._workspace.get(item["id"])
        row = consumer_oauth.store_grant(
            app,
            row,
            {
                "access_token": "old",
                "refresh_token": "refresh",
                "expires_at": 0,
                "scope": " ".join(PRODUCT_SCHEMAS["google-tasks"]["scopes"]),
            },
        )

        async def refresh(data):
            assert data == {"grant_type": "refresh_token", "refresh_token": "refresh"}
            return {"access_token": "new", "expires_at": time.time() + 3600}

        monkeypatch.setattr(consumer_oauth, "token_request", refresh)
        assert asyncio.run(consumer_oauth.access_token(app, row)) == "new"
        assert (
            consumer_oauth.load_grant(app, app._workspace.get(item["id"]))[
                "refresh_token"
            ]
            == "refresh"
        )
        # A disconnect wins over an in-flight refresh, via record revision.
        client.post("/registry/workspace/connections/" + item["id"] + "/disconnect")
        import pytest

        with pytest.raises(ValueError):
            asyncio.run(consumer_oauth.access_token(app, row))


def test_actual_profile_call_uses_only_selected_user_key(monkeypatch):
    enabled(monkeypatch)
    app = PureCipherRegistry(
        signing_secret="test-secret",
        auth_settings=registry()._auth_settings,
        enable_contracts=False,
        enable_consent=False,
        enable_provenance=False,
        enable_reflexive=False,
    )
    seen = []

    async def get(url, headers, params=None):
        seen.append((url, headers.copy(), params))
        return {"web": {"results": []}}

    monkeypatch.setattr(consumer_runtime, "provider_get", get)
    from fastmcp.server.security.gateway.tool_marketplace import PublishStatus

    listing = app._marketplace().publish(
        "purecipher-brave-search",
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={
            "introspection": {"tool_names": ["brave_web_search"]},
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
        conn = add(client, "brave-search", {"BRAVE_API_KEY": "alice-key"})
        assert client.post(
            "/registry/workspace/connections/" + conn["id"] + "/verify"
        ).json()["runtime_ready"]
        entry = client.post(
            "/registry/workspace/clients", json={"display_name": "My client"}
        ).json()
        profile = client.post(
            "/registry/workspace/profiles",
            json={
                "name": "Search",
                "status": "active",
                "client_ids": [entry["client"]["client_id"]],
                "servers": [
                    {
                        "listing_id": listing.listing_id,
                        "tools": ["brave_web_search"],
                        "connection_id": conn["id"],
                    }
                ],
            },
        ).json()
        assert "id" in profile, profile
        headers = {
            "Authorization": "Bearer " + entry["token"],
            "Accept": "application/json, text/event-stream",
        }
        path = "/mcp/profiles/" + profile["id"]
        rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "brave_web_search", "arguments": {"query": "test"}},
        }
        response = client.post(path, headers=headers, json=rpc)
        assert (
            response.status_code == 200
            and "error" not in response.json()
            and not response.json().get("result", {}).get("isError")
        ), response.text
        assert seen[-1][1] == {"X-Subscription-Token": "alice-key"}
        assert (
            "alice-key" not in response.text and consumer_runtime._ACCESS.get() is None
        )
        login(client, "bob")
        add(client, "brave-search", {"BRAVE_API_KEY": "bob-key"})
        assert (
            client.post(
                "/registry/workspace/profiles", json={**profile, "id": None}
            ).status_code
            == 400
        )
        login(client)
        client.post("/registry/workspace/connections/" + conn["id"] + "/disconnect")
        count = len(seen)
        assert client.post(path, headers=headers, json=rpc).status_code == 403
        assert len(seen) == count


def test_token_exchange_uses_fixed_origin_and_body_credentials(monkeypatch):
    import httpx

    config(monkeypatch)
    original = httpx.AsyncClient
    captured = []

    def handler(request):
        assert str(request.url) == "https://oauth2.googleapis.com/token"
        fields = parse_qs(request.content.decode())
        assert fields["client_secret"] == ["fixture-app-secret"]
        assert fields["code_verifier"] == ["verifier"]
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "fixture-access",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = asyncio.run(
        consumer_oauth.token_request(
            {
                "grant_type": "authorization_code",
                "code": "fixture",
                "code_verifier": "verifier",
            }
        )
    )
    assert result["access_token"] == "fixture-access" and len(captured) == 1
