"""Hosted MCP/SecureMCP gateway for OpenAPI-derived toolsets (MVP).

This gateway exposes selected OpenAPI operations as MCP tools and proxies calls
to the publisher's upstream HTTP API.

MVP constraints:
- OpenAPI document must be JSON (no YAML ingestion here)
- Only supports JSON request bodies and JSON-ish responses
- Input shape is a single object with optional keys: path, query, headers, body
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from mcp.server.lowlevel.server import LifespanResultT

from purecipher.openapi_store import OpenAPIStore, extract_openapi_operations
from securemcp import SecureMCP
from securemcp.config import SecurityConfig


def _format_path(path_template: str, values: dict[str, Any]) -> str:
    out = path_template
    for key, value in values.items():
        out = out.replace(
            "{" + str(key) + "}",
            httpx.QueryParams({str(key): str(value)}).get(str(key)) or str(value),
        )
    return out


@dataclass
class OpenAPIGatewayConfig:
    toolset_id: str
    persistence_path: str
    upstream_base_url: str
    timeout_seconds: float = 12.0


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
        super().__init__(
            name=name, security=security, mount_security_api=False, **kwargs
        )
        self._config = config
        self._store = OpenAPIStore(config.persistence_path)
        self._http_client = http_client or httpx.AsyncClient(
            base_url=config.upstream_base_url.rstrip("/"),
            timeout=config.timeout_seconds,
            headers={"accept": "application/json"},
        )
        self._owns_client = http_client is None
        self._mount_toolset()

    def _mount_toolset(self) -> None:
        toolset = self._store.get_toolset(self._config.toolset_id)
        if toolset is None:
            raise ValueError(f"Unknown toolset_id {self._config.toolset_id!r}")
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
                    {str(k): str(v) for k, v in dict(header_values).items()}
                    if isinstance(header_values, dict)
                    else {}
                )

                url_path = _format_path(_p, path_dict)
                qs = urlencode(
                    {k: v for k, v in query_dict.items() if v is not None}, doseq=True
                )
                url = f"{url_path}{'?' + qs if qs else ''}"

                res = await self._http_client.request(
                    _m.upper(),
                    url,
                    headers=header_dict or None,
                    json=body_value if body_value is not None else None,
                )

                text = await res.aread()
                # Best effort JSON decode; fall back to text.
                parsed: Any
                try:
                    parsed = res.json()
                except Exception:
                    parsed = text.decode("utf-8", errors="replace")
                return {
                    "status_code": res.status_code,
                    "headers": {k: v for k, v in res.headers.items()},
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
]
