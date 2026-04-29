"""Resolve a curator-supplied upstream reference into a registry preview.

Four channels supported:

- ``HTTP`` — direct MCP HTTP/SSE endpoint. Pasted as a URL.
- ``PYPI`` — Python package on PyPI. Pasted as ``pypi:pkg@version``
  or just the bare package name.
- ``NPM``  — npm package. Pasted as ``npm:@scope/pkg@version`` or
  ``npm:pkg``.
- ``DOCKER`` — Docker / OCI image. Pasted as ``docker:image:tag`` or
  ``docker:image@sha256:...`` (digest preferred). Custom registries
  are supported via ``docker:registry/namespace/image:tag``.

GitHub channel is reserved on :class:`UpstreamChannel` but not
implemented yet. The curator wizard auto-detects the channel from the
prefix (``pypi:`` / ``npm:`` / ``docker:``) or scheme (``https://``);
ambiguous inputs are rejected with a clear message.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from fastmcp.server.security.gateway.tool_marketplace import (
    UpstreamChannel,
    UpstreamRef,
)

logger = logging.getLogger(__name__)


# Schemes accepted for HTTP-channel curation. We intentionally refuse
# ``http://`` for non-loopback hosts so curated listings carry signed
# attestations of TLS-protected upstreams. Loopback is allowed because
# operators sometimes onboard via an SSH tunnel or local dev server.
_ALLOWED_HTTP_SCHEMES = {"https", "http"}
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

import os as _os

_EXTRA_HTTP_HOSTS = frozenset(
    h.strip().lower()
    for h in _os.getenv("PURECIPHER_ALLOW_HTTP_HOSTS", "").split(",")
    if h.strip()
)
_HTTP_ALLOWED_HOSTS = _LOOPBACK_HOSTS | _EXTRA_HTTP_HOSTS

# Path segments commonly used as transport markers — when they show up
# as the last URL segment, they make terrible tool-name slugs. Fall
# back to the host's primary label instead.
_TRANSPORT_SUFFIXES = {"sse", "mcp", "stream", "stream-http", "ws", "websocket"}


class UpstreamResolutionError(ValueError):
    """The curator-supplied upstream reference is invalid or unreachable.

    Raised with operator-friendly messages so the wizard can surface
    them inline (e.g. "URL must use https://").
    """


@dataclass
class UpstreamPreview:
    """The registry's draft preview of a resolved upstream.

    Returned by the resolve step of the onboard wizard. The curator
    confirms or edits the fields, then the wizard moves to introspect.
    """

    upstream_ref: UpstreamRef
    suggested_tool_name: str = ""
    suggested_display_name: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "upstream_ref": self.upstream_ref.to_dict(),
            "suggested_tool_name": self.suggested_tool_name,
            "suggested_display_name": self.suggested_display_name,
            "notes": list(self.notes),
        }


def _reject_internal_host(host: str) -> None:
    """SSRF defence: refuse curator-supplied hosts that resolve to or
    are obviously private / link-local / cloud-metadata addresses.

    The check is *literal* — we don't DNS-resolve here (that's the
    introspector's job and it can pin to the resolved IP). What we
    catch are URLs whose host is *itself* an IP literal in a
    sensitive range, plus the well-known cloud metadata service.

    DNS-rebinding-style attacks where a hostname resolves to a public
    IP at validation time and a private IP at fetch time are mitigated
    in the introspector's connect path, not here.
    """
    if not host:
        return
    lower = host.lower()
    if lower in _LOOPBACK_HOSTS:
        return  # Loopback is explicitly allowed for dev.
    # The cloud-provider metadata service. Refused with a specific
    # message so curators understand why.
    if lower in {"169.254.169.254", "metadata.google.internal", "fd00:ec2::254"}:
        raise UpstreamResolutionError(
            "Refusing to curate a cloud-metadata endpoint."
        )
    # IP-literal in a private/link-local/multicast/reserved range?
    try:
        addr = ipaddress.ip_address(lower)
    except ValueError:
        return  # Hostname, not an IP literal — let DNS handle it.
    if (
        addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise UpstreamResolutionError(
            "Refusing to curate a private / link-local / reserved IP. "
            "Use a public hostname or HTTPS URL."
        )


def _split_versioned(spec: str) -> tuple[str, str]:
    """Split ``pkg@version`` into ``(pkg, version)``; leave ``pkg`` if no @.

    Handles npm-scoped names like ``@scope/pkg@1.0`` correctly: the
    first ``@`` (the scope) is preserved, only the *last* ``@`` is
    treated as the version separator.
    """
    if "@" not in spec or spec.startswith("@") and spec.count("@") == 1:
        return spec, ""
    last_at = spec.rfind("@")
    # Scoped npm: ``@scope/pkg`` — only one @ at the start, no version.
    if last_at == 0:
        return spec, ""
    return spec[:last_at], spec[last_at + 1 :]


# Python identifier rules for PyPI package names per PEP 503: letters,
# digits, dots, dashes, underscores. We keep it permissive but
# bounded so curator input doesn't accidentally smuggle path segments.
_PYPI_PKG_RE = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_NPM_PKG_RE = __import__("re").compile(
    r"^(@[a-z0-9][\w.-]*\/)?[a-z0-9][\w.-]*$",
    flags=__import__("re").IGNORECASE,
)


def parse_pypi_upstream(raw: str) -> UpstreamRef:
    """Parse ``pypi:pkg`` / ``pypi:pkg@version`` into an :class:`UpstreamRef`.

    The bare ``pypi:`` prefix is required so the wizard can't
    mis-detect a typo URL as a Python package. Version is optional —
    when omitted, the resolver picks the latest published version.
    """
    if not isinstance(raw, str):
        raise UpstreamResolutionError("Upstream reference must be text.")
    cleaned = raw.strip()
    if not cleaned.lower().startswith("pypi:"):
        raise UpstreamResolutionError(
            "PyPI upstream must start with 'pypi:' "
            "(e.g. 'pypi:markitdown-mcp@1.2.3')."
        )
    spec = cleaned[len("pypi:") :].strip()
    if not spec:
        raise UpstreamResolutionError(
            "Empty PyPI package name after 'pypi:' prefix."
        )
    pkg, version = _split_versioned(spec)
    if not _PYPI_PKG_RE.match(pkg):
        raise UpstreamResolutionError(
            f"Invalid PyPI package name: {pkg!r}."
        )
    return UpstreamRef(
        channel=UpstreamChannel.PYPI,
        identifier=pkg,
        version=version,
        pinned_hash="",
        source_url="",
        metadata={"raw_spec": cleaned},
    )


def parse_npm_upstream(raw: str) -> UpstreamRef:
    """Parse ``npm:pkg`` / ``npm:@scope/pkg@version`` into an :class:`UpstreamRef`.

    Scoped names (``@modelcontextprotocol/server-everything``) are
    supported. The version is optional.
    """
    if not isinstance(raw, str):
        raise UpstreamResolutionError("Upstream reference must be text.")
    cleaned = raw.strip()
    if not cleaned.lower().startswith("npm:"):
        raise UpstreamResolutionError(
            "npm upstream must start with 'npm:' "
            "(e.g. 'npm:@modelcontextprotocol/server-everything@0.5.0')."
        )
    spec = cleaned[len("npm:") :].strip()
    if not spec:
        raise UpstreamResolutionError(
            "Empty npm package name after 'npm:' prefix."
        )
    pkg, version = _split_versioned(spec)
    if not _NPM_PKG_RE.match(pkg):
        raise UpstreamResolutionError(
            f"Invalid npm package name: {pkg!r}."
        )
    return UpstreamRef(
        channel=UpstreamChannel.NPM,
        identifier=pkg,
        version=version,
        pinned_hash="",
        source_url="",
        metadata={"raw_spec": cleaned},
    )


# Docker / OCI image references — strict-but-pragmatic. The OCI spec
# allows lowercase alphanumerics plus ``.``, ``-``, ``_``, with ``/``
# separating path components, and an optional registry domain
# (which may include a port like ``localhost:5000``). We don't do a
# full grammar match because real-world references are messier than
# the spec; we reject obvious garbage and accept the rest.
_DOCKER_REF_RE = __import__("re").compile(
    r"^[a-z0-9]([a-z0-9._/:-]*[a-z0-9])?$"
)
_DOCKER_TAG_RE = __import__("re").compile(r"^[\w][\w.-]{0,127}$")
_DOCKER_DIGEST_RE = __import__("re").compile(
    r"^sha(?:256:[a-f0-9]{64}|512:[a-f0-9]{128})$"
)


def _split_docker_reference(spec: str) -> tuple[str, str, str]:
    """Split ``image[:tag][@digest]`` into ``(image, tag, digest)``.

    Handles the OCI reference grammar pragmatically:

    - The digest, if present, is everything after the last ``@``.
    - The tag, if present, is everything between the last ``/`` and
      the first ``:`` that follows it (so ``localhost:5000/img:v1``
      yields tag ``v1``, not the registry's port).
    """
    digest = ""
    if "@" in spec:
        at_idx = spec.rfind("@")
        digest = spec[at_idx + 1 :].strip()
        spec = spec[:at_idx]

    last_slash = spec.rfind("/")
    tag = ""
    # Look for ``:`` AFTER the last slash so we don't mistake a
    # registry port (``localhost:5000``) for a tag separator.
    colon_search_start = last_slash + 1 if last_slash >= 0 else 0
    last_colon = spec.find(":", colon_search_start)
    if last_colon > 0:
        tag = spec[last_colon + 1 :]
        spec = spec[:last_colon]

    return spec, tag, digest


def _detect_docker_registry(image_name: str) -> str:
    """Return the registry portion of an image reference, or ``docker.io``.

    The first path component is treated as a registry domain when it
    contains a ``.``, a ``:`` (port), or is the literal string
    ``localhost``. Everything else is assumed to live on Docker Hub.
    """
    if "/" not in image_name:
        return "docker.io"
    first = image_name.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return "docker.io"


def parse_docker_upstream(raw: str) -> UpstreamRef:
    """Parse ``docker:image[:tag][@sha256:...]`` into an :class:`UpstreamRef`.

    Accepted forms (after stripping the ``docker:`` prefix):

    - ``image``                                  (e.g. ``nginx``)
    - ``image:tag``                              (e.g. ``nginx:latest``)
    - ``image@sha256:...``                       (digest-pinned)
    - ``image:tag@sha256:...``                   (both)
    - ``namespace/image:tag``                    (e.g. ``library/nginx:1``)
    - ``registry/namespace/image[:tag][@digest]``
                                                (e.g. ``ghcr.io/x/y:v1``,
                                                ``localhost:5000/img:dev``)

    Notes:

    - Digests must be ``sha256:`` (64 hex) or ``sha512:`` (128 hex) —
      the only algorithms the OCI spec mandates support for. Bare
      hashes without the algorithm prefix are rejected.
    - Tags follow Docker's reference grammar: word char start, then
      word chars / ``.`` / ``-``, capped at 128 chars. We don't verify
      the tag actually exists on the upstream registry; that would
      require a network call, which the parser intentionally avoids.
    - The reference ``image_name`` returned in :attr:`UpstreamRef.identifier`
      is the bare repository portion *without* tag/digest. Reconstruct
      a full ref via ``image_ref_for(upstream_ref)``.
    """
    if not isinstance(raw, str):
        raise UpstreamResolutionError("Upstream reference must be text.")
    cleaned = raw.strip()
    if not cleaned.lower().startswith("docker:"):
        raise UpstreamResolutionError(
            "Docker upstream must start with 'docker:' "
            "(e.g. 'docker:ghcr.io/example/mcp:v1' or "
            "'docker:nginx@sha256:abcdef...')."
        )
    spec = cleaned[len("docker:") :].strip()
    if not spec:
        raise UpstreamResolutionError(
            "Empty Docker reference after 'docker:' prefix."
        )

    image_name, tag, digest = _split_docker_reference(spec)
    if not image_name:
        raise UpstreamResolutionError(
            "Docker reference is missing the image name."
        )
    if not _DOCKER_REF_RE.match(image_name):
        raise UpstreamResolutionError(
            f"Invalid Docker image name: {image_name!r}. Use lowercase "
            "alphanumerics with '.', '-', '_', '/', and an optional "
            "registry domain like 'ghcr.io/...'."
        )
    if tag and not _DOCKER_TAG_RE.match(tag):
        raise UpstreamResolutionError(
            f"Invalid Docker tag: {tag!r}. Tags must start with a word "
            "char and contain only word chars, '.', or '-'."
        )
    if digest and not _DOCKER_DIGEST_RE.match(digest):
        raise UpstreamResolutionError(
            f"Invalid Docker digest: {digest!r}. Use 'sha256:<64-hex>' "
            "or 'sha512:<128-hex>'."
        )

    registry = _detect_docker_registry(image_name)
    return UpstreamRef(
        channel=UpstreamChannel.DOCKER,
        identifier=image_name,
        version=tag,
        pinned_hash=digest,
        source_url="",
        metadata={"raw_spec": cleaned, "registry": registry},
    )


def image_ref_for(upstream_ref: UpstreamRef) -> str:
    """Reconstruct the full ``image[:tag][@digest]`` form for ``docker run``.

    Used by the introspector and proxy runtime when invoking
    ``docker run --rm -i <image_ref>``. Prefers the digest over the
    tag for reproducibility — when both are present we still pass
    both to docker (it accepts ``image:tag@digest`` and validates the
    digest matches the tag's manifest), but a digest-only reference
    is the safest form.
    """
    parts = upstream_ref.identifier
    if upstream_ref.version:
        parts = f"{parts}:{upstream_ref.version}"
    if upstream_ref.pinned_hash:
        parts = f"{parts}@{upstream_ref.pinned_hash}"
    return parts


def parse_upstream(raw: str) -> UpstreamRef:
    """Top-level parser: dispatch to the right channel parser.

    Auto-detects channel from prefix:

    - ``pypi:...``    → PyPI
    - ``npm:...``     → npm
    - ``docker:...``  → Docker / OCI image
    - ``http(s)://...`` → HTTP

    Anything else fails fast with a curator-facing message that lists
    the supported prefixes.
    """
    if not isinstance(raw, str):
        raise UpstreamResolutionError("Upstream reference must be text.")
    cleaned = raw.strip()
    lower = cleaned.lower()
    if lower.startswith("pypi:"):
        return parse_pypi_upstream(cleaned)
    if lower.startswith("npm:"):
        return parse_npm_upstream(cleaned)
    if lower.startswith("docker:"):
        return parse_docker_upstream(cleaned)
    if lower.startswith("http://") or lower.startswith("https://"):
        return parse_http_upstream(cleaned)
    raise UpstreamResolutionError(
        "Couldn't tell what kind of upstream this is. Use a URL "
        "(https://...), a PyPI package (pypi:pkg@version), an npm "
        "package (npm:pkg@version), or a Docker image "
        "(docker:image:tag or docker:image@sha256:...)."
    )


def parse_http_upstream(raw: str) -> UpstreamRef:
    """Parse a curator-pasted HTTP upstream URL into an :class:`UpstreamRef`.

    Validates scheme, host, and basic shape. Raises
    :class:`UpstreamResolutionError` with a user-facing message on any
    failure so the wizard can render it inline next to the input.

    Args:
        raw: Whatever the curator pasted into the wizard input.

    Returns:
        An :class:`UpstreamRef` with channel ``HTTP``, identifier set to
        the validated URL, and an empty version (HTTP endpoints aren't
        content-addressable).
    """
    if not isinstance(raw, str):
        raise UpstreamResolutionError("Upstream URL must be text.")
    cleaned = raw.strip()
    if not cleaned:
        raise UpstreamResolutionError("Paste an MCP server URL to continue.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in _ALLOWED_HTTP_SCHEMES:
        raise UpstreamResolutionError(
            "Use a URL starting with https:// (or http:// for loopback)."
        )
    if not parsed.netloc:
        raise UpstreamResolutionError(
            "URL is missing a host. Did you paste a path by itself?"
        )

    host = parsed.hostname or ""
    if parsed.scheme == "http" and host.lower() not in _HTTP_ALLOWED_HOSTS:
        raise UpstreamResolutionError(
            "Plain http:// is only allowed for loopback. Use https://."
        )

    # SSRF defence: refuse private / link-local / cloud-metadata IPs.
    _reject_internal_host(host)

    # Canonicalize: strip auth + fragment, lowercase the scheme + host,
    # drop a trailing slash on the path so equivalent URLs dedupe.
    cleaned_path = parsed.path.rstrip("/") if parsed.path != "/" else ""
    canonical = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=cleaned_path,
        fragment="",
    ).geturl()

    return UpstreamRef(
        channel=UpstreamChannel.HTTP,
        identifier=canonical,
        version="",
        pinned_hash="",
        source_url="",
        metadata={"host": host, "scheme": parsed.scheme},
    )


def _slugify(raw: str) -> str:
    """Slug-safe version of ``raw``: keep alnum, collapse separators."""
    chars: list[str] = []
    prev_dash = False
    for ch in raw.lower():
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif ch in {"-", "_", ".", "/"}:
            if not prev_dash:
                chars.append("-")
                prev_dash = True
    return "".join(chars).strip("-")


def _host_primary_label(host: str) -> str:
    """Return the most identifying label of a hostname for slug purposes.

    Strips common subdomain prefixes (``www``, ``mcp``, ``api``) and
    drops the TLD so ``mcp.context7.com`` → ``context7``.
    """
    parts = [p for p in host.lower().split(".") if p]
    if not parts:
        return ""
    # If only one label (e.g. localhost), use it.
    if len(parts) == 1:
        return parts[0]
    # Strip leading subdomain noise.
    while parts and parts[0] in {"www", "mcp", "api", "app"}:
        parts = parts[1:]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    # Drop TLD; the second-to-last label is usually the brand.
    return parts[-2]


def _suggested_tool_name(ref: UpstreamRef) -> str:
    """Derive a slug-safe tool name from an upstream URL host + path.

    Heuristic:
      1. If the last path segment is a real word (not a transport
         marker like ``sse`` / ``mcp`` / ``stream``), use it.
      2. Otherwise fall back to the host's primary label
         (``mcp.context7.com`` → ``context7``).
      3. Last resort: literal ``mcp-server``.
    """
    if ref.channel != UpstreamChannel.HTTP:
        return ""
    parsed = urlparse(ref.identifier)
    host = (parsed.hostname or "").lower()
    path = parsed.path.strip("/").split("/")
    last = path[-1] if path and path[-1] else ""

    # Try the last segment unless it's an obvious transport marker.
    if last and last.lower() not in _TRANSPORT_SUFFIXES:
        slug = _slugify(last)
        if slug:
            return slug

    # Fall back to the host's brand label.
    brand = _host_primary_label(host)
    if brand:
        slug = _slugify(brand)
        if slug:
            return slug

    return "mcp-server"


class HTTPUpstreamFetcher:
    """Resolves an HTTP-channel upstream reference into a curator preview.

    For the MVP this is intentionally lightweight — we only validate
    the URL and propose a tool-name slug. We do *not* probe the
    endpoint here because (a) the introspect step does that and (b) the
    resolve step needs to be cheap so the wizard's first screen feels
    instant.
    """

    def resolve(self, raw_upstream: str) -> UpstreamPreview:
        """Validate the URL and produce a wizard preview.

        Raises:
            UpstreamResolutionError: If the URL is malformed or uses an
                unsupported scheme. The wizard surfaces ``str(exc)``
                inline.
        """
        ref = parse_http_upstream(raw_upstream)
        slug = _suggested_tool_name(ref)
        display = slug.replace("-", " ").title() if slug else ""
        notes: list[str] = []
        host = (ref.metadata.get("host") or "").lower()
        if host in _LOOPBACK_HOSTS:
            notes.append(
                "This is a loopback URL. Listings backed by loopback "
                "endpoints are useful for testing but won't be reachable "
                "by other users."
            )
        return UpstreamPreview(
            upstream_ref=ref,
            suggested_tool_name=slug,
            suggested_display_name=display,
            notes=notes,
        )


# ── PyPI / npm fetchers ─────────────────────────────────────────


# Cap how long we'll wait on the package registry before reporting
# the package as unreachable. Real PyPI / npm latencies are <1s; we
# allow more headroom for slow networks but bail before the wizard's
# overall step timeout kicks in.
_PACKAGE_REGISTRY_TIMEOUT_S = 8.0


def _slugify_pkg(name: str) -> str:
    """Slug-safe version of a package name (drop scope, dashify)."""
    # npm scoped names like ``@scope/pkg`` → use the part after the slash.
    if "/" in name:
        name = name.split("/", 1)[1]
    return _slugify(name) or "mcp-server"


class PyPIUpstreamFetcher:
    """Resolves a PyPI package reference into a curator preview.

    Hits PyPI's JSON metadata endpoint
    (``https://pypi.org/pypi/{pkg}/json``) to confirm the package
    exists and to pick a default version + grab the description.

    Args:
        http_client_factory: Optional override for tests. Must return
            an object with a ``get(url, timeout=...)`` method whose
            response exposes ``.status_code``, ``.raise_for_status()``,
            and ``.json()``. Production uses ``httpx.Client``.
    """

    def __init__(self, *, http_client_factory: Any = None) -> None:
        self._client_factory = http_client_factory

    def _make_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        import httpx  # local import — keeps httpx optional for tests

        return httpx.Client(timeout=_PACKAGE_REGISTRY_TIMEOUT_S)

    def resolve(self, raw_upstream: str) -> UpstreamPreview:
        ref = parse_pypi_upstream(raw_upstream)
        url = f"https://pypi.org/pypi/{ref.identifier}/json"
        try:
            with self._make_client() as client:
                response = client.get(url)
                if response.status_code == 404:
                    raise UpstreamResolutionError(
                        f"PyPI couldn't find a package named "
                        f"{ref.identifier!r}."
                    )
                response.raise_for_status()
                data = response.json()
        except UpstreamResolutionError:
            raise
        except Exception as exc:
            logger.warning(
                "PyPI resolution failed for %s: %s",
                ref.identifier,
                exc,
                exc_info=True,
            )
            raise UpstreamResolutionError(
                f"Couldn't reach PyPI to resolve {ref.identifier!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        info = data.get("info") or {}
        latest_version = str(info.get("version") or "")
        version = ref.version or latest_version
        if not version:
            raise UpstreamResolutionError(
                f"PyPI returned no version for {ref.identifier!r}."
            )
        # Use the project_url or home_page if present.
        source_url = (
            info.get("project_url")
            or info.get("home_page")
            or info.get("package_url")
            or ""
        )
        # Pin the artifact hash if PyPI exposes a sha256 for this
        # version's first wheel/sdist.
        pinned_hash = ""
        releases = data.get("releases", {}) or {}
        artifacts = releases.get(version, []) or []
        for artifact in artifacts:
            digests = (artifact or {}).get("digests") or {}
            if digests.get("sha256"):
                pinned_hash = f"sha256:{digests['sha256']}"
                break

        slug = _slugify_pkg(ref.identifier)
        display = info.get("name") or slug.replace("-", " ").title()
        description_full = str(info.get("summary") or "")

        new_ref = UpstreamRef(
            channel=UpstreamChannel.PYPI,
            identifier=ref.identifier,
            version=version,
            pinned_hash=pinned_hash,
            source_url=str(source_url),
            metadata={
                "raw_spec": ref.metadata.get("raw_spec", ""),
                "summary": description_full,
                "license": str(info.get("license") or ""),
                "registry": "pypi",
            },
        )
        notes: list[str] = []
        if not ref.version:
            notes.append(
                f"Pinned to latest version {version}. Pass an explicit "
                f"version (pypi:{ref.identifier}@X.Y.Z) to lock differently."
            )
        if not pinned_hash:
            notes.append(
                "PyPI did not publish a sha256 for this version's "
                "artifacts; integrity hash is empty."
            )
        return UpstreamPreview(
            upstream_ref=new_ref,
            suggested_tool_name=slug,
            suggested_display_name=str(display),
            notes=notes,
        )


class NpmUpstreamFetcher:
    """Resolves an npm package reference into a curator preview.

    Hits npm's registry metadata endpoint
    (``https://registry.npmjs.org/{pkg}``).
    """

    def __init__(self, *, http_client_factory: Any = None) -> None:
        self._client_factory = http_client_factory

    def _make_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        import httpx

        return httpx.Client(timeout=_PACKAGE_REGISTRY_TIMEOUT_S)

    def resolve(self, raw_upstream: str) -> UpstreamPreview:
        ref = parse_npm_upstream(raw_upstream)
        # Scoped names need URL encoding of the slash.
        encoded = ref.identifier.replace("/", "%2F")
        url = f"https://registry.npmjs.org/{encoded}"
        try:
            with self._make_client() as client:
                response = client.get(url)
                if response.status_code == 404:
                    raise UpstreamResolutionError(
                        f"npm couldn't find a package named "
                        f"{ref.identifier!r}."
                    )
                response.raise_for_status()
                data = response.json()
        except UpstreamResolutionError:
            raise
        except Exception as exc:
            logger.warning(
                "npm resolution failed for %s: %s",
                ref.identifier,
                exc,
                exc_info=True,
            )
            raise UpstreamResolutionError(
                f"Couldn't reach npm to resolve {ref.identifier!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        dist_tags = data.get("dist-tags") or {}
        latest_version = str(dist_tags.get("latest") or "")
        version = ref.version or latest_version
        if not version:
            raise UpstreamResolutionError(
                f"npm returned no version for {ref.identifier!r}."
            )
        versions = data.get("versions") or {}
        version_data = versions.get(version) or {}
        # The integrity field uses subresource integrity format
        # (``sha512-...``). We surface as-is.
        dist = version_data.get("dist") or {}
        pinned_hash = str(dist.get("integrity") or dist.get("shasum") or "")
        repository = (
            (version_data.get("repository") or {}).get("url")
            or (data.get("repository") or {}).get("url")
            or ""
        )
        slug = _slugify_pkg(ref.identifier)
        display = version_data.get("name") or data.get("name") or slug
        description_full = str(version_data.get("description") or data.get("description") or "")

        new_ref = UpstreamRef(
            channel=UpstreamChannel.NPM,
            identifier=ref.identifier,
            version=version,
            pinned_hash=pinned_hash,
            source_url=_strip_git_prefix(str(repository)),
            metadata={
                "raw_spec": ref.metadata.get("raw_spec", ""),
                "summary": description_full,
                "license": str(version_data.get("license") or data.get("license") or ""),
                "registry": "npm",
            },
        )
        notes: list[str] = []
        if not ref.version:
            notes.append(
                f"Pinned to latest version {version}. Pass an explicit "
                f"version (npm:{ref.identifier}@X.Y.Z) to lock differently."
            )
        return UpstreamPreview(
            upstream_ref=new_ref,
            suggested_tool_name=slug,
            suggested_display_name=str(display),
            notes=notes,
        )


class DockerUpstreamFetcher:
    """Resolves a Docker / OCI image reference into a curator preview.

    The MVP is intentionally pure-parsing: we do *not* hit Docker Hub
    / GHCR / etc. to resolve a tag to a digest or pull image labels.
    Each upstream registry has its own auth and rate-limit story, and
    the curator workflow already requires the curator to vouch for an
    introspected tool surface — so the high-value step is the
    introspection itself (which spawns the image to observe its MCP
    capabilities), not metadata enrichment.

    What this fetcher does provide:

    - Validates the reference shape via :func:`parse_docker_upstream`.
    - Surfaces a tool-name slug derived from the image's leaf path
      component (``ghcr.io/x/y`` → ``y``).
    - Generates curator-facing notes when the reference isn't pinned
      to a digest, when the tag is ``latest`` (notoriously unstable),
      or when the registry isn't Docker Hub (so the curator confirms
      the registry is intentional).
    """

    def resolve(self, raw_upstream: str) -> UpstreamPreview:
        ref = parse_docker_upstream(raw_upstream)
        # Slug from the image's leaf path component. ``ghcr.io/x/y``
        # → ``y``; ``library/nginx`` → ``nginx``; bare ``nginx`` →
        # ``nginx``.
        leaf = ref.identifier.rsplit("/", 1)[-1]
        slug = _slugify_pkg(leaf)
        display = slug.replace("-", " ").title() if slug else ""

        notes: list[str] = []
        if not ref.pinned_hash:
            notes.append(
                "No digest was supplied. Tag-only references are "
                "mutable — the image at this tag may change without "
                "the listing's attestation reflecting the new "
                "content. Pin a digest "
                f"(docker:{ref.identifier}@sha256:...) for "
                "reproducible curation."
            )
        if ref.version == "latest":
            notes.append(
                "The tag 'latest' floats — different curators may "
                "observe different surfaces over time. Prefer a "
                "specific tag or digest."
            )
        registry = ref.metadata.get("registry") or "docker.io"
        if registry != "docker.io":
            notes.append(
                f"Image is hosted on {registry!r} (not Docker Hub). "
                "Make sure the registry is intentional and that the "
                "registry server hosting the proxy can reach it."
            )

        return UpstreamPreview(
            upstream_ref=ref,
            suggested_tool_name=slug,
            suggested_display_name=str(display),
            notes=notes,
        )


def _strip_git_prefix(repo_url: str) -> str:
    """``git+https://github.com/x/y.git`` → ``https://github.com/x/y``."""
    if not repo_url:
        return ""
    if repo_url.startswith("git+"):
        repo_url = repo_url[len("git+") :]
    if repo_url.endswith(".git"):
        repo_url = repo_url[: -len(".git")]
    return repo_url


# ── Top-level dispatcher ────────────────────────────────────────


class UpstreamFetcher:
    """Channel-agnostic resolver. Dispatches to the right per-channel
    fetcher based on the parsed channel.

    This is the entry point the registry routes call so the wizard's
    single ``upstream`` field works for any channel.
    """

    def __init__(
        self,
        *,
        http_fetcher: HTTPUpstreamFetcher | None = None,
        pypi_fetcher: PyPIUpstreamFetcher | None = None,
        npm_fetcher: NpmUpstreamFetcher | None = None,
        docker_fetcher: DockerUpstreamFetcher | None = None,
    ) -> None:
        self._http = http_fetcher or HTTPUpstreamFetcher()
        self._pypi = pypi_fetcher or PyPIUpstreamFetcher()
        self._npm = npm_fetcher or NpmUpstreamFetcher()
        self._docker = docker_fetcher or DockerUpstreamFetcher()

    def resolve(self, raw_upstream: str) -> UpstreamPreview:
        ref = parse_upstream(raw_upstream)
        if ref.channel == UpstreamChannel.HTTP:
            return self._http.resolve(raw_upstream)
        if ref.channel == UpstreamChannel.PYPI:
            return self._pypi.resolve(raw_upstream)
        if ref.channel == UpstreamChannel.NPM:
            return self._npm.resolve(raw_upstream)
        if ref.channel == UpstreamChannel.DOCKER:
            return self._docker.resolve(raw_upstream)
        raise UpstreamResolutionError(
            f"Channel {ref.channel.value} is not supported in this iteration."
        )
