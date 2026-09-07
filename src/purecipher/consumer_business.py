"""Owner-authorized business tools; provider requests never use publisher secrets.

See docs/business-tool-coverage.md for API versions, permissions and boundaries.
"""

import base64
import binascii
import json
from datetime import datetime
from email.headerregistry import Address
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlencode, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fastmcp.server.security.outbound import (
    OutboundRequestError,
    async_secure_outbound_request,
)
from purecipher.consumer_cloud import BASE_KEYS, CUSTOM, PRODUCTS

Limit = Annotated[int, Field(ge=1, le=100)]
Page = Annotated[int, Field(ge=1, le=500)]
Resource = Annotated[str, Field(min_length=1, max_length=1024)]
Title = Annotated[str, Field(min_length=1, max_length=255)]
Text = Annotated[str, Field(max_length=32000)]
Cursor = Annotated[str, Field(max_length=4096)]
Positive = Annotated[int, Field(ge=1, le=2147483647)]
IdempotencyKey = Annotated[str, Field(min_length=1, max_length=255)]
MAX_RESPONSE = 2 * 1024 * 1024
MAX_UPLOAD = 1024 * 1024


def identifier(value: str) -> str:
    from purecipher.consumer_runtime import identifier as safe_identifier

    if len(value) > 1024:
        raise ValueError("Resource ID is too long")
    return safe_identifier(value)


def resource_path(value: str) -> str:
    if len(value) > 2048:
        raise ValueError("Resource path is too long")
    return "/".join(identifier(part) for part in value.split("/"))


def nonempty(data: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in data.items() if value is not None}
    if not result:
        raise ValueError("Provide at least one field to update")
    return result


def bounded_json(value: Any, maximum: int = 64000) -> Any:
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Provide finite JSON values") from None
    if len(encoded.encode()) > maximum:
        raise ValueError("JSON input is too large")
    return value


def safe_header(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Header values must not contain control characters")
    return value


def redact(value: Any) -> Any:
    """Do not hand provider credentials or presigned download URLs to MCP clients."""
    hidden = {
        "client_secret",
        "access_token",
        "refresh_token",
        "api_key",
        "token",
        "credentials",
        "@microsoft.graph.downloadUrl",
    }
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items() if key not in hidden}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


async def request(
    product: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    content: bytes | None = None,
    content_type: str = "application/json",
    idempotency_key: str | None = None,
    read_only: bool = False,
) -> dict[str, Any]:
    """Fixed routes, bounded responses, no retry/redirect, fresh access per call."""
    from purecipher.consumer_runtime import (
        _ACCESS,
        access,
        current_profile_client,
        runtime_ready,
    )

    headers = dict(access(product))
    context = _ACCESS.get() or {}
    registry = context.get("registry")
    if registry is not None:
        from purecipher.workspace import allowed_profile_tools

        allowed = allowed_profile_tools(
            registry,
            context["profile_id"],
            current_profile_client(registry, context["profile_id"], context["client"]),
        )
        connection = registry._workspace.get(context["connection_id"])
        profile = registry._workspace.get(context["profile_id"])
        if (
            context["tool_name"] not in allowed
            or not connection
            or not profile
            or connection["revision"] != context["connection_revision"]
            or profile["revision"] != context["profile_revision"]
            or not runtime_ready(registry, connection)
        ):
            raise ValueError(
                "Connection or profile changed; check access before retrying"
            )
    mutation = method != "GET" and not read_only
    if idempotency_key is not None:
        if not 1 <= len(idempotency_key) <= 255:
            raise ValueError("Idempotency key must contain 1 to 255 characters")
        headers["Idempotency-Key"] = safe_header(idempotency_key)
    if body is not None:
        bounded_json(body)
        if product == "stripe":
            content = urlencode(body, doseq=True).encode()
            content_type = "application/x-www-form-urlencoded"
        else:
            content = json.dumps(body, allow_nan=False).encode()
    if content is not None:
        headers["Content-Type"] = content_type
    base = PRODUCTS[product][2]
    if product in CUSTOM:
        base = str(context.get("values", {}).get(BASE_KEYS[product], "")).strip()
        parsed = urlsplit(base)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Configure a valid HTTPS product URL without credentials")
    url = base.rstrip("/") + "/" + path.lstrip("/")
    if params:
        url += "?" + urlencode(params, doseq=True)
    uncertain = "Request outcome is unknown. Check the product before retrying to avoid duplicate changes"
    try:
        if product in CUSTOM:
            response = await async_secure_outbound_request(
                url,
                method=method,
                headers=headers,
                content=content or b"",
                timeout=20,
                max_response_bytes=MAX_RESPONSE,
            )
            status, raw = response.status_code, response.content
            links = {}
        else:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                async with client.stream(
                    method, url, headers=headers, content=content
                ) as response:
                    status = response.status_code
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE:
                            raise ValueError(
                                uncertain
                                if mutation
                                else "Product response is too large; narrow the request"
                            )
                        chunks.append(chunk)
                    raw = b"".join(chunks)
                    links = response.links
        if not 200 <= status < 300:
            if mutation and status >= 500:
                raise ValueError(uncertain)
            raise ValueError(
                f"Product request failed ({status}); check permissions and resource IDs"
            )
        if not raw:
            return {"accepted": True, "status": status}
        data = json.loads(raw)
        if not isinstance(data, (dict, list)):
            raise ValueError(
                uncertain if mutation else "Product returned an unexpected response"
            )
        if isinstance(data, dict) and data.get("ok") is False:
            raise ValueError(
                "Product rejected the request; check permissions and resource IDs"
            )
        result = redact(data) if isinstance(data, dict) else {"items": redact(data)}
        # Inform callers that another page exists; never follow provider-supplied URLs.
        if links.get("next"):
            result["has_next_page"] = True
        return result
    except (httpx.HTTPError, OutboundRequestError):
        raise ValueError(
            uncertain
            if mutation
            else "Product is unavailable; check the connection and retry"
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError(
            uncertain if mutation else "Product returned invalid JSON"
        ) from None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContactFields(StrictModel):
    first_name: Title | None = None
    last_name: Title | None = None
    title: Title | None = None
    organization_name: Title | None = None
    email: Annotated[str, Field(max_length=320)] | None = None


class OutlookMail(StrictModel):
    subject: Title
    body: Text
    to: list[str] = Field(min_length=1, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    body_type: Literal["Text", "HTML"] = "Text"

    @field_validator("to", "cc")
    @classmethod
    def addresses(cls, values: list[str]) -> list[str]:
        for value in values:
            safe_header(value)
            try:
                parsed = Address(addr_spec=value)
                if not parsed.username or not parsed.domain:
                    raise ValueError()
            except (ValueError, IndexError):
                raise ValueError(
                    "Recipients must be complete email addresses"
                ) from None
        return values

    def payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "body": {"contentType": self.body_type, "content": self.body},
            "toRecipients": [{"emailAddress": {"address": email}} for email in self.to],
            "ccRecipients": [{"emailAddress": {"address": email}} for email in self.cc],
        }


class CalendarEvent(StrictModel):
    subject: Title
    start: Annotated[str, Field(max_length=64)]
    end: Annotated[str, Field(max_length=64)]
    time_zone: Annotated[str, Field(min_length=1, max_length=128)] = "UTC"
    description: Text = ""
    location: Annotated[str, Field(max_length=255)] = ""

    @model_validator(mode="after")
    def valid_times(self):
        try:
            start, end = (
                datetime.fromisoformat(self.start),
                datetime.fromisoformat(self.end),
            )
            if end <= start:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(
                "Event times must be ISO date-times with end after start"
            ) from None
        return self

    def payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "start": {"dateTime": self.start, "timeZone": self.time_zone},
            "end": {"dateTime": self.end, "timeZone": self.time_zone},
            "body": {"contentType": "Text", "content": self.description},
            "location": {"displayName": self.location},
        }


