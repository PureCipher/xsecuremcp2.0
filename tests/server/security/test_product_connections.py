"""Consumer secrets must never cross users, listings, or generic workspace routes."""

import json

from starlette.testclient import TestClient

from purecipher.product_connections import decrypt
from purecipher.product_schemas import PRODUCT_SCHEMAS
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


def test_product_forms_match_consumer_auth_not_publisher_oauth_secrets():
    assert len(PRODUCT_SCHEMAS) == 48
    for slug in [
        "google-gmail",
        "google-docs",
        "google-calendar",
        "google-tasks",
        "google-drive",
        "stripe",
        "apollo",
        "huggingface",
    ]:
        spec = PRODUCT_SCHEMAS[slug]
        assert spec["kind"] == "oauth" and spec["fields"] == []
        assert spec["audience"] == "consumer"
    assert any(
        f["key"] == "GRAFANA_API_KEY" for f in PRODUCT_SCHEMAS["grafana"]["fields"]
    )
    assert any(
        f["key"] == "MDB_MCP_CONNECTION_STRING" and f["type"] == "secret"
        for f in PRODUCT_SCHEMAS["mongodb"]["fields"]
    )
    assert any(
        f["key"] == "param:paths" for f in PRODUCT_SCHEMAS["filesystem"]["fields"]
    )


def test_encryption_redaction_owner_isolation_update_and_delete():
    app = registry()
    with TestClient(app.http_app()) as client:
        assert client.get("/registry/workspace/connections").status_code == 401
        login(client)
        response = client.post(
            "/registry/workspace/connections",
            json={
                "product": "grafana",
                "name": "My Grafana",
                "values": {
                    "GRAFANA_API_KEY": "fixture-private-key",
                    "param:url": "https://grafana.example.com",
                },
            },
        )
        assert response.status_code == 201, response.text
        item = response.json()
        assert "fixture-private-key" not in response.text
        assert item["secret_fields"] == ["GRAFANA_API_KEY"]
        stored = app._workspace.get(item["id"])
        assert "fixture-private-key" not in json.dumps(stored)
        assert decrypt(app, stored)["GRAFANA_API_KEY"] == "fixture-private-key"
        path = "/registry/workspace/connections/" + item["id"]
        # A different account cannot read, overwrite or remove it.
        login(client, "bob")
        assert client.get("/registry/workspace/connections").json()["connections"] == []
        assert client.put(path, json={**item, "values": {}}).status_code == 404
        assert client.delete(path).status_code == 404
        login(client)
        assert (
            client.put(
                "/registry/workspace/profiles/" + item["id"], json={}
            ).status_code
            == 404
        )
        assert (
            client.delete("/registry/workspace/profiles/" + item["id"]).status_code
            == 404
        )
        assert client.get("/registry/workspace").json()["profiles"] == []
        updated = client.put(
            path,
            json={
                **item,
                "values": {
                    "GRAFANA_API_KEY": "",
                    "param:url": "https://next.example.com",
                },
            },
        )
        assert updated.status_code == 200
        assert (
            decrypt(app, app._workspace.get(item["id"]))["GRAFANA_API_KEY"]
            == "fixture-private-key"
        )
        assert client.put(path, json=item).status_code == 409
        item = updated.json()
        updated = client.put(
            path, json={**item, "values": {}, "clear_secrets": ["GRAFANA_API_KEY"]}
        )
        assert updated.status_code == 200
        assert updated.json()["secret_fields"] == []
        assert updated.json()["runtime_ready"] is False
        assert client.delete(path).status_code == 200
        assert app._workspace.get(item["id"]) is None


def test_oauth_app_secrets_and_unknown_fields_rejected_for_consumers():
    app = registry()
    with TestClient(app.http_app()) as client:
        login(client)
        for values in [
            {"client_secret": "do-not-store"},
            {"PURECIPHER_GOOGLE_CLIENT_SECRET": "do-not-store"},
        ]:
            assert (
                client.post(
                    "/registry/workspace/connections",
                    json={"product": "google-gmail", "name": "Gmail", "values": values},
                ).status_code
                == 400
            )
        response = client.post(
            "/registry/workspace/connections",
            json={"product": "google-gmail", "name": "Gmail", "values": {}},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "authorization_pending"
        assert response.json()["runtime_ready"] is False
        for value in ["NaN", "Infinity", "not-a-number"]:
            assert (
                client.post(
                    "/registry/workspace/connections",
                    json={
                        "product": "clickhouse",
                        "name": "Database",
                        "values": {"param:port": value},
                    },
                ).status_code
                == 400
            )


def test_credentials_are_bound_to_the_encrypted_record_identity():
    app = registry()
    with TestClient(app.http_app()) as client:
        login(client)
        response = client.post(
            "/registry/workspace/connections",
            json={
                "product": "notion",
                "name": "Notion",
                "values": {"INTERNAL_INTEGRATION_TOKEN": "fixture"},
            },
        )
        record = app._workspace.get(response.json()["id"])
        record["owner"] = "bob"
        import pytest

        with pytest.raises(ValueError, match="identity mismatch"):
            decrypt(app, record)


def test_end_user_can_save_credentials_without_publisher_role():
    app = registry()
    with TestClient(app.http_app()) as client:
        assert (
            client.post(
                "/registry/register",
                json={"username": "consumer", "password": "fixture-long-password"},
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/registry/login",
                json={"username": "consumer", "password": "fixture-long-password"},
            ).status_code
            == 200
        )
        response = client.post(
            "/registry/workspace/connections",
            json={
                "product": "brave-search",
                "name": "My search",
                "values": {"BRAVE_API_KEY": "fixture-private"},
            },
        )
        assert response.status_code == 201
        login(client)
        assert client.get("/registry/workspace/connections").json()["connections"] == []
        assert (
            client.delete(
                "/registry/workspace/connections/" + response.json()["id"]
            ).status_code
            == 404
        )
