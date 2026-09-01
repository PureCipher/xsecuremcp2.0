"""Hosted MCP/SecureMCP gateway for OpenAPI-derived toolsets (MVP).

This gateway exposes selected OpenAPI operations as MCP tools and proxies calls
to the publisher's upstream HTTP API.

MVP constraints:
- OpenAPI document must be JSON (no YAML ingestion here)
- Only supports JSON request bodies and JSON-ish responses
- Input shape is a single object with optional keys: path, query, headers, body
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx
from mcp.server.lowlevel.server import LifespanResultT

from fastmcp.server.security.policy.policies.allowlist import AllowlistPolicy
from purecipher.openapi_store import OpenAPIStore, extract_openapi_operations
from purecipher.outbound_security import (
    DEFAULT_MAX_RESPONSE_BYTES,
    PinnedDNSAsyncTransport,
    encode_outbound_path_segment,
    read_response_body_limited,
    validate_outbound_url,
)
from securemcp import SecureMCP
from securemcp.config import (
    AlertConfig,
    PolicyConfig,
    ProvenanceConfig,
    SecurityConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastmcp.server.security.orchestrator import SecurityContext


class UnsafeOutboundHeaderError(ValueError):
    """Raised when a hosted caller tries to control a sensitive header."""


_BLOCKED_REQUEST_HEADERS = frozenset(
    {
        "authorization",
        "connection",
        "content-length",
        "cookie",
        "cookie2",
        "cf-connecting-ip",
        "expect",
        "forwarded",
        "host",
        "keep-alive",
        "proxy-authorization",
        "proxy-connection",
        "origin",
        "referer",
        "te",
        "trailer",
        "transfer-encoding",
        "true-client-ip",
        "upgrade",
        "x-client-ip",
        "x-cluster-client-ip",
        "x-http-method-override",
        "x-method-override",
        "x-original-url",
        "x-real-ip",
        "x-rewrite-url",
    }
)


def _encode_path_segment(value: Any) -> str:
    return encode_outbound_path_segment(str(value))


def _format_path(path_template: str, values: dict[str, Any]) -> str:
    out = path_template
    for key, value in values.items():
        out = out.replace("{" + str(key) + "}", _encode_path_segment(value))
    return out


def _safe_request_headers(values: Mapping[Any, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_name, raw_value in values.items():
        name = str(raw_name).strip()
        normalized = name.lower()
        if (
            not name
            or normalized in _BLOCKED_REQUEST_HEADERS
            or normalized.startswith("x-forwarded-")
            or normalized.startswith("proxy-")
        ):
            raise UnsafeOutboundHeaderError(
                f"Hosted callers may not forward the {name or '<empty>'!r} header"
            )
        value = str(raw_value)
        if "\r" in value or "\n" in value:
            raise UnsafeOutboundHeaderError(
                f"Hosted caller header {name!r} contains a line break"
            )
        headers[name] = value
    return headers


def build_openapi_gateway_security(
    toolset: Mapping[str, Any],
    *,
    shared_context: SecurityContext | None = None,
) -> SecurityConfig:
    """Create an isolated policy with shared registry audit components."""
    toolset_id = str(toolset.get("toolset_id") or "unknown")
    prefix = str(toolset.get("tool_name_prefix") or "").strip()
    allowed = {
        f"{prefix}.{operation}" if prefix else str(operation)
        for operation in toolset.get("selected_operations") or []
        if str(operation).strip()
    }
    shared_ledger = shared_context.provenance_ledger if shared_context else None
    shared_event_bus = shared_context.event_bus if shared_context else None
    return SecurityConfig(
        policy=PolicyConfig(
            providers=[
                AllowlistPolicy(
                    allowed=allowed,
                    policy_id=f"hosted-toolset-allowlist-{toolset_id}",
                )
            ],
            fail_closed=True,
        ),
        provenance=ProvenanceConfig(
            ledger=shared_ledger,
            ledger_id=f"hosted-toolset-{toolset_id}",
        ),
        alerts=AlertConfig(event_bus=shared_event_bus),
        enabled=True,
    )


@dataclass
class OpenAPIGatewayConfig:
    toolset_id: str
    persistence_path: str
    upstream_base_url: str
    timeout_seconds: float = 12.0
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES


class OpenAPIGateway(SecureMCP[LifespanResultT]):
    """SecureMCP server that serves a stored OpenAPI toolset."""

    def __init__(
        self,
        name: str,
        *,
        config: OpenAPIGatewayConfig,
        security: SecurityConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
        **kwargs: Any,
    ) -> None:
        validate_outbound_url(config.upstream_base_url)
        if config.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be greater than zero")
        self._config = config
        self._store = OpenAPIStore(config.persistence_path)
        toolset = self._store.get_toolset(config.toolset_id)
        if toolset is None:
            raise ValueError(f"Unknown toolset_id {config.toolset_id!r}")
        effective_security = security or build_openapi_gateway_security(toolset)
        kwargs.setdefault("bypass_stdio", False)
        super().__init__(
            name=name,
            security=effective_security,
            mount_security_api=False,
            **kwargs,
        )
        self._http_client: httpx.AsyncClient
        self._mount_toolset(toolset)
        self._http_client = http_client or httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers={"accept": "application/json"},
            transport=PinnedDNSAsyncTransport(),
        )
        self._owns_client = http_client is None

    def _mount_toolset(self, toolset: Mapping[str, Any]) -> None:
        source_id = str(toolset.get("source_id") or "")
        spec = self._store.get_source_spec(source_id)
        if spec is None:
            raise ValueError(f"Toolset source {source_id!r} is missing.")

        ops = extract_openapi_operations(spec)
        selected = set(toolset.get("selected_operations") or [])
        prefix = str(toolset.get("tool_name_prefix") or "").strip()

        for op in ops:
            op_key = str(op.get("operation_key") or "")
            if not op_key or op_key not in selected:
                continue
            method = str(op.get("method") or "get").lower()
            path_template = str(op.get("path") or "/")
            tool_name = op_key
            if prefix:
                tool_name = f"{prefix}.{tool_name}"

            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            doc = (
                summary + "\n\n" + description
            ).strip() or f"Proxy {method.upper()} {path_template}"

            async def _handler(
                payload: dict[str, Any], *, _m=method, _p=path_template
            ) -> dict[str, Any]:
                path_values = payload.get("path")
                query_values = payload.get("query")
                header_values = payload.get("headers")
                body_value = payload.get("body")

                path_dict = dict(path_values) if isinstance(path_values, dict) else {}
                query_dict = (
                    dict(query_values) if isinstance(query_values, dict) else {}
                )
                header_dict = (
                    _safe_request_headers(header_values)
                    if isinstance(header_values, dict)
                    else {}
                )

                url_path = _format_path(_p, path_dict)
                qs = urlencode(
                    {k: v for k, v in query_dict.items() if v is not None}, doseq=True
                )
                upstream = self._config.upstream_base_url.rstrip("/")
                url = f"{upstream}/{url_path.lstrip('/')}"
                if qs:
                    url = f"{url}?{qs}"
                validate_outbound_url(url)

                async with self._http_client.stream(
                    _m.upper(),
                    url,
                    headers=header_dict or None,
                    json=body_value if body_value is not None else None,
                    follow_redirects=False,
                ) as res:
                    response_body = await read_response_body_limited(
                        res,
                        max_bytes=self._config.max_response_bytes,
                    )
                    status_code = res.status_code
                    response_headers = {
                        k: v
                        for k, v in res.headers.items()
                        if k.lower()
                        in {
                            "cache-control",
                            "content-language",
                            "content-length",
                            "content-type",
                            "etag",
                        }
                    }
                    encoding = res.encoding or "utf-8"

                # Best effort JSON decode; fall back to text.
                parsed: Any
                try:
                    parsed = json.loads(response_body)
                except ValueError:
                    parsed = response_body.decode(encoding, errors="replace")
                return {
                    "status_code": status_code,
                    "headers": response_headers,
                    "data": parsed,
                }

            # Register tool with FastMCP
            decorated = self.tool(name=tool_name, description=doc)(_handler)
            _ = decorated

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()


__all__ = [
    "OpenAPIGateway",
    "OpenAPIGatewayConfig",
    "UnsafeOutboundHeaderError",
    "build_openapi_gateway_security",
]
