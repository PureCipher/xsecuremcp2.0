"""Gmail tool contracts over local MCP and mocked HTTP; no account/network access.

The direct context fixture bypasses profile setup only for these provider unit
tests. Real profile authentication and approval are covered separately.
"""

import base64
import json
from email import policy
from email.parser import BytesParser
from typing import Any

import httpx
import pytest

from fastmcp import Client, FastMCP
from purecipher import consumer_gmail as gmail
from purecipher import consumer_runtime

TOKEN = "private-fixture-token-do-not-return"
MAIL = {"to": ["recipient@example.test"], "subject": "Hello", "body": "Hello there"}
CASES = [
    ("gmail_profile", {}, "GET", "/profile"),
    ("gmail_list_messages", {"query": "is:unread"}, "GET", "/messages"),
    ("gmail_get_message", {"message_id": "m1"}, "GET", "/messages/m1"),
    (
        "gmail_get_attachment",
        {"message_id": "m1", "attachment_id": "a1"},
        "GET",
        "/messages/m1/attachments/a1",
    ),
    ("gmail_list_threads", {"query": "from:sender@example.test"}, "GET", "/threads"),
    ("gmail_get_thread", {"thread_id": "t1"}, "GET", "/threads/t1"),
    ("gmail_list_labels", {}, "GET", "/labels"),
    ("gmail_get_label", {"label_id": "Label_1"}, "GET", "/labels/Label_1"),
    ("gmail_list_drafts", {}, "GET", "/drafts"),
    ("gmail_get_draft", {"draft_id": "d1"}, "GET", "/drafts/d1"),
    ("gmail_list_history", {"start_history_id": "456"}, "GET", "/history"),
    ("gmail_create_draft", {"content": MAIL}, "POST", "/drafts"),
    ("gmail_update_draft", {"draft_id": "d1", "content": MAIL}, "PUT", "/drafts/d1"),
    ("gmail_delete_draft", {"draft_id": "d1"}, "DELETE", "/drafts/d1"),
    ("gmail_send_draft", {"draft_id": "d1"}, "POST", "/drafts/send"),
    ("gmail_send_message", {"content": MAIL}, "POST", "/messages/send"),
    (
        "gmail_reply_message",
        {
            "message_id": "m-source",
            "content": {"to": ["explicit@example.test"], "body": "Reply"},
        },
        "POST",
        "/messages/send",
    ),
    ("gmail_create_label", {"name": "Reviewed"}, "POST", "/labels"),
    (
        "gmail_update_label",
        {"label_id": "Label_1", "name": "Renamed"},
        "PATCH",
        "/labels/Label_1",
    ),
    ("gmail_delete_label", {"label_id": "Label_1"}, "DELETE", "/labels/Label_1"),
    (
        "gmail_modify_message_labels",
        {"message_id": "m1", "remove_label_ids": ["UNREAD"]},
        "POST",
        "/messages/m1/modify",
    ),
    ("gmail_trash_message", {"message_id": "m1"}, "POST", "/messages/m1/trash"),
    ("gmail_untrash_message", {"message_id": "m1"}, "POST", "/messages/m1/untrash"),
    (
        "gmail_modify_thread_labels",
        {"thread_id": "t1", "add_label_ids": ["Label_1"]},
        "POST",
        "/threads/t1/modify",
    ),
    ("gmail_trash_thread", {"thread_id": "t1"}, "POST", "/threads/t1/trash"),
    ("gmail_untrash_thread", {"thread_id": "t1"}, "POST", "/threads/t1/untrash"),
]


def mime_from(request: httpx.Request):
    payload = json.loads(request.content)
    message = payload.get("message", payload)
    raw = base64.urlsafe_b64decode(message["raw"])
    return BytesParser(policy=policy.default).parsebytes(raw)


def error_text(result) -> str:
    return "\n".join(getattr(item, "text", "") for item in result.content)


