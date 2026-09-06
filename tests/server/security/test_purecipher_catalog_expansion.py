"""Offline security and request-boundary checks for the new preparation packages."""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from examples.securemcp.business_integrations import catalog_adapter as catalog
from examples.securemcp.business_integrations import huggingface_server as hf
from examples.securemcp.business_integrations import stripe_server as stripe
from fastmcp import Client, FastMCP
from purecipher.registry import _parse_manifest


def auth():
    return stripe.create_oauth(
        "fixture-client", "fixture-key", "https://stripe.example.test"
    )


@pytest.mark.parametrize(
    "module,tool,args",
    [
        (stripe, "stripe_get_balance", {}),
        (hf, "hf_get_model", {"repository": "owner/model"}),
    ],
)
async def test_secure_discovery_consent_and_http(module, tool, args, caplog):
    app = module.create_server(auth())
    assert app.security_context.provenance_ledger is not None
    assert app.security_context.introspection_engine is not None
    async with Client(app) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == module.TOOLS
        assert all(t.annotations.read_only_hint for t in tools)
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool(tool, args)
    assert "ConsentRequiredError" in caplog.text
    with TestClient(app.http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


@pytest.mark.parametrize(
    "repository",
    [
        "../secret",
        "org/a/b",
        "org/%2fsecret",
        "org/a?x",
        "org/",
        "",
        "https://evil.test/x",
    ],
)
def test_hf_repository_path_rejected(repository):
    with pytest.raises(ValueError):
        hf.repo_path(repository)


@pytest.mark.parametrize(
    "name,args,path,params",
    [
        ("hf_get_model", {"repository": "owner/model"}, "models/owner/model", None),
        ("hf_get_dataset", {"repository": "owner/data"}, "datasets/owner/data", None),
        (
            "hf_search_models",
            {"search": "tiny", "limit": 3},
            "models",
            {"search": "tiny", "limit": 3},
        ),
        (
            "hf_search_datasets",
            {"search": "tiny", "limit": 3},
            "datasets",
            {"search": "tiny", "limit": 3},
        ),
    ],
)
async def test_hf_endpoint_mapping(monkeypatch, name, args, path, params):
    async def read(base, requested, query=None):
        assert (
            base == "https://huggingface.co/api/"
            and requested == path
            and query == params
        )
        return {"ok": True}

    monkeypatch.setattr(hf, "read_json", read)
    tool = await hf.create_server(auth()).get_tool(name)
    assert tool is not None
    assert await tool.fn(**args) == {"ok": True}


async def test_stripe_summaries_do_not_return_client_secrets(monkeypatch):
    async def read(base, path, params=None):
        assert base == stripe.BASE and path == "payment_intents"
        assert params == {"limit": 2, "starting_after": "pi_previous"}
        return {
            "data": [
                {
                    "id": "pi_test",
                    "amount": 100,
                    "client_secret": "must-not-return",
                    "payment_method": {"card": "private"},
                }
            ],
            "has_more": True,
        }

    monkeypatch.setattr(stripe, "read_json", read)
    tool = await stripe.create_server(auth()).get_tool("stripe_list_payment_intents")
    assert tool is not None
    assert await tool.fn(limit=2, starting_after="pi_previous") == {
        "data": [{"id": "pi_test", "amount": 100}],
        "has_more": True,
    }


@pytest.mark.parametrize(
    "limit,cursor", [(0, ""), (101, ""), (2, "in_wrong"), (2, "pi_a/b"), (2, "pi_%2f")]
)
def test_stripe_pagination_rejected(limit, cursor):
    with pytest.raises(ValueError):
        stripe.list_params(limit, cursor, "pi_")


async def test_stripe_token_exchange_uses_developer_key_as_basic_username():
    proxy = auth()
    client = proxy._create_upstream_oauth_client()
    try:
        data, headers = {"grant_type": "authorization_code", "code": "fixture-code"}, {}
        client._apply_client_auth(data, headers)
        assert base64.b64decode(headers["Authorization"].split()[1]) == b"fixture-key:"
        assert "client_secret" not in data and "client_id" not in data
        assert proxy.required_scopes == ["stripe_apps"]
        assert proxy._uses_alternate_verification()
    finally:
        await client.aclose()


@pytest.mark.parametrize("module", [stripe, hf])
@pytest.mark.parametrize(
    "values",
    [
        ("", "", "https://a.test"),
        ("id", "secret", "http://a.test"),
        ("id", "secret", "https://user@a.test"),
    ],
)
def test_oauth_fails_without_valid_configuration(module, values):
    with pytest.raises(ValueError):
        module.create_oauth(*values)


async def test_hf_scopes_exclude_write_and_inference():
    provider = hf.create_oauth(
        "fixture-client", "fixture-secret", "https://hf.example.test"
    )
    assert provider.required_scopes == ["openid", "profile", "read-repos"]


def upstream():
    app = FastMCP("fixture upstream")

    @app.tool
    def read_item(item: str) -> str:
        return item

    @app.tool
    def delete_everything() -> str:
        raise AssertionError("Unapproved tool must never execute")

    return Client(app)


@pytest.mark.parametrize("service", catalog.CATALOG)
async def test_all_catalog_adapters_require_auth_and_consent(service, caplog):
    app = catalog.create_server(
        service, auth(), upstream(), {"read_item"}, allow_archived=True
    )
    async with Client(app) as client:
        assert {t.name for t in await client.list_tools()} == catalog.TOOLS
        with pytest.raises(Exception, match="Internal server error"):
            await client.call_tool(
                "catalog_call",
                {"tool_name": "read_item", "arguments": {"item": "test"}},
            )
    assert "ConsentRequiredError" in caplog.text
    with TestClient(app.http_app()) as client:
        assert client.post("/mcp", json={}).status_code == 401


async def test_adapter_never_exposes_or_dispatches_unapproved_tools():
    allowed = {"read_item"}
    app = catalog.create_server("time", auth(), upstream(), allowed)
    allowed.add("delete_everything")
    discover = await app.get_tool("catalog_list_tools")
    call = await app.get_tool("catalog_call")
    assert discover is not None and call is not None
    assert [t["name"] for t in (await discover.fn())["tools"]] == ["read_item"]
    with pytest.raises(ValueError, match="not allowed"):
        await call.fn(tool_name="delete_everything", arguments={})
    result = await call.fn(tool_name="read_item", arguments={"item": "ok"})
    assert result[0]["text"] == "ok"


@pytest.mark.parametrize("service", ["slack-archived", "puppeteer"])
def test_archived_upstreams_blocked_by_default(service):
    with pytest.raises(ValueError, match="Archived"):
        catalog.create_server(service, auth(), upstream(), {"read_item"})


def test_empty_allowlist_fails_closed():
    with pytest.raises(ValueError, match="allowlist"):
        catalog.create_server("time", auth(), upstream(), set())


@pytest.mark.parametrize("service", [*catalog.CATALOG, "stripe", "huggingface"])
def test_preparation_manifests_match_sources_and_do_not_claim_live(service):
    root = Path(catalog.__file__).parent
    data = json.loads((root / (service + "-submission.json")).read_text())
    manifest = _parse_manifest(data["manifest"])
    assert manifest.author == "purecipher" and manifest.requires_consent
    meta = data["metadata"]
    assert meta["deployment_ready"] is False and meta["live_tested"] is False
    for filename, digest in meta["bundle_sha256"].items():
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == digest
