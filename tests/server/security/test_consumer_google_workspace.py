"""Google Workspace contracts over local MCP and mocked provider HTTP only."""

import base64
import json
from collections import Counter
from email import policy
from email.parser import BytesParser
from typing import Any

import httpx
import pytest

from fastmcp import Client, FastMCP
from purecipher import consumer_google_workspace as google
from purecipher import consumer_runtime
from purecipher.consumer_google_permissions import (
    CALENDAR_ADMIN_TOOLS,
    DRIVE_CONTENT_TOOLS,
    GOOGLE_READ_TOOLS,
    GOOGLE_WRITE_TOOLS,
)

TOKEN = "private-workspace-fixture-token"
EVENT = {
    "summary": "Review",
    "start": {"date_time": "2026-09-07T10:00:00+00:00"},
    "end": {"date_time": "2026-09-07T11:00:00+00:00"},
    "attendees": ["person@example.test"],
}
CASES = [
    ("docs_get_document", {"document_id": "doc1"}, "GET", "/documents/doc1"),
    ("docs_create_document", {"title": "Plan"}, "POST", "/documents"),
    (
        "docs_insert_text",
        {"document_id": "doc1", "text": "Hello", "required_revision_id": "rev1"},
        "POST",
        "/documents/doc1:batchUpdate",
    ),
    (
        "docs_append_text",
        {"document_id": "doc1", "text": "Hello", "required_revision_id": "rev1"},
        "POST",
        "/documents/doc1:batchUpdate",
    ),
    (
        "docs_replace_text",
        {
            "document_id": "doc1",
            "contains_text": "Hello",
            "replacement": "Goodbye",
            "required_revision_id": "rev1",
        },
        "POST",
        "/documents/doc1:batchUpdate",
    ),
    (
        "docs_delete_text",
        {
            "document_id": "doc1",
            "start_index": 1,
            "end_index": 3,
            "required_revision_id": "rev1",
        },
        "POST",
        "/documents/doc1:batchUpdate",
    ),
    (
        "docs_format_text",
        {
            "document_id": "doc1",
            "start_index": 1,
            "end_index": 3,
            "bold": True,
            "required_revision_id": "rev1",
        },
        "POST",
        "/documents/doc1:batchUpdate",
    ),
    ("tasks_list_tasklists", {}, "GET", "/users/@me/lists"),
    ("tasks_list_tasks", {"tasklist_id": "list1"}, "GET", "/lists/list1/tasks"),
    ("tasks_get_tasklist", {"tasklist_id": "list1"}, "GET", "/users/@me/lists/list1"),
    ("tasks_create_tasklist", {"title": "Plan"}, "POST", "/users/@me/lists"),
    (
        "tasks_update_tasklist",
        {"tasklist_id": "list1", "title": "Plan"},
        "PATCH",
        "/users/@me/lists/list1",
    ),
    (
        "tasks_delete_tasklist",
        {"tasklist_id": "list1", "confirm_delete": True},
        "DELETE",
        "/users/@me/lists/list1",
    ),
    (
        "tasks_get_task",
        {"tasklist_id": "list1", "task_id": "task1"},
        "GET",
        "/lists/list1/tasks/task1",
    ),
    (
        "tasks_create_task",
        {"tasklist_id": "list1", "task": {"title": "Read", "due_date": "2026-09-08"}},
        "POST",
        "/lists/list1/tasks",
    ),
    (
        "tasks_update_task",
        {
            "tasklist_id": "list1",
            "task_id": "task1",
            "changes": {"status": "completed"},
        },
        "PATCH",
        "/lists/list1/tasks/task1",
    ),
    (
        "tasks_delete_task",
        {"tasklist_id": "list1", "task_id": "task1", "confirm_delete": True},
        "DELETE",
        "/lists/list1/tasks/task1",
    ),
    (
        "tasks_move_task",
        {"tasklist_id": "list1", "task_id": "task1", "parent_id": "parent1"},
        "POST",
        "/lists/list1/tasks/task1/move",
    ),
    (
        "tasks_clear_completed",
        {"tasklist_id": "list1", "confirm_clear": True},
        "POST",
        "/lists/list1/clear",
    ),
    ("calendar_list_calendars", {}, "GET", "/users/me/calendarList"),
    ("calendar_list_events", {}, "GET", "/calendars/primary/events"),
    ("calendar_get_calendar", {}, "GET", "/calendars/primary"),
    (
        "calendar_get_event",
        {"event_id": "event1"},
        "GET",
        "/calendars/primary/events/event1",
    ),
    (
        "calendar_list_event_instances",
        {"event_id": "event1"},
        "GET",
        "/calendars/primary/events/event1/instances",
    ),
    (
        "calendar_free_busy",
        {
            "calendar_ids": ["primary"],
            "time_min": "2026-09-07T10:00:00Z",
            "time_max": "2026-09-07T11:00:00Z",
        },
        "POST",
        "/freeBusy",
    ),
    (
        "calendar_create_event",
        {"event": EVENT, "send_updates": "all"},
        "POST",
        "/calendars/primary/events",
    ),
    (
        "calendar_update_event",
        {
            "event_id": "event1",
            "changes": {"summary": "New"},
            "etag": '"etag1"',
            "send_updates": "none",
        },
        "PATCH",
        "/calendars/primary/events/event1",
    ),
    (
        "calendar_delete_event",
        {
            "event_id": "event1",
            "etag": '"etag1"',
            "send_updates": "all",
            "confirm_delete": True,
        },
        "DELETE",
        "/calendars/primary/events/event1",
    ),
    (
        "calendar_move_event",
        {
            "event_id": "event1",
            "destination_calendar_id": "secondary@example.test",
            "send_updates": "all",
        },
        "POST",
        "/calendars/primary/events/event1/move",
    ),
    (
        "calendar_create_calendar",
        {"summary": "Plan", "time_zone": "Europe/London"},
        "POST",
        "/calendars",
    ),
    (
        "calendar_update_calendar",
        {"calendar_id": "secondary", "summary": "Plan", "etag": '"etag1"'},
        "PATCH",
        "/calendars/secondary",
    ),
    (
        "calendar_delete_calendar",
        {"calendar_id": "secondary", "etag": '"etag1"', "confirm_delete": True},
        "DELETE",
        "/calendars/secondary",
    ),
    ("drive_search_files", {}, "GET", "/files"),
    ("drive_get_file", {"file_id": "file1"}, "GET", "/files/file1"),
    ("drive_list_folder_files", {"folder_id": "folder1"}, "GET", "/files"),
    ("drive_list_revisions", {"file_id": "file1"}, "GET", "/files/file1/revisions"),
    ("drive_download_file", {"file_id": "file1"}, "GET", "/files/file1"),
    ("drive_export_file", {"file_id": "file1"}, "GET", "/files/file1/export"),
    (
        "drive_create_file",
        {
            "name": "plan.txt",
            "content_base64": "aGVsbG8=",
            "mime_type": "text/plain",
            "parent_id": "folder1",
        },
        "POST",
        "/files",
    ),
    ("drive_create_folder", {"name": "Plan"}, "POST", "/files"),
    (
        "drive_update_file_content",
        {"file_id": "file1", "content_base64": "aGVsbG8=", "mime_type": "text/plain"},
        "PATCH",
        "/files/file1",
    ),
    (
        "drive_update_file_metadata",
        {"file_id": "file1", "name": "Plan"},
        "PATCH",
        "/files/file1",
    ),
    (
        "drive_move_file",
        {
            "file_id": "file1",
            "destination_folder_id": "folder2",
            "remove_parent_ids": ["folder1"],
        },
        "PATCH",
        "/files/file1",
    ),
    (
        "drive_copy_file",
        {"file_id": "file1", "name": "Plan"},
        "POST",
        "/files/file1/copy",
    ),
    ("drive_trash_file", {"file_id": "file1"}, "PATCH", "/files/file1"),
    ("drive_restore_file", {"file_id": "file1"}, "PATCH", "/files/file1"),
    (
        "drive_delete_file",
        {"file_id": "file1", "confirm_permanent_delete": True},
        "DELETE",
        "/files/file1",
    ),
]


