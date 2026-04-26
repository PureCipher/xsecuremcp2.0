"""Introspect a third-party MCP server.

Two per-channel introspectors plus a dispatcher:

- HTTP/SSE — :class:`HTTPIntrospector` connects to a curator-supplied
  URL via the FastMCP client SDK.
- Stdio (PyPI / npm / Docker) — :class:`StdioIntrospector` spawns the
  upstream as a subprocess and talks MCP over stdin/stdout. Launchers
  used per channel: ``uvx`` (PyPI), ``npx`` (npm), ``docker run``
  (Docker / OCI images). Subprocess lifecycle is managed by the
  underlying transport; introspection is bounded by a per-call
  timeout so a slow upstream can't hang the wizard.
- :class:`Introspector` is the channel-agnostic dispatcher used by
  the registry routes — it picks the right per-channel introspector
  from the upstream's ``UpstreamRef.channel``.

All three return the same :class:`IntrospectionResult` shape so
``manifest_generator.derive_manifest_draft`` works uniformly.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client
from fastmcp.server.security.gateway.tool_marketplace import (
    UpstreamChannel,
    UpstreamRef,
)

logger = logging.getLogger(__name__)


# Cap how long the registry will wait on a single upstream while
# introspecting. Real MCP servers return list/list/list almost
# instantly; anything slower than this is either misbehaving or an
# adversary, and either way we bail rather than block the wizard.
_DEFAULT_INTROSPECT_TIMEOUT_S = 15.0


class IntrospectionError(RuntimeError):
    """The upstream MCP server could not be introspected.

    Raised with curator-friendly messages so the wizard can render
    them next to the introspect step.
    """


@dataclass
class CapabilityTool:
    """Snapshot of a single tool exposed by the upstream."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "tags": list(self.tags),
        }


@dataclass
class CapabilityResource:
    """Snapshot of a single resource exposed by the upstream."""

    uri: str
    name: str = ""
    description: str = ""
    mime_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mime_type": self.mime_type,
        }


@dataclass
class CapabilityPrompt:
    """Snapshot of a single prompt exposed by the upstream."""

    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description}


@dataclass
class IntrospectionResult:
    """Aggregate observed capabilities for a curated upstream."""

    upstream_ref: UpstreamRef
    tools: list[CapabilityTool] = field(default_factory=list)
    resources: list[CapabilityResource] = field(default_factory=list)
    prompts: list[CapabilityPrompt] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def resource_count(self) -> int:
        return len(self.resources)

    @property
    def prompt_count(self) -> int:
        return len(self.prompts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "upstream_ref": self.upstream_ref.to_dict(),
            "tool_count": self.tool_count,
            "resource_count": self.resource_count,
            "prompt_count": self.prompt_count,
            "duration_ms": round(self.duration_ms, 1),
            "tools": [t.to_dict() for t in self.tools],
            "resources": [r.to_dict() for r in self.resources],
            "prompts": [p.to_dict() for p in self.prompts],
        }


