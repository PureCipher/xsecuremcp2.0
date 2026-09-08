import json

import pytest
from starlette.testclient import TestClient

from purecipher import PureCipherRegistry
from purecipher.auth import RegistryAuthSettings, RegistryRole

PASSWORD = "registration-fixture-password"


def app(dsn=None):
    return PureCipherRegistry(
        signing_secret="test-signing-secret-long-enough",
        persistence_path=dsn,
        auth_settings=RegistryAuthSettings.from_values(
            enabled=True,
            issuer="test",
            jwt_secret="test-jwt-secret-long-enough",
            cookie_secure=False,
            users_json=json.dumps(
                [
                    {"username": "admin", "password": PASSWORD, "role": "admin"},
                    {
                        "username": "publisher",
                        "password": PASSWORD,
                        "role": "publisher",
                    },
                ]
            ),
        ),
    )


def payload(role="viewer"):
    return dict(
        username="new-person",
        password=PASSWORD,
        display_name="New Person",
        email="person@example.test",
        requested_role=role,
        organization="Test organization",
        purpose="Evaluate tools",
        website="https://example.test",
        review_experience="Security reviews",
    )


def signin(c, username="admin"):
    return c.post("/registry/login", json={"username": username, "password": PASSWORD})


def decision(c, status="approved", role="viewer", revision=0, reason=""):
    return c.post(
        "/registry/admin/account-requests/new-person",
        json={"decision": status, "role": role, "revision": revision, "reason": reason},
    )


@pytest.mark.parametrize("role", ["viewer", "publisher", "reviewer"])
def test_approval_required_for_every_role(role):
    r = app()
    with TestClient(r.http_app()) as c:
        created = c.post("/registry/register", json=payload(role))
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "pending"
        assert signin(c, "new-person").status_code == 401
        assert c.get("/registry/workspace").status_code == 401
        assert c.get("/registry/admin/account-requests").status_code == 401
        assert not r._account_security.session_is_active("", username="new-person")
        with pytest.raises(ValueError):
            r._account_security.create_api_token(username="new-person", name="blocked")
        status = c.post(
            "/registry/registration/status",
            json={"username": "new-person", "password": PASSWORD},
        )
        assert (
            status.status_code == 200
            and status.json()["request"]["status"] == "pending"
        )
        assert "set-cookie" not in status.headers
        signin(c, "publisher")
        assert decision(c).status_code == 403
        signin(c)
        assert decision(c, role=role).status_code == 200
        assert decision(c, role=role).status_code == 400
        c.cookies.clear()
        assert signin(c, "new-person").status_code == 200
        assert c.get("/registry/session").json()["session"]["role"] == role


def test_information_reply_stale_decision_and_rejection():
    r = app()
    with TestClient(r.http_app()) as c:
        c.post("/registry/register", json=payload("reviewer"))
        signin(c)
        assert (
            decision(c, status="information_required", role="reviewer").status_code
            == 400
        )
        assert (
            decision(
                c,
                status="information_required",
                role="reviewer",
                reason="Confirm affiliation",
            ).status_code
            == 200
        )
        assert decision(c, role="reviewer").status_code == 400
        c.cookies.clear()
        credentials = {"username": "new-person", "password": PASSWORD}
        assert (
            c.post(
                "/registry/registration/status",
                json={**credentials, "reply": "Confirmed affiliation", "revision": 1},
            ).status_code
            == 200
        )
        assert c.get("/registry/workspace").status_code == 401
        signin(c)
        assert (
            decision(
                c,
                status="rejected",
                role="reviewer",
                revision=2,
                reason="Unable to verify affiliation",
            ).status_code
            == 200
        )
        c.cookies.clear()
        assert signin(c, "new-person").status_code == 401
        data = c.post("/registry/registration/status", json=credentials).json()[
            "request"
        ]
        assert data["status"] == "rejected" and len(data["history"]) == 3
        assert (
            c.post(
                "/registry/registration/status",
                json={**credentials, "reply": "retry", "revision": 3},
            ).status_code
            == 400
        )


