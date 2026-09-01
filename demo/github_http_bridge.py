"""Expose the GitHub MCP server as a local HTTP endpoint for the registry.

Why this exists
---------------
The registry can host Docker upstreams, but (1) its introspector runs the
image with no command — GitHub's image needs the ``stdio`` subcommand, so the
container exits and you get "McpError: Connection closed" — and (2) proxy
hosting never injects credentials at call time. So registering
``docker:ghcr.io/github/github-mcp-server`` directly does not work.

This bridge sidesteps both: it runs the GitHub stdio server itself (with the
``stdio`` arg and your token in the container's env) and re-exposes it as a
plain HTTP MCP server on localhost. You then register that loopback URL as an
*HTTP* proxy listing — the registry just forwards to it, governance (allowlist
+ provenance) still applies, and your token stays in this process.

Usage
-----
    export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx          # a fresh, scoped PAT
    uv run python demo/github_http_bridge.py             # serves http://localhost:9100/mcp

Then register it (auth-disabled registry on :8001 shown):
    curl -s -X POST http://localhost:8001/registry/curate/submit \
      -H 'Content-Type: application/json' \
      -d '{"upstream":"http://localhost:9100/mcp","hosting_mode":"proxy",
           "attestation_kind":"curator","tool_name":"github-local",
           "display_name":"GitHub (local HTTP)","version":"1.0.0"}'
    # approve if needed, then it appears in the agent client app.

Env:
    GITHUB_PERSONAL_ACCESS_TOKEN   required — forwarded into the container
    GITHUB_TOOLSETS                optional — e.g. "repos,issues,pull_requests"
    GITHUB_BRIDGE_PORT             optional — default 9100
    GITHUB_MCP_IMAGE               optional — default ghcr.io/github/github-mcp-server
"""

from __future__ import annotations

import os
import shutil
import sys

PORT = int(os.getenv("GITHUB_BRIDGE_PORT", "9100"))
IMAGE = os.getenv("GITHUB_MCP_IMAGE", "ghcr.io/github/github-mcp-server")
TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
TOOLSETS = os.getenv("GITHUB_TOOLSETS", "")


def main() -> int:
    if shutil.which("docker") is None:
        sys.exit("docker not found on PATH. Install Docker Desktop (or set "
                 "GITHUB_MCP_IMAGE to a locally available image).")
    if not TOKEN:
        sys.exit("GITHUB_PERSONAL_ACCESS_TOKEN is not set. Export a fresh, "
                 "scoped GitHub PAT and re-run.")

    from fastmcp import FastMCP
    from fastmcp.client.transports.stdio import StdioTransport

    # docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN [-e GITHUB_TOOLSETS] <image> stdio
    #   -e KEY (no value) forwards the value from this process's env, so the
    #   token never appears in the container's argv / `ps` listing.
    docker_args = ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN"]
    passthrough_env = {"GITHUB_PERSONAL_ACCESS_TOKEN": TOKEN}
    if TOOLSETS:
        docker_args += ["-e", "GITHUB_TOOLSETS"]
        passthrough_env["GITHUB_TOOLSETS"] = TOOLSETS
    docker_args += [IMAGE, "stdio"]   # <-- the subcommand the registry omits

    transport = StdioTransport(command="docker", args=docker_args, env=passthrough_env)
    bridge = FastMCP.as_proxy(transport, name="GitHub MCP Bridge")

    print(f"GitHub MCP bridge → http://localhost:{PORT}/mcp")
    print(f"  image: {IMAGE} stdio   toolsets: {TOOLSETS or '(default)'}")
    print("  register this URL as an HTTP proxy listing in the registry.")
    # streamable-http is the transport the registry's proxy/introspector speaks.
    bridge.run(transport="streamable-http", host="127.0.0.1", port=PORT, path="/mcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
