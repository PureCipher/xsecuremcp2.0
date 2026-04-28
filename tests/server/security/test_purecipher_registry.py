from __future__ import annotations

import json
from typing import Any, cast

from starlette.testclient import TestClient

from fastmcp.server.security.certification.attestation import CertificationLevel
from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    ResourceAccessDeclaration,
    SecurityManifest,
)
from purecipher import PureCipherRegistry, ToolCategory
from purecipher.auth import RegistryAuthSettings

TEST_SIGNING_SECRET = "purecipher-registry-signing-secret-for-tests"
TEST_JWT_SECRET = "purecipher-registry-jwt-secret-for-tests"
TEST_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "display_name": "Registry Admin",
        },
        {
            "username": "reviewer",
            "password": "reviewer123",
            "role": "reviewer",
            "display_name": "Registry Reviewer",
        },
        {
            "username": "publisher",
            "password": "publisher123",
            "role": "publisher",
            "display_name": "Registry Publisher",
        },
    ]
)


def _manifest(**overrides: Any) -> SecurityManifest:
    defaults: dict[str, Any] = dict(
        tool_name="weather-lookup",
        version="1.0.0",
        author="acme",
        description="Fetch current weather for a city.",
        permissions={PermissionScope.NETWORK_ACCESS},
        data_flows=[
            DataFlowDeclaration(
                source="input.city",
                destination="output.forecast",
                classification=DataClassification.PUBLIC,
                description="City name is sent to the weather provider.",
            )
        ],
        resource_access=[
            ResourceAccessDeclaration(
                resource_pattern="https://api.weather.example/*",
                access_type="read",
                description="Call weather provider endpoint.",
                classification=DataClassification.PUBLIC,
            )
        ],
        tags={"weather", "api"},
    )
    defaults.update(overrides)
    return SecurityManifest(**cast(Any, defaults))


def _runtime_metadata() -> dict[str, object]:
    return {
        "endpoint": "https://mcp.acme.example/weather",
        "transport": "streamable-http",
        "command": "uvx",
        "args": ["weather-lookup"],
        "docker_image": "ghcr.io/acme/weather-lookup:1.0.0",
        "env": {"WEATHER_API_KEY": "${WEATHER_API_KEY}"},
    }


def _auth_settings() -> RegistryAuthSettings:
    return RegistryAuthSettings.from_values(
        enabled=True,
        issuer="purecipher-registry",
        jwt_secret=TEST_JWT_SECRET,
        users_json=TEST_USERS_JSON,
    )