class GmailHarness:
    def __init__(self, monkeypatch):
        self.requests: list[httpx.Request] = []
        self.options: list[dict[str, Any]] = []
        self.responder = None
        self.server: Any = FastMCP("Gmail provider contract tests")
        self.server._consumer_products = set()
        self.server._consumer_tool_products = {}
        gmail.register(self.server)
        original = httpx.AsyncClient

        def client(**kwargs):
            self.options.append(kwargs)
            return original(transport=httpx.MockTransport(self.handle), **kwargs)

        monkeypatch.setattr(gmail.httpx, "AsyncClient", client)

    def handle(self, request):
        self.requests.append(request)
        assert request.url.host == "gmail.googleapis.com"
        assert request.url.path.startswith("/gmail/v1/users/me/")
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if self.responder:
            result = self.responder(request)
            if result is not None:
                return result
        if request.url.path.endswith("/profile"):
            return httpx.Response(
                200, json={"emailAddress": "owner@example.test", "historyId": "456"}
            )
        if request.url.path.endswith("/messages/m-source"):
            return httpx.Response(
                200,
                json={
                    "id": "m-source",
                    "threadId": "thread-original",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "=?utf-8?b?Q2Fmw6k=?="},
                            {"name": "Message-ID", "value": "<original@example.test>"},
                            {"name": "References", "value": "<earlier@example.test>"},
                            {"name": "To", "value": "not-selected@example.test"},
                        ]
                    },
                },
            )
        return httpx.Response(
            200, json={"id": "fixture-result", "path": request.url.path}
        )

    async def call(self, name, arguments=None, *, with_access=True):
        token = consumer_runtime._ACCESS.set(
            {"product": "google-gmail", "headers": {"Authorization": f"Bearer {TOKEN}"}}
            if with_access
            else None
        )
        try:
            async with Client(self.server) as client:
                return await client.call_tool(
                    name, arguments or {}, raise_on_error=False
                )
        finally:
            consumer_runtime._ACCESS.reset(token)


@pytest.fixture
def harness(monkeypatch):
    return GmailHarness(monkeypatch)


@pytest.mark.parametrize(
    "name,arguments,method,path", CASES, ids=[case[0] for case in CASES]
)
async def test_every_tool_uses_its_fixed_provider_method_and_owner_mailbox(
    harness, name, arguments, method, path
):
    result = await harness.call(name, arguments)
    assert not result.is_error, error_text(result)
    request = harness.requests[-1]
    assert request.method == method
    assert request.url.path == "/gmail/v1/users/me" + path
    assert all(
        options["follow_redirects"] is False and options["timeout"] == 20
        for options in harness.options
    )
    assert TOKEN not in str(result.data)


