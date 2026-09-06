"""Product-specific, read-only calls using consumer-owned API credentials."""

import base64
import json
from urllib.parse import urlencode, urlsplit

import httpx

from fastmcp.server.security.outbound import (
    OutboundRequestError,
    async_secure_outbound_request,
)

# Fixed origins: neither tool arguments nor connection settings select a host.
CUSTOM = {"grafana", "n8n", "sonarqube", "jira", "atlassian", "dynatrace"}
BASE_KEYS = {
    "grafana": "param:url",
    "sonarqube": "param:url",
    "n8n": "param:api_url",
    "dynatrace": "param:url",
    "atlassian": "param:confluence.url",
    "jira": "BASE_URL",
}
PRODUCTS = {
    "firecrawl": (
        "FIRECRAWL_API_KEY",
        "Firecrawl API key",
        "https://api.firecrawl.dev/v2/",
        "team/credit-usage",
    ),
    "dynatrace": (
        "DYNATRACE_API_TOKEN",
        "Dynatrace API token (entities.read)",
        "",
        "api/v2/entities?entitySelector=type(HOST)&pageSize=1",
    ),
    "grafana": ("GRAFANA_API_KEY", "Grafana service-account token", "", "api/search"),
    "n8n": ("N8N_API_KEY", "n8n API key", "", "api/v1/workflows?limit=1"),
    "sonarqube": (
        "SONARQUBE_TOKEN",
        "SonarQube user token",
        "",
        "api/authentication/validate",
    ),
    "jira": ("JIRA_API_TOKEN", "Jira Cloud API token", "", "rest/api/3/myself"),
    "atlassian": (
        "CONFLUENCE_API_TOKEN",
        "Confluence Cloud API token",
        "",
        "wiki/api/v2/spaces?limit=1",
    ),
    "apollo": (
        "APOLLO_API_KEY",
        "Apollo API key",
        "https://api.apollo.io/api/v1/",
        "users/api_profile",
    ),
    "stripe": (
        "STRIPE_API_KEY",
        "Stripe restricted API key",
        "https://api.stripe.com/v1/",
        "balance",
    ),
    "github": (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GitHub fine-grained personal access token",
        "https://api.github.com/",
        "user",
    ),
    "github-reference": (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GitHub personal access token",
        "https://api.github.com/",
        "user",
    ),
    "slack": (
        "SLACK_BOT_TOKEN",
        "Slack bot token",
        "https://slack.com/api/",
        "auth.test",
    ),
    "slack-archived": (
        "SLACK_BOT_TOKEN",
        "Slack bot token",
        "https://slack.com/api/",
        "auth.test",
    ),
    "huggingface": (
        "HF_TOKEN",
        "Hugging Face read token",
        "https://huggingface.co/api/",
        "whoami-v2",
    ),
    "notion": (
        "INTERNAL_INTEGRATION_TOKEN",
        "Notion integration token",
        "https://api.notion.com/v1/",
        "users/me",
    ),
    "outlook": (
        "MICROSOFT_ACCESS_TOKEN",
        "Microsoft delegated access token",
        "https://graph.microsoft.com/v1.0/",
        "me",
    ),
    "onedrive": (
        "MICROSOFT_ACCESS_TOKEN",
        "Microsoft delegated access token",
        "https://graph.microsoft.com/v1.0/",
        "me",
    ),
}


def headers(product, values):
    key = PRODUCTS[product][0]
    token = values.get(key, "")
    if not token or any(c in token for c in "\r\n"):
        raise ValueError("Enter a valid product credential first")
    result = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if product in {"jira", "atlassian"}:
        email = values.get("ACCOUNT_EMAIL", "")
        if not email or ":" in email:
            raise ValueError("Enter your Atlassian account email")
        result["Authorization"] = (
            "Basic " + base64.b64encode((email + ":" + token).encode()).decode()
        )
    if product == "dynatrace":
        result["Authorization"] = "Api-Token " + token
    if product == "n8n":
        result = {"X-N8N-API-KEY": token, "Accept": "application/json"}
    if product == "apollo":
        result = {"x-api-key": token, "Accept": "application/json"}
    if product == "notion":
        result["Notion-Version"] = "2026-03-11"
    if product.startswith("github"):
        result["X-GitHub-Api-Version"] = "2022-11-28"
    return result


