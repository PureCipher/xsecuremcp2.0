"""Offline preparation tests; no real provider credentials or account data."""

from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from examples.securemcp.business_integrations import (
    common,
    github_server,
    jira_server,
    oauth,
    onedrive_server,
    outlook_server,
    slack_server,
)
from fastmcp import Client
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)
from securemcp import SecureMCP

MODULES = {
    "github": github_server,
    "slack": slack_server,
    "jira": jira_server,
    "outlook": outlook_server,
    "onedrive": onedrive_server,
}


def make_server(service):
    auth = oauth.create_oauth(
        service,
        "http://127.0.0.1:9111",
        "fixture-client",
        "fixture-secret",
        tenant_id="fixture-tenant",
        cloud_id="fixture-cloud",
    )
    if service == "github":
        return github_server.create_server(auth, {"PureCipher/example"})
    if service == "slack":
        return slack_server.create_server(auth, {"C123"})
    if service == "jira":
        return jira_server.create_server(auth, "fixture-cloud")
    if service == "outlook":
        return outlook_server.create_server(auth)
    return onedrive_server.create_server(auth)



@pytest.mark.parametrize("service", MODULES)
async def test_controls_discovery_and_unconsented_call(service, caplog):
    server = make_server(service)
    assert isinstance(server, SecureMCP)
    ctx = server.security_context
    assert (
        ctx
        and ctx.policy_engine
        and ctx.consent_graph
        and ctx.provenance_ledger
        and ctx.introspection_engine
    )
    async with Client(server) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == MODULES[service].TOOLS
        assert all(
            t.annotations.read_only_hint and not t.annotations.destructive_hint
            for t in tools
        )
        name, args = {
            "github": (
                "github_list_issues",
                {"owner": "PureCipher", "repo": "example"},
            ),
            "slack": ("slack_channel_history", {"channel_id": "C123"}),
            "jira": ("jira_get_issue", {"issue_key": "PC-1"}),
            "outlook": ("outlook_list_messages", {}),
            "onedrive": ("onedrive_list_files", {}),
        }[service]
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool(name, args)
        assert "ConsentRequiredError" in caplog.text


@pytest.mark.parametrize("service", MODULES)
def test_unauthenticated_http_rejected(service):
    with TestClient(make_server(service).http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


@pytest.mark.parametrize("service", MODULES)
async def test_undeclared_write_denied(service):
    policy = common.ReadPolicy(service, MODULES[service].TOOLS)
    result = await policy.evaluate(
        PolicyEvaluationContext(
            actor_id="fixture", action="call_tool", resource_id=service + "_delete"
        )
    )
    assert result.decision == PolicyDecision.DENY


@pytest.mark.parametrize("service", MODULES)
def test_missing_credentials_fails_closed(service):
    with pytest.raises(ValueError, match="must be configured"):
        oauth.create_oauth(service, "http://localhost:9111", "", "")


@pytest.mark.parametrize(
    "value", ["", "..", ".", "a/b", "a?b", "a#b", "a%2fb", "a\\b", "a\nb"]
)
def test_invalid_ids(value):
    with pytest.raises(ValueError):
        common.resource_id(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://graph.microsoft.com/v1.0/me/messages",
        "https://example.test/v1.0/me/messages",
        "https://graph.microsoft.com.evil.test/v1.0/me/messages",
        "https://graph.microsoft.com/v1.0/users/other/messages",
        "https://graph.microsoft.com/v1.0/me/messages#fragment",
        "https://user@graph.microsoft.com/v1.0/me/messages",
    ],
)
def test_untrusted_pagination_rejected(url):
    with pytest.raises(ValueError):
        common.graph_page(url, "me/messages")


def test_valid_pagination_preserved():
    assert (
        common.graph_page(
            "https://graph.microsoft.com/v1.0/me/messages?$skiptoken=abc", "me/messages"
        )[0]
        == "me/messages?$skiptoken=abc"
    )


@pytest.mark.parametrize(
    "service,tool,args,path",
    [
        (
            "github",
            "github_list_issues",
            {"owner": "PureCipher", "repo": "example"},
            "repos/PureCipher/example/issues",
        ),
        (
            "github",
            "github_list_pull_requests",
            {"owner": "PureCipher", "repo": "example"},
            "repos/PureCipher/example/pulls",
        ),
        (
            "github",
            "github_get_issue",
            {"owner": "PureCipher", "repo": "example", "issue_number": 2},
            "repos/PureCipher/example/issues/2",
        ),
        (
            "slack",
            "slack_channel_history",
            {"channel_id": "C123"},
            "conversations.history",
        ),
        ("jira", "jira_search_issues", {"jql": "project = PC"}, "search/jql"),
        ("jira", "jira_get_issue", {"issue_key": "PC-1"}, "issue/PC-1"),
        ("outlook", "outlook_list_messages", {}, "me/messages"),
        ("outlook", "outlook_get_message", {"message_id": "m123"}, "me/messages/m123"),
        ("outlook", "outlook_list_events", {}, "me/events"),
        ("onedrive", "onedrive_list_files", {}, "me/drive/root/children"),
        ("onedrive", "onedrive_get_file", {"file_id": "f123"}, "me/drive/items/f123"),
    ],
)
async def test_tool_request_mapping(monkeypatch, service, tool, args, path):
    async def get(base, actual_path, params=None):
        assert actual_path == path
        assert base.startswith("https://")
        return {"items": []}

    monkeypatch.setattr(MODULES[service], "read_json", get)
    registered = await make_server(service).get_tool(tool)
    assert await registered.fn(**args) == (
        {} if service == "onedrive" else {"items": []}
    )


