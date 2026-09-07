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

API_SOURCES = {
    "google-docs": "https://developers.google.com/workspace/docs/api/reference/rest",
    "google-tasks": "https://developers.google.com/workspace/tasks/reference/rest",
    "google-calendar": "https://developers.google.com/workspace/calendar/api/v3/reference",
    "google-drive": "https://developers.google.com/workspace/drive/api/reference/rest/v3",
    "github": "https://docs.github.com/en/rest?apiVersion=2022-11-28",
    "github-reference": "https://docs.github.com/en/rest?apiVersion=2022-11-28",
    "slack": "https://docs.slack.dev/reference/methods/",
    "slack-archived": "https://docs.slack.dev/reference/methods/",
    "notion": "https://developers.notion.com/reference/intro",
    "jira": "https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
    "atlassian": "https://developer.atlassian.com/cloud/confluence/rest/v2/intro/",
    "outlook": "https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview?view=graph-rest-1.0",
    "onedrive": "https://learn.microsoft.com/en-us/graph/api/resources/onedrive?view=graph-rest-1.0",
    "stripe": "https://docs.stripe.com/api",
    "huggingface": "https://huggingface.co/docs/hub/api",
    "apollo": "https://docs.apollo.io/reference/search-for-contacts",
    "n8n": "https://docs.n8n.io/api/api-reference/",
    "aws-core": "https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Welcome.html",
    "cloudwatch": "https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/Welcome.html",
    "grafana": "https://grafana.com/docs/grafana/latest/developers/http_api/",
    "dynatrace": "https://docs.dynatrace.com/docs/dynatrace-api/environment-api",
    "sonarqube": "https://next.sonarqube.com/sonarqube/web_api",
    "brave-search": "https://api-dashboard.search.brave.com/app/documentation",
    "firecrawl": "https://docs.firecrawl.dev/api-reference/introduction",
    "arxiv": "https://info.arxiv.org/help/api/user-manual.html",
    "wikipedia": "https://www.mediawiki.org/wiki/API:Main_page",
}


