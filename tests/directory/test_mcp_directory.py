from typing import Any, cast

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from purecipher.mcp_directory import (
    compare,
    fetch_all,
    mount_directory,
    normalize,
    probe,
    read_snapshot,
    save_snapshot,
)


def row(name="io.example/server", version="1"):
    return {
        "server": {
            "name": name,
            "version": version,
            "description": "Example",
            "remotes": [{"type": "streamable-http", "url": "https://example.com/mcp"}],
        }
    }


async def test_cursor_and_latest_filter():
    def handle(request):
        assert request.url.params["version"] == "latest"
        cursor = request.url.params.get("cursor")
        return httpx.Response(
            200,
            json={
                "servers": [row("io.example/second" if cursor else "io.example/first")],
                "metadata": {} if cursor else {"nextCursor": "opaque/+=="},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        items = await fetch_all(client)
    assert len(items) == 2


async def test_repeated_cursor_aborts_without_publishing(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot({"servers": ["previous"]}, path)

    def handle(request):
        return httpx.Response(
            200, json={"servers": [row()], "metadata": {"nextCursor": "again"}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="cursor"):
            await fetch_all(client)
    assert read_snapshot(path)["servers"] == ["previous"]


def test_all_connection_options_and_arguments_preserved():
    r = row()
    r["server"]["packages"] = [
        {
            "registryType": "npm",
            "identifier": "@example/server",
            "version": "1.2.3",
            "transport": {"type": "stdio"},
            "packageArguments": [{"value": "--read-only"}],
        }
    ]
    normalized = normalize(r)
    assert len(normalized["options"]) == 2
    assert normalized["options"][1]["onboard_reference"] is None
    assert normalized["raw"]["server"]["packages"][0]["packageArguments"]
    assert normalized["readiness"] == "not_tested"


def test_oci_version_not_dropped():
    r = row()
    r["server"]["packages"] = [
        {
            "registryType": "oci",
            "identifier": "ghcr.io/example/server",
            "version": "1.2",
            "transport": {"type": "stdio"},
        }
    ]
    assert (
        normalize(r)["options"][1]["onboard_reference"]
        == "docker:ghcr.io/example/server:1.2"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com/mcp",
        "https://example.com/mcp?api_key=x",
        "https://{tenant}.example.com/mcp",
    ],
)
def test_configured_or_unsafe_url_not_auto_connected(url):
    r = row()
    r["server"]["remotes"][0]["url"] = url
    assert normalize(r)["options"][0]["onboard_reference"] is None


async def test_credentials_and_inactive_servers_not_probed():
    r = row()
    r["server"]["remotes"][0]["headers"] = [
        {"name": "Authorization", "isSecret": True, "isRequired": True}
    ]
    item = normalize(r)
    assert (await probe(item))["status"] == "setup_required"
    item["upstream_status"] = "deleted"
    assert (await probe(item))["status"] == "upstream_inactive"


def test_delta_distinguishes_repo_candidate_from_identity():
    item = normalize(row())
    item["repository"] = "https://github.com/example/mono"
    baseline = [{"id": "legacy", "source": item["repository"]}]
    delta = compare([item], baseline, baseline_kind="legacy")
    assert not delta["exact_matches"]
    assert delta["repository_overlap_candidates"][0]["repository_candidates"] == [
        item["name"]
    ]
    baseline[0]["upstream_ref"] = {
        "channel": "http",
        "identifier": "https://example.com/mcp",
    }
    assert compare([item], baseline, baseline_kind="legacy")["exact_matches"] == [
        item["name"]
    ]


def test_directory_read_routes_paginate_and_hide_deleted(tmp_path, monkeypatch):
    target = tmp_path / "directory.json"
    monkeypatch.setenv("PURECIPHER_DIRECTORY_FILE", str(target))
    active = normalize(row())
    deleted = normalize(row("io.example/deleted"))
    deleted["upstream_status"] = "deleted"
    save_snapshot({"servers": [active, deleted], "synced_at": "today"}, target)

    class Registry:
        routes = []

        def custom_route(self, path, methods):
            def register(fn):
                self.routes.append(Route(path, fn, methods=methods))
                return fn

            return register

    registry = Registry()
    mount_directory(registry, "/registry")
    with TestClient(Starlette(routes=registry.routes)) as client:
        payload = client.get("/registry/directory?q=example&limit=1").json()
        assert payload["total"] == 1
        assert "raw" not in payload["servers"][0]
        assert client.get("/registry/directory?limit=0").status_code == 400
        assert client.get("/registry/directory/" + deleted["id"]).status_code == 404
        assert client.get("/registry/directory/" + active["id"]).json()["raw"] == row()
        assert client.post("/registry/directory", json={}).status_code == 405


async def test_transport_retry_and_cached_resume(tmp_path, monkeypatch):
    import purecipher.mcp_directory as directory

    calls = 0

    async def no_wait(_):
        pass

    monkeypatch.setattr(directory.asyncio, "sleep", no_wait)

    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadError("interrupted")
        return httpx.Response(200, json={"servers": [row()], "metadata": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        first = await fetch_all(client, tmp_path)
        resumed = await fetch_all(client, tmp_path)
    assert first == resumed and calls == 2


def test_declared_transport_survives_resolve_and_proxy(monkeypatch):
    import purecipher.curation.http_transport as transport
    from fastmcp.client.transports import SSETransport, StreamableHttpTransport
    from fastmcp.server.security.gateway.tool_marketplace import ToolListing
    from purecipher.curation.proxy_runtime import _build_client_factory
    from purecipher.curation.upstream import UpstreamFetcher, UpstreamResolutionError

    monkeypatch.setattr(transport, "client_factory", lambda *args: None)
    for declared, expected in [
        ("sse", SSETransport),
        ("streamable-http", StreamableHttpTransport),
    ]:
        preview = UpstreamFetcher().resolve(
            "https://example.com/custom-endpoint", http_transport=declared
        )
        client = _build_client_factory(ToolListing(upstream_ref=preview.upstream_ref))()
        assert isinstance(client.transport, expected)
    for invalid in ["stdio", ["sse"]]:
        with pytest.raises(UpstreamResolutionError):
            UpstreamFetcher().resolve(
                "https://example.com/mcp", http_transport=cast(Any, invalid)
            )
    with pytest.raises(UpstreamResolutionError):
        UpstreamFetcher().resolve("npm:example", http_transport="sse")


async def test_introspection_honors_transport_not_url_suffix(monkeypatch):
    import purecipher.curation.http_transport as transport
    import purecipher.curation.introspector as module
    from fastmcp.client.transports import SSETransport
    from purecipher.curation.upstream import UpstreamFetcher

    captured = []

    class FakeClient:
        def __init__(self, value):
            captured.append(value)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def list_tools(self):
            return []

        async def list_resources(self):
            return []

        async def list_prompts(self):
            return []

    monkeypatch.setattr(module, "Client", FakeClient)
    monkeypatch.setattr(transport, "client_factory", lambda *args: None)
    preview = UpstreamFetcher().resolve(
        "https://example.com/custom-endpoint", http_transport="sse"
    )
    await module.HTTPIntrospector().introspect(preview.upstream_ref)
    assert isinstance(captured[0], SSETransport)


def test_custom_registry_never_falls_back_to_public_npm():
    r = row()
    r["server"]["packages"] = [
        {
            "registryType": "npm",
            "registryBaseUrl": "https://private.example.test/npm",
            "identifier": "example",
            "version": "1",
            "transport": {"type": "stdio"},
        }
    ]
    assert normalize(r)["options"][1]["onboard_reference"] is None
    r["server"]["packages"][0]["registryBaseUrl"] = "https://registry.npmjs.org"
    r["server"]["packages"][0]["runtimeHint"] = "npx"
    assert normalize(r)["options"][1]["onboard_reference"] == "npm:example@1"
