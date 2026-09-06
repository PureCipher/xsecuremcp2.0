"""Shared read-only SecureMCP controls for PureCipher preparation packages."""

from __future__ import annotations

from urllib.parse import quote, urlsplit

import httpx

from fastmcp.server.auth import AuthProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.security.policy.provider import PolicyDecision, PolicyResult
from securemcp import SecureMCP
from securemcp.config import (
    ConsentConfig,
    IntrospectionConfig,
    PolicyConfig,
    ProvenanceConfig,
    ReflexiveConfig,
    SecurityConfig,
)

ANNOTATIONS = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}


class ReadPolicy:
    def __init__(self, service: str, tools: set[str]):
        self.service, self.tools = service, frozenset(tools)

    async def evaluate(self, context):
        allow = context.action == "list_tools" or (
            context.action == "call_tool" and context.resource_id in self.tools
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW if allow else PolicyDecision.DENY,
            reason="Only declared read tools are permitted.",
            policy_id=await self.get_policy_id(),
        )

    async def get_policy_id(self):
        return f"purecipher-{self.service}-readonly-v1"

    async def get_policy_version(self):
        return "1.0.0"


def secured(service: str, auth: AuthProvider, tools: set[str]) -> SecureMCP:
    if auth is None:
        raise ValueError("Authentication must be configured")
    return SecureMCP(
        f"PureCipher {service.title()}",
        auth=auth,
        security=SecurityConfig(
            policy=PolicyConfig(
                providers=[ReadPolicy(service, tools)], fail_closed=True
            ),
            consent=ConsentConfig(
                graph_id=f"purecipher-{service}", resource_owner="purecipher"
            ),
            provenance=ProvenanceConfig(ledger_id=f"purecipher-{service}"),
            reflexive=ReflexiveConfig(),
            introspection=IntrospectionConfig(enable_pre_execution_gating=True),
        ),
        mount_security_api=False,
    )


def resource_id(value: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or any(c in value for c in "/\\?#%")
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("A valid resource ID is required")
    return quote(value, safe="")


def page_size(value: int) -> int:
    if not 1 <= value <= 100:
        raise ValueError("Page size must be between 1 and 100")
    return value


async def read_json(base: str, path: str, params: dict | None = None) -> dict:
    """Only internally constructed paths; never follow redirects with credentials."""
    token = get_access_token()
    if token is None:
        raise ValueError("Authorization is required")
    if path.startswith(("/", "http:", "https:")) or ".." in path.split("/"):
        raise ValueError("Invalid API path")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(
            base + path,
            params=params,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Accept": "application/json",
            },
        )
    if response.status_code != 200:
        raise ValueError(f"Provider request failed ({response.status_code})")
    data = response.json()
    if isinstance(data, list):
        return {"items": data}
    if not isinstance(data, dict) or data.get("ok") is False:
        raise ValueError("Provider rejected the request")
    return data


def graph_page(next_link: str, expected_path: str) -> tuple[str, dict | None]:
    """Accept Graph pagination only for the exact resource being listed."""
    if not next_link:
        return expected_path, None
    parsed = urlsplit(next_link)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "graph.microsoft.com"
        or parsed.path != "/v1.0/" + expected_path
        or parsed.fragment
    ):
        raise ValueError("Invalid pagination link")
    return expected_path + ("?" + parsed.query if parsed.query else ""), None
