"""Preparation tests; no Google account or live messages are used."""

from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from examples.securemcp.google_workspace import gmail_server as gmail
from fastmcp import Client
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)
from securemcp import SecureMCP


def server():
    return gmail.create_server(
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
        assert {t.name for t in tools} == gmail.TOOLS
        assert all(t.annotations.read_only_hint for t in tools)
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool("gmail_profile", {})
        assert "ConsentRequiredError" in caplog.text


async def test_read_policy_denies_undeclared_write_tool():
    policy = gmail.GmailReadPolicy()
    allowed = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="gmail_profile"
        )
    )
    denied = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="gmail_send"
        )
    )
    assert allowed.decision == PolicyDecision.ALLOW
    assert denied.decision == PolicyDecision.DENY


def test_http_requires_oauth():
    with TestClient(server().http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


async def test_google_request_uses_current_principal_token(monkeypatch):
    monkeypatch.setattr(
        gmail,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[gmail.GMAIL_SCOPE]),
    )
    original = httpx.AsyncClient

    def handler(request):
        assert request.url.host == "gmail.googleapis.com"
        assert request.url.path == "/gmail/v1/users/me/profile"
        assert request.headers["authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json={"emailAddress": "fixture@example.test"})

    monkeypatch.setattr(
        gmail.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await gmail.gmail_get("profile") == {"emailAddress": "fixture@example.test"}


async def test_missing_google_scope_denied(monkeypatch):
    monkeypatch.setattr(
        gmail,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[]),
    )
    with pytest.raises(ValueError, match="authorization"):
        await gmail.gmail_get("profile")


def test_no_oauth_credentials_fails_closed():
    with pytest.raises(ValueError, match="must be configured"):
        gmail.create_server("", "", "http://127.0.0.1:9101")
