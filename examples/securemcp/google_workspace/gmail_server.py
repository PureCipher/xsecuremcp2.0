"""PureCipher Gmail: OAuth + SecureMCP policy, consent, provenance and gating."""

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

TOOLS = frozenset({"gmail_profile", "gmail_list_messages", "gmail_get_message"})
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailReadPolicy:
    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        allowed = context.action == "list_tools" or (
            context.action == "call_tool" and context.resource_id in TOOLS
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            reason="Only the declared Gmail read tools are permitted.",
            policy_id="purecipher-gmail-readonly-v1",
        )

    async def get_policy_id(self) -> str:
        return "purecipher-gmail-readonly-v1"

    async def get_policy_version(self) -> str:
        return "1.0.0"


async def gmail_get(path: str, params: dict | None = None) -> dict:
    token = get_access_token()
    if token is None or GMAIL_SCOPE not in token.scopes:
        raise ValueError("Google authorization with gmail.readonly is required.")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/" + path,
            params=params,
            headers={"Authorization": f"Bearer {token.token}"},
        )
    if response.status_code >= 300:
        # Do not expose OAuth tokens, provider response bodies, or message contents in errors.
        raise ValueError(f"Gmail request failed ({response.status_code}).")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Gmail response.")
    return payload


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
            GMAIL_SCOPE,
        ],
    )
    server = SecureMCP(
        "PureCipher Gmail",
        auth=auth,
        security=SecurityConfig(
            policy=PolicyConfig(providers=[GmailReadPolicy()], fail_closed=True),
            consent=ConsentConfig(
                graph_id="purecipher-gmail", resource_owner="purecipher"
            ),
            provenance=ProvenanceConfig(ledger_id="purecipher-gmail"),
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
    async def gmail_profile() -> dict:
        """Get the authenticated user's Gmail profile."""
        return await gmail_get("profile")

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    async def gmail_list_messages(
        query: str = "", page_token: str = "", max_results: int = 20
    ) -> dict:
        """List message IDs for the authenticated user, with optional Gmail search."""
        if not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100.")
        params = {"maxResults": max_results}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token
        return await gmail_get("messages", params)

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    async def gmail_get_message(message_id: str) -> dict:
        """Read one Gmail message belonging to the authenticated user."""
        if not message_id or not message_id.isalnum():
            raise ValueError("A Gmail message ID is required.")
        return await gmail_get(
            "messages/" + quote(message_id, safe=""), {"format": "full"}
        )

    return server


if __name__ == "__main__":
    create_server(
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_ID", ""),
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_SECRET", ""),
        os.environ.get("PURECIPHER_GMAIL_BASE_URL", "http://127.0.0.1:9101"),
    ).run(transport="http", host="127.0.0.1", port=9101)
