from starlette.testclient import TestClient

from purecipher.auth import RegistryRole
from tests.server.security.test_account_registration import app, signin


def exercise(registry):
    registry.record_registry_notification(
        event_kind="listing_published",
        title="Published",
        body="Test",
        audiences=("publisher",),
    )
    registry.record_registry_notification(
        event_kind="security_alert",
        title="Admin only",
        body="Test",
        audiences=("admin",),
    )
    with TestClient(registry.http_app()) as c:
        assert c.get("/registry/notifications").status_code == 401
        signin(c, "publisher")
        first = c.get("/registry/notifications").json()
        assert first["unread_count"] == 1
        assert first["items"][0]["read"] is False
        assert c.get("/registry/notifications").json()["unread_count"] == 1
        assert c.post("/registry/notifications", json={"id": "bad"}).status_code == 400
        assert (
            c.post(
                "/registry/notifications", json={"id": first["items"][0]["id"]}
            ).json()["unread_count"]
            == 0
        )
        registry.record_registry_notification(
            event_kind="listing_updated",
            title="Later",
            body="Test",
            audiences=("publisher",),
        )
        assert (
            c.post(
                "/registry/notifications",
                json={"all": True, "through_id": first["through_id"]},
            ).json()["unread_count"]
            == 1
        )
        signin(c)
        admin = c.get("/registry/notifications").json()
        assert admin["unread_count"] == 1 and admin["items"][0]["title"] == "Admin only"
        assert (
            c.post(
                "/registry/notifications", json={"id": first["items"][0]["id"]}
            ).json()["unread_count"]
            == 1
        )
        signin(c, "publisher")
        current = c.get("/registry/notifications").json()
        assert (
            c.post(
                "/registry/notifications",
                json={"all": True, "through_id": current["through_id"]},
            ).json()["unread_count"]
            == 0
        )
    return registry


def test_inbox_per_account_explicit_read_and_snapshot_boundary():
    exercise(app())


def test_postgres_read_state_survives_new_registry(registry_dsn):
    exercise(app(registry_dsn))
    with TestClient(app(registry_dsn).http_app()) as c:
        signin(c, "publisher")
        assert c.get("/registry/notifications").json()["unread_count"] == 0
        signin(c)
        assert c.get("/registry/notifications").json()["unread_count"] == 1


def test_preferences_and_same_role_account_isolation():
    r = app()
    r._account_security.create_account(
        username="second",
        password="registration-fixture-password",
        role=RegistryRole.PUBLISHER,
        display_name="Second",
    )
    r.record_registry_notification(
        event_kind="listing_published",
        title="Published",
        body="Test",
        audiences=("publisher",),
    )
    with TestClient(r.http_app()) as c:
        signin(c, "publisher")
        d = c.get("/registry/notifications").json()
        c.post("/registry/notifications", json={"id": d["items"][0]["id"]})
        signin(c, "second")
        assert c.get("/registry/notifications").json()["unread_count"] == 1
        r._user_preferences.set("second", {"notifications": {"publishUpdates": False}})
        assert c.get("/registry/notifications").json()["unread_count"] == 0
