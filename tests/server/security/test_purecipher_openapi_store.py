"""Tests for the detailed OpenAPI extractor in `purecipher.openapi_store`.

These exercise the schema-walking helpers that the executor (Iter 13.3)
and tool-listing bridge (Iter 13.4) rely on, plus the YAML ingestion
path opened up in Iter 13.1.2.
"""

from __future__ import annotations

import textwrap

import pytest

from purecipher.openapi_store import (
    OpenAPIStore,
    _coerce_openapi_doc,
    _coerce_openapi_json,
    _credential_secret_hint,
    _resolve_local_ref,
    _walk_schema,
    extract_openapi_operations_detailed,
    extract_security_schemes,
    resolve_operation_security,
)

# ---------------------------------------------------------------------------
# YAML / JSON ingestion
# ---------------------------------------------------------------------------


class TestCoerceOpenAPIDoc:
    def test_parses_json(self):
        spec = _coerce_openapi_doc('{"openapi": "3.0.0"}')
        assert spec == {"openapi": "3.0.0"}

    def test_parses_yaml(self):
        text = textwrap.dedent(
            """
            openapi: 3.0.0
            info:
              title: Demo
              version: 1.0.0
            """
        ).strip()
        spec = _coerce_openapi_doc(text)
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Demo"

    def test_yaml_list_root_rejected(self):
        with pytest.raises(ValueError, match="JSON/YAML object"):
            _coerce_openapi_doc("- one\n- two\n")

    def test_invalid_yaml_rejected(self):
        with pytest.raises(ValueError, match="neither valid JSON nor YAML"):
            # A tab inside a flow mapping breaks YAML and is not JSON.
            _coerce_openapi_doc("{key:\tvalue}\n: : :")

    def test_json_helper_remains_strict(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            _coerce_openapi_json("openapi: 3.0.0\n")


# ---------------------------------------------------------------------------
# $ref resolution
# ---------------------------------------------------------------------------


class TestResolveLocalRef:
    def test_resolves_components_schema(self):
        spec = {
            "components": {"schemas": {"Pet": {"type": "object"}}},
        }
        assert _resolve_local_ref(spec, "#/components/schemas/Pet") == {
            "type": "object"
        }

    def test_decodes_pointer_escapes(self):
        spec = {"a/b": {"x~y": {"hit": True}}}
        # ~1 → "/", ~0 → "~"
        assert _resolve_local_ref(spec, "#/a~1b/x~0y") == {"hit": True}

    def test_returns_none_for_external_ref(self):
        assert _resolve_local_ref({}, "https://example.com/spec.yaml") is None

    def test_returns_none_for_missing_pointer(self):
        spec = {"components": {"schemas": {}}}
        assert _resolve_local_ref(spec, "#/components/schemas/Missing") is None

    def test_returns_none_for_non_object_target(self):
        spec = {"x": 42}
        assert _resolve_local_ref(spec, "#/x") is None


# ---------------------------------------------------------------------------
# Schema walking
# ---------------------------------------------------------------------------


class TestWalkSchema:
    def test_resolves_top_level_ref(self):
        spec = {
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                }
            }
        }
        result = _walk_schema(spec, {"$ref": "#/components/schemas/Pet"})
        assert result["type"] == "object"
        assert result["properties"]["name"] == {"type": "string"}

    def test_resolves_nested_refs(self):
        spec = {
            "components": {
                "schemas": {
                    "Tag": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                    },
                    "Pet": {
                        "type": "object",
                        "properties": {
                            "tag": {"$ref": "#/components/schemas/Tag"},
                            "tags": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Tag"},
                            },
                        },
                    },
                }
            }
        }
        result = _walk_schema(spec, {"$ref": "#/components/schemas/Pet"})
        tag_props = result["properties"]["tag"]
        assert tag_props["type"] == "object"
        assert tag_props["properties"]["id"] == {"type": "integer"}
        assert result["properties"]["tags"]["items"]["properties"]["id"] == {
            "type": "integer"
        }

    def test_breaks_self_reference_cycles(self):
        spec = {
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "next": {"$ref": "#/components/schemas/Node"},
                        },
                    }
                }
            }
        }
        result = _walk_schema(spec, {"$ref": "#/components/schemas/Node"})
        # First level expands; recursive child stays as a $ref so consumers
        # can resolve it lazily without an infinite expansion.
        assert result["properties"]["value"] == {"type": "string"}
        assert result["properties"]["next"] == {"$ref": "#/components/schemas/Node"}

    def test_resolves_all_of(self):
        spec = {
            "components": {
                "schemas": {
                    "Base": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                        "required": ["id"],
                    },
                    "Pet": {
                        "allOf": [
                            {"$ref": "#/components/schemas/Base"},
                            {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                            },
                        ]
                    },
                }
            }
        }
        result = _walk_schema(spec, {"$ref": "#/components/schemas/Pet"})
        assert result["type"] == "object"
        assert set(result["properties"].keys()) == {"id", "name"}
        assert sorted(result["required"]) == ["id", "name"]

    def test_walks_one_of_and_any_of(self):
        spec = {
            "components": {
                "schemas": {"S": {"type": "string"}, "I": {"type": "integer"}}
            }
        }
        schema = {
            "oneOf": [
                {"$ref": "#/components/schemas/S"},
                {"$ref": "#/components/schemas/I"},
            ],
            "anyOf": [
                {"$ref": "#/components/schemas/S"},
                {"type": "boolean"},
            ],
        }
        result = _walk_schema(spec, schema)
        assert result["oneOf"][0] == {"type": "string"}
        assert result["oneOf"][1] == {"type": "integer"}
        assert result["anyOf"][1] == {"type": "boolean"}

    def test_normalises_nullable(self):
        result = _walk_schema({}, {"type": "string", "nullable": True})
        assert result["type"] == ["string", "null"]
        # nullable key itself is dropped
        assert "nullable" not in result

    def test_nullable_with_array_type_appends_null(self):
        result = _walk_schema({}, {"type": ["string", "integer"], "nullable": True})
        assert result["type"] == ["string", "integer", "null"]

    def test_dangling_ref_preserved(self):
        result = _walk_schema({}, {"$ref": "#/components/schemas/Missing"})
        assert result == {"$ref": "#/components/schemas/Missing"}

    def test_passes_through_non_dict(self):
        assert _walk_schema({}, "scalar") == "scalar"
        assert _walk_schema({}, None) is None


