"""Catalog browsing must paginate after filtering and never leak private facets."""

import json

import pytest
from starlette.datastructures import QueryParams
from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus, ToolCategory
from purecipher import PureCipherRegistry
from purecipher.auth import RegistryAuthSettings
from purecipher.catalog_query import browse_catalog
from tests.server.security.test_purecipher_registry import (
    TEST_SIGNING_SECRET,
    _manifest,
)


def rows():
    return {
        "tools": [
            {
                "tool_name": "z",
                "display_name": "Zebra",
                "author": "alice",
                "status": "draft",
                "categories": ["database"],
                "description": "Query records",
                "tags": ["sql"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"tools": ["one"]},
            },
            {
                "tool_name": "a",
                "display_name": "Álpha",
                "author": "alice",
                "status": "published",
                "categories": ["search"],
                "description": "Find records",
                "tags": ["web"],
                "created_at": "2026-02-01T00:00:00+00:00",
                "metadata": {"tools": ["one", "two"]},
            },
            {
                "tool_name": "b",
                "display_name": "Beta",
                "author": "bob",
                "status": "rejected",
                "categories": ["database"],
                "description": "Query records",
                "tags": ["sql"],
                "created_at": "2026-03-01T00:00:00+00:00",
            },
        ]
    }


def test_search_is_case_and_accent_insensitive_and_includes_categories_and_publisher():
    assert browse_catalog(rows(), QueryParams("q=ALPHA+alice"))["total"] == 1
    assert browse_catalog(rows(), QueryParams("q=database+query"))["total"] == 2
    assert browse_catalog(rows(), QueryParams("q=doesnotexist"))["total"] == 0


def test_filtering_precedes_pagination_and_facets_are_from_authorized_input():
    result = browse_catalog(
        rows(), QueryParams("category=database&sort=name_asc&limit=1&offset=1")
    )
    assert [i["tool_name"] for i in result["tools"]] == ["z"]
    assert (
        result["total"] == 2
        and result["count"] == 1
        and result["unfiltered_count"] == 3
    )
    assert result["facets"]["categories"][0]["count"] == 2


@pytest.mark.parametrize(
    "sort,expected",
    [
        ("name_asc", ["a", "b", "z"]),
        ("name_desc", ["z", "b", "a"]),
        ("newest", ["b", "a", "z"]),
        ("tools", ["a", "z", "b"]),
        ("status", ["b", "z", "a"]),
    ],
)
def test_sort_orders(sort, expected):
    assert [
        i["tool_name"]
        for i in browse_catalog(rows(), QueryParams({"sort": sort}))["tools"]
    ] == expected


@pytest.mark.parametrize(
    "query",
    [
        "sort=invalid",
        "limit=no",
        "limit=0",
        "limit=201",
        "offset=-1",
        "offset=1000001",
        "category=invalid",
        "status=invalid",
        "q=" + "x" * 301,
    ],
)
def test_bad_queries_are_rejected(query):
    with pytest.raises(ValueError):
        browse_catalog(rows(), QueryParams(query))


def registry():
    return PureCipherRegistry(
        signing_secret=TEST_SIGNING_SECRET,
        auth_settings=RegistryAuthSettings.from_values(
            enabled=True,
            issuer="test",
            jwt_secret="catalog-query-secret-for-tests-only",
            cookie_secure=False,
            users_json=json.dumps(
                [
                    {
                        "username": "alice",
                        "password": "fixture-password",
                        "role": "publisher",
                    },
                    {
                        "username": "bob",
                        "password": "fixture-password",
                        "role": "publisher",
                    },
                ]
            ),
        ),
    )


