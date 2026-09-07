"""Provider-contract and isolation checks; no live credentials or provider calls."""

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import boto3
import pytest

from fastmcp.server.security.outbound import OutboundNetworkPolicy, OutboundRequestError
from purecipher import consumer_cloud
from purecipher import consumer_observability as obs
from purecipher.consumer_runtime import _ACCESS

START = "2026-09-01T00:00:00+00:00"
END = "2026-09-01T01:00:00+00:00"
WINDOW = {"start_time": START, "end_time": END}
ATOM = '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:op="http://a9.com/-/spec/opensearch/1.1/"><op:totalResults>1</op:totalResults><op:startIndex>0</op:startIndex><entry><id>https://arxiv.org/abs/2301.12345</id><title>Example paper</title><summary>An abstract</summary><published>2026-01-01</published><author><name>Researcher</name></author></entry></feed>'
WIKI = {
    "query": {
        "pages": [
            {
                "title": "MCP",
                "pageid": 5,
                "revisions": [
                    {
                        "revid": 10,
                        "timestamp": START,
                        "slots": {"main": {"content": "Article content"}},
                    }
                ],
            }
        ]
    }
}
AUTH = {"Authorization": "Bearer owner-only-test-token"}
VALUES = {
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "owner-test-key",
    "AWS_SECRET_ACCESS_KEY": "owner-test-secret",
    "AWS_SESSION_TOKEN": "owner-test-session",
    "param:url": "https://tenant.example/tenant",
}

