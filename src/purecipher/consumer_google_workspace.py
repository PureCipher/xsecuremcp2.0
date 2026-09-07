"""Typed Google Workspace operations with owner-bound grants and fixed API origins.

No caller-provided endpoint, credentials, local paths or arbitrary batch request.
"""

import base64
import binascii
import json
import re
import secrets
from datetime import date, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

BASES = {
    "google-docs": "https://docs.googleapis.com/v1",
    "google-tasks": "https://tasks.googleapis.com/tasks/v1",
    "google-calendar": "https://www.googleapis.com/calendar/v3",
    "google-drive": "https://www.googleapis.com/drive/v3",
}
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
PageSize = Annotated[int, Field(ge=1, le=100)]
ShortText = Annotated[str, Field(min_length=1, max_length=1024)]
Text = Annotated[str, Field(max_length=262144)]
Index = Annotated[int, Field(ge=1, le=2147483647)]
SendUpdates = Literal["all", "externalOnly", "none"]
ExportMime = Literal[
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/tab-separated-values",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
]
FILE_FIELDS = "id,name,mimeType,modifiedTime,webViewLink,parents,size,description,trashed,version,capabilities(canDownload,canEdit,canTrash,canDelete)"


def identifier(value: str) -> str:
    from purecipher.consumer_runtime import identifier as safe_identifier

    if len(value) > 1024:
        raise ValueError("Resource ID is too long")
    return safe_identifier(value)


def header(value: str) -> str:
    if (
        not value
        or len(value) > 1024
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("A valid resource ETag is required")
    if value == "*":
        raise ValueError("Use the resource's exact ETag from its get tool")
    return value


def page(page_token: str, max_results: int) -> dict[str, Any]:
    if len(page_token) > 4096 or not 1 <= max_results <= 100:
        raise ValueError("Invalid page token or page size (1–100)")
    return {
        "maxResults": max_results,
        **({"pageToken": page_token} if page_token else {}),
    }


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError("Use an RFC3339 timestamp with a timezone offset") from None
    if parsed.tzinfo is None or "T" not in value or len(value) > 64:
        raise ValueError("Use an RFC3339 timestamp with a timezone offset")
    return parsed


def timezone_name(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Use an IANA timezone, for example America/New_York") from None
    return value


class EventTime(BaseModel):
    """Exactly one all-day date or timezone-aware date_time; end is exclusive."""

    model_config = ConfigDict(extra="forbid")
    date: str | None = Field(default=None, max_length=10)
    date_time: str | None = Field(default=None, max_length=64)
    time_zone: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check(self):
        if (self.date is None) == (self.date_time is None):
            raise ValueError("Choose exactly one date or date_time")
        if self.date is not None:
            date.fromisoformat(self.date)
        if self.date_time is not None:
            timestamp(self.date_time)
        if self.time_zone is not None:
            timezone_name(self.time_zone)
        return self

    def payload(self):
        return {
            k: v
            for k, v in {
                "date": self.date,
                "dateTime": self.date_time,
                "timeZone": self.time_zone,
            }.items()
            if v is not None
        }


class EventFields(BaseModel):
    """Explicit editable event fields. Attendees replace the entire attendee list."""

    model_config = ConfigDict(extra="forbid")
    summary: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=16384)
    location: str | None = Field(default=None, max_length=1024)
    start: EventTime | None = None
    end: EventTime | None = None
    attendees: list[str] | None = Field(default=None, max_length=100)
    transparency: Literal["opaque", "transparent"] | None = None
    visibility: Literal["default", "public", "private", "confidential"] | None = None

    @model_validator(mode="after")
    def check(self):
        from purecipher.consumer_gmail import address

        if (self.start is None) != (self.end is None):
            raise ValueError("Provide start and end together")
        if self.start is not None and self.end is not None:
            if (self.start.date is None) != (self.end.date is None):
                raise ValueError("Start and end must both be dates or both date-times")
            if self.start.date is not None and self.end.date is not None:
                left, right = (
                    date.fromisoformat(self.start.date),
                    date.fromisoformat(self.end.date),
                )
            else:
                if self.start.date_time is None or self.end.date_time is None:
                    raise ValueError("Start and end must include date-times")
                left, right = (
                    timestamp(self.start.date_time),
                    timestamp(self.end.date_time),
                )
            if right <= left:
                raise ValueError("Event end must be after its start")
        if self.attendees is not None:
            self.attendees = list(
                dict.fromkeys(address(value) for value in self.attendees)
            )
        return self

    def payload(self):
        result = self.model_dump(
            exclude_none=True, exclude={"start", "end", "attendees"}
        )
        if self.start is not None and self.end is not None:
            result.update(start=self.start.payload(), end=self.end.payload())
        if self.attendees is not None:
            result["attendees"] = [{"email": address} for address in self.attendees]
        return result


class TaskFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=1024)
    notes: str | None = Field(default=None, max_length=8192)
    status: Literal["needsAction", "completed"] | None = None
    due_date: str | None = Field(default=None, max_length=10)
    clear_due_date: bool = False

    @model_validator(mode="after")
    def check(self):
        if self.due_date:
            date.fromisoformat(self.due_date)
        if self.due_date is not None and self.clear_due_date:
            raise ValueError("Choose due_date or clear_due_date")
        return self

    def payload(self):
        result = self.model_dump(
            exclude_none=True, exclude={"due_date", "clear_due_date"}
        )
        if self.due_date:
            result["due"] = self.due_date + "T00:00:00.000Z"
        if self.clear_due_date:
            result["due"] = None
        return result


