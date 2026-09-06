"""Apollo preparation: OAuth, policy, credit boundary and endpoint mapping."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.testclient import TestClient

from examples.securemcp.business_integrations import apollo_server as apollo
from examples.securemcp.business_integrations.common import ReadPolicy
from fastmcp import Client
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)


def server(enabled=False):
    auth = apollo.create_oauth(
        "fixture-client",
        "fixture-secret",
        "https://apollo.example.test",
        enable_company_search=enabled,
    )
    return apollo.create_server(auth, enable_company_search=enabled)


async def test_discovery_and_unconsented_call(caplog):
    app = server()
    assert app.security_context.consent_graph is not None
    assert app.security_context.provenance_ledger is not None
    assert app.security_context.introspection_engine is not None
    async with Client(app) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == apollo.TOOLS
        assert all(t.annotations.read_only_hint for t in tools)
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool("apollo_profile", {})
        assert "ConsentRequiredError" in caplog.text


def test_http_rejects_missing_auth():
    with TestClient(server().http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


@pytest.mark.parametrize(
    "tool", ["apollo_send_email", "apollo_enrich_person", "apollo_create_contact"]
)
async def test_non_read_tools_denied(tool):
    result = await ReadPolicy("apollo", apollo.TOOLS).evaluate(
        PolicyEvaluationContext(
            actor_id="fixture", action="call_tool", resource_id=tool
        )
    )
    assert result.decision == PolicyDecision.DENY


@pytest.mark.parametrize("page,size", [(0, 20), (501, 20), (1, 0), (1, 101)])
def test_pagination_limits(page, size):
    with pytest.raises(ValueError):
        apollo.pagination(page, size)


async def test_company_search_disabled_without_any_provider_call(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Provider must not be called")

    monkeypatch.setattr(apollo, "apollo_request", unexpected)
    tool = await server().get_tool("apollo_search_companies")
    with pytest.raises(ValueError, match="credits"):
        await tool.fn(company_name="Example")


@pytest.mark.parametrize(
    "tool,args,path,scope",
    [
        (
            "apollo_search_people",
            {
                "keywords": "engineering",
                "job_titles": ["CTO"],
                "company_domains": ["example.com"],
            },
            "mixed_people/api_search",
            apollo.PEOPLE_SCOPE,
        ),
        (
            "apollo_search_companies",
            {"company_name": "Example"},
            "mixed_companies/search",
            apollo.COMPANY_SCOPE,
        ),
        ("apollo_profile", {}, "users/api_profile", apollo.PROFILE_SCOPE),
    ],
)
async def test_tool_mapping(monkeypatch, tool, args, path, scope):
    async def request(actual_path, actual_scope, params=None):
        assert actual_path == path and actual_scope == scope
        if tool == "apollo_search_people":
            assert params is not None
            assert params["person_titles[]"] == ["CTO"]
            assert params["q_organization_domains_list[]"] == ["example.com"]
        return {"fixture": True}

    monkeypatch.setattr(apollo, "apollo_request", request)
    registered = await server(True).get_tool(tool)
    assert await registered.fn(**args) == {"fixture": True}


@pytest.mark.parametrize(
    "path,scope,method",
    [
        ("mixed_people/api_search", apollo.PEOPLE_SCOPE, "POST"),
        ("mixed_companies/search", apollo.COMPANY_SCOPE, "POST"),
        ("users/api_profile", apollo.PROFILE_SCOPE, "GET"),
    ],
)
async def test_wire_request_uses_user_token_and_exact_endpoint(
    monkeypatch, path, scope, method
):
    monkeypatch.setattr(
        apollo,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[scope]),
    )
    original = httpx.AsyncClient

    def handler(request):
        assert (
            request.url.host == "api.apollo.io"
            and request.url.path == "/api/v1/" + path
        )
        assert request.method == method
        assert request.headers["authorization"] == "Bearer fixture-token"
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json={"items": []})

    monkeypatch.setattr(
        apollo.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await apollo.apollo_request(path, scope) == {"items": []}


async def test_scope_required(monkeypatch):
    monkeypatch.setattr(
        apollo,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture", scopes=[apollo.PROFILE_SCOPE]),
    )
    with pytest.raises(ValueError, match="scope"):
        await apollo.apollo_request("mixed_people/api_search", apollo.PEOPLE_SCOPE)


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
async def test_errors_hide_provider_body(monkeypatch, status):
    monkeypatch.setattr(
        apollo,
        "get_access_token",
        lambda: SimpleNamespace(token="fixture-token", scopes=[apollo.PROFILE_SCOPE]),
    )
    original = httpx.AsyncClient
    monkeypatch.setattr(
        apollo.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(status, json={"error": "private-details"})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ValueError) as exc:
        await apollo.apollo_request("users/api_profile", apollo.PROFILE_SCOPE)
    assert "private-details" not in str(exc.value) and "fixture-token" not in str(
        exc.value
    )


@pytest.mark.parametrize(
    "payload,status,subject",
    [
        ({"id": "user-1"}, 200, "user-1"),
        ({"user": {"id": "user-2"}}, 200, "user-2"),
        ({}, 200, None),
        ({"id": "user-1"}, 401, None),
        ([], 200, None),
    ],
)
async def test_identity_verification(monkeypatch, payload, status, subject):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        apollo.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(status, json=payload)
            ),
            **kwargs,
        ),
    )
    token = await apollo.ApolloIdentityVerifier().verify_token("fixture")
    assert (token.subject if token else None) == subject


def test_oauth_url_preserves_apollo_fragment_route_and_cost_scope_opt_in():
    auth = apollo.create_oauth(
        "fixture", "fixture-secret", "https://apollo.example.test"
    )
    url = auth._build_upstream_authorize_url("state123", {})
    parsed = urlsplit(url)
    assert parsed.scheme == "https" and parsed.netloc == "app.apollo.io"
    route, query = parsed.fragment.split("?", 1)
    assert route == "/oauth/authorize"
    params = parse_qs(query)
    assert params["state"] == ["state123"]
    assert params["redirect_uri"] == ["https://apollo.example.test/auth/callback"]
    assert apollo.PEOPLE_SCOPE in params["scope"][0]
    assert apollo.COMPANY_SCOPE not in params["scope"][0]
    assert apollo.PEOPLE_SCOPE in auth._prepare_scopes_for_upstream_refresh([])


@pytest.mark.parametrize(
    "client,secret,url",
    [
        ("", "", "https://apollo.example.test"),
        ("id", "secret", "http://localhost:9116"),
        ("id", "secret", ""),
    ],
)
def test_unconfigured_startup_denied(client, secret, url):
    with pytest.raises(ValueError):
        apollo.create_oauth(client, secret, url)
