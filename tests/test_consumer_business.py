"""Business provider contracts over local MCP; all outbound traffic is mocked."""

import base64
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from fastmcp import Client, FastMCP
from purecipher import consumer_business as business
from purecipher import consumer_runtime
from purecipher.consumer_cloud import BASE_KEYS, CUSTOM, PRODUCTS, headers

TOKEN = "private-provider-secret-never-return"
MAIL = {"subject": "Hello", "body": "Test message", "to": ["a@example.test"]}
EVENT = {
    "subject": "Focus",
    "start": "2026-09-08T10:00:00",
    "end": "2026-09-08T11:00:00",
}

# The operation contract table is independent of implementation registration.
# Every new name must have a provider method/path and valid MCP invocation.
CASES: list[tuple[str, str, dict[str, Any], str, str]] = []
for product, prefix in (("github", "github"), ("github-reference", "github_reference")):
    common = {"owner": "org", "repository": "repo"}
    for suffix, arguments, method, path in [
        ("get_repository", {}, "GET", "/repos/org/repo"),
        ("get_issue", {"issue_number": 12}, "GET", "/repos/org/repo/issues/12"),
        ("list_pull_requests", {"page_number": 2}, "GET", "/repos/org/repo/pulls"),
        ("get_pull_request", {"pull_number": 7}, "GET", "/repos/org/repo/pulls/7"),
        (
            "get_file",
            {"path": "src/main.py", "ref": "feature/new"},
            "GET",
            "/repos/org/repo/contents/src/main.py",
        ),
        (
            "create_issue",
            {"title": "Bug", "body": "Steps"},
            "POST",
            "/repos/org/repo/issues",
        ),
        (
            "update_issue",
            {"issue_number": 12, "state": "closed"},
            "PATCH",
            "/repos/org/repo/issues/12",
        ),
        (
            "add_issue_comment",
            {"issue_number": 12, "body": "Comment"},
            "POST",
            "/repos/org/repo/issues/12/comments",
        ),
    ]:
        CASES.append(
            (product, prefix + "_" + suffix, {**common, **arguments}, method, path)
        )
for product, prefix in (("slack", "slack"), ("slack-archived", "slack_reference")):
    for suffix, arguments, method, path in [
        ("get_channel", {"channel_id": "C1"}, "GET", "conversations.info"),
        ("get_user", {"user_id": "U1"}, "GET", "users.info"),
        (
            "thread_replies",
            {"channel_id": "C1", "thread_ts": "123.456", "cursor": "next"},
            "GET",
            "conversations.replies",
        ),
        (
            "post_message",
            {"channel_id": "C1", "text": "Hi", "thread_ts": "123.456"},
            "POST",
            "chat.postMessage",
        ),
        (
            "update_message",
            {"channel_id": "C1", "message_ts": "123.456", "text": "Edit"},
            "POST",
            "chat.update",
        ),
        (
            "delete_message",
            {"channel_id": "C1", "message_ts": "123.456"},
            "POST",
            "chat.delete",
        ),
    ]:
        CASES.append(
            (product, prefix + "_" + suffix, arguments, method, "/api/" + path)
        )

