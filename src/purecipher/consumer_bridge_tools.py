"""Private, individually selectable tools from a verified upstream connection.

No descriptors are registered globally: every lookup resolves the current
authenticated profile, so one owner's catalog cannot leak into another's.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.providers import Provider
from fastmcp.server.transforms import Transform
from fastmcp.tools.base import Tool, ToolResult
from fastmcp.utilities.versions import VersionSpec


def tool_alias(product: str, name: str, descriptor: dict) -> str:
    # A new schema/description produces a new selectable capability. Re-verifying
    # a changed service must not silently broaden an already approved profile.
    identity = json.dumps(
        [product, name, descriptor], sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
    return f"up_{digest}_{readable}"


def connection_descriptors(registry: Any, item: dict) -> dict[str, dict]:
    from purecipher.consumer_bridge import PRODUCTS, approved_tools
    from purecipher.consumer_runtime import runtime_ready

    if item.get("product") not in PRODUCTS or not runtime_ready(registry, item):
        return {}
    return {
        tool_alias(item["product"], name, descriptor): {
            **descriptor,
            "profile_tool_name": tool_alias(item["product"], name, descriptor),
        }
        for name, descriptor in approved_tools(registry, item).items()
    }


def selected_descriptors(registry: Any, owner: str, selected: dict) -> dict[str, dict]:
    item = registry._workspace.get(selected.get("connection_id", ""))
    listing = registry._marketplace().get(selected["listing_id"])
    if (
        not item
        or item.get("kind") != "product_connection"
        or item["owner"] != owner
        or not listing
        or listing.author != "purecipher"
        or listing.tool_name != "purecipher-" + item["product"]
        or (listing.metadata or {}).get("runtime_kind")
        not in {None, "upstream-connector"}
    ):
        return {}
    # Publication of the connector is still required. Private tools extend only
    # a listing that exposes this connector's own checked invocation route.
    from purecipher.workspace import inspected_tools

    helper = item["product"].replace("-", "_") + "_call_approved_tool"
    if helper not in inspected_tools(listing):
        return {}
    return connection_descriptors(registry, item)


def selected_product(registry: Any, profile: dict, name: str) -> str | None:
    if not name.startswith("up_"):
        return None
    matches = [
        registry._workspace.get(selected["connection_id"])["product"]
        for selected in profile["servers"]
        if name in selected.get("tools", [])
        and name in selected_descriptors(registry, profile["owner"], selected)
    ]
    return matches[0] if len(matches) == 1 else None


class ConnectedTool(Tool):
    _registry: Any = None
    _upstream_name: str = ""

    def __init__(self, registry: Any, descriptor: dict):
        super().__init__(
            name=descriptor["profile_tool_name"],
            title=descriptor["name"],
            description=descriptor["description"],
            parameters=descriptor["inputSchema"],
            # Upstream descriptions/hints are untrusted. Keep conservative
            # effects for registry enforcement; never import security tags.
            annotations={
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            },
            tags={"risk:high", "resource:upstream-mcp"},
            meta={
                "upstream_tool_name": descriptor["name"],
                "inventory_source": "owner-approved-connection",
            },
        )
        self._registry = registry
        self._upstream_name = descriptor["name"]

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        from purecipher.consumer_bridge import call_approved
        from purecipher.consumer_runtime import _ACCESS

        context = _ACCESS.get()
        if not context or context.get("tool_name") != self.name:
            raise ValueError("Use an assigned profile with this tool selected")
        result = await call_approved(
            self._registry, context, self._upstream_name, arguments
        )
        # Preserve typed MCP content, including images and structured results.
        from mcp_types import CallToolResult

        return ToolResult.from_mcp_result(CallToolResult.model_validate(result))


class ConnectedToolsProvider(Provider):
    def __init__(self, registry: Any):
        super().__init__()
        self.registry = registry

    def descriptors(self) -> dict[str, dict]:
        from purecipher.workspace import allowed_profile_tools

        headers = get_http_headers(include={"authorization"})
        profile_id = headers.get("x-purecipher-profile")
        if not profile_id:
            return {}
        token = headers.get("authorization", "")
        if not token.lower().startswith("bearer "):
            return {}
        resolved = self.registry.authenticate_client_token(token[7:].strip())
        if not resolved:
            return {}
        allowed = allowed_profile_tools(self.registry, profile_id, resolved[0])
        profile = self.registry._workspace.get(profile_id)
        result = {}
        for selected in profile["servers"]:
            for name, descriptor in selected_descriptors(
                self.registry, profile["owner"], selected
            ).items():
                if name in allowed:
                    result[name] = descriptor
        return result

    async def _list_tools(self) -> list[Tool]:
        return [ConnectedTool(self.registry, d) for d in self.descriptors().values()]

    async def _get_tool(
        self, name: str, version: VersionSpec | None = None
    ) -> Tool | None:
        if not name.startswith("up_") or version is not None:
            return None
        descriptor = self.descriptors().get(name)
        return ConnectedTool(self.registry, descriptor) if descriptor else None


class ConnectedToolIdentityTransform(Transform):
    """Reserve private aliases at every lookup, including final dispatch.

    A static published tool otherwise wins over a provider tool with the same
    name. Checking only before middleware leaves a publication race while other
    planes await. This transform also checks the final execution lookup.
    """

    def __init__(self, registry: Any):
        self.registry = registry

    def matches(self, component: Tool | None, name: str) -> bool:
        return (
            isinstance(component, ConnectedTool)
            and component._registry is self.registry
            and component.name == name
        )

    async def get_tool(self, name, call_next, *, version=None):
        component = await call_next(name, version=version)
        if name.startswith("up_") and not self.matches(component, name):
            return None
        return component

    async def list_tools(self, tools):
        conflicts = {
            component.name
            for component in tools
            if component.name.startswith("up_")
            and not self.matches(component, component.name)
        }
        return [component for component in tools if component.name not in conflicts]