def _access(product: str) -> dict[str, str]:
    from purecipher.consumer_oauth import load_grant, validate_connection_grant
    from purecipher.consumer_runtime import (
        _ACCESS,
        access,
        current_profile_client,
        runtime_ready,
    )
    from purecipher.workspace import allowed_profile_tools

    headers = access(product)
    context = _ACCESS.get() or {}
    registry = context.get("registry")
    if registry is not None:
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
        grant = load_grant(registry, connection) or {}
        validate_connection_grant(
            registry, connection, grant, tool_name=context["tool_name"]
        )
    return headers


async def request(
    product: str,
    method: str,
    path: str,
    *,
    params=None,
    body=None,
    etag: str = "",
    content: bytes | None = None,
    content_type: str = "",
    upload: bool = False,
    binary: bool = False,
    read_only: bool = False,
) -> dict:
    headers = dict(_access(product))
    if etag:
        headers["If-Match"] = header(etag)
    if content_type:
        headers["Content-Type"] = content_type
    base = UPLOAD_BASE if upload and product == "google-drive" else BASES[product]
    limit = MAX_FILE_BYTES if binary else MAX_RESPONSE_BYTES
    mutation = method != "GET" and not read_only
    uncertain = "Google request outcome is unknown. Check the resource before retrying to avoid duplicate changes"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream(
                method,
                base + path,
                headers=headers,
                params=params,
                content=content,
                json=body if content is None else None,
            ) as response:
                if not 200 <= response.status_code < 300:
                    if response.status_code == 412:
                        raise ValueError(
                            "This resource changed; get its latest version before retrying"
                        )
                    if mutation and response.status_code >= 500:
                        raise ValueError(uncertain)
                    raise ValueError(
                        f"Google request failed ({response.status_code}); check permissions and resource IDs"
                    )
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > limit:
                        raise ValueError(
                            uncertain
                            if mutation
                            else "Google response exceeds the size limit; use a smaller file or page"
                        )
                    data.extend(chunk)
                if binary:
                    return {
                        "data_base64": base64.b64encode(data).decode(),
                        "size_bytes": len(data),
                        "mime_type": response.headers.get(
                            "content-type", "application/octet-stream"
                        ),
                    }
                if not data:
                    return {"deleted": True} if method == "DELETE" else {}
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError(
                        uncertain
                        if mutation
                        else "Google returned an unexpected response"
                    )
                return result
    except httpx.HTTPError:
        if not mutation:
            raise ValueError(
                "Google is unavailable; retry or reconnect your account"
            ) from None
        raise ValueError(uncertain) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError(
            uncertain if mutation else "Google returned an invalid response"
        ) from None


