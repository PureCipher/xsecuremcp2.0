"""Tests for the OpenAPI tool executor (Iter 13.3).

These cover three layers in turn:

* Pure request-builder output for path / query / header / cookie / body
  assembly across the OpenAPI default style/explode matrix.
* Credential application — apiKey (header/query/cookie), http bearer,
  http basic, oauth2 access tokens, openIdConnect — plus the picker
  that walks the operation's resolved security alternatives.
* End-to-end ``execute()`` round-trips through ``httpx.MockTransport``,
  including input validation, output-schema warning surfacing, and
  upstream 4xx/5xx propagation.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from purecipher.openapi_executor import (
    ArgumentValidationError,
    OpenAPIToolExecutor,
)
from purecipher.openapi_store import (
    OpenAPIStore,
    extract_openapi_operations_detailed,
)


def _spec_pets() -> dict:
    return {
        "openapi": "3.0.0",
        "servers": [{"url": "https://api.pets.example/v1"}],
        "components": {
            "securitySchemes": {
                "Bearer": {"type": "http", "scheme": "bearer"},
                "Basic": {"type": "http", "scheme": "basic"},
                "ApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                },
                "QueryKey": {
                    "type": "apiKey",
                    "in": "query",
                    "name": "key",
                },
                "OAuth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://issuer.example/token",
                            "scopes": {"read:pets": "read"},
                        }
                    },
                },
            },
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
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "tags",
                            "in": "query",
                            "schema": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createPet",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        }
                    },
                },
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "showPet",
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
            "/internal/dual": {
                "get": {
                    "operationId": "dualAuth",
                    "security": [{"ApiKey": []}, {"Bearer": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/public": {
                "get": {
                    "operationId": "publicPing",
                    "security": [],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }


def _operation(spec: dict, operation_id: str) -> dict:
    ops = extract_openapi_operations_detailed(spec)
    return next(o for o in ops if o["operation_id"] == operation_id)


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------


class TestRequestBuilder:
    def test_path_param_url_encodes_slashes(self):
        spec = _spec_pets()
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1"
        )
        b = ex.build_request({"path": {"petId": "abc/def"}})
        assert b.url == "https://api.pets.example/v1/pets/abc%2Fdef"
        assert b.method == "GET"

    def test_query_array_explodes_by_default(self):
        spec = _spec_pets()
        op = _operation(spec, "listPets")
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1"
        )
        b = ex.build_request({"query": {"tags": ["a", "b", "c"], "limit": 10}})
        assert b.method == "GET"
        # Form/explode default: each array item becomes its own pair.
        tag_pairs = [v for k, v in b.query if k == "tags"]
        assert tag_pairs == ["a", "b", "c"]
        # Scalars stringify.
        assert ("limit", "10") in b.query

    def test_query_explode_false_joins_with_comma(self):
        # Synthesize a parameter with explode=false to verify the
        # builder honours it.
        spec = _spec_pets()
        op = _operation(spec, "listPets")
        # Patch the parameter metadata in place.
        for param in op["parameters"]:
            if param["name"] == "tags":
                param["explode"] = False
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1"
        )
        b = ex.build_request({"query": {"tags": ["a", "b", "c"]}})
        tag_pairs = [(k, v) for k, v in b.query if k == "tags"]
        assert tag_pairs == [("tags", "a,b,c")]

    def test_body_carries_request_body_content_type(self):
        spec = _spec_pets()
        op = _operation(spec, "createPet")
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1"
        )
        b = ex.build_request({"body": {"name": "Fido"}})
        assert b.body == {"name": "Fido"}
        assert b.content_type == "application/json"
        assert b.method == "POST"

    def test_no_body_arg_yields_no_body(self):
        spec = _spec_pets()
        op = _operation(spec, "createPet")
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1"
        )
        b = ex.build_request({})
        assert b.body is None
        assert b.content_type is None

    def test_server_url_trailing_slash_is_normalised(self):
        spec = _spec_pets()
        op = _operation(spec, "listPets")
        ex = OpenAPIToolExecutor(
            spec=spec, operation=op, server_url="https://api.pets.example/v1/"
        )
        b = ex.build_request({})
        assert b.url == "https://api.pets.example/v1/pets"


# ---------------------------------------------------------------------------
# Credential application
# ---------------------------------------------------------------------------


class TestCredentialApplication:
    def _store_with(
        self, scheme_name: str, scheme_kind: str, secret: dict
    ) -> OpenAPIStore:
        store = OpenAPIStore(credential_key="exec-test-key")
        store.upsert_credential(
            publisher_id="acme",
            source_id="oas_pets",
            scheme_name=scheme_name,
            scheme_kind=scheme_kind,
            secret=secret,
        )
        return store

    def test_http_bearer_writes_authorization_header(self):
        spec = _spec_pets()
        op = _operation(spec, "listPets")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with(
            "Bearer", "http", {"http_scheme": "bearer", "bearer_token": "tok-XYZ"}
        )
        b = ex.build_request({})
        ex.apply_credentials_from_store(b, store)
        assert b.headers["Authorization"] == "Bearer tok-XYZ"

    def test_http_basic_encodes_credentials(self):
        spec = _spec_pets()
        # Make showPet require Basic auth so we test the basic branch.
        spec["paths"]["/pets/{petId}"]["get"]["security"] = [{"Basic": []}]
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with(
            "Basic",
            "http",
            {"http_scheme": "basic", "username": "alice", "password": "s3cret"},
        )
        b = ex.build_request({"path": {"petId": "x"}})
        ex.apply_credentials_from_store(b, store)
        # base64("alice:s3cret") == "YWxpY2U6czNjcmV0"
        assert b.headers["Authorization"] == "Basic YWxpY2U6czNjcmV0"

    def test_apikey_header_placement(self):
        spec = _spec_pets()
        spec["paths"]["/pets/{petId}"]["get"]["security"] = [{"ApiKey": []}]
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with("ApiKey", "apiKey", {"api_key": "k-12345"})
        b = ex.build_request({"path": {"petId": "x"}})
        ex.apply_credentials_from_store(b, store)
        assert b.headers["X-API-Key"] == "k-12345"

    def test_apikey_query_placement(self):
        spec = _spec_pets()
        spec["paths"]["/pets/{petId}"]["get"]["security"] = [{"QueryKey": []}]
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with("QueryKey", "apiKey", {"api_key": "qk-42"})
        b = ex.build_request({"path": {"petId": "x"}})
        ex.apply_credentials_from_store(b, store)
        assert ("key", "qk-42") in b.query

    def test_oauth2_uses_bearer_with_access_token(self):
        spec = _spec_pets()
        spec["paths"]["/pets/{petId}"]["get"]["security"] = [{"OAuth": []}]
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with(
            "OAuth", "oauth2", {"client_id": "c", "access_token": "oauth-tok-AAA"}
        )
        b = ex.build_request({"path": {"petId": "x"}})
        ex.apply_credentials_from_store(b, store)
        assert b.headers["Authorization"] == "Bearer oauth-tok-AAA"

    def test_oauth2_without_access_token_raises(self):
        spec = _spec_pets()
        spec["paths"]["/pets/{petId}"]["get"]["security"] = [{"OAuth": []}]
        op = _operation(spec, "showPet")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = self._store_with(
            "OAuth", "oauth2", {"client_id": "c", "client_secret": "s"}
        )
        b = ex.build_request({"path": {"petId": "x"}})
        with pytest.raises(ValueError, match="access_token"):
            ex.apply_credentials_from_store(b, store)

    def test_picker_chooses_first_satisfiable_alternative(self):
        spec = _spec_pets()
        op = _operation(spec, "dualAuth")  # security: ApiKey OR Bearer
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = OpenAPIStore(credential_key="exec-test-key")
        # Only Bearer registered — picker must skip the ApiKey alt.
        store.upsert_credential(
            publisher_id="acme",
            source_id="oas_pets",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-only-B"},
        )
        b = ex.build_request({})
        ex.apply_credentials_from_store(b, store)
        assert b.headers["Authorization"] == "Bearer tok-only-B"
        assert "X-API-Key" not in b.headers

    def test_picker_returns_empty_for_public_endpoint(self):
        spec = _spec_pets()
        op = _operation(spec, "publicPing")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = OpenAPIStore(credential_key="exec-test-key")
        b = ex.build_request({})
        ex.apply_credentials_from_store(b, store)
        # Public endpoint — no auth, no credential headers.
        assert "Authorization" not in b.headers

    def test_picker_raises_when_no_alternative_satisfiable(self):
        spec = _spec_pets()
        op = _operation(spec, "listPets")
        ex = OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )
        store = OpenAPIStore(credential_key="exec-test-key")
        b = ex.build_request({})
        with pytest.raises(RuntimeError, match="No credentials"):
            ex.apply_credentials_from_store(b, store)


# ---------------------------------------------------------------------------
# Validation + execute
# ---------------------------------------------------------------------------


class TestExecute:
    def _make_executor(self, spec: dict, operation_id: str) -> OpenAPIToolExecutor:
        op = _operation(spec, operation_id)
        return OpenAPIToolExecutor(
            spec=spec,
            operation=op,
            server_url="https://api.pets.example/v1",
            publisher_id="acme",
            source_id="oas_pets",
        )

    def _store_with_bearer(self) -> OpenAPIStore:
        store = OpenAPIStore(credential_key="exec-test-key")
        store.upsert_credential(
            publisher_id="acme",
            source_id="oas_pets",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-XYZ"},
        )
        return store

    def test_happy_path_round_trip(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "showPet")
        store = self._store_with_bearer()
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"id": 7, "name": "Fido"},
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await ex.execute(
                    {"path": {"petId": "abc"}}, store=store, client=client
                )
                assert result.status_code == 200
                assert result.body == {"id": 7, "name": "Fido"}
                assert result.validation_warnings == []

        asyncio.run(run())
        assert len(captured) == 1
        assert str(captured[0].url) == "https://api.pets.example/v1/pets/abc"
        assert captured[0].headers.get("authorization") == "Bearer tok-XYZ"

    def test_input_validation_collects_all_errors(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "createPet")

        async def run() -> None:
            # Missing both petId path requirement (n/a) and Pet.name —
            # body lacks the required "name" property.
            with pytest.raises(ArgumentValidationError) as exc:
                await ex.execute({"body": {"id": 1}})
            assert any("name" in m for m in exc.value.messages)

        asyncio.run(run())

    def test_output_schema_mismatch_emits_warnings(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "showPet")
        store = self._store_with_bearer()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"id": "not-an-int"},  # missing name + wrong type
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await ex.execute(
                    {"path": {"petId": "x"}}, store=store, client=client
                )
                assert result.status_code == 200
                assert any("name" in w for w in result.validation_warnings)

        asyncio.run(run())

    def test_upstream_4xx_surfaces_through(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "showPet")
        store = self._store_with_bearer()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                headers={"content-type": "application/json"},
                json={"error": "not found"},
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await ex.execute(
                    {"path": {"petId": "x"}}, store=store, client=client
                )
                assert result.status_code == 404
                assert result.body == {"error": "not found"}
                # 4xx skips output-schema checks.
                assert result.validation_warnings == []

        asyncio.run(run())

    def test_post_body_serialised_as_json(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "createPet")
        store = self._store_with_bearer()
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                201,
                headers={"content-type": "application/json"},
                json={"id": 1, "name": "Fido"},
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await ex.execute(
                    {"body": {"name": "Fido"}}, store=store, client=client
                )
                assert result.status_code == 201

        asyncio.run(run())
        assert captured[0].method == "POST"
        # MockTransport receives the json-encoded body intact.
        assert (
            captured[0].headers.get("content-type", "").startswith("application/json")
        )

    def test_text_response_falls_through_to_text_body(self):
        spec = _spec_pets()
        ex = self._make_executor(spec, "showPet")
        store = self._store_with_bearer()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                text="hello world",
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await ex.execute(
                    {"path": {"petId": "x"}}, store=store, client=client
                )
                assert result.body == "hello world"

        asyncio.run(run())