# Each named operation must have a provider-wire contract case below.
HTTP = [
    (
        "grafana",
        "grafana_query_prometheus",
        {"datasource_uid": "metrics", "query": "up", **WINDOW},
        "/tenant/api/datasources/proxy/uid/metrics/api/v1/query_range",
        {
            "query": "up",
            "start": START,
            "end": END,
            "step": 300,
            "timeout": "10s",
            "limit": 20,
        },
        None,
        {"status": "success", "data": {"resultType": "matrix", "result": []}},
    ),
    (
        "grafana",
        "grafana_query_loki",
        {"datasource_uid": "logs", "query": '{app="mcp"} |= "error"', **WINDOW},
        "/tenant/api/datasources/proxy/uid/logs/loki/api/v1/query_range",
        {
            "query": '{app="mcp"} |= "error"',
            "start": START,
            "end": END,
            "limit": 100,
            "direction": "backward",
        },
        None,
        {"status": "success", "data": {"resultType": "streams", "result": []}},
    ),
    (
        "grafana",
        "grafana_get_dashboard",
        {"uid": "dash-1"},
        "/tenant/api/dashboards/uid/dash-1",
        {},
        None,
        {"dashboard": {"uid": "dash-1"}},
    ),
    (
        "grafana",
        "grafana_list_datasources",
        {"max_results": 1},
        "/tenant/api/datasources",
        {},
        None,
        [
            {
                "uid": "ds",
                "name": "Metrics",
                "type": "prometheus",
                "password": "not-returned",
            }
        ],
    ),
    (
        "grafana",
        "grafana_get_datasource",
        {"uid": "ds"},
        "/tenant/api/datasources/uid/ds",
        {},
        None,
        {
            "uid": "ds",
            "name": "Metrics",
            "type": "prometheus",
            "secureJsonData": {"secret": "not-returned"},
        },
    ),
    (
        "grafana",
        "grafana_list_alert_rules",
        {"max_results": 1},
        "/tenant/api/v1/provisioning/alert-rules",
        {},
        None,
        [{"uid": "alert", "title": "High CPU", "data": [{"secret": "not-returned"}]}],
    ),
    (
        "dynatrace",
        "dynatrace_get_entity",
        {"entity_id": "HOST-0123456789ABCDEF"},
        "/tenant/api/v2/entities/HOST-0123456789ABCDEF",
        {"fields": "properties,tags"},
        None,
        {"entityId": "HOST-0123456789ABCDEF"},
    ),
    (
        "dynatrace",
        "dynatrace_list_problems",
        {"max_results": 10},
        "/tenant/api/v2/problems",
        {"pageSize": 10, "from": "now-7d", "to": "now"},
        None,
        {"problems": [], "nextPageKey": "more"},
    ),
    (
        "dynatrace",
        "dynatrace_get_problem",
        {"problem_id": "PROBLEM-1"},
        "/tenant/api/v2/problems/PROBLEM-1",
        {},
        None,
        {"problemId": "PROBLEM-1"},
    ),
    (
        "dynatrace",
        "dynatrace_query_metric",
        {
            "metric_key": "builtin:host.cpu.usage",
            "entity_id": "HOST-0123456789ABCDEF",
            **WINDOW,
        },
        "/tenant/api/v2/metrics/query",
        {
            "metricSelector": "builtin:host.cpu.usage",
            "entitySelector": 'entityId("HOST-0123456789ABCDEF")',
            "from": START,
            "to": END,
            "resolution": "120",
        },
        None,
        {"result": []},
    ),
    (
        "sonarqube",
        "sonarqube_search_projects",
        {"query": "repo", "page_number": 2, "max_results": 10},
        "/tenant/api/components/search",
        {"qualifiers": "TRK", "q": "repo", "p": 2, "ps": 10},
        None,
        {"components": []},
    ),
    (
        "sonarqube",
        "sonarqube_get_project_measures",
        {"project": "org:repo", "metric_keys": ["coverage", "bugs"], "branch": "main"},
        "/tenant/api/measures/component",
        {"component": "org:repo", "metricKeys": "coverage,bugs", "branch": "main"},
        None,
        {"component": {"measures": []}},
    ),
    (
        "sonarqube",
        "sonarqube_get_quality_gate",
        {"project": "org:repo", "branch": "main"},
        "/tenant/api/qualitygates/project_status",
        {"projectKey": "org:repo", "branch": "main"},
        None,
        {"projectStatus": {"status": "OK"}},
    ),
    (
        "sonarqube",
        "sonarqube_list_project_analyses",
        {"project": "org:repo", "page_number": 2, "max_results": 10},
        "/tenant/api/project_analyses/search",
        {"project": "org:repo", "p": 2, "ps": 10},
        None,
        {"analyses": []},
    ),
    (
        "brave-search",
        "brave_news_search",
        {"query": "MCP", "count": 3, "freshness": "pw"},
        "https://api.search.brave.com/res/v1/news/search",
        {"q": "MCP", "count": 3, "freshness": "pw"},
        None,
        {"results": []},
    ),
    (
        "brave-search",
        "brave_image_search",
        {"query": "MCP", "count": 3},
        "https://api.search.brave.com/res/v1/images/search",
        {"q": "MCP", "count": 3},
        None,
        {"results": []},
    ),
    (
        "brave-search",
        "brave_video_search",
        {"query": "MCP", "count": 3},
        "https://api.search.brave.com/res/v1/videos/search",
        {"q": "MCP", "count": 3},
        None,
        {"results": []},
    ),
    (
        "firecrawl",
        "firecrawl_scrape_url",
        {"url": "https://public.example/page", "max_characters": 7},
        "https://api.firecrawl.dev/v2/scrape",
        {},
        {
            "url": "https://public.example/page",
            "formats": ["markdown"],
            "onlyMainContent": True,
            "timeout": 15000,
        },
        {
            "success": True,
            "data": {
                "markdown": "Example page content",
                "metadata": {"title": "Example"},
            },
        },
    ),
    (
        "firecrawl",
        "firecrawl_map_website",
        {"url": "https://public.example", "search": "docs", "max_results": 10},
        "https://api.firecrawl.dev/v2/map",
        {},
        {
            "url": "https://public.example",
            "search": "docs",
            "limit": 10,
            "includeSubdomains": False,
            "timeout": 15000,
        },
        {"success": True, "links": []},
    ),
    (
        "firecrawl",
        "firecrawl_get_credit_usage",
        {},
        "https://api.firecrawl.dev/v2/team/credit-usage",
        {},
        None,
        {"success": True, "data": {"remainingCredits": 50}},
    ),
    (
        "aws-documentation",
        "aws_search_documentation",
        {"query": "Lambda", "max_results": 1},
        "https://proxy.search.docs.aws.com/search",
        {"session": "fixture-session"},
        {
            "textQuery": {"input": "Lambda"},
            "contextAttributes": [{"key": "domain", "value": "docs.aws.amazon.com"}],
            "acceptSuggestionBody": "RawText",
            "locales": ["en_us"],
        },
        {
            "suggestions": [
                {
                    "textExcerptSuggestion": {
                        "title": "Lambda",
                        "link": "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html",
                        "summary": "Lambda guide",
                    }
                },
                {"textExcerptSuggestion": {"title": "More"}},
            ]
        },
    ),
    (
        "aws-documentation",
        "aws_recommend_documentation",
        {"url": "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html"},
        "https://api.contentrecs.docs.aws.com/v1/recommendations",
        {
            "path": "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html",
            "session": "fixture-session",
        },
        None,
        {"recommended": []},
    ),
    (
        "arxiv",
        "arxiv_get_paper",
        {"identifier": "2301.12345v2"},
        "https://export.arxiv.org/api/query",
        {"id_list": "2301.12345v2", "max_results": 1},
        None,
        ATOM,
    ),
    (
        "arxiv",
        "arxiv_recent_papers",
        {"category": "cs.AI", "start": 20, "max_results": 10},
        "https://export.arxiv.org/api/query",
        {
            "search_query": "cat:cs.AI",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 20,
            "max_results": 10,
        },
        None,
        ATOM,
    ),
    (
        "wikipedia",
        "wikipedia_get_article",
        {"title": "MCP", "max_characters": 7},
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "revisions",
            "titles": "MCP",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "rvlimit": 1,
            "redirects": 1,
        },
        None,
        WIKI,
    ),
    (
        "wikipedia",
        "wikipedia_article_history",
        {"title": "MCP", "max_results": 5, "next_token": "20260901|3"},
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "revisions",
            "titles": "MCP",
            "rvprop": "ids|timestamp|user|comment",
            "rvlimit": 5,
            "rvcontinue": "20260901|3",
            "continue": "||",
        },
        None,
        {"continue": {"rvcontinue": "more"}, "query": {"pages": []}},
    ),
    (
        "wikipedia",
        "wikipedia_article_links",
        {"title": "MCP", "max_results": 5, "next_token": "5|0|Next"},
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "links",
            "titles": "MCP",
            "pllimit": 5,
            "plcontinue": "5|0|Next",
            "continue": "||",
        },
        None,
        {"continue": {"plcontinue": "more"}, "query": {"pages": []}},
    ),
]
AWS = [
    (
        "aws-core",
        "aws_list_tagged_resources",
        {"resource_types": ["ec2:instance"], "max_results": 10, "next_token": "more"},
        "resourcegroupstaggingapi",
        "get_resources",
        {
            "ResourcesPerPage": 10,
            "ResourceTypeFilters": ["ec2:instance"],
            "PaginationToken": "more",
        },
    ),
    (
        "aws-core",
        "aws_list_regions",
        {},
        "ec2",
        "describe_regions",
        {"AllRegions": False},
    ),
    (
        "aws-core",
        "aws_list_instances",
        {"max_results": 10, "next_token": "more"},
        "ec2",
        "describe_instances",
        {"MaxResults": 10, "NextToken": "more"},
    ),
    (
        "cloudwatch",
        "cloudwatch_get_metric_statistics",
        {
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": {"InstanceId": "i-example"},
            **WINDOW,
        },
        "cloudwatch",
        "get_metric_statistics",
        {
            "Namespace": "AWS/EC2",
            "MetricName": "CPUUtilization",
            "StartTime": datetime.fromisoformat(START),
            "EndTime": datetime.fromisoformat(END),
            "Period": 300,
            "Statistics": ["Average"],
            "Dimensions": [{"Name": "InstanceId", "Value": "i-example"}],
        },
    ),
    (
        "cloudwatch",
        "cloudwatch_describe_alarms",
        {
            "name_prefix": "prod",
            "state": "ALARM",
            "max_results": 10,
            "next_token": "more",
        },
        "cloudwatch",
        "describe_alarms",
        {
            "MaxRecords": 10,
            "AlarmTypes": ["MetricAlarm", "CompositeAlarm"],
            "AlarmNamePrefix": "prod",
            "StateValue": "ALARM",
            "NextToken": "more",
        },
    ),
    (
        "cloudwatch",
        "cloudwatch_list_log_streams",
        {"log_group": "/aws/lambda/test", "max_results": 10, "next_token": "more"},
        "logs",
        "describe_log_streams",
        {
            "logGroupName": "/aws/lambda/test",
            "limit": 10,
            "orderBy": "LastEventTime",
            "descending": True,
            "nextToken": "more",
        },
    ),
    (
        "cloudwatch",
        "cloudwatch_filter_log_events",
        {
            "log_group": "/aws/lambda/test",
            "filter_pattern": "ERROR",
            "max_results": 10,
            "next_token": "more",
            **WINDOW,
        },
        "logs",
        "filter_log_events",
        {
            "logGroupName": "/aws/lambda/test",
            "startTime": int(datetime.fromisoformat(START).timestamp() * 1000),
            "endTime": int(datetime.fromisoformat(END).timestamp() * 1000),
            "filterPattern": "ERROR",
            "limit": 10,
            "nextToken": "more",
        },
    ),
]


