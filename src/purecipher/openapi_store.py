"""OpenAPI ingestion and toolset storage for the PureCipher registry.

The store layer accepts JSON or YAML OpenAPI payloads (3.0 / 3.1),
extracts the operation surface, and persists raw + selected
operations to the registry SQLite file when one is available.

There are two extractor surfaces:

* :func:`extract_openapi_operations` — the original shallow walker.
  Returns method + path + operationId + summary + description + tags.
  Kept verbatim so existing callers (the wizard, ingest route) don't
  break.
* :func:`extract_openapi_operations_detailed` — Iter 13.1. Walks
  parameters and request/response bodies, resolves local
  ``$ref`` pointers (``#/components/schemas/…``), normalises
  ``allOf`` / ``oneOf`` / ``anyOf`` / ``nullable``, and produces a
  per-operation ``input_schema`` (JSON Schema covering path / query /
  header / cookie params + body) and ``output_schema`` (success
  response). The downstream executor + tool-listing bridge consume
  this richer shape.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

HttpMethod = Literal["get", "post", "put", "patch", "delete", "head", "options"]
ParamLocation = Literal["path", "query", "header", "cookie"]
SecuritySchemeKind = Literal["apiKey", "http", "oauth2", "openIdConnect", "mutualTLS"]
ApiKeyLocation = Literal["query", "header", "cookie"]


class OpenAPIOperation(TypedDict, total=False):
    operation_key: str
    method: HttpMethod
    path: str
    operation_id: str
    summary: str
    description: str
    tags: list[str]


class OpenAPIParameter(TypedDict, total=False):
    name: str
    location: ParamLocation
    required: bool
    description: str
    schema: dict[str, Any]


class OpenAPIRequestBody(TypedDict, total=False):
    required: bool
    description: str
    content_type: str
    schema: dict[str, Any]


class OpenAPIResponse(TypedDict, total=False):
    status_code: str
    description: str
    content_type: str
    schema: dict[str, Any]


class OpenAPIOperationDetailed(TypedDict, total=False):
    operation_key: str
    method: HttpMethod
    path: str
    operation_id: str
    summary: str
    description: str
    tags: list[str]
    parameters: list[OpenAPIParameter]
    request_body: OpenAPIRequestBody | None
    responses: list[OpenAPIResponse]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    security: list[dict[str, list[str]]]
    server_urls: list[str]


class SecurityScheme(TypedDict, total=False):
    """Normalised view of a single ``components.securitySchemes`` entry.

    All five OpenAPI scheme kinds collapse into this one shape. Only
    the fields relevant to the chosen ``kind`` are populated; consumers
    should switch on ``kind`` before reading kind-specific fields.
    """

    scheme_name: str
    kind: SecuritySchemeKind
    description: str
    # apiKey kind
    api_key_name: str
    api_key_in: ApiKeyLocation
    # http kind
    http_scheme: str
    bearer_format: str
    # oauth2 kind — flow_type -> {tokenUrl, authorizationUrl, refreshUrl, scopes}
    oauth_flows: dict[str, dict[str, Any]]
    # openIdConnect kind
    open_id_connect_url: str


class SecurityRequirement(TypedDict, total=False):
    """Resolved view of one entry in an operation's ``security`` array.

    A ``security`` list element is shaped ``{schemeName: [scopes]}``;
    after resolution against the document's ``securitySchemes`` map we
    surface the underlying scheme alongside the requested scopes.
    """

    scheme_name: str
    scopes: list[str]
    scheme: SecurityScheme | None


class OpenAPISourceRecord(TypedDict, total=False):
    source_id: str
    created_at: float
    publisher_id: str
    title: str
    source_url: str
    spec_json: dict[str, Any]
    spec_sha256: str
    operation_count: int
    # Iter 13.2: parsed view of components.securitySchemes — purely
    # derived from spec_json so it stays in sync via re-extraction.
    security_schemes: dict[str, SecurityScheme]


class OpenAPIToolsetRecord(TypedDict, total=False):
    toolset_id: str
    created_at: float
    publisher_id: str
    source_id: str
    title: str
    selected_operations: list[str]
    tool_name_prefix: str
    metadata: dict[str, Any]


class OpenAPICredentialRecord(TypedDict, total=False):
    """Stored credential bound to one ``(publisher, source, scheme)`` triple.

    The ``secret`` field carries plaintext credential material — this
    shape is returned only to internal callers (e.g. the executor in
    Iter 13.3) and never serialised over HTTP. Use
    :class:`OpenAPICredentialPublic` for any external surface.
    """

    credential_id: str
    created_at: float
    updated_at: float
    publisher_id: str
    source_id: str
    scheme_name: str
    scheme_kind: SecuritySchemeKind
    label: str
    secret: dict[str, Any]


class OpenAPICredentialPublic(TypedDict, total=False):
    """Sanitised view of a credential — all secret material redacted.

    The ``secret_hint`` field surfaces a non-reversible fingerprint
    (last four characters of the secret token, masked username, etc.)
    so the UI can confirm "this is the credential you stored" without
    exposing the value.
    """

    credential_id: str
    created_at: float
    updated_at: float
    publisher_id: str
    source_id: str
    scheme_name: str
    scheme_kind: SecuritySchemeKind
    label: str
    secret_hint: str


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> float:
    return float(time.time())


def _coerce_openapi_json(raw_text: str) -> dict[str, Any]:
    """Back-compat alias: parse strict JSON only.

    Pre-Iter-13.1 callers expected a JSON-only path; preserved so
    existing tests and routes that still call this name continue to
    behave identically.
    """
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAPI document is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must decode to a JSON object.")
    return payload


def _coerce_openapi_doc(raw_text: str) -> dict[str, Any]:
    """Parse an OpenAPI document supplied as either JSON or YAML.

    Strategy: try JSON first (cheap, strict); on JSONDecodeError fall
    back to YAML via PyYAML's safe loader. PyYAML's ``safe_load`` is
    a strict superset of JSON, so a YAML-only spec round-trips
    correctly. Only ``dict`` payloads are accepted — top-level lists
    or scalars are rejected with a clear error.
    """
    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            import yaml  # local import; only needed for YAML inputs

            payload = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:  # type: ignore[name-defined]
            raise ValueError(
                f"OpenAPI document is neither valid JSON nor YAML: {exc}"
            ) from exc
        except ImportError as exc:  # pragma: no cover — pyyaml is a hard dep
            raise ValueError(
                "PyYAML is required to ingest YAML OpenAPI documents."
            ) from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must decode to a JSON/YAML object.")
    return payload


def extract_openapi_operations(spec: dict[str, Any]) -> list[OpenAPIOperation]:
    """Extract operation inventory from an OpenAPI document.

    MVP: does not resolve $refs or deeply inspect schemas.
    """

    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return []

    out: list[OpenAPIOperation] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            m = str(method).lower()
            if m not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(op, dict):
                continue

            operation_id = str(op.get("operationId") or "").strip()
            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            tags = op.get("tags")
            tags_list = [str(t) for t in tags] if isinstance(tags, list) else []

            operation_key = operation_id or f"{m.upper()} {path}"
            out.append(
                {
                    "operation_key": operation_key,
                    "method": m,  # type: ignore[typeddict-item]
                    "path": str(path),
                    "operation_id": operation_id,
                    "summary": summary,
                    "description": description,
                    "tags": tags_list,
                }
            )

    # Stable ordering for UI and tests
    out.sort(
        key=lambda item: (
            item.get("path", ""),
            item.get("method", ""),
            item.get("operation_key", ""),
        )
    )
    return out


# ---------------------------------------------------------------------------
# Detailed extractor (Iter 13.1) — walks the spec deeply.
# ---------------------------------------------------------------------------

_REF_PREFIX = "#/"
_JSON_CONTENT_TYPES_PREFERRED = (
    "application/json",
    "application/vnd.api+json",
    "application/problem+json",
)
_VALID_PARAM_LOCATIONS: frozenset[str] = frozenset(
    {"path", "query", "header", "cookie"}
)
_VALID_HTTP_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options"}
)
_MAX_REF_DEPTH = 64


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> dict[str, Any] | None:
    """Resolve a local JSON pointer like ``#/components/schemas/Pet``.

    Returns ``None`` for non-local refs (e.g. ``http://...``), missing
    pointers, or non-object targets. JSON-pointer escapes (``~0`` → ``~``,
    ``~1`` → ``/``) are decoded.
    """
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        return None
    parts = ref[len(_REF_PREFIX) :].split("/") if ref != _REF_PREFIX else []
    cursor: Any = spec
    for raw in parts:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cursor, dict) and token in cursor:
            cursor = cursor[token]
        elif isinstance(cursor, list):
            try:
                idx = int(token)
            except ValueError:
                return None
            if 0 <= idx < len(cursor):
                cursor = cursor[idx]
            else:
                return None
        else:
            return None
    return cursor if isinstance(cursor, dict) else None


def _merge_all_of_parts(parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Shallow merge ``allOf`` parts.

    Object-y fields (``properties``) are unioned; ``required`` is unioned
    while preserving order; everything else takes the first occurrence so
    later parts can override but not silently clobber.
    """
    merged: dict[str, Any] = {}
    props: dict[str, Any] = {}
    required: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key, value in part.items():
            if key == "properties" and isinstance(value, dict):
                props.update(value)
            elif key == "required" and isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item not in required:
                        required.append(item)
            elif key not in merged:
                merged[key] = value
    if props:
        merged["properties"] = props
    if required:
        merged["required"] = required
    return merged


def _walk_schema(
    spec: dict[str, Any],
    schema: Any,
    seen: frozenset[str] | None = None,
    depth: int = 0,
) -> Any:
    """Resolve refs and normalise an OpenAPI schema fragment.

    Returns a JSON Schema-compatible dict. ``allOf`` parts are merged in
    place; ``oneOf`` / ``anyOf`` / ``items`` / ``properties`` /
    ``additionalProperties`` are walked recursively. ``nullable: true``
    (OpenAPI 3.0) is converted to ``type: [..., "null"]`` so 3.0 and
    3.1 specs land in the same shape downstream.

    Cycles are broken by tracking seen ``$ref`` pointers — when a ref
    is re-entered, the original ``$ref`` is preserved so consumers can
    still resolve it lazily without an infinite expansion.
    """
    if seen is None:
        seen = frozenset()
    if depth > _MAX_REF_DEPTH:
        return schema if isinstance(schema, dict) else {}
    if not isinstance(schema, dict):
        return schema

    # 1. Resolve top-level $ref
    ref = schema.get("$ref") if isinstance(schema.get("$ref"), str) else None
    if ref:
        if ref in seen:
            return {"$ref": ref}
        target = _resolve_local_ref(spec, ref)
        if target is None:
            return {"$ref": ref}
        return _walk_schema(spec, target, seen | {ref}, depth + 1)

    out: dict[str, Any] = {}

    # 2. Resolve allOf first so sibling fields can override
    if isinstance(schema.get("allOf"), list):
        resolved_parts = [
            _walk_schema(spec, part, seen, depth + 1) for part in schema["allOf"]
        ]
        merged = _merge_all_of_parts([p for p in resolved_parts if isinstance(p, dict)])
        out.update(merged)

    # 3. Walk remaining keys
    for key, value in schema.items():
        if key in {"allOf", "$ref"}:
            continue
        if key in {"oneOf", "anyOf"} and isinstance(value, list):
            out[key] = [_walk_schema(spec, item, seen, depth + 1) for item in value]
        elif key == "properties" and isinstance(value, dict):
            walked = {
                pname: _walk_schema(spec, pval, seen, depth + 1)
                for pname, pval in value.items()
            }
            existing = out.get("properties")
            if isinstance(existing, dict):
                # allOf-supplied properties merge with explicit ones; the
                # explicit definition wins for any name collisions.
                merged_props = dict(existing)
                merged_props.update(walked)
                out["properties"] = merged_props
            else:
                out["properties"] = walked
        elif key == "items":
            if isinstance(value, list):
                out[key] = [_walk_schema(spec, item, seen, depth + 1) for item in value]
            else:
                out[key] = _walk_schema(spec, value, seen, depth + 1)
        elif key == "additionalProperties" and isinstance(value, dict):
            out[key] = _walk_schema(spec, value, seen, depth + 1)
        elif key == "required" and isinstance(value, list):
            existing = out.get("required")
            existing_list = list(existing) if isinstance(existing, list) else []
            for item in value:
                if isinstance(item, str) and item not in existing_list:
                    existing_list.append(item)
            out["required"] = existing_list
        elif key == "not" and isinstance(value, dict):
            out[key] = _walk_schema(spec, value, seen, depth + 1)
        else:
            out[key] = value

    # 4. Normalise nullable (OpenAPI 3.0) → type union (JSON Schema 2020-12)
    if out.pop("nullable", False) is True:
        existing_type = out.get("type")
        if isinstance(existing_type, str) and existing_type != "null":
            out["type"] = [existing_type, "null"]
        elif isinstance(existing_type, list):
            if "null" not in existing_type:
                out["type"] = [*existing_type, "null"]
        else:
            # No type set; nullability alone is preserved as a hint.
            out["type"] = ["null"]

    return out


def _pick_content_entry(content: Any) -> tuple[str, dict[str, Any]] | None:
    """Pick the most JSON-flavoured entry from an OpenAPI content map."""
    if not isinstance(content, dict) or not content:
        return None
    for ct in _JSON_CONTENT_TYPES_PREFERRED:
        entry = content.get(ct)
        if isinstance(entry, dict):
            return ct, entry
    # Fall through: pick any content type with a schema-bearing entry.
    for ct, entry in content.items():
        if isinstance(entry, dict):
            return str(ct), entry
    return None


def _pick_success_response(
    responses: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Pick the primary success response or fall back to ``default``."""
    if not isinstance(responses, dict):
        return None
    for code in ("200", "201", "202"):
        entry = responses.get(code)
        if isinstance(entry, dict):
            return code, entry
    for code in ("2XX", "2xx"):
        entry = responses.get(code)
        if isinstance(entry, dict):
            return code, entry
    for code, entry in responses.items():
        if isinstance(code, str) and code.startswith("2") and isinstance(entry, dict):
            return code, entry
    default_entry = responses.get("default")
    if isinstance(default_entry, dict):
        return "default", default_entry
    return None


def _resolve_param(spec: dict[str, Any], raw: Any) -> dict[str, Any] | None:
    """Resolve a parameter, following a top-level ``$ref`` if present."""
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("$ref"), str):
        resolved = _resolve_local_ref(spec, raw["$ref"])
        return resolved if isinstance(resolved, dict) else None
    return raw


def _build_input_schema(
    parameters: list[OpenAPIParameter],
    request_body: OpenAPIRequestBody | None,
) -> dict[str, Any]:
    """Build a JSON Schema describing an operation's inputs.

    Inputs are grouped by their HTTP location so the executor can
    dispatch path interpolation, query string assembly, header writes,
    and body serialisation independently::

        {"type": "object",
         "properties": {
           "path":   {"type": "object", "properties": {...}, "required": [...]},
           "query":  {"type": "object", "properties": {...}, "required": [...]},
           "header": {"type": "object", "properties": {...}, "required": [...]},
           "cookie": {"type": "object", "properties": {...}, "required": [...]},
           "body":   <walked body schema> }}
    """
    sections: dict[str, dict[str, Any]] = {}
    section_required: dict[str, list[str]] = {}
    for param in parameters:
        loc = param.get("location")
        if loc not in _VALID_PARAM_LOCATIONS:
            continue
        section = sections.setdefault(
            loc, {"type": "object", "properties": {}, "additionalProperties": False}
        )
        props = section.setdefault("properties", {})
        p_schema = param.get("schema") or {}
        if isinstance(p_schema, dict):
            sub_schema = dict(p_schema)
            if param.get("description") and "description" not in sub_schema:
                sub_schema["description"] = param["description"]
            props[param["name"]] = sub_schema
        else:
            props[param["name"]] = {}
        if param.get("required"):
            section_required.setdefault(loc, []).append(param["name"])

    for loc, names in section_required.items():
        sections[loc]["required"] = names

    properties: dict[str, Any] = dict(sections)
    required: list[str] = []
    # Path params are inherently required by the OpenAPI spec, so the
    # whole "path" group is required if it exists at all.
    if "path" in properties:
        required.append("path")
    if request_body is not None:
        body_schema = request_body.get("schema") or {}
        properties["body"] = body_schema if isinstance(body_schema, dict) else {}
        if request_body.get("required"):
            required.append("body")

    out: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        out["required"] = required
    return out


def extract_openapi_operations_detailed(
    spec: dict[str, Any],
) -> list[OpenAPIOperationDetailed]:
    """Walk an OpenAPI document into a per-operation detailed surface.

    Resolves local ``$ref`` pointers, normalises ``allOf`` / ``oneOf`` /
    ``anyOf`` / ``nullable``, and produces an aggregated JSON Schema
    for each operation's inputs (path / query / header / cookie + body)
    and success-response output. Operation-level ``security`` and
    ``servers`` override the document-level fallback.

    Compared to the shallow :func:`extract_openapi_operations`, this
    walker is what the executor uses to validate arguments and the
    public detail page consumes to surface a real input form.
    """
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return []

    top_security_raw = spec.get("security")
    top_security_list: list[dict[str, list[str]]] = (
        [s for s in top_security_raw if isinstance(s, dict)]
        if isinstance(top_security_raw, list)
        else []
    )
    top_servers_raw = spec.get("servers")
    top_server_urls: list[str] = []
    if isinstance(top_servers_raw, list):
        for server in top_servers_raw:
            if isinstance(server, dict):
                url = server.get("url")
                if isinstance(url, str) and url:
                    top_server_urls.append(url)

    out: list[OpenAPIOperationDetailed] = []

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_level_params_raw = path_item.get("parameters")
        path_level_params_list = (
            list(path_level_params_raw)
            if isinstance(path_level_params_raw, list)
            else []
        )
        path_servers_raw = path_item.get("servers")
        path_server_urls: list[str] = []
        if isinstance(path_servers_raw, list):
            for server in path_servers_raw:
                if isinstance(server, dict):
                    url = server.get("url")
                    if isinstance(url, str) and url:
                        path_server_urls.append(url)

        for method, op in path_item.items():
            m = str(method).lower()
            if m not in _VALID_HTTP_METHODS:
                continue
            if not isinstance(op, dict):
                continue

            operation_id = str(op.get("operationId") or "").strip()
            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            tags_raw = op.get("tags")
            tags_list = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []
            operation_key = operation_id or f"{m.upper()} {path}"

            # Combine path-level + operation-level parameters.
            # OpenAPI rule: an operation-level parameter overrides a
            # path-level parameter sharing the same (name, location).
            op_params_raw = op.get("parameters")
            op_params_list = (
                list(op_params_raw) if isinstance(op_params_raw, list) else []
            )
            combined_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            ordered_keys: list[tuple[str, str]] = []
            for raw_param in path_level_params_list + op_params_list:
                resolved = _resolve_param(spec, raw_param)
                if resolved is None:
                    continue
                p_name = str(resolved.get("name") or "").strip()
                p_in = str(resolved.get("in") or "").strip().lower()
                if not p_name or p_in not in _VALID_PARAM_LOCATIONS:
                    continue
                key = (p_name, p_in)
                if key not in combined_by_key:
                    ordered_keys.append(key)
                combined_by_key[key] = resolved

            params: list[OpenAPIParameter] = []
            for key in ordered_keys:
                resolved = combined_by_key[key]
                p_name, p_in = key
                # Path params are always required per the OpenAPI spec.
                p_required = bool(resolved.get("required") or p_in == "path")
                p_description = str(resolved.get("description") or "").strip()
                p_schema_raw = resolved.get("schema")
                p_schema_walked: Any = (
                    _walk_schema(spec, p_schema_raw)
                    if isinstance(p_schema_raw, dict)
                    else {}
                )
                params.append(
                    {
                        "name": p_name,
                        "location": p_in,  # type: ignore[typeddict-item]
                        "required": p_required,
                        "description": p_description,
                        "schema": (
                            p_schema_walked if isinstance(p_schema_walked, dict) else {}
                        ),
                    }
                )

            # Request body
            request_body: OpenAPIRequestBody | None = None
            body_obj_raw = op.get("requestBody")
            if isinstance(body_obj_raw, dict) and isinstance(
                body_obj_raw.get("$ref"), str
            ):
                body_obj_raw = _resolve_local_ref(spec, body_obj_raw["$ref"])
            if isinstance(body_obj_raw, dict):
                content = body_obj_raw.get("content")
                picked_body = (
                    _pick_content_entry(content) if isinstance(content, dict) else None
                )
                if picked_body is not None:
                    body_ct, body_entry = picked_body
                    body_schema_raw = body_entry.get("schema")
                    body_schema_walked: dict[str, Any] = {}
                    if isinstance(body_schema_raw, dict):
                        walked = _walk_schema(spec, body_schema_raw)
                        if isinstance(walked, dict):
                            body_schema_walked = walked
                    request_body = {
                        "required": bool(body_obj_raw.get("required") or False),
                        "description": str(
                            body_obj_raw.get("description") or ""
                        ).strip(),
                        "content_type": body_ct,
                        "schema": body_schema_walked,
                    }

            # Responses (full list + chosen primary)
            responses_out: list[OpenAPIResponse] = []
            output_schema: dict[str, Any] | None = None
            responses_raw = op.get("responses")
            if isinstance(responses_raw, dict):
                for code, raw_resp in responses_raw.items():
                    if isinstance(raw_resp, dict) and isinstance(
                        raw_resp.get("$ref"), str
                    ):
                        raw_resp = _resolve_local_ref(spec, raw_resp["$ref"])
                    if not isinstance(raw_resp, dict):
                        continue
                    r_description = str(raw_resp.get("description") or "").strip()
                    r_content = raw_resp.get("content")
                    r_pick = (
                        _pick_content_entry(r_content)
                        if isinstance(r_content, dict)
                        else None
                    )
                    r_ct = ""
                    r_schema_walked: dict[str, Any] = {}
                    if r_pick is not None:
                        r_ct, r_entry = r_pick
                        r_schema_raw = r_entry.get("schema")
                        if isinstance(r_schema_raw, dict):
                            walked = _walk_schema(spec, r_schema_raw)
                            if isinstance(walked, dict):
                                r_schema_walked = walked
                    responses_out.append(
                        {
                            "status_code": str(code),
                            "description": r_description,
                            "content_type": r_ct,
                            "schema": r_schema_walked,
                        }
                    )
                primary = _pick_success_response(responses_raw)
                if primary is not None:
                    _, raw_resp = primary
                    if isinstance(raw_resp, dict) and isinstance(
                        raw_resp.get("$ref"), str
                    ):
                        raw_resp = _resolve_local_ref(spec, raw_resp["$ref"])
                    if isinstance(raw_resp, dict):
                        r_content = raw_resp.get("content")
                        r_pick = (
                            _pick_content_entry(r_content)
                            if isinstance(r_content, dict)
                            else None
                        )
                        if r_pick is not None:
                            _, r_entry = r_pick
                            r_schema_raw = r_entry.get("schema")
                            if isinstance(r_schema_raw, dict):
                                walked = _walk_schema(spec, r_schema_raw)
                                if isinstance(walked, dict):
                                    output_schema = walked

            # Aggregated input schema for executors / form rendering
            input_schema = _build_input_schema(params, request_body)

            # Security: operation-level overrides top-level (an empty
            # array is a valid override that disables auth requirements).
            op_security_raw = op.get("security")
            if isinstance(op_security_raw, list):
                op_security_list: list[dict[str, list[str]]] = [
                    s for s in op_security_raw if isinstance(s, dict)
                ]
            else:
                op_security_list = list(top_security_list)

            # Server resolution order: operation-level wins over
            # path-level, which wins over the document-level fallback.
            op_servers_raw = op.get("servers")
            op_server_urls: list[str] = []
            if isinstance(op_servers_raw, list) and op_servers_raw:
                for server in op_servers_raw:
                    if isinstance(server, dict):
                        url = server.get("url")
                        if isinstance(url, str) and url:
                            op_server_urls.append(url)
            elif path_server_urls:
                op_server_urls = list(path_server_urls)
            else:
                op_server_urls = list(top_server_urls)

            entry: OpenAPIOperationDetailed = {
                "operation_key": operation_key,
                "method": m,  # type: ignore[typeddict-item]
                "path": str(path),
                "operation_id": operation_id,
                "summary": summary,
                "description": description,
                "tags": tags_list,
                "parameters": params,
                "request_body": request_body,
                "responses": responses_out,
                "input_schema": input_schema,
                "output_schema": output_schema,
                "security": op_security_list,
                "server_urls": op_server_urls,
            }
            out.append(entry)

    out.sort(
        key=lambda item: (
            item.get("path", ""),
            item.get("method", ""),
            item.get("operation_key", ""),
        )
    )
    return out


# ---------------------------------------------------------------------------
# Security scheme parsing (Iter 13.2)
# ---------------------------------------------------------------------------

_VALID_SECURITY_KINDS: frozenset[str] = frozenset(
    {"apiKey", "http", "oauth2", "openIdConnect", "mutualTLS"}
)
_VALID_API_KEY_LOCATIONS: frozenset[str] = frozenset({"query", "header", "cookie"})
_VALID_OAUTH_FLOWS: frozenset[str] = frozenset(
    {"implicit", "password", "clientCredentials", "authorizationCode"}
)


def _parse_oauth_flows(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalise an OAuth2 ``flows`` block.

    Returns a dict keyed by flow type with each value containing only
    the standard fields (``tokenUrl``, ``authorizationUrl``,
    ``refreshUrl``, ``scopes``). Unknown flow types or junk values are
    dropped so downstream UI doesn't have to defend against malformed
    specs.
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for flow_name, flow_def in raw.items():
        if flow_name not in _VALID_OAUTH_FLOWS or not isinstance(flow_def, dict):
            continue
        scopes_raw = flow_def.get("scopes")
        scopes: dict[str, str] = {}
        if isinstance(scopes_raw, dict):
            for scope_name, scope_desc in scopes_raw.items():
                scopes[str(scope_name)] = str(scope_desc or "")
        normalised: dict[str, Any] = {"scopes": scopes}
        for key in ("tokenUrl", "authorizationUrl", "refreshUrl"):
            val = flow_def.get(key)
            if isinstance(val, str) and val:
                normalised[key] = val
        out[flow_name] = normalised
    return out


def _parse_security_scheme(scheme_name: str, raw: Any) -> SecurityScheme | None:
    """Normalise a single ``components.securitySchemes`` entry."""
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("type") or "").strip()
    if kind not in _VALID_SECURITY_KINDS:
        return None
    out: SecurityScheme = {
        "scheme_name": scheme_name,
        "kind": kind,  # type: ignore[typeddict-item]
        "description": str(raw.get("description") or "").strip(),
    }
    if kind == "apiKey":
        api_name = str(raw.get("name") or "").strip()
        api_in = str(raw.get("in") or "").strip().lower()
        if not api_name or api_in not in _VALID_API_KEY_LOCATIONS:
            # Malformed apiKey scheme — drop it so callers can't
            # accidentally produce an invalid HTTP request.
            return None
        out["api_key_name"] = api_name
        out["api_key_in"] = api_in  # type: ignore[typeddict-item]
    elif kind == "http":
        http_scheme = str(raw.get("scheme") or "").strip().lower()
        if not http_scheme:
            return None
        out["http_scheme"] = http_scheme
        bearer_format = str(raw.get("bearerFormat") or "").strip()
        if bearer_format:
            out["bearer_format"] = bearer_format
    elif kind == "oauth2":
        out["oauth_flows"] = _parse_oauth_flows(raw.get("flows"))
    elif kind == "openIdConnect":
        url = str(raw.get("openIdConnectUrl") or "").strip()
        if not url:
            return None
        out["open_id_connect_url"] = url
    # mutualTLS has no extra fields per the OpenAPI 3.1 spec.
    return out


def extract_security_schemes(spec: dict[str, Any]) -> dict[str, SecurityScheme]:
    """Walk ``components.securitySchemes`` into a normalised map.

    Returns ``{scheme_name: SecurityScheme}``. Local ``$ref`` pointers
    inside the securitySchemes map are followed; malformed or unknown
    scheme entries are silently skipped so the caller receives only
    actionable scheme records.
    """
    components = spec.get("components")
    if not isinstance(components, dict):
        return {}
    raw_map = components.get("securitySchemes")
    if not isinstance(raw_map, dict):
        return {}

    out: dict[str, SecurityScheme] = {}
    for scheme_name, raw in raw_map.items():
        if not isinstance(scheme_name, str) or not scheme_name.strip():
            continue
        target: Any = raw
        if isinstance(target, dict) and isinstance(target.get("$ref"), str):
            target = _resolve_local_ref(spec, target["$ref"])
        parsed = _parse_security_scheme(scheme_name, target)
        if parsed is not None:
            out[scheme_name] = parsed
    return out


def resolve_operation_security(
    operation_security: list[dict[str, list[str]]] | None,
    scheme_map: dict[str, SecurityScheme],
) -> list[list[SecurityRequirement]]:
    """Resolve an operation's ``security`` array against the scheme map.

    OpenAPI semantics: the outer list is OR'd (any one of these
    requirement sets satisfies the operation), the inner mapping is
    AND'd (every scheme listed must be supplied). The shape returned
    preserves both: a list of "alternative" requirement groups, each
    group a list of resolved :class:`SecurityRequirement` records.

    A scheme reference that doesn't exist in ``scheme_map`` still
    appears in the output with ``scheme=None`` so callers can flag it
    as missing rather than silently drop the requirement.
    """
    if not operation_security:
        return []
    alternatives: list[list[SecurityRequirement]] = []
    for requirement in operation_security:
        if not isinstance(requirement, dict):
            continue
        group: list[SecurityRequirement] = []
        for scheme_name, scopes_raw in requirement.items():
            scopes = (
                [str(s) for s in scopes_raw] if isinstance(scopes_raw, list) else []
            )
            group.append(
                {
                    "scheme_name": str(scheme_name),
                    "scopes": scopes,
                    "scheme": scheme_map.get(str(scheme_name)),
                }
            )
        alternatives.append(group)
    return alternatives


_CREDENTIAL_KEY_INFO = b"purecipher-openapi-cred-v1"


def _derive_credential_key(secret: bytes | str | None) -> bytes | None:
    """Derive a stable Fernet key from the registry signing secret.

    Returns ``None`` if no secret was provided — credential storage
    will refuse encrypt/decrypt calls in that case rather than silently
    persist plaintext.
    """
    if secret is None:
        return None
    if isinstance(secret, str):
        if not secret:
            return None
        secret = secret.encode("utf-8")
    if not secret:
        return None
    digest = hmac.new(secret, _CREDENTIAL_KEY_INFO, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest)


def _credential_secret_hint(scheme_kind: str, secret: dict[str, Any]) -> str:
    """Render a non-reversible hint for the UI.

    The hint reveals just enough to confirm "this is the value you
    stored" (last 4 chars of a token, masked username, etc.) without
    enabling reconstruction. Always safe for the public API surface.
    """
    if scheme_kind == "apiKey":
        token = str(secret.get("api_key") or "")
        return f"…{token[-4:]}" if len(token) >= 4 else "set"
    if scheme_kind == "http":
        http_scheme = str(secret.get("http_scheme") or "").lower()
        if http_scheme == "bearer":
            token = str(secret.get("bearer_token") or "")
            return f"bearer …{token[-4:]}" if len(token) >= 4 else "bearer set"
        if http_scheme == "basic":
            user = str(secret.get("username") or "")
            return f"basic {user[:2]}***" if user else "basic set"
        return "set"
    if scheme_kind == "oauth2":
        token = str(secret.get("access_token") or "")
        if token:
            return f"…{token[-4:]}" if len(token) >= 4 else "set"
        client_id = str(secret.get("client_id") or "")
        return f"client_id {client_id[:4]}***" if client_id else "set"
    if scheme_kind == "openIdConnect":
        token = str(secret.get("id_token") or "")
        return f"…{token[-4:]}" if len(token) >= 4 else "set"
    return "set"


@dataclass
class OpenAPIStore:
    """Persists OpenAPI sources, toolset selections, and credentials.

    Credentials are encrypted at rest with Fernet, keyed off the
    registry's signing secret (so we don't add a new secret-management
    surface). Construct with ``credential_key`` set to the registry
    signing secret to enable credential CRUD; without it, credential
    methods raise ``RuntimeError`` rather than silently store plaintext.
    """

    db_path: str | None = None
    ensure_schema: bool = True
    credential_key: bytes | str | None = None

    def __post_init__(self) -> None:
        self._memory_sources: dict[str, OpenAPISourceRecord] = {}
        self._memory_toolsets: dict[str, OpenAPIToolsetRecord] = {}
        self._memory_credentials: dict[str, OpenAPICredentialRecord] = {}
        self._shared_conn: sqlite3.Connection | None = None
        self._fernet_key: bytes | None = _derive_credential_key(self.credential_key)
        if self.db_path:
            if self.db_path == ":memory:":
                # Keep a single connection so tables persist.
                self._shared_conn = sqlite3.connect(
                    self.db_path, check_same_thread=False
                )
            if self.ensure_schema:
                self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path:
            raise RuntimeError("OpenAPIStore is not configured with a sqlite path.")
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self.db_path)

    def _ensure_tables(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_openapi_sources (
              source_id TEXT PRIMARY KEY,
              created_at REAL NOT NULL,
              publisher_id TEXT NOT NULL,
              title TEXT NOT NULL,
              source_url TEXT NOT NULL,
              spec_json TEXT NOT NULL,
              spec_sha256 TEXT NOT NULL,
              operation_count INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_openapi_toolsets (
              toolset_id TEXT PRIMARY KEY,
              created_at REAL NOT NULL,
              publisher_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              title TEXT NOT NULL,
              selected_operations_json TEXT NOT NULL,
              tool_name_prefix TEXT NOT NULL,
              metadata_json TEXT NOT NULL
            );
            """
        )
        # Credentials (Iter 13.2). The (publisher_id, source_id,
        # scheme_name) triple is unique — one credential per scheme per
        # publisher per source — so a re-store is an upsert.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_openapi_credentials (
              credential_id TEXT PRIMARY KEY,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              publisher_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              scheme_name TEXT NOT NULL,
              scheme_kind TEXT NOT NULL,
              label TEXT NOT NULL,
              secret_hint TEXT NOT NULL,
              secret_ciphertext TEXT NOT NULL,
              UNIQUE (publisher_id, source_id, scheme_name)
            );
            """
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()

    def ingest_source(
        self,
        *,
        publisher_id: str,
        title: str,
        source_url: str = "",
        raw_text: str,
    ) -> tuple[OpenAPISourceRecord, list[OpenAPIOperation]]:
        # Iter 13.1.2: accept YAML or JSON. ``_coerce_openapi_doc`` is a
        # strict-superset of the old JSON-only path, so existing JSON
        # callers continue to work unchanged.
        spec = _coerce_openapi_doc(raw_text)
        ops = extract_openapi_operations(spec)
        spec_sha = _sha256_text(json.dumps(spec, sort_keys=True, separators=(",", ":")))
        source_id = f"oas_{spec_sha[:24]}"
        # Iter 13.2: extract security schemes alongside operations so
        # the credential UI can drive off the source record without
        # re-walking the raw spec.
        schemes = extract_security_schemes(spec)
        record: OpenAPISourceRecord = {
            "source_id": source_id,
            "created_at": _now(),
            "publisher_id": publisher_id,
            "title": title.strip() or "OpenAPI source",
            "source_url": source_url.strip(),
            "spec_json": spec,
            "spec_sha256": spec_sha,
            "operation_count": len(ops),
            "security_schemes": schemes,
        }

        if not self.db_path:
            self._memory_sources[source_id] = record
            return record, ops

        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO purecipher_openapi_sources
              (source_id, created_at, publisher_id, title, source_url, spec_json, spec_sha256, operation_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                record["created_at"],
                record["publisher_id"],
                record["title"],
                record["source_url"],
                json.dumps(spec),
                record["spec_sha256"],
                record["operation_count"],
            ),
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return record, ops

    def create_toolset(
        self,
        *,
        publisher_id: str,
        source_id: str,
        title: str,
        selected_operations: list[str],
        tool_name_prefix: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OpenAPIToolsetRecord:
        toolset_id = f"toolset_{hashlib.sha256((publisher_id + ':' + source_id + ':' + title).encode('utf-8')).hexdigest()[:18]}"
        record: OpenAPIToolsetRecord = {
            "toolset_id": toolset_id,
            "created_at": _now(),
            "publisher_id": publisher_id,
            "source_id": source_id,
            "title": title.strip() or "OpenAPI toolset",
            "selected_operations": list(selected_operations),
            "tool_name_prefix": tool_name_prefix.strip(),
            "metadata": dict(metadata or {}),
        }

        if not self.db_path:
            self._memory_toolsets[toolset_id] = record
            return record

        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO purecipher_openapi_toolsets
              (toolset_id, created_at, publisher_id, source_id, title,
               selected_operations_json, tool_name_prefix, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                toolset_id,
                record["created_at"],
                record["publisher_id"],
                record["source_id"],
                record["title"],
                json.dumps(record["selected_operations"]),
                record["tool_name_prefix"],
                json.dumps(record["metadata"]),
            ),
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return record

    def get_source_spec(self, source_id: str) -> dict[str, Any] | None:
        if not self.db_path:
            rec = self._memory_sources.get(source_id)
            return dict(rec.get("spec_json") or {}) if rec else None

        conn = self._connect()
        cur = conn.execute(
            "SELECT spec_json FROM purecipher_openapi_sources WHERE source_id = ?",
            (source_id,),
        )
        row = cur.fetchone()
        if self._shared_conn is None:
            conn.close()
        if not row:
            return None
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def get_toolset(self, toolset_id: str) -> OpenAPIToolsetRecord | None:
        if not self.db_path:
            rec = self._memory_toolsets.get(toolset_id)
            return dict(rec) if rec else None

        conn = self._connect()
        cur = conn.execute(
            """
            SELECT toolset_id, created_at, publisher_id, source_id, title,
                   selected_operations_json, tool_name_prefix, metadata_json
            FROM purecipher_openapi_toolsets
            WHERE toolset_id = ?
            """,
            (toolset_id,),
        )
        row = cur.fetchone()
        if self._shared_conn is None:
            conn.close()
        if not row:
            return None
        (
            tid,
            created_at,
            publisher_id,
            source_id,
            title,
            selected_json,
            tool_name_prefix,
            metadata_json,
        ) = row
        try:
            selected = json.loads(selected_json)
        except json.JSONDecodeError:
            selected = []
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        return {
            "toolset_id": str(tid),
            "created_at": float(created_at),
            "publisher_id": str(publisher_id),
            "source_id": str(source_id),
            "title": str(title),
            "selected_operations": [str(x) for x in selected]
            if isinstance(selected, list)
            else [],
            "tool_name_prefix": str(tool_name_prefix),
            "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        }

    def list_toolsets(self, *, limit: int = 200) -> list[OpenAPIToolsetRecord]:
        if limit <= 0:
            return []
        if not self.db_path:
            items = list(self._memory_toolsets.values())
            items.sort(key=lambda x: float(x.get("created_at", 0.0)), reverse=True)
            return [dict(item) for item in items[:limit]]

        conn = self._connect()
        cur = conn.execute(
            """
            SELECT toolset_id, created_at, publisher_id, source_id, title,
                   selected_operations_json, tool_name_prefix, metadata_json
            FROM purecipher_openapi_toolsets
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        if self._shared_conn is None:
            conn.close()

        out: list[OpenAPIToolsetRecord] = []
        for row in rows:
            (
                tid,
                created_at,
                publisher_id,
                source_id,
                title,
                selected_json,
                tool_name_prefix,
                metadata_json,
            ) = row
            try:
                selected = json.loads(selected_json)
            except json.JSONDecodeError:
                selected = []
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
            out.append(
                {
                    "toolset_id": str(tid),
                    "created_at": float(created_at),
                    "publisher_id": str(publisher_id),
                    "source_id": str(source_id),
                    "title": str(title),
                    "selected_operations": [str(x) for x in selected]
                    if isinstance(selected, list)
                    else [],
                    "tool_name_prefix": str(tool_name_prefix),
                    "metadata": dict(metadata) if isinstance(metadata, dict) else {},
                }
            )
        return out

    # ------------------------------------------------------------------
    # Credentials (Iter 13.2)
    # ------------------------------------------------------------------

    def _require_cipher(self) -> Any:
        if self._fernet_key is None:
            raise RuntimeError(
                "OpenAPIStore: credential operations require credential_key."
            )
        # Local import keeps cryptography off the import path for stores
        # that never touch credentials.
        from cryptography.fernet import Fernet

        return Fernet(self._fernet_key)

    def _encrypt_secret(self, secret: dict[str, Any]) -> str:
        cipher = self._require_cipher()
        plaintext = json.dumps(secret, sort_keys=True).encode("utf-8")
        return cipher.encrypt(plaintext).decode("utf-8")

    def _decrypt_secret(self, ciphertext: str) -> dict[str, Any]:
        cipher = self._require_cipher()
        try:
            payload = cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            raise RuntimeError(
                "OpenAPIStore: failed to decrypt credential secret."
            ) from exc
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "OpenAPIStore: stored credential secret was not valid JSON."
            ) from exc
        return decoded if isinstance(decoded, dict) else {}

    @staticmethod
    def _credential_id(publisher_id: str, source_id: str, scheme_name: str) -> str:
        # Deterministic id so an upsert hits the same row even when the
        # caller omits the existing id.
        digest = hashlib.sha256(
            f"{publisher_id}\x1f{source_id}\x1f{scheme_name}".encode()
        ).hexdigest()
        return f"cred_{digest[:24]}"

    def upsert_credential(
        self,
        *,
        publisher_id: str,
        source_id: str,
        scheme_name: str,
        scheme_kind: SecuritySchemeKind,
        secret: dict[str, Any],
        label: str = "",
    ) -> OpenAPICredentialRecord:
        if not publisher_id or not source_id or not scheme_name:
            raise ValueError("publisher_id, source_id, and scheme_name are required.")
        if not isinstance(secret, dict) or not secret:
            raise ValueError("secret must be a non-empty dict.")
        # Touching the cipher up-front so a misconfigured store fails
        # before we mutate state.
        self._require_cipher()

        credential_id = self._credential_id(publisher_id, source_id, scheme_name)
        now = _now()
        hint = _credential_secret_hint(scheme_kind, secret)
        record: OpenAPICredentialRecord = {
            "credential_id": credential_id,
            "created_at": now,
            "updated_at": now,
            "publisher_id": publisher_id,
            "source_id": source_id,
            "scheme_name": scheme_name,
            "scheme_kind": scheme_kind,
            "label": label.strip(),
            "secret": dict(secret),
        }

        if not self.db_path:
            existing = self._memory_credentials.get(credential_id)
            if existing:
                record["created_at"] = float(existing.get("created_at") or now)
            self._memory_credentials[credential_id] = record
            return record

        ciphertext = self._encrypt_secret(secret)
        conn = self._connect()
        existing_row = conn.execute(
            "SELECT created_at FROM purecipher_openapi_credentials"
            " WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
        created_at = float(existing_row[0]) if existing_row is not None else float(now)
        record["created_at"] = created_at
        conn.execute(
            """
            INSERT OR REPLACE INTO purecipher_openapi_credentials
              (credential_id, created_at, updated_at, publisher_id, source_id,
               scheme_name, scheme_kind, label, secret_hint, secret_ciphertext)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                created_at,
                float(now),
                publisher_id,
                source_id,
                scheme_name,
                scheme_kind,
                record["label"],
                hint,
                ciphertext,
            ),
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return record

    def get_credential(
        self, credential_id: str, *, publisher_id: str | None = None
    ) -> OpenAPICredentialRecord | None:
        """Return the full credential including plaintext ``secret``.

        ``publisher_id`` enforces tenant isolation when supplied — a
        cross-publisher read returns ``None`` rather than the record.
        Callers exposing this method via HTTP MUST pass the session's
        publisher id.
        """
        if not self.db_path:
            rec = self._memory_credentials.get(credential_id)
            if rec is None:
                return None
            if publisher_id is not None and rec.get("publisher_id") != publisher_id:
                return None
            return dict(rec)  # type: ignore[return-value]

        conn = self._connect()
        cur = conn.execute(
            """
            SELECT credential_id, created_at, updated_at, publisher_id,
                   source_id, scheme_name, scheme_kind, label,
                   secret_hint, secret_ciphertext
            FROM purecipher_openapi_credentials
            WHERE credential_id = ?
            """,
            (credential_id,),
        )
        row = cur.fetchone()
        if self._shared_conn is None:
            conn.close()
        if not row:
            return None
        (
            cid,
            created_at,
            updated_at,
            row_publisher,
            source_id,
            scheme_name,
            scheme_kind,
            label,
            _hint,
            ciphertext,
        ) = row
        if publisher_id is not None and str(row_publisher) != publisher_id:
            return None
        return {
            "credential_id": str(cid),
            "created_at": float(created_at),
            "updated_at": float(updated_at),
            "publisher_id": str(row_publisher),
            "source_id": str(source_id),
            "scheme_name": str(scheme_name),
            "scheme_kind": str(scheme_kind),  # type: ignore[typeddict-item]
            "label": str(label),
            "secret": self._decrypt_secret(str(ciphertext)),
        }

    def list_credentials(
        self,
        *,
        publisher_id: str,
        source_id: str | None = None,
    ) -> list[OpenAPICredentialPublic]:
        """List credentials for the publisher, with secrets redacted.

        Always scoped to a single publisher — there is no global view.
        Pass ``source_id`` to narrow further to credentials for one
        ingested OpenAPI source.
        """
        if not self.db_path:
            items = [
                rec
                for rec in self._memory_credentials.values()
                if rec.get("publisher_id") == publisher_id
                and (source_id is None or rec.get("source_id") == source_id)
            ]
            items.sort(key=lambda x: float(x.get("updated_at", 0.0)), reverse=True)
            return [
                {
                    "credential_id": str(r.get("credential_id", "")),
                    "created_at": float(r.get("created_at", 0.0)),
                    "updated_at": float(r.get("updated_at", 0.0)),
                    "publisher_id": str(r.get("publisher_id", "")),
                    "source_id": str(r.get("source_id", "")),
                    "scheme_name": str(r.get("scheme_name", "")),
                    "scheme_kind": str(r.get("scheme_kind", "")),  # type: ignore[typeddict-item]
                    "label": str(r.get("label", "")),
                    "secret_hint": _credential_secret_hint(
                        str(r.get("scheme_kind", "")),
                        r.get("secret", {}) or {},
                    ),
                }
                for r in items
            ]

        params: list[Any] = [publisher_id]
        sql = (
            "SELECT credential_id, created_at, updated_at, publisher_id,"
            " source_id, scheme_name, scheme_kind, label, secret_hint"
            " FROM purecipher_openapi_credentials"
            " WHERE publisher_id = ?"
        )
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY updated_at DESC"

        conn = self._connect()
        cur = conn.execute(sql, tuple(params))
        rows = cur.fetchall()
        if self._shared_conn is None:
            conn.close()
        out: list[OpenAPICredentialPublic] = []
        for row in rows:
            (
                cid,
                created_at,
                updated_at,
                row_publisher,
                row_source,
                scheme_name,
                scheme_kind,
                label,
                hint,
            ) = row
            out.append(
                {
                    "credential_id": str(cid),
                    "created_at": float(created_at),
                    "updated_at": float(updated_at),
                    "publisher_id": str(row_publisher),
                    "source_id": str(row_source),
                    "scheme_name": str(scheme_name),
                    "scheme_kind": str(scheme_kind),  # type: ignore[typeddict-item]
                    "label": str(label),
                    "secret_hint": str(hint),
                }
            )
        return out

    def delete_credential(self, credential_id: str, *, publisher_id: str) -> bool:
        """Delete a credential. Scoped to ``publisher_id`` so a request
        from one tenant can never touch another tenant's row."""
        if not credential_id or not publisher_id:
            return False
        if not self.db_path:
            existing = self._memory_credentials.get(credential_id)
            if existing is None or existing.get("publisher_id") != publisher_id:
                return False
            del self._memory_credentials[credential_id]
            return True

        conn = self._connect()
        cur = conn.execute(
            "DELETE FROM purecipher_openapi_credentials"
            " WHERE credential_id = ? AND publisher_id = ?",
            (credential_id, publisher_id),
        )
        conn.commit()
        deleted = cur.rowcount > 0
        if self._shared_conn is None:
            conn.close()
        return deleted
