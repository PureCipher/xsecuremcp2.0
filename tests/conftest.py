import asyncio
import logging
import secrets
import socket
import sys
from collections.abc import Callable, Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fastmcp.utilities.tests import temporary_settings

# Use SelectorEventLoop on Windows to avoid ProactorEventLoop crashes
# See: https://github.com/python/cpython/issues/116773
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def pytest_collection_modifyitems(items):
    """Automatically mark tests in integration_tests folder with 'integration' marker."""
    for item in items:
        # Check if the test is in the integration_tests folder
        if "integration_tests" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def import_rich_rule():
    # What a hack
    import rich.rule  # noqa: F401

    yield


@pytest.fixture(autouse=True)
def enable_fastmcp_logger_propagation(caplog):
    """Enable propagation on FastMCP root logger so caplog captures FastMCP log messages.

    FastMCP loggers have propagate=False by default, which prevents messages from
    reaching pytest's caplog handler (attached to root logger). This fixture
    temporarily enables propagation on the FastMCP root logger so FastMCP logs
    are captured in tests.
    """
    root_logger = logging.getLogger("fastmcp")
    original_propagate = root_logger.propagate
    root_logger.propagate = True

    yield

    root_logger.propagate = original_propagate


@pytest.fixture(autouse=True)
def isolate_settings_home(tmp_path: Path):
    """Ensure each test uses an isolated settings.home directory.

    This prevents file locking issues when multiple tests share the same
    storage directory in settings.home / "oauth-proxy".

    Also sets a fast Docket polling interval for tests — the default 50ms
    is fine for production but still adds ~25ms average pickup latency per
    task. 10ms makes task tests near-instant.
    """
    test_home = tmp_path / "fastmcp-test-home"
    test_home.mkdir(exist_ok=True)

    with temporary_settings(
        home=test_home,
        docket__minimum_check_interval=timedelta(milliseconds=10),
        docket__url=f"memory://{secrets.token_hex(4)}",
        client_disconnect_timeout=1,
    ):
        yield


def get_fn_name(fn: Callable[..., Any]) -> str:
    return fn.__name__  # ty: ignore[unresolved-attribute]


@pytest.fixture
def worker_id(request):
    """Get the xdist worker ID, or 'master' if not using xdist."""
    return getattr(request.config, "workerinput", {}).get("workerid", "master")


# ── PostgreSQL persistence fixtures ───────────────────────────────
#
# The PureCipher registry persists to PostgreSQL. Persistence tests run
# against a real database: each test gets its own freshly-created, migrated
# database so xdist workers never collide and state never leaks between tests.
#
# Point the suite at a server with PURECIPHER_TEST_DATABASE_URL (a maintenance
# DSN, e.g. the compose Postgres:
#   postgresql://purecipher:purecipher@localhost:5432/purecipher
# ). When no server is reachable the persistence tests are skipped rather than
# failed, so contributors without Postgres aren't blocked; CI runs them with a
# postgres service.

_DEFAULT_TEST_DSN = "postgresql://purecipher:purecipher@localhost:5432/purecipher"


