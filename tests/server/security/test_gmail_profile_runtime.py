"""Gmail discovery and calls traverse the actual SecureMCP profile HTTP stack."""

import asyncio
import base64
import json
import time
from email import policy
from email.parser import BytesParser

import httpx
import pytest
from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus
from fastmcp.server.security.policy.policies.published_tools import PublishedToolsPolicy
from purecipher import PureCipherRegistry, consumer_oauth, consumer_runtime
from purecipher.consumer_google_permissions import GMAIL_MODIFY, GMAIL_READONLY
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_consumer_runtime import add
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login

NAMES = [
    "gmail_get_message",
    "gmail_send_message",
    "gmail_reply_message",
    "gmail_trash_message",
]


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv("PURECIPHER_CONSUMER_RUNTIME_ENABLED", "true")
    app = PureCipherRegistry(
        signing_secret="fixture-signing",
        auth_settings=registry()._auth_settings,
        enable_contracts=True,
        enable_consent=True,
        enable_provenance=False,
        enable_reflexive=False,
    )
    listing = app._marketplace().publish(
        "purecipher-google-gmail",
        author="purecipher",
        version="0.4.0",
        status=PublishStatus.PUBLISHED,
        metadata={"introspection": {"tool_names": NAMES}, "deployment_ready": True},
    )
    monkeypatch.setattr(
        app,
        "_get_public_listing",
        lambda name: listing if name == listing.tool_name else None,
    )
    seen = []
    hooks = {}
    original = httpx.AsyncClient

    def handle(request):
        assert request.url.host == "gmail.googleapis.com"
        assert request.headers["authorization"] == "Bearer alice-google-token"
        seen.append(request)
        if hook := hooks.get("request"):
            hook(request)
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "alice@example.com"})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "original-message",
                    "threadId": "thread-1",
                    "payload": {
                        "headers": [
                            {"name": "Message-ID", "value": "<original@example.com>"},
                            {"name": "Subject", "value": "Original subject"},
                        ]
                    },
                },
            )
        return httpx.Response(200, json={"id": "sent-message", "threadId": "thread-1"})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    with TestClient(app.http_app(stateless_http=True, json_response=True)) as client:
        login(client)
        connection = add(client, "google-gmail", {"access_mode": "manage_mail"})
        consumer_oauth.store_grant(
            app,
            app._workspace.get(connection["id"]),
            {
                "access_token": "alice-google-token",
                "expires_at": time.time() + 3600,
                "scope": GMAIL_MODIFY,
                "access_mode": "manage_mail",
                "requested_scopes": [GMAIL_MODIFY],
            },
        )
        entry = client.post(
            "/registry/workspace/clients", json={"display_name": "Alice laptop"}
        ).json()
        response = client.post(
            "/registry/workspace/profiles",
            json={
                "name": "Mail",
                "purpose": "Fixture mailbox operations",
                "status": "inactive",
                "client_ids": [entry["client"]["client_id"]],
                "servers": [
                    {
                        "listing_id": listing.listing_id,
                        "tools": NAMES,
                        "connection_id": connection["id"],
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
        profile = approve_profile(app, client, response.json())
        path = "/mcp/profiles/" + profile["id"]
        headers = {
            "Authorization": "Bearer " + entry["token"],
            "Accept": "application/json, text/event-stream",
        }

        def rpc(method, params=None, override_headers=None):
            return client.post(
                path,
                headers=override_headers or headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params or {},
                },
            )

        def call(name, args):
            return rpc("tools/call", {"name": name, "arguments": args})

        yield app, client, connection, entry, profile, rpc, call, seen, hooks


def success(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body and not body.get("result", {}).get("isError"), (
        response.text
    )
    assert "alice-google-token" not in response.text
    return body["result"]


def denied(response):
    assert response.status_code in {400, 401, 403} or (
        response.status_code == 200
        and (
            "error" in response.json()
            or response.json().get("result", {}).get("isError")
        )
    ), response.text


def test_profile_discovery_and_read_send_keep_scoped_tokens_and_tool_annotations(
    runtime,
):
    app, client, connection, entry, profile, rpc, call, seen, _ = runtime
    tools = success(rpc("tools/list"))["tools"]
    assert {tool["name"] for tool in tools} == set(NAMES)
    assert next(t for t in tools if t["name"] == "gmail_get_message")["annotations"][
        "readOnlyHint"
    ]
    send = next(t for t in tools if t["name"] == "gmail_send_message")
    assert send["annotations"]["readOnlyHint"] is False
    assert send["annotations"]["idempotentHint"] is False
    assert "content" in send["inputSchema"]["properties"]
    success(call("gmail_get_message", {"message_id": "original-message"}))
    success(
        call(
            "gmail_send_message",
            {
                "content": {
                    "to": ["recipient@example.com"],
                    "subject": "Explicit send",
                    "body": "Fixture message",
                }
            },
        )
    )
    assert seen[-1].method == "POST" and seen[-1].url.path.endswith("/messages/send")
    mime = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(json.loads(seen[-1].content)["raw"])
    )
    assert mime["From"] == "alice@example.com" and mime["To"] == "recipient@example.com"
    body = mime.get_body(preferencelist=("plain",))
    assert body is not None
    assert body.get_content().strip() == "Fixture message"
    assert consumer_runtime._ACCESS.get() is None
    count = len(seen)
    denied(call("gmail_delete_label", {"label_id": "Label_1"}))
    assert len(seen) == count
    login(client, "bob")
    outsider = client.post(
        "/registry/workspace/clients", json={"display_name": "Bob laptop"}
    ).json()
    denied(
        rpc(
            "tools/list",
            override_headers={
                "Authorization": "Bearer " + outsider["token"],
                "Accept": "application/json, text/event-stream",
            },
        )
    )
    assert len(seen) == count


def test_connection_permission_downgrade_stops_active_profile_before_provider_calls(
    runtime,
):
    app, client, connection, entry, profile, rpc, call, seen, _ = runtime
    row = app._workspace.get(connection["id"])
    response = client.put(
        "/registry/workspace/connections/" + connection["id"],
        json={
            "revision": row["revision"],
            "name": "Read only now",
            "values": {"access_mode": "read_only"},
        },
    )
    assert response.status_code == 200 and not response.json()["runtime_ready"]
    consumer_oauth.store_grant(
        app,
        app._workspace.get(connection["id"]),
        {
            "access_token": "alice-google-token",
            "expires_at": time.time() + 3600,
            "scope": GMAIL_READONLY,
            "access_mode": "read_only",
            "requested_scopes": [GMAIL_READONLY],
        },
    )
    denied(
        call(
            "gmail_send_message",
            {"content": {"to": ["recipient@example.com"], "body": "Denied"}},
        )
    )
    assert not seen


def test_disconnect_between_compose_read_and_send_prevents_send(runtime):
    app, client, connection, entry, profile, rpc, call, seen, hooks = runtime

    def disconnect(request):
        if request.url.path.endswith("/profile"):
            row = app._workspace.get(connection["id"])
            row.pop("oauth_encrypted", None)
            app._workspace.save(row, row["revision"])

    hooks["request"] = disconnect
    denied(
        call(
            "gmail_send_message",
            {"content": {"to": ["recipient@example.com"], "body": "Must not send"}},
        )
    )
    assert len(seen) == 1 and seen[0].method == "GET"
    assert consumer_runtime._ACCESS.get() is None


def test_client_token_revocation_between_compose_read_and_send_prevents_send(runtime):
    app, client, connection, entry, profile, rpc, call, seen, hooks = runtime

    def revoke(request):
        if request.url.path.endswith("/profile"):
            token = app._client_store.list_tokens(entry["client"]["client_id"])[0]
            app._client_store.revoke_token(token.token_id)

    hooks["request"] = revoke
    denied(
        call(
            "gmail_send_message",
            {"content": {"to": ["recipient@example.com"], "body": "Must not send"}},
        )
    )
    assert len(seen) == 1 and seen[0].method == "GET"


def test_profile_edits_require_new_approval_and_policies_still_block_calls(runtime):
    app, client, connection, entry, profile, rpc, call, seen, _ = runtime
    # A restrictive published/read-only pack without verified evidence fails
    # closed even for an otherwise fully approved Gmail connection and profile.
    asyncio.run(
        app._required_context().policy_engine.add_provider(PublishedToolsPolicy())
    )
    denied(
        call(
            "gmail_send_message",
            {"content": {"to": ["recipient@example.com"], "body": "Blocked by policy"}},
        )
    )
    assert not seen
    response = client.put(
        "/registry/workspace/profiles/" + profile["id"],
        json={**profile, "status": "inactive"},
    )
    assert response.status_code == 200
    denied(rpc("tools/list"))
    assert not seen
