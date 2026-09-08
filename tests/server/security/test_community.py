from types import SimpleNamespace

from starlette.datastructures import QueryParams
from starlette.testclient import TestClient

from fastmcp.server.security.storage.sqlite import SQLiteBackend
from purecipher.catalog_query import browse_catalog
from purecipher.community import client_counts, refresh
from tests.server.security.test_release_candidates import setup
from tests.server.security.test_workspace_profiles import login


def test_rating_identity_upsert_persistence_and_public_projection(
    tmp_path, monkeypatch
):
    registry, key = setup()
    mp = registry._marketplace()
    mp._backend = SQLiteBackend(str(tmp_path / "ratings.db"))
    endpoint = "/registry/tools/weather-lookup/ratings"
    with TestClient(registry.http_app()) as client:
        assert client.put(endpoint, json={"rating": 5}).status_code == 401
        login(client, "alice")
        assert client.put(endpoint, json={"rating": 5}).status_code == 403
        login(client, "bob")
        for rating in [0, 6, True, "5"]:
            assert client.put(endpoint, json={"rating": rating}).status_code == 400
        assert (
            client.put(
                endpoint,
                json={"rating": 5, "body": "Good tools", "reviewer_id": "alice"},
            ).status_code
            == 200
        )
        result = client.put(
            endpoint, json={"rating": 3, "body": "Updated feedback"}
        ).json()
        assert result["review_count"] == 1 and result["average_rating"] == 3
        assert result["mine"]["body"] == "Updated feedback"
        assert "reviewer_id" not in result["reviews"][0]
        assert mp.get(key).reviews[0].reviewer_id == "bob"
        mp.get(key).reviews = []
        refresh(registry)
        assert mp.get(key).average_rating == 3 and mp.get(key).review_count == 1
        monkeypatch.setattr(
            mp._backend,
            "append_tool_review",
            lambda *args: (_ for _ in ()).throw(RuntimeError("disk failed")),
        )
        assert client.put(endpoint, json={"rating": 1}).status_code == 503
        assert mp.get(key).average_rating == 3
        assert "release_summary" not in registry.get_verified_tool("weather-lookup")


def test_update_filters_count_each_listing_once():
    payload = {
        "tools": [
            {
                "tool_name": "a",
                "status": "published",
                "release_summary": {"status": "pending_review"},
            },
            {
                "tool_name": "b",
                "status": "published",
                "release_summary": {"status": "changes_requested"},
            },
            {"tool_name": "c", "status": "pending_review"},
            {
                "tool_name": "d",
                "status": "published",
                "release_summary": {"status": "approved"},
            },
        ]
    }
    result = browse_catalog(payload, QueryParams("workspace_status=in_review&limit=1"))
    assert result["total"] == 2 and len(result["tools"]) == 1
    assert (
        next(
            x["count"]
            for x in result["facets"]["workspace"]
            if x["value"] == "in_review"
        )
        == 2
    )
    assert (
        browse_catalog(payload, QueryParams("workspace_status=needs_attention"))[
            "tools"
        ][0]["tool_name"]
        == "b"
    )


def test_client_counts_deduplicate_and_exclude_inactive_or_unselected():
    profiles = [
        {
            "status": "active",
            "client_ids": ["one", "two"],
            "servers": [
                {"listing_id": "a", "tools": ["read"], "client_tools": {"two": []}}
            ],
        },
        {
            "status": "active",
            "client_ids": ["one"],
            "servers": [{"listing_id": "a", "tools": ["read"]}],
        },
        {
            "status": "inactive",
            "client_ids": ["two"],
            "servers": [{"listing_id": "a", "tools": ["read"]}],
        },
    ]
    registry = SimpleNamespace(
        _workspace=SimpleNamespace(list_kind=lambda kind: profiles),
        _client_store=SimpleNamespace(
            get_client=lambda key: SimpleNamespace(status="active")
        ),
    )
    assert client_counts(registry) == {"a": 1}
