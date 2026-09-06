"""PureCipher Apollo.io: OAuth-backed prospect/company search preparation."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.dependencies import get_access_token

from .common import ANNOTATIONS, page_size, secured

BASE = "https://api.apollo.io/api/v1/"
TOOLS = {"apollo_search_people", "apollo_search_companies", "apollo_profile"}
PEOPLE_SCOPE = "mixed_people_api_search"
COMPANY_SCOPE = "mixed_companies_search"
PROFILE_SCOPE = "read_user_profile"


class ApolloIdentityVerifier(TokenVerifier):
    """Only for tokens obtained by this app's OAuth proxy, not direct API keys."""

    def __init__(self):
        super().__init__(required_scopes=[PROFILE_SCOPE])

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(
                    BASE + "users/api_profile",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code != 200:
                return None
            payload = response.json()
            if not isinstance(payload, dict):
                return None
            user = payload.get("user", payload)
            if (
                not isinstance(user, dict)
                or not isinstance(user.get("id"), str)
                or not user["id"]
            ):
                return None
            return AccessToken(
                token=token,
                client_id=user["id"],
                subject=user["id"],
                scopes=[PROFILE_SCOPE],
            )
        except (httpx.HTTPError, ValueError):
            return None


class ApolloOAuthProxy(OAuthProxy):
    def _prepare_scopes_for_token_exchange(self, scopes):
        return self._extra_authorize_params["scope"].split()

    def _prepare_scopes_for_upstream_refresh(self, scopes):
        return self._extra_authorize_params["scope"].split()


def create_oauth(
    client_id: str,
    client_secret: str,
    base_url: str,
    *,
    enable_company_search: bool = False,
):
    if not client_id or not client_secret:
        raise ValueError("Apollo partner OAuth client ID and secret must be configured")
    url = urlsplit(base_url)
    if (
        url.scheme != "https"
        or not url.netloc
        or url.query
        or url.fragment
        or url.username
    ):
        raise ValueError("Apollo requires an HTTPS callback base URL")
    scopes = [PROFILE_SCOPE, PEOPLE_SCOPE]
    if enable_company_search:
        scopes.append(COMPANY_SCOPE)
    return ApolloOAuthProxy(
        upstream_authorization_endpoint="https://app.apollo.io/#/oauth/authorize",
        upstream_token_endpoint="https://app.apollo.io/api/v1/oauth/token",
        upstream_client_id=client_id,
        upstream_client_secret=client_secret,
        base_url=base_url,
        token_verifier=ApolloIdentityVerifier(),
        valid_scopes=scopes,
        extra_authorize_params={"scope": " ".join(scopes)},
        token_endpoint_auth_method="client_secret_post",
        forward_pkce=False,
        forward_resource=False,
    )


async def apollo_request(path: str, scope: str, params: dict | None = None) -> dict:
    methods = {
        "users/api_profile": "GET",
        "mixed_people/api_search": "POST",
        "mixed_companies/search": "POST",
    }
    if path not in methods:
        raise ValueError("Apollo endpoint is not allowed")
    token = get_access_token()
    if token is None or scope not in token.scopes:
        raise ValueError("Required Apollo authorization scope is missing")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.request(
                methods[path],
                BASE + path,
                params=params,
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError:
        raise ValueError("Apollo connection failed") from None
    if response.status_code != 200:
        raise ValueError(f"Apollo request failed ({response.status_code})")
    data = response.json()
    if not isinstance(data, dict) or data.get("error") or data.get("error_code"):
        raise ValueError("Apollo rejected the request")
    return data


def pagination(page: int, per_page: int) -> dict:
    if not 1 <= page <= 500:
        raise ValueError("Page must be between 1 and 500")
    return {"page": page, "per_page": page_size(per_page)}


def create_server(auth, *, enable_company_search: bool = False):
    server = secured("apollo", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def apollo_search_people(
        keywords: str,
        job_titles: list[str] | None = None,
        company_domains: list[str] | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Search professional prospect previews. No email/phone enrichment. Apollo currently lists zero credits for this endpoint."""
        if not keywords.strip() and not job_titles and not company_domains:
            raise ValueError("At least one search filter is required")
        if len(job_titles or []) > 20 or len(company_domains or []) > 20:
            raise ValueError("At most 20 titles or domains per search")
        params = {**pagination(page, per_page), "q_keywords": keywords}
        if job_titles:
            params["person_titles[]"] = job_titles
        if company_domains:
            params["q_organization_domains_list[]"] = company_domains
        return await apollo_request("mixed_people/api_search", PEOPLE_SCOPE, params)

    @server.tool(annotations=ANNOTATIONS)
    async def apollo_search_companies(
        company_name: str, page: int = 1, per_page: int = 20
    ) -> dict:
        """Search companies. Costs one Apollo credit per page per current documentation; disabled unless explicitly enabled by the operator."""
        if not enable_company_search:
            raise ValueError(
                "Company search is disabled because it consumes Apollo credits"
            )
        if not company_name.strip():
            raise ValueError("A company name is required")
        return await apollo_request(
            "mixed_companies/search",
            COMPANY_SCOPE,
            {**pagination(page, per_page), "q_organization_name": company_name},
        )

    @server.tool(annotations=ANNOTATIONS)
    async def apollo_profile() -> dict:
        """Read the authenticated Apollo profile, without requesting credit-usage details."""
        return await apollo_request("users/api_profile", PROFILE_SCOPE)

    return server


if __name__ == "__main__":
    enabled = (
        os.environ.get("PURECIPHER_APOLLO_ENABLE_COMPANY_SEARCH", "false").lower()
        == "true"
    )
    auth = create_oauth(
        os.environ.get("PURECIPHER_APOLLO_CLIENT_ID", ""),
        os.environ.get("PURECIPHER_APOLLO_CLIENT_SECRET", ""),
        os.environ.get("PURECIPHER_APOLLO_BASE_URL", ""),
        enable_company_search=enabled,
    )
    create_server(auth, enable_company_search=enabled).run(
        transport="http", host="127.0.0.1", port=9116
    )
