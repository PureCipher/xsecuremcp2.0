"""Serve the Space README alongside the installed registry backend."""

from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse

from fastmcp.server.security.storage.pg_pool import is_postgres_dsn
from purecipher.cli import build_parser, build_registry_from_args
from purecipher.registry import PureCipherRegistry


def create_registry(page: Path) -> PureCipherRegistry:
    if not page.is_file():
        raise FileNotFoundError(f"Missing Space README page: {page}")
    args = build_parser().parse_args(["--host", "0.0.0.0", "--port", "8000"])
    target = args.database_url or args.database_path
    # Match the registry CLI: PostgreSQL persists; other targets are ephemeral.
    args.database_path = target if target and is_postgres_dsn(target) else None
    registry = build_registry_from_args(args)

    @registry.custom_route("/", methods=["GET", "HEAD"])
    async def readme_page(request: Request) -> FileResponse:
        return FileResponse(
            page,
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; "
                    "base-uri 'none'; form-action 'none'"
                ),
            },
        )

    return registry


if __name__ == "__main__":
    create_registry(Path(__file__).with_name("index.html")).run(
        transport="streamable-http", host="0.0.0.0", port=8000
    )
