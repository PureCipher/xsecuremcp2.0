"""Hosted runtime helpers for serving registry-managed MCP servers.

Hosts the PureCipher registry control plane and dynamically hosts OpenAPI
toolsets as Streamable HTTP MCP endpoints without requiring a restart.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.applications import Starlette
from starlette.routing import Mount

from purecipher.auth import RegistryAuthSettings
from purecipher.openapi_gateway import OpenAPIGateway, OpenAPIGatewayConfig
from purecipher.openapi_store import OpenAPIStore
from purecipher.registry import PureCipherRegistry


@asynccontextmanager
async def hosted_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Ensure child Starlette apps get their lifespan events."""

    children = getattr(app.state, "children", [])
    contexts = [child.router.lifespan_context(child) for child in children]
    router = getattr(app.state, "toolset_router", None)
    try:
        for ctx in contexts:
            await ctx.__aenter__()
        yield
    finally:
        if router is not None:
            await router.aclose()
        for ctx in reversed(contexts):
            await ctx.__aexit__(None, None, None)


class ToolsetGatewayRouter:
    """ASGI app that hosts toolsets at /mcp/toolsets/<toolset_id> dynamically."""

    def __init__(
        self,
        *,
        persistence_path: str,
        auth_settings: RegistryAuthSettings | None = None,
    ) -> None:
        self._store = OpenAPIStore(persistence_path)
        self._lock = asyncio.Lock()
        self._apps: dict[str, Starlette] = {}
        self._lifespans: dict[str, Any] = {}
        self._persistence_path = persistence_path
        self._auth_settings = auth_settings

    async def _ensure_toolset_app(self, toolset_id: str) -> Starlette | None:
        if toolset_id in self._apps:
            return self._apps[toolset_id]

        async with self._lock:
            if toolset_id in self._apps:
                return self._apps[toolset_id]

            toolset = self._store.get_toolset(toolset_id)
            if toolset is None:
                return None
            metadata = toolset.get("metadata") or {}
            upstream = str(metadata.get("upstream_base_url") or "").strip() if isinstance(metadata, dict) else ""
            if not upstream:
                return None

            gateway = OpenAPIGateway(
                name=f"toolset-{toolset_id}",
                config=OpenAPIGatewayConfig(
                    toolset_id=toolset_id,
                    persistence_path=self._persistence_path,
                    upstream_base_url=upstream,
                ),
            )
            # Mounted under /mcp/toolsets, so the child app sees path "/<toolset_id>".
            toolset_app = gateway.http_app(
                path=f"/{toolset_id}",
                transport="streamable-http",
            )

            lifespan_ctx = toolset_app.router.lifespan_context(toolset_app)
            await lifespan_ctx.__aenter__()

            self._apps[toolset_id] = toolset_app
            self._lifespans[toolset_id] = lifespan_ctx
            return toolset_app

    def _session_from_scope(self, scope) -> Any | None:
        if self._auth_settings is None or not self._auth_settings.enabled:
            return None
        headers = dict(scope.get("headers") or [])
        raw_cookie = headers.get(b"cookie", b"").decode("utf-8", errors="ignore")
        if not raw_cookie:
            return None
        cookie_name = self._auth_settings.cookie_name
        token = ""
        for chunk in raw_cookie.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if not chunk.startswith(cookie_name + "="):
                continue
            token = chunk.split("=", 1)[1].strip()
            break
        if not token:
            return None
        return self._auth_settings.decode_token(token)

    def _enforce_visibility(self, *, toolset: dict[str, Any], scope) -> Response | None:
        metadata = toolset.get("metadata") or {}
        metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
        visibility = str(metadata_dict.get("hosting_visibility") or "public").strip().lower()

        # Public = no auth required.
        if visibility == "public":
            return None

        # Protected / private require auth when auth is enabled.
        if self._auth_settings is None or not self._auth_settings.enabled:
            # If auth is disabled, treat protected/private as public (dev convenience).
            return None

        session = self._session_from_scope(scope)
        if session is None:
            return JSONResponse(
                {"error": "Authentication required for hosted toolset.", "status": 401},
                status_code=401,
            )

        if visibility == "protected":
            return None

        if visibility == "private":
            allowed_users = metadata_dict.get("allowed_users")
            allowed = (
                [str(x).strip() for x in allowed_users]
                if isinstance(allowed_users, list)
                else []
            )
            allowed = [x for x in allowed if x]
            if allowed and getattr(session, "username", None) not in set(allowed):
                return JSONResponse(
                    {"error": "Not authorized for private hosted toolset.", "status": 403},
                    status_code=403,
                )
            return None

        return JSONResponse(
            {"error": "Unknown hosting_visibility.", "status": 400, "hosting_visibility": visibility},
            status_code=400,
        )

    async def aclose(self) -> None:
        async with self._lock:
            lifespans = list(self._lifespans.items())
            self._lifespans = {}
            self._apps = {}
        for _, ctx in lifespans:
            await ctx.__aexit__(None, None, None)

    async def __call__(self, scope, receive, send) -> None:
        # Starlette Mount("/mcp/toolsets", app=...) strips prefix; expect "/<toolset_id>"
        if scope.get("type") != "http":
            await PlainTextResponse("Unsupported scope.", status_code=400)(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        toolset_id = path.lstrip("/").split("/", 1)[0].strip()
        if not toolset_id:
            await JSONResponse(
                {"error": "Missing toolset id.", "status": 400},
                status_code=400,
            )(scope, receive, send)
            return

        toolset = self._store.get_toolset(toolset_id)
        if toolset is None:
            await JSONResponse(
                {
                    "error": "Toolset not found or missing upstream_base_url.",
                    "toolset_id": toolset_id,
                    "status": 404,
                },
                status_code=404,
            )(scope, receive, send)
            return

        deny = self._enforce_visibility(toolset=toolset, scope=scope)
        if deny is not None:
            await deny(scope, receive, send)
            return

        app = await self._ensure_toolset_app(toolset_id)
        if app is None:
            await JSONResponse(
                {
                    "error": "Toolset not found or missing upstream_base_url.",
                    "toolset_id": toolset_id,
                    "status": 404,
                },
                status_code=404,
            )(scope, receive, send)
            return

        await app(scope, receive, send)


def build_hosted_registry_app(
    *,
    registry: PureCipherRegistry,
    persistence_path: str | None,
    upstream_default_base_url: str | None = None,
) -> Starlette:
    """Build a Starlette app hosting the registry plus toolset gateways."""

    registry_app = registry.http_app(path="/mcp", transport="streamable-http")
    routes: list[Any] = []
    children: list[Any] = [registry_app]

    toolset_router = None
    if persistence_path:
        toolset_router = ToolsetGatewayRouter(
            persistence_path=persistence_path,
            auth_settings=getattr(registry, "_auth_settings", None),
        )
        # Mount toolsets first so they take precedence over registry /mcp.
        routes.append(Mount("/mcp/toolsets", app=toolset_router))

    routes.append(Mount("/", app=registry_app))

    app = Starlette(routes=routes, lifespan=hosted_lifespan)
    app.state.children = children
    app.state.toolset_router = toolset_router
    return app


__all__ = ["build_hosted_registry_app", "hosted_lifespan"]