def tool_descriptor(tool: Any) -> dict[str, Any]:
    descriptor = {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }
    annotations = getattr(tool, "annotations", None)
    if annotations is not None:
        descriptor["annotations"] = (
            annotations.model_dump(mode="json", by_alias=True, exclude_none=True)
            if hasattr(annotations, "model_dump")
            else dict(annotations)
        )
    return descriptor


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
        names = sorted(
            name for name, p in server._consumer_tool_products.items() if p == product
        )
        manifest = old["manifest"]
        manifest["version"] = "0.4.0"
        product_tools = [tool for tool in tools if tool.name in names]
        write_tools = product in BRIDGES or any(
            not tool.annotations or tool.annotations.read_only_hint is not True
            for tool in product_tools
        )
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
        # Derive declared effects from actual registered tools. A broadened
        # implementation must not retain a read-only publication manifest.
        for permission in [
            "call_tool",
            "read_resource",
            *(["write_resource"] if write_tools else []),
        ]:
            if permission not in manifest["permissions"]:
                manifest["permissions"].append(permission)
        manifest["idempotent"] = not write_tools
        if write_tools and not any(
            resource.get("access_type") == "write"
            for resource in manifest["resource_access"]
        ):
            manifest["resource_access"].append(
                {
                    "resource_pattern": f"{product}:*",
                    "access_type": "write",
                    "classification": "restricted",
                }
            )
        if product != "google-gmail":
            manifest["data_flows"] = [
                {
                    "source": "authenticated MCP client",
                    "destination": old["display_name"],
                    "classification": "restricted",
                    "description": "Explicitly selected operations use the owner's connection and its granted provider permissions.",
                },
                {
                    "source": old["display_name"],
                    "destination": "authenticated MCP client",
                    "classification": "restricted",
                    "description": "Results are returned only through assigned active profiles and can contain private account data.",
                },
            ]
        if product == "google-gmail":
            for permission in ("read_resource", "write_resource", "call_tool"):
                if permission not in manifest["permissions"]:
                    manifest["permissions"].append(permission)
            manifest["idempotent"] = False
            manifest["resource_access"] = [
                {
                    "resource_pattern": "google:gmail:*",
                    "access_type": access,
                    "classification": "restricted",
                }
                for access in ("read", "write")
            ]
            manifest["data_flows"] = [
                {
                    "source": "Gmail",
                    "destination": "authenticated MCP client",
                    "classification": "restricted",
                    "description": "Account-authorized mailbox results may contain personal and sensitive information.",
                },
                {
                    "source": "authenticated MCP client",
                    "destination": "Gmail and explicitly addressed email recipients",
                    "classification": "restricted",
                    "description": "Explicitly selected and authorized write tools can change mailbox data, manage drafts, and send email to the supplied recipients.",
                },
            ]
            description = f"Registry-hosted Gmail with {len(names)} SecureMCP tools for reading, drafting, sending, and organizing mail. Choose Read only, Read, draft and send, or Manage mail for your own connection. Google OAuth app configuration and account authorization are required."
        elif product in BRIDGES:
            description = f"SecureMCP connector for your own {old['display_name']} MCP service. Verify your connection to discover actual tool schemas, then select individual tools in a profile. Upstream tools may write or execute. Requires a running authenticated HTTPS upstream."
        elif product in {"memory", "sequential-thinking"}:
            description = f"Registry-hosted {old['display_name']} with encrypted state scoped to your connection. Use an assigned active profile; state persists until the connection is removed."
        else:
            access = "read and change" if write_tools else "read"
            description = f"{len(names)} product-specific SecureMCP tools to {access} {old['display_name']} data using your own connection. Select only the tools you need; provider permissions and profile approval are required."
        if product.startswith("google-") and product != "google-gmail":
            description += " Google OAuth app configuration is pending."
        manifest["description"] = description
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
            "individual_upstream_tools": product in BRIDGES,
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
                "tools": [tool_descriptor(t) for t in tools if t.name in names],
            },
            "tool_coverage": {
                "version": "0.4.0",
                "reviewed_at": "2026-09-07",
                "source_url": API_SOURCES.get(
                    product, PRODUCT_SCHEMAS[product]["source"]
                ),
                "scope": "Owner-approved upstream tools are discovered per connection; public definitions count connector helpers only"
                if product in BRIDGES
                else "Implemented product operations; does not claim every vendor API endpoint",
                "tool_count": len(names),
                "live_tested": False,
            },
        }
        if PRODUCT_SCHEMAS[product].get("oauth_modes"):
            metadata["oauth_access_modes"] = PRODUCT_SCHEMAS[product]["oauth_modes"]
            metadata["default_access_mode"] = "read_only"
        if product == "google-gmail":
            source_file = "src/purecipher/consumer_gmail.py"
            metadata.update(
                {
                    "source_file": source_file,
                    "source_sha256": hashlib.sha256(
                        (root / source_file).read_bytes()
                    ).hexdigest(),
                    "oauth_access_modes": PRODUCT_SCHEMAS[product].get(
                        "oauth_modes", []
                    ),
                    "default_access_mode": "read_only",
                    "tool_coverage": {
                        "version": "0.4.0",
                        "api": "Gmail API",
                        "api_version": "v1",
                        "reviewed_at": "2026-09-07",
                        "source_url": "https://developers.google.com/workspace/gmail/api/reference/rest",
                        "scope_source_url": "https://developers.google.com/workspace/gmail/api/auth/scopes",
                        "scope": "Mailbox product operations; partial Gmail API coverage",
                        "tool_count": len(names),
                        "covered": [
                            "mailbox profile",
                            "message and thread search and retrieval",
                            "attachments",
                            "draft creation, replacement, deletion and sending",
                            "sending and replying",
                            "label definitions and message/thread labels",
                            "message/thread trash and restoration",
                            "mailbox history",
                        ],
                        "excluded": [
                            "account settings and administration",
                            "permanent message/thread deletion",
                            "bulk message mutation",
                            "push watches and background synchronization",
                            "message import and insertion",
                        ],
                    },
                }
            )
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
