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

Iter 14.8 — token-on-introspect. Some upstream MCP servers (Stripe,
Slack, GitHub, Linear, Notion) refuse to start, or return zero tools,
unless a credential is present in their environment. To unblock those
during the Onboard wizard, both the stdio and HTTP introspectors
accept an optional ``env`` dict that's threaded into the spawn (stdio)
or attached as headers (HTTP). The credentials are passed once for
introspection and dropped from process memory when ``introspect``
returns — the registry never persists them. Logging of subprocess
arguments uses an explicit redactor so token values don't leak into
operator logs.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client
from fastmcp.server.security.gateway.tool_marketplace import (
    UpstreamChannel,
    UpstreamRef,
)

logger = logging.getLogger(__name__)


# ── Iter 14.8 — credential validation ──────────────────────────

# POSIX env var names: leading letter or underscore, followed by
# letters, digits, or underscores. We additionally upper-case and
# reject lowercase keys to catch obvious typos like ``Github_Token``.
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

# Hard cap on env value length — keeps logs and request bodies sane,
# and blocks accidental file-paste of an entire .env. Real tokens are
# well under this.
_ENV_VALUE_MAX_LEN = 4096

# Hard cap on number of credentials accepted in a single introspect
# call. Real-world MCP servers need 1-3; anything more is suspicious.
_ENV_MAX_KEYS = 32

# Env var names we refuse to override. Letting a curator set ``PATH``
# or ``LD_PRELOAD`` during introspection would let them re-route the
# launcher itself; ``HOME`` and ``USER`` are equally load-bearing for
# uvx / npx caches. Tokens never need these names.
_ENV_REJECTED_KEYS = frozenset(
    {
        "PATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
        "HOME",
        "USER",
        "SHELL",
        "PYTHONPATH",
        "PYTHONHOME",
        "NODE_OPTIONS",
        "NODE_PATH",
    }
)


class CredentialValidationError(ValueError):
    """Raised when a curator-supplied env dict is malformed or unsafe.

    Distinct from :class:`IntrospectionError` so the registry route can
    return 400 (bad input from the wizard) instead of 502 (upstream
    couldn't be reached).
    """


def validate_introspect_env(
    env: dict[str, str] | None,
) -> dict[str, str] | None:
    """Validate a curator-supplied env dict for one-shot introspection.

    Iter 14.8. Performs strict input validation:

    - ``None`` or empty dict → returns ``None`` (caller treats as
      "no credentials, spawn with default environment").
    - Keys must match POSIX env var naming and must not be in the
      reserved set above.
    - Values must be non-empty strings ≤ ``_ENV_VALUE_MAX_LEN``.
    - Total entries must be ≤ ``_ENV_MAX_KEYS``.

    Raises:
        CredentialValidationError: With a curator-friendly message if
            any check fails. Caller surfaces verbatim.
    """
    if not env:
        return None
    if not isinstance(env, dict):
        raise CredentialValidationError(
            "Credentials must be a JSON object of {KEY: value} pairs."
        )
    if len(env) > _ENV_MAX_KEYS:
        raise CredentialValidationError(
            f"Too many credential entries ({len(env)}); max is "
            f"{_ENV_MAX_KEYS}. Pass only what the upstream needs."
        )
    cleaned: dict[str, str] = {}
    for raw_key, raw_value in env.items():
        if not isinstance(raw_key, str):
            raise CredentialValidationError("Credential keys must be strings.")
        key = raw_key.strip()
        if not _ENV_KEY_RE.match(key):
            raise CredentialValidationError(
                f"Invalid credential key {raw_key!r}. Use uppercase env "
                f"var names like GITHUB_PERSONAL_ACCESS_TOKEN."
            )
        if key in _ENV_REJECTED_KEYS:
            raise CredentialValidationError(
                f"{key} cannot be set during introspection — it would "
                "override the launcher's own environment. If your MCP "
                "server really needs it, contact the registry operator."
            )
        if not isinstance(raw_value, str):
            raise CredentialValidationError(
                f"Credential value for {key!r} must be a string."
            )
        if len(raw_value) == 0:
            raise CredentialValidationError(
                f"Credential value for {key!r} is empty. Remove the "
                "key or fill in a value."
            )
        if len(raw_value) > _ENV_VALUE_MAX_LEN:
            raise CredentialValidationError(
                f"Credential value for {key!r} is too long "
                f"({len(raw_value)} chars; max {_ENV_VALUE_MAX_LEN})."
            )
        cleaned[key] = raw_value
    return cleaned or None


