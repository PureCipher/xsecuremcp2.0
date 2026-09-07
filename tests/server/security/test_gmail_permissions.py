"""Gmail upgrades preserve existing grants and require explicit owner permission."""

import asyncio
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from purecipher import consumer_oauth
from purecipher.consumer_google_permissions import (
    GMAIL_COMPOSE,
    GMAIL_COMPOSE_TOOLS,
    GMAIL_MANAGE_TOOLS,
    GMAIL_MODIFY,
    GMAIL_READ_TOOLS,
    GMAIL_READONLY,
    GMAIL_SEND,
    required_scopes,
    validate_tool_scope,
)
from purecipher.product_connections import connection_blocker, decrypt
from tests.server.security.test_consumer_runtime import add, config, enabled
from tests.server.security.test_workspace_profiles import login


def grant(mode="read_only", scope=GMAIL_READONLY, **extra):
    return {
        "access_token": "private-access",
        "refresh_token": "private-refresh",
        "expires_at": time.time() + 3600,
        "scope": scope,
        "access_mode": mode,
        **extra,
    }


@pytest.mark.parametrize("tool", sorted(GMAIL_READ_TOOLS))
def test_existing_readonly_grants_support_all_read_tools(tool):
    validate_tool_scope({"scope": GMAIL_READONLY}, tool)
    validate_tool_scope(grant("manage_mail", GMAIL_MODIFY), tool)


@pytest.mark.parametrize("tool", sorted(GMAIL_COMPOSE_TOOLS | GMAIL_MANAGE_TOOLS))
def test_provider_broad_grant_does_not_override_readonly_connection_choice(tool):
    with pytest.raises(ValueError, match="connection"):
        validate_tool_scope(
            grant(scope=" ".join([GMAIL_READONLY, GMAIL_COMPOSE, GMAIL_MODIFY])), tool
        )


@pytest.mark.parametrize("tool", sorted(GMAIL_COMPOSE_TOOLS))
def test_draft_and_send_tools_require_mode_and_granted_scope(tool):
    validate_tool_scope(grant("draft_and_send", GMAIL_COMPOSE), tool)
    validate_tool_scope(grant("manage_mail", GMAIL_MODIFY), tool)
    with pytest.raises(ValueError, match="not granted"):
        validate_tool_scope(grant("draft_and_send", GMAIL_READONLY), tool)


def test_send_only_scope_cannot_manage_drafts_or_mail():
    validate_tool_scope(grant("draft_and_send", GMAIL_SEND), "gmail_send_message")
    with pytest.raises(ValueError):
        validate_tool_scope(grant("draft_and_send", GMAIL_SEND), "gmail_create_draft")
    with pytest.raises(ValueError):
        validate_tool_scope(
            grant("draft_and_send", GMAIL_MODIFY), "gmail_trash_message"
        )
    with pytest.raises(ValueError, match="Unknown Gmail"):
        validate_tool_scope(grant("manage_mail", GMAIL_MODIFY), "gmail_delete_message")


def test_permission_modes_keep_readonly_default_and_other_products_unchanged():
    assert required_scopes("google-gmail", {}) == {GMAIL_READONLY}
    assert required_scopes("google-gmail", {"access_mode": "draft_and_send"}) == {
        GMAIL_READONLY,
        GMAIL_COMPOSE,
    }
    assert required_scopes("google-gmail", {"access_mode": "manage_mail"}) == {
        GMAIL_MODIFY
    }
    assert required_scopes("google-docs", {}) == {
        "https://www.googleapis.com/auth/documents.readonly"
    }
    with pytest.raises(ValueError):
        required_scopes("google-gmail", {"access_mode": "unrestricted"})


def test_mode_changes_disconnect_but_name_edits_preserve_existing_readonly_grants(
    monkeypatch,
):
    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        assert item["values"] == {"access_mode": "read_only"}
        assert item["missing"] == []
        row = consumer_oauth.store_grant(app, app._workspace.get(item["id"]), grant())
        url = "/registry/workspace/connections/" + item["id"]
        response = client.put(
            url, json={"name": "Renamed", "revision": row["revision"], "values": {}}
        )
        assert response.status_code == 200
        assert response.json()["runtime_ready"] is True
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"]))
        response = client.put(
            url,
            json={
                "name": "Renamed",
                "revision": response.json()["revision"],
                "values": {"access_mode": "manage_mail"},
            },
        )
        assert response.status_code == 200
        assert response.json()["runtime_ready"] is False
        assert response.json()["requested_scopes"] == [GMAIL_MODIFY]
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None
        assert (
            decrypt(app, app._workspace.get(item["id"]))["access_mode"] == "manage_mail"
        )
        assert (
            "private-access" not in response.text
            and "private-refresh" not in response.text
        )


@pytest.mark.parametrize("mode", ["read_only", "draft_and_send", "manage_mail"])
def test_oauth_requests_saved_mode_scopes_and_records_owner_bound_grant(
    monkeypatch, mode
):
    app = enabled(monkeypatch)
    config(monkeypatch)
    requested = required_scopes("google-gmail", {"access_mode": mode})

    async def exchange(data):
        assert data["grant_type"] == "authorization_code"
        return grant(scope=" ".join(requested))

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail", {"access_mode": mode})
        response = client.post(
            "/registry/workspace/connections/" + item["id"] + "/authorize"
        )
        assert response.status_code == 200
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
        assert connection["access_mode"] == mode
        assert set(connection["granted_scopes"]) == requested
        assert (
            "private-access" not in response.text
            and "private-refresh" not in response.text
        )