async def test_discovery_is_complete_and_distinguishes_reads_from_sends(harness):
    async with Client(harness.server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert set(tools) == {case[0] for case in CASES}
    assert len(tools) == 26
    assert tools["gmail_get_message"].annotations.read_only_hint is True
    for name in ("gmail_send_message", "gmail_send_draft", "gmail_reply_message"):
        hints = tools[name].annotations
        assert hints.read_only_hint is False
        assert hints.idempotent_hint is False
        assert hints.destructive_hint is True
    assert not harness.requests


async def test_message_and_thread_pagination_preserves_repeated_labels(harness):
    for name in ("gmail_list_messages", "gmail_list_threads"):
        result = await harness.call(
            name,
            {
                "query": 'subject:"Quarterly update"',
                "page_token": "opaque+/=",
                "max_results": 31,
                "label_ids_filter": ["INBOX", "STARRED"],
                "include_spam_trash": True,
            },
        )
        assert not result.is_error
        params = harness.requests[-1].url.params
        assert params["q"] == 'subject:"Quarterly update"'
        assert params["pageToken"] == "opaque+/="
        assert params["maxResults"] == "31"
        assert params.get_list("labelIds") == ["INBOX", "STARRED"]
        assert params["includeSpamTrash"] == "true"


async def test_metadata_formats_and_history_filters_reach_the_provider(harness):
    result = await harness.call(
        "gmail_get_message",
        {
            "message_id": "m1",
            "format": "metadata",
            "metadata_headers": ["Subject", "From"],
        },
    )
    assert not result.is_error
    assert harness.requests[-1].url.params.get_list("metadataHeaders") == [
        "Subject",
        "From",
    ]
    result = await harness.call("gmail_get_draft", {"draft_id": "d1", "format": "raw"})
    assert not result.is_error
    assert harness.requests[-1].url.params["format"] == "raw"
    result = await harness.call(
        "gmail_list_history",
        {
            "start_history_id": "456",
            "page_token": "history-next",
            "label_id": "INBOX",
            "history_types": ["messageAdded", "labelRemoved"],
        },
    )
    assert not result.is_error
    params = harness.requests[-1].url.params
    assert params["startHistoryId"] == "456"
    assert params["pageToken"] == "history-next"
    assert params["labelId"] == "INBOX"
    assert params.get_list("historyTypes") == ["messageAdded", "labelRemoved"]


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("gmail_get_thread", {"thread_id": "t1", "format": "raw"}),
        (
            "gmail_get_message",
            {"message_id": "m1", "format": "full", "metadata_headers": ["Subject"]},
        ),
        ("gmail_list_messages", {"max_results": 101}),
        ("gmail_list_drafts", {"max_results": 0}),
        ("gmail_list_history", {"start_history_id": "not-a-checkpoint"}),
        (
            "gmail_list_history",
            {"start_history_id": "456", "history_types": ["unknown"]},
        ),
        ("gmail_get_message", {"message_id": "../other-account"}),
        (
            "gmail_get_attachment",
            {"message_id": "m1", "attachment_id": "https://attacker.test/file"},
        ),
    ],
)
async def test_invalid_formats_pagination_and_resource_paths_fail_before_http(
    harness, name, arguments
):
    result = await harness.call(name, arguments)
    assert result.is_error
    assert not harness.requests


async def test_structured_mail_roundtrips_unicode_alternatives_and_attachment(harness):
    attachment = b"fixture attachment\x00\xff"
    result = await harness.call(
        "gmail_send_message",
        {
            "content": {
                "to": ["recipient@example.test"],
                "cc": ["copy@example.test"],
                "bcc": ["private@example.test"],
                "subject": "Résumé ✓",
                "body": "Plain café",
                "html_body": "<p>HTML café</p>",
                "attachments": [
                    {
                        "filename": "résumé.bin",
                        "mime_type": "application/octet-stream",
                        "data_base64": base64.b64encode(attachment).decode(),
                    }
                ],
            }
        },
    )
    assert not result.is_error, error_text(result)
    assert [request.method for request in harness.requests] == ["GET", "POST"]
    message = mime_from(harness.requests[-1])
    assert str(message["From"]) == "owner@example.test"
    assert str(message["To"]) == "recipient@example.test"
    assert str(message["Cc"]) == "copy@example.test"
    assert str(message["Bcc"]) == "private@example.test"
    assert str(message["Subject"]) == "Résumé ✓"
    assert message.get_body(("plain",)).get_content().strip() == "Plain café"
    assert message.get_body(("html",)).get_content().strip() == "<p>HTML café</p>"
    files = list(message.iter_attachments())
    assert len(files) == 1
    assert files[0].get_filename() == "résumé.bin"
    assert files[0].get_payload(decode=True) == attachment


@pytest.mark.parametrize(
    "content",
    [
        {**MAIL, "subject": "Hello\r\nBcc: stolen@example.test"},
        {**MAIL, "to": ["recipient@example.test\nBcc: stolen@example.test"]},
        {
            **MAIL,
            "attachments": [
                {"filename": "report\r\nX-Header: bad", "data_base64": "Zg=="}
            ],
        },
        {
            **MAIL,
            "attachments": [
                {
                    "filename": "report",
                    "mime_type": "text/plain\r\nX: bad",
                    "data_base64": "Zg==",
                }
            ],
        },
        {**MAIL, "attachments": [{"filename": "report", "data_base64": "not base64"}]},
        {**MAIL, "from": "spoofed@example.test"},
    ],
)
async def test_untrusted_headers_and_attachment_inputs_never_send(harness, content):
    result = await harness.call("gmail_send_message", {"content": content})
    assert result.is_error
    assert not any(request.method != "GET" for request in harness.requests)


