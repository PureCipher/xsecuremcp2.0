"""Hosted runtime helpers for serving registry-managed MCP servers.

Hosts the PureCipher registry control plane and dynamically hosts OpenAPI
toolsets as Streamable HTTP MCP endpoints without requiring a restart.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager
from http.cookies import CookieError, SimpleCookie
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount

from purecipher.auth import RegistryAuthSettings, RegistrySession
from purecipher.openapi_gateway import (
    OpenAPIGateway,
    OpenAPIGatewayConfig,
    build_openapi_gateway_security,
)
from purecipher.openapi_store import OpenAPIStore
from purecipher.registry import PureCipherRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def hosted_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Ensure child Starlette apps get their lifespan events."""

    children = getattr(app.state, "children", [])
    contexts = [child.router.lifespan_context(child) for child in children]
    toolset_router = getattr(app.state, "toolset_router", None)
    curator_proxy_router = getattr(app.state, "curator_proxy_router", None)
    try:
        for ctx in contexts:
            await ctx.__aenter__()
        yield
    finally:
        if curator_proxy_router is not None:
            await curator_proxy_router.aclose()
        if toolset_router is not None:
            await toolset_router.aclose()
        for ctx in reversed(contexts):
            await ctx.__aexit__(None, None, None)


class ToolsetGatewayRouter:
    """ASGI app that hosts toolsets at /mcp/toolsets/<toolset_id> dynamically."""

    def __init__(
        self,
        *,
        persistence_path: str,
        auth_settings: RegistryAuthSettings | None = None,
        session_resolver: Callable[..., RegistrySession | None] | None = None,
        shared_security_context: Any = None,
    ) -> None:
        if (
            auth_settings is not None
            and auth_settings.enabled
            and session_resolver is None
        ):
            raise ValueError(
                "Authenticated toolset hosting requires a revocation-aware "
                "session_resolver"
            )
        self._store = OpenAPIStore(persistence_path)
        self._lock = asyncio.Lock()
        self._apps: dict[str, Starlette] = {}
        self._lifespans: dict[str, Any] = {}
        self._gateways: dict[str, OpenAPIGateway] = {}
        self._persistence_path = persistence_path
        self._auth_settings = auth_settings
        self._session_resolver = session_resolver
        self._shared_security_context = shared_security_context

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
            upstream = (
                str(metadata.get("upstream_base_url") or "").strip()
                if isinstance(metadata, dict)
                else ""
            )
            if not upstream:
                return None

            gateway = OpenAPIGateway(
                name=f"toolset-{toolset_id}",
                config=OpenAPIGatewayConfig(
                    toolset_id=toolset_id,
                    persistence_path=self._persistence_path,
                    upstream_base_url=upstream,
                ),
                security=build_openapi_gateway_security(
                    toolset,
                    shared_context=self._shared_security_context,
                ),
            )
            # Mounted under /mcp/toolsets, so the child app sees path "/<toolset_id>".
            toolset_app = gateway.http_app(
                path=f"/{toolset_id}",
                transport="streamable-http",
            )

            lifespan_ctx = toolset_app.router.lifespan_context(toolset_app)
            try:
                await lifespan_ctx.__aenter__()
            except Exception:
                try:
                    await gateway.aclose()
                except Exception:
                    logger.warning(
                        "Toolset gateway cleanup after startup failure raised",
                        exc_info=True,
                    )
                raise

            self._apps[toolset_id] = toolset_app
            self._lifespans[toolset_id] = lifespan_ctx
            self._gateways[toolset_id] = gateway
            return toolset_app

    def _session_from_scope(self, scope: Mapping[str, Any]) -> RegistrySession | None:
        if self._auth_settings is None or not self._auth_settings.enabled:
            return None
        headers = dict(scope.get("headers") or [])
        raw_cookie = headers.get(b"cookie", b"").decode("utf-8", errors="ignore")
        cookie_token = ""
        if raw_cookie:
            cookies = SimpleCookie()
            try:
                cookies.load(raw_cookie)
            except CookieError:
                cookies = SimpleCookie()
            morsel = cookies.get(self._auth_settings.cookie_name)
            cookie_token = morsel.value if morsel is not None else ""

        authorization = headers.get(b"authorization", b"").decode(
            "utf-8", errors="ignore"
        )
        scheme, _, candidate = authorization.partition(" ")
        bearer_token = candidate.strip() if scheme.lower() == "bearer" else ""
        if self._session_resolver is None:
            return None
        return self._session_resolver(
            cookie_token=cookie_token,
            bearer_token=bearer_token,
        )

    def _enforce_visibility(
        self, *, toolset: Mapping[str, Any], scope
    ) -> Response | None:
        metadata = toolset.get("metadata") or {}
        metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
        visibility = (
            str(metadata_dict.get("hosting_visibility") or "public").strip().lower()
        )

        # Public = no auth required.
        if visibility == "public":
            return None
        if visibility not in {"protected", "private"}:
            return JSONResponse(
                {
                    "error": "Unknown hosting_visibility.",
                    "status": 400,
                    "hosting_visibility": visibility,
                },
                status_code=400,
            )

        # Protected / private are never downgraded to public merely because
        # registry authentication is unavailable or misconfigured.
        if self._auth_settings is None or not self._auth_settings.enabled:
            return JSONResponse(
                {
                    "error": "Authentication is unavailable for hosted toolset.",
                    "status": 503,
                },
                status_code=503,
            )

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
            if getattr(session, "username", None) not in set(allowed):
                return JSONResponse(
                    {
                        "error": "Not authorized for private hosted toolset.",
                        "status": 403,
                    },
                    status_code=403,
                )
            return None

        return None

    async def aclose(self) -> None:
        async with self._lock:
            lifespans = list(self._lifespans.items())
            gateways = list(self._gateways.values())
            self._lifespans = {}
            self._apps = {}
            self._gateways = {}
        for _, ctx in lifespans:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.warning("Toolset lifespan teardown raised", exc_info=True)
        for gateway in gateways:
            try:
                await gateway.aclose()
            except Exception:
                logger.warning("Toolset gateway teardown raised", exc_info=True)

    async def __call__(self, scope, receive, send) -> None:
        # Raw ASGI mounts preserve the full path and expose the stripped prefix
        # as ``root_path``; direct calls already provide the inner path.
        if scope.get("type") != "http":
            await PlainTextResponse("Unsupported scope.", status_code=400)(
                scope, receive, send
            )
            return

        full_path = str(scope.get("path") or "")
        root_path = str(scope.get("root_path") or "")
        if root_path and full_path.startswith(root_path):
            inner_path = full_path[len(root_path) :]
        else:
            inner_path = full_path
        toolset_id = inner_path.lstrip("/").split("/", 1)[0].strip()
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
    """Build a Starlette app hosting the registry plus toolset gateways
    and curator-mode proxies.

    Routes are mounted in priority order:

    1. ``/mcp/toolsets/{id}``  → OpenAPI-toolset gateway (existing).
    2. ``/runtime/proxy/{id}/mcp/...`` → curator-mode SecureMCP proxy
       (this iteration). Listings published with
       ``hosting_mode: "proxy"`` get an enforced gateway here.
    3. ``/`` → the registry control plane.
    """

    registry_app = registry.http_app(path="/mcp", transport="streamable-http")
    routes: list[Any] = []
    children: list[Any] = [registry_app]

    shared_ctx = None
    try:
        shared_ctx = registry.security_context
    except Exception:
        pass

    toolset_router = None
    if persistence_path:
        toolset_router = ToolsetGatewayRouter(
            persistence_path=persistence_path,
            auth_settings=getattr(registry, "_auth_settings", None),
            session_resolver=registry.resolve_registry_session,
            shared_security_context=shared_ctx,
        )
        # Mount toolsets first so they take precedence over registry /mcp.
        routes.append(Mount("/mcp/toolsets", app=toolset_router))

    # Curator-mode proxy router: lazy-mounts a SecureMCP-enforced
    # proxy per ``hosting_mode: "proxy"`` listing. Bound to the
    # registry's marketplace via a closure so the router doesn't need
    # to import the registry class directly.
    from purecipher.curation.proxy_runtime import CuratorProxyRouter

    def _lookup_listing(listing_id: str) -> Any:
        marketplace = getattr(registry, "_marketplace", None)
        if marketplace is None:
            return None
        # The registry's _marketplace() helper builds/returns the
        # ToolMarketplace lazily; call it as a method when callable,
        # use the attribute directly otherwise (test seam).
        try:
            mp = marketplace() if callable(marketplace) else marketplace
        except Exception:
            return None
        if mp is None:
            return None
        return mp.get(listing_id) if hasattr(mp, "get") else None

    curator_proxy_router = CuratorProxyRouter(
        listing_lookup=_lookup_listing,
        auth_settings=getattr(registry, "_auth_settings", None),
        shared_security_context=shared_ctx,
        # Pass the registry so proxies can resolve bearer tokens to
        # client slugs for consent/contract enforcement. Kept as a
        # separate argument (rather than a SecurityContext attribute)
        # so we don't widen SecureMCP's dataclass schema.
        registry=registry,
    )
    routes.append(Mount("/runtime/proxy", app=curator_proxy_router))

    routes.append(Mount("/", app=registry_app))

    app = Starlette(routes=routes, lifespan=hosted_lifespan)
    from purecipher.middleware.profile_access import ProfileBoundary

    app.add_middleware(ProfileBoundary, registry=registry, guard_only=True)
    app.state.children = children
    app.state.toolset_router = toolset_router
    app.state.curator_proxy_router = curator_proxy_router
    return app


__all__ = ["build_hosted_registry_app", "hosted_lifespan"]
