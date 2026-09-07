"""Google connection choices bind scopes, saved grants and selected tool access."""

import asyncio
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from purecipher import consumer_oauth
from purecipher.consumer_google_permissions import (
    CALENDAR_ADMIN_TOOLS,
    DRIVE_CONTENT_TOOLS,
    GOOGLE_OAUTH_MODES,
    GOOGLE_READ_TOOLS,
    GOOGLE_WRITE_TOOLS,
    google_access_mode,
    required_scopes,
    validate_google_tool_scope,
)
from purecipher.product_connections import decrypt
from purecipher.product_schemas import PRODUCT_SCHEMAS
from tests.server.security.test_consumer_runtime import add, config, enabled
from tests.server.security.test_workspace_profiles import login

PRODUCTS = sorted(set(GOOGLE_OAUTH_MODES) - {"google-gmail"})
MODE_CASES = [
    (product, mode["id"])
    for product in PRODUCTS
    for mode in GOOGLE_OAUTH_MODES[product]
]
READ_CASES = [
    (product, tool)
    for product in PRODUCTS
    for tool in sorted(GOOGLE_READ_TOOLS[product])
]
WRITE_CASES = [
    (product, tool)
    for product in PRODUCTS
    for tool in sorted(GOOGLE_WRITE_TOOLS[product])
]
RESTRICTED_CASES = (
    WRITE_CASES
    + [("google-drive", tool) for tool in sorted(DRIVE_CONTENT_TOOLS)]
    + [("google-calendar", tool) for tool in sorted(CALENDAR_ADMIN_TOOLS)]
)


def grant(product, mode="read_only", **extra):
    return {
        "access_token": "private-google-access",
        "refresh_token": "private-google-refresh",
        "expires_at": time.time() + 3600,
        "scope": " ".join(required_scopes(product, {"access_mode": mode})),
        "access_mode": mode,
        **extra,
    }


@pytest.mark.parametrize("product", PRODUCTS)
def test_schema_default_preserves_existing_readonly_scope_and_describes_upgrade(
    product,
):
    assert google_access_mode(product, {}) == "read_only"
    assert required_scopes(product, {}) == set(PRODUCT_SCHEMAS[product]["scopes"])
    assert PRODUCT_SCHEMAS[product]["oauth_modes"] == GOOGLE_OAUTH_MODES[product]
    assert PRODUCT_SCHEMAS[product]["oauth_mode_field"] == "access_mode"
    with pytest.raises(ValueError):
        google_access_mode(product, {"access_mode": "unlimited"})


@pytest.mark.parametrize("product,tool", READ_CASES)
def test_all_read_tools_accept_legacy_readonly_and_current_write_grants(product, tool):
    readonly = grant(product)
    readonly.pop("access_mode")
    validate_google_tool_scope(product, readonly, tool)
    validate_google_tool_scope(
        product, grant(product, GOOGLE_OAUTH_MODES[product][-1]["id"]), tool
    )


@pytest.mark.parametrize("product,tool", RESTRICTED_CASES)
def test_broader_provider_grant_never_overrides_readonly_choice(product, tool):
    broad = grant(product, GOOGLE_OAUTH_MODES[product][-1]["id"])
    broad["access_mode"] = "read_only"
    with pytest.raises(ValueError, match="requires"):
        validate_google_tool_scope(product, broad, tool)
    broad.pop("access_mode")
    with pytest.raises(ValueError, match="requires"):
        validate_google_tool_scope(product, broad, tool)


@pytest.mark.parametrize("product,tool", RESTRICTED_CASES)
def test_write_scope_and_selected_mode_are_both_required(product, tool):
    write_mode = GOOGLE_OAUTH_MODES[product][-1]["id"]
    validate_google_tool_scope(product, grant(product, write_mode), tool)
    missing_scope = grant(
        product, write_mode, scope=" ".join(required_scopes(product, {}))
    )
    with pytest.raises(ValueError, match="not granted"):
        validate_google_tool_scope(product, missing_scope, tool)