def error_text(result):
    return "\n".join(getattr(item, "text", "") for item in result.content)


class Harness:
    def __init__(self, monkeypatch):
        self.requests = []
        self.options = []
        self.responder = None
        self.server: Any = FastMCP("Google Workspace tests")
        self.server._consumer_products = set()
        self.server._consumer_tool_products = {}
        google.register(self.server)
        original = httpx.AsyncClient

        def client(**kwargs):
            self.options.append(kwargs)
            return original(transport=httpx.MockTransport(self.handle), **kwargs)

        monkeypatch.setattr(google.httpx, "AsyncClient", client)

    def handle(self, request):
        self.requests.append(request)
        assert request.url.host in {
            "docs.googleapis.com",
            "tasks.googleapis.com",
            "www.googleapis.com",
        }
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if self.responder:
            return self.responder(request)
        if request.url.params.get("alt") == "media" or request.url.path.endswith(
            "/export"
        ):
            return httpx.Response(
                200, content=b"hello", headers={"Content-Type": "text/plain"}
            )
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": "fixture-result"})

    async def call(self, name, arguments, *, with_access=True, product=None):
        token = consumer_runtime._ACCESS.set(
            {
                "product": product or self.server._consumer_tool_products[name],
                "headers": {"Authorization": f"Bearer {TOKEN}"},
            }
            if with_access
            else None
        )
        try:
            async with Client(self.server) as client:
                return await client.call_tool(name, arguments, raise_on_error=False)
        finally:
            consumer_runtime._ACCESS.reset(token)


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