class HTTPIntrospector:
    """Connects to an HTTP MCP upstream and lists its capability surface.

    Args:
        timeout_seconds: Hard cap on how long ``introspect`` will wait
            for the upstream to respond before raising
            :class:`IntrospectionError`. Default 15s.
        client_factory: Optional override for tests — a callable taking
            the URL and returning a client-like object exposing the
            async context manager + ``list_tools``/``list_resources``/
            ``list_prompts`` methods. Production uses the real FastMCP
            client.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = _DEFAULT_INTROSPECT_TIMEOUT_S,
        client_factory: Any = None,
    ) -> None:
        self._timeout = float(timeout_seconds)
        self._client_factory = client_factory or (lambda url: Client(url))

    async def introspect(self, upstream_ref: UpstreamRef) -> IntrospectionResult:
        """Connect to the upstream and capture its capabilities.

        Args:
            upstream_ref: Must be an HTTP-channel ref with a valid URL.

        Raises:
            IntrospectionError: On any connect/list failure or timeout.
                The exception message is curator-facing.
        """
        if upstream_ref.channel != UpstreamChannel.HTTP:
            raise IntrospectionError(
                f"This iteration supports HTTP upstreams only "
                f"(got {upstream_ref.channel.value})."
            )
        url = upstream_ref.identifier
        if not url:
            raise IntrospectionError("Upstream URL is empty.")

        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            result = await asyncio.wait_for(
                self._do_introspect(url, upstream_ref),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            raise IntrospectionError(
                f"Upstream did not respond within {int(self._timeout)}s. "
                "Check the URL and try again."
            ) from exc
        except IntrospectionError:
            raise
        except Exception as exc:
            # Catch every other underlying exception (network, protocol,
            # MCP error) and surface as a curator-facing message. We
            # log at WARNING with full traceback for operators.
            logger.warning(
                "Upstream introspection failed for %s: %s",
                url,
                exc,
                exc_info=True,
            )
            raise IntrospectionError(
                f"Couldn't connect to the upstream MCP server: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        result.duration_ms = (loop.time() - start) * 1000.0
        return result

    async def _do_introspect(
        self, url: str, upstream_ref: UpstreamRef
    ) -> IntrospectionResult:
        client = self._client_factory(url)
        async with client:
            tools_raw = await client.list_tools()
            try:
                resources_raw = await client.list_resources()
            except Exception:
                # Servers that don't implement resources will surface
                # an MCP error here. Treat as "no resources" rather
                # than failing the whole introspection.
                logger.debug(
                    "Upstream %s did not expose resources/list", url
                )
                resources_raw = []
            try:
                prompts_raw = await client.list_prompts()
            except Exception:
                logger.debug(
                    "Upstream %s did not expose prompts/list", url
                )
                prompts_raw = []

        tools = [_to_capability_tool(t) for t in (tools_raw or [])]
        resources = [_to_capability_resource(r) for r in (resources_raw or [])]
        prompts = [_to_capability_prompt(p) for p in (prompts_raw or [])]

        return IntrospectionResult(
            upstream_ref=upstream_ref,
            tools=tools,
            resources=resources,
            prompts=prompts,
        )


# ── Adapters from MCP SDK objects to local capability snapshots ──


def _to_capability_tool(raw: Any) -> CapabilityTool:
    """Tolerant adapter: pulls fields off whatever shape the SDK returns."""
    name = getattr(raw, "name", "") or ""
    description = getattr(raw, "description", "") or ""
    schema = getattr(raw, "inputSchema", None)
    if schema is None:
        schema = getattr(raw, "input_schema", {}) or {}
    if not isinstance(schema, dict):
        try:
            # pydantic models from the MCP SDK expose ``.model_dump``.
            schema = schema.model_dump()  # type: ignore[union-attr]
        except Exception:
            schema = {}
    tags = list(getattr(raw, "tags", []) or [])
    return CapabilityTool(
        name=str(name),
        description=str(description),
        input_schema=dict(schema),
        tags=[str(t) for t in tags],
    )


def _to_capability_resource(raw: Any) -> CapabilityResource:
    uri = getattr(raw, "uri", "") or ""
    return CapabilityResource(
        uri=str(uri),
        name=str(getattr(raw, "name", "") or ""),
        description=str(getattr(raw, "description", "") or ""),
        mime_type=str(getattr(raw, "mimeType", "") or getattr(raw, "mime_type", "") or ""),
    )


def _to_capability_prompt(raw: Any) -> CapabilityPrompt:
    return CapabilityPrompt(
        name=str(getattr(raw, "name", "") or ""),
        description=str(getattr(raw, "description", "") or ""),
    )


# ── Stdio (PyPI / npm / Docker) introspector ───────────────────


# uvx / npx / docker may need extra time on cold cache (image pulls in
# particular). Bound by the per-introspection timeout below.
_STDIO_INTROSPECT_TIMEOUT_S = 60.0


# Launcher resource limits for Docker introspection. Keep small —
# introspection only needs the upstream long enough to answer
# tools/list / resources/list / prompts/list.
_DOCKER_INTROSPECT_FLAGS = (
    "--rm",  # auto-remove the container on exit
    "-i",  # keep stdin open for the MCP stdio transport
    "--memory=512m",
    "--pids-limit=128",
)


def _launcher_name_for_channel(channel) -> str:
    """Map an :class:`UpstreamChannel` to the OS-level launcher binary.

    Used by error messages so the curator sees the actual command to
    install (``uvx`` / ``npx`` / ``docker``) rather than a channel name.
    """
    from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

    if channel == UpstreamChannel.PYPI:
        return "uvx"
    if channel == UpstreamChannel.NPM:
        return "npx"
    if channel == UpstreamChannel.DOCKER:
        return "docker"
    return channel.value if hasattr(channel, "value") else str(channel)


class StdioIntrospector:
    """Spawns a PyPI / npm / Docker upstream as a subprocess and lists
    its MCP surface.

    Channel → launcher mapping:

    - ``PYPI``   → ``uvx`` (via :class:`UvxStdioTransport`)
    - ``NPM``    → ``npx`` (via :class:`NpxStdioTransport`)
    - ``DOCKER`` → ``docker run --rm -i ...`` (via the generic
      :class:`StdioTransport`)

    All three require the respective launcher to be available on PATH
    at the registry server. A missing launcher surfaces as a clear,
    curator-friendly error.

    Subprocess lifecycle is owned by the FastMCP transport — the
    ``async with client:`` context starts the subprocess and tears it
    down on exit. We wrap the entire block in :func:`asyncio.wait_for`
    so a slow / wedged package can't hang the wizard.

    Args:
        timeout_seconds: Hard cap for the introspection call.
        client_factory: Optional ``(channel, identifier, version) →
            client`` override for tests so we don't actually launch
            uvx / npx / docker.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = _STDIO_INTROSPECT_TIMEOUT_S,
        client_factory: Any = None,
    ) -> None:
        self._timeout = float(timeout_seconds)
        self._client_factory = client_factory

    async def introspect(self, upstream_ref) -> IntrospectionResult:
        from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

        channel = upstream_ref.channel
        if channel not in (
            UpstreamChannel.PYPI,
            UpstreamChannel.NPM,
            UpstreamChannel.DOCKER,
        ):
            raise IntrospectionError(
                f"StdioIntrospector handles PyPI / npm / Docker only "
                f"(got {channel.value})."
            )
        if not upstream_ref.identifier:
            raise IntrospectionError("Upstream identifier is empty.")

        client = self._build_client(upstream_ref)
        launcher = _launcher_name_for_channel(channel)

        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            result = await asyncio.wait_for(
                self._do_introspect(client, upstream_ref),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            # Docker pulls can be slow on cold cache; mention this in
            # the timeout copy so the curator knows it's a one-time
            # cost rather than a "this MCP server is broken" signal.
            extra = (
                " (Docker images on cold cache may take longer than "
                "the timeout while the image is pulled — re-running "
                "introspection often succeeds on the second try.)"
                if channel == UpstreamChannel.DOCKER
                else ""
            )
            raise IntrospectionError(
                f"Subprocess introspection timed out after "
                f"{int(self._timeout)}s. The package may have a slow "
                f"first launch — try once more, or pass a smaller "
                f"package.{extra}"
            ) from exc
        except IntrospectionError:
            raise
        except FileNotFoundError as exc:
            # uvx / npx / docker missing on PATH — give the operator the fix.
            raise IntrospectionError(
                f"Couldn't find {launcher!r} on PATH. The registry needs "
                f"{launcher} installed to introspect "
                f"{channel.value} upstreams."
            ) from exc
        except ValueError as exc:
            # FastMCP's NpxStdioTransport raises ValueError if npx is
            # missing; surface as a friendly message.
            if launcher in str(exc).lower():
                raise IntrospectionError(
                    f"Couldn't find {launcher!r} on PATH. The registry "
                    f"needs {launcher} installed to introspect "
                    f"{channel.value} upstreams."
                ) from exc
            raise
        except Exception as exc:
            logger.warning(
                "Stdio introspection failed for %s:%s: %s",
                channel.value,
                upstream_ref.identifier,
                exc,
                exc_info=True,
            )
            raise IntrospectionError(
                f"Couldn't introspect the {channel.value} upstream "
                f"{upstream_ref.identifier!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        result.duration_ms = (loop.time() - start) * 1000.0
        return result

    def _build_client(self, upstream_ref) -> Any:
        """Construct the MCP client with the right stdio transport."""
        from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

        if self._client_factory is not None:
            return self._client_factory(
                upstream_ref.channel,
                upstream_ref.identifier,
                upstream_ref.version,
            )

        from fastmcp import Client
        from fastmcp.client.transports.stdio import (
            NpxStdioTransport,
            StdioTransport,
            UvxStdioTransport,
        )

        if upstream_ref.channel == UpstreamChannel.PYPI:
            spec = (
                f"{upstream_ref.identifier}@{upstream_ref.version}"
                if upstream_ref.version
                else upstream_ref.identifier
            )
            transport = UvxStdioTransport(tool_name=spec)
            return Client(transport)
        if upstream_ref.channel == UpstreamChannel.NPM:
            spec = (
                f"{upstream_ref.identifier}@{upstream_ref.version}"
                if upstream_ref.version
                else upstream_ref.identifier
            )
            transport = NpxStdioTransport(package=spec)
            return Client(transport)
        # Docker: ``docker run --rm -i [resource flags] <image_ref>``
        # — generic StdioTransport bridges container stdin/stdout to
        # the FastMCP client. Resource limits are conservative; the
        # operator can tune them via daemon-level config if needed.
        from purecipher.curation.upstream import image_ref_for

        image_ref = image_ref_for(upstream_ref)
        transport = StdioTransport(
            command="docker",
            args=[*_DOCKER_INTROSPECT_FLAGS, image_ref],
        )
        return Client(transport)

    async def _do_introspect(self, client: Any, upstream_ref) -> IntrospectionResult:
        async with client:
            tools_raw = await client.list_tools()
            try:
                resources_raw = await client.list_resources()
            except Exception:
                logger.debug(
                    "Stdio upstream %s did not expose resources/list",
                    upstream_ref.identifier,
                )
                resources_raw = []
            try:
                prompts_raw = await client.list_prompts()
            except Exception:
                logger.debug(
                    "Stdio upstream %s did not expose prompts/list",
                    upstream_ref.identifier,
                )
                prompts_raw = []

        tools = [_to_capability_tool(t) for t in (tools_raw or [])]
        resources = [_to_capability_resource(r) for r in (resources_raw or [])]
        prompts = [_to_capability_prompt(p) for p in (prompts_raw or [])]
        return IntrospectionResult(
            upstream_ref=upstream_ref,
            tools=tools,
            resources=resources,
            prompts=prompts,
        )


# ── Channel dispatcher ─────────────────────────────────────────


def check_introspection_launchers() -> dict[str, str | None]:
    """Probe PATH for ``uvx`` / ``npx`` / ``docker`` and return paths.

    Operators can call this at startup to log whether the registry
    can introspect PyPI / npm / Docker channels in this environment.
    Missing launchers are not fatal — HTTP-channel curation keeps
    working — but any ``pypi:`` / ``npm:`` / ``docker:`` curate
    attempt will fail with a "couldn't find on PATH" error until the
    relevant launcher is installed.

    Returns:
        Mapping ``{launcher_name: resolved_path_or_None}``. Logs a
        warning for each missing launcher.
    """
    found: dict[str, str | None] = {
        "uvx": shutil.which("uvx"),
        "npx": shutil.which("npx"),
        "docker": shutil.which("docker"),
    }
    if found["uvx"] is None:
        logger.warning(
            "Curator stdio introspection: 'uvx' not on PATH. PyPI "
            "(pypi:...) curate submissions will fail. Install with "
            "'pip install uv' (uv ships with the registry's runtime "
            "deps; if you're seeing this, your environment isn't "
            "picking it up)."
        )
    if found["npx"] is None:
        logger.warning(
            "Curator stdio introspection: 'npx' not on PATH. npm "
            "(npm:...) curate submissions will fail. Install Node.js "
            "(any LTS) on the registry server to enable npm curation."
        )
    if found["docker"] is None:
        logger.warning(
            "Curator stdio introspection: 'docker' not on PATH. "
            "Docker (docker:...) curate submissions will fail. "
            "Install Docker (or a compatible OCI runtime exposing the "
            "'docker' CLI) on the registry server to enable Docker "
            "curation."
        )
    return found


class Introspector:
    """Channel-agnostic introspector. Dispatches to HTTP or stdio
    based on the upstream's channel.
    """

    def __init__(
        self,
        *,
        http_introspector: HTTPIntrospector | None = None,
        stdio_introspector: StdioIntrospector | None = None,
    ) -> None:
        self._http = http_introspector or HTTPIntrospector()
        self._stdio = stdio_introspector or StdioIntrospector()

    async def introspect(self, upstream_ref) -> IntrospectionResult:
        from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

        if upstream_ref.channel == UpstreamChannel.HTTP:
            return await self._http.introspect(upstream_ref)
        if upstream_ref.channel in (
            UpstreamChannel.PYPI,
            UpstreamChannel.NPM,
            UpstreamChannel.DOCKER,
        ):
            return await self._stdio.introspect(upstream_ref)
        raise IntrospectionError(
            f"Channel {upstream_ref.channel.value} is not supported in "
            "this iteration."
        )