def test_http_search_and_facets_cannot_reveal_other_publishers_drafts():
    app = registry()
    for owner, category in [
        ("alice", ToolCategory.SEARCH),
        ("bob", ToolCategory.DATABASE),
    ]:
        app._marketplace().publish(
            owner + "-draft",
            author=owner,
            version="1",
            display_name=owner.title(),
            categories={category},
            status=PublishStatus.DRAFT,
        )
    with TestClient(app.http_app()) as client:
        assert client.get("/registry/me/listings").status_code == 401
        public = client.get("/registry/tools?status=draft&author=bob").json()
        assert public["total"] == 0 and public["facets"]["categories"] == []
        assert (
            client.post(
                "/registry/login",
                json={"username": "alice", "password": "fixture-password"},
            ).status_code
            == 200
        )
        mine = client.get("/registry/me/listings?sort=name_asc").json()
        assert [i["tool_name"] for i in mine["tools"]] == ["alice-draft"]
        assert mine["facets"]["categories"] == [
            {"value": "search", "label": "Search", "count": 1}
        ]
        assert client.get("/registry/me/listings?author=bob").json()["total"] == 0
        assert client.get("/registry/me/listings?limit=bad").status_code == 400
        assert client.get("/registry/tools?category=invalid").status_code == 400
        assert "automation" in {
            c["value"] for c in client.get("/registry/categories").json()["categories"]
        }


def test_public_catalog_uses_all_matching_rows_before_applying_offset():
    app = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
    for name in ["zebra", "alpha", "beta"]:
        assert app.submit_tool(
            _manifest(tool_name=name),
            display_name=name.title(),
            categories={ToolCategory.SEARCH},
        ).accepted
    with TestClient(app.http_app()) as client:
        result = client.get(
            "/registry/tools?category=search&sort=name_asc&limit=1&offset=1"
        ).json()
        assert result["total"] == 3 and result["count"] == 1
        assert result["tools"][0]["tool_name"] == "beta"


def test_categories_and_product_titles_persist_without_changing_ids(registry_dsn):
    first = PureCipherRegistry(
        signing_secret=TEST_SIGNING_SECRET, persistence_path=registry_dsn
    )
    listing = first._marketplace().publish(
        "stable-id",
        author="alice",
        version="1",
        display_name="Notion",
        categories={ToolCategory.AUTOMATION, ToolCategory.PRODUCTIVITY},
        status=PublishStatus.DRAFT,
    )
    second = PureCipherRegistry(
        signing_secret=TEST_SIGNING_SECRET, persistence_path=registry_dsn
    )
    saved = second._marketplace().get_by_name("stable-id")
    assert (
        saved
        and saved.listing_id == listing.listing_id
        and saved.display_name == "Notion"
    )
    assert saved.categories == {ToolCategory.AUTOMATION, ToolCategory.PRODUCTIVITY}


def test_configuration_trust_and_transport_filters():
    payload = rows()
    a, b, c = payload["tools"]
    a["metadata"].update(
        configuration=["oauth"], server_type="remote", known_publisher=True
    )
    b["metadata"].update(configuration=["secrets"], server_type="remote")
    b["known_publisher"] = True
    c["metadata"] = {"configuration": ["none"], "server_type": "local"}
    result = browse_catalog(
        payload,
        QueryParams(
            "configuration=oauth&configuration=secrets&server_type=remote&trust=known"
        ),
    )
    assert [item["tool_name"] for item in result["tools"]] == ["a"]
    # A publisher-controlled metadata claim must never grant a trust badge.
    assert (
        browse_catalog(payload, QueryParams("configuration=oauth&trust=known"))["total"]
        == 0
    )
    assert browse_catalog(payload, QueryParams("configuration=none"))["total"] == 1
    assert browse_catalog(rows(), QueryParams("configuration=none"))["total"] == 0


@pytest.mark.parametrize(
    "query", ["configuration=unknown", "trust=certified", "server_type=invalid"]
)
def test_rejects_unknown_filter_values(query):
    with pytest.raises(ValueError):
        browse_catalog(rows(), QueryParams(query))


def test_reference_sort_menu_orders():
    payload = rows()
    payload["tools"][0]["install_count"] = 12
    assert [
        i["tool_name"]
        for i in browse_catalog(payload, QueryParams("sort=oldest"))["tools"]
    ] == ["z", "a", "b"]
    assert [
        i["tool_name"]
        for i in browse_catalog(payload, QueryParams("sort=popularity"))["tools"]
    ] == ["z", "a", "b"]
    assert [
        i["tool_name"]
        for i in browse_catalog(payload, QueryParams("sort=default"))["tools"]
    ] == ["a", "b", "z"]
