"""Bridge an OpenAPI toolset into registry ToolListings (Iter 13.4).

The store layer (Iter 13.1) extracts operations from a spec; the
executor (Iter 13.3) calls them at runtime. This module converts the
extracted operation surface into a :class:`SecurityManifest` and
publishing payload so the operation becomes a first-class
``ToolListing`` in the registry's marketplace — visible on the public
catalog and gated by all five governance planes the same way a
hand-written FastMCP tool is.

The shape we produce matches what ``ToolMarketplace.publish`` accepts.
The actual marketplace call lives on :class:`PureCipherRegistry` so
the registry can wire signing, certification level, and the publisher
identity through.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    ResourceAccessDeclaration,
    SecurityManifest,
)
from purecipher.openapi_store import (
    OpenAPIOperationDetailed,
    OpenAPISourceRecord,
    OpenAPIToolsetRecord,
)

# Manifest metadata keys carrying OpenAPI provenance. Stable strings
# so anything reading the manifest (executor, public detail page) can
# round-trip without knowing about this module.
META_PROVIDER_KIND = "purecipher.provider_kind"
META_OPENAPI_SOURCE_ID = "purecipher.openapi.source_id"
META_OPENAPI_TOOLSET_ID = "purecipher.openapi.toolset_id"
META_OPENAPI_OPERATION_KEY = "purecipher.openapi.operation_key"
META_OPENAPI_OPERATION_ID = "purecipher.openapi.operation_id"
META_OPENAPI_METHOD = "purecipher.openapi.method"
META_OPENAPI_PATH = "purecipher.openapi.path"
META_OPENAPI_SERVER_URL = "purecipher.openapi.server_url"
META_OPENAPI_SPEC_SHA256 = "purecipher.openapi.spec_sha256"
META_OPENAPI_INPUT_SCHEMA = "purecipher.openapi.input_schema"
META_OPENAPI_OUTPUT_SCHEMA = "purecipher.openapi.output_schema"

PROVIDER_KIND_OPENAPI = "openapi"

# HTTP method → declarative access type used by the consent /
# provenance planes when summarising what the tool does.
_METHOD_TO_ACCESS_TYPE = {
    "GET": "read",
    "HEAD": "read",
    "OPTIONS": "read",
    "POST": "write",
    "PUT": "write",
    "PATCH": "write",
    "DELETE": "delete",
}

_TOOL_NAME_INVALID = re.compile(r"[^A-Za-z0-9_\-]+")


def sanitize_tool_name(raw: str) -> str:
    """Make ``raw`` safe for use as a registry tool name.

    The marketplace accepts names with letters, digits, underscores,
    and hyphens. We collapse any other characters down to a single
    hyphen, then collapse runs of hyphens back to one, and trim
    leading/trailing hyphens so a slugged operation name like
    ``GET /pets/{petId}`` round-trips to ``GET-pets-petId``.
    """
    if not raw:
        return "openapi-tool"
    cleaned = _TOOL_NAME_INVALID.sub("-", raw)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "openapi-tool"


def _server_pattern(server_url: str, path: str) -> str:
    """Build a resource_access glob from server + path.

    Path tokens become ``*`` so the consent graph can summarise
    "this tool reaches https://api.example.com/v1/pets/*" without
    pinning every individual ``petId``.
    """
    base = server_url.rstrip("/")
    if not path:
        return f"{base}/*"
    pattern = re.sub(r"\{[^}]+\}", "*", path)
    if not pattern.startswith("/"):
        pattern = "/" + pattern
    return f"{base}{pattern}"


def _data_classification_for_security(security_required: bool) -> DataClassification:
    """Pick a default classification.

    Operations gated by a security scheme typically handle
    ``CONFIDENTIAL`` material; truly public endpoints default to
    ``PUBLIC``. Publishers can promote to PII / PHI / FINANCIAL by
    re-publishing with an overridden manifest if the tool warrants it.
    """
    return (
        DataClassification.CONFIDENTIAL
        if security_required
        else DataClassification.PUBLIC
    )


def derive_tool_name(
    operation: OpenAPIOperationDetailed,
    *,
    prefix: str = "",
) -> str:
    """Pick a tool_name for a published OpenAPI operation.

    Prefers ``operationId`` (most authors set one and it's stable
    across spec versions). Falls back to ``METHOD-path`` if absent.
    The optional ``prefix`` (from the toolset record) lets a publisher
    avoid collisions with their existing FastMCP-published tools.
    """
    operation_id = (operation.get("operation_id") or "").strip()
    if operation_id:
        candidate = operation_id
    else:
        method = (operation.get("method") or "").upper()
        path = operation.get("path") or ""
        candidate = f"{method}-{path}"
    if prefix:
        candidate = f"{prefix.rstrip('-')}-{candidate}"
    return sanitize_tool_name(candidate)


def build_manifest_for_operation(
    operation: OpenAPIOperationDetailed,
    *,
    source: OpenAPISourceRecord,
    toolset: OpenAPIToolsetRecord,
    server_url: str,
    publisher_id: str,
    version: str = "0.0.0",
) -> SecurityManifest:
    """Build a :class:`SecurityManifest` for one OpenAPI operation.

    The manifest is intentionally lean — its ``metadata`` carries
    everything the executor needs to reconstruct the request
    (``source_id`` + ``operation_key`` is enough; the input/output
    schemas are duplicated into metadata so the public detail page
    can render an input form without refetching the raw spec).

    Permissions: ``NETWORK_ACCESS`` always (every OpenAPI tool calls
    out), plus a method-derived ``READ_RESOURCE``/``WRITE_RESOURCE``
    so the policy plane can dispatch on read-vs-write without
    re-parsing the operation.
    """
    method = (operation.get("method") or "GET").upper()
    path = operation.get("path") or ""
    operation_key = operation.get("operation_key") or f"{method} {path}"
    operation_id = operation.get("operation_id") or ""

    summary = (operation.get("summary") or "").strip()
    long_description = (operation.get("description") or "").strip()
    description_parts = [s for s in (summary, long_description) if s]
    if not description_parts:
        description_parts.append(f"OpenAPI operation {method} {path}")
    description = "\n\n".join(description_parts)

    # Permissions: always need network; map method → read/write.
    permissions: set[PermissionScope] = {PermissionScope.NETWORK_ACCESS}
    if method in {"GET", "HEAD", "OPTIONS"}:
        permissions.add(PermissionScope.READ_RESOURCE)
    elif method == "DELETE":
        permissions.add(PermissionScope.WRITE_RESOURCE)
    else:
        permissions.add(PermissionScope.WRITE_RESOURCE)

    # Resource access — one record describing the upstream URL pattern.
    access_type = _METHOD_TO_ACCESS_TYPE.get(method, "write")
    pattern = _server_pattern(server_url, path)
    parsed = urlparse(server_url)
    resource_desc = (
        f"{method} {path} on {parsed.hostname or server_url}"
        if path
        else f"{method} on {parsed.hostname or server_url}"
    )
    classification = _data_classification_for_security(bool(operation.get("security")))
    resource_access = [
        ResourceAccessDeclaration(
            resource_pattern=pattern,
            access_type=access_type,
            description=resource_desc,
            classification=classification,
        )
    ]

    # Data flows — a single in→out arrow representing the round-trip.
    # Even shallow this is useful: the consent graph and provenance
    # ledger render flows per tool, so the new listing isn't blank.
    data_flows: list[DataFlowDeclaration] = []
    if operation.get("request_body") or any(
        p.get("location") in {"path", "query", "body"}
        for p in operation.get("parameters") or []
    ):
        data_flows.append(
            DataFlowDeclaration(
                source="input.arguments",
                destination=f"upstream.{parsed.hostname or 'api'}",
                classification=classification,
                description=f"Tool arguments are sent to {pattern}.",
            )
        )
    if operation.get("output_schema") is not None:
        data_flows.append(
            DataFlowDeclaration(
                source=f"upstream.{parsed.hostname or 'api'}",
                destination="output.body",
                classification=classification,
                description="Upstream response body is returned to the caller.",
            )
        )

    tags_list = [str(t) for t in (operation.get("tags") or []) if t]
    tags_set: set[str] = set(tags_list)
    tags_set.add("openapi")

    metadata: dict[str, Any] = {
        META_PROVIDER_KIND: PROVIDER_KIND_OPENAPI,
        META_OPENAPI_SOURCE_ID: str(source.get("source_id") or ""),
        META_OPENAPI_TOOLSET_ID: str(toolset.get("toolset_id") or ""),
        META_OPENAPI_OPERATION_KEY: operation_key,
        META_OPENAPI_OPERATION_ID: operation_id,
        META_OPENAPI_METHOD: method,
        META_OPENAPI_PATH: path,
        META_OPENAPI_SERVER_URL: server_url,
        META_OPENAPI_SPEC_SHA256: str(source.get("spec_sha256") or ""),
        META_OPENAPI_INPUT_SCHEMA: operation.get("input_schema") or {},
        META_OPENAPI_OUTPUT_SCHEMA: operation.get("output_schema"),
    }

    return SecurityManifest(
        tool_name=derive_tool_name(
            operation, prefix=str(toolset.get("tool_name_prefix") or "")
        ),
        version=version or "0.0.0",
        author=publisher_id or "",
        description=description,
        permissions=permissions,
        data_flows=data_flows,
        resource_access=resource_access,
        idempotent=method in {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"},
        deterministic=method in {"GET", "HEAD", "OPTIONS"},
        requires_consent=bool(operation.get("security")),
        tags=tags_set,
        metadata=metadata,
    )


def build_listing_payload(
    operation: OpenAPIOperationDetailed,
    *,
    source: OpenAPISourceRecord,
    toolset: OpenAPIToolsetRecord,
    server_url: str,
    publisher_id: str,
    version: str = "0.0.0",
) -> dict[str, Any]:
    """Build the complete kwargs dict for ``ToolMarketplace.publish``.

    Returned shape mirrors the ``publish`` signature so the registry
    can splat it directly. The bridge keeps every operation as its own
    listing — toolsets are a publisher-side grouping, not a marketplace
    concept.
    """
    manifest = build_manifest_for_operation(
        operation,
        source=source,
        toolset=toolset,
        server_url=server_url,
        publisher_id=publisher_id,
        version=version,
    )
    operation_id = operation.get("operation_id") or ""
    summary = (operation.get("summary") or "").strip()
    display_name = summary or operation_id or manifest.tool_name

    return {
        "tool_name": manifest.tool_name,
        "display_name": display_name,
        "description": manifest.description,
        "version": manifest.version,
        "author": publisher_id,
        "manifest": manifest,
        "tags": set(manifest.tags),
        "metadata": dict(manifest.metadata),
    }
