"""Run the PureCipher registry and host OpenAPI toolsets as MCP endpoints."""

from __future__ import annotations

import os

import uvicorn

from purecipher import PureCipherRegistry
from purecipher.hosted_runtime import build_hosted_registry_app


def _persistence_path() -> str:
    return os.getenv("PURECIPHER_PERSISTENCE_PATH", "purecipher-registry.db")


def build_app():
    persistence = _persistence_path()
    registry = PureCipherRegistry(
        signing_secret=os.getenv("PURECIPHER_SIGNING_SECRET", "dev-secret"),
        persistence_path=persistence,
    )
    return build_hosted_registry_app(registry=registry, persistence_path=persistence)


if __name__ == "__main__":
    uvicorn.run(
        build_app(),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
