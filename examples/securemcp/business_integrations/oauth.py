"""Provider-specific OAuth preparation. No credentials or tokens are packaged."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.auth.oauth_proxy.upstream import AsyncOAuth2Client
from fastmcp.server.auth.providers.github import GitHubProvider


class IdentityVerifier(TokenVerifier):
    """Verify only tokens acquired by our OAuth proxy; not a standalone bearer API.

    Graph validates identity through /me; delegated data permissions are enforced
    by Graph on every tool request, not inferred from opaque token contents.
    Jira also verifies the configured site's granted scopes. Slack validates the
    user token and actual scope header. No token-verification caching is used.
    """

    def __init__(self, service: str, cloud_id: str = ""):
        self.service, self.cloud_id = service, cloud_id
        scopes = {
            "jira": ["read:me", "read:jira-work"],
            "slack": ["channels:read", "channels:history"],
        }.get(service, ["User.Read"])
        super().__init__(required_scopes=scopes)

    async def verify_token(self, token: str) -> AccessToken | None:
        url = {
            "slack": "https://slack.com/api/auth.test",
            "jira": "https://api.atlassian.com/me",
        }.get(self.service, "https://graph.microsoft.com/v1.0/me?$select=id")
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(
                    url, headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                if not isinstance(data, dict):
                    return None
                if self.service == "slack":
                    scopes = [
                        s.strip()
                        for s in response.headers.get("x-oauth-scopes", "").split(",")
                        if s.strip()
                    ]
                    if (
                        data.get("ok") is not True
                        or data.get("bot_id")
                        or not data.get("team_id")
                        or not data.get("user_id")
                    ):
                        return None
                    subject = f"{data['team_id']}:{data['user_id']}"
                elif self.service == "jira":
                    sites = await client.get(
                        "https://api.atlassian.com/oauth/token/accessible-resources",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if sites.status_code != 200:
                        return None
                    site = next(
                        (
                            s
                            for s in sites.json()
                            if isinstance(s, dict) and s.get("id") == self.cloud_id
                        ),
                        None,
                    )
                    if site is None or "read:jira-work" not in site.get("scopes", []):
                        return None
                    scopes = ["read:me", "read:jira-work"]
                    subject = data.get("account_id")
                else:
                    scopes = ["User.Read"]  # Only this permission was verified by /me.
                    subject = data.get("id")
                if not subject or not set(self.required_scopes).issubset(scopes):
                    return None
                return AccessToken(
                    token=token,
                    client_id=str(subject),
                    subject=str(subject),
                    scopes=scopes,
                )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None


def slack_token_response(data):
    """Normalize Slack's nested user token; never substitute the workspace bot token."""
    user = data.get("authed_user", {})
    if data.get("ok") is not True:
        raise ValueError("Slack OAuth failed")
    # Refresh responses for a user token can already be flat.
    if data.get("token_type") == "user" and data.get("access_token"):
        user = data
    if not user.get("access_token") or user.get("token_type") != "user":
        raise ValueError("Slack user authorization is required")
    return {
        "access_token": user["access_token"],
        "token_type": "Bearer",
        "scope": user.get("scope", "").replace(",", " "),
        **{k: user[k] for k in ("refresh_token", "expires_in") if k in user},
    }


class SlackOAuthClient(AsyncOAuth2Client):
    async def _request_token(self, url, data):
        return slack_token_response(await super()._request_token(url, data))


class SlackOAuthProxy(OAuthProxy):
    def _create_upstream_oauth_client(self):
        return SlackOAuthClient(
            client_id=self._upstream_client_id,
            client_secret=self._upstream_client_secret.get_secret_value()
            if self._upstream_client_secret
            else None,
            token_endpoint_auth_method="client_secret_post",
            timeout=20,
        )


class GraphOAuthProxy(OAuthProxy):
    def _prepare_scopes_for_token_exchange(self, scopes):
        return self._extra_authorize_params["scope"].split()

    def _prepare_scopes_for_upstream_refresh(self, scopes):
        return self._extra_authorize_params["scope"].split()


def create_oauth(
    service: str,
    base_url: str,
    client_id: str,
    client_secret: str,
    *,
    tenant_id: str = "",
    cloud_id: str = "",
):
    if not client_id or not client_secret:
        raise ValueError("OAuth client ID and secret must be configured")
    if service == "github":
        return GitHubProvider(
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
            required_scopes=["read:user"],
            forward_resource=False,
        )
    verifier = IdentityVerifier(service, cloud_id)
    options: dict[str, Any] = dict(
        upstream_client_id=client_id,
        upstream_client_secret=client_secret,
        base_url=base_url,
        token_verifier=verifier,
        forward_resource=False,
        token_endpoint_auth_method="client_secret_post",
    )
    if service == "slack":
        return SlackOAuthProxy(
            **options,
            upstream_authorization_endpoint="https://slack.com/oauth/v2/authorize",
            upstream_token_endpoint="https://slack.com/api/oauth.v2.access",
            forward_pkce=False,
            extra_authorize_params={
                "scope": "",
                "user_scope": "channels:read,channels:history",
            },
        )
    if service == "jira":
        if not re.fullmatch(r"[a-zA-Z0-9-]+", cloud_id):
            raise ValueError("A Jira cloud ID must be configured")
        return OAuthProxy(
            **options,
            upstream_authorization_endpoint="https://auth.atlassian.com/authorize",
            upstream_token_endpoint="https://auth.atlassian.com/oauth/token",
            forward_pkce=False,
            extra_authorize_params={
                "audience": "api.atlassian.com",
                "prompt": "consent",
                "scope": "read:me read:jira-work offline_access",
            },
        )
    if service not in {"outlook", "onedrive"} or not re.fullmatch(
        r"[a-zA-Z0-9-]+", tenant_id
    ):
        raise ValueError(
            "A supported service and Microsoft tenant ID must be configured"
        )
    scopes = "User.Read offline_access " + (
        "Mail.Read Calendars.Read" if service == "outlook" else "Files.Read"
    )
    return GraphOAuthProxy(
        **options,
        upstream_authorization_endpoint=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        upstream_token_endpoint=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        extra_authorize_params={"scope": scopes},
    )


def from_environment(service: str, port: int):
    prefix = "PURECIPHER_" + service.upper()
    return create_oauth(
        service,
        os.environ.get(prefix + "_BASE_URL", f"http://127.0.0.1:{port}"),
        os.environ.get(prefix + "_CLIENT_ID", ""),
        os.environ.get(prefix + "_CLIENT_SECRET", ""),
        tenant_id=os.environ.get(prefix + "_TENANT_ID", ""),
        cloud_id=os.environ.get("PURECIPHER_JIRA_CLOUD_ID", ""),
    )
