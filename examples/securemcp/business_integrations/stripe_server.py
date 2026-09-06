"""Stripe Apps OAuth preparation: balances, invoice and payment summaries only."""

import base64
import os
from urllib.parse import urlsplit

import httpx

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.auth.oauth_proxy.upstream import AsyncOAuth2Client

from .common import ANNOTATIONS, page_size, read_json, resource_id, secured

BASE = "https://api.stripe.com/v1/"
TOOLS = {"stripe_get_balance", "stripe_list_payment_intents", "stripe_list_invoices"}
PERMISSIONS = [
    "connected_account_read",
    "balance_read",
    "payment_intent_read",
    "invoice_read",
]


class StripeVerifier(TokenVerifier):
    """Validate identity; OAuthProxy obtains scopes from its stored token response."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(
                    BASE + "account", headers={"Authorization": f"Bearer {token}"}
                )
            if response.status_code != 200:
                return None
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("object") != "account"
                or not isinstance(data.get("id"), str)
                or not data["id"].startswith("acct_")
            ):
                return None
            return AccessToken(
                token=token, client_id=data["id"], subject=data["id"], scopes=[]
            )
        except (httpx.HTTPError, ValueError):
            return None


class StripeOAuthClient(AsyncOAuth2Client):
    def _apply_client_auth(self, data, headers):
        # Stripe Apps uses the developer API key as the Basic username.
        headers["Authorization"] = (
            "Basic " + base64.b64encode(f"{self.client_secret}:".encode()).decode()
        )


class StripeOAuthProxy(OAuthProxy):
    def _create_upstream_oauth_client(self):
        if self._upstream_client_secret is None:
            raise ValueError("Stripe app developer credential is required")
        return StripeOAuthClient(
            client_id=self._upstream_client_id,
            client_secret=self._upstream_client_secret.get_secret_value(),
            timeout=20,
        )

    def _uses_alternate_verification(self):
        return True


def create_oauth(client_id: str, developer_key: str, base_url: str):
    url = urlsplit(base_url)
    if not client_id or not developer_key:
        raise ValueError("Stripe Apps OAuth client ID and developer key are required")
    if (
        url.scheme != "https"
        or not url.netloc
        or url.username
        or url.query
        or url.fragment
    ):
        raise ValueError("An HTTPS callback base URL is required")
    auth = StripeOAuthProxy(
        upstream_authorization_endpoint="https://marketplace.stripe.com/oauth/v2/authorize",
        upstream_token_endpoint=BASE + "oauth/token",
        upstream_client_id=client_id,
        upstream_client_secret=developer_key,
        token_verifier=StripeVerifier(),
        base_url=base_url,
        valid_scopes=["stripe_apps"],
        forward_pkce=False,
        forward_resource=False,
        fallback_access_token_expiry_seconds=3600,
        fallback_refresh_token_expiry_seconds=31536000,
    )
    auth.required_scopes = ["stripe_apps"]
    auth.update_default_scopes(["stripe_apps"])
    return auth


def list_params(limit: int, starting_after: str, prefix: str) -> dict:
    params = {"limit": page_size(limit)}
    if starting_after:
        if not starting_after.startswith(prefix):
            raise ValueError("Invalid pagination cursor")
        params["starting_after"] = resource_id(starting_after)
    return params


def summaries(data: dict, fields: set[str]) -> dict:
    rows = data.get("data")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid Stripe list response")
    return {
        "data": [{key: row[key] for key in fields if key in row} for row in rows],
        "has_more": bool(data.get("has_more", False)),
    }


def create_server(auth):
    server = secured("stripe", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def stripe_get_balance() -> dict:
        """Read available and pending Stripe balances; no transfers or payouts."""
        data = await read_json(BASE, "balance")
        return {
            "livemode": data.get("livemode"),
            **{
                key: [
                    {"amount": row["amount"], "currency": row["currency"]}
                    for row in data.get(key, [])
                ]
                for key in ("available", "pending")
            },
        }

    @server.tool(annotations=ANNOTATIONS)
    async def stripe_list_payment_intents(
        limit: int = 20, starting_after: str = ""
    ) -> dict:
        """Read payment summaries. Client secrets and payment method details are excluded."""
        return summaries(
            await read_json(
                BASE, "payment_intents", list_params(limit, starting_after, "pi_")
            ),
            {"id", "amount", "currency", "status", "created", "livemode"},
        )

    @server.tool(annotations=ANNOTATIONS)
    async def stripe_list_invoices(limit: int = 20, starting_after: str = "") -> dict:
        """Read invoice summaries without customer contacts or hosted invoice links."""
        return summaries(
            await read_json(
                BASE, "invoices", list_params(limit, starting_after, "in_")
            ),
            {
                "id",
                "number",
                "amount_due",
                "amount_paid",
                "currency",
                "status",
                "created",
                "livemode",
            },
        )

    return server


if __name__ == "__main__":
    create_server(
        create_oauth(
            os.environ.get("PURECIPHER_STRIPE_CLIENT_ID", ""),
            os.environ.get("PURECIPHER_STRIPE_DEVELOPER_KEY", ""),
            os.environ.get("PURECIPHER_STRIPE_BASE_URL", ""),
        )
    ).run(transport="http", host="127.0.0.1", port=9117)