async def test_attachment_aggregate_bound_prevents_send(harness, monkeypatch):
    assert gmail.MAX_ATTACHMENTS_BYTES == 5 * 1024 * 1024
    # Exercise aggregation through MCP without flooding its debug transport
    # logger with multiple megabytes of fixture arguments.
    monkeypatch.setattr(gmail, "MAX_ATTACHMENTS_BYTES", 64)
    size = gmail.MAX_ATTACHMENTS_BYTES // 2 + 1
    data = base64.b64encode(b"a" * size).decode()
    result = await harness.call(
        "gmail_send_message",
        {
            "content": {
                **MAIL,
                "attachments": [
                    {"filename": "a.bin", "data_base64": data},
                    {"filename": "b.bin", "data_base64": data},
                ],
            }
        },
    )
    assert result.is_error
    assert "5 MiB" in error_text(result)
    assert not any(request.method == "POST" for request in harness.requests)


async def test_reply_derives_thread_headers_but_uses_only_explicit_recipients(harness):
    result = await harness.call(
        "gmail_reply_message",
        {
            "message_id": "m-source",
            "content": {"to": ["explicit@example.test"], "body": "Reply text"},
        },
    )
    assert not result.is_error, error_text(result)
    payload = json.loads(harness.requests[-1].content)
    assert payload["threadId"] == "thread-original"
    message = mime_from(harness.requests[-1])
    assert str(message["Subject"]) == "Café"
    assert str(message["In-Reply-To"]) == "<original@example.test>"
    assert (
        str(message["References"]) == "<earlier@example.test> <original@example.test>"
    )
    assert str(message["To"]) == "explicit@example.test"
    assert message["Cc"] is None and message["Bcc"] is None
    assert "not-selected@example.test" not in message.as_string()


@pytest.mark.parametrize(
    "name,args",
    [
        ("gmail_send_message", {"content": {"body": "No recipients"}}),
        (
            "gmail_reply_message",
            {"message_id": "m-source", "content": {"body": "No recipients"}},
        ),
    ],
)
async def test_sending_never_infers_recipients(harness, name, args):
    result = await harness.call(name, args)
    assert result.is_error
    assert "explicit recipient" in error_text(result)
    assert not any(request.method == "POST" for request in harness.requests)


async def test_invalid_original_thread_headers_prevent_reply(harness):
    harness.responder = lambda request: httpx.Response(
        200,
        json={
            "threadId": "t1",
            "payload": {
                "headers": [
                    {
                        "name": "Message-ID",
                        "value": "<original@example.test>\r\nBcc: attacker@example.test",
                    }
                ]
            },
        },
    )
    result = await harness.call(
        "gmail_reply_message",
        {
            "message_id": "m-source",
            "content": {"to": ["explicit@example.test"], "body": "Reply"},
        },
    )
    assert result.is_error
    assert len(harness.requests) == 1
    assert harness.requests[0].method == "GET"