# ---------------------------------------------------------------------------
# extract_openapi_operations_detailed
# ---------------------------------------------------------------------------


def _spec_pets() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Pets", "version": "1.0.0"},
        "servers": [{"url": "https://api.pets.example/v1"}],
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "tag": {"type": "string", "nullable": True},
                    },
                    "required": ["id", "name"],
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "message": {"type": "string"},
                    },
                },
            },
            "parameters": {
                "PageSize": {
                    "name": "pageSize",
                    "in": "query",
                    "schema": {"type": "integer", "default": 20},
                    "description": "Max items to return.",
                }
            },
        },
        "security": [{"apiKeyAuth": []}],
        "paths": {
            "/pets": {
                "parameters": [
                    {"$ref": "#/components/parameters/PageSize"},
                ],
                "get": {
                    "operationId": "listPets",
                    "summary": "List pets",
                    "tags": ["pets"],
                    "responses": {
                        "200": {
                            "description": "A paged array of pets.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"},
                                    }
                                }
                            },
                        },
                        "default": {
                            "description": "Unexpected error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        },
                    },
                },
                "post": {
                    "operationId": "createPet",
                    "summary": "Create a pet",
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
                            "description": "Found",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        }
                    },
                    "security": [],  # operation-level override disabling auth
                    "servers": [{"url": "https://internal.pets.example/v1"}],
                }
            },
        },
    }