def test_intermediate_modes_cannot_elevate_to_administration_or_file_writes():
    for tool in GOOGLE_WRITE_TOOLS["google-calendar"]:
        validate_google_tool_scope(
            "google-calendar", grant("google-calendar", "manage_events"), tool
        )
    for tool in CALENDAR_ADMIN_TOOLS:
        broad = grant("google-calendar", "manage_calendars")
        broad["access_mode"] = "manage_events"
        with pytest.raises(ValueError, match="manage-calendars"):
            validate_google_tool_scope("google-calendar", broad, tool)
    for tool in DRIVE_CONTENT_TOOLS:
        validate_google_tool_scope(
            "google-drive", grant("google-drive", "read_files"), tool
        )
    for tool in GOOGLE_WRITE_TOOLS["google-drive"]:
        broad = grant("google-drive", "manage_files")
        broad["access_mode"] = "read_files"
        with pytest.raises(ValueError, match="requires"):
            validate_google_tool_scope("google-drive", broad, tool)
    with pytest.raises(ValueError, match="Unknown"):
        validate_google_tool_scope(
            "google-docs", grant("google-docs", "edit_documents"), "drive_delete_file"
        )


@pytest.mark.parametrize("product,mode", MODE_CASES)
def test_oauth_authorize_callback_persists_exact_saved_mode_scopes(
    monkeypatch, product, mode
):
    app = enabled(monkeypatch)
    config(monkeypatch)
    requested = required_scopes(product, {"access_mode": mode})

    async def exchange(data):
        assert data["grant_type"] == "authorization_code"
        return grant(product, mode)

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, product, {"access_mode": mode})
        response = client.post(
            "/registry/workspace/connections/" + item["id"] + "/authorize"
        )
        assert response.status_code == 200, response.text
        params = parse_qs(urlsplit(response.json()["authorization_url"]).query)
        assert set(params["scope"][0].split()) == requested
        response = client.get(
            "/registry/workspace/oauth/callback",
            params={"state": params["state"][0], "code": "fixture"},
            follow_redirects=False,
        )
        assert "success" in response.headers["location"]
        saved = consumer_oauth.load_grant(app, app._workspace.get(item["id"]))
        assert saved["access_mode"] == mode
        assert set(saved["requested_scopes"]) == requested
        response = client.get("/registry/workspace/connections")
        connection = response.json()["connections"][0]
        assert connection["access_mode"] == mode and connection["runtime_ready"]
        assert set(connection["granted_scopes"]) == requested
        assert (
            "private-google-access" not in response.text
            and "private-google-refresh" not in response.text
        )


@pytest.mark.parametrize("product", PRODUCTS)
def test_legacy_readonly_refresh_and_upgrade_invalidates_grant(monkeypatch, product):
    app = enabled(monkeypatch)
    config(monkeypatch)
    calls = []

    async def refresh(data):
        calls.append(data)
        return {"access_token": "refreshed-private", "expires_at": time.time() + 3600}

    monkeypatch.setattr(consumer_oauth, "token_request", refresh)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, product)
        old = grant(product, expires_at=0)
        old.pop("access_mode")
        row = consumer_oauth.store_grant(app, app._workspace.get(item["id"]), old)
        read_tool = next(iter(GOOGLE_READ_TOOLS[product]))
        assert (
            asyncio.run(consumer_oauth.access_token(app, row, tool_name=read_tool))
            == "refreshed-private"
        )
        assert len(calls) == 1
        row = app._workspace.get(item["id"])
        url = "/registry/workspace/connections/" + item["id"]
        result = client.put(
            url, json={"name": "Renamed", "revision": row["revision"], "values": {}}
        )
        assert result.status_code == 200 and result.json()["runtime_ready"]
        mode = GOOGLE_OAUTH_MODES[product][-1]["id"]
        result = client.put(
            url,
            json={
                "name": "Upgraded",
                "revision": result.json()["revision"],
                "values": {"access_mode": mode},
            },
        )
        assert result.status_code == 200 and not result.json()["runtime_ready"]
        assert set(result.json()["requested_scopes"]) == required_scopes(
            product, {"access_mode": mode}
        )
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None
        assert decrypt(app, app._workspace.get(item["id"]))["access_mode"] == mode


