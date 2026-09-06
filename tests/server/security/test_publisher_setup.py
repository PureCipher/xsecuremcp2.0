"""Private setup survives restarts without changing a listing's runtime or status."""

import json

from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import (
    PublishStatus,
    ToolMarketplace,
)
from fastmcp.server.security.storage.sqlite import SQLiteBackend
from tests.server.security.test_purecipher_catalog_query import registry


def test_private_setup_persistence_and_public_exclusion(tmp_path):
    backend = SQLiteBackend(str(tmp_path / "setup.db"))
    market = ToolMarketplace(backend=backend)
    listing = market.publish(
        "saved", author="alice", version="1", status=PublishStatus.DRAFT
    )
    setup = {"runtimeText": '{"endpoint":"https://private.example/mcp"}'}
    market.save_publisher_setup(listing, setup)
    restored = ToolMarketplace(backend=backend).get(listing.listing_id)
    assert restored is not None
    assert restored.publisher_setup == setup
    assert restored.status == PublishStatus.DRAFT
    assert "publisher_setup" not in restored.to_dict()
    assert "private.example" not in json.dumps(restored.to_dict())
    backend.close()


def test_setup_endpoint_is_owner_scoped_and_does_not_publish(tmp_path, monkeypatch):
    app = registry()
    market = app._marketplace()
    market._backend = SQLiteBackend(str(tmp_path / "route.db"))
    own = market.publish(
        "saved", author="alice", version="1", status=PublishStatus.DRAFT
    )
    other = market.publish(
        "other", author="bob", version="1", status=PublishStatus.DRAFT
    )
    body = {
        "displayName": "Saved",
        "categories": "search",
        "manifestText": '{"tool_name":"saved"}',
        "runtimeText": "{}",
    }
    url = f"/registry/me/listings/{own.listing_id}/setup"
    with TestClient(app.http_app()) as client:
        assert client.put(url, json=body).status_code == 401
        client.post(
            "/registry/login",
            json={"username": "alice", "password": "fixture-password"},
        )
        assert (
            client.get(f"/registry/me/listings/{other.listing_id}/setup").status_code
            == 404
        )
        assert (
            client.put(
                f"/registry/me/listings/{other.listing_id}/setup", json=body
            ).status_code
            == 404
        )
        assert (
            client.put(
                url, json={**body, "manifestText": '{"tool_name":"renamed"}'}
            ).status_code
            == 400
        )
        assert client.put(url, json=body).status_code == 200
        assert client.get(url).json()["setup"]["displayName"] == "Saved"
        assert own.status == PublishStatus.DRAFT and own.attestation is None
        assert "publisher_setup" not in client.get("/registry/me/listings").text
        own.status = PublishStatus.PUBLISHED
        assert client.put(url, json=body).status_code == 409
        own.status = PublishStatus.DRAFT

        def fail(*args):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(market._backend, "save_tool_listing", fail)
        assert (
            client.put(url, json={**body, "displayName": "Unsaved"}).status_code == 503
        )
        assert own.publisher_setup["displayName"] == "Saved"
    market._backend.close()