@pytest.mark.parametrize(
    "name,args,method,path", CASES, ids=[case[0] for case in CASES]
)
async def test_all_47_tools_use_fixed_provider_methods_and_typed_payloads(
    harness, name, args, method, path
):
    result = await harness.call(name, args)
    assert not result.is_error, error_text(result)
    assert len(harness.requests) == 1
    request = harness.requests[0]
    assert request.method == method
    product = harness.server._consumer_tool_products[name]
    upload = name in {"drive_create_file", "drive_update_file_content"}
    assert (
        str(request.url).split("?")[0]
        == (google.UPLOAD_BASE if upload else google.BASES[product]) + path
    )
    assert TOKEN not in error_text(result)
    assert harness.options[0]["follow_redirects"] is False
    assert harness.options[0]["timeout"] == 20
    if name.startswith("docs_") and name not in {
        "docs_get_document",
        "docs_create_document",
    }:
        body = json.loads(request.content)
        assert body["writeControl"] == {"requiredRevisionId": "rev1"}
        assert len(body["requests"]) == 1
    if name == "tasks_create_task":
        assert json.loads(request.content)["due"] == "2026-09-08T00:00:00.000Z"
    if name == "calendar_create_event":
        assert json.loads(request.content)["attendees"] == [
            {"email": "person@example.test"}
        ]
    if "send_updates" in args:
        assert request.url.params["sendUpdates"] == args["send_updates"]
    if "etag" in args:
        assert request.headers["If-Match"] == args["etag"]
    if upload:
        message = BytesParser(policy=policy.default).parsebytes(
            (
                "Content-Type: "
                + request.headers["Content-Type"]
                + "\r\nMIME-Version: 1.0\r\n\r\n"
            ).encode()
            + request.content
        )
        parts = list(message.iter_parts())
        assert len(parts) == 2 and parts[1].get_payload(decode=True) == b"hello"
        metadata_bytes = parts[0].get_payload(decode=True)
        assert isinstance(metadata_bytes, bytes)
        metadata = json.loads(metadata_bytes)
        assert metadata == (
            {"name": "plan.txt", "parents": ["folder1"]}
            if name == "drive_create_file"
            else {}
        )


async def test_tools_inventory_and_readonly_hints_match_permission_surface(harness):
    async with Client(harness.server) as client:
        tools = await client.list_tools()
    assert len(tools) == 47
    assert Counter(harness.server._consumer_tool_products.values()) == {
        "google-docs": 7,
        "google-tasks": 12,
        "google-calendar": 13,
        "google-drive": 15,
    }
    permitted = set().union(
        *GOOGLE_READ_TOOLS.values(),
        *GOOGLE_WRITE_TOOLS.values(),
        DRIVE_CONTENT_TOOLS,
        CALENDAR_ADMIN_TOOLS,
    )
    assert {item.name for item in tools} == permitted == {case[0] for case in CASES}
    readonly = set().union(*GOOGLE_READ_TOOLS.values(), DRIVE_CONTENT_TOOLS)
    for item in tools:
        assert item.description and item.input_schema["type"] == "object"
        assert item.annotations.read_only_hint == (item.name in readonly)
        assert "Authorization" not in json.dumps(item.input_schema)
        assert "endpoint" not in item.input_schema.get("properties", {})


@pytest.mark.parametrize(
    "name,args,method,path", CASES, ids=[case[0] for case in CASES]
)
async def test_every_tool_denied_without_product_access(
    harness, name, args, method, path
):
    result = await harness.call(name, args, with_access=False)
    assert result.is_error
    assert not harness.requests