@pytest.mark.parametrize("product", PRODUCTS)
def test_mode_drift_or_missing_scopes_cannot_be_runtime_ready(monkeypatch, product):
    from purecipher.consumer_runtime import runtime_ready

    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        mode = GOOGLE_OAUTH_MODES[product][-1]["id"]
        item = add(client, product, {"access_mode": mode})
        row = consumer_oauth.store_grant(
            app, app._workspace.get(item["id"]), grant(product)
        )
        assert not runtime_ready(app, row)
        row = consumer_oauth.store_grant(
            app, row, grant(product, mode, requested_scopes=["wrong"])
        )
        assert not runtime_ready(app, row)
        row = consumer_oauth.store_grant(app, row, grant(product, mode))
        assert runtime_ready(app, row)


@pytest.mark.parametrize("product", PRODUCTS)
def test_callback_rejects_insufficient_scope_and_changed_intent(monkeypatch, product):
    app = enabled(monkeypatch)
    config(monkeypatch)

    async def exchange(data):
        return grant(product)

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        mode = GOOGLE_OAUTH_MODES[product][-1]["id"]
        item = add(client, product, {"access_mode": mode})
        result = client.post(
            "/registry/workspace/connections/" + item["id"] + "/authorize"
        )
        state = parse_qs(urlsplit(result.json()["authorization_url"]).query)["state"][0]
        result = client.get(
            "/registry/workspace/oauth/callback",
            params={"state": state, "code": "fixture"},
            follow_redirects=False,
        )
        assert "failed" in result.headers["location"]
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None


@pytest.mark.parametrize("product", PRODUCTS)
def test_legacy_pending_state_with_null_mode_remains_readonly(monkeypatch, product):
    import hashlib

    app = enabled(monkeypatch)
    config(monkeypatch)

    async def exchange(data):
        # Google may omit scope when it grants exactly the requested scopes.
        return {"access_token": "private-legacy", "expires_at": time.time() + 3600}

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, product)
        result = client.post(
            "/registry/workspace/connections/" + item["id"] + "/authorize"
        )
        state = parse_qs(urlsplit(result.json()["authorization_url"]).query)["state"][0]
        pending = app._workspace.get(hashlib.sha256(state.encode()).hexdigest())
        pending.pop("requested_scopes")
        pending["access_mode"] = None
        app._workspace.save(pending, pending["revision"])
        result = client.get(
            "/registry/workspace/oauth/callback",
            params={"state": state, "code": "fixture"},
            follow_redirects=False,
        )
        assert "success" in result.headers["location"]
        saved = consumer_oauth.load_grant(app, app._workspace.get(item["id"]))
        assert saved["access_mode"] == "read_only"
        assert set(saved["scope"].split()) == required_scopes(product, {})


@pytest.mark.parametrize("product", PRODUCTS)
def test_refresh_cannot_drop_write_permissions_or_replace_previous_grant(
    monkeypatch, product
):
    app = enabled(monkeypatch)
    mode = GOOGLE_OAUTH_MODES[product][-1]["id"]

    async def refresh(data):
        return grant(product, access_token="private-downgraded")

    monkeypatch.setattr(consumer_oauth, "token_request", refresh)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, product, {"access_mode": mode})
        row = consumer_oauth.store_grant(
            app, app._workspace.get(item["id"]), grant(product, mode, expires_at=0)
        )
        with pytest.raises(ValueError, match="permissions"):
            asyncio.run(
                consumer_oauth.access_token(
                    app, row, tool_name=next(iter(GOOGLE_WRITE_TOOLS[product]))
                )
            )
        assert (
            consumer_oauth.load_grant(app, app._workspace.get(item["id"]))[
                "access_token"
            ]
            == "private-google-access"
        )