CASES += [
    (
        "notion",
        "notion_get_data_source",
        {"data_source_id": "d1"},
        "GET",
        "/v1/data_sources/d1",
    ),
    (
        "notion",
        "notion_query_data_source",
        {
            "data_source_id": "d1",
            "filter": {"property": "Done", "checkbox": {"equals": True}},
            "start_cursor": "cursor",
        },
        "POST",
        "/v1/data_sources/d1/query",
    ),
    (
        "notion",
        "notion_create_page",
        {
            "parent_id": "p1",
            "properties": {"title": {"title": [{"text": {"content": "Hello"}}]}},
        },
        "POST",
        "/v1/pages",
    ),
    (
        "notion",
        "notion_update_page_properties",
        {"page_id": "p1", "properties": {"Done": {"checkbox": True}}},
        "PATCH",
        "/v1/pages/p1",
    ),
    (
        "notion",
        "notion_append_paragraphs",
        {"block_id": "p1", "paragraphs": ["First", "Second"]},
        "PATCH",
        "/v1/blocks/p1/children",
    ),
    (
        "notion",
        "notion_set_page_trashed",
        {"page_id": "p1", "in_trash": True},
        "PATCH",
        "/v1/pages/p1",
    ),
    (
        "jira",
        "jira_search_issues",
        {"jql": "project = TEST", "next_page_token": "next"},
        "POST",
        "/rest/api/3/search/jql",
    ),
    (
        "jira",
        "jira_create_issue",
        {
            "project_key": "TEST",
            "issue_type_id": "1",
            "summary": "Bug",
            "description": "Reproduce",
        },
        "POST",
        "/rest/api/3/issue",
    ),
    (
        "jira",
        "jira_update_issue",
        {"issue_key": "TEST-1", "description": "New"},
        "PUT",
        "/rest/api/3/issue/TEST-1",
    ),
    (
        "jira",
        "jira_add_comment",
        {"issue_key": "TEST-1", "text": "Comment"},
        "POST",
        "/rest/api/3/issue/TEST-1/comment",
    ),
    (
        "jira",
        "jira_list_transitions",
        {"issue_key": "TEST-1"},
        "GET",
        "/rest/api/3/issue/TEST-1/transitions",
    ),
    (
        "jira",
        "jira_transition_issue",
        {"issue_key": "TEST-1", "transition_id": "5"},
        "POST",
        "/rest/api/3/issue/TEST-1/transitions",
    ),
    (
        "atlassian",
        "confluence_list_spaces",
        {"cursor": "next"},
        "GET",
        "/wiki/api/v2/spaces",
    ),
    (
        "atlassian",
        "confluence_list_space_pages",
        {"space_id": "1", "cursor": "next"},
        "GET",
        "/wiki/api/v2/spaces/1/pages",
    ),
    (
        "atlassian",
        "confluence_create_page",
        {"space_id": "1", "title": "Draft", "storage_body": "<p>Hi</p>"},
        "POST",
        "/wiki/api/v2/pages",
    ),
    (
        "atlassian",
        "confluence_update_page",
        {
            "page_id": "1",
            "title": "Next",
            "storage_body": "<p>New</p>",
            "next_version": 2,
        },
        "PUT",
        "/wiki/api/v2/pages/1",
    ),
    (
        "atlassian",
        "confluence_delete_page",
        {"page_id": "1"},
        "DELETE",
        "/wiki/api/v2/pages/1",
    ),
    (
        "outlook",
        "outlook_get_message",
        {"message_id": "m1"},
        "GET",
        "/v1.0/me/messages/m1",
    ),
    (
        "outlook",
        "outlook_list_folder_messages",
        {"folder_id": "inbox", "skip": 40},
        "GET",
        "/v1.0/me/mailFolders/inbox/messages",
    ),
    ("outlook", "outlook_list_folders", {}, "GET", "/v1.0/me/mailFolders"),
    ("outlook", "outlook_create_draft", {"message": MAIL}, "POST", "/v1.0/me/messages"),
    (
        "outlook",
        "outlook_send_draft",
        {"message_id": "m1"},
        "POST",
        "/v1.0/me/messages/m1/send",
    ),
    (
        "outlook",
        "outlook_move_message",
        {"message_id": "m1", "destination_folder_id": "archive"},
        "POST",
        "/v1.0/me/messages/m1/move",
    ),
    (
        "outlook",
        "outlook_set_message_read",
        {"message_id": "m1", "is_read": True},
        "PATCH",
        "/v1.0/me/messages/m1",
    ),
    (
        "outlook",
        "outlook_delete_message",
        {"message_id": "m1"},
        "DELETE",
        "/v1.0/me/messages/m1",
    ),
    (
        "outlook",
        "outlook_create_event",
        {"event": EVENT, "transaction_id": "event-attempt-1"},
        "POST",
        "/v1.0/me/events",
    ),
    (
        "outlook",
        "outlook_update_event",
        {"event_id": "e1", "event": EVENT},
        "PATCH",
        "/v1.0/me/events/e1",
    ),
    (
        "outlook",
        "outlook_delete_event",
        {"event_id": "e1"},
        "DELETE",
        "/v1.0/me/events/e1",
    ),
    (
        "onedrive",
        "onedrive_list_folder",
        {"folder_id": "folder1", "skip_token": "next"},
        "GET",
        "/v1.0/me/drive/items/folder1/children",
    ),
    (
        "onedrive",
        "onedrive_search_files",
        {"query": "quarterly report"},
        "GET",
        "/v1.0/me/drive/root/search(q='quarterly report')",
    ),
    (
        "onedrive",
        "onedrive_create_folder",
        {"parent_id": "root", "name": "Reports"},
        "POST",
        "/v1.0/me/drive/items/root/children",
    ),
    (
        "onedrive",
        "onedrive_upload_file",
        {"parent_id": "root", "name": "hello.txt", "data_base64": "aGVsbG8="},
        "PUT",
        "/v1.0/me/drive/items/root:/hello.txt:/content",
    ),
    (
        "onedrive",
        "onedrive_move_or_rename",
        {"item_id": "f1", "name": "Renamed.txt"},
        "PATCH",
        "/v1.0/me/drive/items/f1",
    ),
    (
        "onedrive",
        "onedrive_delete_item",
        {"item_id": "f1"},
        "DELETE",
        "/v1.0/me/drive/items/f1",
    ),
    (
        "stripe",
        "stripe_list_customers",
        {"starting_after": "cus_prev"},
        "GET",
        "/v1/customers",
    ),
    (
        "stripe",
        "stripe_get_customer",
        {"customer_id": "cus_1"},
        "GET",
        "/v1/customers/cus_1",
    ),
    (
        "stripe",
        "stripe_create_customer",
        {"name": "Customer", "email": "a@example.test", "idempotency_key": "create-1"},
        "POST",
        "/v1/customers",
    ),
    (
        "stripe",
        "stripe_update_customer",
        {"customer_id": "cus_1", "name": "New", "idempotency_key": "update-1"},
        "POST",
        "/v1/customers/cus_1",
    ),
    ("stripe", "stripe_list_products", {}, "GET", "/v1/products"),
    ("stripe", "stripe_list_prices", {"product_id": "prod_1"}, "GET", "/v1/prices"),
    (
        "stripe",
        "stripe_get_invoice",
        {"invoice_id": "in_1"},
        "GET",
        "/v1/invoices/in_1",
    ),
    (
        "stripe",
        "stripe_create_invoice",
        {"customer_id": "cus_1", "idempotency_key": "invoice-1"},
        "POST",
        "/v1/invoices",
    ),
    (
        "stripe",
        "stripe_add_invoice_item",
        {
            "customer_id": "cus_1",
            "invoice_id": "in_1",
            "amount": 500,
            "currency": "usd",
            "description": "Line",
            "idempotency_key": "line-1",
        },
        "POST",
        "/v1/invoiceitems",
    ),
    (
        "stripe",
        "stripe_list_subscriptions",
        {"customer_id": "cus_1"},
        "GET",
        "/v1/subscriptions",
    ),
    (
        "stripe",
        "stripe_set_subscription_cancel_at_period_end",
        {
            "subscription_id": "sub_1",
            "cancel_at_period_end": True,
            "idempotency_key": "cancel-1",
        },
        "POST",
        "/v1/subscriptions/sub_1",
    ),
    (
        "stripe",
        "stripe_create_payment_intent",
        {"amount": 500, "currency": "usd", "idempotency_key": "payment-1"},
        "POST",
        "/v1/payment_intents",
    ),
    (
        "stripe",
        "stripe_refund_payment",
        {"payment_intent_id": "pi_1", "amount": 100, "idempotency_key": "refund-1"},
        "POST",
        "/v1/refunds",
    ),
    (
        "huggingface",
        "huggingface_get_model",
        {"repo_id": "org/model"},
        "GET",
        "/api/models/org/model",
    ),
    (
        "huggingface",
        "huggingface_get_dataset",
        {"repo_id": "org/data"},
        "GET",
        "/api/datasets/org/data",
    ),
    (
        "huggingface",
        "huggingface_get_space",
        {"repo_id": "org/space"},
        "GET",
        "/api/spaces/org/space",
    ),
    (
        "huggingface",
        "huggingface_search_spaces",
        {"search": "demo"},
        "GET",
        "/api/spaces",
    ),
    (
        "huggingface",
        "huggingface_create_repository",
        {"name": "private-model", "repo_type": "model", "organization": "org"},
        "POST",
        "/api/repos/create",
    ),
    (
        "apollo",
        "apollo_search_contacts",
        {"query": "CEO", "page_number": 2},
        "POST",
        "/api/v1/contacts/search",
    ),
    (
        "apollo",
        "apollo_search_accounts",
        {"organization_name": "Company"},
        "POST",
        "/api/v1/accounts/search",
    ),
    (
        "apollo",
        "apollo_create_contact",
        {"contact": {"first_name": "Alice", "email": "a@example.test"}},
        "POST",
        "/api/v1/contacts",
    ),
    (
        "apollo",
        "apollo_update_contact",
        {"contact_id": "c1", "contact": {"title": "Director"}},
        "PATCH",
        "/api/v1/contacts/c1",
    ),
    (
        "apollo",
        "apollo_create_account",
        {"name": "Company", "domain": "example.test"},
        "POST",
        "/api/v1/accounts",
    ),
    ("n8n", "n8n_get_workflow", {"workflow_id": "w1"}, "GET", "/api/v1/workflows/w1"),
    (
        "n8n",
        "n8n_list_executions",
        {"workflow_id": "w1", "cursor": "next"},
        "GET",
        "/api/v1/executions",
    ),
    (
        "n8n",
        "n8n_activate_workflow",
        {"workflow_id": "w1"},
        "POST",
        "/api/v1/workflows/w1/activate",
    ),
    (
        "n8n",
        "n8n_deactivate_workflow",
        {"workflow_id": "w1"},
        "POST",
        "/api/v1/workflows/w1/deactivate",
    ),
    (
        "n8n",
        "n8n_delete_workflow",
        {"workflow_id": "w1"},
        "DELETE",
        "/api/v1/workflows/w1",
    ),
]