class Registry:
    def __init__(self):
        self._consumer_products = set()
        self._consumer_tool_products = {}
        self.functions = {}
        self.annotations = {}

    def tool(self, **options):
        def decorate(function):
            assert function.__name__ not in self.functions
            self.functions[function.__name__] = function
            self.annotations[function.__name__] = options
            return function

        return decorate


@pytest.fixture
def registry():
    result = Registry()
    obs.register(result)
    return result


async def invoke(registry, product, name, arguments, *, context_product=None):
    token = _ACCESS.set(
        {
            "product": context_product or product,
            "headers": (
                {"X-Subscription-Token": "owner-only-test-token"}
                if product == "brave-search"
                else AUTH
            ),
            "values": VALUES,
        }
    )
    try:
        return await registry.functions[name](**arguments)
    finally:
        _ACCESS.reset(token)


@pytest.mark.parametrize(
    "product,name,args,url,params,body,payload", HTTP, ids=[case[1] for case in HTTP]
)
def test_http_contract(
    monkeypatch, registry, product, name, args, url, params, body, payload
):
    captured = []
    monkeypatch.setattr(obs, "uuid4", lambda: "fixture-session")
    monkeypatch.setattr(OutboundNetworkPolicy, "resolve", lambda self, url: url)

    async def outbound(destination, **kwargs):
        captured.append((destination, kwargs))
        return SimpleNamespace(
            status_code=200,
            content=(
                payload if isinstance(payload, str) else json.dumps(payload)
            ).encode(),
        )

    monkeypatch.setattr(obs, "async_secure_outbound_request", outbound)
    monkeypatch.setattr(consumer_cloud, "async_secure_outbound_request", outbound)
    result = asyncio.run(invoke(registry, product, name, args))
    assert len(captured) == 1
    destination, options = captured[0]
    parsed = urlsplit(destination)
    expected_url = "https://tenant.example" + url if url.startswith("/") else url
    assert parsed.scheme + "://" + parsed.netloc + parsed.path == expected_url
    assert parse_qs(parsed.query, keep_blank_values=True) == {
        key: [str(value)] for key, value in params.items()
    }
    assert options["method"] == ("POST" if body is not None else "GET")
    assert (json.loads(options["content"]) if options["content"] else None) == body
    assert options["max_response_bytes"] <= 2 * 1024 * 1024
    assert options["timeout"] == 20
    if product in {"arxiv", "aws-documentation", "wikipedia"}:
        assert "Authorization" not in options["headers"]
    elif product == "brave-search":
        assert options["headers"]["X-Subscription-Token"] == "owner-only-test-token"
    else:
        assert options["headers"]["Authorization"] == AUTH["Authorization"]
    assert "owner-only-test-token" not in str(result)
    assert "not-returned" not in str(result)
    if name == "firecrawl_scrape_url":
        assert result["markdown"] == "Example" and result["truncated"] is True
    if name == "wikipedia_get_article":
        assert (
            result["wikitext"] == "Article"
            and result["revision_id"] == 10
            and result["truncated"] is True
        )
    if name == "aws_search_documentation":
        assert len(result["results"]) == 1 and result["truncated"] is True
    if product == "arxiv":
        assert options["headers"]["Accept"] == "application/atom+xml"
        assert result["papers"][0]["title"] == "Example paper"


