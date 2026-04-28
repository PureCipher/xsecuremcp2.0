"""Tests for the toolset → ToolListing bridge (Iter 13.4).

Two layers of coverage:

* Unit tests on :mod:`purecipher.openapi_publish` for the manifest
  builder shape (tool name sanitisation, permission inference,
  resource_access patterns, manifest metadata round-trip).
* HTTP-level tests on ``POST /registry/openapi/toolset/{id}/publish``
  exercising the registry method via the route to confirm tenant
  isolation, attestation kind serialisation, and re-publish upserts.
"""

from __future__ import annotations

import json

from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import AttestationKind
from purecipher import PureCipherRegistry
from purecipher.auth import RegistryAuthSettings
from purecipher.openapi_publish import (
    META_OPENAPI_OPERATION_KEY,
    META_OPENAPI_SOURCE_ID,
    META_OPENAPI_SPEC_SHA256,
    META_PROVIDER_KIND,
    PROVIDER_KIND_OPENAPI,
    build_listing_payload,
    build_manifest_for_operation,
    derive_tool_name,
    sanitize_tool_name,
)
from purecipher.openapi_store import (
    OpenAPIStore,
    extract_openapi_operations_detailed,
)

TEST_SIGNING_SECRET = "purecipher-registry-signing-secret-for-tests"
TEST_JWT_SECRET = "purecipher-registry-jwt-secret-for-tests"
TEST_USERS_JSON = json.dumps(
    [
        {
            "username": "publisher",
            "password": "publisher123",
            "role": "publisher",
            "display_name": "Demo Publisher",
        },
        {
            "username": "intruder",
            "password": "intruder123",
            "role": "publisher",
            "display_name": "Other Publisher",
        },
    ]
)


def _auth_settings() -> RegistryAuthSettings:
    return RegistryAuthSettings.from_values(
        enabled=True,
        issuer="purecipher-registry",
        jwt_secret=TEST_JWT_SECRET,
        users_json=TEST_USERS_JSON,
    )


