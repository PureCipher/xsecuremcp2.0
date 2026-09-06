"""Read-only consumer runtimes. Credentials are scoped to one profile call."""

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
        from purecipher.consumer_oauth import load_grant

        grant = load_grant(registry, item)
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

    @tool("google-gmail")
    async def gmail_profile() -> dict:
        """Read the authorized user's Gmail profile."""
        return await provider_get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            access("google-gmail"),
        )

    @tool("google-gmail")
    async def gmail_list_messages(
        query: str = "", page_token: str = "", max_results: int = 20
    ) -> dict:
        """List message IDs in your authorized Gmail account."""
        return await provider_get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            access("google-gmail"),
            {**page(max_results, page_token), "q": query},
        )

    @tool("google-gmail")
    async def gmail_get_message(message_id: str) -> dict:
        """Read a message from your authorized Gmail account."""
        return await provider_get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
            + identifier(message_id),
            access("google-gmail"),
            {"format": "full"},
        )

    @tool("google-docs")
    async def docs_get_document(document_id: str) -> dict:
        """Read a Google document accessible to your authorized account."""
        return await provider_get(
            "https://docs.googleapis.com/v1/documents/" + identifier(document_id),
            access("google-docs"),
        )

    @tool("google-tasks")
    async def tasks_list_tasklists(page_token: str = "", max_results: int = 20) -> dict:
        """List your Google task lists."""
        return await provider_get(
            "https://tasks.googleapis.com/tasks/v1/users/@me/lists",
            access("google-tasks"),
            page(max_results, page_token),
        )

    @tool("google-tasks")
    async def tasks_list_tasks(
        tasklist_id: str, page_token: str = "", max_results: int = 20
    ) -> dict:
        """Read tasks in one of your Google task lists."""
        return await provider_get(
            "https://tasks.googleapis.com/tasks/v1/lists/"
            + identifier(tasklist_id)
            + "/tasks",
            access("google-tasks"),
            page(max_results, page_token),
        )

    @tool("google-calendar")
    async def calendar_list_calendars(
        page_token: str = "", max_results: int = 20
    ) -> dict:
        """List calendars available to your authorized Google account."""
        return await provider_get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            access("google-calendar"),
            page(max_results, page_token),
        )

    @tool("google-calendar")
    async def calendar_list_events(
        calendar_id: str = "primary", page_token: str = "", max_results: int = 20
    ) -> dict:
        """Read events in an authorized Google calendar."""
        return await provider_get(
            "https://www.googleapis.com/calendar/v3/calendars/"
            + identifier(calendar_id)
            + "/events",
            access("google-calendar"),
            page(max_results, page_token),
        )

    @tool("google-drive")
    async def drive_search_files(
        query: str = "", page_token: str = "", max_results: int = 20
    ) -> dict:
        """Search file metadata in your authorized Google Drive."""
        params = page(max_results, page_token)
        params["pageSize"] = params.pop("maxResults")
        return await provider_get(
            "https://www.googleapis.com/drive/v3/files",
            access("google-drive"),
            {
                **params,
                "q": query,
                "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
            },
        )

    @tool("google-drive")
    async def drive_get_file(file_id: str) -> dict:
        """Read metadata for a Google Drive file; does not download file contents."""
        return await provider_get(
            "https://www.googleapis.com/drive/v3/files/" + identifier(file_id),
            access("google-drive"),
            {"fields": "id,name,mimeType,modifiedTime,webViewLink"},
        )

    from purecipher.consumer_cloud import register

    register(registry)
    from purecipher.consumer_utilities import register as register_utilities

    register_utilities(registry)
    from purecipher.consumer_aws import register as register_aws

    register_aws(registry)
    from purecipher.consumer_bridge import register as register_bridge

    register_bridge(registry)


async def resolve_access(registry, profile_id, client, tool_name):
    from purecipher.product_connections import decrypt
    from purecipher.workspace import allowed_profile_tools

    if tool_name not in allowed_profile_tools(registry, profile_id, client):
        raise ValueError("Tool is not selected in this profile")
    product = registry._consumer_tool_products[tool_name]
    profile = registry._workspace.get(profile_id)
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

    if product in BRIDGES:
        headers = {}
    elif product in GOOGLE:
        from purecipher.consumer_oauth import access_token

        token = await access_token(registry, item)
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
    allowed_profile_tools(registry, profile_id, client)
    current = registry._workspace.get(item["id"])
    current_profile = registry._workspace.get(profile_id)
    if (
        not current
        or not runtime_ready(registry, current)
        or current_profile["revision"] != profile["revision"]
    ):
        raise ValueError("Connection or profile changed; retry")
    return {
        "product": product,
        "owner": current["owner"],
        "profile_id": profile_id,
        "client": client,
        "connection_id": current["id"],
        "headers": headers,
        "values": decrypt(registry, current),
    }
