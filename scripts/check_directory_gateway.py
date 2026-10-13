"""Explicit, read-only live smoke checks through the SecureMCP proxy implementation.

Runs a public docs request and starts the imported, pinned Context7 npm package.
It never publishes listings or treats discovery as certification.
"""

import asyncio
import json

from fastmcp import Client
from fastmcp.server.security.certification.manifest import (
    PermissionScope,
    SecurityManifest,
)
from fastmcp.server.security.gateway.tool_marketplace import (
    HostingMode,
    ToolListing,
    UpstreamChannel,
    UpstreamRef,
)
from purecipher.curation import build_curator_proxy_server
from purecipher.mcp_directory import now, read_snapshot, save_snapshot


async def check(name, upstream, tool, arguments):
    listing = ToolListing(
        tool_name="directory-smoke",
        version="1",
        hosting_mode=HostingMode.PROXY,
        upstream_ref=upstream,
        manifest=SecurityManifest(
            tool_name="directory-smoke",
            version="1",
            author="local-runtime-check",
            description="Temporary read-only runtime smoke check",
            permissions={PermissionScope.NETWORK_ACCESS, PermissionScope.CALL_TOOL},
            tags={tool},
        ),
        metadata={"introspection": {"tool_names": [tool]}},
    )
    proxy = build_curator_proxy_server(listing)
    async with Client(proxy) as client:
        tools = await client.list_tools()
        assert tool in {t.name for t in tools}, "Expected tool not exposed"
        result = await client.call_tool(tool, arguments)
        if result.is_error:
            raise ValueError("Upstream tool returned an error")
        text = "\n".join(getattr(c, "text", "") for c in result.content)
        if tool == "get_start_path":
            payload = json.loads(text)
            assert payload.get("role") == "developer" and payload.get("steps"), (
                "Expected documentation paths"
            )
        if tool == "resolve-library-id":
            assert "/vercel/next.js" in text, "Expected a usable library identifier"

        return {
            "server": name,
            "tool": tool,
            "status": "tool_execution_passed",
            "checked_at": now(),
            "scope": "temporary_in_process_securemcp_proxy",
            "tools_discovered": len(tools),
            "content_blocks": len(result.content),
            "result_excerpt": "\n".join(getattr(c, "text", "") for c in result.content)[
                :1500
            ],
        }


async def main():
    servers = {s["name"]: s for s in read_snapshot()["servers"]}
    docs = servers["ac.tandem/docs-mcp"]
    context = servers["io.github.upstash/context7"]
    package = next(
        p for p in context["raw"]["server"]["packages"] if p["registryType"] == "npm"
    )
    cases = [
        (
            docs["name"],
            UpstreamRef(
                channel=UpstreamChannel.HTTP, identifier=docs["options"][0]["reference"]
            ),
            "get_start_path",
            {"role": "developer"},
        ),
        (
            context["name"],
            UpstreamRef(
                channel=UpstreamChannel.NPM,
                identifier=package["identifier"],
                version=package["version"],
            ),
            "resolve-library-id",
            {"libraryName": "next.js", "query": "Find Next.js routing documentation"},
        ),
    ]
    results = []
    for name, ref, tool, arguments in cases:
        try:
            result = await asyncio.wait_for(
                check(name, ref, tool, arguments), timeout=120
            )
        except Exception as exc:
            result = {
                "server": name,
                "tool": tool,
                "status": "execution_failed",
                "error_type": type(exc).__name__,
                "checked_at": now(),
            }
        results.append(result)
        print(json.dumps(result), flush=True)
        save_snapshot({"checks": results}, ".data/mcp-gateway-smoke.json")


if __name__ == "__main__":
    asyncio.run(main())
