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
from purecipher import PureCipherRegistry, RegistryAuthSettings, ToolCategory

TEST_SIGNING_SECRET = "purecipher-registry-signing-secret-for-tests"
TEST_JWT_SECRET = "purecipher-registry-jwt-secret-for-tests"
TEST_USERS_JSON = json.dumps(
    [
        {
            "username": "viewer",
            "password": "viewer123",
            "role": "viewer",
            "display_name": "Registry Viewer",
        },
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


def _auth_settings() -> RegistryAuthSettings:
    return RegistryAuthSettings.from_values(
        enabled=True,
        issuer="purecipher-registry",
        jwt_secret=TEST_JWT_SECRET,
        users_json=TEST_USERS_JSON,
    )


class TestPureCipherRegistryAuth:
    def test_bootstrap_setup_creates_first_admin(self, tmp_path):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=RegistryAuthSettings.from_values(
                enabled=True,
                issuer="purecipher-registry",
                jwt_secret=TEST_JWT_SECRET,
            ),
            persistence_path=str(tmp_path / "registry.sqlite"),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            session = client.get("/registry/session")
            assert session.status_code == 200
            assert session.json()["bootstrap_required"] is True

            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 428

            setup = client.post(
                "/registry/setup",
                json={
                    "username": "admin",
                    "display_name": "Registry Admin",
                    "password": "admin456",
                },
            )
            assert setup.status_code == 201
            assert setup.json()["session"]["role"] == "admin"

            after_setup = client.get("/registry/session")
            assert after_setup.status_code == 200
            assert after_setup.json()["bootstrap_required"] is False
            assert after_setup.json()["session"]["username"] == "admin"

            second_setup = client.post(
                "/registry/setup",
                json={
                    "username": "another-admin",
                    "display_name": "Another Admin",
                    "password": "admin789",
                },
            )
            assert second_setup.status_code == 409

    def test_login_session_and_logout_round_trip(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login_page = client.get("/registry/login?next=/registry/review")

            assert login_page.status_code == 200
            assert "PureCipher Secured MCP Registry" in login_page.text
            assert "Sign In" in login_page.text

            login = client.post(
                "/registry/login",
                data={
                    "username": "reviewer",
                    "password": "reviewer123",
                    "next": "/registry/review",
                },
                follow_redirects=False,
            )

            assert login.status_code == 303
            assert login.headers["location"] == "/registry/review"

            session = client.get("/registry/session")
            assert session.status_code == 200
            session_payload = session.json()
            assert session_payload["auth_enabled"] is True
            assert session_payload["session"]["role"] == "reviewer"
            assert session_payload["session"]["can_review"] is True

            logout = client.get("/registry/logout", follow_redirects=False)
            assert logout.status_code == 303

            cleared = client.get("/registry/session")
            assert cleared.status_code == 200
            assert cleared.json()["session"] is None

    def test_notifications_require_login_when_auth_enabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            res = client.get("/registry/notifications")
            assert res.status_code == 401
            assert res.json().get("error") == "Authentication required."

    def test_preferences_require_login_when_auth_enabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            res = client.get("/registry/me/preferences")
            assert res.status_code == 401
            assert res.json().get("error") == "Authentication required."

            update = client.put(
                "/registry/me/preferences",
                json={"preferences": {"workspace": {"density": "compact"}}},
            )
            assert update.status_code == 401

    def test_preferences_persist_per_user(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200

            update = client.put(
                "/registry/me/preferences",
                json={
                    "preferences": {
                        "workspace": {"density": "compact"},
                        "publisher": {"defaultCertification": "advanced"},
                    }
                },
            )
            assert update.status_code == 200
            updated = update.json()
            assert updated["username"] == "publisher"
            assert updated["preferences"]["workspace"]["density"] == "compact"
            assert (
                updated["preferences"]["publisher"]["defaultCertification"]
                == "advanced"
            )
            assert updated["preferences"]["notifications"]["securityAlerts"] is True

            logout = client.get("/registry/logout", follow_redirects=False)
            assert logout.status_code == 303

        restarted = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        restarted_app = restarted.http_app()

        with TestClient(restarted_app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200

            prefs = client.get("/registry/me/preferences")
            assert prefs.status_code == 200
            assert prefs.json()["preferences"]["workspace"]["density"] == "compact"

    def test_account_activity_records_login_and_logout(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            unauthenticated = client.get("/registry/me/activity")
            assert unauthenticated.status_code == 401

            failed_login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "wrong"},
            )
            assert failed_login.status_code == 401

            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200

            activity = client.get("/registry/me/activity")
            assert activity.status_code == 200
            events = [item["event_kind"] for item in activity.json()["items"]]
            assert "login_success" in events
            assert "login_failed" in events

            logout = client.get("/registry/logout", follow_redirects=False)
            assert logout.status_code == 303

            login_again = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login_again.status_code == 200

            latest = client.get("/registry/me/activity")
            assert latest.status_code == 200
            latest_events = [item["event_kind"] for item in latest.json()["items"]]
            assert "logout" in latest_events

    def test_password_change_updates_writable_account_store(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200

            changed = client.post(
                "/registry/me/password",
                json={
                    "current_password": "publisher123",
                    "new_password": "publisher456",
                },
            )
            assert changed.status_code == 200

            old_login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert old_login.status_code == 401

            new_login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher456"},
            )
            assert new_login.status_code == 200

    def test_sessions_can_be_revoked(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200

            sessions = client.get("/registry/me/sessions")
            assert sessions.status_code == 200
            current_session_id = sessions.json()["current_session_id"]
            assert current_session_id

            revoked = client.delete(f"/registry/me/sessions/{current_session_id}")
            assert revoked.status_code == 200
            assert revoked.json()["ok"] is True

            session = client.get("/registry/session")
            assert session.status_code == 200
            assert session.json()["session"] is None

    def test_api_tokens_work_as_bearer_tokens_and_can_be_revoked(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            created = client.post(
                "/registry/me/tokens",
                json={"name": "CI token"},
            )
            assert created.status_code == 201
            token_payload = created.json()
            token = token_payload["token"]
            token_id = token_payload["token_record"]["token_id"]

            client.get("/registry/logout", follow_redirects=False)

            prefs = client.get(
                "/registry/me/preferences",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert prefs.status_code == 200
            assert prefs.json()["username"] == "admin"

            login_again = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login_again.status_code == 200

            revoked = client.delete(f"/registry/me/tokens/{token_id}")
            assert revoked.status_code == 200
            assert revoked.json()["ok"] is True

        with TestClient(app) as client:
            denied = client.get(
                "/registry/me/preferences",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert denied.status_code == 401

    def test_admin_can_manage_users_and_roles(self, tmp_path):
        db_path = str(tmp_path / "registry.sqlite")
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            persistence_path=db_path,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            viewer_login = client.post(
                "/registry/login",
                json={"username": "viewer", "password": "viewer123"},
            )
            assert viewer_login.status_code == 200

            viewer_denied = client.get("/registry/admin/users")
            assert viewer_denied.status_code == 403

            admin_login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert admin_login.status_code == 200

            users = client.get("/registry/admin/users")
            assert users.status_code == 200
            assert users.json()["counts"]["admin"] == 1

            created = client.post(
                "/registry/admin/users",
                json={
                    "username": "new-publisher",
                    "display_name": "New Publisher",
                    "role": "publisher",
                    "password": "publisher456",
                },
            )
            assert created.status_code == 201
            assert created.json()["user"]["role"] == "publisher"

            duplicate = client.post(
                "/registry/admin/users",
                json={
                    "username": "new-publisher",
                    "display_name": "Duplicate",
                    "role": "publisher",
                    "password": "publisher456",
                },
            )
            assert duplicate.status_code == 409

            updated = client.patch(
                "/registry/admin/users/new-publisher",
                json={"role": "reviewer", "display_name": "Review Publisher"},
            )
            assert updated.status_code == 200
            assert updated.json()["user"]["role"] == "reviewer"

            reset = client.post(
                "/registry/admin/users/new-publisher/password",
                json={"new_password": "publisher789"},
            )
            assert reset.status_code == 200

            disable = client.delete("/registry/admin/users/new-publisher")
            assert disable.status_code == 200
            assert disable.json()["user"]["active"] is False

            last_admin_demote = client.patch(
                "/registry/admin/users/admin",
                json={"role": "reviewer"},
            )
            assert last_admin_demote.status_code == 400
            assert "last active admin" in last_admin_demote.json()["error"]

        with TestClient(app) as client:
            old_password = client.post(
                "/registry/login",
                json={"username": "new-publisher", "password": "publisher456"},
            )
            assert old_password.status_code == 401

            disabled_login = client.post(
                "/registry/login",
                json={"username": "new-publisher", "password": "publisher789"},
            )
            assert disabled_login.status_code == 401

    def test_me_listings_require_login_when_auth_enabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            res = client.get("/registry/me/listings")
            assert res.status_code == 401
            assert res.json().get("error") == "Authentication required."

    def test_review_routes_require_auth_when_enabled(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.BASIC,
        )
        app = registry.http_app()

        with TestClient(app) as client:
            review_page = client.get("/registry/review", follow_redirects=False)
            assert review_page.status_code == 303
            assert review_page.headers["location"].startswith("/registry/login?next=")

            queue = client.get("/registry/review/submissions")
            assert queue.status_code == 401
            assert queue.json()["error"] == "Authentication required."

            submit = client.post(
                "/registry/submit",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network"],
                    "requested_level": "basic",
                },
            )
            assert submit.status_code == 401

            catalog = client.get("/registry", follow_redirects=False)
            assert catalog.status_code == 200
            assert "PureCipher Secured MCP Registry" in catalog.text

            publish_page = client.get("/registry/publish", follow_redirects=False)
            assert publish_page.status_code == 303
            assert publish_page.headers["location"].startswith("/registry/login?next=")

            preflight = client.post(
                "/registry/preflight",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network"],
                    "requested_level": "basic",
                },
            )
            assert preflight.status_code == 200
            assert preflight.json()["effective_certification_level"] == "basic"

    def test_publisher_can_submit_but_cannot_access_review_queue(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200
            assert login.json()["session"]["role"] == "publisher"

            submit = client.post(
                "/registry/submit",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network"],
                    "requested_level": "basic",
                },
            )
            assert submit.status_code == 201
            assert submit.json()["accepted"] is True

            queue = client.get("/registry/review/submissions")
            assert queue.status_code == 403
            assert queue.json()["error"] == "Reviewer or admin role required."

            publish_page = client.get("/registry/publish")
            assert publish_page.status_code == 200
            assert 'href="/registry/review"' not in publish_page.text

    def test_viewer_cannot_submit(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "viewer", "password": "viewer123"},
            )
            assert login.status_code == 200
            assert login.json()["session"]["role"] == "viewer"

            submit = client.post(
                "/registry/submit",
                json={
                    "manifest": _manifest().to_dict(),
                    "display_name": "Weather Lookup",
                    "categories": ["network"],
                    "requested_level": "basic",
                },
            )
            assert submit.status_code == 403
            assert (
                "Publisher, reviewer, or admin role required" in submit.json()["error"]
            )

    def test_policy_routes_require_reviewer_or_admin(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            unauthenticated = client.get("/registry/policy")
            assert unauthenticated.status_code == 401

            unauthenticated_export = client.get("/registry/policy/export")
            assert unauthenticated_export.status_code == 401

            unauthenticated_bundles = client.get("/registry/policy/bundles")
            assert unauthenticated_bundles.status_code == 401

            unauthenticated_packs = client.get("/registry/policy/packs")
            assert unauthenticated_packs.status_code == 401

            unauthenticated_promotions = client.get("/registry/policy/promotions")
            assert unauthenticated_promotions.status_code == 401

            unauthenticated_analytics = client.get("/registry/policy/analytics")
            assert unauthenticated_analytics.status_code == 401

            unauthenticated_migration = client.post(
                "/registry/policy/migrations/preview",
                json={"target_environment": "staging"},
            )
            assert unauthenticated_migration.status_code == 401

            unauthenticated_import = client.post(
                "/registry/policy/import",
                json={"snapshot": {"providers": []}},
            )
            assert unauthenticated_import.status_code == 401

            unauthenticated_capture = client.post(
                "/registry/policy/environments/staging/capture",
                json={"source_version_number": 1},
            )
            assert unauthenticated_capture.status_code == 401

            viewer_login = client.post(
                "/registry/login",
                json={"username": "viewer", "password": "viewer123"},
            )
            assert viewer_login.status_code == 200

            forbidden = client.get("/registry/policy")
            assert forbidden.status_code == 403

            forbidden_export = client.get("/registry/policy/export")
            assert forbidden_export.status_code == 403

            forbidden_bundles = client.get("/registry/policy/bundles")
            assert forbidden_bundles.status_code == 403

            forbidden_packs = client.get("/registry/policy/packs")
            assert forbidden_packs.status_code == 403

            forbidden_promotions = client.get("/registry/policy/promotions")
            assert forbidden_promotions.status_code == 403

            forbidden_analytics = client.get("/registry/policy/analytics")
            assert forbidden_analytics.status_code == 403

            forbidden_migration = client.post(
                "/registry/policy/migrations/preview",
                json={"target_environment": "staging"},
            )
            assert forbidden_migration.status_code == 403

            forbidden_import = client.post(
                "/registry/policy/import",
                json={"snapshot": {"providers": []}},
            )
            assert forbidden_import.status_code == 403

            forbidden_capture = client.post(
                "/registry/policy/environments/staging/capture",
                json={"source_version_number": 1},
            )
            assert forbidden_capture.status_code == 403

    def test_publisher_cannot_access_policy_routes(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200

            denied = client.get("/registry/policy")
            assert denied.status_code == 403

    def test_admin_can_access_policy_routes(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            policy = client.get("/registry/policy")
            assert policy.status_code == 200
            assert "policy" in policy.json()

    def test_reviewer_can_manage_policy_chain(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200

            status = client.get("/registry/policy")
            assert status.status_code == 200
            payload = status.json()
            assert payload["policy"]["provider_count"] == 1
            assert payload["versions"]["version_count"] == 1
            assert payload["bundles"]["count"] >= 1
            assert "packs" in payload
            assert payload["analytics"]["overview"]["provider_count"] == 1
            assert payload["environments"]["count"] >= 1
            assert "promotions" in payload

            bundles = client.get("/registry/policy/bundles")
            assert bundles.status_code == 200
            bundle_list = bundles.json()["bundles"]
            bundle = next(
                b for b in bundle_list if b.get("bundle_id") == "registry-balanced"
            )

            stage_bundle = client.post(
                f"/registry/policy/bundles/{bundle['bundle_id']}/stage",
                json={"description": "Stage bundle for review."},
            )
            assert stage_bundle.status_code == 200
            assert stage_bundle.json()["bundle"]["bundle_id"] == bundle["bundle_id"]
            assert stage_bundle.json()["proposal"]["action"] == "replace_chain"

            analytics = client.get("/registry/policy/analytics")
            assert analytics.status_code == 200
            assert "overview" in analytics.json()
            assert "history" in analytics.json()

            save_pack = client.post(
                "/registry/policy/packs",
                json={
                    "title": "Reviewer pack",
                    "source_version_number": 1,
                    "recommended_environments": ["development"],
                },
            )
            assert save_pack.status_code == 200
            pack_id = save_pack.json()["pack"]["pack_id"]

            stage_pack = client.post(f"/registry/policy/packs/{pack_id}/stage")
            assert stage_pack.status_code == 200

            migration_preview = client.post(
                "/registry/policy/migrations/preview",
                json={
                    "source_version_number": 1,
                    "target_environment": "production",
                },
            )
            assert migration_preview.status_code == 200
            assert (
                migration_preview.json()["environment"]["environment_id"]
                == "production"
            )
            assert "summary" in migration_preview.json()

            capture_environment = client.post(
                "/registry/policy/environments/development/capture",
                json={"source_version_number": 1},
            )
            assert capture_environment.status_code == 200

            promotions = client.get("/registry/policy/promotions")
            assert promotions.status_code == 200
            assert "promotions" in promotions.json()

            add_response = client.post(
                "/registry/policy/proposals",
                json={
                    "action": "add",
                    "config": {"type": "denylist", "denied": ["admin-*"]},
                    "description": "Protect admin tools",
                },
            )
            assert add_response.status_code == 200
            proposal_id = add_response.json()["proposal"]["proposal_id"]
            assert add_response.json()["proposal"]["status"] == "validated"

            proposal_queue = client.get("/registry/policy/proposals")
            assert proposal_queue.status_code == 200
            queue_payload = proposal_queue.json()
            assert queue_payload["pending_count"] == 2
            proposal_ids = {
                proposal["proposal_id"] for proposal in queue_payload["proposals"]
            }
            assert proposal_id in proposal_ids
            assert stage_bundle.json()["proposal"]["proposal_id"] in proposal_ids

            assign_response = client.post(
                f"/registry/policy/proposals/{proposal_id}/assign",
                json={
                    "reviewer": "reviewer",
                    "note": "Taking ownership before simulation.",
                },
            )
            assert assign_response.status_code == 200
            assert assign_response.json()["proposal"]["assigned_reviewer"] == "reviewer"

            simulate_response = client.post(
                f"/registry/policy/proposals/{proposal_id}/simulate",
            )
            assert simulate_response.status_code == 200
            assert simulate_response.json()["proposal"]["status"] == "simulated"

            approve_response = client.post(
                f"/registry/policy/proposals/{proposal_id}/approve",
                json={"note": "Ready for release."},
            )
            assert approve_response.status_code == 200
            assert approve_response.json()["proposal"]["status"] == "approved"

            deploy_response = client.post(
                f"/registry/policy/proposals/{proposal_id}/deploy",
                json={"note": "Applying to live chain."},
            )
            assert deploy_response.status_code == 200
            assert deploy_response.json()["policy"]["provider_count"] == 2
            trail = deploy_response.json()["proposal"]["decision_trail"]
            events = [item["event"] for item in trail]
            assert "assigned" in events
            assert events[-3:] == ["simulated", "approved", "deployed"]

            rollback_response = client.post(
                "/registry/policy/versions/rollback",
                json={
                    "version_number": 1,
                    "reason": "Back to baseline",
                },
            )
            assert rollback_response.status_code == 200
            assert rollback_response.json()["policy"]["provider_count"] == 1

    def test_reviewer_can_export_and_import_policy_json(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert login.status_code == 200

            export_live = client.get("/registry/policy/export")
            assert export_live.status_code == 200
            live_snapshot = export_live.json()["snapshot"]
            assert live_snapshot["format"] == "securemcp-policy-set/v1"
            assert len(live_snapshot["providers"]) == 1

            export_version = client.get("/registry/policy/export?version=1")
            assert export_version.status_code == 200
            assert export_version.json()["version_number"] == 1
            assert (
                export_version.json()["snapshot"]["providers"]
                == live_snapshot["providers"]
            )

            no_change_import = client.post(
                "/registry/policy/import",
                json={
                    "snapshot": live_snapshot,
                    "description_prefix": "Imported baseline",
                },
            )
            assert no_change_import.status_code == 200
            assert no_change_import.json()["status"] == "no_changes"

            imported_snapshot = json.loads(json.dumps(live_snapshot))
            imported_snapshot["providers"].append(
                {
                    "type": "denylist",
                    "policy_id": "imported-denylist",
                    "version": "1.0.0",
                    "denied": ["admin-*"],
                }
            )

            import_response = client.post(
                "/registry/policy/import",
                json={
                    "snapshot": imported_snapshot,
                    "description_prefix": "Imported denylist",
                },
            )
            assert import_response.status_code == 200
            import_payload = import_response.json()
            assert import_payload["status"] == "imported"
            assert import_payload["summary"]["created"] == 1
            proposal = import_payload["proposal"]
            assert proposal["action"] == "replace_chain"
            assert proposal["replacement_provider_count"] == 2
            assert proposal["description"].startswith("Imported denylist")

    def test_reviewer_can_approve_but_admin_is_required_to_suspend(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
            require_moderation=True,
        )
        result = registry.submit_tool(
            _manifest(),
            display_name="Weather Lookup",
            categories={ToolCategory.NETWORK, ToolCategory.UTILITY},
            requested_level=CertificationLevel.BASIC,
        )
        assert result.listing is not None

        app = registry.http_app()

        with TestClient(app) as client:
            reviewer_login = client.post(
                "/registry/login",
                json={"username": "reviewer", "password": "reviewer123"},
            )
            assert reviewer_login.status_code == 200

            queue = client.get("/registry/review/submissions")
            assert queue.status_code == 200
            pending_item = queue.json()["sections"]["pending_review"][0]
            assert "approve" in pending_item["available_actions"]
            assert "suspend" not in pending_item["available_actions"]

            approve = client.post(
                f"/registry/review/{result.listing.listing_id}/approve",
                json={"moderator_id": "reviewer-1", "reason": "Approved."},
            )
            assert approve.status_code == 200
            assert approve.json()["listing"]["status"] == "published"

            suspend_denied = client.post(
                f"/registry/review/{result.listing.listing_id}/suspend",
                json={"moderator_id": "reviewer-1", "reason": "No access."},
            )
            assert suspend_denied.status_code == 403
            assert suspend_denied.json()["error"] == "Admin role required."

            admin_login = client.post(
                "/registry/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert admin_login.status_code == 200

            suspend = client.post(
                f"/registry/review/{result.listing.listing_id}/suspend",
                json={"moderator_id": "admin-1", "reason": "Hold for review."},
            )
            assert suspend.status_code == 200
            assert suspend.json()["listing"]["status"] == "suspended"

    def test_login_api_rejects_invalid_credentials(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            response = client.post(
                "/registry/login",
                json={"username": "admin", "password": "wrong-password"},
            )

            assert response.status_code == 401
            assert response.json()["error"] == "Invalid username or password."
