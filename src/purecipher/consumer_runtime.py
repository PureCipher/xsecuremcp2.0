"""Consumer runtimes. Credentials and capabilities are scoped to one profile call."""

import contextvars
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import quote

import httpx

_ACCESS: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "purecipher_consumer_access", default=None
)
GOOGLE = {
    "google-gmail",
    "google-docs",
    "google-tasks",
    "google-calendar",
    "google-drive",
}
SUPPORTED = GOOGLE | {"brave-search"}


def digest(registry, values):
    return hmac.new(
        registry._signing_secret_bytes,
        json.dumps(values, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()


def runtime_ready(registry, item):
    if item["product"] not in getattr(registry, "_consumer_products", set()):
        return False
    if item["product"] in GOOGLE:
        from purecipher.consumer_oauth import load_grant, validate_connection_grant

        grant = load_grant(registry, item)
        if grant:
            try:
                validate_connection_grant(registry, item, grant)
            except ValueError:
                return False
        return bool(
            grant
            and (
                grant.get("expires_at", 0) > time.time() + 30
                or grant.get("refresh_token")
            )
        )
    from purecipher.product_connections import decrypt

    return bool(
        item.get("verified_values")
        and hmac.compare_digest(
            item["verified_values"], digest(registry, decrypt(registry, item))
        )
    )


async def provider_get(url, headers, params=None):
    # Callers supply only fixed provider origins and locally constructed paths.
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise ValueError(
                f"Provider request failed ({response.status_code}); check your connection"
            )
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Unexpected provider response")
        return result
    except (httpx.HTTPError, json.JSONDecodeError):
        raise ValueError(
            "Provider connection failed; retry or reconnect your account"
        ) from None


def access(product):
    value = _ACCESS.get()
    if not value or value["product"] != product:
        raise ValueError("Use an active profile with your own product connection")
    return value["headers"]


def identifier(value):
    if (
        not value
        or value in {".", ".."}
        or any(c in value for c in "/\\?#%")
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Invalid resource ID")
    return quote(value, safe="")


def page(limit, token=""):
    if not 1 <= limit <= 100:
        raise ValueError("Page size must be between 1 and 100")
    return {"maxResults": limit, **({"pageToken": token} if token else {})}


def register_consumer_tools(registry):
    registry._consumer_products = SUPPORTED
    registry._consumer_tool_products = {}

    def tool(product):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = product
            registry.tool(
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": True,
                }
            )(fn)
            return fn

        return decorate

    @tool("brave-search")
    async def brave_web_search(query: str, count: int = 5) -> dict:
        """Search the web with the API key selected in your profile."""
        if not query.strip() or len(query) > 400 or not 1 <= count <= 20:
            raise ValueError("Provide a query up to 400 characters and count 1–20")
        return await provider_get(
            "https://api.search.brave.com/res/v1/web/search",
            access("brave-search"),
            {"q": query, "count": count},
        )

    from purecipher.consumer_google_workspace import (
        register as register_google_workspace,
    )

    register_google_workspace(registry)

    from purecipher.consumer_gmail import register as register_gmail

    register_gmail(registry)

    from purecipher.consumer_cloud import register

    register(registry)
    from purecipher.consumer_utilities import register as register_utilities

    register_utilities(registry)
    from purecipher.consumer_aws import register as register_aws

    register_aws(registry)
    from purecipher.consumer_business import register as register_business

    register_business(registry)
    from purecipher.consumer_observability import register as register_observability

    register_observability(registry)
    from purecipher.consumer_bridge import register as register_bridge

    register_bridge(registry)


def current_profile_client(registry, profile_id, client):
    """Recheck the current request token after awaited provider work."""
    from fastmcp.server.dependencies import get_http_headers

    headers = get_http_headers(include={"authorization", "x-purecipher-profile"})
    # Direct trusted invocations have no profile HTTP request. The profile ASGI
    # wrapper strips caller-supplied markers and supplies its own authenticated ID.
    if not headers.get("x-purecipher-profile"):
        return client
    authorization = headers.get("authorization", "")
    resolved = (
        registry.authenticate_client_token(authorization[7:].strip())
        if authorization.lower().startswith("bearer ")
        else None
    )
    if (
        headers["x-purecipher-profile"] != profile_id
        or not resolved
        or resolved[0].client_id != client.client_id
    ):
        raise ValueError("Client token revoked or client suspended")
    return resolved[0]


async def resolve_access(registry, profile_id, client, tool_name):
    from purecipher.product_connections import decrypt
    from purecipher.workspace import allowed_profile_tools

    if tool_name not in allowed_profile_tools(registry, profile_id, client):
        raise ValueError("Tool is not selected in this profile")
    profile = registry._workspace.get(profile_id)
    from purecipher.consumer_bridge_tools import selected_product

    product = registry._consumer_tool_products.get(tool_name) or selected_product(
        registry, profile, tool_name
    )
    if not product:
        raise ValueError("Consumer tool is unavailable in this profile")
    selected = next(s for s in profile["servers"] if tool_name in s["tools"])
    item = registry._workspace.get(selected.get("connection_id", ""))
    if (
        not item
        or item.get("kind") != "product_connection"
        or item["owner"] != profile["owner"]
        or item["product"] != product
        or not runtime_ready(registry, item)
    ):
        raise ValueError("Your product connection must be authorized and verified")
    from purecipher.consumer_bridge import PRODUCTS as BRIDGES

    token = None
    if product in BRIDGES:
        headers = {}
    elif product in GOOGLE:
        from purecipher.consumer_oauth import access_token

        token = await access_token(registry, item, tool_name=tool_name)
        headers = {"Authorization": "Bearer " + token}
    elif product in {
        "time",
        "memory",
        "sequential-thinking",
        "wikipedia",
        "fetch",
        "aws-documentation",
        "arxiv",
        "aws-core",
        "cloudwatch",
    }:
        headers = {}
    elif product == "brave-search":
        headers = {"X-Subscription-Token": decrypt(registry, item)["BRAVE_API_KEY"]}
    else:
        from purecipher.consumer_cloud import headers as product_headers

        headers = product_headers(product, decrypt(registry, item))
    # Revalidate after an awaited refresh; revocations and profile edits win.
    client = current_profile_client(registry, profile_id, client)
    allowed_profile_tools(registry, profile_id, client)
    current = registry._workspace.get(item["id"])
    current_profile = registry._workspace.get(profile_id)
    if (
        not current
        or not runtime_ready(registry, current)
        or current_profile["revision"] != profile["revision"]
    ):
        raise ValueError("Connection or profile changed; retry")
    if product in GOOGLE:
        from purecipher.consumer_oauth import load_grant, validate_connection_grant

        current_grant = load_grant(registry, current) or {}
        validate_connection_grant(registry, current, current_grant, tool_name=tool_name)
        if token is None or not hmac.compare_digest(
            current_grant.get("access_token", ""), token
        ):
            raise ValueError(
                "Google authorization changed; retry after checking access"
            )
    return {
        "product": product,
        "registry": registry,
        "tool_name": tool_name,
        "profile_revision": current_profile["revision"],
        "connection_revision": current["revision"],
        "owner": current["owner"],
        "profile_id": profile_id,
        "client": client,
        "connection_id": current["id"],
        "headers": headers,
        "values": decrypt(registry, current),
    }