class Harness:
    def __init__(self, monkeypatch):
        self.requests = []
        self.options = []
        self.secure_requests = []
        self.responder = None
        self.server: Any = FastMCP("Business provider contract tests")
        self.server._consumer_products = set()
        self.server._consumer_tool_products = {}
        business.register(self.server)
        original = httpx.AsyncClient

        def client(**kwargs):
            self.options.append(kwargs)
            return original(transport=httpx.MockTransport(self.handle), **kwargs)

        monkeypatch.setattr(business.httpx, "AsyncClient", client)

        async def secure(url, **kwargs):
            self.secure_requests.append((url, kwargs))
            response = self.handle(
                httpx.Request(
                    kwargs["method"],
                    url,
                    headers=kwargs["headers"],
                    content=kwargs["content"],
                )
            )
            return SimpleNamespace(
                status_code=response.status_code, content=response.content
            )

        monkeypatch.setattr(business, "async_secure_outbound_request", secure)

    def handle(self, request):
        self.requests.append(request)
        if self.responder:
            return self.responder(request)
        return httpx.Response(
            200,
            json={
                "id": "result",
                "name": "Fixture",
                "ok": True,
                "data": [],
                "nextCursor": "next",
                "active": False,
            },
        )

    async def call(self, name, arguments=None, *, product=None, context=None):
        product = product or self.server._consumer_tool_products[name]
        values = {PRODUCTS[product][0]: TOKEN, "ACCOUNT_EMAIL": "owner@example.test"}
        if product in CUSTOM:
            values[BASE_KEYS[product]] = "https://business.example.test"
        token = consumer_runtime._ACCESS.set(
            context
            if context is not None
            else {
                "product": product,
                "headers": headers(product, values),
                "values": values,
            }
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
    return Harness(monkeypatch)


def error_text(result):
    return " ".join(getattr(item, "text", "") for item in result.content)


@pytest.mark.parametrize(
    "product,name,arguments,method,path", CASES, ids=[case[1] for case in CASES]
)
async def test_every_operation_contract(
    harness, product, name, arguments, method, path
):
    result = await harness.call(name, arguments)
    assert not result.is_error, error_text(result)
    assert len(harness.requests) == 1
    request = harness.requests[0]
    assert request.method == method
    assert request.url.path == path
    assert request.url.host == (
        "business.example.test"
        if product in CUSTOM
        else httpx.URL(PRODUCTS[product][2]).host
    )
    assert any(TOKEN in value for value in request.headers.values()) or product in {
        "jira",
        "atlassian",
    }
    if product in CUSTOM:
        assert (
            harness.secure_requests[0][1]["max_response_bytes"] == business.MAX_RESPONSE
        )
    else:
        assert harness.options[0]["follow_redirects"] is False
    if product == "stripe" and method != "GET":
        assert request.headers["Idempotency-Key"] == arguments["idempotency_key"]
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert parse_qs(request.content.decode())
    if name == "onedrive_upload_file":
        assert request.content == b"hello"
        assert request.headers["Content-Type"] == "application/octet-stream"


async def test_all_registered_names_have_contracts_and_annotations(harness):
    async with Client(harness.server) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == {case[1] for case in CASES}
    for tool in tools:
        assert tool.description
        assert tool.annotations.open_world_hint
        if any(
            word in tool.name
            for word in (
                "delete",
                "refund",
                "send_draft",
                "activate",
                "update",
                "move",
                "upload",
                "transition_issue",
                "trashed",
            )
        ):
            assert tool.annotations.read_only_hint is False
            assert tool.annotations.destructive_hint is True
        assert tool.input_schema["type"] == "object"


async def test_provider_payloads_do_not_silently_publish_send_or_charge(harness):
    await harness.call(
        "confluence_create_page",
        {"space_id": "1", "title": "Draft", "storage_body": "<p>Hi</p>"},
    )
    assert json.loads(harness.requests[-1].content)["status"] == "draft"
    await harness.call("outlook_create_draft", {"message": MAIL})
    message = json.loads(harness.requests[-1].content)
    assert message["toRecipients"] == [{"emailAddress": {"address": "a@example.test"}}]
    assert harness.requests[-1].url.path.endswith("/messages")
    await harness.call(
        "stripe_create_invoice", {"customer_id": "cus_1", "idempotency_key": "draft-1"}
    )
    assert parse_qs(harness.requests[-1].content.decode())["auto_advance"] == ["false"]
    assert parse_qs(harness.requests[-1].content.decode())[
        "pending_invoice_items_behavior"
    ] == ["exclude"]
    await harness.call(
        "stripe_create_payment_intent",
        {"amount": 250, "currency": "usd", "idempotency_key": "intent-1"},
    )
    assert parse_qs(harness.requests[-1].content.decode())["confirm"] == ["false"]
    await harness.call(
        "huggingface_create_repository", {"name": "model", "repo_type": "model"}
    )
    assert json.loads(harness.requests[-1].content)["visibility"] == "private"
    await harness.call("apollo_create_contact", {"contact": {"first_name": "Alice"}})
    assert json.loads(harness.requests[-1].content)["run_dedupe"] is False


async def test_structured_documents_version_and_pagination(harness):
    await harness.call(
        "jira_create_issue",
        {
            "project_key": "TEST",
            "issue_type_id": "1",
            "summary": "Bug",
            "description": "Description",
        },
    )
    fields = json.loads(harness.requests[-1].content)["fields"]
    assert fields["description"] == {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Description"}]}
        ],
    }
    await harness.call(
        "jira_search_issues", {"jql": "project = TEST", "next_page_token": "abc"}
    )
    assert json.loads(harness.requests[-1].content)["nextPageToken"] == "abc"
    await harness.call(
        "confluence_update_page",
        {
            "page_id": "1",
            "title": "New",
            "storage_body": "<p>New</p>",
            "next_version": 8,
        },
    )
    assert json.loads(harness.requests[-1].content)["version"] == {"number": 8}
    await harness.call(
        "notion_append_paragraphs", {"block_id": "p1", "paragraphs": ["One", "Two"]}
    )
    children = json.loads(harness.requests[-1].content)["children"]
    assert [
        item["paragraph"]["rich_text"][0]["text"]["content"] for item in children
    ] == ["One", "Two"]
    await harness.call(
        "notion_query_data_source",
        {
            "data_source_id": "d1",
            "start_cursor": "next",
            "filter": {"property": "Done", "checkbox": {"equals": True}},
        },
    )
    assert harness.requests[-1].headers["Notion-Version"] == "2026-03-11"
    assert json.loads(harness.requests[-1].content)["start_cursor"] == "next"


