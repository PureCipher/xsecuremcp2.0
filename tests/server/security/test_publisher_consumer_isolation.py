import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus
from purecipher import PureCipherRegistry, consumer_oauth, consumer_runtime
from purecipher.auth import RegistryRole
from purecipher.consumer_google_permissions import GMAIL_READONLY
from tests.server.security.profile_approval_helpers import approve_profile
from tests.server.security.test_consumer_runtime import add
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


def test_publisher_and_end_user_share_listing_but_never_credentials(monkeypatch):
    monkeypatch.setenv("PURECIPHER_CONSUMER_RUNTIME_ENABLED", "true")
    app = PureCipherRegistry(
        signing_secret="isolated-test-secret",
        auth_settings=registry()._auth_settings,
        enable_contracts=True,
        enable_consent=True,
        enable_provenance=False,
        enable_reflexive=False,
    )
    app._account_security.create_account(
        username="purecipher",
        password="fixture-password",
        role=RegistryRole.PUBLISHER,
        display_name="PureCipher",
    )
    app._account_security.create_account(
        username="enduser",
        password="fixture-password",
        role=RegistryRole.VIEWER,
        display_name="End User",
    )
    listing = app._marketplace().publish(
        "purecipher-google-gmail",
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={
            "introspection": {"tool_names": ["gmail_get_message"]},
            "deployment_ready": True,
        },
    )
    monkeypatch.setattr(
        app,
        "_get_public_listing",
        lambda name: listing if name == listing.tool_name else None,
    )
    original = httpx.AsyncClient
    seen = []

    def handle(request):
        token = request.headers.get("authorization")
        assert token in [
            "Bearer purecipher-private-token",
            "Bearer enduser-private-token",
        ]
        seen.append(token)
        return httpx.Response(
            200,
            json={
                "id": "message",
                "snippet": "publisher mailbox"
                if "purecipher" in token
                else "end-user mailbox",
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    with TestClient(app.http_app(stateless_http=True, json_response=True)) as c:
        records = {}
        for owner in ["purecipher", "enduser"]:
            login(c, owner)
            conn = add(c, "google-gmail", {"access_mode": "read_only"})
            consumer_oauth.store_grant(
                app,
                app._workspace.get(conn["id"]),
                {
                    "access_token": owner + "-private-token",
                    "expires_at": time.time() + 3600,
                    "scope": GMAIL_READONLY,
                    "access_mode": "read_only",
                    "requested_scopes": [GMAIL_READONLY],
                },
            )
            entry = c.post(
                "/registry/workspace/clients", json={"display_name": owner + " client"}
            ).json()
            body = {
                "name": owner + " mail",
                "purpose": "Read own mail",
                "status": "inactive",
                "client_ids": [entry["client"]["client_id"]],
                "servers": [
                    {
                        "listing_id": listing.listing_id,
                        "tools": ["gmail_get_message"],
                        "connection_id": conn["id"],
                    }
                ],
            }
            p = c.post("/registry/workspace/profiles", json=body)
            assert p.status_code == 200, p.text
            profile = approve_profile(app, c, p.json())
            records[owner] = (conn, entry, profile)

        def call(owner, target=None):
            _, entry, profile = records[target or owner]
            token = records[owner][1]["token"]
            return c.post(
                "/mcp/profiles/" + profile["id"],
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "gmail_get_message",
                        "arguments": {"message_id": "message"},
                    },
                },
            )

        # Concurrent requests use independent provider credentials for the same listing.
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(call, ["purecipher", "enduser"] * 3))
        for i, r in enumerate(outcomes):
            assert (
                r.status_code == 200
                and not r.json().get("error")
                and not r.json().get("result", {}).get("isError")
            ), r.text
            assert ("publisher mailbox" if i % 2 == 0 else "end-user mailbox") in r.text
            assert "-private-token" not in r.text
        assert (
            seen.count("Bearer purecipher-private-token") == 3
            and seen.count("Bearer enduser-private-token") == 3
        )
        before = len(seen)
        assert call("enduser", "purecipher").status_code == 403
        assert len(seen) == before
        login(c, "enduser")
        conn, entry, profile = records["enduser"]
        forged = {
            **profile,
            "servers": [
                {
                    **profile["servers"][0],
                    "connection_id": records["purecipher"][0]["id"],
                }
            ],
        }
        assert (
            c.put(
                "/registry/workspace/profiles/" + profile["id"], json=forged
            ).status_code
            == 400
        )
        assert (
            c.delete(
                "/registry/workspace/connections/" + records["purecipher"][0]["id"]
            ).status_code
            == 404
        )
        assert "-private-token" not in c.get("/registry/workspace/connections").text
        c.post("/registry/workspace/connections/" + conn["id"] + "/disconnect")
        before = len(seen)
        assert call("enduser").status_code == 403
        assert (
            len(seen) == before
        )  # No fallback to the publisher's still-valid connection.
        assert call("purecipher").status_code == 200
        assert consumer_runtime._ACCESS.get() is None
