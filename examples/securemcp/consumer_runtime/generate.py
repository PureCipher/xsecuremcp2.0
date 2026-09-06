import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from purecipher.consumer_runtime import register_consumer_tools

root = Path(__file__).resolve().parents[3]
server: Any = FastMCP("Descriptor inspection")
register_consumer_tools(server)


async def main():
    tools = await server.list_tools()
    payloads: list[dict[str, Any]] = []
    sha = hashlib.sha256(
        (root / "src/purecipher/consumer_runtime.py").read_bytes()
    ).hexdigest()
    for product in sorted(server._consumer_products):
        folder = (
            "google_workspace"
            if product.startswith("google-")
            else "business_integrations"
        )
        stem = product.removeprefix("google-")
        old = json.loads(
            (root / f"examples/securemcp/{folder}/{stem}-submission.json").read_text()
        )
        manifest = old["manifest"]
        manifest["version"] = "0.2.0"
        manifest["permissions"] = [
            p
            for p in manifest["permissions"]
            if p not in {"write_resource", "environment_read"}
        ]
        manifest["resource_access"] = [
            r
            for r in manifest.get("resource_access", [])
            if r.get("access_type") == "read"
        ]
        description = (
            "Registry-hosted read-only "
            + old["display_name"]
            + " tools. Each user must authorize or verify their own connection before an assigned profile can call these tools. Google OAuth app configuration is pending."
            if product.startswith("google-")
            else "Registry-hosted Brave web search using the end user’s own verified API key. Each call requires an active profile and remains subject to SecureMCP controls."
        )
        manifest["description"] = description
        names = sorted(
            name for name, p in server._consumer_tool_products.items() if p == product
        )
        metadata = {
            "publisher_profile": old["metadata"].get("publisher_profile", {}),
            "security_framework": "SecureMCP 2.0",
            "icon_key": old["metadata"].get("icon_key", product),
            "configuration": ["oauth"]
            if product.startswith("google-")
            else ["secrets"],
            "transport": "streamable-http",
            "server_type": "remote",
            "endpoint": "https://registry.purecipher.com/mcp",
            "connection_instructions": "Create your own connection and select it in an active profile. Use that profile endpoint with an assigned client token.",
            "deployment_ready": True,
            "live_tested": False,
            "readiness": "authorization_pending",
            "runtime": "consumer-profile-v1",
            "source_file": "src/purecipher/consumer_runtime.py",
            "source_sha256": sha,
            "tools": names,
            "introspection": {
                "source": "registered-runtime-descriptors",
                "tool_names": names,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.parameters,
                    }
                    for t in tools
                    if t.name in names
                ],
            },
        }
        payloads.append(
            {
                "display_name": old["display_name"],
                "categories": old.get("categories", ["utility"]),
                "manifest": manifest,
                "metadata": metadata,
                "requested_level": "basic",
            }
        )
    Path(__file__).with_name("submissions.json").write_text(
        json.dumps(payloads, indent=2)
    )
    print([(p["manifest"]["tool_name"], p["metadata"]["tools"]) for p in payloads])


asyncio.run(main())