@pytest.mark.parametrize(
    "name,args",
    [
        ("docs_get_document", {"document_id": "../private"}),
        (
            "docs_insert_text",
            {"document_id": "doc1", "text": "bad", "required_revision_id": ""},
        ),
        (
            "docs_delete_text",
            {
                "document_id": "doc1",
                "start_index": 3,
                "end_index": 2,
                "required_revision_id": "rev1",
            },
        ),
        ("tasks_list_tasks", {"tasklist_id": "list1", "max_results": 1000}),
        (
            "tasks_create_task",
            {"tasklist_id": "list1", "task": {"title": "bad", "due_date": "tomorrow"}},
        ),
        (
            "tasks_delete_task",
            {"tasklist_id": "list1", "task_id": "task1", "confirm_delete": False},
        ),
        (
            "tasks_update_task",
            {
                "tasklist_id": "list1",
                "task_id": "task1",
                "changes": {"arbitrary": "value"},
            },
        ),
        ("calendar_create_event", {"event": EVENT}),
        ("calendar_create_event", {"event": EVENT, "send_updates": "automatic"}),
        (
            "calendar_create_event",
            {
                "event": {
                    **EVENT,
                    "attendees": ["person@example.test\r\nBcc:hacker@example.test"],
                },
                "send_updates": "all",
            },
        ),
        (
            "calendar_update_event",
            {
                "event_id": "event1",
                "changes": {"summary": "bad"},
                "etag": "*",
                "send_updates": "all",
            },
        ),
        (
            "calendar_delete_calendar",
            {"calendar_id": "primary", "etag": "e1", "confirm_delete": True},
        ),
        ("calendar_create_calendar", {"summary": "Bad", "time_zone": "Not/A_Zone"}),
        ("drive_get_file", {"file_id": "https://attacker.example/file"}),
        ("drive_create_file", {"name": "bad", "content_base64": "invalid base64!"}),
        (
            "drive_create_file",
            {
                "name": "bad",
                "content_base64": "",
                "mime_type": "text/plain\r\nX-Evil:1",
            },
        ),
        ("drive_delete_file", {"file_id": "file1", "confirm_permanent_delete": False}),
    ],
)
async def test_validation_blocks_invalid_or_ambiguous_requests_before_network(
    harness, name, args
):
    result = await harness.call(name, args)
    assert result.is_error
    assert not harness.requests


@pytest.mark.parametrize("status", [301, 401, 403, 404, 412, 429, 500])
async def test_provider_errors_are_redacted_and_never_retried(harness, status):
    harness.responder = lambda request: httpx.Response(
        status, text="SECRET upstream credentials " + TOKEN
    )
    result = await harness.call("docs_create_document", {"title": "Plan"})
    assert result.is_error
    assert len(harness.requests) == 1
    assert "SECRET" not in error_text(result) and TOKEN not in error_text(result)
    if status == 500:
        assert "outcome is unknown" in error_text(result)


async def test_streamed_download_is_bounded(harness, monkeypatch):
    monkeypatch.setattr(google, "MAX_FILE_BYTES", 4)
    result = await harness.call("drive_download_file", {"file_id": "file1"})
    assert result.is_error and "size limit" in error_text(result)
    assert "aGVsbG8=" not in error_text(result)


def test_upload_limit_and_event_model_dates():
    with pytest.raises(ValueError, match="5 MiB"):
        google.decode_file(
            base64.b64encode(b"a" * (google.MAX_FILE_BYTES + 1)).decode()
        )
    for start, end in [("2026-09-07", "2026-09-06"), ("2026-09-07", "2026-09-07")]:
        with pytest.raises(ValueError):
            google.EventFields(start={"date": start}, end={"date": end})
    event = google.EventFields(start={"date": "2026-09-07"}, end={"date": "2026-09-08"})
    assert event.payload()["start"] == {"date": "2026-09-07"}


@pytest.mark.parametrize(
    "name,args",
    [
        ("drive_search_files", {}),
        ("drive_list_folder_files", {"folder_id": "shared-folder"}),
    ],
)
async def test_shared_drive_discovery_and_incomplete_results_are_explicit(
    harness, name, args
):
    harness.responder = lambda request: httpx.Response(
        200, json={"files": [], "incompleteSearch": True, "nextPageToken": "next"}
    )
    result = await harness.call(name, args)
    assert not result.is_error
    assert result.data["incompleteSearch"] is True
    params = harness.requests[-1].url.params
    assert params["supportsAllDrives"] == "true"
    assert params["includeItemsFromAllDrives"] == "true"
    assert "incompleteSearch" in params["fields"]


@pytest.mark.parametrize("failure", ["timeout", "server_error", "invalid_json"])
async def test_free_busy_failures_are_read_only_not_uncertain_mutations(
    harness, failure
):
    def responder(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        return httpx.Response(503 if failure == "server_error" else 200, text=TOKEN)

    harness.responder = responder
    result = await harness.call(
        "calendar_free_busy",
        {
            "calendar_ids": ["primary"],
            "time_min": "2026-09-07T10:00:00Z",
            "time_max": "2026-09-07T11:00:00Z",
        },
    )
    assert result.is_error
    assert "outcome is unknown" not in error_text(result)
    assert TOKEN not in error_text(result)
    assert len(harness.requests) == 1


async def test_oversized_or_invalid_mutation_response_is_uncertain(
    harness, monkeypatch
):
    monkeypatch.setattr(google, "MAX_RESPONSE_BYTES", 10)
    harness.responder = lambda request: httpx.Response(201, text="a" * 20)
    result = await harness.call("docs_create_document", {"title": "Plan"})
    assert result.is_error and "outcome is unknown" in error_text(result)
    assert len(harness.requests) == 1