def _redacted_env_keys(env: dict[str, str] | None) -> str:
    """Render an env dict for logs without leaking values.

    Returns a comma-joined list of just the keys, e.g.
    ``"GITHUB_PERSONAL_ACCESS_TOKEN, SLACK_BOT_TOKEN"``. Used inside
    log messages so operators can see *what* was passed without ever
    seeing the values themselves.
    """
    if not env:
        return "(none)"
    return ", ".join(sorted(env.keys()))


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

    async def introspect(
        self,
        upstream_ref: UpstreamRef,
        *,
        env: dict[str, str] | None = None,
    ) -> IntrospectionResult:
        """Connect to the upstream and capture its capabilities.

        Args:
            upstream_ref: Must be an HTTP-channel ref with a valid URL.
            env: Iter 14.8 — currently not supported for HTTP. HTTP MCP
                servers expect credentials inline in the URL or via
                bearer headers; we don't have a robust way to pick the
                right header name from a generic env dict yet, so the
                wizard hides the credential editor for HTTP upstreams.
                Passing a non-empty env raises so a curator can't be
                misled into thinking it's being sent.

        Raises:
            IntrospectionError: On any connect/list failure or timeout.
                The exception message is curator-facing.
        """
        if upstream_ref.channel != UpstreamChannel.HTTP:
            raise IntrospectionError(
                f"This iteration supports HTTP upstreams only "
                f"(got {upstream_ref.channel.value})."
            )
        if env:
            raise IntrospectionError(
                "Credentials at introspect time are only supported for "
                "PyPI / npm / Docker upstreams. For HTTP MCP servers, "
                "embed the token in the URL or expose an authenticated "
                "endpoint."
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
                logger.debug("Upstream %s did not expose resources/list", url)
                resources_raw = []
            try:
                prompts_raw = await client.list_prompts()
            except Exception:
                logger.debug("Upstream %s did not expose prompts/list", url)
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
        mime_type=str(
            getattr(raw, "mimeType", "") or getattr(raw, "mime_type", "") or ""
        ),
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

    async def introspect(
        self,
        upstream_ref,
        *,
        env: dict[str, str] | None = None,
    ) -> IntrospectionResult:
        """Spawn the stdio upstream and capture its capabilities.

        Args:
            upstream_ref: PyPI / npm / Docker channel ref.
            env: Iter 14.8 — optional one-shot environment. Threaded
                into the subprocess (uvx / npx) or as ``-e KEY=VALUE``
                flags on the docker run command. Dropped from process
                memory when this method returns; never logged with
                values; never persisted.
        """
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

        if env:
            # Log keys only — never values. Operators want to see whether
            # a curator passed credentials (and which ones) for support
            # debugging, but the values must stay out of logs.
            logger.info(
                "Stdio introspect: %s:%s with credential keys: %s",
                channel.value,
                upstream_ref.identifier,
                _redacted_env_keys(env),
            )

        client = self._build_client(upstream_ref, env=env)
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

    def _build_client(
        self,
        upstream_ref,
        *,
        env: dict[str, str] | None = None,
    ) -> Any:
        """Construct the MCP client with the right stdio transport.

        Iter 14.8 — accepts an optional ``env`` dict that's passed
        through to the launcher subprocess so token-required servers
        (Stripe / Slack / GitHub / Linear / Notion) can return their
        full tool list during introspection.
        """
        from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

        if self._client_factory is not None:
            # Test factories accept an optional env kwarg. Older test
            # factories that pre-date Iter 14.8 (3-positional only) keep
            # working — we fall back to the un-env'd signature.
            try:
                return self._client_factory(
                    upstream_ref.channel,
                    upstream_ref.identifier,
                    upstream_ref.version,
                    env=env,
                )
            except TypeError:
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
            transport = UvxStdioTransport(tool_name=spec, env_vars=env)
            return Client(transport)
        if upstream_ref.channel == UpstreamChannel.NPM:
            spec = (
                f"{upstream_ref.identifier}@{upstream_ref.version}"
                if upstream_ref.version
                else upstream_ref.identifier
            )
            transport = NpxStdioTransport(package=spec, env_vars=env)
            return Client(transport)
        # Docker: ``docker run --rm -i [resource flags] [-e KEY ...]
        # <image_ref>`` — generic StdioTransport bridges container
        # stdin/stdout to the FastMCP client. Resource limits are
        # conservative; the operator can tune them via daemon-level
        # config if needed.
        #
        # Iter 14.8 — credential handling for Docker is two-step:
        # 1. We pass ``-e KEY`` flags (without the value) on argv so
        #    Docker knows which vars to forward into the container.
        # 2. We set the actual KEY=VALUE on the docker CLI's *own*
        #    environment via the StdioTransport ``env`` parameter.
        # Docker then forwards the value from its own environ into the
        # container at startup. This keeps the secret out of the host
        # process listing (``ps`` only sees ``-e GITHUB_TOKEN``, never
        # the value), which a curator-supplied ``KEY=VALUE`` argv
        # form would have exposed.
        from purecipher.curation.upstream import image_ref_for

        image_ref = image_ref_for(upstream_ref)
        docker_args: list[str] = list(_DOCKER_INTROSPECT_FLAGS)
        docker_env: dict[str, str] | None = None
        if env:
            for key in env:
                docker_args.extend(["-e", key])
            docker_env = dict(env)
        docker_args.append(image_ref)
        transport = StdioTransport(
            command="docker",
            args=docker_args,
            env=docker_env,
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

    async def introspect(
        self,
        upstream_ref,
        *,
        env: dict[str, str] | None = None,
    ) -> IntrospectionResult:
        """Dispatch to the right per-channel introspector.

        Args:
            upstream_ref: Resolved upstream reference.
            env: Iter 14.8 — optional one-shot environment for stdio
                channels (PyPI / npm / Docker). Forwarded into the
                spawned subprocess and dropped from memory when this
                method returns. HTTP rejects non-empty env (see
                :meth:`HTTPIntrospector.introspect`).
        """
        from fastmcp.server.security.gateway.tool_marketplace import UpstreamChannel

        if upstream_ref.channel == UpstreamChannel.HTTP:
            return await self._http.introspect(upstream_ref, env=env)
        if upstream_ref.channel in (
            UpstreamChannel.PYPI,
            UpstreamChannel.NPM,
            UpstreamChannel.DOCKER,
        ):
            return await self._stdio.introspect(upstream_ref, env=env)
        raise IntrospectionError(
            f"Channel {upstream_ref.channel.value} is not supported in this iteration."
        )