@pytest.mark.parametrize(
    "name,arguments",
    [
        (
            "github_get_file",
            {"owner": "org", "repository": "repo", "path": "../secret"},
        ),
        (
            "github_get_issue",
            {"owner": "org?token=bad", "repository": "repo", "issue_number": 1},
        ),
        (
            "github_list_pull_requests",
            {"owner": "org", "repository": "repo", "limit": 101},
        ),
        ("slack_thread_replies", {"channel_id": "C1", "thread_ts": "bad", "limit": 16}),
        (
            "stripe_refund_payment",
            {"payment_intent_id": "pi_1", "amount": 0, "idempotency_key": "refund"},
        ),
        (
            "stripe_create_customer",
            {
                "name": "Name",
                "email": "a@example.test",
                "idempotency_key": "key\r\nInjected: yes",
            },
        ),
        (
            "notion_create_page",
            {"parent_id": "p1", "properties": {"not_a_title": "bad"}},
        ),
        ("notion_update_page_properties", {"page_id": "p1", "properties": {}}),
        ("notion_append_paragraphs", {"block_id": "p1", "paragraphs": ["a"] * 101}),
        ("jira_update_issue", {"issue_key": "KEY-1"}),
        (
            "confluence_update_page",
            {"page_id": "1", "title": "Edit", "storage_body": "Hi", "next_version": 0},
        ),
        (
            "outlook_create_draft",
            {"message": {**MAIL, "to": ["a@example.test\r\nBcc: evil@example.test"]}},
        ),
        (
            "outlook_create_event",
            {"event": {**EVENT, "end": "2026-09-08T09:00:00"}, "transaction_id": "x"},
        ),
        ("onedrive_create_folder", {"parent_id": "root", "name": "../outside"}),
        (
            "onedrive_upload_file",
            {"parent_id": "root", "name": "file", "data_base64": "!invalid!"},
        ),
        ("onedrive_move_or_rename", {"item_id": "f1"}),
        ("huggingface_get_model", {"repo_id": "org/repo/extra"}),
        ("huggingface_create_repository", {"name": "space", "repo_type": "space"}),
        ("apollo_create_contact", {"contact": {}}),
        (
            "apollo_update_contact",
            {"contact_id": "1", "contact": {"api_key": "inject"}},
        ),
        ("n8n_activate_workflow", {"workflow_id": "../credentials"}),
    ],
)
async def test_invalid_arguments_never_reach_provider(harness, name, arguments):
    result = await harness.call(name, arguments)
    assert result.is_error
    assert not harness.requests