async def request(product, path, auth, params=None, body=None, base=None):
    try:
        if product in CUSTOM:
            if base is None:
                from purecipher.consumer_runtime import _ACCESS

                current = _ACCESS.get()
                if not current or current["product"] != product:
                    raise ValueError("An assigned profile is required")
                base = current["values"].get(BASE_KEYS[product], "")
            parsed = urlsplit(base)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Use your service's HTTPS base URL without credentials or query parameters"
                )
            url = base.rstrip("/") + "/" + path
            if params:
                url += ("&" if "?" in url else "?") + urlencode(params)
            response = await async_secure_outbound_request(
                url,
                method="POST" if body is not None else "GET",
                content=json.dumps(body).encode() if body is not None else b"",
                headers={**auth, "Content-Type": "application/json"},
                timeout=20,
                max_response_bytes=2 * 1024 * 1024,
            )
            data = json.loads(response.content) if response.status_code == 200 else {}
        else:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.request(
                    "POST" if body is not None else "GET",
                    PRODUCTS[product][2] + path,
                    headers=auth,
                    params=params,
                    json=body,
                )
            data = response.json() if response.status_code == 200 else {}
        if response.status_code != 200:
            raise ValueError(
                f"Provider request failed ({response.status_code}); check token permissions or expiry"
            )
        if isinstance(data, list):
            data = {"items": data}
        if not isinstance(data, dict) or data.get("ok") is False:
            raise ValueError("Provider rejected the request; check token permissions")
        return data
    except (httpx.HTTPError, TypeError, OutboundRequestError, json.JSONDecodeError):
        raise ValueError("Provider connection failed; try again") from None


async def verify(product, values):
    result = await request(
        product,
        PRODUCTS[product][3],
        headers(product, values),
        body={} if product.startswith("slack") else None,
        **({"base": values.get(BASE_KEYS[product], "")} if product in CUSTOM else {}),
    )
    if product == "sonarqube" and result.get("valid") is not True:
        raise ValueError("SonarQube rejected the token")
    return result


