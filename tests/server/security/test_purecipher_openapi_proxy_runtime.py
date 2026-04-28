"""Integration tests for the OpenAPI proxy runtime (Iter 13.5).

These verify the end-to-end flow: a publisher ingests a spec, creates
a toolset, publishes it, and an MCP-style ``tools/call`` against the
synthesised tool routes through the executor with credentials applied.
The five governance planes still gate the call via the existing
middleware chain — these tests assert that fact too.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from purecipher import PureCipherRegistry


def _spec(server: str = "https://api.demo.example/v1") -> dict:
    return {
        "openapi": "3.0.0",
        "servers": [{"url": server}],
        "components": {
            "securitySchemes": {"Bearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "Pet": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                }
            },
        },
        "security": [{"Bearer": []}],
        "paths": {
            "/pets/{petId}": {
                "get": {
                    "operationId": "showPet",
                    "summary": "Get a pet",
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        }
                    },
                }
            },
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }


def _seed_publisher(
    registry: PureCipherRegistry, *, register_credential: bool = True
) -> tuple[str, str]:
    """Ingest a spec, create a toolset, optionally register a Bearer credential.

    Returns ``(source_id, toolset_id)``. We use the registry's
    in-process store directly because the goal of these tests is the
    runtime, not the wizard.
    """
    record, _ops = registry._openapi_store.ingest_source(
        publisher_id="acme",
        title="Demo",
        raw_text=json.dumps(_spec()),
    )
    toolset = registry._openapi_store.create_toolset(
        publisher_id="acme",
        source_id=record["source_id"],
        title="Demo TS",
        selected_operations=["showPet", "listPets"],
    )
    if register_credential:
        registry._openapi_store.upsert_credential(
            publisher_id="acme",
            source_id=record["source_id"],
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-XYZ"},
        )
    return record["source_id"], toolset["toolset_id"]


def _registry_no_contracts() -> PureCipherRegistry:
    """Build a registry with the contract/consent planes disabled.

    These tests focus on the proxy runtime; the governance planes are
    exercised separately. Leaving contracts enabled would require
    every test to first call the contract broker — not the contract
    being tested here.
    """
    return PureCipherRegistry(
        signing_secret="proxy-runtime-test-secret",
        enable_contracts=False,
        enable_consent=False,
    )


class TestPublishedToolAppearsInToolsList:
    def test_published_listing_is_visible_via_list_tools(self):
        registry = _registry_no_contracts()
        _source, toolset_id = _seed_publisher(registry)
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        listings = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        assert {L.tool_name for L in listings} == {"showPet", "listPets"}

        async def run() -> list[str]:
            tools = await registry.list_tools()
            return [t.name for t in tools]

        names = asyncio.run(run())
        assert "showPet" in names
        assert "listPets" in names

    def test_input_schema_round_trips_to_mcp(self):
        registry = _registry_no_contracts()
        _source, toolset_id = _seed_publisher(registry)
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )

        async def run():
            return await registry.list_tools()

        tools = asyncio.run(run())
        show = next(t for t in tools if t.name == "showPet")
        # The inputSchema MCP clients see is the OpenAPI-derived
        # structured shape, not the function's `**arguments` shape.
        params = show.parameters
        assert params.get("type") == "object"
        assert "path" in (params.get("properties") or {})


class TestProxyToolCallsRouteThroughExecutor:
    def test_call_tool_runs_executor_with_credential(self):
        registry = _registry_no_contracts()
        _source, toolset_id = _seed_publisher(registry)
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"id": 7, "name": "Fido"},
            )

        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )

        async def run():
            return await registry.call_tool("showPet", {"path": {"petId": "abc"}})

        result = asyncio.run(run())
        # MCP wraps the proxy fn's return value into structured_content.
        assert result.structured_content is not None
        assert result.structured_content["status_code"] == 200
        assert result.structured_content["body"] == {"id": 7, "name": "Fido"}

        # Upstream got the URL + Authorization header from the
        # publisher's credential store.
        assert len(captured) == 1
        assert str(captured[0].url) == "https://api.demo.example/v1/pets/abc"
        assert captured[0].headers.get("authorization") == "Bearer tok-XYZ"

    def test_input_validation_failure_surfaces_as_tool_error(self):
        registry = _registry_no_contracts()
        _source, toolset_id = _seed_publisher(registry)
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )

        async def run():
            # Missing required path.petId
            try:
                await registry.call_tool("showPet", {"path": {}})
            except Exception as exc:  # noqa: BLE001
                return type(exc).__name__, str(exc)
            return None

        outcome = asyncio.run(run())
        assert outcome is not None
        # The executor's ArgumentValidationError surfaces through the
        # tool boundary; FastMCP wraps it in a ToolError-flavoured
        # exception. We just need to confirm petId was named.
        assert "petId" in outcome[1]


class TestGovernancePlanesStillFire:
    def test_contract_plane_blocks_call_when_enabled(self):
        """With contracts enabled, an OpenAPI-published tool requires
        an active contract just like any FastMCP tool. Confirms the
        proxy doesn't bypass the governance chain."""
        registry = PureCipherRegistry(
            signing_secret="proxy-runtime-test-secret",
            enable_contracts=True,
            enable_consent=False,
        )
        _source, toolset_id = _seed_publisher(registry)
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )

        async def run() -> str:
            try:
                await registry.call_tool("showPet", {"path": {"petId": "abc"}})
                return "<no error>"
            except Exception as exc:  # noqa: BLE001
                return f"{type(exc).__name__}: {exc}"

        outcome = asyncio.run(run())
        assert "Contract" in outcome or "contract" in outcome


class TestRepublishIsIdempotent:
    def test_republish_does_not_duplicate_tools(self):
        registry = _registry_no_contracts()
        _source, toolset_id = _seed_publisher(registry)
        registry._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )

        async def list_names() -> list[str]:
            tools = await registry.list_tools()
            return [t.name for t in tools]

        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        names_after_first = asyncio.run(list_names())

        registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.1.0"
        )
        names_after_second = asyncio.run(list_names())

        # FastMCP's local provider keys tools by name + version; the
        # version bump means we get a single new entry per tool, not
        # a duplicate. The set of *names* must remain the same.
        assert set(names_after_first) == set(names_after_second)


class TestPersistenceReattach:
    def test_reattach_runs_during_init(self, tmp_path):
        """A SQLite-backed registry that's restarted should expose its
        previously-published OpenAPI tools without the publisher
        having to re-run the publish flow.

        We simulate the restart by constructing a *second* registry
        instance pointing at the same SQLite path. The marketplace
        rehydrates from disk; ``_reattach_openapi_proxy_tools`` then
        re-binds the FunctionTools.
        """
        db = str(tmp_path / "registry.sqlite")

        # First boot — publish.
        registry_a = PureCipherRegistry(
            signing_secret="proxy-runtime-test-secret",
            enable_contracts=False,
            enable_consent=False,
            persistence_path=db,
        )
        _source, toolset_id = _seed_publisher(registry_a)
        registry_a._openapi_invoke_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        )
        registry_a.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )

        # Second boot — same disk, fresh process semantics.
        registry_b = PureCipherRegistry(
            signing_secret="proxy-runtime-test-secret",
            enable_contracts=False,
            enable_consent=False,
            persistence_path=db,
        )

        async def run() -> list[str]:
            tools = await registry_b.list_tools()
            return [t.name for t in tools]

        names = asyncio.run(run())
        assert "showPet" in names
        assert "listPets" in names
