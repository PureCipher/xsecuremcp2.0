import pytest
from starlette.testclient import TestClient

from purecipher import PureCipherRegistry, consumer_cloud, consumer_runtime
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


@pytest.mark.parametrize(
    "product,tool,args",
    [
        ("grafana", "grafana_search_dashboards", {}),
        ("sonarqube", "sonarqube_search_issues", {"project": "project"}),
        ("n8n", "n8n_list_workflows", {}),
        ("jira", "jira_get_issue", {"issue_key": "EX-1"}),
        ("atlassian", "confluence_list_pages", {}),
        ("dynatrace", "dynatrace_list_entities", {}),
        ("firecrawl", "firecrawl_search", {"query": "test"}),
        ("stripe", "stripe_get_balance", {}),
        ("github", "github_list_repositories", {}),
        ("github-reference", "github_reference_list_repositories", {}),
        ("slack", "slack_list_channels", {}),
        ("slack-archived", "slack_reference_list_channels", {}),
        ("huggingface", "huggingface_search_models", {}),
        ("notion", "notion_search", {}),
        ("outlook", "outlook_list_messages", {}),
        ("onedrive", "onedrive_list_files", {}),
        ("apollo", "apollo_search_people", {"job_title": "Engineer"}),
    ],
)
def test_cloud_profile_isolates_owner_and_revokes(monkeypatch, product, tool, args):
    key = consumer_cloud.PRODUCTS[product][0]
    extra = {"BASE_URL": "https://service.example", "ACCOUNT_EMAIL": "user@example.com"}
    if product in consumer_cloud.CUSTOM:
        extra[consumer_cloud.BASE_KEYS[product]] = extra.pop("BASE_URL")
    if product not in consumer_cloud.CUSTOM:
        extra = {}
    elif product not in {"jira", "atlassian"}:
        extra.pop("ACCOUNT_EMAIL")
    enabled(monkeypatch)
    app = PureCipherRegistry(
        signing_secret="test-secret",
        auth_settings=registry()._auth_settings,
        enable_contracts=False,
        enable_consent=False,
        enable_provenance=False,
        enable_reflexive=False,
    )
    seen = []

    async def get(product, path, auth, params=None, body=None, **kwargs):
        seen.append((product, auth.copy(), params))
        return {"ok": True, "valid": True, "data": []}

    monkeypatch.setattr(consumer_cloud, "request", get)
    from fastmcp.server.security.gateway.tool_marketplace import PublishStatus

    listing = app._marketplace().publish(
        "purecipher-" + product,
        author="purecipher",
        version="1",
        status=PublishStatus.PUBLISHED,
        metadata={
            "introspection": {"tool_names": [tool]},
            "deployment_ready": True,
            "live_tested": False,
        },
    )
    monkeypatch.setattr(
        app,
        "_get_public_listing",
        lambda name: listing if name == listing.tool_name else None,
    )
    with TestClient(app.http_app(stateless_http=True, json_response=True)) as client:
        login(client)
        conn = add(client, product, {key: "alice-key", **extra})
        assert client.post(
            "/registry/workspace/connections/" + conn["id"] + "/verify"
        ).json()["runtime_ready"]
        entry = client.post(
            "/registry/workspace/clients", json={"display_name": "My client"}
        ).json()
        profile = client.post(
            "/registry/workspace/profiles",
            json={
                "name": "Search",
                "status": "active",
                "client_ids": [entry["client"]["client_id"]],
                "servers": [
                    {
                        "listing_id": listing.listing_id,
                        "tools": [tool],
                        "connection_id": conn["id"],
                    }
                ],
            },
        ).json()
        assert "id" in profile, profile
        headers = {
            "Authorization": "Bearer " + entry["token"],
            "Accept": "application/json, text/event-stream",
        }
        path = "/mcp/profiles/" + profile["id"]
        rpc = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
        response = client.post(path, headers=headers, json=rpc)
        assert (
            response.status_code == 200
            and "error" not in response.json()
            and not response.json().get("result", {}).get("isError")
        ), response.text
        assert seen[-1][1] == consumer_cloud.headers(
            product, {key: "alice-key", **extra}
        )
        assert (
            "alice-key" not in response.text and consumer_runtime._ACCESS.get() is None
        )
        login(client, "bob")
        add(client, product, {key: "bob-key", **extra})
        assert (
            client.post(
                "/registry/workspace/profiles", json={**profile, "id": None}
            ).status_code
            == 400
        )
        login(client)
        client.post("/registry/workspace/connections/" + conn["id"] + "/disconnect")
        count = len(seen)
        assert client.post(path, headers=headers, json=rpc).status_code == 403
        assert len(seen) == count