class TestExtractOpenAPIOperationsDetailed:
    def test_returns_empty_when_paths_missing(self):
        assert extract_openapi_operations_detailed({"openapi": "3.1.0"}) == []

    def test_extracts_listpets_with_inherited_query_param(self):
        ops = extract_openapi_operations_detailed(_spec_pets())
        list_pets = next(op for op in ops if op["operation_id"] == "listPets")

        assert list_pets["method"] == "get"
        assert list_pets["path"] == "/pets"
        assert list_pets["tags"] == ["pets"]
        assert list_pets["server_urls"] == ["https://api.pets.example/v1"]
        assert list_pets["security"] == [{"apiKeyAuth": []}]

        # Inherited path-level $ref'd parameter is resolved.
        page_size = next(p for p in list_pets["parameters"] if p["name"] == "pageSize")
        assert page_size["location"] == "query"
        assert page_size["schema"]["type"] == "integer"
        assert page_size["schema"]["default"] == 20
        assert page_size["description"] == "Max items to return."

        # Aggregated input schema groups by location.
        input_schema = list_pets["input_schema"]
        assert input_schema["type"] == "object"
        assert "query" in input_schema["properties"]
        assert "pageSize" in input_schema["properties"]["query"]["properties"]
        # listPets has no required path/body, so no top-level required.
        assert input_schema.get("required", []) == []

        # Output schema is the resolved 200 response (array of Pet).
        output = list_pets["output_schema"]
        assert output is not None
        assert output["type"] == "array"
        assert output["items"]["properties"]["id"] == {"type": "integer"}

    def test_create_pet_body_schema_resolved_and_required(self):
        ops = extract_openapi_operations_detailed(_spec_pets())
        create = next(op for op in ops if op["operation_id"] == "createPet")
        assert create["request_body"] is not None
        assert create["request_body"]["required"] is True
        assert create["request_body"]["content_type"] == "application/json"
        assert create["request_body"]["schema"]["properties"]["name"] == {
            "type": "string"
        }
        # nullable normalised to type union
        assert create["request_body"]["schema"]["properties"]["tag"]["type"] == [
            "string",
            "null",
        ]

        input_schema = create["input_schema"]
        assert input_schema["properties"]["body"]["properties"]["id"] == {
            "type": "integer"
        }
        assert "body" in input_schema.get("required", [])

    def test_path_param_marked_required_and_overrides_apply(self):
        ops = extract_openapi_operations_detailed(_spec_pets())
        show = next(op for op in ops if op["operation_id"] == "showPet")

        pet_id = next(p for p in show["parameters"] if p["name"] == "petId")
        assert pet_id["required"] is True
        assert pet_id["location"] == "path"

        # showPet sits under /pets/{petId} so it does NOT inherit the
        # path-level pageSize parameter from /pets — only the petId
        # parameter declared on its own operation should appear.
        names = {p["name"] for p in show["parameters"]}
        assert names == {"petId"}

        # Operation-level security: empty list overrides top-level.
        assert show["security"] == []
        # Operation-level servers override.
        assert show["server_urls"] == ["https://internal.pets.example/v1"]

        # Path group is required because it has a path param.
        assert "path" in show["input_schema"].get("required", [])

    def test_default_response_does_not_become_output_schema_when_2xx_present(self):
        ops = extract_openapi_operations_detailed(_spec_pets())
        list_pets = next(op for op in ops if op["operation_id"] == "listPets")
        # 200 should win over default.
        out = list_pets["output_schema"]
        assert out is not None
        assert out["type"] == "array"

    def test_missing_operation_id_falls_back_to_method_path(self):
        spec = {
            "openapi": "3.0.0",
            "paths": {
                "/health": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                },
                            }
                        }
                    }
                }
            },
        }
        ops = extract_openapi_operations_detailed(spec)
        assert len(ops) == 1
        assert ops[0]["operation_key"] == "GET /health"
        assert ops[0]["operation_id"] == ""

    def test_handles_yaml_round_trip(self):
        yaml_text = textwrap.dedent(
            """
            openapi: 3.0.3
            info:
              title: Tiny
              version: 0.1.0
            paths:
              /ping:
                get:
                  operationId: ping
                  responses:
                    "200":
                      description: pong
                      content:
                        application/json:
                          schema:
                            type: object
                            properties:
                              ok:
                                type: boolean
            """
        ).strip()
        spec = _coerce_openapi_doc(yaml_text)
        ops = extract_openapi_operations_detailed(spec)
        assert len(ops) == 1
        op = ops[0]
        assert op["operation_id"] == "ping"
        assert op["output_schema"]["properties"]["ok"] == {"type": "boolean"}


