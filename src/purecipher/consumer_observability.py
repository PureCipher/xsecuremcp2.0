"""Bounded observability and research operations for owner-scoped connections."""

from __future__ import annotations

import asyncio
import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastmcp.server.security.outbound import (
    OutboundNetworkPolicy,
    OutboundRequestError,
    async_secure_outbound_request,
)
from purecipher import consumer_aws, consumer_cloud
from purecipher.consumer_runtime import _ACCESS, access, identifier

PRODUCTS = {
    "aws-core",
    "cloudwatch",
    "grafana",
    "dynatrace",
    "sonarqube",
    "brave-search",
    "firecrawl",
    "aws-documentation",
    "arxiv",
    "wikipedia",
}
MAX_RESPONSE_BYTES = 512 * 1024
USER_AGENT = "PureCipherRegistry/1.0 (https://purecipher.com)"
PUBLIC_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
BILLABLE_UNKNOWN = (
    "Firecrawl request outcome is unknown and credits may have been consumed. "
    "Check your Firecrawl activity before submitting the operation again."
)


def live_headers(product: str) -> dict[str, str]:
    """Recheck persisted access after asynchronous work before a billable request."""
    from purecipher.consumer_runtime import current_profile_client, runtime_ready
    from purecipher.workspace import allowed_profile_tools

    headers = dict(access(product))
    context = _ACCESS.get() or {}
    registry = context.get("registry")
    if registry is not None:
        client = current_profile_client(
            registry, context["profile_id"], context["client"]
        )
        allowed = allowed_profile_tools(registry, context["profile_id"], client)
        connection = registry._workspace.get(context["connection_id"])
        profile = registry._workspace.get(context["profile_id"])
        if (
            context["tool_name"] not in allowed
            or not connection
            or not profile
            or connection["revision"] != context["connection_revision"]
            or profile["revision"] != context["profile_revision"]
            or not runtime_ready(registry, connection)
        ):
            raise ValueError(
                "Connection or profile changed; check access before retrying"
            )
    return headers


def text(value: str, maximum: int, *, empty: bool = False) -> str:
    if (
        (not value.strip() and not empty)
        or len(value) > maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(
            f"Use {'up to' if empty else '1–'}{maximum} characters without control characters"
        )
    return value


def limit(value: int, maximum: int = 100, minimum: int = 1) -> int:
    if isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"Limit must be between {minimum} and {maximum}")
    return value


def resource_id(value: str) -> str:
    return identifier(text(value, 1024))


def page_token(value: str) -> str:
    return text(value, 4096, empty=True)


def time_window(start_time: str, end_time: str) -> tuple[datetime, datetime]:
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if (
            start.utcoffset() is None
            or end.utcoffset() is None
            or not 0 < (end - start).total_seconds() <= 7 * 86400
        ):
            raise ValueError
    except (ValueError, OverflowError):
        raise ValueError(
            "Use ISO timestamps with timezone offsets and a positive interval of at most 7 days"
        ) from None
    return start, end


def bounded(data: dict[str, Any]) -> dict[str, Any]:
    if len(json.dumps(data, default=str).encode()) > MAX_RESPONSE_BYTES:
        raise ValueError(
            "Provider result exceeds 512 KiB; narrow the query or request a smaller page"
        )
    return data


async def public_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    xml: bool = False,
    allow_list: bool = False,
    billable: bool = False,
) -> Any:
    """Only callers construct URLs; redirects and private destinations are blocked."""
    if params:
        url += "?" + urlencode(params)
    try:
        response = await async_secure_outbound_request(
            url,
            method="POST" if body is not None else "GET",
            content=json.dumps(body).encode() if body is not None else b"",
            headers={
                **(headers or PUBLIC_HEADERS),
                "Content-Type": "application/json",
                **({"Accept": "application/atom+xml"} if xml else {}),
            },
            timeout=20,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )
        if response.status_code != 200:
            if billable and response.status_code >= 500:
                raise ValueError(BILLABLE_UNKNOWN)
            raise ValueError(
                f"Provider request failed ({response.status_code}); check account permissions and query"
            )
        if xml:
            return response.content.decode("utf-8")
        data = json.loads(response.content)
        if not isinstance(data, dict) and not (allow_list and isinstance(data, list)):
            if billable:
                raise ValueError(BILLABLE_UNKNOWN)
            raise ValueError("Unexpected provider response")
        if isinstance(data, dict) and (data.get("success") is False or "error" in data):
            raise ValueError(
                "Provider rejected the request; check permissions and query"
            )
        return data
    except (OutboundRequestError, json.JSONDecodeError, UnicodeDecodeError):
        if billable:
            raise ValueError(BILLABLE_UNKNOWN) from None
        raise ValueError(
            "Provider response could not be read safely; retry or narrow the request"
        ) from None