class TestPureCipherRegistry:
    def test_constructor_mounts_registry_routes(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
        )

        paths = {
            path
            for route in registry._additional_http_routes
            if (path := getattr(route, "path", None)) is not None
        }
        assert "/registry" in paths
        assert "/registry/app" in paths
        assert "/registry/health" in paths
        assert "/registry/session" in paths
        assert "/registry/login" in paths
        assert "/registry/logout" in paths
        assert "/registry/publish" in paths
        assert "/registry/listings/{tool_name}" in paths
        assert "/registry/install/{tool_name}" in paths
        assert "/registry/publishers" in paths
        assert "/registry/publishers/{publisher_id}" in paths
        assert "/registry/review" in paths
        assert "/registry/review/submissions" in paths
        assert "/registry/review/{listing_id}/{action_name}" in paths
        assert "/registry/policy" in paths
        assert "/registry/policy/schema" in paths
        assert "/registry/policy/bundles" in paths
        assert "/registry/policy/bundles/{bundle_id}/stage" in paths
        assert "/registry/policy/packs" in paths
        assert "/registry/policy/packs/{pack_id}" in paths
        assert "/registry/policy/packs/{pack_id}/stage" in paths
        assert "/registry/policy/environments" in paths
        assert "/registry/policy/environments/{environment_id}/capture" in paths
        assert "/registry/policy/promotions" in paths
        assert "/registry/policy/analytics" in paths
        assert "/registry/policy/export" in paths
        assert "/registry/policy/import" in paths
        assert "/registry/policy/migrations/preview" in paths
        assert "/registry/policy/versions" in paths
        assert "/registry/policy/versions/diff" in paths
        assert "/registry/policy/versions/rollback" in paths
        assert "/registry/policy/proposals" in paths
        assert "/registry/policy/proposals/{proposal_id}" in paths
        assert "/registry/policy/proposals/{proposal_id}/approve" in paths
        assert "/registry/policy/proposals/{proposal_id}/assign" in paths
        assert "/registry/policy/proposals/{proposal_id}/simulate" in paths
        assert "/registry/policy/proposals/{proposal_id}/deploy" in paths
        assert "/registry/policy/proposals/{proposal_id}/reject" in paths
        assert "/registry/policy/proposals/{proposal_id}/withdraw" in paths
        assert "/registry/policy/providers" in paths
        assert "/registry/policy/providers/{index}" in paths
        assert "/registry/tools" in paths
        assert "/registry/submit" in paths
        assert "/registry/preflight" in paths
        assert "/registry/notifications" in paths
        assert "/registry/me/listings" in paths
        assert "/registry/openapi/ingest" in paths
        assert "/registry/openapi/toolset" in paths

    def test_http_registry_openapi_ingest_and_toolset(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=":memory:",
        )
        app = registry.http_app()

        openapi = {
            "openapi": "3.0.3",
            "info": {"title": "Demo", "version": "1.0.0"},
            "paths": {
                "/users/{id}": {
                    "get": {
                        "operationId": "getUser",
                        "summary": "Get a user",
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/users": {
                    "post": {
                        "operationId": "createUser",
                        "summary": "Create user",
                        "responses": {"201": {"description": "created"}},
                    }
                },
            },
        }

        with TestClient(app) as client:
            ingest = client.post(
                "/registry/openapi/ingest",
                json={"title": "Demo API", "text": json.dumps(openapi)},
            )
            assert ingest.status_code == 200
            ingest_payload = ingest.json()
            assert ingest_payload["source"]["operation_count"] == 2
            ops = ingest_payload["operations"]
            keys = {op["operation_key"] for op in ops}
            assert {"getUser", "createUser"} <= keys

            source_id = ingest_payload["source"]["source_id"]
            toolset = client.post(
                "/registry/openapi/toolset",
                json={
                    "source_id": source_id,
                    "title": "Demo toolset",
                    "selected_operations": ["getUser"],
                    "tool_name_prefix": "demo",
                },
            )
            assert toolset.status_code == 200
            toolset_payload = toolset.json()
            assert toolset_payload["operation_count"] == 1
            assert toolset_payload["toolset"]["source_id"] == source_id
            assert toolset_payload["toolset"]["selected_operations"] == ["getUser"]

    def test_submit_tool_accepts_certified_manifest(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)

        result = registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            tool_license="MIT",
            requested_level=CertificationLevel.BASIC,
        )

        assert result.accepted is True
        assert result.listing is not None
        assert result.listing.tool_name == "weather-lookup"

        detail = registry.get_verified_tool("weather-lookup")
        assert detail["tool_name"] == "weather-lookup"
        assert detail["verification"]["valid"] is True

    def test_submit_tool_rejects_below_minimum_level(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)

        result = registry.submit_tool(
            _manifest(),
            requested_level=CertificationLevel.SELF_ATTESTED,
        )

        assert result.accepted is False
        assert "minimum certification level" in result.reason

    def test_list_verified_tools_returns_catalog(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )

        catalog = registry.list_verified_tools(query="weather")

        assert catalog["count"] == 1
        assert catalog["tools"][0]["tool_name"] == "weather-lookup"

    def test_persistence_reloads_verified_tools(self, tmp_path):
        db_path = tmp_path / "purecipher-registry.db"

        registry1 = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=str(db_path),
        )
        result = registry1.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True

        registry2 = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=str(db_path),
        )
        catalog = registry2.list_verified_tools(query="weather")
        detail = registry2.get_verified_tool("weather-lookup")

        assert catalog["count"] == 1
        assert catalog["tools"][0]["tool_name"] == "weather-lookup"
        assert detail["attestation"]["tool_name"] == "weather-lookup"
        assert detail["trust_score"] is not None
        assert detail["verification"]["valid"] is True

    def test_registry_notifications_surface_after_submit(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            empty = client.get("/registry/notifications")
            assert empty.status_code == 200
            assert empty.json().get("items") == []

            submit = client.post(
                "/registry/submit",
                json={
                    "manifest": _manifest(tool_name="notify-tool").to_dict(),
                    "display_name": "Notify Tool",
                    "categories": ["network"],
                    "requested_level": "basic",
                },
            )
            assert submit.status_code == 201

            feed = client.get("/registry/notifications?limit=5")
            assert feed.status_code == 200
            items = feed.json().get("items") or []
            assert len(items) >= 1
            kinds = {item.get("event_kind") for item in items}
            assert "listing_published" in kinds or "listing_pending_review" in kinds
            assert any("notify-tool" in (item.get("body") or "") for item in items)

    def test_http_registry_submit_and_verify(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            submit = client.post(
                "/registry/submit",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network", "utility"],
                    "tool_license": "MIT",
                    "requested_level": "basic",
                },
            )

            assert submit.status_code == 201
            assert submit.json()["accepted"] is True

            listing = client.get("/registry/tools/weather-lookup")
            assert listing.status_code == 200
            assert listing.json()["tool_name"] == "weather-lookup"

            verify = client.post(
                "/registry/verify",
                json={"tool_name": "weather-lookup"},
            )
            assert verify.status_code == 200
            assert verify.json()["verification"]["valid"] is True

    def test_http_registry_install_recipes(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            source_url="https://github.com/acme/weather-lookup",
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.get("/registry/install/weather-lookup")

            assert response.status_code == 200
            payload = response.json()
            assert payload["tool_name"] == "weather-lookup"
            recipe_ids = {recipe["recipe_id"] for recipe in payload["recipes"]}
            assert {
                "registry_reference",
                "mcp_client_http",
                "mcp_client_stdio",
                "docker_compose",
                "verify_attestation",
            } <= recipe_ids
            assert any(
                "ghcr.io/acme/weather-lookup:1.0.0" in recipe["content"]
                for recipe in payload["recipes"]
            )

    def test_http_registry_listing_detail_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            source_url="https://github.com/acme/weather-lookup",
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.get(
                "/registry/listings/weather-lookup?q=weather&min_certification=basic"
            )

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "Get oriented quickly" in response.text
            assert "Fastest start" in response.text
            assert "Access and setup snapshot" in response.text
            assert "Ways To Use This Tool" in response.text
            assert "Why People Choose It" in response.text
            assert "Start Here" in response.text
            assert "/registry/install/weather-lookup" in response.text
            assert "Connect From Another App" in response.text
            assert "Copy all setup steps" in response.text
            assert "Copy tool JSON" in response.text
            assert "Back to browse" in response.text
            assert ">Publisher<" in response.text

    def test_http_registry_publisher_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        registry.submit_tool(
            _manifest(
                tool_name="forecast-archive",
                version="2.1.0",
                description="Historical weather and climate data.",
                tags={"weather", "history"},
            ),
            display_name="Forecast Archive",
            categories={ToolCategory.DATA_ACCESS},
            requested_level=CertificationLevel.BASIC,
        )
        registry.submit_tool(
            _manifest(
                tool_name="news-wire",
                author="another-publisher",
                description="Breaking news API integration.",
                tags={"news"},
            ),
            display_name="News Wire",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            index = client.get("/registry/publishers")
            assert index.status_code == 200
            summaries = index.json()
            assert summaries["count"] == 2
            assert any(
                publisher["publisher_id"] == "acme"
                for publisher in summaries["publishers"]
            )

            # Default: JSON. The Next.js publisher-profile page reads
            # this contract — it must NOT receive an HTML body.
            response = client.get("/registry/publishers/acme")
            assert response.status_code == 200
            payload = response.json()
            assert payload["publisher_id"] == "acme"
            tool_names = {tool["tool_name"] for tool in payload.get("listings", [])}
            assert "weather-lookup" in tool_names
            assert "forecast-archive" in tool_names

            # Opt-in HTML view for the legacy server-rendered page.
            html_response = client.get("/registry/publishers/acme?view=html")
            assert html_response.status_code == 200
            assert "Publisher Profile" in html_response.text
            assert "Start with this publisher" in html_response.text
            assert "Best first click" in html_response.text
            assert "Trust snapshot" in html_response.text
            assert "Weather Lookup" in html_response.text
            assert "Forecast Archive" in html_response.text
            assert "Live Tools" in html_response.text

            directory = client.get("/registry/publishers?view=html")
            assert directory.status_code == 200
            assert "People and teams behind the tools" in directory.text
            assert "Featured Publishers" in directory.text

    def test_http_registry_review_queue_and_actions(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        result = registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        assert result.listing.status.value == "pending_review"

        app = registry.http_app()

        with TestClient(app) as client:
            public_catalog = client.get("/registry/tools")
            assert public_catalog.status_code == 200
            assert public_catalog.json()["count"] == 0

            queue = client.get("/registry/review/submissions")
            assert queue.status_code == 200
            queue_payload = queue.json()
            assert queue_payload["counts"]["pending_review"] == 1
            assert (
                queue_payload["sections"]["pending_review"][0]["tool_name"]
                == "weather-lookup"
            )

            review_page = client.get("/registry/review")
            assert review_page.status_code == 200
            assert "Review shared tools" in review_page.text
            assert "Waiting For Approval" in review_page.text

            # An attacker tries to spoof attribution by passing
            # ``moderator_id`` in the request body. The registry now
            # ignores body-supplied moderator_id and derives it from the
            # session instead. With auth disabled, the moderator_id
            # falls back to ``"local"`` regardless of what the body
            # claims.
            approve = client.post(
                f"/registry/review/{result.listing.listing_id}/approve",
                json={
                    "moderator_id": "moderator-1",  # spoof attempt — ignored
                    "reason": "Manifest is ready for publication.",
                },
            )
            assert approve.status_code == 200
            approve_payload = approve.json()
            assert approve_payload["listing"]["status"] == "published"
            assert approve_payload["decision"]["moderator_id"] == "local"
            assert approve_payload["decision"]["moderator_id"] != "moderator-1"

            published_catalog = client.get("/registry/tools")
            assert published_catalog.status_code == 200
            assert published_catalog.json()["count"] == 1

            suspend = client.post(
                f"/registry/review/{result.listing.listing_id}/suspend",
                json={
                    "moderator_id": "moderator-2",
                    "reason": "Temporarily disabled for investigation.",
                },
            )
            assert suspend.status_code == 200
            assert suspend.json()["listing"]["status"] == "suspended"
            assert suspend.json()["decision"]["moderator_id"] == "local"

            unsuspend = client.post(
                f"/registry/review/{result.listing.listing_id}/unsuspend",
                json={
                    "moderator_id": "moderator-3",
                    "reason": "Issue resolved.",
                },
            )
            assert unsuspend.status_code == 200
            assert unsuspend.json()["listing"]["status"] == "published"
            assert unsuspend.json()["decision"]["moderator_id"] == "local"

    def test_login_lockout_after_repeated_failures(self):
        """Regression: registry must rate-limit failed logins per
        (username, ip) tuple. Pre-fix the registry accepted unbounded
        password attempts, allowing trivial brute force."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        # Tighten the lockout so the test is fast: 3 attempts then lock.
        from purecipher.account_security import LoginLockout

        registry._login_lockout = LoginLockout(
            max_failures=3, window_seconds=60.0, lockout_seconds=60.0
        )
        app = registry.http_app()

        with TestClient(app) as client:
            # Attempts 1 and 2 fail with 401 — under the threshold.
            for attempt in range(2):
                bad = client.post(
                    "/registry/login",
                    json={"username": "admin", "password": "wrong"},
                )
                assert bad.status_code == 401, (
                    f"attempt {attempt} got {bad.status_code}"
                )

            # Attempt 3 — the failure that hits the threshold — itself
            # returns 429 with a Retry-After header.
            triggering = client.post(
                "/registry/login",
                json={"username": "admin", "password": "wrong"},
            )
            assert triggering.status_code == 429
            assert int(triggering.headers["Retry-After"]) > 0

            # Subsequent attempts — even with the *correct* password —
            # are still rejected because the tuple is locked.
            blocked = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert blocked.status_code == 429
            assert "Retry-After" in blocked.headers
            payload = blocked.json()
            assert "Too many failed sign-in attempts" in payload["error"]

    def test_login_lockout_clears_on_successful_auth(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        from purecipher.account_security import LoginLockout

        registry._login_lockout = LoginLockout(
            max_failures=5, window_seconds=60.0, lockout_seconds=60.0
        )
        app = registry.http_app()

        with TestClient(app) as client:
            # Two failed attempts, well under the threshold.
            for _ in range(2):
                client.post(
                    "/registry/login",
                    json={"username": "admin", "password": "wrong"},
                )

            # Successful login resets the counter.
            ok = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert ok.status_code == 200

            # Hit logout to drop the session and try a fresh round of
            # bad attempts — the prior failures must NOT have stuck.
            client.get("/registry/logout")
            for _ in range(4):
                bad = client.post(
                    "/registry/login",
                    json={"username": "admin", "password": "wrong"},
                )
                assert bad.status_code == 401  # not yet at the new threshold

    def test_login_lockout_not_cleared_when_session_issuance_fails(self):
        """Regression: ``register_success`` must run only AFTER the
        session is fully issued. If JWT decode fails (or any later step
        in session creation), the lockout counter must remain intact so
        an attacker who guessed the password but can't get a session
        doesn't reset their lockout budget on every attempt.
        """
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        from purecipher.account_security import LoginLockout

        registry._login_lockout = LoginLockout(
            max_failures=3, window_seconds=60.0, lockout_seconds=60.0
        )

        app = registry.http_app()

        # Force decode_token to return None — simulates a JWT/config
        # break while keeping authenticate() functional. The settings
        # object is a frozen dataclass so we patch the method on the
        # class within a context manager.
        from unittest.mock import patch

        with (
            TestClient(app) as client,
            patch.object(
                type(registry._auth_settings), "decode_token", return_value=None
            ),
        ):
            # Two failed attempts under the threshold.
            for _ in range(2):
                bad = client.post(
                    "/registry/login",
                    json={"username": "admin", "password": "wrong"},
                )
                assert bad.status_code == 401

            # Now a CORRECT password — but session decode fails, so the
            # endpoint returns 500. The pre-fix behaviour was to clear
            # the counter at this point; the fix keeps it.
            session_fail = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert session_fail.status_code == 500

            # The counter must still be 2 (the prior failures), so the
            # next bad attempt is the 3rd-and-locking one.
            triggering = client.post(
                "/registry/login",
                json={"username": "admin", "password": "wrong"},
            )
            assert triggering.status_code == 429, (
                "lockout counter was cleared by failed session issuance — "
                f"got {triggering.status_code}"
            )

    def test_login_lockout_records_event(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        from purecipher.account_security import LoginLockout

        registry._login_lockout = LoginLockout(
            max_failures=2, window_seconds=60.0, lockout_seconds=60.0
        )
        app = registry.http_app()

        with TestClient(app) as client:
            for _ in range(3):
                client.post(
                    "/registry/login",
                    json={"username": "admin", "password": "wrong"},
                )
            # Find the activity feed for admin and assert the lockout
            # produced both ``login_failed`` and ``login_locked`` events.
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            # Still locked.
            assert login.status_code == 429

        # Inspect the activity store directly (admin can't sign in to
        # read their own feed while locked).
        rows = registry._account_activity.list_recent(username="admin", limit=20)
        kinds = {row["event_kind"] for row in rows}
        assert "login_failed" in kinds
        assert "login_locked" in kinds

    def test_moderation_audit_uses_session_username_not_request_body(self):
        """Regression: moderator_id in moderation_log must reflect the
        authenticated user, never the request body. Pre-fix any caller
        could spoof attribution by sending ``moderator_id`` in JSON."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        result = registry.submit_tool(
            _manifest(tool_name="audit-target"),
            display_name="Audit Target",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200

            # Reviewer issues approval AND tries to spoof moderator_id
            # via the request body. The body field must be ignored.
            approve = client.post(
                f"/registry/review/{result.listing.listing_id}/approve",
                json={
                    "moderator_id": "spoofed-attacker",
                    "reason": "Approved.",
                },
            )
            assert approve.status_code == 200
            decision = approve.json()["decision"]
            assert decision["moderator_id"] == "reviewer"
            assert decision["moderator_id"] != "spoofed-attacker"

            # And the moderator's own activity feed records the action.
            activity = client.get("/registry/me/activity?limit=10")
            assert activity.status_code == 200
            kinds = {item["event_kind"] for item in activity.json()["items"]}
            assert "moderation_action" in kinds

    def test_moderation_unauthenticated_request_rejected_when_auth_enabled(self):
        """A moderation POST with no session must 401 when auth is on,
        rather than fall through to a "local" attribution."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        result = registry.submit_tool(
            _manifest(tool_name="auth-required"),
            display_name="Auth Required",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.post(
                f"/registry/review/{result.listing.listing_id}/approve",
                json={"reason": "no auth"},
            )
            assert response.status_code == 401

    def test_http_registry_public_routes_only_expose_published_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        result = registry.submit_tool(
            _manifest(tool_name="pending-tool"),
            display_name="Pending Tool",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None

        app = registry.http_app()

        with TestClient(app) as client:
            pending_detail = client.get("/registry/tools/pending-tool")
            pending_install = client.get("/registry/install/pending-tool")
            pending_listing = client.get("/registry/listings/pending-tool")
            pending_verify = client.post(
                "/registry/verify",
                json={"tool_name": "pending-tool"},
            )

            assert pending_detail.status_code == 404
            assert pending_install.status_code == 404
            assert pending_listing.status_code == 404
            assert pending_verify.status_code == 404

            approve = client.post(
                f"/registry/review/{result.listing.listing_id}/approve",
                json={"moderator_id": "reviewer", "reason": "Looks good."},
            )
            assert approve.status_code == 200

            published_detail = client.get("/registry/tools/pending-tool")
            assert published_detail.status_code == 200
            assert published_detail.json()["status"] == "published"

            suspend = client.post(
                f"/registry/review/{result.listing.listing_id}/suspend",
                json={"moderator_id": "admin", "reason": "Temporarily paused."},
            )
            assert suspend.status_code == 200

            suspended_detail = client.get("/registry/tools/pending-tool")
            suspended_install = client.get("/registry/install/pending-tool")

            assert suspended_detail.status_code == 404
            assert suspended_install.status_code == 404

    def test_authenticated_users_can_verify_pending_tool(self):
        """Regression: ``/registry/verify`` must accept pending listings
        for authenticated callers so the post-submit detail page
        renders real verification data instead of a misleading
        "Signature invalid" chip.

        Pre-fix the route always called ``verify_tool`` with the
        public-only lookup, so any pending listing returned 404 and
        the frontend defaulted to ``signature_valid=false`` /
        ``manifest_match=no``."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        result = registry.submit_tool(
            _manifest(tool_name="pending-verify"),
            display_name="Pending Verify",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        assert result.listing.status.value == "pending_review"

        app = registry.http_app()
        with TestClient(app) as client:
            # Anonymous: still 404 (pending listings stay private).
            anon = client.post(
                "/registry/verify",
                json={"tool_name": "pending-verify"},
            )
            assert anon.status_code == 404

            # Sign in and re-verify — should now return 200 with a
            # real verification payload (signature_valid=True since
            # the registry just signed the attestation at submit).
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200, login.text

            authed = client.post(
                "/registry/verify",
                json={"tool_name": "pending-verify"},
            )
            assert authed.status_code == 200, authed.text
            payload = authed.json()
            assert payload["tool_name"] == "pending-verify"
            assert payload["verification"]["signature_valid"] is True
            assert payload["verification"]["manifest_match"] is True

    def test_authenticated_users_can_view_pending_tool_detail(self):
        """Regression: post a curator submission, click 'View listing'
        in the wizard's Step 4 — the listing is still ``PENDING_REVIEW``
        (under default moderation) but the detail page must show it
        instead of 404'ing.

        Pre-fix the ``/registry/tools/{name}`` endpoint always
        delegated to ``get_verified_tool`` which only returns
        publicly-published listings. Logged-in publishers / reviewers
        / admins should be able to see their own pending submissions
        the same way ``/registry/tools/{name}/versions`` already
        permits.
        """
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        result = registry.submit_tool(
            _manifest(tool_name="pending-tool"),
            display_name="Pending Tool",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        assert result.listing.status.value == "pending_review"

        app = registry.http_app()
        with TestClient(app) as client:
            # Anonymous: 404 stays the rule for unauthenticated
            # callers — pending listings aren't part of the public
            # surface.
            anon_detail = client.get("/registry/tools/pending-tool")
            assert anon_detail.status_code == 404

            # Sign in as the admin user and re-fetch — should now
            # return 200 with the pending listing so the curator's
            # post-submit "View listing" link works.
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200, login.text

            authed_detail = client.get("/registry/tools/pending-tool")
            assert authed_detail.status_code == 200, authed_detail.text
            payload = authed_detail.json()
            assert payload["tool_name"] == "pending-tool"
            assert payload["status"] == "pending_review"

    def test_submit_tool_requeues_existing_listing_when_moderation_is_enabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        first = registry.submit_tool(
            _manifest(tool_name="weather-lookup", version="1.0.0"),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )

        assert first.accepted is True
        assert first.listing is not None
        assert first.listing.status.value == "pending_review"

        approved = registry.moderate_listing(
            first.listing.listing_id,
            action_name="approve",
            moderator_id="reviewer-1",
            reason="Initial version approved.",
        )
        assert approved["listing"]["status"] == "published"

        second = registry.submit_tool(
            _manifest(tool_name="weather-lookup", version="1.1.0"),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )

        assert second.accepted is True
        assert second.listing is not None
        assert second.listing.status.value == "pending_review"

        detail = registry.get_verified_tool("weather-lookup")
        assert detail["status"] == 404

    def test_http_registry_ui_route(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            # Auth is disabled by default, so /registry should redirect to the app UI.
            landing = client.get("/registry", follow_redirects=False)
            assert landing.status_code == 303
            assert landing.headers["location"] == "/registry/app"

            response = client.get("/registry/app")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "PureCipher Secured MCP Registry" in response.text
            assert "Browse Tools" in response.text
            assert "What would you like to do?" in response.text
            assert "Find a tool you can trust" in response.text
            assert "Start Here" in response.text
            assert "Choose your next step" in response.text
            assert "Popular topics" in response.text
            assert "Overview" in response.text
            assert "Featured Publishers" in response.text
            assert "Share A Tool" in response.text

    def test_http_registry_ui_can_be_disabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_legacy_registry_ui=False,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            landing = client.get("/registry", follow_redirects=False)
            assert landing.status_code == 404
            assert "Legacy registry UI is disabled" in landing.text

            app_page = client.get("/registry/app")
            assert app_page.status_code == 404
            assert "Legacy registry UI is disabled" in app_page.text

            publishers_html = client.get("/registry/publishers?view=html")
            assert publishers_html.status_code == 404
            assert "Legacy registry UI is disabled" in publishers_html.text

            publishers_json = client.get("/registry/publishers")
            assert publishers_json.status_code == 200

    def test_http_registry_policy_proposal_lifecycle(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            created = client.post(
                "/registry/policy/proposals",
                json={
                    "action": "add",
                    "config": {
                        "type": "denylist",
                        "policy_id": "admin-guard",
                        "version": "1.0.0",
                        "denied": ["admin-*"],
                    },
                    "description": "Protect admin tools.",
                },
            )
            assert created.status_code == 200
            proposal = created.json()["proposal"]
            proposal_id = proposal["proposal_id"]
            assert proposal["status"] == "validated"

            proposals = client.get("/registry/policy/proposals")
            assert proposals.status_code == 200
            assert proposals.json()["pending_count"] == 1

            assigned = client.post(
                f"/registry/policy/proposals/{proposal_id}/assign",
                json={
                    "reviewer": "reviewer",
                    "note": "Reviewer owns the rollout.",
                },
            )
            assert assigned.status_code == 200
            assert assigned.json()["proposal"]["assigned_reviewer"] == "reviewer"

            simulated = client.post(
                f"/registry/policy/proposals/{proposal_id}/simulate"
            )
            assert simulated.status_code == 200
            assert simulated.json()["proposal"]["status"] == "simulated"
            assert simulated.json()["simulation"]["total"] == 5

            approved = client.post(
                f"/registry/policy/proposals/{proposal_id}/approve",
                json={"note": "Ready to release."},
            )
            assert approved.status_code == 200
            assert approved.json()["proposal"]["status"] == "approved"

            deployed = client.post(
                f"/registry/policy/proposals/{proposal_id}/deploy",
                json={"note": "Applying to the live chain."},
            )
            assert deployed.status_code == 200
            assert deployed.json()["proposal"]["status"] == "deployed"
            assert deployed.json()["policy"]["provider_count"] == 2
            trail = deployed.json()["proposal"]["decision_trail"]
            events = [item["event"] for item in trail]
            assert "assigned" in events
            assert events[-3:] == ["simulated", "approved", "deployed"]

    def test_http_registry_rejects_stale_policy_proposal(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            original = client.post(
                "/registry/policy/proposals",
                json={
                    "action": "add",
                    "config": {
                        "type": "allowlist",
                        "policy_id": "tool-gate",
                        "version": "1.0.0",
                        "allowed": ["tool:*"],
                    },
                    "description": "Gate tool access.",
                },
            )
            assert original.status_code == 200
            original_proposal = original.json()["proposal"]
            original_id = original_proposal["proposal_id"]
            assert original_proposal["base_version_number"] == 1
            assert original_proposal["live_version_number"] == 1
            assert original_proposal["is_stale"] is False

            live = client.post(
                "/registry/policy/proposals",
                json={
                    "action": "add",
                    "config": {
                        "type": "denylist",
                        "policy_id": "admin-guard",
                        "version": "1.0.0",
                        "denied": ["admin-*"],
                    },
                    "description": "Protect admin tools.",
                },
            )
            assert live.status_code == 200
            live_id = live.json()["proposal"]["proposal_id"]

            simulate_live = client.post(
                f"/registry/policy/proposals/{live_id}/simulate"
            )
            assert simulate_live.status_code == 200
            approve_live = client.post(f"/registry/policy/proposals/{live_id}/approve")
            assert approve_live.status_code == 200
            deploy_live = client.post(f"/registry/policy/proposals/{live_id}/deploy")
            assert deploy_live.status_code == 200

            refreshed = client.get(f"/registry/policy/proposals/{original_id}")
            assert refreshed.status_code == 200
            assert refreshed.json()["live_version_number"] == 2
            assert refreshed.json()["is_stale"] is True

            stale_simulate = client.post(
                f"/registry/policy/proposals/{original_id}/simulate"
            )
            assert stale_simulate.status_code == 400
            assert "Create a fresh proposal" in stale_simulate.json()["error"]

    def test_http_registry_policy_packs_and_promotions(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            saved_pack = client.post(
                "/registry/policy/packs",
                json={
                    "title": "Team baseline",
                    "summary": "Reusable private pack",
                    "description": "A private reviewer baseline.",
                    "source_version_number": 1,
                    "recommended_environments": ["development", "staging"],
                    "tags": ["private", "baseline"],
                },
            )
            assert saved_pack.status_code == 200
            saved_pack_payload = saved_pack.json()
            pack_id = saved_pack_payload["pack"]["pack_id"]
            assert saved_pack_payload["pack"]["visibility"] == "private"

            list_packs = client.get("/registry/policy/packs")
            assert list_packs.status_code == 200
            assert list_packs.json()["count"] == 1

            capture_staging = client.post(
                "/registry/policy/environments/staging/capture",
                json={"source_version_number": 1},
            )
            assert capture_staging.status_code == 200
            assert capture_staging.json()["environment"]["current_version_number"] == 1

            created = client.post(
                "/registry/policy/proposals",
                json={
                    "action": "add",
                    "config": {
                        "type": "denylist",
                        "policy_id": "admin-guard",
                        "version": "1.0.0",
                        "denied": ["admin-*"],
                    },
                    "description": "Protect admin tools.",
                },
            )
            assert created.status_code == 200
            created_id = created.json()["proposal"]["proposal_id"]
            simulated_created = client.post(
                f"/registry/policy/proposals/{created_id}/simulate"
            )
            assert simulated_created.status_code == 200
            approved = client.post(f"/registry/policy/proposals/{created_id}/approve")
            assert approved.status_code == 200
            deployed = client.post(f"/registry/policy/proposals/{created_id}/deploy")
            assert deployed.status_code == 200
            assert deployed.json()["versions"]["current_version"] == 2

            capture_dev = client.post(
                "/registry/policy/environments/development/capture",
                json={"source_version_number": 2},
            )
            assert capture_dev.status_code == 200
            assert capture_dev.json()["environment"]["current_version_number"] == 2

            stage_pack = client.post(f"/registry/policy/packs/{pack_id}/stage")
            assert stage_pack.status_code == 200
            assert stage_pack.json()["pack"]["pack_id"] == pack_id

            stage_promotion = client.post(
                "/registry/policy/promotions",
                json={
                    "source_environment": "development",
                    "target_environment": "staging",
                    "description": "Promote development into staging",
                },
            )
            assert stage_promotion.status_code == 200
            promotion_payload = stage_promotion.json()
            assert promotion_payload["promotions"]["count"] == 1
            promotion_id = promotion_payload["proposal"]["proposal_id"]
            assert (
                promotion_payload["proposal"]["metadata"]["workbench_kind"]
                == "promotion"
            )

            simulated_promotion = client.post(
                f"/registry/policy/proposals/{promotion_id}/simulate"
            )
            assert simulated_promotion.status_code == 200
            approved_promotion = client.post(
                f"/registry/policy/proposals/{promotion_id}/approve"
            )
            assert approved_promotion.status_code == 200
            deployed_promotion = client.post(
                f"/registry/policy/proposals/{promotion_id}/deploy"
            )
            assert deployed_promotion.status_code == 200
            assert deployed_promotion.json()["versions"]["current_version"] == 3

            promotions = client.get("/registry/policy/promotions")
            assert promotions.status_code == 200
            assert promotions.json()["promotions"][0]["status"] == "deployed"

            environments = client.get("/registry/policy/environments")
            assert environments.status_code == 200
            staging = next(
                item
                for item in environments.json()["environments"]
                if item["environment_id"] == "staging"
            )
            assert staging["current_version_number"] == 3

    def test_http_registry_ui_hides_review_details_from_public_users(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        registry.submit_tool(
            _manifest(tool_name="pending-tool", version="1.0.0"),
            display_name="Pending Tool",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.get("/registry", follow_redirects=True)

            assert response.status_code == 200
            assert "PureCipher Secured MCP Registry" in response.text
            assert "Pending Tool" not in response.text
            assert 'href="/registry/review"' not in response.text

    def test_http_registry_ui_shows_review_details_to_reviewers(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        registry.submit_tool(
            _manifest(tool_name="pending-tool", version="1.0.0"),
            display_name="Pending Tool",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200

            response = client.get("/registry/app")

            assert response.status_code == 200
            assert "Pending Tool" in response.text
            assert 'href="/registry/review"' in response.text
            assert "Open approvals" in response.text

    def test_registry_pages_do_not_link_to_post_only_api_routes(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            catalog = client.get("/registry")
            publish = client.get("/registry/publish")

            assert 'href="/registry/submit"' not in catalog.text
            assert 'href="/registry/preflight"' not in catalog.text
            assert 'href="/registry/submit"' not in publish.text
            assert 'href="/registry/preflight"' not in publish.text
            assert "POST /registry/submit" in catalog.text
            assert "POST /registry/preflight" in publish.text

    def test_http_registry_ui_form_submission(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.post(
                "/registry/publish",
                data={
                    "manifest": json.dumps(_manifest().to_dict(), indent=2),
                    "runtime_metadata": json.dumps(_runtime_metadata(), indent=2),
                    "display_name": "Weather Lookup",
                    "categories": "network,utility",
                    "tags": "weather,api",
                    "source_url": "https://github.com/acme/weather-lookup",
                    "tool_license": "MIT",
                    "requested_level": "basic",
                    "submission_action": "publish",
                },
            )

            assert response.status_code == 200
            assert "Accepted into the PureCipher verified registry." in response.text
            assert "Share Form" in response.text
            assert "Check Results" in response.text
            assert "Ready To Share" in response.text

    def test_http_registry_publish_page_and_preflight(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            page = client.get("/registry/publish")

            assert page.status_code == 200
            assert "Share your tool" in page.text
            assert "Share your tool without guessing" in page.text
            assert "What happens on this page?" in page.text
            assert "Sharing should feel straightforward" in page.text
            assert "Share Form" in page.text
            assert "Check Results" in page.text
            assert "Start from a real listing" in page.text
            assert "Blank verified listing" in page.text

            preview = client.post(
                "/registry/publish",
                data={
                    "manifest": json.dumps(_manifest().to_dict(), indent=2),
                    "runtime_metadata": json.dumps(_runtime_metadata(), indent=2),
                    "display_name": "Weather Lookup",
                    "categories": "network,utility",
                    "tags": "weather,api",
                    "source_url": "https://github.com/acme/weather-lookup",
                    "tool_license": "MIT",
                    "requested_level": "basic",
                    "submission_action": "preview",
                },
            )

            assert preview.status_code == 200
            assert "Preflight complete" in preview.text
            assert "What People Will See" in preview.text
            assert "Things To Fix" in preview.text

    def test_http_registry_preflight_api(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.post(
                "/registry/preflight",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network", "utility"],
                    "requested_level": "basic",
                    "metadata": _runtime_metadata(),
                },
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["ready_for_publish"] is True
            assert payload["install_ready"] is True
            recipe_ids = {recipe["recipe_id"] for recipe in payload["install_recipes"]}
            assert "mcp_client_http" in recipe_ids
            assert "docker_compose" in recipe_ids

    def test_http_registry_tools_search(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.get("/registry/tools?q=weather&category=network")

            assert response.status_code == 200
            payload = response.json()
            assert payload["count"] == 1
            assert payload["tools"][0]["tool_name"] == "weather-lookup"

    def test_http_registry_tool_versions_endpoint(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.submit_tool(
            _manifest(tool_name="weather-lookup", version="1.0.0"),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        registry.submit_tool(
            _manifest(tool_name="weather-lookup", version="1.1.0"),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            resp = client.get("/registry/tools/weather-lookup/versions")
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["tool_name"] == "weather-lookup"
            assert payload["version_count"] >= 1
            versions = payload["versions"]
            assert isinstance(versions, list)
            assert versions[0]["version"] in {"1.1.0", "1.0.0"}


class TestServerPolicyGovernance:
    """Iteration 1 of the server-profile Governance tab: replace the
    "Policy Kernel: inherited (stub)" line with a real, derived
    policy-binding view.

    The endpoint is ``/registry/servers/{server_id}/governance/policy``.
    It returns:

    * ``registry_policy`` — a UI-shaped projection of the registry-
      wide policy engine's status (set id, current version, version
      count, fail-closed, provider/evaluation/deny counts).
    * ``per_tool_policies`` — one row per listing the publisher
      owns. ``binding_source="proxy_allowlist"`` for proxy-mode
      curator listings whose curator-vouched tool surface gates
      calls; ``binding_source="inherited"`` for catalog-mode
      listings (no listing-specific policy at the registry layer).
    * ``summary`` — counts.
    * ``links`` — pointer to the Policy Kernel page.

    Visibility mirrors ``/registry/tools/{name}`` and
    ``/registry/verify``: anonymous callers see only public listings;
    authenticated callers see all of the publisher's listings.
    """

    def _proxy_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
        observed_tools: list[str] | None = None,
        version: str = "1.0.0",
    ) -> str:
        """Submit a curator-attested proxy listing with observed tools.

        Returns the listing's ``listing_id``.
        """
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        observed_tools = observed_tools or ["fetch", "save"]
        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            version=version,
            tags={"curated", *observed_tools},
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            metadata={
                "introspection": {
                    "tool_names": list(observed_tools),
                    "resource_uris": [],
                    "prompt_names": [],
                },
            },
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            tags={"curated"},
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/governance/policy")
            assert resp.status_code == 404
            payload = resp.json()
            assert "not found" in payload["error"].lower()

    def test_emits_inherited_binding_for_catalog_listing(self):
        """Catalog-mode listings have no per-listing policy at the
        registry layer — calls bypass the gateway entirely. The row
        must surface this honestly as ``binding_source="inherited"``
        with ``policy_provider=null``."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._catalog_listing(registry, tool_name="cat-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        assert payload["server_id"] == "alice"
        per_tool = payload["per_tool_policies"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["listing_id"] == listing_id
        assert row["tool_name"] == "cat-tool"
        assert row["hosting_mode"] == "catalog"
        assert row["attestation_kind"] == "curator"
        assert row["binding_source"] == "inherited"
        assert row["policy_provider"] is None

        summary = payload["summary"]
        assert summary["tool_count"] == 1
        assert summary["inherited_count"] == 1
        assert summary["overridden_count"] == 0

    def test_emits_proxy_allowlist_binding_for_proxy_listing(self):
        """Proxy-mode curator listings carry a real AllowlistPolicy
        on the gateway, derived from the curator-vouched tool surface.
        The endpoint must surface that as
        ``binding_source="proxy_allowlist"`` with the policy provider
        details."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._proxy_listing(
            registry,
            tool_name="proxy-tool",
            observed_tools=["fetch_url", "save_doc", "lookup"],
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        per_tool = payload["per_tool_policies"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["listing_id"] == listing_id
        assert row["binding_source"] == "proxy_allowlist"
        assert row["hosting_mode"] == "proxy"

        provider = row["policy_provider"]
        assert provider is not None
        assert provider["type"] == "allowlist"
        assert provider["fail_closed"] is True
        assert provider["allowed_count"] == 3
        # Sample is sorted, capped at 10 per spec.
        assert provider["allowed_sample"] == sorted(["fetch_url", "save_doc", "lookup"])
        # Policy id matches what the proxy gateway would attach.
        assert provider["policy_id"] == f"curator-allowlist-{listing_id}"

        summary = payload["summary"]
        assert summary["tool_count"] == 1
        assert summary["inherited_count"] == 0
        assert summary["overridden_count"] == 1

    def test_summary_counts_aggregate_across_mixed_listings(self):
        """A server with both catalog and proxy listings should have a
        summary that distinguishes them — this is the trust signal a
        curator wants when scanning the page."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="cat-1")
        self._catalog_listing(registry, tool_name="cat-2")
        self._proxy_listing(registry, tool_name="proxy-1")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200
            payload = resp.json()

        summary = payload["summary"]
        assert summary["tool_count"] == 3
        assert summary["inherited_count"] == 2
        assert summary["overridden_count"] == 1

    def test_registry_policy_block_describes_active_engine(self):
        """The registry_policy projection must carry the live policy
        engine's identifying metadata so the UI can render the active
        version chip without having to make a second round-trip to
        the Policy Kernel endpoint."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="any-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200
            payload = resp.json()

        rp = payload["registry_policy"]
        assert rp["available"] is True
        assert rp["policy_set_id"] == "purecipher-registry"
        assert isinstance(rp["current_version"], int)
        assert rp["current_version"] >= 1
        assert isinstance(rp["fail_closed"], bool)
        assert isinstance(rp["provider_count"], int)
        assert rp["provider_count"] >= 1
        assert "evaluation_count" in rp
        assert "deny_count" in rp

    def test_links_point_at_policy_kernel_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200
            assert resp.json()["links"]["policy_kernel_url"] == "/registry/policy"

    def test_anonymous_caller_sees_public_listings_only(self):
        """Anonymous callers under auth_enabled=True must NOT see
        pending listings — same visibility rule as
        ``/registry/tools/{name}``."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        # All catalog/proxy submits land in PENDING_REVIEW under
        # require_moderation=True.
        self._catalog_listing(registry, tool_name="pending-tool")

        with TestClient(registry.http_app()) as client:
            anon = client.get("/registry/servers/alice/governance/policy")
            assert anon.status_code == 404, anon.text

    def test_authenticated_caller_sees_pending_listings(self):
        """Curators must be able to inspect how their just-submitted
        listings will be governed before a moderator approves them.
        Mirrors the tool-detail and verify endpoints' session-aware
        visibility."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        # Submit by username "publisher" so the publisher_id slug
        # exactly matches the role's username.
        listing_id = self._proxy_listing(
            registry,
            tool_name="curator-pending",
            author="publisher",
            observed_tools=["one", "two"],
        )

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/governance/policy")
            assert authed.status_code == 200, authed.text
            payload = authed.json()
            assert payload["summary"]["tool_count"] == 1
            row = payload["per_tool_policies"][0]
            assert row["listing_id"] == listing_id
            assert row["status"] == "pending_review"
            assert row["binding_source"] == "proxy_allowlist"

    def test_per_tool_rows_sorted_by_recent_activity(self):
        """The most-recently-touched listing must appear first so the
        curator's freshest activity is on top."""
        import time

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="older")
        # Stagger the timestamp so updated_at is strictly increasing.
        time.sleep(0.01)
        self._catalog_listing(registry, tool_name="newer")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200
            tool_names = [row["tool_name"] for row in resp.json()["per_tool_policies"]]
            # Newest first.
            assert tool_names == ["newer", "older"]

    def test_proxy_listing_without_observed_tools_falls_back_to_inherited(
        self,
    ):
        """A proxy listing with no curator-vouched tool surface (no
        introspection metadata, no manifest tag fallback) shouldn't
        falsely advertise an allowlist binding — it should report
        ``inherited`` so the operator sees the gap."""
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        # Submit a proxy listing with NO observed tools and no
        # non-marker tags so the fallback in
        # ``_observed_tool_allowlist`` finds nothing.
        manifest = _manifest(
            tool_name="empty-proxy",
            author="alice",
            tags={"curated"},  # only marker tag — no observed tools
        )
        result = registry.submit_tool(
            manifest,
            display_name="Empty Proxy",
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            curator_id="alice",
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/policy")
            assert resp.status_code == 200
            row = resp.json()["per_tool_policies"][0]
            assert row["binding_source"] == "inherited"
            assert row["policy_provider"] is None


class TestServerContractGovernance:
    """Iteration 2 of the server-profile Governance tab — Contract
    Broker.

    The endpoint is ``/registry/servers/{server_id}/governance/contracts``.
    Contracts in this system are scoped to ``(agent_id, server_id)``,
    not to specific tools. Tool-targeting lives inside each
    contract's term constraints (``allowed_resources``,
    ``resource_pattern``, etc.). The endpoint walks every active
    contract's terms looking for tool-name references, so the
    per-tool view honestly distinguishes ``no_contracts`` (no agent
    has a live contract that would govern calls to this tool) from
    ``agent_contracts`` (one or more agents have contracts whose
    terms reference this tool).

    The Context Broker is opt-in on the registry's SecurityConfig —
    most deployments don't enable it. The ``broker.available`` flag
    tells the consumer whether the rest of the broker block is real.
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            tags={"curated"},
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _attach_broker(self, registry: PureCipherRegistry):
        """Stub a real :class:`ContextBroker` onto the registry's
        SecurityContext for tests. Production registries opt in via
        SecurityConfig(contracts=...); we go around that wiring here
        because the public surface we're testing is a read-only
        projection of broker state.
        """
        from fastmcp.server.security.contracts.broker import ContextBroker

        broker = ContextBroker(server_id="test-registry")
        registry._required_context().broker = broker
        return broker

    def _seed_active_contract(
        self,
        broker,
        *,
        agent_id: str,
        constraint: dict,
        contract_id: str | None = None,
        term_type=None,
    ):
        """Seed a single ACTIVE contract with one term whose
        constraint payload references one or more tool names."""
        from datetime import datetime, timedelta, timezone

        from fastmcp.server.security.contracts.schema import (
            Contract,
            ContractStatus,
            ContractTerm,
            TermType,
        )

        cid = contract_id or f"contract-{agent_id}"
        contract = Contract(
            contract_id=cid,
            session_id=f"session-{cid}",
            server_id=broker.server_id,
            agent_id=agent_id,
            terms=[
                ContractTerm(
                    term_type=term_type or TermType.ACCESS_CONTROL,
                    description="Access scope",
                    constraint=constraint,
                )
            ],
            status=ContractStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        broker._active_contracts[cid] = contract
        return contract

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/governance/contracts")
            assert resp.status_code == 404
            assert "not found" in resp.json()["error"].lower()

    def test_broker_unavailable_when_not_configured(self):
        """As of Iter8 the broker is *enabled by default*. Operators
        who explicitly opt out via ``enable_contracts=False`` get a
        registry with no broker — the endpoint must surface that
        honestly with operator-actionable copy."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_contracts=False,
        )
        self._catalog_listing(registry, tool_name="tool-a")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        assert payload["server_id"] == "alice"
        broker = payload["broker"]
        assert broker["available"] is False
        assert "not enabled" in broker["reason"].lower()

        # Per-tool block still renders, just with no_contracts
        # everywhere — the broker's absence isn't a per-tool failure.
        per_tool = payload["per_tool_contracts"]
        assert len(per_tool) == 1
        assert per_tool[0]["binding_source"] == "no_contracts"
        assert per_tool[0]["matching_contract_count"] == 0

        summary = payload["summary"]
        assert summary == {
            "tool_count": 1,
            "contracted_count": 0,
            "uncontracted_count": 1,
        }

    def test_broker_available_with_no_contracts(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        broker = self._attach_broker(registry)

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            assert resp.status_code == 200
            payload = resp.json()

        broker_block = payload["broker"]
        assert broker_block["available"] is True
        assert broker_block["broker_id"] == "default"
        assert broker_block["server_id"] == broker.server_id
        assert broker_block["max_rounds"] == 5
        assert broker_block["contract_duration_seconds"] == 3600
        assert broker_block["session_timeout_seconds"] == 1800
        assert broker_block["default_term_count"] == 0
        assert broker_block["default_terms"] == []
        assert broker_block["active_contract_count"] == 0
        assert broker_block["negotiation_session_count"] == 0
        assert broker_block["exchange_log_session_count"] == 0
        assert broker_block["exchange_log_entry_count"] == 0

        # No contracts means every tool is uncontracted.
        per_tool = payload["per_tool_contracts"]
        assert len(per_tool) == 1
        assert per_tool[0]["binding_source"] == "no_contracts"

    def test_active_contract_with_allowed_resources_matches_tool(self):
        """A term constraint of ``{"allowed_resources": ["tool-a"]}``
        on an active contract must be picked up as an
        ``agent_contracts`` binding for ``tool-a``."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        broker = self._attach_broker(registry)
        self._seed_active_contract(
            broker,
            agent_id="agent-007",
            constraint={"allowed_resources": ["tool-a"]},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            assert resp.status_code == 200
            payload = resp.json()

        per_tool = payload["per_tool_contracts"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["binding_source"] == "agent_contracts"
        assert row["matching_contract_count"] == 1
        assert row["matching_agents"] == ["agent-007"]

        summary = payload["summary"]
        assert summary["contracted_count"] == 1
        assert summary["uncontracted_count"] == 0

    def test_glob_pattern_in_constraint_matches_tool(self):
        """``{"resource_pattern": "tool-*"}`` should match
        ``tool-a`` via the same _matches_any helper AllowlistPolicy
        uses, so contracts written with globs are surfaced too."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        self._catalog_listing(registry, tool_name="other-tool")
        broker = self._attach_broker(registry)
        self._seed_active_contract(
            broker,
            agent_id="agent-glob",
            constraint={"resource_pattern": "tool-*"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            payload = resp.json()

        bindings = {
            row["tool_name"]: row["binding_source"]
            for row in payload["per_tool_contracts"]
        }
        assert bindings["tool-a"] == "agent_contracts"
        # ``other-tool`` does NOT match ``tool-*`` (prefix doesn't
        # cover ``other``), so it remains uncontracted.
        assert bindings["other-tool"] == "no_contracts"

    def test_resource_id_constraint_matches_tool(self):
        """A constraint that names a single ``resource_id`` must
        match too — covers the negotiation pattern where each term
        scopes one specific tool."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        broker = self._attach_broker(registry)
        self._seed_active_contract(
            broker,
            agent_id="single-resource-agent",
            constraint={"resource_id": "tool-a"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            payload = resp.json()
        row = payload["per_tool_contracts"][0]
        assert row["binding_source"] == "agent_contracts"
        assert row["matching_agents"] == ["single-resource-agent"]

    def test_multiple_agent_contracts_aggregate_per_tool(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        broker = self._attach_broker(registry)

        for i, agent_id in enumerate(("agent-1", "agent-2", "agent-3")):
            self._seed_active_contract(
                broker,
                agent_id=agent_id,
                constraint={"allowed_resources": ["tool-a"]},
                contract_id=f"c-{i}",
            )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            payload = resp.json()

        row = payload["per_tool_contracts"][0]
        assert row["matching_contract_count"] == 3
        assert set(row["matching_agents"]) == {
            "agent-1",
            "agent-2",
            "agent-3",
        }

    def test_expired_contracts_are_excluded(self):
        """Only currently-valid contracts should count — expired
        contracts shouldn't ghost-bind to tools."""
        from datetime import datetime, timedelta, timezone

        from fastmcp.server.security.contracts.schema import (
            Contract,
            ContractStatus,
            ContractTerm,
            TermType,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        broker = self._attach_broker(registry)

        expired = Contract(
            contract_id="c-expired",
            server_id=broker.server_id,
            agent_id="ghost-agent",
            terms=[
                ContractTerm(
                    term_type=TermType.ACCESS_CONTROL,
                    constraint={"allowed_resources": ["tool-a"]},
                )
            ],
            status=ContractStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        broker._active_contracts[expired.contract_id] = expired

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            row = resp.json()["per_tool_contracts"][0]
        assert row["binding_source"] == "no_contracts"

    def test_anonymous_caller_sees_public_listings_only(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")

        with TestClient(registry.http_app()) as client:
            anon = client.get("/registry/servers/alice/governance/contracts")
            assert anon.status_code == 404

    def test_authenticated_caller_sees_pending_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="curator-tool", author="publisher")

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/governance/contracts")
            assert authed.status_code == 200, authed.text
            payload = authed.json()
            assert payload["summary"]["tool_count"] == 1
            assert payload["per_tool_contracts"][0]["status"] == "pending_review"

    def test_links_point_at_contracts_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            assert resp.json()["links"]["contract_broker_url"] == "/registry/contracts"

    def test_default_terms_are_summarized(self):
        """When the broker is configured with default terms, those
        are surfaced on the broker block so curators see what every
        contract automatically inherits."""
        from fastmcp.server.security.contracts.broker import ContextBroker
        from fastmcp.server.security.contracts.schema import (
            ContractTerm,
            TermType,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")

        broker = ContextBroker(
            server_id="terms-registry",
            default_terms=[
                ContractTerm(
                    term_type=TermType.AUDIT,
                    description="Mandatory audit trail",
                    required=True,
                )
            ],
        )
        registry._required_context().broker = broker

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/contracts")
            broker_block = resp.json()["broker"]
        assert broker_block["default_term_count"] == 1
        assert broker_block["default_terms"][0]["term_type"] == "audit"
        assert broker_block["default_terms"][0]["required"] is True


class TestServerConsentGovernance:
    """Iteration 3 of the server-profile Governance tab — Consent
    Graph.

    The endpoint is ``/registry/servers/{server_id}/governance/consent``.

    Two orthogonal signals per tool:

    - ``binding_source`` is driven by ``SecurityManifest.requires_consent``
      and is deterministic. It only describes the listing's *posture*
      — does the tool say it needs consent before being executed?
    - ``graph_grant_count`` is a best-effort heuristic that walks
      the active consent edges for tool-name references in scopes,
      metadata, source/target node IDs.

    Like the Context Broker, the Consent Graph is opt-in on the
    registry's ``SecurityConfig``. The ``consent_graph.available``
    flag tells the consumer whether the rest of the block is real.
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
        requires_consent: bool = False,
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            tags={"curated"},
            requires_consent=requires_consent,
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _attach_graph(self, registry: PureCipherRegistry):
        from fastmcp.server.security.consent.graph import ConsentGraph

        graph = ConsentGraph(graph_id="test-graph")
        registry._required_context().consent_graph = graph
        return graph

    def _seed_active_edge(
        self,
        graph,
        *,
        source_id: str = "owner",
        target_id: str = "agent-1",
        scopes: set[str] | None = None,
        metadata: dict | None = None,
    ):
        """Seed an ACTIVE consent edge directly into the graph's
        internal state — the public ``grant`` API requires nodes
        and emits audit/event traffic we don't need here."""
        from datetime import datetime, timedelta, timezone

        from fastmcp.server.security.consent.models import (
            ConsentEdge,
            ConsentStatus,
        )

        edge = ConsentEdge(
            source_id=source_id,
            target_id=target_id,
            scopes=scopes or {"execute"},
            status=ConsentStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            metadata=metadata or {},
        )
        graph._edges[edge.edge_id] = edge
        graph._outgoing.setdefault(source_id, []).append(edge)
        graph._incoming.setdefault(target_id, []).append(edge)
        return edge

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/governance/consent")
            assert resp.status_code == 404
            assert "not found" in resp.json()["error"].lower()

    def test_graph_unavailable_when_not_configured(self):
        """As of Iter8 the consent graph is *enabled by default*.
        Operators who explicitly opt out via ``enable_consent=False``
        get a registry with no graph — the endpoint surfaces that
        honestly."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_consent=False,
        )
        self._catalog_listing(registry, tool_name="tool-a")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        assert payload["server_id"] == "alice"
        graph_block = payload["consent_graph"]
        assert graph_block["available"] is False
        assert "not enabled" in graph_block["reason"].lower()

        # Per-tool block still renders — the manifest-side signal
        # (requires_consent=False) is independent of graph wiring.
        per_tool = payload["per_tool_consent"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["binding_source"] == "consent_optional"
        assert row["graph_grant_count"] == 0
        assert row["grant_sources"] == []

    def test_federation_block_advertises_unavailable(self):
        """Federation isn't on the security context yet. The block
        must say so explicitly so the UI doesn't render misleading
        peer/jurisdiction values."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            payload = resp.json()
        federation = payload["federation"]
        assert federation["available"] is False
        assert "federated" in federation["reason"].lower()

    def test_manifest_requires_consent_drives_binding_source(self):
        """``binding_source=consent_required`` reflects the listing's
        manifest, not graph activity. A tool that requires consent
        with no graph grants must STILL show consent_required —
        that's the operator-gap signal."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(
            registry, tool_name="needs-consent", requires_consent=True
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            payload = resp.json()

        row = payload["per_tool_consent"][0]
        assert row["requires_consent"] is True
        assert row["binding_source"] == "consent_required"
        assert row["graph_grant_count"] == 0

        summary = payload["summary"]
        assert summary["requires_consent_count"] == 1
        assert summary["with_grants_count"] == 0

    def test_graph_configured_with_no_grants(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        graph = self._attach_graph(registry)

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            payload = resp.json()

        gb = payload["consent_graph"]
        assert gb["available"] is True
        assert gb["graph_id"] == graph.graph_id
        assert gb["node_count"] == 0
        assert gb["edge_count"] == 0
        assert gb["active_edge_count"] == 0
        assert gb["audit_entry_count"] == 0
        assert gb["node_counts_by_type"] == {
            "agent": 0,
            "resource": 0,
            "scope": 0,
            "group": 0,
            "institution": 0,
        }
        # No grants exist anywhere.
        assert payload["per_tool_consent"][0]["graph_grant_count"] == 0

    def test_edge_with_scope_referencing_tool_surfaces_grant(self):
        """Scopes like ``call:weather-lookup`` are common in the
        consent graph. The walker must surface them as grants for
        ``weather-lookup``."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="weather-lookup")
        graph = self._attach_graph(registry)
        self._seed_active_edge(
            graph,
            source_id="data-owner",
            target_id="agent-007",
            scopes={"call:weather-lookup", "execute"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            row = resp.json()["per_tool_consent"][0]

        assert row["graph_grant_count"] == 1
        assert row["grant_sources"] == ["data-owner"]

    def test_edge_with_metadata_referencing_tool_surfaces_grant(self):
        """Some operators encode the tool reference in edge metadata
        rather than scope strings. The walker should still pick it up."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-meta")
        graph = self._attach_graph(registry)
        self._seed_active_edge(
            graph,
            source_id="meta-owner",
            target_id="agent-meta",
            scopes={"execute"},
            metadata={"tool_name": "tool-meta"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            row = resp.json()["per_tool_consent"][0]
        assert row["graph_grant_count"] == 1

    def test_edge_with_source_or_target_naming_tool_surfaces_grant(self):
        """If an operator wires the tool as a graph node directly
        (``source_id="weather-lookup"`` or ``"tool:weather-lookup"``),
        the walker should pick that up too."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="weather-lookup")
        graph = self._attach_graph(registry)
        self._seed_active_edge(
            graph,
            source_id="tool:weather-lookup",
            target_id="agent-direct",
            scopes={"execute"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            row = resp.json()["per_tool_consent"][0]
        assert row["graph_grant_count"] == 1
        assert row["grant_sources"] == ["tool:weather-lookup"]

    def test_expired_consent_edges_excluded(self):
        from datetime import datetime, timedelta, timezone

        from fastmcp.server.security.consent.models import (
            ConsentEdge,
            ConsentStatus,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        graph = self._attach_graph(registry)

        expired = ConsentEdge(
            source_id="ghost-owner",
            target_id="ghost-agent",
            scopes={"call:tool-a"},
            status=ConsentStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        graph._edges[expired.edge_id] = expired
        graph._outgoing.setdefault("ghost-owner", []).append(expired)

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            row = resp.json()["per_tool_consent"][0]
        assert row["graph_grant_count"] == 0

    def test_revoked_consent_edges_excluded(self):
        from fastmcp.server.security.consent.models import (
            ConsentEdge,
            ConsentStatus,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        graph = self._attach_graph(registry)

        revoked = ConsentEdge(
            source_id="rev-owner",
            target_id="rev-agent",
            scopes={"call:tool-a"},
            status=ConsentStatus.REVOKED,
        )
        graph._edges[revoked.edge_id] = revoked

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            row = resp.json()["per_tool_consent"][0]
        assert row["graph_grant_count"] == 0

    def test_node_counts_by_type_aggregate_correctly(self):
        from fastmcp.server.security.consent.models import (
            ConsentNode,
            NodeType,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        graph = self._attach_graph(registry)

        graph.add_node(ConsentNode("a1", NodeType.AGENT))
        graph.add_node(ConsentNode("a2", NodeType.AGENT))
        graph.add_node(ConsentNode("r1", NodeType.RESOURCE))
        graph.add_node(ConsentNode("g1", NodeType.GROUP))

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            gb = resp.json()["consent_graph"]
        assert gb["node_counts_by_type"]["agent"] == 2
        assert gb["node_counts_by_type"]["resource"] == 1
        assert gb["node_counts_by_type"]["group"] == 1
        assert gb["node_count"] == 4

    def test_summary_aggregates_across_mixed_listings(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(
            registry, tool_name="tool-required", requires_consent=True
        )
        self._catalog_listing(
            registry, tool_name="tool-optional", requires_consent=False
        )
        graph = self._attach_graph(registry)
        # A grant for tool-required only.
        self._seed_active_edge(
            graph,
            source_id="grant-owner",
            target_id="grant-agent",
            scopes={"call:tool-required"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            payload = resp.json()

        summary = payload["summary"]
        assert summary["tool_count"] == 2
        assert summary["requires_consent_count"] == 1
        assert summary["with_grants_count"] == 1
        assert summary["without_grants_count"] == 1

    def test_anonymous_caller_sees_public_listings_only(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")
        with TestClient(registry.http_app()) as client:
            assert (
                client.get("/registry/servers/alice/governance/consent").status_code
                == 404
            )

    def test_authenticated_caller_sees_pending_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(
            registry,
            tool_name="curator-tool",
            author="publisher",
            requires_consent=True,
        )

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/governance/consent")
            assert authed.status_code == 200
            payload = authed.json()
            row = payload["per_tool_consent"][0]
            assert row["status"] == "pending_review"
            assert row["binding_source"] == "consent_required"

    def test_links_point_at_consent_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/consent")
            assert resp.json()["links"]["consent_graph_url"] == "/registry/consent"


class TestServerLedgerGovernance:
    """Iteration 4 of the server-profile Governance tab — Provenance
    Ledger.

    Two layers, parallel to the Policy Kernel story:

    - **Registry-wide ledger** (opt-in via
      ``SecurityConfig.provenance``): records registry-side actions.
      The endpoint surfaces availability + counts + current Merkle
      root; verification (verify_chain/verify_tree) is deferred to
      a separate endpoint to keep the panel fast.
    - **Per-listing ledger bindings**: every curator-attested proxy
      listing gets a dedicated ledger spun up at gateway mount
      (``ledger_id=f"curator-proxy-{listing_id}"``), so its
      ``binding_source="proxy_ledger"`` with ``expected_ledger_id``.
      Catalog-only listings get ``binding_source="no_ledger"``.
      When the registry-wide ledger is configured, per-tool rows
      additionally surface ``central_record_count`` /
      ``latest_central_record_at`` from records whose
      ``resource_id`` matches the tool name.
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(tool_name=tool_name, author=author, tags={"curated"})
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _proxy_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(tool_name=tool_name, author=author, tags={"curated"})
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            metadata={"introspection": {"tool_names": ["x"]}},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _attach_ledger(self, registry: PureCipherRegistry):
        """Replace whatever provenance ledger the registry has with
        a clean test-scoped one. As of Iter8 the default registry
        already has a ledger wired, so this helper *replaces* it
        with one whose state we control rather than appending."""
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        ledger = ProvenanceLedger(ledger_id="test-ledger")
        registry._required_context().provenance_ledger = ledger
        return ledger

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/governance/ledger")
            assert resp.status_code == 404

    def test_ledger_unavailable_when_not_configured(self):
        """As of Iter8 the central ledger is *enabled by default*.
        Operators who explicitly opt out via
        ``enable_provenance=False`` get a registry with no central
        ledger — the endpoint surfaces that honestly while the
        per-tool block still renders proxy_ledger / no_ledger
        bindings, which are intrinsic to hosting_mode."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_provenance=False,
        )
        listing_id = self._proxy_listing(registry, tool_name="proxy-tool")
        self._catalog_listing(registry, tool_name="cat-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            assert resp.status_code == 200
            payload = resp.json()

        assert payload["ledger"]["available"] is False
        assert "not enabled" in payload["ledger"]["reason"].lower()

        # Per-tool bindings are still meaningful.
        rows_by_tool = {row["tool_name"]: row for row in payload["per_tool_ledger"]}
        proxy_row = rows_by_tool["proxy-tool"]
        assert proxy_row["binding_source"] == "proxy_ledger"
        assert proxy_row["expected_ledger_id"] == f"curator-proxy-{listing_id}"
        assert proxy_row["central_record_count"] == 0

        cat_row = rows_by_tool["cat-tool"]
        assert cat_row["binding_source"] == "no_ledger"
        assert cat_row["expected_ledger_id"] is None

    def test_ledger_available_with_no_records(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        ledger = self._attach_ledger(registry)

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            payload = resp.json()

        block = payload["ledger"]
        assert block["available"] is True
        assert block["ledger_id"] == ledger.ledger_id
        assert block["record_count"] == 0
        assert block["latest_record_at"] is None
        assert block["latest_record_action"] is None

    def test_proxy_listing_gets_proxy_ledger_binding(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._proxy_listing(registry, tool_name="px-1")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            row = resp.json()["per_tool_ledger"][0]
        assert row["binding_source"] == "proxy_ledger"
        assert row["expected_ledger_id"] == f"curator-proxy-{listing_id}"

    def test_catalog_listing_gets_no_ledger_binding(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="cat-1")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            row = resp.json()["per_tool_ledger"][0]
        assert row["binding_source"] == "no_ledger"
        assert row["expected_ledger_id"] is None

    def test_central_records_matching_resource_id_surface(self):
        """Records on the registry-wide ledger whose ``resource_id``
        equals a tool's name must surface as the tool's
        ``central_record_count``."""
        from fastmcp.server.security.provenance.records import (
            ProvenanceAction,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._proxy_listing(registry, tool_name="px-rec")
        self._catalog_listing(registry, tool_name="cat-rec")
        ledger = self._attach_ledger(registry)

        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent-1",
            resource_id="px-rec",
        )
        ledger.record(
            action=ProvenanceAction.TOOL_RESULT,
            actor_id="agent-1",
            resource_id="px-rec",
        )
        # Unrelated record — shouldn't bind to either listing.
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent-1",
            resource_id="not-a-listing",
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            rows = {r["tool_name"]: r for r in resp.json()["per_tool_ledger"]}
        assert rows["px-rec"]["central_record_count"] == 2
        assert rows["px-rec"]["latest_central_record_action"] == "tool_result"
        assert rows["cat-rec"]["central_record_count"] == 0

        ledger_block = resp.json()["ledger"]
        assert ledger_block["record_count"] == 3
        assert ledger_block["latest_record_resource_id"] == "not-a-listing"

    def test_summary_aggregates_across_mixed_listings(self):
        from fastmcp.server.security.provenance.records import (
            ProvenanceAction,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._proxy_listing(registry, tool_name="px-1")
        self._proxy_listing(registry, tool_name="px-2")
        self._catalog_listing(registry, tool_name="cat-1")
        ledger = self._attach_ledger(registry)
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent",
            resource_id="px-1",
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            payload = resp.json()
        summary = payload["summary"]
        assert summary["tool_count"] == 3
        assert summary["with_proxy_ledger_count"] == 2
        assert summary["with_central_records_count"] == 1
        assert summary["total_central_records_for_tools"] == 1

    def test_anonymous_caller_sees_public_listings_only(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")

        with TestClient(registry.http_app()) as client:
            assert (
                client.get("/registry/servers/alice/governance/ledger").status_code
                == 404
            )

    def test_authenticated_caller_sees_pending_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._proxy_listing(registry, tool_name="curator-tool", author="publisher")

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/governance/ledger")
            assert authed.status_code == 200
            row = authed.json()["per_tool_ledger"][0]
            assert row["status"] == "pending_review"
            assert row["binding_source"] == "proxy_ledger"

    def test_links_point_at_provenance_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/ledger")
            assert (
                resp.json()["links"]["provenance_ledger_url"] == "/registry/provenance"
            )


class TestServerOverridesGovernance:
    """Iteration 5 of the server-profile Governance tab — Overrides.

    Surfaces operator/moderator interventions across all of a
    server's tools in one rollup view: status overrides
    (PENDING_REVIEW / SUSPENDED / DEPRECATED / REJECTED), the
    moderation log of every approve/reject/suspend/etc decision,
    yanked versions, and the cross-reference to per-listing policy
    overrides (proxy AllowlistPolicy from earlier iterations).
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(tool_name=tool_name, author=author, tags={"curated"})
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _proxy_listing_with_observed(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        observed: list[str],
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(tool_name=tool_name, author=author, tags={"curated"})
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            metadata={"introspection": {"tool_names": list(observed)}},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/governance/overrides")
            assert resp.status_code == 404

    def test_active_listing_with_no_overrides(self):
        """A plain published listing with no moderation activity
        should render as ``binding_source=active`` and contribute
        cleanly to the published count."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="clean-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/overrides")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        assert payload["server_id"] == "alice"
        per_tool = payload["per_tool_overrides"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["binding_source"] == "active"
        assert row["status"] == "published"
        assert row["moderation"]["open"] is False
        assert row["moderation"]["log_entries"] == 0
        assert row["moderation"]["latest_action"] is None
        assert row["yanked_versions"] == []
        assert row["policy_override"]["active"] is False

        summary = payload["summary"]
        assert summary["tool_count"] == 1
        assert summary["published_count"] == 1
        assert summary["pending_review_count"] == 0
        assert summary["suspended_count"] == 0
        assert summary["yanked_version_count"] == 0
        assert summary["policy_override_count"] == 0
        assert summary["open_moderation_actions"] == 0

        assert payload["recent_moderation_decisions"] == []
        assert payload["links"]["moderation_queue_url"] == "/registry/review"

    def test_pending_review_listing_surfaces_moderation_pending(self):
        """A listing with ``status=PENDING_REVIEW`` is the most
        actionable override — must surface as the highest-priority
        binding_source.

        We call the registry method directly with
        ``include_non_public=True`` so the test isolates the
        binding-source projection from the route's visibility
        gating. The visibility paths themselves are covered by the
        anonymous/authenticated tests below.
        """
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")

        payload = registry.get_server_overrides_governance(
            "alice", include_non_public=True
        )
        row = payload["per_tool_overrides"][0]
        assert row["status"] == "pending_review"
        assert row["binding_source"] == "moderation_pending"
        assert row["moderation"]["open"] is True

        summary = payload["summary"]
        assert summary["pending_review_count"] == 1
        assert summary["open_moderation_actions"] == 1

    def test_suspended_listing_with_log_surfaces_moderated(self):
        """A listing that's been approved then suspended carries two
        decisions in its log. The row's ``binding_source`` is
        ``moderated``, ``status`` is ``suspended``, and the latest
        decision metadata reflects the suspend."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        listing_id = self._catalog_listing(registry, tool_name="sus-tool")
        registry.moderate_listing(listing_id, action_name="approve", reason="ok")
        registry.moderate_listing(listing_id, action_name="suspend", reason="temporary")

        payload = registry.get_server_overrides_governance(
            "alice", include_non_public=True
        )

        row = payload["per_tool_overrides"][0]
        assert row["status"] == "suspended"
        assert row["binding_source"] == "moderated"
        assert row["moderation"]["log_entries"] == 2
        assert row["moderation"]["latest_action"] == "suspend"
        assert row["moderation"]["latest_reason"] == "temporary"

        # Recent decisions feed sorts most-recent first.
        decisions = payload["recent_moderation_decisions"]
        assert len(decisions) == 2
        assert decisions[0]["action"] == "suspend"
        assert decisions[0]["tool_name"] == "sus-tool"
        assert decisions[1]["action"] == "approve"

        summary = payload["summary"]
        assert summary["suspended_count"] == 1
        assert summary["published_count"] == 0
        assert summary["open_moderation_actions"] == 0

    def test_proxy_listing_surfaces_policy_override(self):
        """Proxy listings with curator-vouched observed tools have
        a per-listing AllowlistPolicy at the proxy gateway. Surface
        ``policy_override.active=true`` so a moderator scanning the
        Overrides panel sees it without leaving the page."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._proxy_listing_with_observed(
            registry,
            tool_name="proxy-tool",
            observed=["a", "b", "c"],
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/overrides")
            row = resp.json()["per_tool_overrides"][0]
        assert row["policy_override"]["active"] is True
        assert row["policy_override"]["allowed_count"] == 3

        summary = resp.json()["summary"]
        assert summary["policy_override_count"] == 1

    def test_yanked_versions_surface_on_listing(self):
        """A listing with yanked versions in its history must
        surface the yanked entries on the row and contribute to
        the summary's ``yanked_version_count``."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._catalog_listing(registry, tool_name="yanked-tool")

        # Submit a second version then yank the first.
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest_v2 = _manifest(
            tool_name="yanked-tool",
            author="alice",
            version="1.1.0",
            tags={"curated"},
        )
        registry.submit_tool(
            manifest_v2,
            display_name="Yanked Tool",
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id="alice",
            requested_level=CertificationLevel.BASIC,
        )
        marketplace = registry._marketplace()
        marketplace.yank_version(
            listing_id, version="1.0.0", reason="security regression"
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/overrides")
            payload = resp.json()
        row = payload["per_tool_overrides"][0]
        assert len(row["yanked_versions"]) == 1
        yanked = row["yanked_versions"][0]
        assert yanked["version"] == "1.0.0"
        assert yanked["yank_reason"] == "security regression"

        summary = payload["summary"]
        assert summary["yanked_version_count"] == 1

    def test_summary_aggregates_across_mixed_listings(self):
        """Summary counters must aggregate correctly across multiple
        tools with varied override states. Calls the method directly
        with ``include_non_public=True`` so the assertion targets
        the projection logic, not the visibility filter."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        published_id = self._catalog_listing(registry, tool_name="published")
        registry.moderate_listing(published_id, action_name="approve", reason="ok")
        # Pending listing — stays in PENDING_REVIEW.
        self._catalog_listing(registry, tool_name="pending-1")
        # Proxy with observed tools (override active) — also lands
        # in PENDING_REVIEW under require_moderation=True.
        self._proxy_listing_with_observed(
            registry, tool_name="proxy-tool", observed=["one"]
        )
        # Suspended listing.
        sus_id = self._catalog_listing(registry, tool_name="suspended-tool")
        registry.moderate_listing(sus_id, action_name="approve", reason="ok")
        registry.moderate_listing(sus_id, action_name="suspend", reason="bad behavior")

        payload = registry.get_server_overrides_governance(
            "alice", include_non_public=True
        )

        summary = payload["summary"]
        assert summary["tool_count"] == 4
        assert summary["published_count"] == 1
        assert summary["pending_review_count"] == 2
        assert summary["suspended_count"] == 1
        assert summary["policy_override_count"] == 1
        # Two pending tools + the suspend action wasn't open, so
        # only the two pending ones contribute open_moderation_actions.
        assert summary["open_moderation_actions"] == 2

    def test_recent_decisions_are_capped_and_sorted(self):
        """The cross-tool recent_moderation_decisions feed sorts by
        created_at desc and caps at the configured limit so the
        panel renders fast even on busy servers."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._catalog_listing(registry, tool_name="busy-tool")

        for i in range(15):
            registry.moderate_listing(
                listing_id,
                action_name="approve",
                reason=f"decision-{i}",
            )

        # Use the public registry method directly to test capping
        # behavior with a custom limit.
        result = registry.get_server_overrides_governance(
            "alice", recent_decision_limit=5
        )
        decisions = result["recent_moderation_decisions"]
        assert len(decisions) == 5
        # Most-recent first → reasons are the LAST 5 we added
        # (decision-14 ... decision-10 in that order).
        reasons = [d["reason"] for d in decisions]
        assert reasons == [
            "decision-14",
            "decision-13",
            "decision-12",
            "decision-11",
            "decision-10",
        ]

    def test_anonymous_caller_sees_public_listings_only(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")

        with TestClient(registry.http_app()) as client:
            assert (
                client.get("/registry/servers/alice/governance/overrides").status_code
                == 404
            )

    def test_authenticated_caller_sees_pending_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="curator-pending", author="publisher")

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/governance/overrides")
            assert authed.status_code == 200
            row = authed.json()["per_tool_overrides"][0]
            assert row["status"] == "pending_review"
            assert row["binding_source"] == "moderation_pending"

    def test_links_point_at_review_queue(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/governance/overrides")
            assert resp.json()["links"]["moderation_queue_url"] == "/registry/review"


class TestServerObservability:
    """Iteration 6 — the Observability tab's Reflexive Core panel.

    The endpoint is ``/registry/servers/{server_id}/observability``
    (sibling to the governance/* routes; observability is a
    different tab on the server profile, not a control plane).

    Reflexive Core is opt-in via ``SecurityConfig.reflexive``. When
    wired, the registry's ``BehavioralAnalyzer`` tracks per-actor
    metric baselines and raises ``DriftEvent`` records when
    observed values exceed configured thresholds. Drift events are
    actor-centric — tool-binding here is a best-effort match on
    ``event.metadata`` keys (``tool_name`` / ``resource_id`` /
    ``tool_names``) and literal substring matches in
    ``event.description``.
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(tool_name=tool_name, author=author, tags={"curated"})
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _attach_analyzer(self, registry: PureCipherRegistry):
        from fastmcp.server.security.reflexive.analyzer import (
            BehavioralAnalyzer,
        )

        analyzer = BehavioralAnalyzer(analyzer_id="test-analyzer")
        registry._required_context().behavioral_analyzer = analyzer
        return analyzer

    def _seed_drift_event(
        self,
        analyzer,
        *,
        actor_id: str,
        severity_value: str,
        description: str = "",
        metadata: dict | None = None,
        drift_type_value: str = "frequency_spike",
    ):
        """Seed a drift event directly into the analyzer's history."""
        from datetime import datetime, timezone

        from fastmcp.server.security.reflexive.models import (
            DriftEvent,
            DriftSeverity,
            DriftType,
        )

        event = DriftEvent(
            drift_type=DriftType(drift_type_value),
            severity=DriftSeverity(severity_value),
            actor_id=actor_id,
            description=description,
            observed_value=50.0,
            baseline_value=5.0,
            deviation=9.0,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        analyzer._drift_history.append(event)
        return event

    def test_returns_404_for_unknown_publisher(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/nope/observability")
            assert resp.status_code == 404

    def test_analyzer_unavailable_when_not_configured(self):
        """As of Iter8 the Reflexive Core is *enabled by default*.
        Operators who explicitly opt out via
        ``enable_reflexive=False`` get a registry with no analyzer —
        the endpoint surfaces that honestly without faking values."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_reflexive=False,
        )
        self._catalog_listing(registry, tool_name="tool-a")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/observability")
            assert resp.status_code == 200
            payload = resp.json()

        analyzer = payload["analyzer"]
        assert analyzer["available"] is False
        assert "not enabled" in analyzer["reason"].lower()

        # Per-tool block still renders; tools just have no observations.
        per_tool = payload["per_tool_observability"]
        assert len(per_tool) == 1
        row = per_tool[0]
        assert row["binding_source"] == "no_observations"
        assert row["drift_event_count"] == 0
        assert row["highest_severity"] is None

    def test_analyzer_attached_with_no_events(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="tool-a")
        analyzer = self._attach_analyzer(registry)

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/observability")
            payload = resp.json()

        block = payload["analyzer"]
        assert block["available"] is True
        assert block["analyzer_id"] == analyzer.analyzer_id
        assert block["total_drift_count"] == 0
        assert block["monitored_actor_count"] == 0
        assert block["tracked_metric_count"] == 0
        assert block["latest_drift_at"] is None
        # All severity buckets present + zero.
        assert block["severity_distribution"] == {
            "info": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }

    def test_drift_event_with_metadata_tool_name_surfaces_per_tool(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="weather-lookup")
        analyzer = self._attach_analyzer(registry)
        self._seed_drift_event(
            analyzer,
            actor_id="agent-007",
            severity_value="medium",
            description="rate spike",
            metadata={"tool_name": "weather-lookup"},
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/observability")
            payload = resp.json()

        row = payload["per_tool_observability"][0]
        assert row["binding_source"] == "monitored"
        assert row["drift_event_count"] == 1
        assert row["highest_severity"] == "medium"
        assert row["latest_drift_severity"] == "medium"
        assert row["severity_distribution"]["medium"] == 1

        # Cross-tool feed picks up the same event with tool_name tagged.
        feed = payload["recent_drift_events"]
        assert len(feed) == 1
        assert feed[0]["tool_name"] == "weather-lookup"
        assert feed[0]["severity"] == "medium"

    def test_drift_event_with_description_substring_match(self):
        """Some drift events encode the tool reference in the
        description rather than metadata. The walker must pick
        those up too via literal substring match."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="critical-tool")
        analyzer = self._attach_analyzer(registry)
        self._seed_drift_event(
            analyzer,
            actor_id="agent-desc",
            severity_value="high",
            description="Frequency spike on critical-tool by agent-desc",
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/observability")
            row = resp.json()["per_tool_observability"][0]
        assert row["binding_source"] == "monitored"
        assert row["drift_event_count"] == 1
        assert row["highest_severity"] == "high"

    def test_highest_severity_uses_escalation_order(self):
        """When multiple drift events touch a tool, the row reports
        the *highest* severity in the standard escalation order
        (info < low < medium < high < critical)."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="severity-tool")
        analyzer = self._attach_analyzer(registry)
        for severity in ("info", "high", "medium", "low"):
            self._seed_drift_event(
                analyzer,
                actor_id=f"agent-{severity}",
                severity_value=severity,
                metadata={"tool_name": "severity-tool"},
            )

        result = registry.get_server_observability("alice")
        row = result["per_tool_observability"][0]
        assert row["drift_event_count"] == 4
        assert row["highest_severity"] == "high"
        # Distribution captured.
        assert row["severity_distribution"]["info"] == 1
        assert row["severity_distribution"]["low"] == 1
        assert row["severity_distribution"]["medium"] == 1
        assert row["severity_distribution"]["high"] == 1

        summary = result["summary"]
        assert summary["with_high_drift_count"] == 1
        assert summary["with_critical_drift_count"] == 0

    def test_critical_severity_lifts_summary_count(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="critical-tool")
        analyzer = self._attach_analyzer(registry)
        self._seed_drift_event(
            analyzer,
            actor_id="agent-crit",
            severity_value="critical",
            metadata={"tool_name": "critical-tool"},
        )

        result = registry.get_server_observability("alice")
        assert result["summary"]["with_critical_drift_count"] == 1
        assert result["summary"]["with_high_drift_count"] == 0
        assert result["per_tool_observability"][0]["highest_severity"] == "critical"

    def test_recent_drift_events_capped_and_sorted_desc(self):
        """The cross-tool feed is most-recent first and capped at
        the limit so a busy analyzer doesn't bloat the response."""
        import time

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="busy-tool")
        analyzer = self._attach_analyzer(registry)

        for i in range(15):
            self._seed_drift_event(
                analyzer,
                actor_id=f"agent-{i}",
                severity_value="info",
                description=f"event-{i}",
                metadata={"tool_name": "busy-tool"},
            )
            # Force timestamps to differ for stable sort.
            time.sleep(0.001)

        result = registry.get_server_observability("alice", recent_event_limit=5)
        feed = result["recent_drift_events"]
        assert len(feed) == 5
        # Most-recent first → descriptions come from the LAST 5 added.
        descriptions = [item["description"] for item in feed]
        assert descriptions == [
            "event-14",
            "event-13",
            "event-12",
            "event-11",
            "event-10",
        ]

    def test_unrelated_drift_events_excluded_from_feed(self):
        """The feed only carries events that reference one of this
        server's tools — global drift across the registry shouldn't
        leak into a publisher's panel."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="my-tool")
        analyzer = self._attach_analyzer(registry)

        self._seed_drift_event(
            analyzer,
            actor_id="agent-mine",
            severity_value="medium",
            metadata={"tool_name": "my-tool"},
        )
        self._seed_drift_event(
            analyzer,
            actor_id="agent-other",
            severity_value="high",
            metadata={"tool_name": "other-publishers-tool"},
        )

        result = registry.get_server_observability("alice")
        feed = result["recent_drift_events"]
        assert len(feed) == 1
        assert feed[0]["tool_name"] == "my-tool"

    def test_anonymous_caller_sees_public_listings_only(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool")

        with TestClient(registry.http_app()) as client:
            assert (
                client.get("/registry/servers/alice/observability").status_code == 404
            )

    def test_authenticated_caller_sees_pending_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(
            registry,
            tool_name="curator-pending",
            author="publisher",
        )

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/servers/publisher/observability")
            assert authed.status_code == 200
            row = authed.json()["per_tool_observability"][0]
            assert row["status"] == "pending_review"
            assert row["binding_source"] == "no_observations"

    def test_links_point_at_reflexive_page(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/servers/alice/observability")
            assert resp.json()["links"]["reflexive_core_url"] == "/registry/reflexive"


class TestListingGovernance:
    """Iteration 7 — per-listing governance + observability rollup.

    Mirror of the publisher-scoped server profile views, scoped to
    a single listing. The endpoint is
    ``/registry/tools/{tool_name}/governance`` and composes the
    same ``_summarize_listing_*`` projections as the publisher
    endpoints, so a tool's binding_source for any given plane is
    *guaranteed* identical between the per-listing and
    per-publisher views.

    Public callers (anonymous, or unauthenticated when auth is on)
    receive a sanitized response with operator-private fields
    (actor IDs, moderator IDs, agent IDs) stripped so a public
    viewer browsing a tool sees its posture without operator
    internals.
    """

    def _catalog_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
        requires_consent: bool = False,
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            tags={"curated"},
            requires_consent=requires_consent,
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def _proxy_listing(
        self,
        registry: PureCipherRegistry,
        *,
        tool_name: str,
        author: str = "alice",
        observed: list[str] | None = None,
    ) -> str:
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        observed = observed or ["fetch", "save"]
        manifest = _manifest(
            tool_name=tool_name,
            author=author,
            tags={"curated", *observed},
        )
        result = registry.submit_tool(
            manifest,
            display_name=tool_name.title(),
            categories={ToolCategory.NETWORK},
            metadata={"introspection": {"tool_names": list(observed)}},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            curator_id=author,
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        assert result.listing is not None
        return result.listing.listing_id

    def test_returns_404_for_unknown_tool(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/nope/governance")
            assert resp.status_code == 404

    def test_response_carries_all_six_plane_blocks(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._proxy_listing(registry, tool_name="proxy-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/proxy-tool/governance")
            assert resp.status_code == 200, resp.text
            payload = resp.json()

        # Six plane blocks present at top level.
        for plane in (
            "policy",
            "contracts",
            "consent",
            "ledger",
            "overrides",
            "observability",
        ):
            assert plane in payload, f"Missing plane block: {plane}"

        # Header carries identity.
        assert payload["tool_name"] == "proxy-tool"
        assert payload["publisher_id"] == "alice"
        assert payload["hosting_mode"] == "proxy"
        assert payload["attestation_kind"] == "curator"

        # Links cover all five governance pages plus observability + publisher.
        for link in (
            "policy_kernel_url",
            "contract_broker_url",
            "consent_graph_url",
            "provenance_ledger_url",
            "moderation_queue_url",
            "reflexive_core_url",
            "publisher_url",
        ):
            assert payload["links"].get(link), f"Missing link: {link}"

    def test_proxy_listing_policy_block_matches_publisher_view(self):
        """The per-listing projection must agree with the per-
        publisher projection for the same listing — same binding
        source, same provider details."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._proxy_listing(
            registry,
            tool_name="match-tool",
            observed=["x", "y", "z"],
        )

        with TestClient(registry.http_app()) as client:
            listing_resp = client.get("/registry/tools/match-tool/governance")
            publisher_resp = client.get("/registry/servers/alice/governance/policy")
        listing_policy = listing_resp.json()["policy"]
        publisher_row = next(
            row
            for row in publisher_resp.json()["per_tool_policies"]
            if row["tool_name"] == "match-tool"
        )

        assert listing_policy["binding_source"] == publisher_row["binding_source"]
        assert listing_policy["policy_provider"] == publisher_row["policy_provider"]

    def test_catalog_listing_has_inherited_policy_and_no_ledger(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="cat-tool")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/cat-tool/governance")
            payload = resp.json()

        assert payload["policy"]["binding_source"] == "inherited"
        assert payload["ledger"]["binding_source"] == "no_ledger"
        assert payload["ledger"]["expected_ledger_id"] is None
        assert payload["overrides"]["binding_source"] == "active"

    def test_consent_required_flag_propagates_from_manifest(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(
            registry,
            tool_name="needs-consent",
            requires_consent=True,
        )

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/needs-consent/governance")
            payload = resp.json()

        assert payload["consent"]["requires_consent"] is True
        assert payload["consent"]["binding_source"] == "consent_required"

    def test_anonymous_response_is_sanitized(self):
        """Anonymous callers should never see actor IDs, moderator
        IDs, or agent IDs in the payload."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        listing_id = self._catalog_listing(registry, tool_name="moderated-tool")
        registry.moderate_listing(listing_id, action_name="approve", reason="ok")
        registry.moderate_listing(listing_id, action_name="suspend", reason="paused")

        # No auth wired → anonymous + sanitize.
        # But suspending makes the listing non-public; switch off
        # moderation visibility by approving back to PUBLISHED.
        registry.moderate_listing(listing_id, action_name="unsuspend", reason="resumed")

        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/moderated-tool/governance")
            payload = resp.json()

        # Moderation log is wiped for public callers; counts are kept.
        moderation = payload["overrides"]["moderation"]
        assert moderation["log"] == []
        assert moderation["log_entries"] == 3
        assert "latest_moderator_id" not in moderation

        # Contract / consent identity arrays are empty.
        assert payload["contracts"]["matching_agents"] == []
        assert payload["consent"]["grant_sources"] == []

        # Observability analyzer block doesn't leak last actor.
        assert "latest_drift_actor_id" not in payload["observability"]["analyzer"]

    def test_authenticated_response_keeps_operator_fields(self):
        """Logged-in publishers / reviewers / admins need the
        unsanitized view so they can act on the data."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        listing_id = self._catalog_listing(
            registry, tool_name="moderated-tool", author="publisher"
        )
        registry.moderate_listing(listing_id, action_name="approve", reason="ok")

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            resp = client.get("/registry/tools/moderated-tool/governance")
            payload = resp.json()

        # Authenticated view keeps the moderation log + IDs.
        moderation = payload["overrides"]["moderation"]
        assert moderation["log_entries"] == 1
        assert len(moderation["log"]) == 1
        assert moderation["log"][0]["moderator_id"] == "purecipher-admin"
        assert moderation["latest_moderator_id"] == "purecipher-admin"

    def test_authenticated_caller_sees_pending_listing(self):
        """Curators must see their own pending submissions on this
        endpoint — same visibility rule as the listing detail
        endpoint."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        self._catalog_listing(registry, tool_name="pending-tool", author="publisher")

        with TestClient(registry.http_app()) as client:
            anon = client.get("/registry/tools/pending-tool/governance")
            assert anon.status_code == 404

            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200, login.text

            authed = client.get("/registry/tools/pending-tool/governance")
            assert authed.status_code == 200
            assert authed.json()["status"] == "pending_review"

    def test_links_include_publisher_url(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        self._catalog_listing(registry, tool_name="link-tool", author="alice")
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/tools/link-tool/governance")
            assert resp.json()["links"]["publisher_url"] == "/registry/publishers/alice"


class TestDefaultControlPlanesEnabled:
    """Iteration 8 regression — verify the default registry config
    wires all five SecureMCP control planes out of the box, plus
    the constructor opt-out flags work for each."""

    def test_default_registry_enables_all_five_planes(self):
        """Construct a registry with no extra config and confirm
        each plane attaches to the security context."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        ctx = registry._required_context()

        # Policy engine ships unconditionally — covered by the rest
        # of the suite — but the four opt-in planes should now also
        # show up by default.
        assert ctx.broker is not None, "Context Broker should default-on"
        assert ctx.consent_graph is not None, "Consent Graph should default-on"
        assert ctx.provenance_ledger is not None, "Provenance Ledger should default-on"
        assert ctx.behavioral_analyzer is not None, "Reflexive Core should default-on"

    def test_enable_contracts_false_disables_broker(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_contracts=False,
        )
        ctx = registry._required_context()
        assert ctx.broker is None
        # Other planes remain on.
        assert ctx.consent_graph is not None
        assert ctx.provenance_ledger is not None
        assert ctx.behavioral_analyzer is not None

    def test_enable_consent_false_disables_consent_graph(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_consent=False,
        )
        ctx = registry._required_context()
        assert ctx.consent_graph is None
        assert ctx.broker is not None
        assert ctx.provenance_ledger is not None
        assert ctx.behavioral_analyzer is not None

    def test_enable_provenance_false_disables_ledger(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_provenance=False,
        )
        ctx = registry._required_context()
        assert ctx.provenance_ledger is None
        assert ctx.broker is not None
        assert ctx.consent_graph is not None
        assert ctx.behavioral_analyzer is not None

    def test_enable_reflexive_false_disables_analyzer(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_reflexive=False,
        )
        ctx = registry._required_context()
        assert ctx.behavioral_analyzer is None
        assert ctx.broker is not None
        assert ctx.consent_graph is not None
        assert ctx.provenance_ledger is not None

    def test_all_planes_can_be_disabled_at_once(self):
        """An operator who wants only the policy + marketplace
        baseline can disable every opt-in plane in one call."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_contracts=False,
            enable_consent=False,
            enable_provenance=False,
            enable_reflexive=False,
        )
        ctx = registry._required_context()
        assert ctx.broker is None
        assert ctx.consent_graph is None
        assert ctx.provenance_ledger is None
        assert ctx.behavioral_analyzer is None

    def test_iter9_runtime_toggle_persists_then_reapplies_on_restart(self, tmp_path):
        """The persistence path of the runtime toggle: a registry
        constructed with all planes default-on, then toggled off,
        then *reconstructed* with the same persistence path should
        come up with the plane already disabled. This is the whole
        point of persisting toggles — operator intent survives
        restart."""
        db_path = str(tmp_path / "purecipher-registry.sqlite")

        first = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=db_path,
        )
        # Default-on: contracts is wired.
        assert first._required_context().broker is not None
        first.disable_plane("contracts", actor_id="admin")
        assert first._required_context().broker is None

        # New registry, same persistence path. The persisted toggle
        # should override the constructor default.
        second = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=db_path,
        )
        assert second._required_context().broker is None

        # Re-enable on the second registry, reconstruct a third —
        # the persisted record should now read True.
        second.enable_plane("contracts", actor_id="admin")
        assert second._required_context().broker is not None
        third = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            persistence_path=db_path,
        )
        assert third._required_context().broker is not None

    def test_governance_panels_render_planes_as_available_by_default(
        self,
    ):
        """Smoke-level: the five governance endpoints should now
        report each plane as available out of the box, not as
        ``not configured``."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        # Need a publisher with at least one listing for the
        # endpoints to return 200.
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        manifest = _manifest(
            tool_name="default-on-tool", author="alice", tags={"curated"}
        )
        result = registry.submit_tool(
            manifest,
            display_name="Default On",
            categories={ToolCategory.NETWORK},
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id="alice",
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted

        with TestClient(registry.http_app()) as client:
            contracts = client.get("/registry/servers/alice/governance/contracts")
            consent = client.get("/registry/servers/alice/governance/consent")
            ledger = client.get("/registry/servers/alice/governance/ledger")
            observability = client.get("/registry/servers/alice/observability")

        assert contracts.json()["broker"]["available"] is True
        assert consent.json()["consent_graph"]["available"] is True
        assert ledger.json()["ledger"]["available"] is True
        assert observability.json()["analyzer"]["available"] is True


class TestRuntimeControlPlaneToggles:
    """Iteration 9 — admins can enable/disable opt-in control planes
    at runtime. Toggles take effect immediately AND persist across
    restart so an operator's intent survives a process bounce.
    """

    def test_status_snapshot_reports_all_four_opt_in_planes(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        status = registry.get_control_plane_status()
        names = {p["plane"] for p in status["planes"]}
        assert names == {"contracts", "consent", "provenance", "reflexive"}
        for entry in status["planes"]:
            assert entry["enabled"] is True
            assert entry["persisted"] is None

    def test_disable_drops_plane_attribute_and_middleware(self):
        from fastmcp.server.security.middleware.contract_validation import (
            ContractValidationMiddleware,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        ctx = registry._required_context()

        # Pre-state: broker attached, middleware in chain.
        assert ctx.broker is not None
        assert any(isinstance(m, ContractValidationMiddleware) for m in ctx.middleware)

        registry.disable_plane("contracts", actor_id="alice")

        # Post-state: both gone.
        assert ctx.broker is None
        assert not any(
            isinstance(m, ContractValidationMiddleware) for m in ctx.middleware
        )

    def test_enable_attaches_plane_attribute_and_middleware(self):
        from fastmcp.server.security.middleware.consent_enforcement import (
            ConsentEnforcementMiddleware,
        )

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            enable_consent=False,
        )
        ctx = registry._required_context()
        assert ctx.consent_graph is None
        assert not any(
            isinstance(m, ConsentEnforcementMiddleware) for m in ctx.middleware
        )

        registry.enable_plane("consent", actor_id="alice")
        assert ctx.consent_graph is not None
        assert any(isinstance(m, ConsentEnforcementMiddleware) for m in ctx.middleware)

    def test_disable_then_enable_each_plane_independently(self):
        """All four opt-in planes must round-trip cleanly through
        disable → enable cycles."""
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        for plane in ("contracts", "consent", "provenance", "reflexive"):
            registry.disable_plane(plane, actor_id="alice")
            assert registry.get_control_plane_status()["planes"] != []
            entry = next(
                p
                for p in registry.get_control_plane_status()["planes"]
                if p["plane"] == plane
            )
            assert entry["enabled"] is False

            registry.enable_plane(plane, actor_id="alice")
            entry = next(
                p
                for p in registry.get_control_plane_status()["planes"]
                if p["plane"] == plane
            )
            assert entry["enabled"] is True

    def test_unknown_plane_raises_value_error(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        import pytest

        with pytest.raises(ValueError, match="Unknown control plane"):
            registry.enable_plane("nonsense")
        with pytest.raises(ValueError, match="Unknown control plane"):
            registry.disable_plane("policy")  # policy isn't opt-in

    def test_idempotent_enable(self):
        """Re-enabling an already-enabled plane refreshes the
        persisted record but doesn't double-attach middleware."""
        from fastmcp.server.security.middleware.contract_validation import (
            ContractValidationMiddleware,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        ctx = registry._required_context()
        before = sum(
            1 for m in ctx.middleware if isinstance(m, ContractValidationMiddleware)
        )

        registry.enable_plane("contracts", actor_id="alice")
        registry.enable_plane("contracts", actor_id="alice")

        after = sum(
            1 for m in ctx.middleware if isinstance(m, ContractValidationMiddleware)
        )
        assert before == 1
        assert after == 1

    def test_admin_route_status_returns_snapshot(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200, login.text

            resp = client.get("/registry/admin/control-planes")
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert {p["plane"] for p in payload["planes"]} == {
                "contracts",
                "consent",
                "provenance",
                "reflexive",
            }

    def test_admin_route_toggle_round_trips(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            disable = client.post(
                "/registry/admin/control-planes/contracts",
                json={"enabled": False},
            )
            assert disable.status_code == 200, disable.text
            entry = next(
                p for p in disable.json()["planes"] if p["plane"] == "contracts"
            )
            assert entry["enabled"] is False
            assert entry["persisted"]["updated_by"] == "admin"

            enable = client.post(
                "/registry/admin/control-planes/contracts",
                json={"enabled": True},
            )
            assert enable.status_code == 200
            entry = next(
                p for p in enable.json()["planes"] if p["plane"] == "contracts"
            )
            assert entry["enabled"] is True

    def test_admin_route_requires_admin_role(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            # Anonymous: 401
            anon = client.get("/registry/admin/control-planes")
            assert anon.status_code == 401

            # Publisher (non-admin): 403
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200
            forbidden = client.get("/registry/admin/control-planes")
            assert forbidden.status_code == 403

    def test_admin_route_rejects_unknown_plane_with_400(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200
            resp = client.post(
                "/registry/admin/control-planes/nope",
                json={"enabled": True},
            )
            assert resp.status_code == 400
            assert "unknown" in resp.json()["error"].lower()

    def test_admin_route_rejects_missing_enabled_field(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200
            resp = client.post(
                "/registry/admin/control-planes/contracts",
                json={},
            )
            assert resp.status_code == 400

    def test_toggle_writes_audit_log_entry(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200
            client.post(
                "/registry/admin/control-planes/contracts",
                json={"enabled": False},
            )

        events = registry._account_activity.list_recent(username="admin", limit=20)
        toggle_events = [
            e for e in events if e["event_kind"] == "admin_control_plane_toggle"
        ]
        assert toggle_events, "expected an audit log entry for the toggle"
        assert toggle_events[0]["metadata"]["plane"] == "contracts"
        assert toggle_events[0]["metadata"]["enabled"] is False

    def test_disable_then_endpoint_reports_unavailable(self):
        """After a runtime disable, the matching governance endpoint
        should immediately report ``available: false``."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        # Submit a listing under admin so the endpoint has data to
        # return for the publisher slug.
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )

        result = registry.submit_tool(
            _manifest(tool_name="snap-tool", author="admin"),
            display_name="Snap",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.CATALOG,
            curator_id="admin",
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            # Default-on: broker available.
            before = client.get("/registry/servers/admin/governance/contracts")
            assert before.status_code == 200
            assert before.json()["broker"]["available"] is True

            client.post(
                "/registry/admin/control-planes/contracts",
                json={"enabled": False},
            )

            after = client.get("/registry/servers/admin/governance/contracts")
            assert after.status_code == 200
            assert after.json()["broker"]["available"] is False


class TestRegistryClientIdentities:
    """Iteration 10 — registered MCP-client identities flow through
    every plane as the request actor.

    The unit cover three layers:

    * Direct registry calls (``register_client`` /
      ``authenticate_client_token``) that other call sites depend on.
    * The HTTP CRUD surface used by the registry UI.
    * The middleware-resolver wiring that promotes a bearer token
      to a stable per-plane ``actor_id``.
    """

    def test_register_client_round_trips_token_and_kind(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        result = registry.register_client(
            display_name="Claude Desktop",
            owner_publisher_id="acme",
            slug="claude-desktop",
            description="LLM client for testing",
            intended_use="dev",
            kind="agent",
            issue_initial_token=True,
        )
        assert result["client"]["slug"] == "claude-desktop"
        assert result["client"]["kind"] == "agent"
        assert result["client"]["status"] == "active"
        assert result["token"]["secret_prefix"].startswith("pcc_")
        secret = result["secret"]
        assert isinstance(secret, str) and len(secret) >= 16

        # The plain secret authenticates and resolves to the client.
        auth = registry.authenticate_client_token(secret)
        assert auth is not None
        client, token = auth
        assert client.slug == "claude-desktop"
        assert token.name == "Default"

    def test_register_client_rejects_unknown_kind(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        try:
            registry.register_client(
                display_name="Bogus Kind",
                owner_publisher_id="acme",
                slug="bogus",
                kind="not-a-real-kind",
            )
        except ValueError as exc:
            assert "Unknown client kind" in str(exc)
        else:
            raise AssertionError("ValueError was not raised")

    def test_suspended_client_cannot_authenticate(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        result = registry.register_client(
            display_name="Will Be Suspended",
            owner_publisher_id="acme",
            slug="will-be-suspended",
            kind="agent",
        )
        secret = result["secret"]
        client_id = result["client"]["client_id"]

        # Pre-suspend: token works.
        assert registry.authenticate_client_token(secret) is not None

        registry.suspend_client(client_id, reason="Under review")

        # Post-suspend: token no longer authenticates.
        assert registry.authenticate_client_token(secret) is None

        # Unsuspending restores access.
        registry.unsuspend_client(client_id)
        assert registry.authenticate_client_token(secret) is not None

    def test_revoked_token_cannot_authenticate(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        result = registry.register_client(
            display_name="Token Test",
            owner_publisher_id="acme",
            slug="token-test",
            kind="service",
        )
        secret = result["secret"]
        token_id = result["token"]["token_id"]

        assert registry.authenticate_client_token(secret) is not None

        revoked = registry.revoke_client_token(token_id)
        assert revoked is not None
        assert revoked.is_active() is False

        assert registry.authenticate_client_token(secret) is None

    def test_middleware_chain_includes_client_aware_subclasses(self):
        """The constructor swaps the upstream policy / contract /
        consent / provenance / reflexive middlewares for client-aware
        subclasses and inserts the resolver at the head of the chain.
        Without this wiring, every plane would fall back to the
        SecureMCP default actor extraction (truncated bearer token)
        and the client slug would never reach downstream telemetry.
        """
        from purecipher.middleware.client_actor import (
            ClientActorResolverMiddleware,
        )
        from purecipher.middleware.client_aware_middleware import (
            ClientAwareConsentEnforcementMiddleware,
            ClientAwareContractValidationMiddleware,
            ClientAwarePolicyEnforcementMiddleware,
            ClientAwareProvenanceRecordingMiddleware,
            ClientAwareReflexiveMiddleware,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        ctx = registry._required_context()
        chain = list(ctx.middleware)

        assert isinstance(chain[0], ClientActorResolverMiddleware), (
            "ClientActorResolverMiddleware must run first so the "
            "downstream middlewares can read the resolved slug."
        )

        chain_types = {type(m) for m in chain}
        assert ClientAwarePolicyEnforcementMiddleware in chain_types
        assert ClientAwareContractValidationMiddleware in chain_types
        assert ClientAwareConsentEnforcementMiddleware in chain_types
        assert ClientAwareProvenanceRecordingMiddleware in chain_types
        assert ClientAwareReflexiveMiddleware in chain_types

    def test_get_client_governance_projects_per_plane_summary(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Governance Probe",
            owner_publisher_id="acme",
            slug="governance-probe",
            kind="service",
            issue_initial_token=True,
        )

        payload = registry.get_client_governance("governance-probe")
        assert payload.get("error") is None
        assert payload["slug"] == "governance-probe"
        assert payload["kind"] == "service"

        # Each of the five planes appears with its expected shape.
        assert "registry_policy" in payload["policy"]
        assert payload["contracts"]["active_count"] == 0
        assert payload["consent"]["outgoing_count"] == 0
        assert payload["consent"]["incoming_count"] == 0
        assert payload["ledger"]["record_count"] == 0
        assert payload["reflexive"]["drift_event_count"] == 0
        assert payload["tokens"]["total"] == 1
        assert payload["tokens"]["active"] == 1

    def test_sanitized_client_governance_strips_counterparty_ids(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Public View",
            owner_publisher_id="acme",
            slug="public-view",
            kind="agent",
        )
        sanitized = registry.get_client_governance(
            "public-view", sanitize_for_public=True
        )
        # The detail token list is dropped (counts only).
        assert "items" not in sanitized["tokens"]
        # No active contracts in this synthetic ledger; we just
        # verify the sanitized list survives without a server_id.
        for row in sanitized["contracts"]["active_contracts"]:
            assert "server_id" not in row
            assert "session_id" not in row
            assert "contract_id" not in row

    def test_http_clients_create_list_get(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            # Auth disabled: anyone may create.
            create = client.post(
                "/registry/clients",
                json={
                    "display_name": "Acme Bot",
                    "owner_publisher_id": "acme",
                    "slug": "acme-bot",
                    "kind": "agent",
                },
            )
            assert create.status_code == 201, create.text
            payload = create.json()
            assert payload["client"]["slug"] == "acme-bot"
            assert payload["secret"], "secret must be returned once"

            listing = client.get("/registry/clients")
            assert listing.status_code == 200
            items = listing.json()["items"]
            assert any(c["slug"] == "acme-bot" for c in items)
            assert "agent" in listing.json()["kinds"]

            detail = client.get("/registry/clients/acme-bot")
            assert detail.status_code == 200
            assert detail.json()["client"]["slug"] == "acme-bot"
            assert len(detail.json()["tokens"]) == 1

    def test_http_clients_governance_route_returns_payload(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Governance Client",
                    "owner_publisher_id": "acme",
                    "slug": "governance-client",
                    "kind": "agent",
                },
            )
            resp = client.get("/registry/clients/governance-client/governance")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["slug"] == "governance-client"
            assert data["contracts"]["active_count"] == 0
            assert data["tokens"]["total"] == 1

    def test_http_clients_token_lifecycle(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            create = client.post(
                "/registry/clients",
                json={
                    "display_name": "Token Lifecycle",
                    "owner_publisher_id": "acme",
                    "slug": "token-lifecycle",
                    "kind": "tooling",
                },
            )
            assert create.status_code == 201

            # Issue a second token.
            issued = client.post(
                "/registry/clients/token-lifecycle/tokens",
                json={"name": "ci"},
            )
            assert issued.status_code == 201
            new_token_id = issued.json()["token"]["token_id"]
            assert issued.json()["secret"]

            # Two tokens visible.
            listed = client.get("/registry/clients/token-lifecycle/tokens")
            assert listed.status_code == 200
            assert listed.json()["count"] == 2

            # Revoke the new one.
            revoked = client.delete(
                f"/registry/clients/token-lifecycle/tokens/{new_token_id}"
            )
            assert revoked.status_code == 200
            assert revoked.json()["token"]["active"] is False

    def test_http_clients_404_on_unknown_slug(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/clients/does-not-exist")
            assert resp.status_code == 404
            gov = client.get("/registry/clients/nope/governance")
            assert gov.status_code == 404

    def test_http_clients_publisher_can_only_see_own_clients(self):
        """Visibility: with auth on, a publisher sees only the
        clients they own. Admins see everything. Anonymous → 401.
        """
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            # Anonymous: 401.
            anon = client.get("/registry/clients")
            assert anon.status_code == 401

            # Admin logs in and creates a client owned by ``alice``.
            admin_login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert admin_login.status_code == 200
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Alice Bot",
                    "owner_publisher_id": "alice",
                    "slug": "alice-bot",
                    "kind": "agent",
                },
            )
            # Admin sees it.
            admin_list = client.get("/registry/clients")
            assert admin_list.status_code == 200
            assert any(c["slug"] == "alice-bot" for c in admin_list.json()["items"])

            # Publisher logs in: their derived publisher id is not
            # ``alice``, so they shouldn't see ``alice-bot``.
            client.cookies.clear()
            pub_login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert pub_login.status_code == 200
            pub_list = client.get("/registry/clients")
            assert pub_list.status_code == 200
            assert all(c["slug"] != "alice-bot" for c in pub_list.json()["items"])

    def test_http_clients_anonymous_governance_is_sanitized(self):
        """The governance route is intentionally reachable without
        auth — but non-managers get the sanitized payload (token
        list dropped, counterparty identifiers stripped). The
        per-client *detail* route still requires auth; this is the
        public-page surface.
        """
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            admin_login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert admin_login.status_code == 200
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Public Probe",
                    "owner_publisher_id": "acme",
                    "slug": "public-probe",
                    "kind": "agent",
                },
            )

            client.cookies.clear()
            anon_gov = client.get("/registry/clients/public-probe/governance")
            assert anon_gov.status_code == 200, anon_gov.text
            data = anon_gov.json()
            # Sanitization: tokens.items removed, counts kept.
            assert "items" not in data["tokens"]
            assert "total" in data["tokens"]


class TestRegistryClientSimulator:
    """Iteration 11 — the cross-control-plane request simulator
    composes the *real* read-only evaluation path of every plane
    so an operator can preview what running a request would do.

    Tests cover:

    * happy path with a fresh registry (consent denies by default
      because no edges are seeded — that's the realistic baseline);
    * suspended-client behavior surfaces as a top-level blocker;
    * unknown-action provenance preview falls back to ``custom``;
    * required-fields validation on the HTTP route;
    * owner-or-admin gating of the route under auth.
    """

    @staticmethod
    def _run(coro: Any) -> Any:
        import asyncio

        return asyncio.run(coro)

    def test_simulate_returns_full_trace(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Sim Client",
            owner_publisher_id="acme",
            slug="sim-client",
            kind="agent",
        )
        result = self._run(
            registry.simulate_client_request(
                "sim-client",
                action="call_tool",
                resource_id="delete_user",
            )
        )
        assert result.get("error") is None
        assert result["client"]["slug"] == "sim-client"

        # All five planes report.
        assert "policy" in result
        assert "contracts" in result
        assert "consent" in result
        assert "ledger" in result
        assert "reflexive" in result

        # Provenance preview is shaped correctly and not actually
        # written.
        ledger = result["ledger"]
        assert ledger["would_record"] is True
        assert ledger["preview"]["action"] == "tool_called"
        assert ledger["preview"]["actor_id"] == "sim-client"
        assert ledger["preview"]["resource_id"] == "delete_user"

        # Reflexive plane skipped without a metric.
        assert result["reflexive"]["evaluated"] is False

    def test_simulate_consent_denies_by_default(self):
        """Fresh consent graph has no edges, so a request denies.
        The simulator must surface that as a structured blocker —
        not a 500.
        """
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="No Consent",
            owner_publisher_id="acme",
            slug="no-consent",
            kind="agent",
        )
        result = self._run(
            registry.simulate_client_request(
                "no-consent",
                action="call_tool",
                resource_id="some_tool",
                consent_scope="execute",
            )
        )
        assert result["consent"]["available"] is True
        assert result["consent"]["granted"] is False
        assert result["verdict"] == "deny"
        blocker_planes = {b["plane"] for b in result["blockers"]}
        assert "consent" in blocker_planes

    def test_simulate_suspended_client_blocks_at_top_level(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        out = registry.register_client(
            display_name="Suspended",
            owner_publisher_id="acme",
            slug="suspended-client",
            kind="agent",
        )
        registry.suspend_client(out["client"]["client_id"], reason="under audit")
        result = self._run(
            registry.simulate_client_request(
                "suspended-client",
                action="call_tool",
                resource_id="x",
            )
        )
        assert result["verdict"] == "deny"
        blocker_planes = {b["plane"] for b in result["blockers"]}
        assert "client" in blocker_planes

    def test_simulate_unknown_action_falls_back_to_custom(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Custom",
            owner_publisher_id="acme",
            slug="custom-client",
            kind="agent",
        )
        result = self._run(
            registry.simulate_client_request(
                "custom-client",
                action="totally_made_up_action",
                resource_id="x",
            )
        )
        assert result["ledger"]["preview"]["action"] == "custom"

    def test_simulate_returns_404_for_unknown_client(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        result = self._run(
            registry.simulate_client_request(
                "does-not-exist", action="x", resource_id="y"
            )
        )
        assert result.get("status") == 404

    def test_simulate_reflexive_no_baseline(self):
        """Reflexive baseline is empty until the analyzer has seen
        ≥5 calls. The simulator must report that gracefully.
        """
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Baseline Probe",
            owner_publisher_id="acme",
            slug="baseline-probe",
            kind="service",
        )
        result = self._run(
            registry.simulate_client_request(
                "baseline-probe",
                action="call_tool",
                resource_id="x",
                metric_name="call_rate",
                metric_value=2.0,
            )
        )
        assert result["reflexive"]["available"] is True
        # No baseline yet → evaluated=False with a reason.
        assert result["reflexive"]["evaluated"] is False
        assert "baseline" in result["reflexive"]["reason"].lower()

    def test_http_simulate_route_round_trips(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Route Test",
                    "owner_publisher_id": "acme",
                    "slug": "route-test",
                    "kind": "agent",
                },
            )
            resp = client.post(
                "/registry/clients/route-test/simulate",
                json={
                    "action": "call_tool",
                    "resource_id": "delete_user",
                    "consent_scope": "execute",
                },
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["verdict"] in {"allow", "deny", "review"}
            assert data["client"]["slug"] == "route-test"

    def test_http_simulate_route_validates_required_fields(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Validation",
                    "owner_publisher_id": "acme",
                    "slug": "validation",
                    "kind": "agent",
                },
            )
            # Missing action.
            resp = client.post(
                "/registry/clients/validation/simulate",
                json={"resource_id": "x"},
            )
            assert resp.status_code == 400
            # Missing resource_id.
            resp = client.post(
                "/registry/clients/validation/simulate",
                json={"action": "x"},
            )
            assert resp.status_code == 400
            # Non-numeric metric_value.
            resp = client.post(
                "/registry/clients/validation/simulate",
                json={
                    "action": "x",
                    "resource_id": "y",
                    "metric_value": "not-a-number",
                },
            )
            assert resp.status_code == 400

    def test_http_simulate_route_404_for_unknown_client(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            resp = client.post(
                "/registry/clients/missing/simulate",
                json={"action": "x", "resource_id": "y"},
            )
            assert resp.status_code == 404

    def test_http_simulate_route_blocks_unauthorized_callers(self):
        """With auth on, anonymous → 401, non-owner publisher → 403."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            # Admin creates a client owned by 'alice'.
            client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Alice Bot",
                    "owner_publisher_id": "alice",
                    "slug": "alice-bot",
                    "kind": "agent",
                },
            )

            # Anonymous: 401.
            client.cookies.clear()
            anon = client.post(
                "/registry/clients/alice-bot/simulate",
                json={"action": "x", "resource_id": "y"},
            )
            assert anon.status_code == 401

            # Publisher (not the owner): 403.
            client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            forbidden = client.post(
                "/registry/clients/alice-bot/simulate",
                json={"action": "x", "resource_id": "y"},
            )
            assert forbidden.status_code == 403


class TestRegistryClientActivity:
    """Iteration 12 — the activity projection composes per-actor
    ledger records + token ``last_used_at`` into the live-status
    block on the per-client detail page.

    Coverage:

    * never-seen client → ``status_label="never"``;
    * a synthetic ledger record makes the client ``"live"``;
    * graduations through ``recent`` / ``idle`` / ``dormant`` as the
      record's age increases;
    * ``top_resources`` orders by frequency descending;
    * ``hourly_buckets`` returns 24 buckets with offset-from-now
      semantics;
    * sanitized variant strips ``top_resources`` but keeps volumetric
      counts.
    """

    @staticmethod
    def _summarize(*, ledger_rows: list[Any], tokens: list[Any]) -> dict[str, Any]:
        # Direct call into the static helper; keeps tests fast and
        # avoids the orchestrator wiring the full ``get_client_governance``
        # path needs.
        return PureCipherRegistry._summarize_client_activity(
            ledger_rows=ledger_rows, tokens=tokens
        )

    @staticmethod
    def _row(timestamp: Any, *, resource_id: str = "tool_x") -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(timestamp=timestamp, resource_id=resource_id)

    def test_never_seen_yields_never_status(self):
        out = self._summarize(ledger_rows=[], tokens=[])
        assert out["status_label"] == "never"
        assert out["last_seen_at"] is None
        assert out["idle_seconds"] is None
        assert out["calls_last_hour"] == 0
        assert out["calls_last_24h"] == 0
        assert len(out["hourly_buckets"]) == 24
        assert all(b["count"] == 0 for b in out["hourly_buckets"])
        assert out["top_resources"] == []

    def test_recent_ledger_record_yields_live(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        out = self._summarize(
            ledger_rows=[self._row(now)],
            tokens=[],
        )
        assert out["status_label"] == "live"
        assert out["last_seen_source"] == "ledger"
        assert out["calls_last_hour"] == 1
        assert out["calls_last_24h"] == 1

    def test_status_graduates_with_age(self):
        """Walk a single record from 30s old → 30min old → 6h old →
        2 days old; status should step through live → recent → idle
        → dormant.
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # Thresholds (mirror _summarize_client_activity):
        #   live ≤ 60s; recent ≤ 15min; idle ≤ 24h; dormant > 24h.
        cases = [
            (timedelta(seconds=30), "live"),
            (timedelta(minutes=10), "recent"),
            (timedelta(hours=6), "idle"),
            (timedelta(days=2), "dormant"),
        ]
        for age, expected in cases:
            row = self._row(now - age)
            out = self._summarize(ledger_rows=[row], tokens=[])
            assert out["status_label"] == expected, (
                f"age={age} expected {expected} got {out['status_label']}"
            )

    def test_token_last_used_used_when_no_ledger_records(self):
        """A client whose first call was denied still appears
        active because its token authenticated. We fall back to
        the token's ``last_used_at`` to capture that signal.
        """
        from datetime import datetime, timezone
        from types import SimpleNamespace

        now_ts = datetime.now(timezone.utc).timestamp()
        token = SimpleNamespace(last_used_at=now_ts - 5)
        out = self._summarize(ledger_rows=[], tokens=[token])
        assert out["status_label"] == "live"
        assert out["last_seen_source"] == "token"

    def test_top_resources_orders_by_frequency(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        rows = (
            [self._row(now, resource_id="alpha") for _ in range(3)]
            + [self._row(now, resource_id="beta") for _ in range(5)]
            + [self._row(now, resource_id="gamma") for _ in range(1)]
        )
        out = self._summarize(ledger_rows=rows, tokens=[])
        ordered = [r["resource_id"] for r in out["top_resources"]]
        assert ordered == ["beta", "alpha", "gamma"]
        counts = {r["resource_id"]: r["count"] for r in out["top_resources"]}
        assert counts == {"beta": 5, "alpha": 3, "gamma": 1}

    def test_hourly_buckets_match_offset_semantics(self):
        """Bucket at offset 0 = current hour; offset 5 = 5h ago."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        rows = [
            self._row(now),  # offset 0
            self._row(now - timedelta(hours=5, minutes=10)),  # offset 5
            self._row(now - timedelta(hours=23, minutes=30)),  # offset 23
            self._row(now - timedelta(hours=30)),  # outside window
        ]
        out = self._summarize(ledger_rows=rows, tokens=[])
        buckets_by_offset = {
            b["hour_offset"]: b["count"] for b in out["hourly_buckets"]
        }
        assert buckets_by_offset[0] == 1
        assert buckets_by_offset[5] == 1
        assert buckets_by_offset[23] == 1
        # Records older than 24h must not leak into any bucket.
        assert sum(b["count"] for b in out["hourly_buckets"]) == 3

    def test_sanitize_strips_top_resources(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.register_client(
            display_name="Public Activity",
            owner_publisher_id="acme",
            slug="public-activity",
            kind="agent",
        )
        sanitized = registry.get_client_governance(
            "public-activity", sanitize_for_public=True
        )
        # Activity block survives but resource ids are dropped.
        assert "activity" in sanitized
        assert sanitized["activity"]["top_resources"] == []
        assert len(sanitized["activity"]["hourly_buckets"]) == 24
        assert "status_label" in sanitized["activity"]

    def test_governance_route_includes_activity(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        with TestClient(registry.http_app()) as client:
            client.post(
                "/registry/clients",
                json={
                    "display_name": "Activity Probe",
                    "owner_publisher_id": "acme",
                    "slug": "activity-probe",
                    "kind": "agent",
                },
            )
            resp = client.get("/registry/clients/activity-probe/governance")
            assert resp.status_code == 200
            body = resp.json()
            assert "activity" in body
            assert body["activity"]["status_label"] == "never"
            assert isinstance(body["activity"]["hourly_buckets"], list)


class TestRegistryOpenAPICredentials:
    """Iter 13.2 — HTTP CRUD for OpenAPI credentials.

    The store-level behaviour is covered by
    ``test_purecipher_openapi_store.py``; this class verifies the route
    layer: auth gating, role gating, payload validation, and that the
    sanitised public projection never leaks plaintext.
    """

    _SPEC_BODY = json.dumps(
        {
            "openapi": "3.0.0",
            "info": {"title": "Cred Demo", "version": "1.0.0"},
            "components": {
                "securitySchemes": {
                    "Bearer": {"type": "http", "scheme": "bearer"},
                }
            },
            "paths": {
                "/ping": {
                    "get": {
                        "operationId": "ping",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
    )

    def _ingest_source(self, client: TestClient) -> str:
        login = client.post(
            "/registry/login",
            json={"username": "publisher", "password": "publisher123"},
        )
        assert login.status_code == 200, login.text
        resp = client.post(
            "/registry/openapi/ingest",
            json={"text": self._SPEC_BODY, "title": "Cred Demo"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["source"]["source_id"]

    def test_routes_require_auth(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            resp = client.get("/registry/openapi/credentials")
            assert resp.status_code == 401

            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": "x",
                    "scheme_name": "y",
                    "scheme_kind": "http",
                    "secret": {"http_scheme": "bearer", "bearer_token": "z"},
                },
            )
            assert resp.status_code == 401

    def test_upsert_returns_sanitised_record(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            source_id = self._ingest_source(client)
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {
                        "http_scheme": "bearer",
                        "bearer_token": "secrettoken-XYZQ",
                    },
                    "label": "prod",
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            cred = body["credential"]
            # Plaintext must NOT appear on the wire.
            assert "secret" not in cred
            assert cred["secret_hint"] == "bearer …XYZQ"
            assert cred["scheme_kind"] == "http"
            assert cred["label"] == "prod"

    def test_list_returns_sanitised_records(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            source_id = self._ingest_source(client)
            client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {
                        "http_scheme": "bearer",
                        "bearer_token": "tok-AAAA",
                    },
                },
            )
            resp = client.get("/registry/openapi/credentials")
            assert resp.status_code == 200
            creds = resp.json()["credentials"]
            assert len(creds) == 1
            assert "secret" not in creds[0]
            assert creds[0]["secret_hint"] == "bearer …AAAA"

            # source_id filter narrows the list.
            filtered = client.get(
                f"/registry/openapi/credentials?source_id={source_id}"
            )
            assert filtered.status_code == 200
            assert len(filtered.json()["credentials"]) == 1

            other = client.get("/registry/openapi/credentials?source_id=does_not_exist")
            assert other.status_code == 200
            assert other.json()["credentials"] == []

    def test_delete_round_trip(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            source_id = self._ingest_source(client)
            up = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {
                        "http_scheme": "bearer",
                        "bearer_token": "tok-AAAA",
                    },
                },
            )
            cid = up.json()["credential"]["credential_id"]

            # Wrong id → 404.
            missing = client.delete("/registry/openapi/credentials/cred_does_not_exist")
            assert missing.status_code == 404

            # Right id → 200 + idempotent (second delete is 404).
            ok = client.delete(f"/registry/openapi/credentials/{cid}")
            assert ok.status_code == 200
            again = client.delete(f"/registry/openapi/credentials/{cid}")
            assert again.status_code == 404

    def test_upsert_rejects_unknown_source(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": "oas_does_not_exist",
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {
                        "http_scheme": "bearer",
                        "bearer_token": "tok-AAAA",
                    },
                },
            )
            assert resp.status_code == 404

    def test_upsert_validates_secret_payload(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            source_id = self._ingest_source(client)
            # Missing scheme_kind
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "secret": {"bearer_token": "x"},
                },
            )
            assert resp.status_code == 400

            # Bad scheme_kind
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "weirdo",
                    "secret": {"x": "y"},
                },
            )
            assert resp.status_code == 400

            # Empty secret
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {},
                },
            )
            assert resp.status_code == 400

            # http requires http_scheme
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "Bearer",
                    "scheme_kind": "http",
                    "secret": {"bearer_token": "tok"},
                },
            )
            assert resp.status_code == 400

            # apiKey requires api_key
            resp = client.post(
                "/registry/openapi/credentials",
                json={
                    "source_id": source_id,
                    "scheme_name": "ApiKey",
                    "scheme_kind": "apiKey",
                    "secret": {},
                },
            )
            assert resp.status_code == 400


class TestRegistryOpenAPIInvoke:
    """Iter 13.3 — HTTP /invoke route round-trips through the executor.

    Tests inject a ``MockTransport``-backed ``httpx.AsyncClient`` via
    ``registry._openapi_invoke_client`` so the route never hits the
    network. Each test asserts on the captured request to verify URL
    building, credential application, and tenant isolation all wire
    through correctly end-to-end.
    """

    _SPEC_BODY = json.dumps(
        {
            "openapi": "3.0.0",
            "servers": [{"url": "https://api.demo.example/v1"}],
            "components": {
                "securitySchemes": {"Bearer": {"type": "http", "scheme": "bearer"}},
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    }
                },
            },
            "security": [{"Bearer": []}],
            "paths": {
                "/pets/{petId}": {
                    "get": {
                        "operationId": "showPet",
                        "parameters": [
                            {
                                "name": "petId",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Pet"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
    )

    def _setup(
        self, registry: PureCipherRegistry, handler
    ) -> tuple[TestClient, str, str]:
        import httpx

        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = TestClient(registry.http_app())
        client.__enter__()
        login = client.post(
            "/registry/login",
            json={"username": "publisher", "password": "publisher123"},
        )
        assert login.status_code == 200, login.text
        ingest = client.post(
            "/registry/openapi/ingest",
            json={"text": self._SPEC_BODY, "title": "Demo"},
        )
        assert ingest.status_code == 200, ingest.text
        source_id = ingest.json()["source"]["source_id"]

        toolset = client.post(
            "/registry/openapi/toolset",
            json={
                "source_id": source_id,
                "title": "Demo Toolset",
                "selected_operations": ["showPet"],
            },
        )
        assert toolset.status_code == 200, toolset.text
        toolset_id = toolset.json()["toolset"]["toolset_id"]

        # Register the Bearer credential.
        cred = client.post(
            "/registry/openapi/credentials",
            json={
                "source_id": source_id,
                "scheme_name": "Bearer",
                "scheme_kind": "http",
                "secret": {
                    "http_scheme": "bearer",
                    "bearer_token": "tok-XYZQ",
                },
            },
        )
        assert cred.status_code == 200, cred.text
        return client, toolset_id, source_id

    def test_invoke_round_trip_uses_credential(self):
        import httpx

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"id": 7, "name": "Fido"},
            )

        client, toolset_id, _source_id = self._setup(registry, handler)
        try:
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/invoke",
                json={
                    "operation_key": "showPet",
                    "arguments": {"path": {"petId": "abc"}},
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status_code"] == 200
            assert body["body"] == {"id": 7, "name": "Fido"}
            assert body["validation_warnings"] == []

            # Captured upstream request: URL built + Authorization header set.
            assert len(captured) == 1
            assert str(captured[0].url) == "https://api.demo.example/v1/pets/abc"
            assert captured[0].headers.get("authorization") == "Bearer tok-XYZQ"
        finally:
            client.__exit__(None, None, None)

    def test_invoke_input_validation_returns_400(self):
        import httpx

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        client, toolset_id, _source_id = self._setup(registry, handler)
        try:
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/invoke",
                json={
                    "operation_key": "showPet",
                    "arguments": {"path": {}},
                },
            )
            assert resp.status_code == 400
            payload = resp.json()
            assert "issues" in payload
            assert any("petId" in m for m in payload["issues"])
        finally:
            client.__exit__(None, None, None)

    def test_invoke_unselected_operation_rejected(self):
        import httpx

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        client, toolset_id, _source_id = self._setup(registry, handler)
        try:
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/invoke",
                json={
                    "operation_key": "ghostOperation",
                    "arguments": {},
                },
            )
            assert resp.status_code == 400
            assert "not part of toolset" in resp.json()["error"]
        finally:
            client.__exit__(None, None, None)

    def test_invoke_unknown_toolset_returns_404(self):
        import httpx

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200))
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200
            resp = client.post(
                "/registry/openapi/toolset/toolset_does_not_exist/invoke",
                json={"operation_key": "x", "arguments": {}},
            )
            assert resp.status_code == 404

    def test_invoke_requires_auth(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            resp = client.post(
                "/registry/openapi/toolset/some_id/invoke",
                json={"operation_key": "x", "arguments": {}},
            )
            assert resp.status_code == 401

    def test_invoke_4xx_passthrough(self):
        import httpx

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                headers={"content-type": "application/json"},
                json={"error": "Pet not found"},
            )

        client, toolset_id, _source_id = self._setup(registry, handler)
        try:
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/invoke",
                json={
                    "operation_key": "showPet",
                    "arguments": {"path": {"petId": "missing"}},
                },
            )
            # Route returns 200 — the upstream's status code is in the body.
            assert resp.status_code == 200
            body = resp.json()
            assert body["status_code"] == 404
            assert body["body"] == {"error": "Pet not found"}
        finally:
            client.__exit__(None, None, None)


class TestIter14_11AdminDeregister:
    """Iter 14.11 — admins can permanently deregister a listing.

    The deregister flow:
    1. Admin POSTs to /registry/review/{listing_id}/deregister with reason.
    2. Backend transitions status PUBLISHED → DEREGISTERED, records the
       decision in the moderation log, and broadcasts a platform-wide
       notification visible to every role.
    3. Public catalog filters DEREGISTERED listings out (status check).
    4. Proxy mode rejects calls to deregistered listings with HTTP 410.
    """

    def _publish_listing(self, registry, *, tool_name: str = "demo-tool"):
        """Publish a listing through the moderation queue so it lands
        at status=PUBLISHED, ready to be deregistered."""
        result = registry.submit_tool(
            _manifest(tool_name=tool_name),
            display_name="Demo Tool",
            categories={ToolCategory.NETWORK},
            metadata=_runtime_metadata(),
            requested_level=CertificationLevel.BASIC,
        )
        assert result.accepted is True
        listing_id = result.listing.listing_id
        approved = registry.moderate_listing(
            listing_id, action_name="approve", reason="ready"
        )
        assert approved["listing"]["status"] == "published"
        return listing_id

    def test_admin_deregister_transitions_status_and_logs_reason(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        listing_id = self._publish_listing(registry)

        result = registry.moderate_listing(
            listing_id,
            action_name="deregister",
            reason="Author abandoned the package; security advisory open.",
        )
        assert result["listing"]["status"] == "deregistered"
        assert result["decision"]["action"] == "deregister"
        assert "abandoned" in result["decision"]["reason"].lower()

    def test_deregistered_listing_filtered_from_public_catalog(self):
        """The public ``/registry/tools`` listing only includes
        PUBLISHED entries. After deregister, the listing must
        disappear from that response."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        listing_id = self._publish_listing(registry, tool_name="public-demo")

        with TestClient(registry.http_app()) as client:
            before = client.get("/registry/tools").json()
            assert before["count"] == 1
            assert before["tools"][0]["tool_name"] == "public-demo"

            registry.moderate_listing(
                listing_id,
                action_name="deregister",
                reason="Test removal",
            )

            after = client.get("/registry/tools").json()
            assert after["count"] == 0

    def test_deregister_broadcasts_notification_to_every_role(self):
        """The notification body explicitly tells viewers the server
        is gone. Audiences include every role so even unauthenticated
        viewers see it on the notifications panel."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        listing_id = self._publish_listing(registry, tool_name="broadcast-test")

        registry.moderate_listing(
            listing_id,
            action_name="deregister",
            reason="Policy violation",
        )

        # Notifications visible to a viewer (lowest-trust role) — if
        # the deregister event is in there, every role above viewer
        # sees it too.
        feed = registry.get_registry_notifications(auth_enabled=True, role="viewer")
        items = feed["items"]
        assert any(it["event_kind"] == "listing_deregistered" for it in items), [
            it["event_kind"] for it in items
        ]
        deregister_item = next(
            it for it in items if it["event_kind"] == "listing_deregistered"
        )
        # Title makes the action obvious and includes the display name.
        assert "deregistered" in deregister_item["title"].lower()
        # Body tells curators their integrations need to migrate.
        assert "remove or migrate" in deregister_item["body"].lower()

    def test_route_requires_admin_role(self):
        """Non-admin sessions get 403 on the deregister route."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
            auth_settings=_auth_settings(),
        )
        listing_id = self._publish_listing(registry, tool_name="auth-test")

        with TestClient(registry.http_app()) as client:
            # Reviewer (not admin) — must be rejected. Reviewers can
            # approve/reject but not deregister.
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200
            r = client.post(
                f"/registry/review/{listing_id}/deregister",
                json={"reason": "I want to deregister"},
                headers={"Accept": "application/json"},
            )
            assert r.status_code == 403, r.text

    def test_admin_route_accepts_deregister(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
            auth_settings=_auth_settings(),
        )
        listing_id = self._publish_listing(registry, tool_name="happy-path")

        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            r = client.post(
                f"/registry/review/{listing_id}/deregister",
                json={"reason": "End-of-life by author"},
                headers={"Accept": "application/json"},
            )
            assert r.status_code == 200, r.text
            payload = r.json()
            assert payload["listing"]["status"] == "deregistered"
            # Moderator identity comes from the session, not the body.
            assert payload["decision"]["moderator_id"] == "admin"

    def test_deregistered_listing_serialized_status(self):
        """The listing detail endpoint returns ``status: 'deregistered'``
        so the frontend can render the right banner."""
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
        )
        self._publish_listing(registry, tool_name="serial-test")
        listing = registry._marketplace().get_by_name("serial-test")
        assert listing is not None
        registry.moderate_listing(
            listing.listing_id,
            action_name="deregister",
            reason="Test",
        )

        with TestClient(registry.http_app()) as client:
            r = client.get("/registry/tools/serial-test")
            # Public catalog filters it out.
            assert r.status_code == 404
            # But the moderation queue still shows it (admins audit).
            queue = client.get("/registry/review/submissions").json()
            sections = queue["sections"]
            assert "deregistered" in sections
            assert any(
                row["tool_name"] == "serial-test" for row in sections["deregistered"]
            )