class TestOpenAPIStoreYAMLIngest:
    def test_ingest_yaml_text_via_store(self):
        store = OpenAPIStore()
        yaml_text = textwrap.dedent(
            """
            openapi: 3.0.0
            info:
              title: Demo
              version: 1.0.0
            paths:
              /hello:
                get:
                  operationId: hello
                  responses:
                    "200":
                      description: OK
            """
        ).strip()
        record, ops = store.ingest_source(
            publisher_id="acme",
            title="Demo YAML",
            raw_text=yaml_text,
        )
        assert record["operation_count"] == 1
        assert ops[0]["operation_id"] == "hello"
        assert ops[0]["method"] == "get"


# ---------------------------------------------------------------------------
# Iter 13.2 — security schemes + credentials
# ---------------------------------------------------------------------------


class TestExtractSecuritySchemes:
    def test_returns_empty_when_no_components(self):
        assert extract_security_schemes({"openapi": "3.1.0"}) == {}

    def test_parses_all_kinds(self):
        spec = {
            "components": {
                "securitySchemes": {
                    "ApiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                    },
                    "Bearer": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    },
                    "Basic": {"type": "http", "scheme": "basic"},
                    "OAuth": {
                        "type": "oauth2",
                        "flows": {
                            "clientCredentials": {
                                "tokenUrl": "https://issuer.example/oauth/token",
                                "scopes": {"read:pets": "Read pets"},
                            },
                            "junkFlow": {"tokenUrl": "ignored"},
                        },
                    },
                    "OIDC": {
                        "type": "openIdConnect",
                        "openIdConnectUrl": "https://issuer.example/.well-known/openid-configuration",
                    },
                    "Bogus": {"type": "notAType"},
                    "MissingApiKeyName": {"type": "apiKey", "in": "header"},
                    "BadHttp": {"type": "http"},
                    "OIDCnoUrl": {"type": "openIdConnect"},
                }
            }
        }
        out = extract_security_schemes(spec)
        # Malformed entries dropped
        assert "Bogus" not in out
        assert "MissingApiKeyName" not in out
        assert "BadHttp" not in out
        assert "OIDCnoUrl" not in out
        # Well-formed entries normalised
        assert out["ApiKey"]["kind"] == "apiKey"
        assert out["ApiKey"]["api_key_name"] == "X-API-Key"
        assert out["ApiKey"]["api_key_in"] == "header"
        assert out["Bearer"]["kind"] == "http"
        assert out["Bearer"]["http_scheme"] == "bearer"
        assert out["Bearer"]["bearer_format"] == "JWT"
        assert out["Basic"]["http_scheme"] == "basic"
        # oauth2 flow normalisation: junkFlow dropped, valid flow kept
        oauth_flows = out["OAuth"]["oauth_flows"]
        assert "clientCredentials" in oauth_flows
        assert "junkFlow" not in oauth_flows
        assert oauth_flows["clientCredentials"]["scopes"] == {"read:pets": "Read pets"}
        assert (
            oauth_flows["clientCredentials"]["tokenUrl"]
            == "https://issuer.example/oauth/token"
        )
        assert (
            out["OIDC"]["open_id_connect_url"]
            == "https://issuer.example/.well-known/openid-configuration"
        )

    def test_resolves_ref_inside_security_schemes(self):
        spec = {
            "components": {
                "securitySchemes": {
                    "ApiKey": {"$ref": "#/components/customSchemes/Real"},
                },
                "customSchemes": {
                    "Real": {"type": "apiKey", "in": "query", "name": "key"}
                },
            }
        }
        out = extract_security_schemes(spec)
        assert out["ApiKey"]["api_key_in"] == "query"
        assert out["ApiKey"]["api_key_name"] == "key"


