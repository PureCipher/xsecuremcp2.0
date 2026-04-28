"""Third-party MCP server curation for the PureCipher registry.

This module powers the curator workflow — onboarding existing public
MCP servers (HTTP, PyPI, npm, Docker / OCI images) into the registry
without the original author's involvement. The curator vouches for the
server's observed behavior; the registry attests to the manifest the
curator confirmed; users see a third-party trust signal distinct from
an author-attested listing.

Hosting modes: catalog-only (publish the attestation, point install
recipes at the upstream) or proxy (mount a SecureMCP gateway in front
of the upstream and bind calls to the curator-vouched tool surface).
Proxy is supported on every channel: HTTP via direct ``Client(url)``,
PyPI/npm via per-session ``uvx``/``npx`` subprocesses, Docker via
per-session ``docker run --rm -i``.
"""

from purecipher.curation.introspector import (
    CredentialValidationError,
    HTTPIntrospector,
    IntrospectionError,
    IntrospectionResult,
    Introspector,
    StdioIntrospector,
    check_introspection_launchers,
    validate_introspect_env,
)
from purecipher.curation.manifest_generator import (
    ManifestDraft,
    PermissionSuggestion,
    derive_manifest_draft,
)
from purecipher.curation.proxy_runtime import (
    CuratorProxyRouter,
    ProxyHostingError,
    build_curator_proxy_server,
)
from purecipher.curation.upstream import (
    DockerUpstreamFetcher,
    HTTPUpstreamFetcher,
    NpmUpstreamFetcher,
    PyPIUpstreamFetcher,
    UpstreamFetcher,
    UpstreamPreview,
    UpstreamResolutionError,
    image_ref_for,
    parse_docker_upstream,
    parse_http_upstream,
    parse_npm_upstream,
    parse_pypi_upstream,
    parse_upstream,
)

__all__ = [
    "CredentialValidationError",
    "CuratorProxyRouter",
    "DockerUpstreamFetcher",
    "HTTPIntrospector",
    "HTTPUpstreamFetcher",
    "IntrospectionError",
    "IntrospectionResult",
    "Introspector",
    "ManifestDraft",
    "NpmUpstreamFetcher",
    "PermissionSuggestion",
    "ProxyHostingError",
    "PyPIUpstreamFetcher",
    "StdioIntrospector",
    "UpstreamFetcher",
    "UpstreamPreview",
    "UpstreamResolutionError",
    "build_curator_proxy_server",
    "check_introspection_launchers",
    "derive_manifest_draft",
    "image_ref_for",
    "parse_docker_upstream",
    "parse_http_upstream",
    "parse_npm_upstream",
    "parse_pypi_upstream",
    "parse_upstream",
    "validate_introspect_env",
]
