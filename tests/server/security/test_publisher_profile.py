"""Publisher self-service identity, isolation, and persistence contracts."""

import pytest
from starlette.testclient import TestClient

from purecipher.publisher_profile import profile_key
from purecipher.workspace import WorkspaceStore
from tests.server.security.test_publisher_drafts import login
from tests.server.security.test_purecipher_catalog_query import registry

PATH = "/registry/workspace/publisher-profile"
DETAILS = {
    "display_name": "Alice Labs",
    "description": "Secure tools for teams.",
    "website": "https://example.com/about",
    "revision": 0,
}


def test_profile_updates_public_directory_without_changing_account_or_ownership():
    app = registry()
    with TestClient(app.http_app()) as client:
        assert client.get(PATH).status_code == 401
        assert client.put(PATH, json=DETAILS).status_code == 401
        login(client)
        assert client.get(PATH).json()["revision"] == 0
        account_before = app._account_security._get_account("alice")
        response = client.put(PATH, json=DETAILS)
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 1
        assert client.get(PATH).json() == response.json()
        public = app.get_publisher_profile("alice")
        for field in ("display_name", "description", "website"):
            assert public[field] == DETAILS[field]
        assert public["publisher_id"] == "alice"
        assert public["listings"] == []
        assert "owner" not in public and "revision" not in public
        summary = next(
            p
            for p in app.list_publishers()["publishers"]
            if p["publisher_id"] == "alice"
        )
        assert summary["display_name"] == "Alice Labs"
        assert app._account_security._get_account("alice") == account_before
        assert client.put(PATH, json=DETAILS).status_code == 409
        login(client, "bob")
        assert client.get(PATH).json()["display_name"] == "bob"
        assert client.put(PATH, json={**DETAILS, "owner": "alice"}).status_code == 400
        assert (
            client.put(PATH, json={**DETAILS, "display_name": "Bob Labs"}).status_code
            == 200
        )
        assert app.get_publisher_profile("alice")["display_name"] == "Alice Labs"
        login(client)
        cleared = client.put(
            PATH,
            json={
                "display_name": "  New Alice  ",
                "description": "",
                "website": "",
                "revision": 1,
            },
        )
        assert cleared.status_code == 200
        assert app.get_publisher_profile("alice")["display_name"] == "New Alice"
        assert app.get_publisher_profile("alice")["website"] == ""
        assert app._workspace.list("alice", "profile") == []


@pytest.mark.parametrize(
    "change",
    [
        {"display_name": " "},
        {"display_name": "x" * 121},
        {"description": "x" * 2001},
        {"website": "javascript:alert(1)"},
        {"website": "https://user:secret@example.com"},
        {"website": "https://example.com:bad"},
        {"website": "https://exa mple.com"},
        {"website": "//example.com"},
        {"role": "admin"},
        {"publisher_id": "bob"},
        {"display_name": None},
        {"revision": True},
        {"revision": -1},
    ],
)
def test_invalid_profile_does_not_save(change):
    app = registry()
    with TestClient(app.http_app()) as client:
        login(client)
        assert client.put(PATH, json={**DETAILS, **change}).status_code == 400
        assert app._workspace.list_kind("publisher-profile") == []


def test_viewers_cannot_edit_or_read_publisher_settings():
    app = registry()
    with TestClient(app.http_app()) as client:
        client.post(
            "/registry/register",
            json={
                "username": "viewer-test",
                "password": "long-fixture-password",
                "display_name": "Viewer",
            },
        )
        client.post(
            "/registry/login",
            json={"username": "viewer-test", "password": "long-fixture-password"},
        )
        assert client.get(PATH).status_code == 403
        assert client.put(PATH, json=DETAILS).status_code == 403


def test_publisher_profile_persists_and_detects_database_conflicts(registry_dsn):
    app = registry()
    app._workspace = WorkspaceStore(registry_dsn)
    with TestClient(app.http_app()) as client:
        login(client)
        assert client.put(PATH, json=DETAILS).status_code == 200
        app._workspace = WorkspaceStore(registry_dsn)
        assert client.get(PATH).json()["description"] == DETAILS["description"]
        assert app.get_publisher_profile("alice")["website"] == DETAILS["website"]
        assert client.put(PATH, json=DETAILS).status_code == 409
        saved = app._workspace.get(profile_key("alice"))
        assert saved["owner"] == "alice"
        assert saved["revision"] == 1


@pytest.mark.parametrize("role", ["admin", "reviewer", "viewer"])
def test_other_roles_cannot_use_publisher_editor(monkeypatch, role):
    from purecipher.auth import RegistryRole, RegistrySession

    app = registry()
    session = RegistrySession(
        username="alice", role=RegistryRole(role), display_name="Alice", expires_at=""
    )
    monkeypatch.setattr(app, "_session_from_request", lambda request: session)
    with TestClient(app.http_app()) as client:
        assert client.get(PATH).status_code == 403
        assert client.put(PATH, json=DETAILS).status_code == 403


def test_concurrent_first_save_returns_conflict(monkeypatch):
    from psycopg.errors import UniqueViolation

    app = registry()

    def racing_save(*args, **kwargs):
        raise UniqueViolation("Concurrent profile creation")

    monkeypatch.setattr(app._workspace, "save", racing_save)
    with TestClient(app.http_app()) as client:
        login(client)
        assert client.put(PATH, json=DETAILS).status_code == 409