_SPEC = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.demo.example/v1"}],
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
                "tags": ["pets"],
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
            }
        },
        "/public/ping": {
            "get": {
                "operationId": "ping",
                "security": [],
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Manifest builder unit tests
# ---------------------------------------------------------------------------


class TestSanitizeToolName:
    def test_strips_invalid_chars(self):
        assert sanitize_tool_name("GET /pets/{petId}") == "GET-pets-petId"

    def test_collapses_runs(self):
        assert sanitize_tool_name("a/////b") == "a-b"

    def test_strips_edge_hyphens(self):
        assert sanitize_tool_name("---abc---") == "abc"

    def test_empty_input_falls_back(self):
        assert sanitize_tool_name("") == "openapi-tool"
        assert sanitize_tool_name("///") == "openapi-tool"


class TestDeriveToolName:
    def test_uses_operation_id_when_present(self):
        op = {"operation_id": "listPets", "method": "GET", "path": "/pets"}
        assert derive_tool_name(op) == "listPets"

    def test_falls_back_to_method_path(self):
        op = {"operation_id": "", "method": "GET", "path": "/pets/{id}"}
        assert derive_tool_name(op) == "GET-pets-id"

    def test_prefix_is_applied(self):
        op = {"operation_id": "show", "method": "GET", "path": "/x"}
        assert derive_tool_name(op, prefix="acme") == "acme-show"


class TestBuildManifest:
    def _setup(self) -> tuple[dict, dict, dict]:
        store = OpenAPIStore()
        record, _ops = store.ingest_source(
            publisher_id="acme", title="Demo", raw_text=json.dumps(_SPEC)
        )
        toolset = store.create_toolset(
            publisher_id="acme",
            source_id=record["source_id"],
            title="Demo TS",
            selected_operations=["showPet", "createPet", "ping"],
        )
        return _SPEC, dict(record), dict(toolset)

    def _op(self, operation_id: str) -> dict:
        ops = extract_openapi_operations_detailed(_SPEC)
        return next(o for o in ops if o["operation_id"] == operation_id)

    def test_get_operation_yields_read_permissions(self):
        spec, record, toolset = self._setup()
        manifest = build_manifest_for_operation(
            self._op("showPet"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
            version="1.0.0",
        )
        perm_values = {p.value for p in manifest.permissions}
        assert "read_resource" in perm_values
        assert "network_access" in perm_values
        assert manifest.idempotent is True
        assert manifest.deterministic is True
        assert manifest.requires_consent is True  # Bearer required

    def test_post_operation_yields_write_permissions(self):
        spec, record, toolset = self._setup()
        manifest = build_manifest_for_operation(
            self._op("createPet"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
            version="1.0.0",
        )
        perm_values = {p.value for p in manifest.permissions}
        assert "write_resource" in perm_values
        assert manifest.idempotent is False
        assert manifest.deterministic is False

    def test_public_operation_drops_consent_requirement(self):
        spec, record, toolset = self._setup()
        manifest = build_manifest_for_operation(
            self._op("ping"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
        )
        # security: [] at op level → no consent needed.
        assert manifest.requires_consent is False

    def test_resource_access_uses_glob_pattern(self):
        spec, record, toolset = self._setup()
        manifest = build_manifest_for_operation(
            self._op("showPet"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
        )
        assert len(manifest.resource_access) == 1
        ra = manifest.resource_access[0]
        # Path token replaced with *.
        assert ra.resource_pattern == "https://api.demo.example/v1/pets/*"
        assert ra.access_type == "read"

    def test_metadata_round_trips_provenance(self):
        spec, record, toolset = self._setup()
        manifest = build_manifest_for_operation(
            self._op("showPet"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
        )
        assert manifest.metadata[META_PROVIDER_KIND] == PROVIDER_KIND_OPENAPI
        assert manifest.metadata[META_OPENAPI_SOURCE_ID] == record["source_id"]
        assert manifest.metadata[META_OPENAPI_OPERATION_KEY] == "showPet"
        assert manifest.metadata[META_OPENAPI_SPEC_SHA256] == record["spec_sha256"]
        # Input/output schemas are preserved so the public detail page
        # can render a form without re-fetching the raw spec.
        assert "input_schema" in str(manifest.metadata)
        assert manifest.metadata["purecipher.openapi.input_schema"]["type"] == "object"

    def test_build_listing_payload_returns_publish_kwargs(self):
        spec, record, toolset = self._setup()
        payload = build_listing_payload(
            self._op("showPet"),
            source=record,
            toolset=toolset,
            server_url="https://api.demo.example/v1",
            publisher_id="acme",
        )
        assert payload["tool_name"] == "showPet"
        assert payload["display_name"] == "Get a pet"
        assert payload["author"] == "acme"
        assert "openapi" in payload["tags"]
        assert payload["manifest"].tool_name == "showPet"


# ---------------------------------------------------------------------------
# Registry method
# ---------------------------------------------------------------------------


class TestPublishToolsetAsListings:
    def _build_registry(self) -> tuple[PureCipherRegistry, str]:
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        record, _ops = registry._openapi_store.ingest_source(
            publisher_id="acme", title="Demo", raw_text=json.dumps(_SPEC)
        )
        toolset = registry._openapi_store.create_toolset(
            publisher_id="acme",
            source_id=record["source_id"],
            title="Demo TS",
            selected_operations=["showPet", "createPet"],
        )
        return registry, toolset["toolset_id"]

    def test_publishes_one_listing_per_operation(self):
        registry, toolset_id = self._build_registry()
        listings = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        assert len(listings) == 2
        names = {L.tool_name for L in listings}
        assert names == {"showPet", "createPet"}

    def test_attestation_kind_is_openapi(self):
        registry, toolset_id = self._build_registry()
        listings = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        for L in listings:
            assert L.attestation_kind is AttestationKind.OPENAPI
            assert L.attestation_kind.value == "openapi"

    def test_republish_upserts_same_listing(self):
        registry, toolset_id = self._build_registry()
        first = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        second = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.1.0"
        )
        assert {L.listing_id for L in first} == {L.listing_id for L in second}
        assert {L.version for L in second} == {"1.1.0"}

    def test_metadata_carries_openapi_provenance(self):
        registry, toolset_id = self._build_registry()
        listings = registry.publish_toolset_as_listings(
            toolset_id, publisher_id="acme", version="1.0.0"
        )
        for L in listings:
            assert L.metadata.get("purecipher.provider_kind") == PROVIDER_KIND_OPENAPI
            assert L.metadata.get("purecipher.openapi.operation_key") in {
                "showPet",
                "createPet",
            }

    def test_unknown_toolset_raises(self):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        try:
            registry.publish_toolset_as_listings(
                "toolset_does_not_exist", publisher_id="acme"
            )
        except ValueError as exc:
            assert "Unknown toolset" in str(exc)
        else:
            raise AssertionError("ValueError was not raised")


# ---------------------------------------------------------------------------
# HTTP route
# ---------------------------------------------------------------------------


class TestRegistryOpenAPIPublishRoute:
    def _ingest_and_create_toolset(
        self, client: TestClient, *, username: str = "publisher"
    ) -> tuple[str, str]:
        login = client.post(
            "/registry/login",
            json={
                "username": username,
                "password": (
                    "publisher123" if username == "publisher" else "intruder123"
                ),
            },
        )
        assert login.status_code == 200
        ingest = client.post(
            "/registry/openapi/ingest",
            json={"text": json.dumps(_SPEC), "title": "Demo"},
        )
        assert ingest.status_code == 200, ingest.text
        source_id = ingest.json()["source"]["source_id"]
        toolset = client.post(
            "/registry/openapi/toolset",
            json={
                "source_id": source_id,
                "title": "Demo TS",
                "selected_operations": ["showPet", "createPet"],
            },
        )
        assert toolset.status_code == 200
        return source_id, toolset.json()["toolset"]["toolset_id"]

    def test_publish_returns_listings(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            _source, toolset_id = self._ingest_and_create_toolset(client)
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/publish",
                json={"version": "1.0.0"},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            listings = body["listings"]
            assert len(listings) == 2
            names = {L["tool_name"] for L in listings}
            assert names == {"showPet", "createPet"}
            for L in listings:
                assert L["attestation_kind"] == "openapi"
                assert L["hosting_mode"] == "proxy"
                assert L["operation_key"] in names

    def test_publish_requires_auth(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            resp = client.post(
                "/registry/openapi/toolset/some_id/publish",
                json={},
            )
            assert resp.status_code == 401

    def test_publish_blocks_cross_publisher(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        # Publisher creates toolset.
        with TestClient(registry.http_app()) as client:
            _source, toolset_id = self._ingest_and_create_toolset(client)
            client.get("/registry/logout")

            # Other publisher tries to publish it.
            login = client.post(
                "/registry/login",
                json={"username": "intruder", "password": "intruder123"},
            )
            assert login.status_code == 200
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/publish",
                json={"version": "1.0.0"},
            )
            assert resp.status_code == 403

    def test_publish_unknown_toolset_returns_404(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            login = client.post(
                "/registry/login",
                json={"username": "publisher", "password": "publisher123"},
            )
            assert login.status_code == 200
            resp = client.post(
                "/registry/openapi/toolset/missing_id/publish",
                json={"version": "1.0.0"},
            )
            assert resp.status_code == 404

    def test_publish_rejects_unknown_category(self):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=_auth_settings(),
        )
        with TestClient(registry.http_app()) as client:
            _source, toolset_id = self._ingest_and_create_toolset(client)
            resp = client.post(
                f"/registry/openapi/toolset/{toolset_id}/publish",
                json={"version": "1.0.0", "categories": ["NOT_A_CATEGORY"]},
            )
            assert resp.status_code == 400
            assert "Unknown category" in resp.json()["error"]
