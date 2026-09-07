"""Check installed wheels without importing packages from the source tree."""

from __future__ import annotations

import asyncio
import tempfile
from importlib.metadata import version
from pathlib import Path

import fastmcp
import fastmcp_remote
import fastmcp_tasks
import purecipher
import securemcp
from fastmcp import Client
from purecipher.db_migrations import migrate_registry_database
from securemcp import SecureMCP


async def main() -> None:
    versions = {
        version(name)
        for name in ("fastmcp", "fastmcp-slim", "fastmcp-remote", "fastmcp-tasks")
    }
    assert len(versions) == 1, versions
    for module in (fastmcp, fastmcp_remote, fastmcp_tasks, purecipher, securemcp):
        assert module.__file__ and "site-packages" in Path(module.__file__).parts, (
            module
        )

    server = SecureMCP("wheel-smoke")

    @server.tool
    def add(a: int, b: int) -> int:
        return a + b

    async with Client(server) as client:
        assert (await client.call_tool("add", {"a": 2, "b": 3})).data == 5

    # Ensure wheel packaging includes the Alembic migrations needed on deployment.
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "registry.sqlite"
        migrate_registry_database(str(database))
        assert database.is_file()
    print("Installed wheels: imports, versions, MCP tool call, and migrations passed.")


if __name__ == "__main__":
    asyncio.run(main())