def test_insufficient_upgrade_grant_is_rejected_without_losing_existing_account(
    monkeypatch,
):
    app = enabled(monkeypatch)
    config(monkeypatch)

    async def exchange(data):
        return grant()

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail", {"access_mode": "draft_and_send"})
        response = client.post(
            "/registry/workspace/connections/" + item["id"] + "/authorize"
        )
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][
            0
        ]
        response = client.get(
            "/registry/workspace/oauth/callback",
            params={"state": state, "code": "fixture"},
            follow_redirects=False,
        )
        assert "failed" in response.headers["location"]
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None
        assert app._workspace.get(item["id"])


def test_legacy_readonly_refresh_and_unexpired_scope_gate(monkeypatch):
    app = enabled(monkeypatch)
    config(monkeypatch)
    calls = []

    async def refresh(data):
        calls.append(data)
        return {"access_token": "refreshed", "expires_at": time.time() + 3600}

    monkeypatch.setattr(consumer_oauth, "token_request", refresh)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        old = grant(expires_at=0)
        old.pop("access_mode")
        row = consumer_oauth.store_grant(app, app._workspace.get(item["id"]), old)
        assert (
            asyncio.run(
                consumer_oauth.access_token(app, row, tool_name="gmail_list_messages")
            )
            == "refreshed"
        )
        assert len(calls) == 1
        row = app._workspace.get(item["id"])
        with pytest.raises(ValueError):
            asyncio.run(
                consumer_oauth.access_token(app, row, tool_name="gmail_send_message")
            )
        assert len(calls) == 1
        wrong = consumer_oauth.store_grant(app, row, grant(scope="unrelated"))
        with pytest.raises(ValueError, match="permissions"):
            asyncio.run(
                consumer_oauth.access_token(app, wrong, tool_name="gmail_profile")
            )
        assert len(calls) == 1


def test_refreshed_grant_cannot_drop_required_permissions(monkeypatch):
    app = enabled(monkeypatch)

    async def refresh(data):
        return {
            "access_token": "private-narrowed",
            "expires_at": time.time() + 3600,
            "scope": GMAIL_READONLY,
        }

    monkeypatch.setattr(consumer_oauth, "token_request", refresh)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail", {"access_mode": "draft_and_send"})
        row = consumer_oauth.store_grant(
            app,
            app._workspace.get(item["id"]),
            grant("draft_and_send", GMAIL_READONLY + " " + GMAIL_COMPOSE, expires_at=0),
        )
        with pytest.raises(ValueError, match="permissions"):
            asyncio.run(
                consumer_oauth.access_token(app, row, tool_name="gmail_send_message")
            )
        assert (
            consumer_oauth.load_grant(app, app._workspace.get(item["id"]))[
                "access_token"
            ]
            == "private-access"
        )


def test_profile_blocker_explains_missing_gmail_write_access(monkeypatch):
    from fastmcp.server.security.gateway.tool_marketplace import PublishStatus

    app = enabled(monkeypatch)
    listing = app._marketplace().publish(
        "purecipher-google-gmail",
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
    )
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        consumer_oauth.store_grant(app, app._workspace.get(item["id"]), grant())
        selected = {
            "listing_id": listing.listing_id,
            "connection_id": item["id"],
            "tools": ["gmail_profile"],
        }
        owner = app._workspace.get(item["id"])["owner"]
        assert connection_blocker(app, owner, selected) is None
        selected["tools"] = ["gmail_send_message"]
        assert "connection" in connection_blocker(app, owner, selected)


def test_pending_oauth_cannot_survive_a_mode_change(monkeypatch):
    app = enabled(monkeypatch)
    config(monkeypatch)
    calls = []

    async def exchange(data):
        calls.append(data)
        return grant()

    monkeypatch.setattr(consumer_oauth, "token_request", exchange)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        path = "/registry/workspace/connections/" + item["id"]
        response = client.post(path + "/authorize")
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][
            0
        ]
        assert (
            client.put(
                path,
                json={
                    "name": "My account",
                    "revision": item["revision"],
                    "values": {"access_mode": "manage_mail"},
                },
            ).status_code
            == 200
        )
        response = client.get(
            "/registry/workspace/oauth/callback",
            params={"state": state, "code": "fixture"},
            follow_redirects=False,
        )
        assert "failed" in response.headers["location"]
        assert calls == []
        assert consumer_oauth.load_grant(app, app._workspace.get(item["id"])) is None


def test_connection_grant_validation_rejects_wrong_mode_scope_or_requested_intent(
    monkeypatch,
):
    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail", {"access_mode": "draft_and_send"})
        row = app._workspace.get(item["id"])
        for invalid in [
            grant("read_only", GMAIL_READONLY + " " + GMAIL_COMPOSE),
            grant("draft_and_send", GMAIL_READONLY),
            grant(
                "draft_and_send",
                GMAIL_READONLY + " " + GMAIL_COMPOSE,
                requested_scopes=[GMAIL_READONLY],
            ),
        ]:
            with pytest.raises(ValueError):
                consumer_oauth.validate_connection_grant(
                    app, row, invalid, tool_name="gmail_send_message"
                )
        consumer_oauth.validate_connection_grant(
            app,
            row,
            grant("draft_and_send", GMAIL_READONLY + " " + GMAIL_COMPOSE),
            tool_name="gmail_send_message",
        )


def test_invalid_gmail_permissions_do_not_report_runtime_ready(monkeypatch):
    from purecipher.consumer_runtime import runtime_ready

    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        item = add(client, "google-gmail")
        row = consumer_oauth.store_grant(
            app, app._workspace.get(item["id"]), grant(scope="unrelated")
        )
        assert runtime_ready(app, row) is False
        response = client.get("/registry/workspace/connections")
        assert response.json()["connections"][0]["runtime_ready"] is False
