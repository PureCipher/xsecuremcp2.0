"""Preparation tests; no Google account or live messages are used."""

from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from examples.securemcp.google_workspace import calendar_server as calendar
from fastmcp import Client
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)
from securemcp import SecureMCP


def server():
    return calendar.create_server(
        "test.apps.googleusercontent.com",
        "test-secret-for-fixtures",
        "http://127.0.0.1:9101",
    )


async def test_securemcp_controls_and_tool_discovery(caplog):
    app = server()
    assert isinstance(app, SecureMCP)
    ctx = app.security_context
    assert ctx is not None
    assert ctx.policy_engine is not None
    assert ctx.consent_graph is not None
    assert ctx.provenance_ledger is not None
    assert ctx.introspection_engine is not None
    async with Client(app) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == calendar.TOOLS
        assert all(t.annotations.read_only_hint for t in tools)
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool("calendar_list_calendars", {})
        assert "ConsentRequiredError" in caplog.text


async def test_read_policy_denies_undeclared_write_tool():
    policy = calendar.CalendarReadPolicy()
    allowed = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="calendar_list_calendars"
        )
    )
    denied = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="calendar_send"
        )
    )
    assert allowed.decision == PolicyDecision.ALLOW
    assert denied.decision == PolicyDecision.DENY


def test_http_requires_oauth():
    with TestClient(server().http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


async def test_google_request_uses_current_principal_token(monkeypatch):
    monkeypatch.setattr(
        calendar,
        "get_access_token",
        lambda: SimpleNamespace(
            token="fixture-token", scopes=[calendar.CALENDAR_SCOPE]
        ),
    )
    original = httpx.AsyncClient

    def handler(request):
        assert request.url.host == "www.googleapis.com"
        assert request.url.path == "/calendar/v3/users/me/calendarList"
        assert request.headers["authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json={"emailAddress": "fixture@example.test"})

    monkeypatch.setattr(
        calendar.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await calendar.calendar_get("users/me/calendarList") == {
        "emailAddress": "fixture@example.test"
    }


async def test_missing_google_scope_denied(monkeypatch):
    monkeypatch.setattr(
        calendar,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[]),
    )
    with pytest.raises(ValueError, match="authorization"):
        await calendar.calendar_get("users/me/calendarList")


def test_no_oauth_credentials_fails_closed():
    with pytest.raises(ValueError, match="must be configured"):
        calendar.create_server("", "", "http://127.0.0.1:9101")


@pytest.mark.parametrize("value", ["", ".", "..", "../secret", "a/b", "a?b", "a#b"])
def test_resource_id_rejects_path_manipulation(value):
    with pytest.raises(ValueError):
        calendar.safe_id(value)


@pytest.mark.parametrize("value", [0, 101, -1])
def test_pagination_bounds(value):
    with pytest.raises(ValueError):
        calendar.page_params("", value)


async def test_calendar_tool_encodes_id_and_forwards_pagination(monkeypatch):
    async def get(path, params):
        assert path == "calendars/user%40example.test/events"
        assert params == {"maxResults": 10, "pageToken": "next"}
        return {"items": []}

    monkeypatch.setattr(calendar, "calendar_get", get)
    tool = await server().get_tool("calendar_list_events")
    assert await tool.fn(
        calendar_id="user@example.test", page_token="next", max_results=10
    ) == {"items": []}
