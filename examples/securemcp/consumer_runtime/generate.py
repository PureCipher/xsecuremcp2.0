import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from purecipher.consumer_bridge import PRODUCTS as BRIDGES
from purecipher.consumer_runtime import register_consumer_tools
from purecipher.product_schemas import PRODUCT_SCHEMAS

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
        manifest["version"] = "0.3.0"
        write_tools = product in BRIDGES or product in {"memory", "sequential-thinking"}
        manifest["permissions"] = [
            p
            for p in manifest["permissions"]
            if p != "environment_read" and (write_tools or p != "write_resource")
        ]
        manifest["resource_access"] = [
            r
            for r in manifest.get("resource_access", [])
            if write_tools or r.get("access_type") == "read"
        ]
        if product in BRIDGES:
            description = f"SecureMCP connector for your own {old['display_name']} MCP service. Requires a running authenticated HTTPS upstream and an explicit approved tool list. Upstream tools may write or execute; no upstream service is installed by this listing."
        elif product in {"memory", "sequential-thinking"}:
            description = f"Registry-hosted {old['display_name']} with encrypted state scoped to your connection. Use an assigned active profile; state persists until the connection is removed."
        else:
            description = f"Registry-hosted read-only {old['display_name']} tools using your selected connection. Provider credentials, permissions or account authorization may be required."
        if product.startswith("google-"):
            description += " Google OAuth app configuration is pending."
        manifest["description"] = description
        names = sorted(
            name for name, p in server._consumer_tool_products.items() if p == product
        )
        metadata = {
            "publisher_profile": old["metadata"].get("publisher_profile", {}),
            "security_framework": "SecureMCP 2.0",
            "icon_key": old["metadata"].get("icon_key", product),
            "configuration": ["oauth"]
            if PRODUCT_SCHEMAS[product]["kind"] == "oauth"
            else ["secrets"]
            if any(f["type"] == "secret" for f in PRODUCT_SCHEMAS[product]["fields"])
            else [],
            "transport": "streamable-http",
            "server_type": "remote",
            "endpoint": "https://registry.purecipher.com/mcp",
            "connection_instructions": "Create your own connection and select it in an active profile. Use that profile endpoint with an assigned client token.",
            "deployment_ready": True,
            "live_tested": False,
            "readiness": "authorization_pending",
            "runtime": "consumer-profile-v2",
            "runtime_kind": "upstream-connector" if product in BRIDGES else "native",
            "upstream_required": product in BRIDGES,
            "bundle_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((root / "src/purecipher").glob("consumer_*.py"))
            },
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
