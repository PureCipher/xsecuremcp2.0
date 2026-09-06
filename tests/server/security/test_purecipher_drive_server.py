"""Preparation tests; no Google account or live messages are used."""

from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from examples.securemcp.google_workspace import drive_server as drive
from fastmcp import Client
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)
from securemcp import SecureMCP


def server():
    return drive.create_server(
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
        assert {t.name for t in tools} == drive.TOOLS
        assert all(t.annotations.read_only_hint for t in tools)
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool("drive_get_file", {"file_id": "testid"})
        assert "ConsentRequiredError" in caplog.text


async def test_read_policy_denies_undeclared_write_tool():
    policy = drive.DriveReadPolicy()
    allowed = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="drive_get_file"
        )
    )
    denied = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="drive_send"
        )
    )
    assert allowed.decision == PolicyDecision.ALLOW
    assert denied.decision == PolicyDecision.DENY


def test_http_requires_oauth():
    with TestClient(server().http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


async def test_google_request_uses_current_principal_token(monkeypatch):
    monkeypatch.setattr(
        drive,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[drive.DRIVE_SCOPE]),
    )
    original = httpx.AsyncClient

    def handler(request):
        assert request.url.host == "www.googleapis.com"
        assert request.url.path == "/drive/v3/files/testid"
        assert request.headers["authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json={"emailAddress": "fixture@example.test"})

    monkeypatch.setattr(
        drive.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await drive.drive_get("files/testid") == {
        "emailAddress": "fixture@example.test"
    }


async def test_missing_google_scope_denied(monkeypatch):
    monkeypatch.setattr(
        drive,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[]),
    )
    with pytest.raises(ValueError, match="authorization"):
        await drive.drive_get("files/testid")


def test_no_oauth_credentials_fails_closed():
    with pytest.raises(ValueError, match="must be configured"):
        drive.create_server("", "", "http://127.0.0.1:9101")


@pytest.mark.parametrize("value", ["", ".", "..", "../secret", "a/b", "a?b", "a#b"])
def test_resource_id_rejects_path_manipulation(value):
    with pytest.raises(ValueError):
        drive.safe_id(value)


@pytest.mark.parametrize("value", [0, 101, -1])
def test_pagination_bounds(value):
    with pytest.raises(ValueError):
        drive.page_params("", value)


async def test_file_metadata_tool(monkeypatch):
    async def get(path, params):
        assert path == "files/file_123"
        assert "alt" not in params
        assert params["supportsAllDrives"] == "true"
        return {"id": "file_123"}

    monkeypatch.setattr(drive, "drive_get", get)
    tool = await server().get_tool("drive_get_file")
    assert await tool.fn(file_id="file_123") == {"id": "file_123"}


async def test_search_excludes_trash_and_forwards_pagination(monkeypatch):
    async def get(path, params):
        assert path == "files"
        assert (
            params["q"]
            == "trashed = false and (mimeType = 'application/vnd.google-apps.folder')"
        )
        assert params["pageSize"] == 10
        assert params["pageToken"] == "next"
        assert "nextPageToken" in params["fields"]
        return {"files": [], "nextPageToken": "later"}

    monkeypatch.setattr(drive, "drive_get", get)
    tool = await server().get_tool("drive_search_files")
    result = await tool.fn(
        query="mimeType = 'application/vnd.google-apps.folder'",
        page_token="next",
        max_results=10,
    )
    assert result["nextPageToken"] == "later"


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
async def test_provider_error_does_not_expose_response(monkeypatch, status):
    monkeypatch.setattr(
        drive,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[drive.DRIVE_SCOPE]),
    )
    original = httpx.AsyncClient

    def handler(request):
        return httpx.Response(
            status,
            json={"error": "private-provider-details"},
            headers={"Location": "https://example.test/redirect"},
        )

    monkeypatch.setattr(
        drive.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(ValueError) as exc:
        await drive.drive_get("files")
    assert "private-provider-details" not in str(exc.value)
    assert "fixture-token" not in str(exc.value)