def register(registry):
    def tool(
        product,
        name=None,
        *,
        write=False,
        destructive=False,
        resource="business",
        idempotent=False,
    ):
        def decorate(fn):
            tool_name = name or fn.__name__
            registry._consumer_products.add(product)
            registry._consumer_tool_products[tool_name] = product
            registry.tool(
                name=tool_name,
                annotations={
                    "readOnlyHint": not write,
                    "destructiveHint": destructive,
                    "idempotentHint": (not write) or idempotent,
                    "openWorldHint": True,
                },
                tags={f"resource:{resource}", "risk:high" if write else "risk:low"},
            )(fn)
            return fn

        return decorate

    def github_tools(product, prefix):
        def repo(owner, repository):
            return f"repos/{identifier(owner)}/{identifier(repository)}"

        @tool(product, prefix + "_get_repository", resource="source_code")
        async def get_repository(owner: Resource, repository: Resource) -> dict:
            """Read a repository's metadata, default branch and permissions."""
            return await request(product, "GET", repo(owner, repository))

        @tool(product, prefix + "_get_issue", resource="source_code")
        async def get_issue(
            owner: Resource, repository: Resource, issue_number: Positive
        ) -> dict:
            """Read the full issue body and current state."""
            return await request(
                product, "GET", f"{repo(owner, repository)}/issues/{issue_number}"
            )

        @tool(product, prefix + "_list_pull_requests", resource="source_code")
        async def list_pull_requests(
            owner: Resource,
            repository: Resource,
            state: Literal["open", "closed", "all"] = "open",
            limit: Limit = 20,
            page_number: Page = 1,
        ) -> dict:
            """List a page of pull requests; advance page_number when has_next_page is true."""
            return await request(
                product,
                "GET",
                repo(owner, repository) + "/pulls",
                params={"state": state, "per_page": limit, "page": page_number},
            )

        @tool(product, prefix + "_get_pull_request", resource="source_code")
        async def get_pull_request(
            owner: Resource, repository: Resource, pull_number: Positive
        ) -> dict:
            """Read pull request changes, review status and mergeability metadata."""
            return await request(
                product, "GET", f"{repo(owner, repository)}/pulls/{pull_number}"
            )

        @tool(product, prefix + "_get_file", resource="source_code")
        async def get_file(
            owner: Resource,
            repository: Resource,
            path: Resource,
            ref: Annotated[str, Field(max_length=255)] = "",
        ) -> dict:
            """Read a repository file (base64 content) or directory listing at a branch/commit. Large files require another approved client."""
            return await request(
                product,
                "GET",
                repo(owner, repository) + "/contents/" + resource_path(path),
                params={"ref": ref} if ref else None,
            )

        @tool(product, prefix + "_create_issue", write=True, resource="source_code")
        async def create_issue(
            owner: Resource, repository: Resource, title: Title, body: Text = ""
        ) -> dict:
            """Create an issue in the specified repository; may notify repository subscribers."""
            return await request(
                product,
                "POST",
                repo(owner, repository) + "/issues",
                body={"title": title, "body": body},
            )

        @tool(
            product,
            prefix + "_update_issue",
            write=True,
            destructive=True,
            resource="source_code",
        )
        async def update_issue(
            owner: Resource,
            repository: Resource,
            issue_number: Positive,
            title: Title | None = None,
            body: Text | None = None,
            state: Literal["open", "closed"] | None = None,
        ) -> dict:
            """Replace selected issue fields or reopen/close the issue; omitted fields are preserved."""
            return await request(
                product,
                "PATCH",
                f"{repo(owner, repository)}/issues/{issue_number}",
                body=nonempty({"title": title, "body": body, "state": state}),
            )

        @tool(
            product, prefix + "_add_issue_comment", write=True, resource="source_code"
        )
        async def add_issue_comment(
            owner: Resource,
            repository: Resource,
            issue_number: Positive,
            body: Annotated[str, Field(min_length=1, max_length=32000)],
        ) -> dict:
            """Post a comment on an issue or pull request; may notify participants."""
            return await request(
                product,
                "POST",
                f"{repo(owner, repository)}/issues/{issue_number}/comments",
                body={"body": body},
            )

    github_tools("github", "github")
    github_tools("github-reference", "github_reference")

    def slack_tools(product, prefix):
        @tool(product, prefix + "_get_channel", resource="messages")
        async def get_channel(channel_id: Resource) -> dict:
            """Read a conversation's topic, purpose and membership metadata."""
            return await request(
                product,
                "GET",
                "conversations.info",
                params={"channel": identifier(channel_id)},
            )

        @tool(product, prefix + "_get_user", resource="messages")
        async def get_user(user_id: Resource) -> dict:
            """Read a workspace member's profile; email fields need users:read.email."""
            return await request(
                product, "GET", "users.info", params={"user": identifier(user_id)}
            )

        @tool(product, prefix + "_thread_replies", resource="messages")
        async def thread_replies(
            channel_id: Resource,
            thread_ts: Annotated[str, Field(pattern=r"^\d+\.\d+$", max_length=40)],
            limit: Annotated[int, Field(ge=1, le=15)] = 15,
            cursor: Cursor = "",
        ) -> dict:
            """Read thread replies. Token type, conversation membership and history scopes restrict availability; some bot tokens cannot read channel threads."""
            return await request(
                product,
                "GET",
                "conversations.replies",
                params={
                    "channel": identifier(channel_id),
                    "ts": thread_ts,
                    "limit": limit,
                    **({"cursor": cursor} if cursor else {}),
                },
            )

        @tool(product, prefix + "_post_message", write=True, resource="messages")
        async def post_message(
            channel_id: Resource,
            text: Annotated[str, Field(min_length=1, max_length=4000)],
            thread_ts: Annotated[str, Field(pattern=r"^\d+\.\d+$", max_length=40)]
            | None = None,
        ) -> dict:
            """Send a bot message or reply to a selected thread. Link/media unfurls are disabled; explicit mentions may notify people."""
            return await request(
                product,
                "POST",
                "chat.postMessage",
                body={
                    "channel": identifier(channel_id),
                    "text": text,
                    "parse": "none",
                    "link_names": False,
                    "unfurl_links": False,
                    "unfurl_media": False,
                    **({"thread_ts": thread_ts} if thread_ts else {}),
                },
            )

        @tool(
            product,
            prefix + "_update_message",
            write=True,
            destructive=True,
            resource="messages",
        )
        async def update_message(
            channel_id: Resource,
            message_ts: Annotated[str, Field(pattern=r"^\d+\.\d+$", max_length=40)],
            text: Annotated[str, Field(min_length=1, max_length=4000)],
        ) -> dict:
            """Replace an owned bot message with plain text; existing rich blocks are removed."""
            return await request(
                product,
                "POST",
                "chat.update",
                body={
                    "channel": identifier(channel_id),
                    "ts": message_ts,
                    "text": text,
                    "blocks": [],
                    "parse": "none",
                    "link_names": False,
                },
            )

        @tool(
            product,
            prefix + "_delete_message",
            write=True,
            destructive=True,
            resource="messages",
        )
        async def delete_message(
            channel_id: Resource,
            message_ts: Annotated[str, Field(pattern=r"^\d+\.\d+$", max_length=40)],
        ) -> dict:
            """Delete a message owned by this bot; this cannot be undone through this tool."""
            return await request(
                product,
                "POST",
                "chat.delete",
                body={"channel": identifier(channel_id), "ts": message_ts},
            )

    slack_tools("slack", "slack")
    slack_tools("slack-archived", "slack_reference")

    @tool("notion", resource="documents")
    async def notion_get_data_source(data_source_id: Resource) -> dict:
        """Read a shared data source's property schema before querying or creating pages."""
        return await request(
            "notion", "GET", "data_sources/" + identifier(data_source_id)
        )

    @tool("notion", resource="documents")
    async def notion_query_data_source(
        data_source_id: Resource,
        page_size: Limit = 20,
        start_cursor: Cursor = "",
        filter: dict[str, Any] | None = None,
        sorts: Annotated[list[dict[str, Any]], Field(max_length=20)] | None = None,
    ) -> dict:
        """Query rows in a shared data source using its native filter/sort schema; follow next_cursor."""
        return await request(
            "notion",
            "POST",
            f"data_sources/{identifier(data_source_id)}/query",
            read_only=True,
            body={
                "page_size": page_size,
                **({"start_cursor": start_cursor} if start_cursor else {}),
                **({"filter": bounded_json(filter)} if filter is not None else {}),
                **({"sorts": bounded_json(sorts)} if sorts is not None else {}),
            },
        )

    @tool("notion", write=True, resource="documents")
    async def notion_create_page(
        parent_id: Resource,
        properties: dict[str, Any],
        parent_type: Literal["page_id", "data_source_id"] = "page_id",
    ) -> dict:
        """Create a page in an explicitly selected parent. Page parents accept title only; data source properties must match its schema."""
        if not properties:
            raise ValueError("Page properties are required")
        if parent_type == "page_id" and set(properties) != {"title"}:
            raise ValueError("A page parent accepts only the title property")
        return await request(
            "notion",
            "POST",
            "pages",
            body={
                "parent": {parent_type: identifier(parent_id)},
                "properties": bounded_json(properties),
            },
        )

    @tool("notion", write=True, destructive=True, resource="documents")
    async def notion_update_page_properties(
        page_id: Resource, properties: dict[str, Any]
    ) -> dict:
        """Replace supplied page properties; retrieve the data source schema first. Page body blocks are unchanged."""
        if not properties:
            raise ValueError("Provide properties to update")
        return await request(
            "notion",
            "PATCH",
            "pages/" + identifier(page_id),
            body={"properties": bounded_json(properties)},
        )

    @tool("notion", write=True, resource="documents")
    async def notion_append_paragraphs(
        block_id: Resource,
        paragraphs: Annotated[
            list[Annotated[str, Field(min_length=1, max_length=2000)]],
            Field(min_length=1, max_length=100),
        ],
    ) -> dict:
        """Append up to 100 plain-text paragraphs to a shared page or block."""
        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            }
            for text in paragraphs
        ]
        return await request(
            "notion",
            "PATCH",
            f"blocks/{identifier(block_id)}/children",
            body={"children": children},
        )

    @tool("notion", write=True, destructive=True, resource="documents")
    async def notion_set_page_trashed(page_id: Resource, in_trash: bool) -> dict:
        """Move a page to trash or restore it; no permanent deletion."""
        return await request(
            "notion",
            "PATCH",
            "pages/" + identifier(page_id),
            body={"in_trash": in_trash},
        )

    def adf(text):
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            ]
            if text
            else [],
        }

    @tool("jira", resource="issues")
    async def jira_search_issues(
        jql: Annotated[str, Field(min_length=1, max_length=4000)],
        limit: Limit = 20,
        next_page_token: Cursor = "",
    ) -> dict:
        """Search visible Jira issues using enhanced JQL search and nextPageToken pagination."""
        return await request(
            "jira",
            "POST",
            "rest/api/3/search/jql",
            read_only=True,
            body={
                "jql": jql,
                "maxResults": limit,
                "fields": ["summary", "status", "description", "assignee", "updated"],
                **({"nextPageToken": next_page_token} if next_page_token else {}),
            },
        )

    @tool("jira", write=True, resource="issues")
    async def jira_create_issue(
        project_key: Resource,
        issue_type_id: Resource,
        summary: Title,
        description: Text = "",
    ) -> dict:
        """Create a Jira issue with plain text converted to Atlassian Document Format. Projects may require extra fields outside this tool."""
        return await request(
            "jira",
            "POST",
            "rest/api/3/issue",
            body={
                "fields": {
                    "project": {"key": identifier(project_key)},
                    "issuetype": {"id": identifier(issue_type_id)},
                    "summary": summary,
                    "description": adf(description),
                }
            },
        )

    @tool("jira", write=True, destructive=True, resource="issues")
    async def jira_update_issue(
        issue_key: Resource,
        summary: Title | None = None,
        description: Text | None = None,
    ) -> dict:
        """Replace an issue summary or description. Omitted fields are preserved."""
        return await request(
            "jira",
            "PUT",
            "rest/api/3/issue/" + identifier(issue_key),
            body={
                "fields": nonempty(
                    {
                        "summary": summary,
                        "description": adf(description)
                        if description is not None
                        else None,
                    }
                )
            },
        )

    @tool("jira", write=True, resource="issues")
    async def jira_add_comment(
        issue_key: Resource, text: Annotated[str, Field(min_length=1, max_length=32000)]
    ) -> dict:
        """Add a plain-text Jira comment, converted to Atlassian Document Format."""
        return await request(
            "jira",
            "POST",
            f"rest/api/3/issue/{identifier(issue_key)}/comment",
            body={"body": adf(text)},
        )

    @tool("jira", resource="issues")
    async def jira_list_transitions(issue_key: Resource) -> dict:
        """Read currently available transitions and required fields before changing issue state."""
        return await request(
            "jira",
            "GET",
            f"rest/api/3/issue/{identifier(issue_key)}/transitions",
            params={"expand": "transitions.fields"},
        )

    @tool("jira", write=True, destructive=True, resource="issues")
    async def jira_transition_issue(
        issue_key: Resource, transition_id: Resource
    ) -> dict:
        """Apply a selected available transition; transitions requiring extra fields must use Jira directly."""
        return await request(
            "jira",
            "POST",
            f"rest/api/3/issue/{identifier(issue_key)}/transitions",
            body={"transition": {"id": identifier(transition_id)}},
        )

    @tool("atlassian", resource="documents")
    async def confluence_list_spaces(limit: Limit = 20, cursor: Cursor = "") -> dict:
        """List visible Confluence spaces; use the cursor in the provider's next link for another page."""
        return await request(
            "atlassian",
            "GET",
            "wiki/api/v2/spaces",
            params={"limit": limit, **({"cursor": cursor} if cursor else {})},
        )

    @tool("atlassian", resource="documents")
    async def confluence_list_space_pages(
        space_id: Resource, limit: Limit = 20, cursor: Cursor = ""
    ) -> dict:
        """List visible pages within one Confluence space, with cursor pagination."""
        return await request(
            "atlassian",
            "GET",
            f"wiki/api/v2/spaces/{identifier(space_id)}/pages",
            params={"limit": limit, **({"cursor": cursor} if cursor else {})},
        )

    @tool("atlassian", write=True, resource="documents")
    async def confluence_create_page(
        space_id: Resource,
        title: Title,
        storage_body: Text,
        parent_id: Resource | None = None,
        status: Literal["draft", "current"] = "draft",
    ) -> dict:
        """Create a Confluence page from storage-format content. Defaults to draft; current publishes it."""
        return await request(
            "atlassian",
            "POST",
            "wiki/api/v2/pages",
            body={
                "spaceId": identifier(space_id),
                "title": title,
                "status": status,
                "body": {"representation": "storage", "value": storage_body},
                **({"parentId": identifier(parent_id)} if parent_id else {}),
            },
        )

    @tool("atlassian", write=True, destructive=True, resource="documents")
    async def confluence_update_page(
        page_id: Resource,
        title: Title,
        storage_body: Text,
        next_version: Positive,
        status: Literal["draft", "current"] = "current",
    ) -> dict:
        """Replace a page body/title using the next version from a prior read; version conflicts are not retried. Current publishes changes."""
        return await request(
            "atlassian",
            "PUT",
            "wiki/api/v2/pages/" + identifier(page_id),
            body={
                "id": page_id,
                "title": title,
                "status": status,
                "body": {"representation": "storage", "value": storage_body},
                "version": {"number": next_version},
            },
        )

    @tool("atlassian", write=True, destructive=True, resource="documents")
    async def confluence_delete_page(page_id: Resource) -> dict:
        """Delete the selected Confluence page (trash semantics depend on page status)."""
        return await request(
            "atlassian", "DELETE", "wiki/api/v2/pages/" + identifier(page_id)
        )

    @tool("outlook", resource="email")
    async def outlook_get_message(message_id: Resource) -> dict:
        """Read a message body and recipients in the connected user's mailbox."""
        return await request("outlook", "GET", "me/messages/" + identifier(message_id))

    @tool("outlook", resource="email")
    async def outlook_list_folder_messages(
        folder_id: Resource,
        limit: Limit = 20,
        skip: Annotated[int, Field(ge=0, le=100000)] = 0,
    ) -> dict:
        """List messages from one folder. Use the $skip value from @odata.nextLink, not the count of returned messages."""
        return await request(
            "outlook",
            "GET",
            f"me/mailFolders/{identifier(folder_id)}/messages",
            params={
                "$top": limit,
                "$skip": skip,
                "$select": "id,subject,from,receivedDateTime,isRead,isDraft",
            },
        )

    @tool("outlook", resource="email")
    async def outlook_list_folders(
        limit: Limit = 20, skip: Annotated[int, Field(ge=0, le=100000)] = 0
    ) -> dict:
        """List top-level mailbox folders with bounded pagination."""
        return await request(
            "outlook", "GET", "me/mailFolders", params={"$top": limit, "$skip": skip}
        )

    @tool("outlook", write=True, resource="email")
    async def outlook_create_draft(message: OutlookMail) -> dict:
        """Create a mail draft with explicit recipients; does not send it."""
        return await request("outlook", "POST", "me/messages", body=message.payload())

    @tool("outlook", write=True, destructive=True, resource="email")
    async def outlook_send_draft(message_id: Resource) -> dict:
        """Send an existing draft to its saved recipients. A 202 response means accepted, not confirmed delivery."""
        return await request(
            "outlook", "POST", f"me/messages/{identifier(message_id)}/send"
        )

    @tool("outlook", write=True, destructive=True, resource="email")
    async def outlook_move_message(
        message_id: Resource, destination_folder_id: Resource
    ) -> dict:
        """Move a message to a chosen folder; the provider may return a new message ID."""
        return await request(
            "outlook",
            "POST",
            f"me/messages/{identifier(message_id)}/move",
            body={"destinationId": identifier(destination_folder_id)},
        )

    @tool("outlook", write=True, destructive=True, resource="email")
    async def outlook_set_message_read(message_id: Resource, is_read: bool) -> dict:
        """Mark a message read or unread without replacing its content."""
        return await request(
            "outlook",
            "PATCH",
            "me/messages/" + identifier(message_id),
            body={"isRead": is_read},
        )

    @tool("outlook", write=True, destructive=True, resource="email")
    async def outlook_delete_message(message_id: Resource) -> dict:
        """Delete the selected mailbox message; no permanent-delete endpoint is used."""
        return await request(
            "outlook", "DELETE", "me/messages/" + identifier(message_id)
        )

    @tool("outlook", write=True, resource="calendar")
    async def outlook_create_event(
        event: CalendarEvent,
        transaction_id: Annotated[str, Field(min_length=1, max_length=255)],
    ) -> dict:
        """Create a personal calendar event without attendees. Reuse transaction_id for the same attempted creation to reduce duplicates."""
        return await request(
            "outlook",
            "POST",
            "me/events",
            body={**event.payload(), "transactionId": transaction_id},
        )

    @tool("outlook", write=True, destructive=True, resource="calendar")
    async def outlook_update_event(event_id: Resource, event: CalendarEvent) -> dict:
        """Replace the supplied event fields; editing an existing meeting can notify its attendees."""
        return await request(
            "outlook",
            "PATCH",
            "me/events/" + identifier(event_id),
            body=event.payload(),
        )

    @tool("outlook", write=True, destructive=True, resource="calendar")
    async def outlook_delete_event(event_id: Resource) -> dict:
        """Delete a calendar event; deleting an organizer's meeting may send cancellations."""
        return await request("outlook", "DELETE", "me/events/" + identifier(event_id))

    drive_fields = (
        "id,name,size,folder,file,parentReference,eTag,lastModifiedDateTime,webUrl"
    )

    @tool("onedrive", resource="files")
    async def onedrive_list_folder(
        folder_id: Resource, limit: Limit = 20, skip_token: Cursor = ""
    ) -> dict:
        """List a selected folder's children; use $skiptoken from @odata.nextLink. Download URLs are omitted."""
        return await request(
            "onedrive",
            "GET",
            f"me/drive/items/{identifier(folder_id)}/children",
            params={
                "$top": limit,
                "$select": drive_fields,
                **({"$skiptoken": skip_token} if skip_token else {}),
            },
        )

    @tool("onedrive", resource="files")
    async def onedrive_search_files(
        query: Annotated[str, Field(min_length=1, max_length=200)],
        limit: Limit = 20,
        skip_token: Cursor = "",
    ) -> dict:
        """Search names/content in the connected drive; use nextLink's $skiptoken for pagination."""
        escaped = quote(query.replace("'", "''"), safe="")
        return await request(
            "onedrive",
            "GET",
            f"me/drive/root/search(q='{escaped}')",
            params={
                "$top": limit,
                "$select": drive_fields,
                **({"$skiptoken": skip_token} if skip_token else {}),
            },
        )

    def filename(name):
        if (
            any(char in name for char in '/\\:*?"<>|')
            or name in {".", ".."}
            or any(ord(char) < 32 for char in name)
        ):
            raise ValueError("Provide a valid file or folder name, not a path")
        return identifier(name)

    @tool("onedrive", write=True, resource="files")
    async def onedrive_create_folder(parent_id: Resource, name: Title) -> dict:
        """Create a folder; fail on a name conflict rather than silently renaming or replacing."""
        filename(name)
        return await request(
            "onedrive",
            "POST",
            f"me/drive/items/{identifier(parent_id)}/children",
            body={
                "name": name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            },
        )

    @tool("onedrive", write=True, destructive=True, resource="files")
    async def onedrive_upload_file(
        parent_id: Resource,
        name: Title,
        data_base64: Annotated[str, Field(max_length=1400000)],
    ) -> dict:
        """Upload up to 1 MiB supplied bytes. A same-named existing file is replaced. No URL or local path is read."""
        try:
            data = base64.b64decode(data_base64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("File content must be standard base64") from None
        if len(data) > MAX_UPLOAD:
            raise ValueError("File upload must be at most 1 MiB")
        return await request(
            "onedrive",
            "PUT",
            f"me/drive/items/{identifier(parent_id)}:/{filename(name)}:/content",
            content=data,
            content_type="application/octet-stream",
        )

    @tool("onedrive", write=True, destructive=True, resource="files")
    async def onedrive_move_or_rename(
        item_id: Resource, name: Title | None = None, parent_id: Resource | None = None
    ) -> dict:
        """Rename or move a file/folder within the connected drive; no cross-drive move."""
        if name is not None:
            filename(name)
        return await request(
            "onedrive",
            "PATCH",
            "me/drive/items/" + identifier(item_id),
            body=nonempty(
                {
                    "name": name,
                    "parentReference": {"id": identifier(parent_id)}
                    if parent_id
                    else None,
                }
            ),
        )

    @tool("onedrive", write=True, destructive=True, resource="files")
    async def onedrive_delete_item(item_id: Resource) -> dict:
        """Delete a file or folder into the drive recycle bin when supported by the provider."""
        return await request(
            "onedrive", "DELETE", "me/drive/items/" + identifier(item_id)
        )

    def stripe_page(limit, starting_after):
        return {
            "limit": limit,
            **(
                {"starting_after": identifier(starting_after)} if starting_after else {}
            ),
        }

    @tool("stripe", resource="payments")
    async def stripe_list_customers(
        limit: Limit = 20,
        starting_after: Cursor = "",
        email: Annotated[str, Field(max_length=320)] = "",
    ) -> dict:
        """List customers with cursor pagination and an optional exact email filter."""
        return await request(
            "stripe",
            "GET",
            "customers",
            params={
                **stripe_page(limit, starting_after),
                **({"email": email} if email else {}),
            },
        )

    @tool("stripe", resource="payments")
    async def stripe_get_customer(customer_id: Resource) -> dict:
        """Read a customer record without returning credential fields."""
        return await request("stripe", "GET", "customers/" + identifier(customer_id))

    @tool("stripe", write=True, resource="payments")
    async def stripe_create_customer(
        name: Title,
        email: Annotated[str, Field(max_length=320)],
        idempotency_key: IdempotencyKey,
    ) -> dict:
        """Create a customer. Supply a unique key per intended operation and reuse it only for that operation."""
        return await request(
            "stripe",
            "POST",
            "customers",
            body={"name": name, "email": email},
            idempotency_key=idempotency_key,
        )

    @tool("stripe", write=True, destructive=True, resource="payments")
    async def stripe_update_customer(
        customer_id: Resource,
        idempotency_key: IdempotencyKey,
        name: Title | None = None,
        email: Annotated[str, Field(max_length=320)] | None = None,
        description: Text | None = None,
    ) -> dict:
        """Update selected customer identity fields; no balance, payment method or card details are accepted."""
        return await request(
            "stripe",
            "POST",
            "customers/" + identifier(customer_id),
            body=nonempty({"name": name, "email": email, "description": description}),
            idempotency_key=idempotency_key,
        )

    @tool("stripe", resource="payments")
    async def stripe_list_products(
        limit: Limit = 20, starting_after: Cursor = "", active: bool = True
    ) -> dict:
        """List product catalog entries with cursor pagination."""
        return await request(
            "stripe",
            "GET",
            "products",
            params={
                **stripe_page(limit, starting_after),
                "active": str(active).lower(),
            },
        )

    @tool("stripe", resource="payments")
    async def stripe_list_prices(
        limit: Limit = 20,
        starting_after: Cursor = "",
        product_id: Resource | None = None,
    ) -> dict:
        """List active prices, optionally for one product."""
        return await request(
            "stripe",
            "GET",
            "prices",
            params={
                **stripe_page(limit, starting_after),
                "active": "true",
                **({"product": identifier(product_id)} if product_id else {}),
            },
        )

    @tool("stripe", resource="payments")
    async def stripe_get_invoice(invoice_id: Resource) -> dict:
        """Read an invoice and its embedded line page; nested client secrets are removed."""
        return await request("stripe", "GET", "invoices/" + identifier(invoice_id))

    @tool("stripe", write=True, resource="payments")
    async def stripe_create_invoice(
        customer_id: Resource, idempotency_key: IdempotencyKey, description: Text = ""
    ) -> dict:
        """Create a draft invoice with automatic advancement disabled and pending invoice items excluded; does not send or collect money."""
        return await request(
            "stripe",
            "POST",
            "invoices",
            body={
                "customer": identifier(customer_id),
                "description": description,
                "auto_advance": "false",
                "pending_invoice_items_behavior": "exclude",
            },
            idempotency_key=idempotency_key,
        )

    @tool("stripe", write=True, resource="payments")
    async def stripe_add_invoice_item(
        customer_id: Resource,
        invoice_id: Resource,
        amount: Annotated[int, Field(ge=1, le=99999999)],
        currency: Annotated[str, Field(pattern=r"^[a-z]{3}$")],
        description: Text,
        idempotency_key: IdempotencyKey,
    ) -> dict:
        """Add an item to a selected draft invoice. Amount is in the currency's smallest unit; does not finalize or charge."""
        return await request(
            "stripe",
            "POST",
            "invoiceitems",
            body={
                "customer": identifier(customer_id),
                "invoice": identifier(invoice_id),
                "amount": amount,
                "currency": currency,
                "description": description,
            },
            idempotency_key=idempotency_key,
        )

    @tool("stripe", resource="payments")
    async def stripe_list_subscriptions(
        limit: Limit = 20,
        starting_after: Cursor = "",
        customer_id: Resource | None = None,
    ) -> dict:
        """List subscriptions, including canceled ones, with optional customer selection."""
        return await request(
            "stripe",
            "GET",
            "subscriptions",
            params={
                **stripe_page(limit, starting_after),
                "status": "all",
                **({"customer": identifier(customer_id)} if customer_id else {}),
            },
        )

    @tool("stripe", write=True, destructive=True, resource="payments")
    async def stripe_set_subscription_cancel_at_period_end(
        subscription_id: Resource,
        cancel_at_period_end: bool,
        idempotency_key: IdempotencyKey,
    ) -> dict:
        """Schedule subscription cancellation at period end or undo that schedule. This affects future billing; no immediate cancellation/refund."""
        return await request(
            "stripe",
            "POST",
            "subscriptions/" + identifier(subscription_id),
            body={"cancel_at_period_end": str(cancel_at_period_end).lower()},
            idempotency_key=idempotency_key,
        )

    @tool("stripe", write=True, resource="payments")
    async def stripe_create_payment_intent(
        amount: Annotated[int, Field(ge=1, le=99999999)],
        currency: Annotated[str, Field(pattern=r"^[a-z]{3}$")],
        idempotency_key: IdempotencyKey,
        customer_id: Resource | None = None,
    ) -> dict:
        """Create an unconfirmed payment intent in smallest currency units. Does not confirm or charge; client_secret is omitted."""
        return await request(
            "stripe",
            "POST",
            "payment_intents",
            body={
                "amount": amount,
                "currency": currency,
                "confirm": "false",
                **({"customer": identifier(customer_id)} if customer_id else {}),
            },
            idempotency_key=idempotency_key,
        )

    @tool("stripe", write=True, destructive=True, resource="payments")
    async def stripe_refund_payment(
        payment_intent_id: Resource,
        amount: Annotated[int, Field(ge=1, le=99999999)],
        idempotency_key: IdempotencyKey,
    ) -> dict:
        """Issue a real refund of an explicit smallest-unit amount against an existing payment. This moves money and requires specific authorization."""
        return await request(
            "stripe",
            "POST",
            "refunds",
            body={"payment_intent": identifier(payment_intent_id), "amount": amount},
            idempotency_key=idempotency_key,
        )

    def hf_repo(repo_id):
        if len(repo_id.split("/")) > 2:
            raise ValueError("Repository ID must be name or namespace/name")
        return resource_path(repo_id)

    @tool("huggingface", resource="models")
    async def huggingface_get_model(repo_id: Resource) -> dict:
        """Read model metadata and listed files; does not download weights or run inference."""
        return await request("huggingface", "GET", "models/" + hf_repo(repo_id))

    @tool("huggingface", resource="datasets")
    async def huggingface_get_dataset(repo_id: Resource) -> dict:
        """Read dataset metadata and listed files; does not download or execute dataset code."""
        return await request("huggingface", "GET", "datasets/" + hf_repo(repo_id))

    @tool("huggingface", resource="models")
    async def huggingface_get_space(repo_id: Resource) -> dict:
        """Read Space metadata and runtime status without calling the application."""
        return await request("huggingface", "GET", "spaces/" + hf_repo(repo_id))

    @tool("huggingface", resource="models")
    async def huggingface_search_spaces(
        search: Annotated[str, Field(max_length=200)] = "", limit: Limit = 20
    ) -> dict:
        """Search a bounded set of Spaces. Refine search when has_next_page is true."""
        return await request(
            "huggingface", "GET", "spaces", params={"search": search, "limit": limit}
        )

    @tool("huggingface", write=True, resource="models")
    async def huggingface_create_repository(
        name: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")],
        repo_type: Literal["model", "dataset", "space"],
        organization: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")]
        | None = None,
        private: bool = True,
        space_sdk: Literal["gradio", "docker", "static"] | None = None,
    ) -> dict:
        """Create a private repository by default. Space creation requires an explicit SDK; no paid hardware is provisioned."""
        if repo_type == "space" and space_sdk is None:
            raise ValueError("Space repositories require space_sdk")
        if repo_type != "space" and space_sdk is not None:
            raise ValueError("space_sdk only applies to Space repositories")
        return await request(
            "huggingface",
            "POST",
            "repos/create",
            body={
                "name": name,
                "type": repo_type,
                "visibility": "private" if private else "public",
                **({"organization": organization} if organization else {}),
                **({"sdk": space_sdk} if space_sdk else {}),
            },
        )

    @tool("apollo", resource="crm")
    async def apollo_search_contacts(
        query: Annotated[str, Field(max_length=500)] = "",
        limit: Limit = 20,
        page_number: Page = 1,
    ) -> dict:
        """Search contacts already saved in your Apollo team; no people enrichment or email reveal."""
        return await request(
            "apollo",
            "POST",
            "contacts/search",
            read_only=True,
            body={"q_keywords": query, "per_page": limit, "page": page_number},
        )

    @tool("apollo", resource="crm")
    async def apollo_search_accounts(
        organization_name: Annotated[str, Field(max_length=255)] = "",
        limit: Limit = 20,
        page_number: Page = 1,
    ) -> dict:
        """Search saved Apollo accounts, with page-number pagination; no organization enrichment."""
        return await request(
            "apollo",
            "POST",
            "accounts/search",
            read_only=True,
            body={
                "q_organization_name": organization_name,
                "per_page": limit,
                "page": page_number,
            },
        )

    @tool("apollo", write=True, resource="crm")
    async def apollo_create_contact(contact: ContactFields) -> dict:
        """Create a CRM contact from caller-supplied fields. Does not enrich, reveal data or merge/overwrite an existing contact."""
        body = nonempty(contact.model_dump(exclude_none=True))
        return await request(
            "apollo", "POST", "contacts", body={**body, "run_dedupe": False}
        )

    @tool("apollo", write=True, destructive=True, resource="crm")
    async def apollo_update_contact(
        contact_id: Resource, contact: ContactFields
    ) -> dict:
        """Update only supplied CRM contact fields; does not alter campaign or list membership."""
        return await request(
            "apollo",
            "PATCH",
            "contacts/" + identifier(contact_id),
            body=nonempty(contact.model_dump(exclude_none=True)),
        )

    @tool("apollo", write=True, resource="crm")
    async def apollo_create_account(
        name: Title,
        domain: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")],
    ) -> dict:
        """Create a saved CRM account from an explicit organization name and domain; does not start outreach."""
        return await request(
            "apollo", "POST", "accounts", body={"name": name, "domain": domain}
        )

    def workflow_summary(result):
        return {
            key: result[key]
            for key in (
                "id",
                "name",
                "active",
                "createdAt",
                "updatedAt",
                "versionId",
                "tags",
            )
            if key in result
        }

    @tool("n8n", resource="automation")
    async def n8n_get_workflow(workflow_id: Resource) -> dict:
        """Read workflow status and version metadata. Node parameters and credentials are intentionally omitted."""
        return workflow_summary(
            await request("n8n", "GET", "api/v1/workflows/" + identifier(workflow_id))
        )

    @tool("n8n", resource="automation")
    async def n8n_list_executions(
        limit: Limit = 20,
        cursor: Cursor = "",
        workflow_id: Resource | None = None,
        status: Literal["error", "success", "waiting"] | None = None,
    ) -> dict:
        """List execution metadata only, with cursor pagination; node input/output data is excluded."""
        result = await request(
            "n8n",
            "GET",
            "api/v1/executions",
            params={
                "limit": limit,
                "includeData": "false",
                **({"cursor": cursor} if cursor else {}),
                **({"workflowId": identifier(workflow_id)} if workflow_id else {}),
                **({"status": status} if status else {}),
            },
        )
        fields = {
            "id",
            "finished",
            "mode",
            "status",
            "startedAt",
            "stoppedAt",
            "workflowId",
            "waitTill",
            "retryOf",
            "retrySuccessId",
        }
        return {
            "data": [
                {key: value for key, value in item.items() if key in fields}
                for item in result.get("data", [])
            ],
            "nextCursor": result.get("nextCursor"),
        }

    @tool("n8n", write=True, destructive=True, resource="automation")
    async def n8n_activate_workflow(workflow_id: Resource) -> dict:
        """Activate an existing workflow. Its triggers may immediately cause external actions; inspect it in n8n before authorizing."""
        return workflow_summary(
            await request(
                "n8n", "POST", f"api/v1/workflows/{identifier(workflow_id)}/activate"
            )
        )

    @tool("n8n", write=True, destructive=True, resource="automation")
    async def n8n_deactivate_workflow(workflow_id: Resource) -> dict:
        """Deactivate an existing workflow's triggers; does not promise to cancel executions already running."""
        return workflow_summary(
            await request(
                "n8n", "POST", f"api/v1/workflows/{identifier(workflow_id)}/deactivate"
            )
        )

    @tool("n8n", write=True, destructive=True, resource="automation")
    async def n8n_delete_workflow(workflow_id: Resource) -> dict:
        """Delete the selected workflow. This is destructive and does not export a backup."""
        return workflow_summary(
            await request(
                "n8n", "DELETE", "api/v1/workflows/" + identifier(workflow_id)
            )
        )
