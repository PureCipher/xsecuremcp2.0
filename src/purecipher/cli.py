"""CLI launcher for PureCipher registry."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import uvicorn

from fastmcp.server.security.certification.attestation import CertificationLevel
from purecipher.auth import RegistryAuthSettings
from purecipher.hosted_runtime import build_hosted_registry_app
from purecipher.registry import PureCipherRegistry


def _env_flag(name: str) -> bool:
    value = _env_or_file(name) or ""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_or_file(name: str) -> str | None:
    """Read a config value from ``$NAME`` or, failing that, ``$NAME_FILE``.

    The ``*_FILE`` convention lets container secrets (Docker/Kubernetes) be
    mounted as files and read without ever placing the value in an environment
    variable or an env file. ``$NAME`` takes precedence when both are set.
    """

    value = os.getenv(name)
    if value not in (None, ""):
        return value
    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        try:
            with open(file_path, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return None
    return value


def _resolve_persistence_target(
    database_url: str | None,
    database_path: str | None,
) -> str | None:
    """Resolve the registry's effective persistence target.

    PostgreSQL is the production engine. Resolution order:

    1. ``--database-url`` / ``DATABASE_URL`` (a PostgreSQL DSN) — used as-is.
    2. ``--database-path`` / ``PURECIPHER_REGISTRY_DB`` — a legacy single-file
       SQLite path, kept for local development. ``:memory:`` stays ephemeral.
    3. Nothing configured → ``None`` (ephemeral, in-memory registry).

    Returns the target string (a Postgres DSN or a SQLite path) or ``None``.
    """

    url = (database_url or "").strip()
    if url:
        return url

    path = (database_path or "").strip()
    if not path:
        return None
    if path != ":memory:":
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    return path


def build_parser() -> argparse.ArgumentParser:
    """Create the PureCipher registry CLI parser."""

    parser = argparse.ArgumentParser(
        prog="purecipher-registry",
        description="Launch the PureCipher Secured MCP Registry.",
    )
    parser.add_argument("--name", default="purecipher-registry")
    parser.add_argument(
        "--signing-secret",
        default=_env_or_file("PURECIPHER_SIGNING_SECRET"),
        help=(
            "Registry signing secret. Defaults to PURECIPHER_SIGNING_SECRET "
            "(or PURECIPHER_SIGNING_SECRET_FILE for a mounted secret)."
        ),
    )
    parser.add_argument("--issuer-id", default="purecipher-registry")
    parser.add_argument(
        "--minimum-certification",
        default=CertificationLevel.BASIC.value,
        choices=[level.value for level in CertificationLevel],
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--registry-prefix", default="/registry")
    parser.add_argument(
        "--enable-legacy-ui",
        action="store_true",
        default=_env_flag("PURECIPHER_ENABLE_LEGACY_UI"),
        help=(
            "Serve the legacy server-rendered registry UI on the backend. "
            "Disabled by default; use the separate Next.js registry console instead."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=_env_or_file("DATABASE_URL"),
        help=(
            "PostgreSQL DSN for persistence (postgresql://user:pass@host:port/db). "
            "This is the production engine. Defaults to DATABASE_URL (or "
            "DATABASE_URL_FILE for a mounted secret). When set, published "
            "listings persist until withdrawn/unregistered."
        ),
    )
    parser.add_argument(
        "--database-path",
        default=os.getenv("PURECIPHER_REGISTRY_DB"),
        help=(
            "Legacy single-file SQLite path for local development, used only when "
            "--database-url/DATABASE_URL is not set. Defaults to "
            "PURECIPHER_REGISTRY_DB. Use ':memory:' for ephemeral storage. "
            "Omit both to run an ephemeral in-memory registry."
        ),
    )
    parser.add_argument(
        "--disable-security-api",
        action="store_true",
        help="Disable the broader /security API surface.",
    )
    parser.add_argument(
        "--require-moderation",
        action="store_true",
        default=_env_flag("PURECIPHER_REQUIRE_MODERATION"),
        help="Place accepted submissions into pending review instead of immediate publication.",
    )
    parser.add_argument(
        "--enable-auth",
        action="store_true",
        default=_env_flag("PURECIPHER_ENABLE_AUTH"),
        help="Enable JWT login and role-based access for registry routes.",
    )
    parser.add_argument(
        "--jwt-secret",
        default=_env_or_file("PURECIPHER_JWT_SECRET") or "",
        help=(
            "JWT secret for registry auth. Defaults to PURECIPHER_JWT_SECRET "
            "(or PURECIPHER_JWT_SECRET_FILE for a mounted secret)."
        ),
    )
    parser.add_argument(
        "--jwt-audience",
        default=os.getenv("PURECIPHER_JWT_AUDIENCE", "purecipher-registry"),
        help="JWT audience used for issued registry tokens.",
    )
    parser.add_argument(
        "--auth-cookie-name",
        default=os.getenv("PURECIPHER_AUTH_COOKIE_NAME", "purecipher_registry_token"),
        help="Cookie name used for browser registry sessions.",
    )
    parser.add_argument(
        "--jwt-ttl-seconds",
        type=int,
        default=int(os.getenv("PURECIPHER_JWT_TTL_SECONDS", "43200")),
        help="JWT lifetime in seconds.",
    )
    parser.add_argument(
        "--users-json",
        default=os.getenv("PURECIPHER_USERS_JSON", ""),
        help="JSON array of static auth users. Defaults to PURECIPHER_USERS_JSON.",
    )
    parser.add_argument(
        "--host-toolsets",
        action="store_true",
        default=_env_flag("PURECIPHER_HOST_TOOLSETS"),
        help="Host OpenAPI toolsets as MCP endpoints under /mcp/toolsets/<toolset_id>.",
    )
    return parser


def build_registry_from_args(args: argparse.Namespace) -> PureCipherRegistry:
    """Instantiate a registry from parsed CLI arguments."""

    if not args.signing_secret:
        raise ValueError(
            "A signing secret is required. Pass --signing-secret or set PURECIPHER_SIGNING_SECRET."
        )

    auth_settings = RegistryAuthSettings.from_values(
        enabled=args.enable_auth,
        issuer=args.issuer_id,
        signing_secret=args.signing_secret,
        jwt_secret=args.jwt_secret,
        audience=args.jwt_audience,
        cookie_name=args.auth_cookie_name,
        token_ttl_seconds=args.jwt_ttl_seconds,
        users_json=args.users_json,
    )

    return PureCipherRegistry(
        args.name,
        signing_secret=args.signing_secret,
        issuer_id=args.issuer_id,
        minimum_certification=CertificationLevel(args.minimum_certification),
        registry_prefix=args.registry_prefix,
        enable_legacy_registry_ui=args.enable_legacy_ui,
        persistence_path=args.database_path,
        mount_security_api=not args.disable_security_api,
        require_moderation=args.require_moderation,
        auth_settings=auth_settings,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PureCipher registry server."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Resolve the effective persistence target. PostgreSQL is the only durable
    # engine; anything else makes the registry run ephemeral (in-memory).
    from fastmcp.server.security.storage.pg_pool import is_postgres_dsn

    target = _resolve_persistence_target(
        getattr(args, "database_url", None), args.database_path
    )
    if target and not is_postgres_dsn(target):
        print(
            f"warning: '{target}' is not a PostgreSQL DSN; the registry persists "
            "only to PostgreSQL. Running ephemeral (in-memory) — set "
            "--database-url/DATABASE_URL to a postgresql:// DSN for durable state.",
            file=sys.stderr,
        )
    args.database_path = target

    registry = build_registry_from_args(args)
    if not args.host_toolsets:
        registry.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )
        return 0

    # Hosted mode: serve registry + toolset gateways in one ASGI app.
    app = build_hosted_registry_app(
        registry=registry,
        persistence_path=args.database_path,
    )
    uvicorn.run(
        app,
        host=args.host,
        port=int(args.port),
        log_level=os.getenv("LOG_LEVEL", "info"),
        lifespan="on",
    )
    return 0


__all__ = [
    "build_parser",
    "build_registry_from_args",
    "main",
]