async def cloud(
    product: str, path: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    # consumer_cloud.request validates/pins configured HTTPS origins and refuses redirects.
    return bounded(await consumer_cloud.request(product, path, access(product), params))


async def aws(
    product: str, service: str, operation: str, params: dict[str, Any]
) -> dict[str, Any]:
    access(product)
    context = _ACCESS.get()
    if context is None:
        raise ValueError("An assigned profile is required")
    return bounded(
        await consumer_aws.execute(context["values"], service, operation, params)
    )


async def public_target(url: str) -> str:
    text(url, 2048)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.port not in {None, 443}
    ):
        raise ValueError(
            "Use a public HTTPS URL without credentials, fragment, or custom port"
        )
    await asyncio.to_thread(OutboundNetworkPolicy().resolve, url)
    return url


def documentation_url(url: str) -> str:
    text(url, 2048)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"docs.aws.amazon.com", "docs.amazonaws.com"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in {None, 443}
    ):
        raise ValueError(
            "Use an official AWS documentation HTTPS page without credentials or query parameters"
        )
    return url


def paper_id(value: str) -> str:
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})(?:v[1-9]\d*)?", value):
        raise ValueError(
            "Use an arXiv paper identifier, for example 2301.12345 or hep-th/9901001"
        )
    return value


def parse_papers(body: str, maximum: int) -> dict[str, Any]:
    if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        raise ValueError("Unexpected arXiv XML response")
    try:
        document = ET.fromstring(body)
    except ET.ParseError:
        raise ValueError("Invalid arXiv XML response") from None
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "o": "http://a9.com/-/spec/opensearch/1.1/",
    }
    if document.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("Unexpected arXiv feed")
    entries = document.findall("a:entry", ns)
    if any(
        (entry.findtext("a:id", default="", namespaces=ns)).endswith("/api/errors")
        for entry in entries
    ):
        raise ValueError("arXiv rejected the query or identifier")
    return {
        "total_results": document.findtext("o:totalResults", namespaces=ns),
        "start_index": document.findtext("o:startIndex", namespaces=ns),
        "papers": [
            {
                "id": entry.findtext("a:id", namespaces=ns),
                "title": entry.findtext("a:title", namespaces=ns),
                "summary": entry.findtext("a:summary", namespaces=ns),
                "published": entry.findtext("a:published", namespaces=ns),
                "updated": entry.findtext("a:updated", namespaces=ns),
                "authors": [
                    author.findtext("a:name", namespaces=ns)
                    for author in entry.findall("a:author", ns)
                ],
                "links": [dict(link.attrib) for link in entry.findall("a:link", ns)],
            }
            for entry in entries[:maximum]
        ],
        "truncated": len(entries) > maximum,
    }


def wikipedia_title(value: str) -> str:
    text(value, 300)
    if "|" in value:
        raise ValueError("Request one Wikipedia article title at a time")
    return value


async def wikipedia(params: dict[str, Any]) -> dict[str, Any]:
    access("wikipedia")
    result = await public_request(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "format": "json", "formatversion": 2, **params},
    )
    if not isinstance(result, dict):
        raise ValueError("Unexpected Wikipedia response")
    return result