@pytest.mark.parametrize(
    "product,name,args,service,operation,params", AWS, ids=[case[1] for case in AWS]
)
def test_aws_sigv4_contract(
    monkeypatch, registry, product, name, args, service, operation, params
):
    captured = []
    closed = []

    class Client:
        def __getattr__(self, method):
            def call(**kwargs):
                captured.append((method, kwargs))
                return {"items": [], "ResponseMetadata": {"private": "hidden"}}

            return call

        def close(self):
            closed.append(True)

    def client(service_name, **kwargs):
        captured.append((service_name, kwargs))
        return Client()

    monkeypatch.setattr(boto3, "client", client)
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://attacker.example")
    result = asyncio.run(invoke(registry, product, name, args))
    client_service, options = captured[0]
    assert client_service == service
    host = {
        "resourcegroupstaggingapi": "tagging",
        "ec2": "ec2",
        "cloudwatch": "monitoring",
        "logs": "logs",
    }[service]
    assert options["endpoint_url"] == f"https://{host}.us-east-1.amazonaws.com"
    assert options["aws_access_key_id"] == VALUES["AWS_ACCESS_KEY_ID"]
    assert options["aws_secret_access_key"] == VALUES["AWS_SECRET_ACCESS_KEY"]
    assert options["aws_session_token"] == VALUES["AWS_SESSION_TOKEN"]
    assert captured[1] == (operation, params)
    assert closed == [True]
    assert result == {"items": []}


ALL = [(case[0], case[1], case[2]) for case in HTTP + AWS]