class TestResolveOperationSecurity:
    def test_empty_input_returns_empty(self):
        assert resolve_operation_security(None, {}) == []
        assert resolve_operation_security([], {}) == []

    def test_alternatives_preserved_with_resolved_schemes(self):
        scheme_map = {
            "Bearer": {
                "scheme_name": "Bearer",
                "kind": "http",
                "http_scheme": "bearer",
            },
            "ApiKey": {
                "scheme_name": "ApiKey",
                "kind": "apiKey",
                "api_key_in": "header",
                "api_key_name": "X-API-Key",
            },
        }
        result = resolve_operation_security(
            [{"Bearer": ["read"]}, {"ApiKey": []}],
            scheme_map,  # type: ignore[arg-type]
        )
        assert len(result) == 2
        assert result[0][0]["scheme_name"] == "Bearer"
        assert result[0][0]["scopes"] == ["read"]
        assert result[0][0]["scheme"]["kind"] == "http"
        assert result[1][0]["scheme_name"] == "ApiKey"

    def test_missing_scheme_marked_as_none(self):
        result = resolve_operation_security([{"GhostScheme": []}], {})
        assert result[0][0]["scheme_name"] == "GhostScheme"
        assert result[0][0]["scheme"] is None


class TestCredentialSecretHint:
    def test_apikey_hint_uses_last_four(self):
        assert (
            _credential_secret_hint("apiKey", {"api_key": "verylongapikey1234"})
            == "…1234"
        )

    def test_apikey_short_token_returns_set_marker(self):
        assert _credential_secret_hint("apiKey", {"api_key": "ab"}) == "set"

    def test_bearer_hint_includes_prefix(self):
        hint = _credential_secret_hint(
            "http", {"http_scheme": "bearer", "bearer_token": "abcdefghij"}
        )
        assert hint == "bearer …ghij"

    def test_basic_hint_is_redacted(self):
        hint = _credential_secret_hint(
            "http", {"http_scheme": "basic", "username": "alice", "password": "x"}
        )
        assert hint == "basic al***"

    def test_oauth2_prefers_access_token(self):
        hint = _credential_secret_hint(
            "oauth2", {"access_token": "longaccesstoken1234"}
        )
        assert hint == "…1234"

    def test_oauth2_falls_back_to_client_id(self):
        hint = _credential_secret_hint("oauth2", {"client_id": "abcdef-client"})
        assert hint == "client_id abcd***"