def register(registry: Any) -> None:
    registry._consumer_products = registry._consumer_products | PRODUCTS

    def tool(
        product: str, *, read: bool = True
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            registry._consumer_tool_products[getattr(fn, "__name__")] = product
            registry.tool(
                annotations={
                    "readOnlyHint": read,
                    "destructiveHint": False,
                    "idempotentHint": read,
                    "openWorldHint": True,
                },
                tags={
                    "consumer",
                    product,
                    f"resource:{product}",
                    "read" if read else "billable",
                    "risk:low" if read else "risk:high",
                },
            )(fn)
            return fn

        return decorate

    @tool("aws-core")
    async def aws_list_tagged_resources(
        resource_types: list[str] | None = None,
        max_results: int = 20,
        next_token: str = "",
    ) -> dict:
        """List tagged or previously tagged resources in the connection's AWS region; requires tag:GetResources. Untagged resources are not included."""
        limit(max_results)
        filters = resource_types or []
        if len(filters) > 20 or any(
            not re.fullmatch(r"[a-z0-9-]+(?::[A-Za-z0-9_-]+)?", value)
            for value in filters
        ):
            raise ValueError("Use up to 20 AWS resource types such as ec2:instance")
        return await aws(
            "aws-core",
            "resourcegroupstaggingapi",
            "get_resources",
            {
                "ResourcesPerPage": max_results,
                **({"ResourceTypeFilters": filters} if filters else {}),
                **({"PaginationToken": page_token(next_token)} if next_token else {}),
            },
        )

    @tool("aws-core")
    async def aws_list_regions() -> dict:
        """List EC2 regions enabled for the connected AWS account; requires ec2:DescribeRegions."""
        return await aws("aws-core", "ec2", "describe_regions", {"AllRegions": False})

    @tool("aws-core")
    async def aws_list_instances(max_results: int = 20, next_token: str = "") -> dict:
        """List one page of EC2 instance reservations in the connection's region; requires ec2:DescribeInstances. Does not start or stop instances."""
        limit(max_results, minimum=5)
        return await aws(
            "aws-core",
            "ec2",
            "describe_instances",
            {
                "MaxResults": max_results,
                **({"NextToken": page_token(next_token)} if next_token else {}),
            },
        )

    @tool("cloudwatch")
    async def cloudwatch_get_metric_statistics(
        namespace: str,
        metric_name: str,
        start_time: str,
        end_time: str,
        period_seconds: int = 300,
        statistic: Literal[
            "Average", "Sum", "Minimum", "Maximum", "SampleCount"
        ] = "Average",
        dimensions: dict[str, str] | None = None,
    ) -> dict:
        """Read one metric's statistics over at most seven days and 1440 datapoints; requires cloudwatch:GetMetricStatistics. Timestamps need timezone offsets."""
        start, end = time_window(start_time, end_time)
        if (
            period_seconds < 60
            or period_seconds % 60
            or math.ceil((end - start).total_seconds() / period_seconds) > 1440
        ):
            raise ValueError(
                "Use a period in whole minutes with at most 1440 datapoints"
            )
        dimensions = dimensions or {}
        if len(dimensions) > 30:
            raise ValueError("At most 30 metric dimensions are supported")
        return await aws(
            "cloudwatch",
            "cloudwatch",
            "get_metric_statistics",
            {
                "Namespace": text(namespace, 255),
                "MetricName": text(metric_name, 255),
                "StartTime": start,
                "EndTime": end,
                "Period": period_seconds,
                "Statistics": [statistic],
                "Dimensions": [
                    {"Name": text(key, 255), "Value": text(value, 1024)}
                    for key, value in dimensions.items()
                ],
            },
        )

    @tool("cloudwatch")
    async def cloudwatch_describe_alarms(
        name_prefix: str = "",
        state: Literal["", "OK", "ALARM", "INSUFFICIENT_DATA"] = "",
        max_results: int = 20,
        next_token: str = "",
    ) -> dict:
        """Read metric/composite alarm definitions and state; requires cloudwatch:DescribeAlarms. Does not change alarms."""
        return await aws(
            "cloudwatch",
            "cloudwatch",
            "describe_alarms",
            {
                "MaxRecords": limit(max_results),
                "AlarmTypes": ["MetricAlarm", "CompositeAlarm"],
                **({"AlarmNamePrefix": text(name_prefix, 255)} if name_prefix else {}),
                **({"StateValue": state} if state else {}),
                **({"NextToken": page_token(next_token)} if next_token else {}),
            },
        )

    @tool("cloudwatch")
    async def cloudwatch_list_log_streams(
        log_group: str, max_results: int = 20, next_token: str = ""
    ) -> dict:
        """Read streams for one log group ordered by recent event time; requires logs:DescribeLogStreams."""
        return await aws(
            "cloudwatch",
            "logs",
            "describe_log_streams",
            {
                "logGroupName": text(log_group, 512),
                "limit": limit(max_results, 50),
                "orderBy": "LastEventTime",
                "descending": True,
                **({"nextToken": page_token(next_token)} if next_token else {}),
            },
        )

    @tool("cloudwatch")
    async def cloudwatch_filter_log_events(
        log_group: str,
        start_time: str,
        end_time: str,
        filter_pattern: str = "",
        max_results: int = 50,
        next_token: str = "",
    ) -> dict:
        """Read a bounded page of matching log events over at most seven days; requires logs:FilterLogEvents. Log content can contain sensitive data."""
        start, end = time_window(start_time, end_time)
        return await aws(
            "cloudwatch",
            "logs",
            "filter_log_events",
            {
                "logGroupName": text(log_group, 512),
                "startTime": int(start.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "filterPattern": text(filter_pattern, 1024, empty=True),
                "limit": limit(max_results),
                **({"nextToken": page_token(next_token)} if next_token else {}),
            },
        )

    @tool("grafana")
    async def grafana_get_dashboard(uid: str) -> dict:
        """Read an accessible dashboard definition by UID; requires dashboards:read. Does not query its data sources."""
        return await cloud("grafana", "api/dashboards/uid/" + resource_id(uid))

    @tool("grafana")
    async def grafana_list_datasources(max_results: int = 20) -> dict:
        """List accessible data-source identities and types; credentials, URLs and configuration are omitted. Grafana's endpoint has no pagination."""
        count = limit(max_results)
        data = await cloud("grafana", "api/datasources")
        items = data.get("items", [])
        return {
            "items": [
                {
                    key: row[key]
                    for key in ("uid", "name", "type", "isDefault")
                    if key in row
                }
                for row in items[:count]
            ],
            "truncated": len(items) > count,
        }

    @tool("grafana")
    async def grafana_get_datasource(uid: str) -> dict:
        """Read one data-source's identity/type by UID; excludes credentials and configuration. Requires datasources:read."""
        data = await cloud("grafana", "api/datasources/uid/" + resource_id(uid))
        return {
            key: data[key]
            for key in ("uid", "name", "type", "isDefault")
            if key in data
        }

    @tool("grafana")
    async def grafana_list_alert_rules(max_results: int = 20) -> dict:
        """Read summaries of Grafana-managed alert rules; no alert/contact-point changes. This API has no pagination."""
        count = limit(max_results)
        data = await cloud("grafana", "api/v1/provisioning/alert-rules")
        items = data.get("items", [])
        return {
            "items": [
                {
                    key: row[key]
                    for key in (
                        "uid",
                        "title",
                        "folderUID",
                        "ruleGroup",
                        "condition",
                        "for",
                        "isPaused",
                    )
                    if key in row
                }
                for row in items[:count]
            ],
            "truncated": len(items) > count,
        }

    @tool("grafana")
    async def grafana_query_prometheus(
        datasource_uid: str,
        query: str,
        start_time: str,
        end_time: str,
        step_seconds: int = 300,
        max_series: int = 20,
    ) -> dict:
        """Query Prometheus metrics through an accessible Grafana data source by UID; requires datasource query permission. At most seven days, 1440 points per series and 100 series; does not modify metrics."""
        start, end = time_window(start_time, end_time)
        if (
            step_seconds < 1
            or math.floor((end - start).total_seconds() / step_seconds) + 1 > 1440
        ):
            raise ValueError("Use a positive step with at most 1440 points per series")
        count = limit(max_series)
        result = await cloud(
            "grafana",
            f"api/datasources/proxy/uid/{resource_id(datasource_uid)}/api/v1/query_range",
            {
                "query": text(query, 2000),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "step": step_seconds,
                "timeout": "10s",
                "limit": count,
            },
        )
        if result.get("status") != "success":
            raise ValueError(
                "Metric query failed; check data-source type, access and query"
            )
        series = result.get("data", {}).get("result", [])
        if len(series) > count or any(
            len(row.get("values", [])) > 1440 for row in series
        ):
            raise ValueError(
                "Metric result exceeds limits; narrow the query or increase the step"
            )
        return result

    @tool("grafana")
    async def grafana_query_loki(
        datasource_uid: str,
        query: str,
        start_time: str,
        end_time: str,
        max_results: int = 100,
    ) -> dict:
        """Read up to 100 Loki log lines over at most seven days through an accessible Grafana data source by UID. Use a LogQL log-stream query, not a metric expression. Log content may be sensitive."""
        start, end = time_window(start_time, end_time)
        expression = text(query, 2000)
        if not expression.lstrip().startswith("{"):
            raise ValueError(
                "Use a LogQL log-stream selector and optional line filters"
            )
        count = limit(max_results)
        result = await cloud(
            "grafana",
            f"api/datasources/proxy/uid/{resource_id(datasource_uid)}/loki/api/v1/query_range",
            {
                "query": expression,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": count,
                "direction": "backward",
            },
        )
        data = result.get("data", {})
        if result.get("status") != "success" or data.get("resultType") != "streams":
            raise ValueError(
                "Log query failed; use a Loki log-stream query and check access"
            )
        if sum(len(row.get("values", [])) for row in data.get("result", [])) > count:
            raise ValueError("Log result exceeds limits; narrow the query")
        return result

    @tool("dynatrace")
    async def dynatrace_get_entity(entity_id: str) -> dict:
        """Read one monitored entity and properties; requires entities.read on the selected environment."""
        return await cloud(
            "dynatrace",
            "api/v2/entities/" + resource_id(entity_id),
            {"fields": "properties,tags"},
        )

    @tool("dynatrace")
    async def dynatrace_list_problems(
        max_results: int = 20, next_page_key: str = ""
    ) -> dict:
        """Read one page of problems from the selected environment; requires problems.read. Continuation uses only nextPageKey as required by Dynatrace."""
        params = (
            {"nextPageKey": page_token(next_page_key)}
            if next_page_key
            else {"pageSize": limit(max_results), "from": "now-7d", "to": "now"}
        )
        return await cloud("dynatrace", "api/v2/problems", params)

    @tool("dynatrace")
    async def dynatrace_get_problem(problem_id: str) -> dict:
        """Read a problem's details; requires problems.read. Does not acknowledge or close it."""
        return await cloud("dynatrace", "api/v2/problems/" + resource_id(problem_id))

    @tool("dynatrace")
    async def dynatrace_query_metric(
        metric_key: str, entity_id: str, start_time: str, end_time: str
    ) -> dict:
        """Read up to about 120 points for one metric and one monitored entity over at most seven days; requires metrics.read. Arbitrary selector expressions are not accepted."""
        start, end = time_window(start_time, end_time)
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", metric_key)
            or len(metric_key) > 255
            or not re.fullmatch(r"[A-Z_]{1,40}-[A-Fa-f0-9]{16}", entity_id)
        ):
            raise ValueError(
                "Use one metric key such as builtin:host.cpu.usage and one entity ID such as HOST-0123456789ABCDEF"
            )
        return await cloud(
            "dynatrace",
            "api/v2/metrics/query",
            {
                "metricSelector": metric_key,
                "entitySelector": f'entityId("{entity_id}")',
                "from": start.isoformat(),
                "to": end.isoformat(),
                "resolution": "120",
            },
        )

    @tool("sonarqube")
    async def sonarqube_search_projects(
        query: str = "", page_number: int = 1, max_results: int = 20
    ) -> dict:
        """Search accessible SonarQube projects with numbered pagination; requires Browse permission."""
        return await cloud(
            "sonarqube",
            "api/components/search",
            {
                "qualifiers": "TRK",
                "q": text(query, 200, empty=True),
                "p": limit(page_number, 1000),
                "ps": limit(max_results),
            },
        )

    @tool("sonarqube")
    async def sonarqube_get_project_measures(
        project: str, metric_keys: list[str], branch: str = ""
    ) -> dict:
        """Read chosen code-quality measures for one project/branch; requires Browse permission."""
        if not 1 <= len(metric_keys) <= 20 or any(
            not re.fullmatch(r"[A-Za-z0-9_]+", key) or len(key) > 100
            for key in metric_keys
        ):
            raise ValueError(
                "Select 1–20 metric keys such as coverage, bugs, vulnerabilities or code_smells"
            )
        return await cloud(
            "sonarqube",
            "api/measures/component",
            {
                "component": text(project, 400),
                "metricKeys": ",".join(metric_keys),
                **({"branch": text(branch, 255)} if branch else {}),
            },
        )

    @tool("sonarqube")
    async def sonarqube_get_quality_gate(project: str, branch: str = "") -> dict:
        """Read a project's quality-gate status and conditions; requires Browse permission. Does not alter the gate."""
        return await cloud(
            "sonarqube",
            "api/qualitygates/project_status",
            {
                "projectKey": text(project, 400),
                **({"branch": text(branch, 255)} if branch else {}),
            },
        )

    @tool("sonarqube")
    async def sonarqube_list_project_analyses(
        project: str, page_number: int = 1, max_results: int = 20
    ) -> dict:
        """Read analysis history for one project; requires Browse permission."""
        return await cloud(
            "sonarqube",
            "api/project_analyses/search",
            {
                "project": text(project, 400),
                "p": limit(page_number, 1000),
                "ps": limit(max_results),
            },
        )

    async def brave(kind: str, query: str, count: int, freshness: str = "") -> dict:
        auth = access("brave-search")
        if len(query.split()) > 50:
            raise ValueError("Use at most 50 query words")
        return await public_request(
            f"https://api.search.brave.com/res/v1/{kind}/search",
            headers=auth,
            params={
                "q": text(query, 400),
                "count": limit(count, 20),
                **({"freshness": freshness} if freshness else {}),
            },
        )

    @tool("brave-search")
    async def brave_news_search(
        query: str, count: int = 5, freshness: Literal["", "pd", "pw", "pm", "py"] = ""
    ) -> dict:
        """Search news with your Brave subscription; freshness can be past day/week/month/year. May count toward provider quota."""
        return await brave("news", query, count, freshness)

    @tool("brave-search")
    async def brave_image_search(query: str, count: int = 5) -> dict:
        """Search image metadata/links using your Brave subscription; does not download image files."""
        return await brave("images", query, count)

    @tool("brave-search")
    async def brave_video_search(query: str, count: int = 5) -> dict:
        """Search video metadata/links using your Brave subscription; does not download or play videos."""
        return await brave("videos", query, count)

    @tool("firecrawl", read=False)
    async def firecrawl_scrape_url(url: str, max_characters: int = 20000) -> dict:
        """Scrape one public HTTPS page to Markdown with your Firecrawl account. This explicit operation consumes credits; browser actions, custom headers and login are not accepted."""
        access("firecrawl")
        limit(max_characters, 50000)
        target = await public_target(url)
        result = await public_request(
            "https://api.firecrawl.dev/v2/scrape",
            headers=live_headers("firecrawl"),
            billable=True,
            body={
                "url": target,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 15000,
            },
        )
        data = result.get("data")
        if not isinstance(data, dict):
            raise ValueError(BILLABLE_UNKNOWN)
        markdown = data.get("markdown")
        if not isinstance(markdown, str):
            raise ValueError(BILLABLE_UNKNOWN)
        return {
            "url": target,
            "markdown": markdown[:max_characters],
            "truncated": len(markdown) > max_characters,
            "metadata": data.get("metadata", {}),
        }

    @tool("firecrawl", read=False)
    async def firecrawl_map_website(
        url: str, search: str = "", max_results: int = 20
    ) -> dict:
        """Find up to 100 page URLs on one public website with Firecrawl; this explicit operation may consume credits. Does not crawl page contents or include subdomains."""
        access("firecrawl")
        text(search, 200, empty=True)
        limit(max_results)
        target = await public_target(url)
        result = await public_request(
            "https://api.firecrawl.dev/v2/map",
            headers=live_headers("firecrawl"),
            billable=True,
            body={
                "url": target,
                "search": search,
                "limit": max_results,
                "includeSubdomains": False,
                "timeout": 15000,
            },
        )
        links = result.get("links")
        if not isinstance(links, list):
            raise ValueError(BILLABLE_UNKNOWN)
        return {
            **result,
            "links": links[:max_results],
            "truncated": len(links) > max_results,
        }

    @tool("firecrawl")
    async def firecrawl_get_credit_usage() -> dict:
        """Read the connected Firecrawl team's remaining credit information; does not start a scrape or crawl."""
        return await public_request(
            "https://api.firecrawl.dev/v2/team/credit-usage",
            headers=access("firecrawl"),
        )

    @tool("aws-documentation")
    async def aws_search_documentation(query: str, max_results: int = 10) -> dict:
        """Search official AWS documentation and return up to 20 matching snippets. Uses the public AWS documentation search API, not your AWS account."""
        access("aws-documentation")
        count = limit(max_results, 20)
        result = await public_request(
            "https://proxy.search.docs.aws.com/search",
            params={"session": str(uuid4())},
            body={
                "textQuery": {"input": text(query, 400)},
                "contextAttributes": [
                    {"key": "domain", "value": "docs.aws.amazon.com"}
                ],
                "acceptSuggestionBody": "RawText",
                "locales": ["en_us"],
            },
        )
        suggestions = result.get("suggestions", [])
        return {
            "query_id": result.get("queryId"),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "context": item.get("summary", item.get("suggestionBody")),
                }
                for row in suggestions[:count]
                if isinstance((item := row.get("textExcerptSuggestion")), dict)
            ],
            "truncated": len(suggestions) > count,
        }

    @tool("aws-documentation")
    async def aws_recommend_documentation(url: str) -> dict:
        """Find related official AWS documentation for one page; uses AWS's public recommendation service."""
        access("aws-documentation")
        data = await public_request(
            "https://api.contentrecs.docs.aws.com/v1/recommendations",
            params={"path": documentation_url(url), "session": str(uuid4())},
            allow_list=True,
        )
        return bounded(data if isinstance(data, dict) else {"recommendations": data})

    @tool("arxiv")
    async def arxiv_get_paper(identifier: str) -> dict:
        """Read title, authors, abstract, dates and links for one arXiv identifier/version. Does not download or execute paper files."""
        access("arxiv")
        body = await public_request(
            "https://export.arxiv.org/api/query",
            params={"id_list": paper_id(identifier), "max_results": 1},
            xml=True,
        )
        return parse_papers(body, 1)

    @tool("arxiv")
    async def arxiv_recent_papers(
        category: str, start: int = 0, max_results: int = 10
    ) -> dict:
        """List recent submissions in one arXiv category with an explicit offset; e.g. cs.AI. Returns metadata/abstracts, not PDFs."""
        access("arxiv")
        if not re.fullmatch(r"[a-z][a-z-]*(?:\.[A-Z]{2})?", category):
            raise ValueError("Use one arXiv category such as cs.AI or math.PR")
        limit(start, 10000, 0)
        count = limit(max_results, 20)
        body = await public_request(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": "cat:" + category,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "start": start,
                "max_results": count,
            },
            xml=True,
        )
        result = parse_papers(body, count)
        result["next_start"] = (
            start + len(result["papers"]) if len(result["papers"]) == count else None
        )
        return result

    @tool("wikipedia")
    async def wikipedia_get_article(title: str, max_characters: int = 20000) -> dict:
        """Read the latest revision of one English Wikipedia article as bounded wikitext, with revision ID/date for citation. Does not edit the article."""
        limit(max_characters, 50000)
        result = await wikipedia(
            {
                "prop": "revisions",
                "titles": wikipedia_title(title),
                "rvprop": "ids|timestamp|content",
                "rvslots": "main",
                "rvlimit": 1,
                "redirects": 1,
            }
        )
        pages = result.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return {"title": title, "missing": True}
        page = pages[0]
        revisions = page.get("revisions", [])
        revision = revisions[0] if revisions else {}
        content = revision.get("slots", {}).get("main", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Article content is unavailable or hidden")
        return {
            "title": page.get("title"),
            "page_id": page.get("pageid"),
            "revision_id": revision.get("revid"),
            "timestamp": revision.get("timestamp"),
            "wikitext": content[:max_characters],
            "truncated": len(content) > max_characters,
        }

    @tool("wikipedia")
    async def wikipedia_article_history(
        title: str, max_results: int = 20, next_token: str = ""
    ) -> dict:
        """Read one page of an English Wikipedia article's revision metadata; continuation token is response.continue.rvcontinue."""
        return await wikipedia(
            {
                "prop": "revisions",
                "titles": wikipedia_title(title),
                "rvprop": "ids|timestamp|user|comment",
                "rvlimit": limit(max_results, 50),
                **(
                    {"rvcontinue": page_token(next_token), "continue": "||"}
                    if next_token
                    else {}
                ),
            }
        )

    @tool("wikipedia")
    async def wikipedia_article_links(
        title: str, max_results: int = 20, next_token: str = ""
    ) -> dict:
        """Read links from one English Wikipedia article; continuation token is response.continue.plcontinue. Does not fetch linked pages."""
        return await wikipedia(
            {
                "prop": "links",
                "titles": wikipedia_title(title),
                "pllimit": limit(max_results, 100),
                **(
                    {"plcontinue": page_token(next_token), "continue": "||"}
                    if next_token
                    else {}
                ),
            }
        )