@pytest.mark.parametrize("product,name,args", ALL, ids=[case[1] for case in ALL])
def test_every_tool_requires_matching_product_context(
    monkeypatch, registry, product, name, args
):
    async def forbidden(*args, **kwargs):
        pytest.fail("A denied call reached outbound transport")

    monkeypatch.setattr(obs, "public_request", forbidden)
    monkeypatch.setattr(consumer_cloud, "request", forbidden)
    monkeypatch.setattr(obs.consumer_aws, "execute", forbidden)
    for context_product in [None, "unrelated-product"]:
        if context_product is None:
            with pytest.raises(ValueError, match="active profile"):
                asyncio.run(registry.functions[name](**args))
        else:
            with pytest.raises(ValueError, match="active profile"):
                asyncio.run(
                    invoke(
                        registry, product, name, args, context_product=context_product
                    )
                )


def test_inventory_exactly_matches_wire_tests_and_effect_annotations(registry):
    assert set(registry.functions) == {name for _, name, _ in ALL}
    assert len(registry.functions) == 34
    for product, name, _ in ALL:
        options = registry.annotations[name]
        billable = name in {"firecrawl_scrape_url", "firecrawl_map_website"}
        assert options["annotations"]["readOnlyHint"] is not billable
        assert options["annotations"]["idempotentHint"] is not billable
        assert options["annotations"]["destructiveHint"] is False
        assert options["annotations"]["openWorldHint"] is True
        assert product in options["tags"]
        assert f"resource:{product}" in options["tags"]
        assert ("risk:high" if billable else "risk:low") in options["tags"]
        assert registry._consumer_tool_products[name] == product


@pytest.mark.parametrize(
    "product,name,args",
    [
        ("aws-core", "aws_list_instances", {"max_results": 4}),
        (
            "aws-core",
            "aws_list_tagged_resources",
            {"resource_types": ["ec2:instance,iam:user"]},
        ),
        (
            "cloudwatch",
            "cloudwatch_get_metric_statistics",
            {
                "namespace": "AWS/EC2",
                "metric_name": "CPU",
                "start_time": START,
                "end_time": "2026-09-09T00:00:00Z",
            },
        ),
        (
            "cloudwatch",
            "cloudwatch_get_metric_statistics",
            {
                "namespace": "AWS/EC2",
                "metric_name": "CPU",
                "start_time": "2026-09-01T00:00:00",
                "end_time": END,
            },
        ),
        (
            "cloudwatch",
            "cloudwatch_get_metric_statistics",
            {
                "namespace": "AWS/EC2",
                "metric_name": "CPU",
                **WINDOW,
                "period_seconds": 1,
            },
        ),
        (
            "cloudwatch",
            "cloudwatch_filter_log_events",
            {"log_group": "logs", **WINDOW, "max_results": 101},
        ),
        ("grafana", "grafana_get_dashboard", {"uid": "../datasources"}),
        (
            "grafana",
            "grafana_query_prometheus",
            {"datasource_uid": "../admin", "query": "up", **WINDOW},
        ),
        (
            "grafana",
            "grafana_query_prometheus",
            {"datasource_uid": "ds", "query": "up", "step_seconds": 1, **WINDOW},
        ),
        (
            "grafana",
            "grafana_query_prometheus",
            {"datasource_uid": "ds", "query": "up", "max_series": 101, **WINDOW},
        ),
        (
            "grafana",
            "grafana_query_loki",
            {"datasource_uid": "ds", "query": 'rate({app="x"}[5m])', **WINDOW},
        ),
        (
            "grafana",
            "grafana_query_loki",
            {
                "datasource_uid": "ds",
                "query": '{app="x"}',
                "max_results": 101,
                **WINDOW,
            },
        ),
        ("dynatrace", "dynatrace_get_problem", {"problem_id": "a%2F..%2Fadmin"}),
        (
            "dynatrace",
            "dynatrace_query_metric",
            {
                "metric_key": "builtin:host.cpu:splitBy()",
                "entity_id": "HOST-1234",
                **WINDOW,
            },
        ),
        (
            "dynatrace",
            "dynatrace_query_metric",
            {
                "metric_key": "builtin:host.cpu",
                "entity_id": 'HOST-1234"),type(HOST)',
                **WINDOW,
            },
        ),
        (
            "sonarqube",
            "sonarqube_get_project_measures",
            {"project": "repo", "metric_keys": ["coverage,bugs"]},
        ),
        ("brave-search", "brave_news_search", {"query": "x", "count": 21}),
        ("brave-search", "brave_image_search", {"query": "x " * 51}),
        ("firecrawl", "firecrawl_scrape_url", {"url": "http://public.example"}),
        (
            "firecrawl",
            "firecrawl_map_website",
            {"url": "https://user:pass@public.example"},
        ),
        (
            "aws-documentation",
            "aws_recommend_documentation",
            {"url": "https://docs.aws.amazon.com.evil.example/page"},
        ),
        ("arxiv", "arxiv_get_paper", {"identifier": "../../etc/passwd"}),
        ("arxiv", "arxiv_recent_papers", {"category": "cs.AI OR all"}),
        ("wikipedia", "wikipedia_get_article", {"title": "One|Two"}),
        (
            "wikipedia",
            "wikipedia_article_links",
            {"title": "MCP", "next_token": "x" * 4097},
        ),
    ],
)
def test_invalid_unbounded_or_path_injecting_arguments_never_reach_provider(
    monkeypatch, registry, product, name, args
):
    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid input reached outbound transport")

    monkeypatch.setattr(obs, "public_request", forbidden)
    monkeypatch.setattr(consumer_cloud, "request", forbidden)
    monkeypatch.setattr(obs.consumer_aws, "execute", forbidden)
    with pytest.raises(ValueError):
        asyncio.run(invoke(registry, product, name, args))