class TestOpenAPIStoreCredentials:
    def _store(self) -> OpenAPIStore:
        return OpenAPIStore(credential_key="test-secret-for-cred-tests")

    def test_credential_round_trip_in_memory(self):
        store = self._store()
        rec = store.upsert_credential(
            publisher_id="acme",
            source_id="oas_1",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "abcdef1234"},
            label="prod",
        )
        assert rec["credential_id"].startswith("cred_")
        got = store.get_credential(rec["credential_id"], publisher_id="acme")
        assert got is not None
        assert got["secret"]["bearer_token"] == "abcdef1234"
        assert got["scheme_kind"] == "http"

    def test_credential_round_trip_sqlite(self):
        store = OpenAPIStore(
            db_path=":memory:", credential_key="test-secret-for-cred-tests"
        )
        rec = store.upsert_credential(
            publisher_id="acme",
            source_id="oas_1",
            scheme_name="ApiKey",
            scheme_kind="apiKey",
            secret={"api_key": "secret-key-with-suffix-AAAA"},
            label="staging",
        )
        listed = store.list_credentials(publisher_id="acme")
        assert len(listed) == 1
        assert listed[0]["secret_hint"] == "…AAAA"
        # Listed records must NOT carry secret payloads
        assert "secret" not in listed[0]
        got = store.get_credential(rec["credential_id"], publisher_id="acme")
        assert got is not None
        assert got["secret"]["api_key"] == "secret-key-with-suffix-AAAA"

    def test_upsert_overwrites_same_triple(self):
        store = self._store()
        first = store.upsert_credential(
            publisher_id="acme",
            source_id="oas_1",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-AAAA"},
        )
        second = store.upsert_credential(
            publisher_id="acme",
            source_id="oas_1",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-BBBB"},
        )
        assert first["credential_id"] == second["credential_id"]
        listed = store.list_credentials(publisher_id="acme")
        assert len(listed) == 1
        assert listed[0]["secret_hint"] == "bearer …BBBB"

    def test_cross_publisher_isolation(self):
        store = OpenAPIStore(
            db_path=":memory:", credential_key="test-secret-for-cred-tests"
        )
        rec = store.upsert_credential(
            publisher_id="acme",
            source_id="oas_1",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-AAAA"},
        )
        # Hostile reader can't fetch
        assert store.get_credential(rec["credential_id"], publisher_id="other") is None
        # ...nor delete
        assert (
            store.delete_credential(rec["credential_id"], publisher_id="other") is False
        )
        # ...nor list
        assert store.list_credentials(publisher_id="other") == []
        # Owner still has access
        assert (
            store.get_credential(rec["credential_id"], publisher_id="acme") is not None
        )

    def test_credential_filtered_by_source_id(self):
        store = self._store()
        store.upsert_credential(
            publisher_id="acme",
            source_id="oas_a",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-A"},
        )
        store.upsert_credential(
            publisher_id="acme",
            source_id="oas_b",
            scheme_name="Bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-B"},
        )
        a_only = store.list_credentials(publisher_id="acme", source_id="oas_a")
        assert len(a_only) == 1
        assert a_only[0]["source_id"] == "oas_a"

    def test_missing_credential_key_blocks_credential_ops(self):
        store = OpenAPIStore()  # no credential_key
        with pytest.raises(RuntimeError, match="credential_key"):
            store.upsert_credential(
                publisher_id="a",
                source_id="b",
                scheme_name="c",
                scheme_kind="http",
                secret={"http_scheme": "bearer", "bearer_token": "t"},
            )

    def test_delete_returns_false_for_unknown_id(self):
        store = self._store()
        assert (
            store.delete_credential("cred_does_not_exist", publisher_id="acme") is False
        )

    def test_ingest_source_extracts_security_schemes(self):
        store = self._store()
        spec_text = textwrap.dedent(
            """
            openapi: 3.0.0
            info:
              title: Demo
              version: 1.0.0
            components:
              securitySchemes:
                ApiKey:
                  type: apiKey
                  in: header
                  name: X-API-Key
            paths:
              /hello:
                get:
                  operationId: hello
                  responses:
                    "200":
                      description: OK
            """
        ).strip()
        record, _ops = store.ingest_source(
            publisher_id="acme", title="Demo", raw_text=spec_text
        )
        schemes = record.get("security_schemes") or {}
        assert "ApiKey" in schemes
        assert schemes["ApiKey"]["kind"] == "apiKey"


# ---------------------------------------------------------------------------
# Regressions captured during the post-13.1/13.2 bug-hunt pass.
# ---------------------------------------------------------------------------


