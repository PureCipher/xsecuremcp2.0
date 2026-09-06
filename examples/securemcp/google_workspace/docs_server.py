"""PureCipher Docs: OAuth + SecureMCP policy, consent, provenance and gating."""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)
from securemcp import SecureMCP
from securemcp.config import (
    ConsentConfig,
    IntrospectionConfig,
    PolicyConfig,
    ProvenanceConfig,
    ReflexiveConfig,
    SecurityConfig,
)

TOOLS = frozenset({"docs_get_document"})
DOCS_SCOPE = "https://www.googleapis.com/auth/documents.readonly"


class DocsReadPolicy:
    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        allowed = context.action == "list_tools" or (
            context.action == "call_tool" and context.resource_id in TOOLS
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            reason="Only the declared Docs read tools are permitted.",
            policy_id="purecipher-docs-readonly-v1",
        )

    async def get_policy_id(self) -> str:
        return "purecipher-docs-readonly-v1"

    async def get_policy_version(self) -> str:
        return "1.0.0"


async def docs_get(path: str, params: dict | None = None) -> dict:
    token = get_access_token()
    if token is None or DOCS_SCOPE not in token.scopes:
        raise ValueError("Google authorization with docs.readonly is required.")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(
            "https://docs.googleapis.com/v1/" + path,
            params=params,
            headers={"Authorization": f"Bearer {token.token}"},
        )
    if response.status_code >= 300:
        # Do not expose OAuth tokens, provider response bodies, or message contents in errors.
        raise ValueError(f"Docs request failed ({response.status_code}).")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Docs response.")
    return payload


def safe_id(value: str) -> str:
    if not value or value in {".", ".."} or any(c in value for c in "/\\?#"):
        raise ValueError("A valid resource ID is required.")
    return quote(value, safe="")


def page_params(page_token: str, max_results: int) -> dict:
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")
    params = {"maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    return params


def create_server(client_id: str, client_secret: str, base_url: str) -> SecureMCP:
    if not client_id or not client_secret:
        raise ValueError("Google OAuth client ID and client secret must be configured.")
    auth = GoogleProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            DOCS_SCOPE,
        ],
    )
    server = SecureMCP(
        "PureCipher Docs",
        auth=auth,
        security=SecurityConfig(
            policy=PolicyConfig(providers=[DocsReadPolicy()], fail_closed=True),
            consent=ConsentConfig(
                graph_id="purecipher-docs", resource_owner="purecipher"
            ),
            provenance=ProvenanceConfig(ledger_id="purecipher-docs"),
            reflexive=ReflexiveConfig(),
            introspection=IntrospectionConfig(enable_pre_execution_gating=True),
        ),
        # Security administration is not exposed to Google-authenticated end users.
        mount_security_api=False,
    )

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    async def docs_get_document(document_id: str) -> dict:
        """Read a Google document, including all tabs, by document ID."""
        return await docs_get(
            "documents/" + safe_id(document_id), {"includeTabsContent": "true"}
        )

    return server


if __name__ == "__main__":
    create_server(
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_ID", ""),
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_SECRET", ""),
        os.environ.get("PURECIPHER_DOCS_BASE_URL", "http://127.0.0.1:9102"),
    ).run(transport="http", host="127.0.0.1", port=9102)