def test_dynatrace_continuation_omits_original_filters(monkeypatch, registry):
    captured = []

    async def cloud(product, path, auth, params):
        captured.append(params)
        return {"problems": []}

    monkeypatch.setattr(consumer_cloud, "request", cloud)
    asyncio.run(
        invoke(
            registry,
            "dynatrace",
            "dynatrace_list_problems",
            {"next_page_key": "page-two"},
        )
    )
    assert captured == [{"nextPageKey": "page-two"}]


@pytest.mark.parametrize(
    "body",
    [
        '<!DOCTYPE feed [<!ENTITY x "attack">]><feed>&x;</feed>',
        "<not-atom/>",
        "<feed>",
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors</id></entry></feed>',
    ],
)
def test_arxiv_rejects_entities_malformed_xml_and_provider_errors(body):
    with pytest.raises(ValueError):
        obs.parse_papers(body, 1)


@pytest.mark.parametrize(
    "status,body",
    [
        (401, b'{"token":"secret"}'),
        (403, b"{}"),
        (429, b"{}"),
        (200, b"not-json"),
        (200, b'{"success":false,"error":"secret"}'),
    ],
)
def test_provider_errors_do_not_echo_response_or_credentials(monkeypatch, status, body):
    async def outbound(*args, **kwargs):
        return SimpleNamespace(status_code=status, content=body)

    monkeypatch.setattr(obs, "async_secure_outbound_request", outbound)
    with pytest.raises(ValueError) as error:
        asyncio.run(
            obs.public_request("https://api.firecrawl.dev/v2/map", headers=AUTH)
        )
    assert "secret" not in str(error.value) and "owner-only" not in str(error.value)


def test_transport_and_response_limits_fail_closed(monkeypatch, registry):
    async def outbound(*args, **kwargs):
        raise OutboundRequestError("secret upstream detail")

    monkeypatch.setattr(obs, "async_secure_outbound_request", outbound)
    with pytest.raises(ValueError, match="could not be read safely"):
        asyncio.run(
            obs.public_request("https://api.firecrawl.dev/v2/map", headers=AUTH)
        )
    with pytest.raises(ValueError, match="512 KiB"):
        obs.bounded({"too_large": "x" * obs.MAX_RESPONSE_BYTES})


def test_firecrawl_private_target_is_rejected_before_provider(monkeypatch, registry):
    original = OutboundNetworkPolicy.resolve

    def private(self, url):
        policy = OutboundNetworkPolicy(
            resolver=lambda host, port: [(2, 1, 6, "", ("127.0.0.1", port))]
        )
        return original(policy, url)

    monkeypatch.setattr(OutboundNetworkPolicy, "resolve", private)
    with pytest.raises(ValueError, match="protected address"):
        asyncio.run(
            invoke(
                registry,
                "firecrawl",
                "firecrawl_scrape_url",
                {"url": "https://internal.example"},
            )
        )


def test_custom_provider_validation_is_retained(monkeypatch, registry):
    from purecipher.consumer_runtime import _ACCESS

    token = _ACCESS.set(
        {
            "product": "grafana",
            "headers": AUTH,
            "values": {"param:url": "https://user:secret@tenant.example"},
        }
    )
    try:
        with pytest.raises(ValueError, match="HTTPS base URL"):
            asyncio.run(registry.functions["grafana_get_dashboard"](uid="dash"))
    finally:
        _ACCESS.reset(token)