class TestOpenAPIRegressions:
    def test_sibling_refs_to_same_schema_both_resolve(self):
        """Cycle detection must not trip on siblings that happen to
        share a referenced schema. We pass the same ``seen`` set across
        sibling property walks, so a buggy implementation that mutated
        it instead of forking it would mark the second sibling as a
        cycle."""
        spec = {
            "components": {
                "schemas": {
                    "Tag": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                    }
                }
            },
        }
        schema = {
            "properties": {
                "a": {"$ref": "#/components/schemas/Tag"},
                "b": {"$ref": "#/components/schemas/Tag"},
            }
        }
        out = _walk_schema(spec, schema)
        assert "type" in out["properties"]["a"]
        assert "type" in out["properties"]["b"]

    def test_chain_of_refs_resolves_through_multiple_hops(self):
        spec = {
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/C"},
                    "C": {"$ref": "#/components/schemas/D"},
                    "D": {"type": "string", "enum": ["x", "y"]},
                }
            }
        }
        out = _walk_schema(spec, {"$ref": "#/components/schemas/A"})
        assert out == {"type": "string", "enum": ["x", "y"]}

    def test_mutual_cycle_preserves_inner_ref(self):
        """A → B → A. The first time A and B expand; the second
        encounter of A is preserved as a $ref so consumers can resolve
        lazily without a stack-blowing recursion."""
        spec = {
            "components": {
                "schemas": {
                    "A": {
                        "type": "object",
                        "properties": {"b": {"$ref": "#/components/schemas/B"}},
                    },
                    "B": {
                        "type": "object",
                        "properties": {"a": {"$ref": "#/components/schemas/A"}},
                    },
                }
            }
        }
        out = _walk_schema(spec, {"$ref": "#/components/schemas/A"})
        assert out["properties"]["b"]["properties"]["a"] == {
            "$ref": "#/components/schemas/A"
        }

    def test_request_body_top_level_ref_is_resolved(self):
        spec = {
            "openapi": "3.0.0",
            "components": {
                "requestBodies": {
                    "PetBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        },
                    }
                }
            },
            "paths": {
                "/pets": {
                    "post": {
                        "operationId": "createPet",
                        "requestBody": {"$ref": "#/components/requestBodies/PetBody"},
                        "responses": {"201": {"description": "Created"}},
                    }
                }
            },
        }
        ops = extract_openapi_operations_detailed(spec)
        op = ops[0]
        assert op["request_body"] is not None
        assert op["request_body"]["required"] is True
        assert op["request_body"]["schema"]["properties"]["name"] == {"type": "string"}

    def test_empty_op_security_overrides_top_level_security(self):
        """A *present-but-empty* operation security array opts the
        operation out of authentication entirely. A bug that conflates
        ``[]`` with "missing" would re-apply the document-level
        requirement and silently force auth on a public endpoint."""
        spec = {
            "openapi": "3.0.0",
            "security": [{"global": []}],
            "paths": {
                "/public": {
                    "get": {
                        "security": [],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        ops = extract_openapi_operations_detailed(spec)
        assert ops[0]["security"] == []

    def test_operation_with_no_responses_block_yields_none_output(self):
        spec = {"openapi": "3.0.0", "paths": {"/p": {"get": {}}}}
        ops = extract_openapi_operations_detailed(spec)
        assert len(ops) == 1
        assert ops[0]["output_schema"] is None
        assert ops[0]["responses"] == []

    def test_parameter_schema_ref_resolves_through_parameter_ref(self):
        """Path-level ``parameters[]`` may itself be a $ref to a
        component parameter, whose ``schema`` may itself be a $ref to
        a component schema. Both layers must resolve."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {"Limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                "parameters": {
                    "LimitParam": {
                        "name": "limit",
                        "in": "query",
                        "schema": {"$ref": "#/components/schemas/Limit"},
                    }
                },
            },
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "parameters": [{"$ref": "#/components/parameters/LimitParam"}],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        ops = extract_openapi_operations_detailed(spec)
        limit = next(p for p in ops[0]["parameters"] if p["name"] == "limit")
        assert limit["schema"]["type"] == "integer"
        assert limit["schema"]["minimum"] == 1
        assert limit["schema"]["maximum"] == 100

    def test_credential_decryption_with_wrong_key_raises_clean_error(self):
        """Tampering or rekeying the store mid-flight must surface a
        clear RuntimeError rather than crash with a Fernet exception."""
        store_a = OpenAPIStore(db_path=":memory:", credential_key="key-A")
        rec = store_a.upsert_credential(
            publisher_id="acme",
            source_id="oas_x",
            scheme_name="bearer",
            scheme_kind="http",
            secret={"http_scheme": "bearer", "bearer_token": "tok-AAAA"},
        )
        # Reuse the same in-memory connection but with a different key.
        store_b = OpenAPIStore(
            db_path=":memory:", credential_key="key-B", ensure_schema=False
        )
        store_b._shared_conn = store_a._shared_conn
        with pytest.raises(RuntimeError, match="failed to decrypt"):
            store_b.get_credential(rec["credential_id"], publisher_id="acme")
