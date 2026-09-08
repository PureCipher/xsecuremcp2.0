import pytest
from starlette.testclient import TestClient

from tests.server.security.test_account_registration import (
    PASSWORD,
    app,
    decision,
    payload,
    signin,
)


def test_suspend_restore_and_permanent_delete():
    registry = app()
    store = registry._account_security
    with TestClient(registry.http_app()) as client:
        assert client.post("/registry/register", json=payload()).status_code == 201
        signin(client)
        assert decision(client).status_code == 200
        store.create_api_token(username="new-person", name="test")
        assert (
            client.patch(
                "/registry/admin/users/new-person", json={"disabled": True}
            ).status_code
            == 200
        )
        assert not store.account_is_approved("new-person")
        assert (
            client.patch(
                "/registry/admin/users/new-person", json={"disabled": False}
            ).status_code
            == 200
        )
        assert store.account_is_approved("new-person")
        deleted = client.delete("/registry/admin/users/new-person")
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["user"]["registration"]["status"] == "deleted"
        assert not store.account_is_approved("new-person")
        assert store.registration_status("new-person", PASSWORD) is None
        assert store.update_account(username="new-person", disabled=False) is None
        assert (
            store.reset_password(username="new-person", new_password=PASSWORD) is False
        )
        assert client.post("/registry/register", json=payload()).status_code == 400
        assert client.delete("/registry/admin/users/admin").status_code == 400
        assert store.account_is_approved("admin")
        history = next(
            a for a in store.list_accounts() if a["username"] == "new-person"
        )["registration"]["history"]
        assert history[-1]["status"] == "deleted"
        assert history[-1]["actor"] == "admin"
        client.cookies.clear()
        assert signin(client, "new-person").status_code == 401
        with pytest.raises(ValueError):
            store.create_api_token(username="new-person", name="blocked")


def test_delete_requires_admin():
    registry = app()
    with TestClient(registry.http_app()) as client:
        assert client.delete("/registry/admin/users/publisher").status_code == 401
        signin(client, "publisher")
        assert client.delete("/registry/admin/users/admin").status_code == 403