@pytest.mark.parametrize("name", ["firecrawl_scrape_url", "firecrawl_map_website"])
@pytest.mark.parametrize(
    "change",
    [
        "disconnect",
        "connection_revision",
        "profile_revision",
        "profile_deleted",
        "tool_removed",
        "not_ready",
        "client_revoked",
        "unchanged",
    ],
)
def test_firecrawl_rechecks_persisted_access_after_target_dns(
    monkeypatch, registry, name, change
):
    from purecipher import consumer_runtime, workspace

    registry._workspace = {"connection": {"revision": 1}, "profile": {"revision": 2}}
    allowed = {name}
    ready = [True]
    active_client = [True]
    sent = []

    def current_client(reg, profile, client):
        assert reg is registry and profile == "profile" and client == "client"
        if not active_client[0]:
            raise ValueError("Connection or profile changed; client access revoked")
        return {"client_id": "fresh-client"}

    def allowed_tools(reg, profile, client):
        assert client == {"client_id": "fresh-client"}
        return allowed

    monkeypatch.setattr(consumer_runtime, "current_profile_client", current_client)
    monkeypatch.setattr(workspace, "allowed_profile_tools", allowed_tools)
    monkeypatch.setattr(
        consumer_runtime, "runtime_ready", lambda reg, connection: ready[0]
    )

    async def resolve(url):
        # Simulates persisted changes while public-target DNS resolution was awaited.
        if change == "disconnect":
            registry._workspace.pop("connection")
        elif change == "connection_revision":
            registry._workspace["connection"]["revision"] += 1
        elif change == "profile_revision":
            registry._workspace["profile"]["revision"] += 1
        elif change == "profile_deleted":
            registry._workspace.pop("profile")
        elif change == "tool_removed":
            allowed.clear()
        elif change == "not_ready":
            ready[0] = False
        elif change == "client_revoked":
            active_client[0] = False
        return url

    async def request(url, **options):
        sent.append((url, options))
        return {"data": {"markdown": "Page"}, "links": []}

    monkeypatch.setattr(obs, "public_target", resolve)
    monkeypatch.setattr(obs, "public_request", request)
    token = _ACCESS.set(
        {
            "product": "firecrawl",
            "headers": AUTH,
            "values": VALUES,
            "registry": registry,
            "profile_id": "profile",
            "client": "client",
            "connection_id": "connection",
            "tool_name": name,
            "connection_revision": 1,
            "profile_revision": 2,
        }
    )
    try:
        if change == "unchanged":
            asyncio.run(registry.functions[name](url="https://public.example"))
            assert len(sent) == 1 and sent[0][1]["billable"] is True
            assert sent[0][1]["headers"] == AUTH
        else:
            with pytest.raises(ValueError, match="Connection or profile changed"):
                asyncio.run(registry.functions[name](url="https://public.example"))
            assert sent == []
    finally:
        _ACCESS.reset(token)


@pytest.mark.parametrize(
    "failure", ["timeout", "server_error", "invalid_json", "unexpected_shape"]
)
@pytest.mark.parametrize("name", ["firecrawl_scrape_url", "firecrawl_map_website"])
def test_billable_firecrawl_failure_does_not_retry_or_claim_no_charge(
    monkeypatch, registry, name, failure
):
    attempts = []
    monkeypatch.setattr(OutboundNetworkPolicy, "resolve", lambda self, url: url)

    async def outbound(url, **options):
        attempts.append(url)
        if failure == "timeout":
            raise OutboundRequestError("secret transport detail")
        return SimpleNamespace(
            status_code=503 if failure == "server_error" else 200,
            content=b"invalid" if failure == "invalid_json" else b"[]",
        )

    monkeypatch.setattr(obs, "async_secure_outbound_request", outbound)
    with pytest.raises(
        ValueError, match="outcome is unknown and credits may have been consumed"
    ) as error:
        asyncio.run(
            invoke(registry, "firecrawl", name, {"url": "https://public.example"})
        )
    assert len(attempts) == 1 and "secret" not in str(error.value)


@pytest.mark.parametrize(
    "name,payload",
    [
        ("firecrawl_scrape_url", {"success": True}),
        ("firecrawl_scrape_url", {"data": {}}),
        ("firecrawl_scrape_url", {"data": {"markdown": ["not markdown"]}}),
        ("firecrawl_map_website", {"success": True}),
        ("firecrawl_map_website", {"links": "not links"}),
    ],
)
def test_billable_unexpected_result_is_not_reported_as_empty_success(
    monkeypatch, registry, name, payload
):
    async def request(*args, **kwargs):
        return payload

    monkeypatch.setattr(OutboundNetworkPolicy, "resolve", lambda self, url: url)
    monkeypatch.setattr(obs, "public_request", request)
    with pytest.raises(ValueError, match="outcome is unknown"):
        asyncio.run(
            invoke(registry, "firecrawl", name, {"url": "https://public.example"})
        )