def register(registry):
    from purecipher.consumer_runtime import access, identifier, page

    registry._consumer_products = registry._consumer_products | PRODUCTS.keys()

    def tool(product, name=None):
        def decorate(fn):
            tool_name = name or fn.__name__
            registry._consumer_tool_products[tool_name] = product
            registry.tool(
                name=tool_name,
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": True,
                },
            )(fn)
            return fn

        return decorate

    @tool("stripe")
    async def stripe_get_balance() -> dict:
        """Read the balance for your Stripe account."""
        return await request("stripe", "balance", access("stripe"))

    @tool("stripe")
    async def stripe_list_invoices(limit: int = 20, starting_after: str = "") -> dict:
        """Read invoice summaries; requires invoice read permission."""
        page(limit)
        data = await request(
            "stripe",
            "invoices",
            access("stripe"),
            {
                "limit": limit,
                **(
                    {"starting_after": identifier(starting_after)}
                    if starting_after
                    else {}
                ),
            },
        )
        return {
            "has_more": data.get("has_more", False),
            "data": [
                {
                    k: row[k]
                    for k in (
                        "id",
                        "number",
                        "amount_due",
                        "amount_paid",
                        "currency",
                        "status",
                        "created",
                    )
                    if k in row
                }
                for row in data.get("data", [])
            ],
        }

    @tool("stripe")
    async def stripe_list_payment_intents(limit: int = 20) -> dict:
        """Read payment summaries; never returns client secrets."""
        page(limit)
        data = await request(
            "stripe", "payment_intents", access("stripe"), {"limit": limit}
        )
        return {
            "has_more": data.get("has_more", False),
            "data": [
                {
                    k: row[k]
                    for k in ("id", "amount", "currency", "status", "created")
                    if k in row
                }
                for row in data.get("data", [])
            ],
        }

    def github(product, prefix):
        @tool(product, prefix + "_list_repositories")
        async def repositories(limit: int = 20, page_number: int = 1) -> dict:
            """List repositories accessible to your token. Page numbering starts at one."""
            page(limit)
            if page_number < 1:
                raise ValueError("Page must be positive")
            return await request(
                product,
                "user/repos",
                access(product),
                {"per_page": limit, "page": page_number},
            )

        @tool(product, prefix + "_list_issues")
        async def issues(owner: str, repository: str, limit: int = 20) -> dict:
            """Read issues and pull requests for one accessible repository."""
            page(limit)
            return await request(
                product,
                f"repos/{identifier(owner)}/{identifier(repository)}/issues",
                access(product),
                {"per_page": limit},
            )

    github("github", "github")
    github("github-reference", "github_reference")

    def slack(product, prefix):
        @tool(product, prefix + "_list_channels")
        async def channels(limit: int = 20, cursor: str = "") -> dict:
            """List conversations available to your Slack bot; requires conversations read scopes."""
            page(limit)
            return await request(
                product,
                "conversations.list",
                access(product),
                {"limit": limit, "cursor": cursor},
            )

        @tool(product, prefix + "_channel_history")
        async def history(channel_id: str, limit: int = 15, cursor: str = "") -> dict:
            """Read messages visible to your Slack bot; requires the channel's history scope."""
            if not 1 <= limit <= 15:
                raise ValueError("Limit must be between 1 and 15")
            return await request(
                product,
                "conversations.history",
                access(product),
                {"channel": channel_id, "limit": limit, "cursor": cursor},
            )

    slack("slack", "slack")
    slack("slack-archived", "slack_reference")

    @tool("huggingface")
    async def huggingface_search_models(search: str = "", limit: int = 20) -> dict:
        """Search Hugging Face model metadata using your account's token."""
        page(limit)
        return await request(
            "huggingface",
            "models",
            access("huggingface"),
            {"search": search, "limit": limit},
        )

    @tool("huggingface")
    async def huggingface_search_datasets(search: str = "", limit: int = 20) -> dict:
        """Search Hugging Face dataset metadata; does not download or execute code."""
        page(limit)
        return await request(
            "huggingface",
            "datasets",
            access("huggingface"),
            {"search": search, "limit": limit},
        )

    @tool("notion")
    async def notion_search(
        query: str = "", page_size: int = 20, start_cursor: str = ""
    ) -> dict:
        """Search pages and databases shared with your Notion integration."""
        page(page_size)
        return await request(
            "notion",
            "search",
            access("notion"),
            body={
                "query": query,
                "page_size": page_size,
                **({"start_cursor": start_cursor} if start_cursor else {}),
            },
        )

    @tool("notion")
    async def notion_get_page(page_id: str) -> dict:
        """Read properties of a page shared with your integration."""
        return await request("notion", "pages/" + identifier(page_id), access("notion"))

    @tool("notion")
    async def notion_get_block_children(block_id: str, page_size: int = 20) -> dict:
        """Read content blocks from a shared page or block."""
        page(page_size)
        return await request(
            "notion",
            "blocks/" + identifier(block_id) + "/children",
            access("notion"),
            {"page_size": page_size},
        )

    @tool("outlook")
    async def outlook_list_messages(limit: int = 20) -> dict:
        """Read Outlook message summaries; requires delegated Mail.Read permission."""
        page(limit)
        return await request(
            "outlook",
            "me/messages",
            access("outlook"),
            {"$top": limit, "$select": "id,subject,from,receivedDateTime,isRead"},
        )

    @tool("outlook")
    async def outlook_list_events(limit: int = 20) -> dict:
        """Read Outlook calendar events; requires delegated Calendars.Read permission."""
        page(limit)
        return await request(
            "outlook",
            "me/events",
            access("outlook"),
            {"$top": limit, "$select": "id,subject,start,end,location"},
        )

    @tool("onedrive")
    async def onedrive_list_files(limit: int = 20) -> dict:
        """List root file metadata; requires delegated Files.Read permission."""
        page(limit)
        return await request(
            "onedrive",
            "me/drive/root/children",
            access("onedrive"),
            {"$top": limit, "$select": "id,name,size,folder,file,lastModifiedDateTime"},
        )

    @tool("onedrive")
    async def onedrive_get_file_metadata(item_id: str) -> dict:
        """Read file metadata without returning temporary download URLs."""
        return await request(
            "onedrive",
            "me/drive/items/" + identifier(item_id),
            access("onedrive"),
            {"$select": "id,name,size,folder,file,lastModifiedDateTime"},
        )

    @tool("apollo")
    async def apollo_search_people(
        job_title: str = "", location: str = "", page_number: int = 1, limit: int = 20
    ) -> dict:
        """Search prospect summaries; does not enrich or reveal email addresses or phone numbers."""
        page(limit)
        if not 1 <= page_number <= 500:
            raise ValueError("Page must be between 1 and 500")
        body = {"page": page_number, "per_page": limit}
        if job_title:
            body["person_titles"] = [job_title]
        if location:
            body["person_locations"] = [location]
        return await request(
            "apollo", "mixed_people/api_search", access("apollo"), body=body
        )

    @tool("apollo")
    async def apollo_profile() -> dict:
        """Read the identity associated with your Apollo API key."""
        return await request("apollo", "users/api_profile", access("apollo"))

    @tool("grafana")
    async def grafana_search_dashboards(query: str = "", limit: int = 20) -> dict:
        """Search dashboards permitted by your Grafana service account."""
        page(limit)
        return await request(
            "grafana",
            "api/search",
            access("grafana"),
            {"query": query, "limit": limit, "type": "dash-db"},
        )

    @tool("n8n")
    async def n8n_list_workflows(limit: int = 20, cursor: str = "") -> dict:
        """Read workflow summaries; does not execute workflows or return node credentials."""
        page(limit)
        result = await request(
            "n8n",
            "api/v1/workflows",
            access("n8n"),
            {"limit": limit, **({"cursor": cursor} if cursor else {})},
        )
        return {
            "data": [
                {
                    k: row[k]
                    for k in ("id", "name", "active", "createdAt", "updatedAt")
                    if k in row
                }
                for row in result.get("data", [])
            ],
            "nextCursor": result.get("nextCursor"),
        }

    @tool("sonarqube")
    async def sonarqube_search_issues(project: str, limit: int = 20) -> dict:
        """Read issues from an accessible SonarQube project."""
        page(limit)
        return await request(
            "sonarqube",
            "api/issues/search",
            access("sonarqube"),
            {"componentKeys": project, "ps": limit},
        )

    @tool("jira")
    async def jira_get_issue(issue_key: str) -> dict:
        """Read one Jira Cloud issue accessible to your account."""
        return await request(
            "jira",
            "rest/api/3/issue/" + identifier(issue_key),
            access("jira"),
            {"fields": "summary,status,description,assignee,updated"},
        )

    @tool("atlassian")
    async def confluence_list_pages(limit: int = 20) -> dict:
        """Read Confluence Cloud pages accessible to your account using API v2."""
        page(limit)
        return await request(
            "atlassian", "wiki/api/v2/pages", access("atlassian"), {"limit": limit}
        )

    @tool("atlassian")
    async def confluence_get_page(page_id: str) -> dict:
        """Read one Confluence Cloud page and its storage-format body."""
        return await request(
            "atlassian",
            "wiki/api/v2/pages/" + identifier(page_id),
            access("atlassian"),
            {"body-format": "storage"},
        )

    @tool("firecrawl")
    async def firecrawl_search(query: str, limit: int = 5) -> dict:
        """Search the web using your Firecrawl account. This consumes provider credits."""
        if not query.strip() or len(query) > 400 or not 1 <= limit <= 10:
            raise ValueError("Provide a query up to 400 characters and a limit of 1–10")
        return await request(
            "firecrawl",
            "search",
            access("firecrawl"),
            body={"query": query, "limit": limit},
        )

    @tool("dynatrace")
    async def dynatrace_list_entities(
        entity_type: str = "HOST", limit: int = 20
    ) -> dict:
        """Read monitored entities; requires an entities.read token."""
        page(limit)
        if not entity_type.replace("_", "").isalnum():
            raise ValueError("Use an entity type such as HOST or SERVICE")
        return await request(
            "dynatrace",
            "api/v2/entities",
            access("dynatrace"),
            {"entitySelector": "type(" + entity_type + ")", "pageSize": limit},
        )
