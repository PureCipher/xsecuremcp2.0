import json

from starlette.testclient import TestClient

from tests.server.security.test_purecipher_catalog_query import registry


def login(client, username="alice"):
    response = client.post(
        "/registry/login", json={"username": username, "password": "fixture-password"}
    )
    assert response.status_code == 200


def test_drafts_are_private_encrypted_and_revision_checked():
    app = registry()
    path = "/registry/workspace/publisher-drafts"
    with TestClient(app.http_app()) as client:
        assert client.get(path).status_code == 401
        login(client)
        body = {
            "name": "Unfinished server",
            "form": {
                "manifestText": "{unfinished",
                "mcpWizardDescription": "private draft marker",
            },
        }
        created = client.post(path, json=body)
        assert created.status_code == 201
        item = created.json()
        key = item["id"]
        assert "private draft marker" not in json.dumps(app._workspace.get(key))
        assert client.get(path + "/" + key).json()["form"] == body["form"]
        assert "form" not in client.get(path).json()["drafts"][0]
        assert client.get("/registry/tools").json()["total"] == 0
        updated = client.put(path + "/" + key, json={**body, "revision": 1})
        assert updated.status_code == 200 and updated.json()["revision"] == 2
        assert (
            client.put(path + "/" + key, json={**body, "revision": 1}).status_code
            == 409
        )
        login(client, "bob")
        assert client.get(path).json()["drafts"] == []
        for method in (client.get, client.delete):
            assert method(path + "/" + key).status_code == 404
        assert (
            client.put(path + "/" + key, json={**body, "revision": 2}).status_code
            == 404
        )
        login(client)
        assert client.get(path + "/" + key).json()["revision"] == 2
        assert client.delete(path + "/" + key).status_code == 200
        assert client.get(path).json()["drafts"] == []


def test_drafts_reject_nonpublisher_invalid_source_and_oversize():
    app = registry()
    path = "/registry/workspace/publisher-drafts"
    with TestClient(app.http_app()) as client:
        assert client.post(
            "/registry/register",
            json={
                "username": "viewer-test",
                "password": "long-fixture-password",
                "display_name": "Viewer",
            },
        ).status_code in (200, 201)
        assert (
            client.post(
                "/registry/login",
                json={"username": "viewer-test", "password": "long-fixture-password"},
            ).status_code
            == 200
        )
        assert client.post(path, json={"form": {}}).status_code == 403
        login(client)
        assert (
            client.post(
                path, json={"form": {}, "source_listing_id": "missing"}
            ).status_code
            == 404
        )
        assert client.post(path, json={"form": "wrong"}).status_code == 400
        assert (
            client.post(path, json={"form": {"text": "x" * 200_001}}).status_code == 400
        )