def test_firecrawl_map_caps_provider_links_explicitly(monkeypatch, registry):
    async def request(*args, **kwargs):
        return {
            "success": True,
            "links": [
                {"url": "https://public.example/1"},
                {"url": "https://public.example/2"},
            ],
        }

    monkeypatch.setattr(OutboundNetworkPolicy, "resolve", lambda self, url: url)
    monkeypatch.setattr(obs, "public_request", request)
    result = asyncio.run(
        invoke(
            registry,
            "firecrawl",
            "firecrawl_map_website",
            {"url": "https://public.example", "max_results": 1},
        )
    )
    assert result == {
        "success": True,
        "links": [{"url": "https://public.example/1"}],
        "truncated": True,
    }


@pytest.mark.parametrize(
    "name,args,payload",
    [
        (
            "grafana_query_prometheus",
            {"query": "up", "max_series": 1},
            {"status": "success", "data": {"result": [{}, {}]}},
        ),
        (
            "grafana_query_prometheus",
            {"query": "up"},
            {"status": "error", "error": "private query"},
        ),
        (
            "grafana_query_loki",
            {"query": '{app="x"}'},
            {"status": "success", "data": {"resultType": "matrix", "result": []}},
        ),
        (
            "grafana_query_loki",
            {"query": '{app="x"}', "max_results": 1},
            {
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [{"values": [[1, "a"], [2, "b"]]}],
                },
            },
        ),
    ],
)
def test_grafana_queries_reject_errors_and_out_of_bound_results(
    monkeypatch, registry, name, args, payload
):
    async def request(*args, **kwargs):
        return payload

    monkeypatch.setattr(consumer_cloud, "request", request)
    with pytest.raises(ValueError):
        asyncio.run(
            invoke(
                registry, "grafana", name, {"datasource_uid": "ds", **WINDOW, **args}
            )
        )


@pytest.mark.parametrize(
    "product,name,args,service,operation,params", AWS, ids=[case[1] for case in AWS]
)
def test_aws_parameters_validate_and_sign_with_real_botocore_models(
    product, name, args, service, operation, params
):
    # Build/sign requests with the installed service model; never send them.
    host = {
        "resourcegroupstaggingapi": "tagging",
        "ec2": "ec2",
        "cloudwatch": "monitoring",
        "logs": "logs",
    }[service]
    client = boto3.client(
        service,
        region_name="us-east-1",
        endpoint_url=f"https://{host}.us-east-1.amazonaws.com",
        aws_access_key_id=VALUES["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=VALUES["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=VALUES["AWS_SESSION_TOKEN"],
    )
    try:
        operation_model = client.meta.service_model.operation_model(
            client.meta.method_to_api_mapping[operation]
        )
        request_dict = client._convert_to_request_dict(
            params, operation_model, endpoint_url=client.meta.endpoint_url
        )
        prepared = client._endpoint.create_request(request_dict, operation_model)
        authorization = prepared.headers["Authorization"].decode()
        assert authorization.startswith("AWS4-HMAC-SHA256 ")
        assert "Credential=owner-test-key/" in authorization
        assert "/us-east-1/" in authorization
        assert (
            prepared.headers["X-Amz-Security-Token"].decode()
            == VALUES["AWS_SESSION_TOKEN"]
        )
        assert prepared.url.startswith(f"https://{host}.us-east-1.amazonaws.com/")
    finally:
        client.close()


def test_registered_runtime_schemas_preserve_enums_and_tool_effects(monkeypatch):
    from fastmcp.exceptions import ValidationError
    from tests.server.security.test_consumer_runtime import enabled

    app = enabled(monkeypatch)
    if "aws_list_tagged_resources" not in app._consumer_tool_products:
        obs.register(app)

    async def check():
        tools = {tool.name: tool for tool in await app.list_tools()}
        for _, name, _ in ALL:
            assert name in tools
            assert tools[name].annotations.read_only_hint is (
                name not in {"firecrawl_scrape_url", "firecrawl_map_website"}
            )
        with pytest.raises(ValidationError):
            await tools["brave_news_search"].run(
                {"query": "MCP", "freshness": "unrecognized"}
            )
        with pytest.raises(ValidationError):
            await tools["cloudwatch_get_metric_statistics"].run(
                {
                    "namespace": "AWS/EC2",
                    "metric_name": "CPU",
                    **WINDOW,
                    "statistic": "arbitrary_operation",
                }
            )

    asyncio.run(check())
