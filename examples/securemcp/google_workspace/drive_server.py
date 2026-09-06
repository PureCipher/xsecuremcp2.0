"""PureCipher Drive: OAuth + SecureMCP policy, consent, provenance and gating."""

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

TOOLS = frozenset({"drive_search_files", "drive_get_file"})
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"


class DriveReadPolicy:
    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        allowed = context.action == "list_tools" or (
            context.action == "call_tool" and context.resource_id in TOOLS
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            reason="Only the declared Drive read tools are permitted.",
            policy_id="purecipher-drive-readonly-v1",
        )

    async def get_policy_id(self) -> str:
        return "purecipher-drive-readonly-v1"

    async def get_policy_version(self) -> str:
        return "1.0.0"


async def drive_get(path: str, params: dict | None = None) -> dict:
    token = get_access_token()
    if token is None or DRIVE_SCOPE not in token.scopes:
        raise ValueError(
            "Google authorization with drive.metadata.readonly is required."
        )
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(
            "https://www.googleapis.com/drive/v3/" + path,
            params=params,
            headers={"Authorization": f"Bearer {token.token}"},
        )
    if response.status_code >= 300:
        # Do not expose OAuth tokens, provider response bodies, or message contents in errors.
        raise ValueError(f"Drive request failed ({response.status_code}).")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Drive response.")
    return payload


def safe_id(value: str) -> str:
    if not value or value in {".", ".."} or any(c in value for c in "/\\?#"):
        raise ValueError("A valid resource ID is required.")
    return quote(value, safe="")


def page_params(page_token: str, max_results: int) -> dict:
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")
    params = {"pageSize": max_results}
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
            DRIVE_SCOPE,
        ],
    )
    server = SecureMCP(
        "PureCipher Drive",
        auth=auth,
        security=SecurityConfig(
            policy=PolicyConfig(providers=[DriveReadPolicy()], fail_closed=True),
            consent=ConsentConfig(
                graph_id="purecipher-drive", resource_owner="purecipher"
            ),
            provenance=ProvenanceConfig(ledger_id="purecipher-drive"),
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
    async def drive_search_files(
        query: str = "", page_token: str = "", max_results: int = 20
    ) -> dict:
        """Search file and folder metadata using Drive query syntax. Does not download content."""
        params = page_params(page_token, max_results)
        params.update(
            {
                "q": "trashed = false" + (" and (" + query + ")" if query else ""),
                "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,webViewLink,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
        )
        return await drive_get("files", params)

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    async def drive_get_file(file_id: str) -> dict:
        """Get one file's metadata and browser link. Does not read file content."""
        return await drive_get(
            "files/" + safe_id(file_id),
            {
                "fields": "id,name,mimeType,modifiedTime,webViewLink,parents,size,description",
                "supportsAllDrives": "true",
            },
        )

    return server


if __name__ == "__main__":
    create_server(
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_ID", ""),
        os.environ.get("PURECIPHER_GOOGLE_CLIENT_SECRET", ""),
        os.environ.get("PURECIPHER_DRIVE_BASE_URL", "http://127.0.0.1:9105"),
    ).run(transport="http", host="127.0.0.1", port=9105)