async def test_draft_update_replaces_content_and_send_keeps_saved_draft(harness):
    result = await harness.call(
        "gmail_update_draft",
        {
            "draft_id": "d1",
            "content": {"subject": "Replacement", "body": "Only the replacement"},
        },
    )
    assert not result.is_error
    request = harness.requests[-1]
    assert request.method == "PUT"
    assert set(json.loads(request.content)) == {"message"}
    message = mime_from(request)
    assert str(message["Subject"]) == "Replacement"
    assert message["To"] is None
    assert list(message.iter_attachments()) == []
    assert [r.url.path for r in harness.requests] == [
        "/gmail/v1/users/me/profile",
        "/gmail/v1/users/me/drafts/d1",
    ]
    harness.requests.clear()
    result = await harness.call("gmail_send_draft", {"draft_id": "d1"})
    assert not result.is_error
    assert len(harness.requests) == 1
    assert json.loads(harness.requests[0].content) == {"id": "d1"}


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("gmail_delete_draft", {"draft_id": "d1"}),
        ("gmail_delete_label", {"label_id": "Label_1"}),
    ],
)
async def test_permanent_draft_and_label_delete_accepts_empty_204(
    harness, name, arguments
):
    harness.responder = lambda request: httpx.Response(204)
    result = await harness.call(name, arguments)
    assert not result.is_error
    assert result.data == {"deleted": True}
    assert harness.requests[0].method == "DELETE"
    assert not harness.requests[0].content


async def test_label_changes_and_patch_preserve_exact_effect(harness):
    result = await harness.call(
        "gmail_modify_message_labels",
        {
            "message_id": "m1",
            "add_label_ids": ["Label_1", "Label_1"],
            "remove_label_ids": ["INBOX", "UNREAD"],
        },
    )
    assert not result.is_error
    assert json.loads(harness.requests[-1].content) == {
        "addLabelIds": ["Label_1"],
        "removeLabelIds": ["INBOX", "UNREAD"],
    }
    result = await harness.call(
        "gmail_update_label",
        {"label_id": "Label_1", "label_list_visibility": "labelHide"},
    )
    assert not result.is_error
    assert harness.requests[-1].method == "PATCH"
    assert json.loads(harness.requests[-1].content) == {
        "labelListVisibility": "labelHide"
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"message_id": "m1"},
        {"message_id": "m1", "add_label_ids": [f"Label_{i}" for i in range(101)]},
        {"message_id": "m1", "add_label_ids": ["INBOX"], "remove_label_ids": ["INBOX"]},
    ],
)
async def test_invalid_label_changes_do_not_call_provider(harness, arguments):
    result = await harness.call("gmail_modify_message_labels", arguments)
    assert result.is_error
    assert not harness.requests


@pytest.mark.parametrize(
    "failure", ["timeout", "502", "503", "redirect", "invalid-json"]
)
async def test_ambiguous_send_is_not_retried_and_provider_secrets_are_scrubbed(
    harness, failure, caplog
):
    def fail(request):
        if not request.url.path.endswith("/messages/send"):
            return None
        if failure == "timeout":
            raise httpx.ReadTimeout(f"upstream failure {TOKEN}", request=request)
        if failure in {"502", "503"}:
            return httpx.Response(int(failure), text=f"upstream private detail {TOKEN}")
        if failure == "redirect":
            return httpx.Response(
                302, headers={"Location": f"https://attacker.test/{TOKEN}"}
            )
        return httpx.Response(200, text=f"invalid response {TOKEN}")

    harness.responder = fail
    result = await harness.call("gmail_send_message", {"content": MAIL})
    assert result.is_error
    assert (
        len([request for request in harness.requests if request.method == "POST"]) == 1
    )
    assert TOKEN not in error_text(result)
    assert TOKEN not in caplog.text
    if failure in {"timeout", "502", "503"}:
        assert "outcome is unknown" in error_text(result)
        assert "Check the mailbox" in error_text(result)


async def test_history_checkpoint_expiry_has_a_recovery_message(harness):
    harness.responder = lambda request: httpx.Response(
        404, text="private upstream body"
    )
    result = await harness.call("gmail_list_history", {"start_history_id": "456"})
    assert result.is_error
    assert "checkpoint expired" in error_text(result)
    assert "private upstream body" not in error_text(result)


async def test_no_direct_provider_access_without_profile_context(harness):
    result = await harness.call("gmail_profile", with_access=False)
    assert result.is_error
    assert "active profile" in error_text(result)
    assert not harness.requests