def decode_file(value: str) -> bytes:
    if len(value) > ((MAX_FILE_BYTES + 2) // 3) * 4:
        raise ValueError("File exceeds the 5 MiB limit")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("File content must be valid standard base64") from None
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 5 MiB limit")
    return data


def mime(value: str) -> str:
    if len(value) > 120 or not re.fullmatch(
        r"[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+", value
    ):
        raise ValueError("Use a valid MIME type without parameters")
    return value


def multipart(metadata: dict, data: bytes, mime_type: str) -> tuple[bytes, str]:
    mime(mime_type)
    boundary = "purecipher_" + secrets.token_hex(16)
    # Random boundary, but still reject a collision in supplied content.
    while boundary.encode() in data:
        boundary = "purecipher_" + secrets.token_hex(16)
    content = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + json.dumps(metadata).encode()
        + f"\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n".encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return content, "multipart/related; boundary=" + boundary


async def document_edit(
    document_id: str, operation: dict, required_revision_id: str
) -> dict:
    if not required_revision_id or len(required_revision_id) > 2048:
        raise ValueError(
            "Use the revisionId from docs_get_document before changing text"
        )
    return await request(
        "google-docs",
        "POST",
        "/documents/" + identifier(document_id) + ":batchUpdate",
        body={
            "requests": [operation],
            "writeControl": {"requiredRevisionId": required_revision_id},
        },
    )


def text_range(start_index: int, end_index: int, tab_id: str) -> dict:
    if not 1 <= start_index < end_index <= 2147483647:
        raise ValueError("Text range must have an end index after its start")
    return {
        "startIndex": start_index,
        "endIndex": end_index,
        **({"tabId": identifier(tab_id)} if tab_id else {}),
    }


def register(registry: Any) -> None:
    registry._consumer_products |= set(BASES)

    def tool(
        product: str,
        *,
        read_only: bool = True,
        destructive: bool = False,
        idempotent: bool = True,
    ):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = product
            registry.tool(
                annotations={
                    "readOnlyHint": read_only,
                    "destructiveHint": destructive,
                    "idempotentHint": idempotent,
                    "openWorldHint": True,
                },
                tags={
                    "resource:"
                    + {
                        "google-docs": "documents",
                        "google-tasks": "tasks",
                        "google-calendar": "calendar",
                        "google-drive": "files",
                    }[product],
                    "risk:low" if read_only else "risk:high",
                },
            )(fn)
            return fn

        return decorate

    @tool("google-docs")
    async def docs_get_document(
        document_id: str, include_tabs_content: bool = False
    ) -> dict:
        """Read a Google document. Keep revisionId for text edits; enable include_tabs_content for all document tabs."""
        return await request(
            "google-docs",
            "GET",
            "/documents/" + identifier(document_id),
            params={"includeTabsContent": include_tabs_content},
        )

    @tool("google-docs", read_only=False, idempotent=False)
    async def docs_create_document(title: ShortText) -> dict:
        """Create an empty Google document owned by the authorized user."""
        return await request("google-docs", "POST", "/documents", body={"title": title})

    @tool("google-docs", read_only=False, idempotent=False)
    async def docs_insert_text(
        document_id: str,
        text: Text,
        required_revision_id: str,
        index: Index = 1,
        tab_id: str = "",
    ) -> dict:
        """Insert text at a UTF-16 index using the exact revisionId from docs_get_document."""
        return await document_edit(
            document_id,
            {
                "insertText": {
                    "text": text,
                    "location": {
                        "index": index,
                        **({"tabId": identifier(tab_id)} if tab_id else {}),
                    },
                }
            },
            required_revision_id,
        )

    @tool("google-docs", read_only=False, idempotent=False)
    async def docs_append_text(
        document_id: str, text: Text, required_revision_id: str, tab_id: str = ""
    ) -> dict:
        """Append text to the selected document tab, guarded by its document revision."""
        return await document_edit(
            document_id,
            {
                "insertText": {
                    "text": text,
                    "endOfSegmentLocation": {
                        **({"tabId": identifier(tab_id)} if tab_id else {})
                    },
                }
            },
            required_revision_id,
        )

    @tool("google-docs", read_only=False, destructive=True)
    async def docs_replace_text(
        document_id: str,
        contains_text: ShortText,
        replacement: Text,
        required_revision_id: str,
        match_case: bool = True,
        tab_ids: list[str] | None = None,
    ) -> dict:
        """Replace every matching text occurrence. Omitted tab_ids applies to all tabs. Requires the current document revision."""
        if tab_ids is not None and not 1 <= len(tab_ids) <= 100:
            raise ValueError("Choose between 1 and 100 document tabs")
        operation = {
            "containsText": {"text": contains_text, "matchCase": match_case},
            "replaceText": replacement,
        }
        if tab_ids:
            operation["tabsCriteria"] = {
                "tabIds": [identifier(value) for value in tab_ids]
            }
        return await document_edit(
            document_id, {"replaceAllText": operation}, required_revision_id
        )

    @tool("google-docs", read_only=False, destructive=True)
    async def docs_delete_text(
        document_id: str,
        start_index: Index,
        end_index: Index,
        required_revision_id: str,
        tab_id: str = "",
    ) -> dict:
        """Delete a UTF-16 text range at a known document revision. Google rejects structurally invalid deletions."""
        return await document_edit(
            document_id,
            {
                "deleteContentRange": {
                    "range": text_range(start_index, end_index, tab_id)
                }
            },
            required_revision_id,
        )

    @tool("google-docs", read_only=False)
    async def docs_format_text(
        document_id: str,
        start_index: Index,
        end_index: Index,
        required_revision_id: str,
        bold: bool | None = None,
        italic: bool | None = None,
        font_size_points: Annotated[float, Field(ge=1, le=400)] | None = None,
        tab_id: str = "",
    ) -> dict:
        """Change bold, italic or font size on an exact text range, guarded by document revision."""
        style: dict[str, Any] = {
            key: value
            for key, value in {"bold": bold, "italic": italic}.items()
            if value is not None
        }
        if font_size_points is not None:
            style["fontSize"] = {"magnitude": font_size_points, "unit": "PT"}
        if not style:
            raise ValueError("Choose at least one text style to change")
        return await document_edit(
            document_id,
            {
                "updateTextStyle": {
                    "range": text_range(start_index, end_index, tab_id),
                    "textStyle": style,
                    "fields": ",".join(style),
                }
            },
            required_revision_id,
        )

    @tool("google-tasks")
    async def tasks_list_tasklists(
        page_token: str = "", max_results: PageSize = 20
    ) -> dict:
        """List the authorized user's task lists; follow nextPageToken for more."""
        return await request(
            "google-tasks",
            "GET",
            "/users/@me/lists",
            params=page(page_token, max_results),
        )

    @tool("google-tasks")
    async def tasks_list_tasks(
        tasklist_id: str,
        page_token: str = "",
        max_results: PageSize = 20,
        show_completed: bool = True,
        show_hidden: bool = False,
        show_deleted: bool = False,
    ) -> dict:
        """Read tasks from one task list. Enable show_hidden to include previously cleared completed tasks."""
        return await request(
            "google-tasks",
            "GET",
            "/lists/" + identifier(tasklist_id) + "/tasks",
            params={
                **page(page_token, max_results),
                "showCompleted": show_completed,
                "showHidden": show_hidden,
                "showDeleted": show_deleted,
            },
        )

    @tool("google-tasks")
    async def tasks_get_tasklist(tasklist_id: str) -> dict:
        """Read one task list's title and metadata."""
        return await request(
            "google-tasks", "GET", "/users/@me/lists/" + identifier(tasklist_id)
        )

    @tool("google-tasks", read_only=False, idempotent=False)
    async def tasks_create_tasklist(title: ShortText) -> dict:
        """Create a task list for the authorized user."""
        return await request(
            "google-tasks", "POST", "/users/@me/lists", body={"title": title}
        )

    @tool("google-tasks", read_only=False)
    async def tasks_update_tasklist(tasklist_id: str, title: ShortText) -> dict:
        """Rename a task list. Concurrent title edits use Google's last-write behavior."""
        return await request(
            "google-tasks",
            "PATCH",
            "/users/@me/lists/" + identifier(tasklist_id),
            body={"title": title},
        )

    @tool("google-tasks", read_only=False, destructive=True)
    async def tasks_delete_tasklist(tasklist_id: str, confirm_delete: bool) -> dict:
        """Permanently delete a task list and its tasks. confirm_delete must be true."""
        if not confirm_delete:
            raise ValueError("Confirm deletion of the task list and its tasks")
        return await request(
            "google-tasks", "DELETE", "/users/@me/lists/" + identifier(tasklist_id)
        )

    @tool("google-tasks")
    async def tasks_get_task(tasklist_id: str, task_id: str) -> dict:
        """Read one task's title, notes, status and date."""
        return await request(
            "google-tasks",
            "GET",
            "/lists/" + identifier(tasklist_id) + "/tasks/" + identifier(task_id),
        )

    @tool("google-tasks", read_only=False, idempotent=False)
    async def tasks_create_task(
        tasklist_id: str, task: TaskFields, parent_id: str = "", previous_id: str = ""
    ) -> dict:
        """Create a task; due_date is a date only, not a time. Optional parent and previous IDs set its location."""
        if not task.title:
            raise ValueError("A new task needs a title")
        params = {
            k: identifier(v)
            for k, v in {"parent": parent_id, "previous": previous_id}.items()
            if v
        }
        return await request(
            "google-tasks",
            "POST",
            "/lists/" + identifier(tasklist_id) + "/tasks",
            params=params,
            body=task.payload(),
        )

    @tool("google-tasks", read_only=False, destructive=True)
    async def tasks_update_task(
        tasklist_id: str, task_id: str, changes: TaskFields
    ) -> dict:
        """Edit supplied task fields, or complete/reopen a task using status. Unspecified fields remain unchanged."""
        body = changes.payload()
        if not body:
            raise ValueError("Choose at least one task field to change")
        return await request(
            "google-tasks",
            "PATCH",
            "/lists/" + identifier(tasklist_id) + "/tasks/" + identifier(task_id),
            body=body,
        )

    @tool("google-tasks", read_only=False, destructive=True)
    async def tasks_delete_task(
        tasklist_id: str, task_id: str, confirm_delete: bool
    ) -> dict:
        """Delete a task. For an assigned task Google also deletes its original in Docs or Chat; confirm_delete must be true."""
        if not confirm_delete:
            raise ValueError(
                "Confirm deletion of the task, including its assignment source if applicable"
            )
        return await request(
            "google-tasks",
            "DELETE",
            "/lists/" + identifier(tasklist_id) + "/tasks/" + identifier(task_id),
        )

    @tool("google-tasks", read_only=False)
    async def tasks_move_task(
        tasklist_id: str, task_id: str, parent_id: str = "", previous_id: str = ""
    ) -> dict:
        """Move a task within its list. Empty parent moves to top level; empty previous moves to first position."""
        params = {
            k: identifier(v)
            for k, v in {"parent": parent_id, "previous": previous_id}.items()
            if v
        }
        return await request(
            "google-tasks",
            "POST",
            "/lists/"
            + identifier(tasklist_id)
            + "/tasks/"
            + identifier(task_id)
            + "/move",
            params=params,
        )

    @tool("google-tasks", read_only=False, destructive=True)
    async def tasks_clear_completed(tasklist_id: str, confirm_clear: bool) -> dict:
        """Clear completed tasks from the visible list. Cleared tasks remain retrievable with show_hidden=true."""
        if not confirm_clear:
            raise ValueError("Confirm clearing all completed tasks in this list")
        return await request(
            "google-tasks", "POST", "/lists/" + identifier(tasklist_id) + "/clear"
        )

    @tool("google-calendar")
    async def calendar_list_calendars(
        page_token: str = "", max_results: PageSize = 20
    ) -> dict:
        """List calendars on the authorized user's calendar list."""
        return await request(
            "google-calendar",
            "GET",
            "/users/me/calendarList",
            params=page(page_token, max_results),
        )

    @tool("google-calendar")
    async def calendar_list_events(
        calendar_id: str = "primary",
        page_token: str = "",
        max_results: PageSize = 20,
        query: str = "",
        time_min: str = "",
        time_max: str = "",
        single_events: bool = False,
        show_deleted: bool = False,
    ) -> dict:
        """List/search events, optionally bounded by RFC3339 times. single_events expands recurring events."""
        if len(query) > 4000:
            raise ValueError("Search query is too long")
        params = {
            **page(page_token, max_results),
            "singleEvents": single_events,
            "showDeleted": show_deleted,
        }
        for key, value in {"timeMin": time_min, "timeMax": time_max}.items():
            if value:
                timestamp(value)
                params[key] = value
        if time_min and time_max and timestamp(time_min) >= timestamp(time_max):
            raise ValueError("time_max must be after time_min")
        if query:
            params["q"] = query
        return await request(
            "google-calendar",
            "GET",
            "/calendars/" + identifier(calendar_id) + "/events",
            params=params,
        )

    @tool("google-calendar")
    async def calendar_get_calendar(calendar_id: str = "primary") -> dict:
        """Read a calendar's metadata and ETag for conditional updates."""
        return await request(
            "google-calendar", "GET", "/calendars/" + identifier(calendar_id)
        )

    @tool("google-calendar")
    async def calendar_get_event(event_id: str, calendar_id: str = "primary") -> dict:
        """Read an event, its attendees and ETag. Use this ETag when updating or deleting it."""
        return await request(
            "google-calendar",
            "GET",
            "/calendars/" + identifier(calendar_id) + "/events/" + identifier(event_id),
        )

    @tool("google-calendar")
    async def calendar_list_event_instances(
        event_id: str,
        calendar_id: str = "primary",
        page_token: str = "",
        max_results: PageSize = 20,
    ) -> dict:
        """Expand instances of one recurring event; follow nextPageToken for more."""
        return await request(
            "google-calendar",
            "GET",
            "/calendars/"
            + identifier(calendar_id)
            + "/events/"
            + identifier(event_id)
            + "/instances",
            params=page(page_token, max_results),
        )

    @tool("google-calendar")
    async def calendar_free_busy(
        calendar_ids: Annotated[list[str], Field(min_length=1, max_length=50)],
        time_min: str,
        time_max: str,
    ) -> dict:
        """Read busy periods for up to 50 calendars within a bounded time window; creates no events."""
        if timestamp(time_max) <= timestamp(time_min):
            raise ValueError("time_max must be after time_min")
        for calendar_id in calendar_ids:
            identifier(calendar_id)
        return await request(
            "google-calendar",
            "POST",
            "/freeBusy",
            read_only=True,
            body={
                "timeMin": time_min,
                "timeMax": time_max,
                "calendarExpansionMax": 50,
                "items": [{"id": value} for value in calendar_ids],
            },
        )

    @tool("google-calendar", read_only=False, idempotent=False)
    async def calendar_create_event(
        event: EventFields, send_updates: SendUpdates, calendar_id: str = "primary"
    ) -> dict:
        """Create an event. Choose send_updates explicitly: all, externalOnly or none. Attendees may receive Google email; none can impair external calendar sync."""
        if event.start is None or event.end is None:
            raise ValueError("A new event requires start and end")
        return await request(
            "google-calendar",
            "POST",
            "/calendars/" + identifier(calendar_id) + "/events",
            params={"sendUpdates": send_updates},
            body=event.payload(),
        )

    @tool("google-calendar", read_only=False, destructive=True)
    async def calendar_update_event(
        event_id: str,
        changes: EventFields,
        etag: str,
        send_updates: SendUpdates,
        calendar_id: str = "primary",
    ) -> dict:
        """Patch supplied event fields at an exact ETag. Attendees replace the full list. Choose notification behavior explicitly; Google may still send some emails."""
        body = changes.payload()
        if not body:
            raise ValueError("Choose at least one event field to change")
        return await request(
            "google-calendar",
            "PATCH",
            "/calendars/" + identifier(calendar_id) + "/events/" + identifier(event_id),
            params={"sendUpdates": send_updates},
            body=body,
            etag=header(etag),
        )

    @tool("google-calendar", read_only=False, destructive=True)
    async def calendar_delete_event(
        event_id: str,
        etag: str,
        send_updates: SendUpdates,
        confirm_delete: bool,
        calendar_id: str = "primary",
    ) -> dict:
        """Delete an event at an exact ETag. A recurring series ID deletes the series; choose notifications and confirm_delete explicitly."""
        if not confirm_delete:
            raise ValueError("Confirm deleting this event or recurring series")
        return await request(
            "google-calendar",
            "DELETE",
            "/calendars/" + identifier(calendar_id) + "/events/" + identifier(event_id),
            params={"sendUpdates": send_updates},
            etag=header(etag),
        )

    @tool("google-calendar", read_only=False, destructive=True)
    async def calendar_move_event(
        event_id: str,
        destination_calendar_id: str,
        send_updates: SendUpdates,
        calendar_id: str = "primary",
    ) -> dict:
        """Move a default event to another calendar, changing its organizer. Choose attendee notification behavior explicitly."""
        identifier(destination_calendar_id)
        return await request(
            "google-calendar",
            "POST",
            "/calendars/"
            + identifier(calendar_id)
            + "/events/"
            + identifier(event_id)
            + "/move",
            params={
                "destination": destination_calendar_id,
                "sendUpdates": send_updates,
            },
        )

    @tool("google-calendar", read_only=False, idempotent=False)
    async def calendar_create_calendar(
        summary: ShortText,
        time_zone: str,
        description: Annotated[str, Field(max_length=8192)] = "",
    ) -> dict:
        """Create a secondary calendar. This does not share the calendar or change its access list."""
        return await request(
            "google-calendar",
            "POST",
            "/calendars",
            body={
                "summary": summary,
                "timeZone": timezone_name(time_zone),
                "description": description,
            },
        )

    @tool("google-calendar", read_only=False)
    async def calendar_update_calendar(
        calendar_id: str,
        etag: str,
        summary: ShortText | None = None,
        description: Annotated[str, Field(max_length=8192)] | None = None,
        time_zone: str | None = None,
    ) -> dict:
        """Update supplied calendar metadata at an exact ETag; access permissions are unchanged."""
        body = {
            k: v
            for k, v in {
                "summary": summary,
                "description": description,
                "timeZone": timezone_name(time_zone) if time_zone is not None else None,
            }.items()
            if v is not None
        }
        if not body:
            raise ValueError("Choose at least one calendar field to change")
        return await request(
            "google-calendar",
            "PATCH",
            "/calendars/" + identifier(calendar_id),
            body=body,
            etag=header(etag),
        )

    @tool("google-calendar", read_only=False, destructive=True)
    async def calendar_delete_calendar(
        calendar_id: str, etag: str, confirm_delete: bool
    ) -> dict:
        """Permanently delete a secondary calendar and all its events at an exact ETag. Primary calendars cannot be deleted."""
        if not confirm_delete or calendar_id == "primary":
            raise ValueError("Confirm deletion of a secondary calendar and its events")
        return await request(
            "google-calendar",
            "DELETE",
            "/calendars/" + identifier(calendar_id),
            etag=header(etag),
        )

    @tool("google-drive")
    async def drive_search_files(
        query: str = "", page_token: str = "", max_results: PageSize = 20
    ) -> dict:
        """Search file metadata using Drive query syntax. Returns no file content; follow nextPageToken for more."""
        if len(query) > 4000:
            raise ValueError("Search query is too long")
        params = {
            "pageSize": max_results,
            "fields": "nextPageToken,incompleteSearch,files(" + FILE_FIELDS + ")",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        checked = page(page_token, max_results)
        if page_token:
            params["pageToken"] = checked["pageToken"]
        if query:
            params["q"] = query
        return await request("google-drive", "GET", "/files", params=params)

    @tool("google-drive")
    async def drive_get_file(file_id: str) -> dict:
        """Read file metadata, including parents and capabilities; this does not download content."""
        return await request(
            "google-drive",
            "GET",
            "/files/" + identifier(file_id),
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
        )

    @tool("google-drive")
    async def drive_list_folder_files(
        folder_id: str, page_token: str = "", max_results: PageSize = 20
    ) -> dict:
        """Read non-trashed files directly inside a folder; does not recursively crawl child folders."""
        identifier(folder_id)
        escaped = folder_id.replace("\\", "\\\\").replace("'", "\\'")
        params = {
            "q": "'" + escaped + "' in parents and trashed = false",
            "pageSize": max_results,
            "fields": "nextPageToken,incompleteSearch,files(" + FILE_FIELDS + ")",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        checked = page(page_token, max_results)
        if page_token:
            params["pageToken"] = checked["pageToken"]
        return await request("google-drive", "GET", "/files", params=params)

    @tool("google-drive")
    async def drive_list_revisions(
        file_id: str, page_token: str = "", max_results: PageSize = 20
    ) -> dict:
        """List available file revision metadata. Google may omit older revisions; this does not download content."""
        checked = page(page_token, max_results)
        params = {
            "pageSize": max_results,
            "fields": "nextPageToken,revisions(id,mimeType,modifiedTime,keepForever,size)",
        }
        if page_token:
            params["pageToken"] = checked["pageToken"]
        return await request(
            "google-drive",
            "GET",
            "/files/" + identifier(file_id) + "/revisions",
            params=params,
        )

    @tool("google-drive")
    async def drive_download_file(file_id: str) -> dict:
        """Download a stored binary file as base64, limited to 5 MiB. Use drive_export_file for Google Workspace documents."""
        return await request(
            "google-drive",
            "GET",
            "/files/" + identifier(file_id),
            params={"alt": "media", "supportsAllDrives": True},
            binary=True,
        )

    @tool("google-drive")
    async def drive_export_file(
        file_id: str, mime_type: ExportMime = "application/pdf"
    ) -> dict:
        """Export a Google Workspace file to a supported MIME type as base64, limited to 5 MiB; format must match the source type."""
        return await request(
            "google-drive",
            "GET",
            "/files/" + identifier(file_id) + "/export",
            params={"mimeType": mime_type},
            binary=True,
        )

    @tool("google-drive", read_only=False, idempotent=False)
    async def drive_create_file(
        name: ShortText,
        content_base64: str,
        mime_type: str = "application/octet-stream",
        parent_id: str = "",
    ) -> dict:
        """Upload a new file from standard base64, limited to 5 MiB. No URLs or local paths are read."""
        metadata = {"name": name}
        if parent_id:
            identifier(parent_id)
            metadata["parents"] = [parent_id]
        content, content_type = multipart(
            metadata, decode_file(content_base64), mime_type
        )
        return await request(
            "google-drive",
            "POST",
            "/files",
            params={
                "uploadType": "multipart",
                "fields": FILE_FIELDS,
                "supportsAllDrives": True,
            },
            upload=True,
            content=content,
            content_type=content_type,
        )

    @tool("google-drive", read_only=False, idempotent=False)
    async def drive_create_folder(name: ShortText, parent_id: str = "") -> dict:
        """Create a folder in My Drive or the specified parent folder. Sharing is inherited from Google Drive."""
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            identifier(parent_id)
            body["parents"] = [parent_id]
        return await request(
            "google-drive",
            "POST",
            "/files",
            body=body,
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
        )

    @tool("google-drive", read_only=False, destructive=True)
    async def drive_update_file_content(
        file_id: str, content_base64: str, mime_type: str = "application/octet-stream"
    ) -> dict:
        """Replace a stored file's content with up to 5 MiB of base64 data. Creates a Google Drive revision; concurrent writes are not guarded."""
        content, content_type = multipart({}, decode_file(content_base64), mime_type)
        return await request(
            "google-drive",
            "PATCH",
            "/files/" + identifier(file_id),
            params={
                "uploadType": "multipart",
                "fields": FILE_FIELDS,
                "supportsAllDrives": True,
            },
            upload=True,
            content=content,
            content_type=content_type,
        )

    @tool("google-drive", read_only=False)
    async def drive_update_file_metadata(
        file_id: str,
        name: ShortText | None = None,
        description: Annotated[str, Field(max_length=16384)] | None = None,
    ) -> dict:
        """Rename a file or update its description, leaving other metadata unchanged."""
        body = {
            k: v
            for k, v in {"name": name, "description": description}.items()
            if v is not None
        }
        if not body:
            raise ValueError("Choose a name or description to change")
        return await request(
            "google-drive",
            "PATCH",
            "/files/" + identifier(file_id),
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
            body=body,
        )

    @tool("google-drive", read_only=False, destructive=True)
    async def drive_move_file(
        file_id: str,
        destination_folder_id: str,
        remove_parent_ids: Annotated[list[str], Field(max_length=20)],
    ) -> dict:
        """Move a file by adding a destination and removing explicitly supplied current parent IDs. Folder permissions may change its effective access."""
        identifier(destination_folder_id)
        for parent_id in remove_parent_ids:
            identifier(parent_id)
            if "," in parent_id or parent_id == destination_folder_id:
                raise ValueError("Invalid or overlapping parent IDs")
        if "," in destination_folder_id:
            raise ValueError("Choose one destination folder")
        return await request(
            "google-drive",
            "PATCH",
            "/files/" + identifier(file_id),
            params={
                "addParents": destination_folder_id,
                "removeParents": ",".join(remove_parent_ids),
                "fields": FILE_FIELDS,
                "supportsAllDrives": True,
            },
            body={},
        )

    @tool("google-drive", read_only=False, idempotent=False)
    async def drive_copy_file(
        file_id: str, name: ShortText, parent_id: str = ""
    ) -> dict:
        """Copy a file with a new name, optionally into a specified folder. Google Drive folder permissions apply."""
        body = {"name": name}
        if parent_id:
            identifier(parent_id)
            body["parents"] = [parent_id]
        return await request(
            "google-drive",
            "POST",
            "/files/" + identifier(file_id) + "/copy",
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
            body=body,
        )

    @tool("google-drive", read_only=False, destructive=True)
    async def drive_trash_file(file_id: str) -> dict:
        """Move a file or folder to trash. Other users can lose access; use restore to undo when allowed."""
        return await request(
            "google-drive",
            "PATCH",
            "/files/" + identifier(file_id),
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
            body={"trashed": True},
        )

    @tool("google-drive", read_only=False)
    async def drive_restore_file(file_id: str) -> dict:
        """Restore a file or folder from trash when the authorized account has permission."""
        return await request(
            "google-drive",
            "PATCH",
            "/files/" + identifier(file_id),
            params={"fields": FILE_FIELDS, "supportsAllDrives": True},
            body={"trashed": False},
        )

    @tool("google-drive", read_only=False, destructive=True)
    async def drive_delete_file(file_id: str, confirm_permanent_delete: bool) -> dict:
        """Permanently delete a file without moving it to trash. Folder deletion also deletes owned descendants; explicit confirmation is required."""
        if not confirm_permanent_delete:
            raise ValueError("Confirm permanent deletion; this cannot be undone")
        return await request(
            "google-drive",
            "DELETE",
            "/files/" + identifier(file_id),
            params={"supportsAllDrives": True},
        )
