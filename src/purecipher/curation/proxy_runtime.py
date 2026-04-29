"""Runtime hosting for ``hosting_mode: "proxy"`` curator listings.

When a curator chooses to host a third-party MCP server through
PureCipher, the registry mounts a SecureMCP-backed proxy at a stable
URL (``/runtime/proxy/{listing_id}/mcp``). User MCP clients connect
to that URL instead of directly to the upstream; the proxy:

1. Verifies the call against an :class:`AllowlistPolicy` built from
   the listing's curator-vouched tool surface — calls to tools the
   curator didn't observe are denied at the gateway.
2. Records every forwarded call in the provenance ledger so the
   listing carries a real audit trail.
3. Forwards the call to the upstream via :class:`ProxyProvider`.

This gives the curator-vouching trust statement a runtime tooth: the
PureCipher attestation now bounds what the upstream is *callable for*
through the registry, not just what's declared in the manifest.

Channel support:

- **HTTP** upstreams: a single :class:`Client` against the upstream
  URL is constructed per session.
- **PyPI** upstreams: each session spawns a fresh subprocess via
  ``uvx`` (:class:`UvxStdioTransport`). The curator-vouched package
  identifier (with optional ``@version`` pin) is forwarded to uvx.
- **npm** upstreams: each session spawns a fresh subprocess via
  ``npx`` (:class:`NpxStdioTransport`). Same versioning convention.
- **Docker** upstreams: each session spawns a fresh container via
  ``docker run --rm -i [resource flags] <image_ref>`` (generic
  :class:`StdioTransport`). The curator-vouched image reference
  (image name + optional tag + optional digest) is reconstructed via
  :func:`image_ref_for` and passed to docker. Resource flags
  (``--memory=512m --pids-limit=128``) are conservative defaults;
  operators tune via daemon-level config (rootless docker, seccomp,
  AppArmor) for stronger isolation.

Per-session lifecycle is provided automatically by
:class:`ProxyProvider` — the gateway holds no shared subprocess and
each MCP client gets its own isolated upstream instance. First
launch may take 10-30s while ``uvx``/``npx`` resolves the package
or while ``docker pull`` downloads the image; subsequent sessions
reuse the cache.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse

from fastmcp import Client
from fastmcp.server.providers.proxy import FastMCPProxy
from fastmcp.server.security.config import (
    AlertConfig,
    PolicyConfig,
    ProvenanceConfig,
    SecurityConfig,
)
from fastmcp.server.security.gateway.tool_marketplace import (
    HostingMode,
    ToolListing,
    UpstreamChannel,
)
from fastmcp.server.security.policy.policies.allowlist import AllowlistPolicy
from securemcp import SecureMCP

if TYPE_CHECKING:
    from purecipher.auth import RegistryAuthSettings

logger = logging.getLogger(__name__)


class ProxyHostingError(RuntimeError):
    """Raised when a listing can't be mounted as a SecureMCP proxy.

    Carries an operator-facing message; the runtime router surfaces
    these as JSON 4xx/5xx responses to the calling MCP client.
    """


def _build_proxy_security_config(
    listing: ToolListing,
    *,
    shared_context: Any = None,
) -> SecurityConfig:
    """Translate a curator listing's manifest into a :class:`SecurityConfig`.

    When ``shared_context`` is provided (the registry's central
    :class:`SecurityContext`), the proxy reuses the registry's
    provenance ledger, alert bus, and reflexive analyzer so events
    appear in the central governance dashboards. The allowlist policy
    is always per-listing.
    """
    observed_tools: set[str] = set()
    # The curator-submission flow persists observed tool names in
    # ``listing.metadata["introspection"]["tool_names"]`` — that's
    # the canonical, structured source. Manifest tags are a fallback
    # for legacy listings published before this metadata key existed.
    metadata = listing.metadata or {}
    if isinstance(metadata, dict):
        introspection = metadata.get("introspection")
        if isinstance(introspection, dict):
            tool_names = introspection.get("tool_names")
            if isinstance(tool_names, list):
                for name in tool_names:
                    s = str(name).strip()
                    if s:
                        observed_tools.add(s)

    if not observed_tools and listing.manifest is not None:
        # Legacy fallback: pull non-marker tags from the manifest.
        for tag in listing.manifest.tags or set():
            tag_str = str(tag)
            if tag_str in {"curated", "third-party"}:
                continue
            observed_tools.add(tag_str)

    # Always allow MCP-protocol introspection calls (list_tools, etc.) —
    # these don't go through the policy engine in our middleware, but
    # we explicitly note the contract here.

    if observed_tools:
        policy = PolicyConfig(
            providers=[
                AllowlistPolicy(
                    allowed=observed_tools,
                    policy_id=f"curator-allowlist-{listing.listing_id}",
                )
            ],
            fail_closed=True,
        )
    else:
        # No observed tools — open policy + warning. Keeps the proxy
        # usable while making the operator aware of the gap.
        logger.warning(
            "Curator listing %s has no observed tools recorded; the "
            "proxy will not enforce a tool allowlist. Re-run "
            "introspection to populate the observed surface.",
            listing.listing_id,
        )
        policy = PolicyConfig(fail_closed=False)

    if shared_context is not None:
        from fastmcp.server.security.config import ReflexiveConfig

        return SecurityConfig(
            policy=policy,
            provenance=ProvenanceConfig(
                ledger_id=shared_context.provenance_ledger.ledger_id
                if shared_context.provenance_ledger
                else f"curator-proxy-{listing.listing_id}",
            ),
            reflexive=ReflexiveConfig() if shared_context.behavioral_analyzer else None,
            alerts=AlertConfig(),
            enabled=True,
        )

    return SecurityConfig(
        policy=policy,
        provenance=ProvenanceConfig(
            ledger_id=f"curator-proxy-{listing.listing_id}",
        ),
        alerts=AlertConfig(),
        enabled=True,
    )


def _spec_with_optional_version(identifier: str, version: str | None) -> str:
    """Format ``identifier@version`` for a stdio launcher when version is set.

    Both ``uvx`` and ``npx`` accept an ``@<version>`` suffix on the
    package spec to pin the released version. We only append the
    suffix when the curator captured a non-empty version on the
    upstream_ref so downstream launchers don't see a stray ``@``.
    """
    if version:
        return f"{identifier}@{version}"
    return identifier


# Resource flags applied to each ``docker run`` invocation in proxy
# mode. Mirrors the introspector's defaults (small memory, capped
# PIDs) plus ``--rm -i`` for clean per-session lifecycle and stdio
# wiring. Operators wanting stronger isolation should configure the
# Docker daemon (rootless, seccomp profiles, AppArmor) — those layers
# don't need per-listing flags.
_DOCKER_PROXY_FLAGS = (
    "--rm",
    "-i",
    "--memory=512m",
    "--pids-limit=128",
)


def _build_client_factory(listing: ToolListing) -> Callable[[], Client]:
    """Build a per-session :class:`Client` factory for the upstream channel.

    Dispatches by :class:`UpstreamChannel`:

    - HTTP: a plain ``Client(url)`` (FastMCP picks the appropriate
      HTTP transport from the URL scheme).
    - PYPI: ``Client(UvxStdioTransport(tool_name=spec))`` — uvx will
      resolve the package on first use and cache it.
    - NPM: ``Client(NpxStdioTransport(package=spec))`` — npx requires
      Node/npm to be installed on the registry host (validated at
      construction time).
    - DOCKER: ``Client(StdioTransport("docker", ["run", "--rm", "-i",
      ..., image_ref]))`` — requires ``docker`` on the registry
      host's PATH. Each session spawns a fresh container.

    The factory is intentionally a closure over the parsed spec so
    :class:`ProxyProvider` can call it once per session without
    re-doing channel dispatch on every connect.
    """
    ref = listing.upstream_ref
    if ref is None:  # pragma: no cover — caller guards this
        raise ProxyHostingError(
            f"Listing {listing.listing_id!r} has no upstream_ref."
        )

    if ref.channel == UpstreamChannel.HTTP:
        upstream_url = ref.identifier
        if not upstream_url:
            raise ProxyHostingError(
                f"Listing {listing.listing_id!r} has an empty upstream URL."
            )

        def _http_factory() -> Client:
            return Client(upstream_url)

        return _http_factory

    if ref.channel == UpstreamChannel.PYPI:
        if not ref.identifier:
            raise ProxyHostingError(
                f"Listing {listing.listing_id!r} has an empty PyPI "
                "package name."
            )
        # Local import keeps the module load cheap when the registry
        # only ever hosts HTTP upstreams (no Node/uv import side
        # effects on startup).
        from fastmcp.client.transports.stdio import UvxStdioTransport

        spec = _spec_with_optional_version(ref.identifier, ref.version)

        def _pypi_factory() -> Client:
            return Client(UvxStdioTransport(tool_name=spec))

        return _pypi_factory

    if ref.channel == UpstreamChannel.NPM:
        if not ref.identifier:
            raise ProxyHostingError(
                f"Listing {listing.listing_id!r} has an empty npm "
                "package name."
            )
        from fastmcp.client.transports.stdio import NpxStdioTransport

        spec = _spec_with_optional_version(ref.identifier, ref.version)

        # NpxStdioTransport probes for ``npx`` at construction time; if
        # the registry host doesn't have Node installed we surface that
        # as a structured ProxyHostingError instead of letting a raw
        # ValueError reach the ASGI router.
        try:
            transport = NpxStdioTransport(package=spec)
        except ValueError as exc:
            raise ProxyHostingError(
                "npm proxy hosting requires the 'npx' launcher to be "
                "installed on the registry host. Install Node.js (which "
                "ships npx) or set hosting_mode='catalog' for this "
                f"listing. Underlying error: {exc}"
            ) from exc

        def _npm_factory() -> Client:
            # Re-construct the transport per session so each MCP client
            # gets its own subprocess. The probe above caught missing
            # npx eagerly; this re-construction is cheap.
            return Client(NpxStdioTransport(package=spec))

        # ``transport`` was only used to validate launcher availability;
        # the per-session factory builds fresh transports. Keep a local
        # reference so static analysis sees the validation is load-
        # bearing.
        del transport
        return _npm_factory

    if ref.channel == UpstreamChannel.DOCKER:
        if not ref.identifier:
            raise ProxyHostingError(
                f"Listing {listing.listing_id!r} has an empty Docker "
                "image name."
            )
        # Probe for ``docker`` on PATH eagerly so a missing launcher
        # surfaces as a structured ProxyHostingError instead of an
        # opaque FileNotFoundError raised inside the per-session
        # subprocess spawn.
        if shutil.which("docker") is None:
            raise ProxyHostingError(
                "Docker proxy hosting requires the 'docker' launcher "
                "to be installed on the registry host. Install Docker "
                "(or a compatible OCI runtime exposing the 'docker' "
                "CLI) or set hosting_mode='catalog' for this listing."
            )

        from fastmcp.client.transports.stdio import StdioTransport

        # Reconstruct the full ``image[:tag][@digest]`` form once so
        # we don't re-do the parse on every session connect. The
        # curator-vouched UpstreamRef carries the canonical image
        # name + optional tag + optional digest.
        from purecipher.curation.upstream import image_ref_for

        image_ref = image_ref_for(ref)
        docker_args = [*_DOCKER_PROXY_FLAGS, image_ref]

        def _docker_factory() -> Client:
            return Client(StdioTransport(command="docker", args=docker_args))

        return _docker_factory

    raise ProxyHostingError(
        f"Listing {listing.listing_id!r} uses upstream channel "
        f"{ref.channel.value!r}, which is not supported for proxy "
        "hosting. Supported channels: http, pypi, npm, docker."
    )


def build_curator_proxy_server(
    listing: ToolListing,
    *,
    shared_context: Any = None,
) -> SecureMCP:
    """Construct a SecureMCP-enforced proxy server for a curator listing.

    The returned :class:`SecureMCP` instance carries:

    - Security middleware sourced from the listing's manifest
      (allowlist policy + provenance + alerts).
    - A :class:`fastmcp.server.providers.proxy.ProxyProvider` whose
      client factory is dispatched per :class:`UpstreamChannel`:
      HTTP upstreams use a single URL-based client, while PyPI/npm
      upstreams spawn one subprocess per session via uvx/npx.

    Raises:
        ProxyHostingError: When the listing isn't eligible for proxy
            hosting (non-PROXY hosting_mode, missing upstream,
            unsupported channel, or — for npm — a missing ``npx``
            launcher on the registry host).
    """
    if listing.hosting_mode != HostingMode.PROXY:
        raise ProxyHostingError(
            f"Listing {listing.listing_id!r} is not configured for "
            "proxy hosting (hosting_mode is "
            f"{listing.hosting_mode.value!r})."
        )
    if listing.upstream_ref is None:
        raise ProxyHostingError(
            f"Listing {listing.listing_id!r} has no upstream_ref; "
            "proxy mode needs a registered upstream to forward to."
        )

    client_factory = _build_client_factory(listing)
    security = _build_proxy_security_config(listing, shared_context=shared_context)

    proxy = SecureMCP(
        name=f"curator-proxy-{listing.tool_name or listing.listing_id}",
        security=security,
        # Proxy gateway is meant to be an internet-facing edge — STDIO
        # bypass is a no-op here since we'll mount over HTTP, but
        # disable it explicitly to make intent clear.
        bypass_stdio=False,
    )
    # FastMCPProxy is a convenience subclass; we instead use
    # ProxyProvider directly so we can keep our SecureMCP wrapper as
    # the outer FastMCP class (security middleware is attached there).
    proxy_helper = FastMCPProxy.__init__  # silence unused-import lint
    del proxy_helper

    from fastmcp.server.providers.proxy import ProxyProvider

    proxy.add_provider(ProxyProvider(client_factory))

    if shared_context is not None:
        from fastmcp.server.security.middleware.consent_enforcement import (
            ConsentEnforcementMiddleware,
        )
        from fastmcp.server.security.middleware.contract_validation import (
            ContractValidationMiddleware,
        )
        from fastmcp.server.security.middleware.policy_enforcement import (
            PolicyEnforcementMiddleware,
        )

        _SKIP = (
            PolicyEnforcementMiddleware,
            ContractValidationMiddleware,
            ConsentEnforcementMiddleware,
        )
        for mw in shared_context.middleware:
            if isinstance(mw, _SKIP):
                continue
            try:
                proxy.add_middleware(mw)
            except Exception:
                logger.debug(
                    "Could not add shared middleware %s to proxy %s",
                    type(mw).__name__,
                    listing.listing_id,
                    exc_info=True,
                )

    return proxy


class CuratorProxyRouter:
    """ASGI app that hosts curator-mode proxies under
    ``/runtime/proxy/{listing_id}/mcp`` dynamically.

    Modeled on :class:`purecipher.hosted_runtime.ToolsetGatewayRouter` —
    lazy-mounts per-listing apps on first request, caches them, runs
    each app's lifespan inside this router's lifespan.
    """

    def __init__(
        self,
        *,
        listing_lookup: Any,
        auth_settings: "RegistryAuthSettings | None" = None,
        shared_security_context: Any = None,
    ) -> None:
        """
        Args:
            listing_lookup: Callable ``(listing_id: str) -> ToolListing | None``.
            auth_settings: Optional registry auth settings.
            shared_security_context: The registry's central
                :class:`SecurityContext`. When set, proxy servers share
                the registry's ledger, analyzer, and event bus so
                governance events appear in the central dashboards.
        """
        self._lookup = listing_lookup
        self._auth_settings = auth_settings
        self._shared_context = shared_security_context
        self._lock = asyncio.Lock()
        self._apps: dict[str, Starlette] = {}
        self._lifespans: dict[str, Any] = {}

    async def _ensure_app(self, listing_id: str) -> Starlette | None:
        if listing_id in self._apps:
            return self._apps[listing_id]
        async with self._lock:
            if listing_id in self._apps:
                return self._apps[listing_id]
            listing = self._lookup(listing_id)
            if listing is None:
                return None
            try:
                proxy = build_curator_proxy_server(
                    listing, shared_context=self._shared_context
                )
            except ProxyHostingError as exc:
                logger.warning(
                    "Curator proxy mount refused for %s: %s",
                    listing_id,
                    exc,
                )
                return None
            proxy_app = proxy.http_app(
                path=f"/{listing_id}/mcp",
                transport="streamable-http",
            )
            lifespan_ctx = proxy_app.router.lifespan_context(proxy_app)
            await lifespan_ctx.__aenter__()
            self._apps[listing_id] = proxy_app
            self._lifespans[listing_id] = lifespan_ctx
            return proxy_app

    async def aclose(self) -> None:
        """Tear down every cached app's lifespan. Called on shutdown."""
        async with self._lock:
            lifespans = list(self._lifespans.items())
            self._lifespans = {}
            self._apps = {}
        for _, ctx in lifespans:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.warning(
                    "Curator proxy lifespan teardown raised", exc_info=True
                )

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await PlainTextResponse(
                "Unsupported scope.", status_code=400
            )(scope, receive, send)
            return

        # Starlette ``Mount("/runtime/proxy", app=raw_asgi)`` does not
        # rewrite ``scope["path"]`` — the prefix lands in
        # ``scope["root_path"]`` instead. Strip the prefix ourselves so
        # the listing_id is the first path segment regardless of how
        # the router is mounted.
        full_path = str(scope.get("path") or "")
        root_path = str(scope.get("root_path") or "")
        if root_path and full_path.startswith(root_path):
            inner_path = full_path[len(root_path):]
        else:
            inner_path = full_path
        listing_id = inner_path.lstrip("/").split("/", 1)[0].strip()
        if not listing_id:
            await JSONResponse(
                {"error": "Missing listing id.", "status": 400},
                status_code=400,
            )(scope, receive, send)
            return

        listing = self._lookup(listing_id)
        if listing is None:
            await JSONResponse(
                {
                    "error": "Curator listing not found.",
                    "listing_id": listing_id,
                    "status": 404,
                },
                status_code=404,
            )(scope, receive, send)
            return
        if listing.hosting_mode != HostingMode.PROXY:
            await JSONResponse(
                {
                    "error": (
                        "Listing is not configured for proxy hosting "
                        "(hosting_mode is "
                        f"{listing.hosting_mode.value!r})."
                    ),
                    "listing_id": listing_id,
                    "status": 409,
                },
                status_code=409,
            )(scope, receive, send)
            return

        # Iter 14.11 — refuse to forward calls to a deregistered
        # listing. Admin deregistration is terminal; clients still
        # holding stale URLs get a clear 410 Gone rather than a
        # generic 502 from a half-mounted proxy.
        from fastmcp.server.security.gateway.tool_marketplace import PublishStatus

        if listing.status == PublishStatus.DEREGISTERED:
            await JSONResponse(
                {
                    "error": (
                        "This server has been deregistered by the "
                        "registry admin and is no longer available. "
                        "Remove or migrate any client integrations."
                    ),
                    "listing_id": listing_id,
                    "tool_name": listing.tool_name,
                    "status": 410,
                },
                status_code=410,
            )(scope, receive, send)
            return

        app = await self._ensure_app(listing_id)
        if app is None:
            await JSONResponse(
                {
                    "error": (
                        "Listing exists but couldn't be mounted as a "
                        "SecureMCP proxy. Check the upstream channel "
                        "and URL."
                    ),
                    "listing_id": listing_id,
                    "status": 502,
                },
                status_code=502,
            )(scope, receive, send)
            return

        await app(scope, receive, send)


__all__ = [
    "CuratorProxyRouter",
    "ProxyHostingError",
    "build_curator_proxy_server",
]