@pytest.mark.parametrize(
    "service,tool,args",
    [
        ("github", "github_list_issues", {"owner": "other", "repo": "private"}),
        ("slack", "slack_channel_history", {"channel_id": "COTHER"}),
    ],
)
async def test_resource_allowlist(service, tool, args):
    registered = await make_server(service).get_tool(tool)
    with pytest.raises(ValueError, match="not allowed"):
        await registered.fn(**args)


async def test_provider_request_is_get_and_uses_current_token(monkeypatch):
    monkeypatch.setattr(
        common, "get_access_token", lambda: SimpleNamespace(token="fixture-token")
    )
    original = httpx.AsyncClient

    def handler(request):
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer fixture-token"
        assert request.url.host == "api.github.com"
        return httpx.Response(200, json=[{"id": 1}])

    monkeypatch.setattr(
        common.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await common.read_json("https://api.github.com/", "repos/a/b/issues") == {
        "items": [{"id": 1}]
    }


@pytest.mark.parametrize(
    "status,data",
    [
        (302, {}),
        (403, {"private": "secret"}),
        (429, {}),
        (200, {"ok": False, "error": "private"}),
    ],
)
async def test_provider_failures_sanitized(monkeypatch, status, data):
    monkeypatch.setattr(
        common, "get_access_token", lambda: SimpleNamespace(token="fixture-token")
    )
    original = httpx.AsyncClient
    monkeypatch.setattr(
        common.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, json=data)),
            **kwargs,
        ),
    )
    with pytest.raises(ValueError) as exc:
        await common.read_json("https://slack.com/api/", "conversations.history")
    assert "private" not in str(exc.value) and "fixture-token" not in str(exc.value)


def test_slack_user_token_normalization_rejects_bot():
    result = oauth.slack_token_response(
        {
            "ok": True,
            "access_token": "bot",
            "authed_user": {
                "access_token": "user",
                "token_type": "user",
                "scope": "channels:read,channels:history",
            },
        }
    )
    assert (
        result["access_token"] == "user"
        and result["scope"] == "channels:read channels:history"
    )
    with pytest.raises(ValueError):
        oauth.slack_token_response({"ok": True, "access_token": "bot"})


@pytest.mark.parametrize("service", ["slack", "jira", "outlook", "onedrive"])
async def test_identity_verification_failure_is_closed(monkeypatch, service):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        oauth.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})),
            **kwargs,
        ),
    )
    assert (
        await oauth.IdentityVerifier(service, "cloud").verify_token("fixture") is None
    )


def test_graph_keeps_delegated_scopes_during_exchange_and_refresh():
    auth = oauth.create_oauth(
        "outlook", "http://localhost:9114", "client", "secret", tenant_id="tenant"
    )
    assert "Mail.Read" in auth._prepare_scopes_for_token_exchange(["User.Read"])
    assert "Calendars.Read" in auth._prepare_scopes_for_upstream_refresh(["User.Read"])


@pytest.mark.parametrize(
    "service,allowed",
    [
        ("slack", True),
        ("jira", True),
        ("outlook", True),
        ("onedrive", True),
        ("slack", False),
        ("jira", False),
    ],
)
async def test_identity_uses_provider_subject_and_real_site_or_scope_checks(
    monkeypatch, service, allowed
):
    original = httpx.AsyncClient

    def handler(request):
        assert request.headers["authorization"] == "Bearer fixture"
        if request.url.host == "slack.com":
            return httpx.Response(
                200,
                json={"ok": True, "team_id": "T1", "user_id": "U1"},
                headers={
                    "x-oauth-scopes": "channels:read,channels:history"
                    if allowed
                    else "channels:read"
                },
            )
        if request.url.path.endswith("accessible-resources"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "cloud" if allowed else "other",
                        "scopes": ["read:jira-work"],
                    }
                ],
            )
        if request.url.host == "api.atlassian.com":
            return httpx.Response(200, json={"account_id": "jira-user"})
        return httpx.Response(200, json={"id": "graph-user"})

    monkeypatch.setattr(
        oauth.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    token = await oauth.IdentityVerifier(service, "cloud").verify_token("fixture")
    if not allowed:
        assert token is None
    else:
        assert token is not None
        assert token.subject == {"slack": "T1:U1", "jira": "jira-user"}.get(
            service, "graph-user"
        )


async def test_slack_oauth_client_normalizes_user_exchange_and_refresh(monkeypatch):
    import httpx2

    original = httpx2.AsyncClient

    def handler(request):
        return httpx2.Response(
            200,
            json={
                "ok": True,
                "authed_user": {
                    "token_type": "user",
                    "access_token": "fixture-user",
                    "refresh_token": "fixture-refresh",
                    "expires_in": 3600,
                    "scope": "channels:read,channels:history",
                },
            },
        )

    monkeypatch.setattr(
        httpx2,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx2.MockTransport(handler), **kwargs),
    )
    client = oauth.SlackOAuthClient(
        "client", "secret", token_endpoint_auth_method="client_secret_post"
    )
    try:
        token = await client.fetch_token(
            "https://slack.com/api/oauth.v2.access", code="fixture-code"
        )
        assert (
            token["access_token"] == "fixture-user" and token["token_type"] == "Bearer"
        )
        refreshed = await client.refresh_token(
            "https://slack.com/api/oauth.v2.access", refresh_token="fixture-refresh"
        )
        assert refreshed["refresh_token"] == "fixture-refresh"
    finally:
        await client.aclose()


def test_onedrive_never_returns_preauthenticated_download_urls():
    data = {
        "id": "f1",
        "name": "File",
        "@microsoft.graph.downloadUrl": "https://sensitive-download.test/token",
    }
    assert onedrive_server.metadata_only(data) == {"id": "f1", "name": "File"}
    assert onedrive_server.metadata_only({"value": [data]}) == {
        "value": [{"id": "f1", "name": "File"}]
    }