@pytest.mark.parametrize(
    "failure", ["timeout", "server_error", "redirect", "invalid_json"]
)
@pytest.mark.parametrize(
    "name,arguments",
    [
        ("slack_post_message", {"channel_id": "C1", "text": "Hi"}),
        ("jira_transition_issue", {"issue_key": "TEST-1", "transition_id": "5"}),
        (
            "stripe_refund_payment",
            {"payment_intent_id": "pi_1", "amount": 100, "idempotency_key": "refund-1"},
        ),
    ],
)
async def test_mutations_never_retry_or_leak_provider_errors(
    harness, failure, name, arguments
):
    def responder(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        if failure == "invalid_json":
            return httpx.Response(200, content=TOKEN)
        return httpx.Response(
            503 if failure == "server_error" else 302,
            headers={"Location": "https://evil.example.test/"},
            content=TOKEN,
        )

    harness.responder = responder
    result = await harness.call(name, arguments)
    assert result.is_error
    assert len(harness.requests) == 1
    assert TOKEN not in error_text(result)
    if failure != "redirect":
        assert "outcome is unknown" in error_text(result)


async def test_redaction_success_statuses_and_n8n_projection(harness):
    harness.responder = lambda request: httpx.Response(
        200,
        json={
            "id": "pi_1",
            "client_secret": TOKEN,
            "nested": {"access_token": TOKEN},
            "@microsoft.graph.downloadUrl": "https://signed.example.test",
        },
    )
    result = await harness.call("stripe_get_invoice", {"invoice_id": "in_1"})
    assert TOKEN not in str(result.data)
    assert "downloadUrl" not in str(result.data)
    harness.responder = lambda request: httpx.Response(201, json={"id": "draft-1"})
    result = await harness.call("outlook_create_draft", {"message": MAIL})
    assert result.data == {"id": "draft-1"}
    harness.responder = lambda request: httpx.Response(202)
    result = await harness.call("outlook_send_draft", {"message_id": "m1"})
    assert result.data == {"accepted": True, "status": 202}
    harness.responder = lambda request: httpx.Response(204)
    result = await harness.call("onedrive_delete_item", {"item_id": "f1"})
    assert result.data == {"accepted": True, "status": 204}
    harness.responder = lambda request: httpx.Response(
        200,
        json={
            "id": "w1",
            "name": "Job",
            "nodes": [{"parameters": {"password": TOKEN}}],
            "credentials": TOKEN,
        },
    )
    result = await harness.call("n8n_get_workflow", {"workflow_id": "w1"})
    assert result.data == {"id": "w1", "name": "Job"}


async def test_wrong_product_and_unsafe_custom_origin_rejected(harness):
    result = await harness.call(
        "slack_post_message", {"channel_id": "C1", "text": "Hi"}, product="github"
    )
    assert result.is_error
    for url in (
        "http://public.example.test",
        "https://user:pass@example.test",
        "https://example.test/?token=secret",
    ):
        result = await harness.call(
            "jira_list_transitions",
            {"issue_key": "TEST-1"},
            context={
                "product": "jira",
                "headers": {"Authorization": "Bearer " + TOKEN},
                "values": {"BASE_URL": url},
            },
        )
        assert result.is_error
    assert not harness.requests


async def test_size_limits_stop_without_network_or_unbounded_response(
    harness, monkeypatch
):
    monkeypatch.setattr(business, "MAX_UPLOAD", 3)
    result = await harness.call(
        "onedrive_upload_file",
        {
            "parent_id": "root",
            "name": "file",
            "data_base64": base64.b64encode(b"four").decode(),
        },
    )
    assert result.is_error and not harness.requests
    monkeypatch.setattr(business, "MAX_RESPONSE", 16)
    result = await harness.call(
        "github_get_repository", {"owner": "org", "repository": "repo"}
    )
    assert result.is_error
    assert "too large" in error_text(result)
    result = await harness.call(
        "slack_post_message", {"channel_id": "C1", "text": "Hi"}
    )
    assert result.is_error
    assert "outcome is unknown" in error_text(result)


async def test_access_rechecked_before_outbound_when_profile_changes(
    harness, monkeypatch
):
    from purecipher import workspace

    monkeypatch.setattr(
        workspace, "allowed_profile_tools", lambda *args: {"slack_post_message"}
    )
    monkeypatch.setattr(consumer_runtime, "runtime_ready", lambda *args: True)
    registry = SimpleNamespace(
        _workspace={"connection": {"revision": 2}, "profile": {"revision": 1}}
    )
    result = await harness.call(
        "slack_post_message",
        {"channel_id": "C1", "text": "Hi"},
        context={
            "product": "slack",
            "headers": {"Authorization": "Bearer " + TOKEN},
            "registry": registry,
            "profile_id": "profile",
            "connection_id": "connection",
            "profile_revision": 1,
            "connection_revision": 1,
            "tool_name": "slack_post_message",
            "client": "client1",
        },
    )
    assert result.is_error
    assert "changed" in error_text(result)
    assert not harness.requests