def _maintenance_dsn() -> str:
    import os

    return (
        os.getenv("PURECIPHER_TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or _DEFAULT_TEST_DSN
    )


def _dsn_with_dbname(dsn: str, dbname: str) -> str:
    """Return ``dsn`` with its database (path) replaced by ``dbname``."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(dsn)
    return urlunsplit(parts._replace(path=f"/{dbname}"))


@pytest.fixture(scope="session")
def _postgres_available() -> bool:
    """Session probe: is the configured PostgreSQL server reachable?"""
    try:
        import psycopg
    except ImportError:  # pragma: no cover - psycopg is a hard dependency
        return False
    try:
        with psycopg.connect(_maintenance_dsn(), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False


@pytest.fixture
def registry_dsn(_postgres_available: bool, worker_id: str):
    """A fresh, migrated PostgreSQL database dedicated to a single test.

    Yields a DSN string suitable for any registry store, the SecureMCP
    ``PostgresBackend``, or ``PureCipherRegistry(persistence_path=...)``. The
    database is created on entry, migrated to head, and dropped on exit.
    Skips the test when no PostgreSQL server is reachable.
    """
    import secrets
    import time

    import psycopg

    if not _postgres_available:
        pytest.skip(
            "PostgreSQL not reachable. Start one (e.g. "
            "`docker compose -f docker-compose.purecipher-registry.yml up -d postgres`) "
            "and set PURECIPHER_TEST_DATABASE_URL."
        )

    from fastmcp.server.security.storage.pg_pool import close_all_pools
    from purecipher.db_migrations import migrate_registry_database

    admin = _maintenance_dsn()
    dbname = (
        f"pctest_{worker_id}_{int(time.time() * 1000) % 100000}_{secrets.token_hex(4)}"
    )
    dbname = dbname.replace("-", "_").lower()

    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{dbname}"')

    dsn = _dsn_with_dbname(admin, dbname)
    try:
        migrate_registry_database(dsn)
        yield dsn
    finally:
        # Drop the per-test database. Close pools first so no live connection
        # blocks the DROP, then terminate any stragglers.
        close_all_pools()
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture
def free_port():
    """Get a free port for the test to use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def free_port_factory(worker_id):
    """Factory to get free ports that tracks used ports per test session."""
    used_ports = set()

    def get_port():
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                s.listen(1)
                port = s.getsockname()[1]
                if port not in used_ports:
                    used_ports.add(port)
                    return port

    return get_port


@pytest.fixture(scope="session")
def otel_trace_provider() -> Generator[
    tuple[TracerProvider, InMemorySpanExporter], None, None
]:
    """Configure OTEL SDK with in-memory span exporter for testing.

    Session-scoped because TracerProvider can only be set once per process.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield provider, exporter


@pytest.fixture
def trace_exporter(
    otel_trace_provider: tuple[TracerProvider, InMemorySpanExporter],
) -> Generator[InMemorySpanExporter, None, None]:
    """Get the span exporter and clear it between tests."""
    _, exporter = otel_trace_provider
    exporter.clear()
    yield exporter
    exporter.clear()


@pytest.fixture
def fastmcp_server():
    """Fixture that creates a FastMCP server with tools, resources, and prompts."""
    import asyncio
    import json

    from fastmcp import FastMCP

    server = FastMCP("TestServer")

    # Add a tool
    @server.tool
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    # Add a second tool
    @server.tool
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @server.tool
    async def sleep(seconds: float) -> str:
        """Sleep for a given number of seconds."""
        await asyncio.sleep(seconds)
        return f"Slept for {seconds} seconds"

    # Add a resource (return JSON string for proper typing)
    @server.resource(uri="data://users")
    async def get_users() -> str:
        return json.dumps(["Alice", "Bob", "Charlie"], separators=(",", ":"))

    # Add a resource template (return JSON string for proper typing)
    @server.resource(uri="data://user/{user_id}")
    async def get_user(user_id: str) -> str:
        return json.dumps(
            {"id": user_id, "name": f"User {user_id}", "active": True},
            separators=(",", ":"),
        )

    # Add a prompt
    @server.prompt
    def welcome(name: str) -> str:
        """Example greeting prompt."""
        return f"Welcome to FastMCP, {name}!"

    return server


@pytest.fixture
def tool_server():
    """Fixture that creates a FastMCP server with comprehensive tool set for provider tests."""
    import base64

    from mcp.types import (
        BlobResourceContents,
        EmbeddedResource,
        ImageContent,
        TextContent,
    )
    from pydantic import AnyUrl

    from fastmcp import FastMCP
    from fastmcp.utilities.types import Audio, File, Image

    mcp = FastMCP()

    @mcp.tool
    def add(x: int, y: int) -> int:
        return x + y

    @mcp.tool
    def list_tool() -> list[str | int]:
        return ["x", 2]

    @mcp.tool
    def error_tool() -> None:
        raise ValueError("Test error")

    @mcp.tool
    def image_tool(path: str) -> Image:
        return Image(path)

    @mcp.tool
    def audio_tool(path: str) -> Audio:
        return Audio(path)

    @mcp.tool
    def file_tool(path: str) -> File:
        return File(path)

    @mcp.tool
    def mixed_content_tool() -> list[TextContent | ImageContent | EmbeddedResource]:
        return [
            TextContent(type="text", text="Hello"),
            ImageContent(type="image", data="abc", mimeType="application/octet-stream"),
            EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    blob=base64.b64encode(b"abc").decode(),
                    mimeType="application/octet-stream",
                    uri=AnyUrl("file:///test.bin"),
                ),
            ),
        ]

    @mcp.tool(output_schema=None)
    def mixed_list_fn(image_path: str) -> list:
        return [
            "text message",
            Image(image_path),
            {"key": "value"},
            TextContent(type="text", text="direct content"),
        ]

    @mcp.tool(output_schema=None)
    def mixed_audio_list_fn(audio_path: str) -> list:
        return [
            "text message",
            Audio(audio_path),
            {"key": "value"},
            TextContent(type="text", text="direct content"),
        ]

    @mcp.tool(output_schema=None)
    def mixed_file_list_fn(file_path: str) -> list:
        return [
            "text message",
            File(file_path),
            {"key": "value"},
            TextContent(type="text", text="direct content"),
        ]

    @mcp.tool
    def file_text_tool() -> File:
        return File(data=b"hello world", format="plain")

    return mcp


@pytest.fixture
def tagged_resources_server():
    """Fixture that creates a FastMCP server with tagged resources and templates."""
    import json

    from fastmcp import FastMCP

    server = FastMCP("TaggedResourcesServer")

    # Add a resource with tags
    @server.resource(
        uri="data://tagged", tags={"test", "metadata"}, description="A tagged resource"
    )
    async def get_tagged_data() -> str:
        return json.dumps({"type": "tagged_data"}, separators=(",", ":"))

    # Add a resource template with tags
    @server.resource(
        uri="template://{id}",
        tags={"template", "parameterized"},
        description="A tagged template",
    )
    async def get_template_data(id: str) -> str:
        return json.dumps({"id": id, "type": "template_data"}, separators=(",", ":"))

    return server
