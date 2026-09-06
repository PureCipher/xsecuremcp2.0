"""SecureMCP boundary for individually reviewed, isolated upstream MCP servers.

Preparation factory only. It does not install or launch upstream programs and
does not infer that a Docker catalog entry is a certified SecureMCP server.
"""

import json
from pathlib import Path

from fastmcp import Client

from .common import secured

CATALOG = json.loads(Path(__file__).with_name("catalog-sources.json").read_text())
TOOLS = {"catalog_list_tools", "catalog_call"}


def create_server(
    service: str,
    auth,
    upstream: Client,
    allowed_tools: set[str],
    *,
    allow_archived: bool = False,
):
    if service not in CATALOG:
        raise ValueError("Unknown catalog integration")
    if CATALOG[service]["archived"] and not allow_archived:
        raise ValueError("Archived upstream requires explicit operator review")
    if not allowed_tools or any(not name.strip() for name in allowed_tools):
        raise ValueError("An explicit reviewed upstream tool allowlist is required")
    allowed = frozenset(allowed_tools)
    server = secured(service, auth, TOOLS)

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    async def catalog_list_tools() -> dict:
        """Read schemas for the operator-approved upstream tools only."""
        async with upstream:
            tools = await upstream.list_tools()
        return {
            "tools": [
                tool.model_dump(mode="json", by_alias=True)
                for tool in tools
                if tool.name in allowed
            ]
        }

    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "openWorldHint": True,
        }
    )
    async def catalog_call(tool_name: str, arguments: dict) -> list[dict]:
        """Call one explicitly approved tool. Effects depend on that tool; SecureMCP consent is required."""
        if tool_name not in allowed:
            raise ValueError("Upstream tool is not allowed")
        async with upstream:
            result = await upstream.call_tool(tool_name, arguments)
        return [
            content.model_dump(mode="json", by_alias=True) for content in result.content
        ]

    return server
