"""Gmail v1 operations using an owner-authorized SecureMCP profile connection."""

import base64
import binascii
import json
import re
from email.header import decode_header, make_header
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_ATTACHMENTS_BYTES = 5 * 1024 * 1024
PageSize = Annotated[int, Field(ge=1, le=100)]
MessageFormat = Literal["full", "metadata", "minimal", "raw"]
ThreadFormat = Literal["full", "metadata", "minimal"]
HistoryType = Literal["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"]


def header(value: str) -> str:
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Mail headers must not contain control characters")
    return value


def address(value: str) -> str:
    header(value)
    try:
        parsed = Address(addr_spec=value.strip())
    except (ValueError, IndexError) as exc:
        raise ValueError(
            "Recipients must be email addresses without display names"
        ) from exc
    if not parsed.username or not parsed.domain:
        raise ValueError("Recipients must include a mailbox and domain")
    return str(parsed)


class Attachment(BaseModel):
    """An attachment supplied as standard base64; no paths or URLs are fetched."""

    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", max_length=100)
    data_base64: str = Field(max_length=7 * 1024 * 1024)


class MailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: list[str] = Field(default_factory=list, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    bcc: list[str] = Field(default_factory=list, max_length=100)
    body: str = Field(default="", max_length=262144)
    html_body: str | None = Field(default=None, max_length=262144)
    attachments: list[Attachment] = Field(default_factory=list, max_length=20)

    @field_validator("to", "cc", "bcc")
    @classmethod
    def recipients(cls, values: list[str]) -> list[str]:
        return [address(value) for value in values]


class MailContent(MailBody):
    subject: str = Field(default="", max_length=998)

    @field_validator("subject")
    @classmethod
    def safe_subject(cls, value: str) -> str:
        return header(value)


def identifier(value: str) -> str:
    from purecipher.consumer_runtime import identifier as safe_identifier

    if len(value) > 1024:
        raise ValueError("Resource ID is too long")
    return safe_identifier(value)


def list_params(query: str, page_token: str, max_results: int) -> dict[str, Any]:
    if len(query) > 4000 or len(page_token) > 4096:
        raise ValueError("Search query or page token is too long")
    if not 1 <= max_results <= 100:
        raise ValueError("Page size must be between 1 and 100")
    return {
        "maxResults": max_results,
        **({"q": query} if query else {}),
        **({"pageToken": page_token} if page_token else {}),
    }


def label_ids(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    if len(values) > 100:
        raise ValueError("At most 100 label IDs are allowed")
    return list(dict.fromkeys(identifier(value) for value in values))


def label_changes(add: list[str] | None, remove: list[str] | None) -> dict[str, Any]:
    added, removed = label_ids(add), label_ids(remove)
    if not added and not removed:
        raise ValueError("Choose at least one label to add or remove")
    if set(added).intersection(removed):
        raise ValueError("A label cannot be both added and removed")
    return {"addLabelIds": added, "removeLabelIds": removed}


async def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from purecipher.consumer_runtime import (
        _ACCESS,
        access,
        current_profile_client,
        runtime_ready,
    )
    from purecipher.workspace import allowed_profile_tools

    headers = access("google-gmail")
    context = _ACCESS.get() or {}
    registry = context.get("registry")
    if registry is not None:
        # Multi-request operations (compose/reply) recheck revocation before
        # sending, after their earlier awaited profile/message read.
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
                "Connection or profile changed; retry after checking access"
            )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.request(
                method, BASE + path, headers=headers, params=params, json=body
            )
        if not 200 <= response.status_code < 300:
            if method != "GET" and response.status_code >= 500:
                raise ValueError(
                    "Gmail request outcome is unknown. Check the mailbox before retrying to avoid duplicate changes"
                )
            if path == "/history" and response.status_code == 404:
                raise ValueError(
                    "Gmail history checkpoint expired; list the mailbox again before resuming history"
                )
            raise ValueError(
                f"Gmail request failed ({response.status_code}); check permissions and resource IDs"
            )
        if response.status_code == 204 or not response.content:
            return {"deleted": True} if method == "DELETE" else {}
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Gmail returned an unexpected response")
        return result
    except httpx.HTTPError:
        if method == "GET":
            raise ValueError(
                "Gmail is unavailable; retry or reconnect your account"
            ) from None
        raise ValueError(
            "Gmail request outcome is unknown. Check the mailbox before retrying to avoid duplicate changes"
        ) from None
    except json.JSONDecodeError:
        raise ValueError(
            "Gmail returned an invalid response; check the mailbox before retrying changes"
        ) from None


def mime_message(
    content: MailBody,
    sender: str,
    subject: str,
    *,
    sending: bool = False,
    reply_headers: dict[str, str] | None = None,
) -> str:
    if sending and not (content.to or content.cc or content.bcc):
        raise ValueError("Sending requires at least one explicit recipient")
    if len(content.to) + len(content.cc) + len(content.bcc) > 100:
        raise ValueError("At most 100 recipients are allowed")
    message = EmailMessage(policy=SMTP)
    message["From"] = address(sender)
    message["Subject"] = header(subject)
    for key in ("to", "cc", "bcc"):
        if getattr(content, key):
            message[key.title()] = ", ".join(getattr(content, key))
    for name, value in (reply_headers or {}).items():
        message[name] = header(value)
    message.set_content(content.body)
    if content.html_body is not None:
        message.add_alternative(content.html_body, subtype="html")
    total = 0
    for attachment in content.attachments:
        header(attachment.filename)
        if not re.fullmatch(
            r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", attachment.mime_type
        ):
            raise ValueError("Attachment MIME type must be type/subtype")
        try:
            data = base64.b64decode(attachment.data_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Attachment data must be valid standard base64") from None
        total += len(data)
        if total > MAX_ATTACHMENTS_BYTES:
            raise ValueError("Attachments must total no more than 5 MiB")
        main, subtype = attachment.mime_type.split("/", 1)
        message.add_attachment(
            data, maintype=main, subtype=subtype, filename=attachment.filename
        )
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


async def compose(
    content: MailBody,
    subject: str,
    *,
    sending: bool = False,
    reply_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if sending and not (content.to or content.cc or content.bcc):
        raise ValueError("Sending requires at least one explicit recipient")
    profile = await request("GET", "/profile")
    sender = profile.get("emailAddress")
    if not isinstance(sender, str):
        raise ValueError("Gmail did not identify the authorized sender")
    return {
        "raw": mime_message(
            content, sender, subject, sending=sending, reply_headers=reply_headers
        )
    }


def register(registry: Any) -> None:
    registry._consumer_products |= {"google-gmail"}

    def tool(
        *, read_only: bool = True, destructive: bool = False, idempotent: bool = True
    ):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = "google-gmail"
            registry.tool(
                annotations={
                    "readOnlyHint": read_only,
                    "destructiveHint": destructive,
                    "idempotentHint": idempotent,
                    "openWorldHint": True,
                },
                tags={"resource:email", "risk:low" if read_only else "risk:high"},
            )(fn)
            return fn

        return decorate

    @tool()
    async def gmail_profile() -> dict:
        """Read the authorized user's Gmail profile and current history ID."""
        return await request("GET", "/profile")

    @tool()
    async def gmail_list_messages(
        query: str = "",
        page_token: str = "",
        max_results: PageSize = 20,
        label_ids_filter: list[str] | None = None,
        include_spam_trash: bool = False,
    ) -> dict:
        """Search message IDs using Gmail search syntax. Follow nextPageToken; use gmail_get_message for content."""
        params = list_params(query, page_token, max_results)
        params.update(
            {
                "includeSpamTrash": str(include_spam_trash).lower(),
                "labelIds": label_ids(label_ids_filter),
            }
        )
        return await request("GET", "/messages", params=params)

    @tool()
    async def gmail_get_message(
        message_id: str,
        format: MessageFormat = "full",
        metadata_headers: list[str] | None = None,
    ) -> dict:
        """Read a message as full MIME parts, selected metadata, minimal IDs, or base64url raw MIME. Attachment IDs can be read separately."""
        if metadata_headers and format != "metadata":
            raise ValueError("metadata_headers requires metadata format")
        headers = [header(name) for name in metadata_headers or []]
        return await request(
            "GET",
            "/messages/" + identifier(message_id),
            params={"format": format, "metadataHeaders": headers},
        )

    @tool()
    async def gmail_get_attachment(message_id: str, attachment_id: str) -> dict:
        """Read an attachment by its message and attachment IDs. Returns base64url data and decoded byte size."""
        return await request(
            "GET",
            f"/messages/{identifier(message_id)}/attachments/{identifier(attachment_id)}",
        )

    @tool()
    async def gmail_list_threads(
        query: str = "",
        page_token: str = "",
        max_results: PageSize = 20,
        label_ids_filter: list[str] | None = None,
        include_spam_trash: bool = False,
    ) -> dict:
        """Search conversation IDs. A thread matches when any contained message matches the Gmail query."""
        params = list_params(query, page_token, max_results)
        params.update(
            {
                "includeSpamTrash": str(include_spam_trash).lower(),
                "labelIds": label_ids(label_ids_filter),
            }
        )
        return await request("GET", "/threads", params=params)

    @tool()
    async def gmail_get_thread(
        thread_id: str,
        format: ThreadFormat = "full",
        metadata_headers: list[str] | None = None,
    ) -> dict:
        """Read the messages in a conversation. Thread retrieval supports full, metadata and minimal formats."""
        if metadata_headers and format != "metadata":
            raise ValueError("metadata_headers requires metadata format")
        return await request(
            "GET",
            "/threads/" + identifier(thread_id),
            params={
                "format": format,
                "metadataHeaders": [header(name) for name in metadata_headers or []],
            },
        )

    @tool()
    async def gmail_list_labels() -> dict:
        """List system and user label IDs and names in the selected Gmail account."""
        return await request("GET", "/labels")

    @tool()
    async def gmail_get_label(label_id: str) -> dict:
        """Read a label's settings and message/thread counts."""
        return await request("GET", "/labels/" + identifier(label_id))

    @tool()
    async def gmail_list_drafts(
        query: str = "",
        page_token: str = "",
        max_results: PageSize = 20,
        include_spam_trash: bool = False,
    ) -> dict:
        """Search draft IDs. Read full content with gmail_get_draft using the draft ID, not its underlying message ID."""
        params = list_params(query, page_token, max_results)
        params["includeSpamTrash"] = str(include_spam_trash).lower()
        return await request("GET", "/drafts", params=params)

    @tool()
    async def gmail_get_draft(draft_id: str, format: MessageFormat = "full") -> dict:
        """Read a saved draft and its underlying message in the requested MIME format."""
        return await request(
            "GET", "/drafts/" + identifier(draft_id), params={"format": format}
        )

    @tool()
    async def gmail_list_history(
        start_history_id: str,
        page_token: str = "",
        max_results: PageSize = 100,
        label_id: str = "",
        history_types: list[HistoryType] | None = None,
    ) -> dict:
        """Read mailbox changes after a saved history ID. An expired checkpoint requires a fresh mailbox listing; history is not a permanent audit log."""
        if (
            not start_history_id.isascii()
            or not start_history_id.isdigit()
            or len(start_history_id) > 30
        ):
            raise ValueError("Use a numeric history ID returned by Gmail")
        params = {
            **list_params("", page_token, max_results),
            "startHistoryId": start_history_id,
        }
        if label_id:
            params["labelId"] = identifier(label_id)
        if history_types:
            params["historyTypes"] = list(dict.fromkeys(history_types))
        return await request("GET", "/history", params=params)

    @tool(read_only=False, idempotent=False)
    async def gmail_create_draft(content: MailContent) -> dict:
        """Create an unsent draft with explicit content and optional attachments. No message is sent."""
        return await request(
            "POST", "/drafts", body={"message": await compose(content, content.subject)}
        )

    @tool(read_only=False, idempotent=False)
    async def gmail_update_draft(draft_id: str, content: MailContent) -> dict:
        """Replace the entire saved draft, including recipients and attachments. The draft ID is stable but its underlying message ID changes."""
        path = "/drafts/" + identifier(draft_id)
        return await request(
            "PUT", path, body={"message": await compose(content, content.subject)}
        )

    @tool(read_only=False, destructive=True)
    async def gmail_delete_draft(draft_id: str) -> dict:
        """Permanently delete one saved draft. This cannot be undone and does not send it."""
        return await request("DELETE", "/drafts/" + identifier(draft_id))

    @tool(read_only=False, destructive=True, idempotent=False)
    async def gmail_send_draft(draft_id: str) -> dict:
        """Send the saved draft unchanged to its saved recipients. Gmail removes the draft and creates a sent message; do not retry an ambiguous result."""
        identifier(draft_id)
        return await request("POST", "/drafts/send", body={"id": draft_id})

    @tool(read_only=False, destructive=True, idempotent=False)
    async def gmail_send_message(content: MailContent) -> dict:
        """Send email to the explicit recipients, from the authorized Gmail account. Supports text, HTML and up to 5 MiB of attachments. No automatic retries."""
        return await request(
            "POST",
            "/messages/send",
            body=await compose(content, content.subject, sending=True),
        )

    @tool(read_only=False, destructive=True, idempotent=False)
    async def gmail_reply_message(message_id: str, content: MailBody) -> dict:
        """Send a reply in the original conversation to explicitly supplied recipients. Derives the subject and threading headers from the original; never selects reply-all recipients automatically."""
        original = await request(
            "GET",
            "/messages/" + identifier(message_id),
            params={
                "format": "metadata",
                "metadataHeaders": ["Subject", "Message-ID", "References"],
            },
        )
        headers = {
            h["name"].lower(): h["value"]
            for h in original.get("payload", {}).get("headers", [])
            if isinstance(h.get("name"), str) and isinstance(h.get("value"), str)
        }
        message_ref = header(headers.get("message-id", ""))
        if not re.fullmatch(r"<[^<>\s]+>", message_ref):
            raise ValueError(
                "Original message lacks a valid Message-ID for a threaded reply"
            )
        references = header(headers.get("references", "")).strip()
        if references and not re.fullmatch(r"<[^<>\s]+>(?:\s+<[^<>\s]+>)*", references):
            raise ValueError("Original message has invalid threading references")
        subject = str(make_header(decode_header(header(headers.get("subject", "")))))
        payload = await compose(
            content,
            subject,
            sending=True,
            reply_headers={
                "In-Reply-To": message_ref,
                "References": (references + " " + message_ref).strip(),
            },
        )
        payload["threadId"] = identifier(original.get("threadId", ""))
        return await request("POST", "/messages/send", body=payload)

    @tool(read_only=False, idempotent=False)
    async def gmail_create_label(name: str) -> dict:
        """Create a user label. Applying it to messages is a separate operation."""
        if not 1 <= len(name.strip()) <= 225:
            raise ValueError("Label name must be 1–225 characters")
        return await request("POST", "/labels", body={"name": header(name.strip())})

    @tool(read_only=False)
    async def gmail_update_label(
        label_id: str,
        name: str | None = None,
        label_list_visibility: Literal["labelShow", "labelShowIfUnread", "labelHide"]
        | None = None,
        message_list_visibility: Literal["show", "hide"] | None = None,
    ) -> dict:
        """Change a user label's name or visibility without replacing unspecified settings."""
        body = {}
        if name is not None:
            if not 1 <= len(name.strip()) <= 225:
                raise ValueError("Label name must be 1–225 characters")
            body["name"] = header(name.strip())
        if label_list_visibility is not None:
            body["labelListVisibility"] = label_list_visibility
        if message_list_visibility is not None:
            body["messageListVisibility"] = message_list_visibility
        if not body:
            raise ValueError("Choose a label setting to change")
        return await request("PATCH", "/labels/" + identifier(label_id), body=body)

    @tool(read_only=False, destructive=True)
    async def gmail_delete_label(label_id: str) -> dict:
        """Permanently remove a user label and its associations. Messages themselves are retained."""
        return await request("DELETE", "/labels/" + identifier(label_id))

    @tool(read_only=False)
    async def gmail_modify_message_labels(
        message_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
    ) -> dict:
        """Add or remove message labels. Remove INBOX to archive; remove UNREAD to mark read. System label restrictions are enforced by Gmail."""
        return await request(
            "POST",
            "/messages/" + identifier(message_id) + "/modify",
            body=label_changes(add_label_ids, remove_label_ids),
        )

    @tool(read_only=False, destructive=True)
    async def gmail_trash_message(message_id: str) -> dict:
        """Move one message to Trash. This is recoverable with gmail_untrash_message until Gmail removes it."""
        return await request("POST", "/messages/" + identifier(message_id) + "/trash")

    @tool(read_only=False)
    async def gmail_untrash_message(message_id: str) -> dict:
        """Restore a message from Trash without permanently deleting data."""
        return await request("POST", "/messages/" + identifier(message_id) + "/untrash")

    @tool(read_only=False)
    async def gmail_modify_thread_labels(
        thread_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
    ) -> dict:
        """Add or remove labels on all existing messages in a thread. Future replies do not inherit this modification automatically."""
        return await request(
            "POST",
            "/threads/" + identifier(thread_id) + "/modify",
            body=label_changes(add_label_ids, remove_label_ids),
        )

    @tool(read_only=False, destructive=True)
    async def gmail_trash_thread(thread_id: str) -> dict:
        """Move every current message in a conversation to Trash."""
        return await request("POST", "/threads/" + identifier(thread_id) + "/trash")

    @tool(read_only=False)
    async def gmail_untrash_thread(thread_id: str) -> dict:
        """Restore the messages in a conversation from Trash."""
        return await request("POST", "/threads/" + identifier(thread_id) + "/untrash")