def test_admin_escalation_and_missing_fields_rejected():
    with TestClient(app().http_app()) as c:
        assert c.post("/registry/register", json=payload("admin")).status_code == 400
        assert (
            c.post(
                "/registry/register", json={**payload(), "role": "admin"}
            ).status_code
            == 400
        )
        assert (
            c.post("/registry/register", json={**payload(), "email": ""}).status_code
            == 400
        )
        assert c.post("/registry/register", json=payload()).status_code == 201
        signin(c)
        assert decision(c, role="admin").status_code == 400
        assert decision(c, role="publisher").status_code == 400
        assert (
            decision(
                c, role="publisher", reason="Publisher role agreed with applicant"
            ).status_code
            == 200
        )


def test_password_reset_and_role_update_do_not_approve_and_suspension_revokes():
    r = app()
    s = r._account_security
    with TestClient(r.http_app()) as c:
        c.post("/registry/register", json=payload())
        s.reset_password(username="new-person", new_password=PASSWORD)
        s.update_account(
            username="new-person", role=RegistryRole.PUBLISHER, disabled=False
        )
        assert not s.account_is_approved("new-person")
        assert signin(c, "new-person").status_code == 401
        signin(c)
        assert decision(c).status_code == 200
        c.cookies.clear()
        signin(c, "new-person")
        token = s.create_api_token(username="new-person", name="fixture")["token"]
        s.update_account(username="new-person", disabled=True)
        assert c.get("/registry/workspace").status_code == 401
        assert s.authenticate_api_token(token) is None
        s.change_password(
            username="new-person", current_password=PASSWORD, new_password=PASSWORD
        )
        assert not s.account_is_approved("new-person")


def test_status_requires_credentials():
    with TestClient(app().http_app()) as c:
        c.post("/registry/register", json=payload())
        assert (
            c.post(
                "/registry/registration/status",
                json={"username": "new-person", "password": "wrong"},
            ).status_code
            == 401
        )
        assert c.get("/registry/registration/status").status_code == 405


def test_persistent_decisions_survive_restart(registry_dsn):
    first = app(registry_dsn)
    with TestClient(first.http_app()) as c:
        assert c.post("/registry/register", json=payload("reviewer")).status_code == 201
        signin(c)
        assert (
            decision(
                c, status="information_required", role="reviewer", reason="More details"
            ).status_code
            == 200
        )
    second = app(registry_dsn)
    data = second._account_security.registration_status("new-person", PASSWORD)
    assert data["status"] == "information_required" and len(data["history"]) == 1
    assert not second._account_security.account_is_approved("new-person")
    with TestClient(second.http_app()) as c:
        signin(c)
        assert decision(c, role="reviewer", revision=1).status_code == 200
    third = app(registry_dsn)
    assert (
        third._account_security.authenticate("new-person", PASSWORD).role
        == RegistryRole.REVIEWER
    )
    assert (
        len(
            third._account_security.registration_status("new-person", PASSWORD)[
                "history"
            ]
        )
        == 2
    )


def test_pending_account_cannot_use_preexisting_profile(monkeypatch):
    from types import SimpleNamespace

    from purecipher.workspace import allowed_profile_tools

    r = app()
    with TestClient(r.http_app()) as c:
        assert c.post("/registry/register", json=payload()).status_code == 201
    r._workspace.save(
        {
            "id": "profile-fixture",
            "kind": "profile",
            "owner": "new-person",
            "status": "active",
            "client_ids": ["client-fixture"],
            "servers": [],
        }
    )
    r._workspace.save({"id": "client-fixture", "kind": "client", "owner": "new-person"})
    monkeypatch.setattr("purecipher.workspace.profile_blockers", lambda *args: [])
    with pytest.raises(ValueError, match="owner is disabled"):
        allowed_profile_tools(
            r,
            "profile-fixture",
            SimpleNamespace(client_id="client-fixture", status="active"),
        )


def test_migration_chain_is_repeatable(tmp_path):
    import sqlite3

    from purecipher.db_migrations import migrate_registry_database

    target = str(tmp_path / "approval.sqlite")
    migrate_registry_database(target)
    migrate_registry_database(target)
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260908_0007",
        )
        assert "registration" in [
            row[1]
            for row in conn.execute("PRAGMA table_info(purecipher_registry_accounts)")
        ]
