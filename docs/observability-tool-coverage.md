# Observability and research tool coverage

Reviewed 2026-09-07. Implementation: `src/purecipher/consumer_observability.py`.
This module adds **34 named operations** to ten existing consumer connectors,
bringing these ten connectors to **45 named operations**. Existing names remain
available. Counts describe implemented runtime handlers, not every vendor API.

| Product | Existing | Added | Total | Added MCP tools |
| --- | ---: | ---: | ---: | --- |
| AWS Core | 1 | 3 | 4 | `aws_list_tagged_resources`, `aws_list_regions`, `aws_list_instances` |
| CloudWatch | 2 | 4 | 6 | `cloudwatch_get_metric_statistics`, `cloudwatch_describe_alarms`, `cloudwatch_list_log_streams`, `cloudwatch_filter_log_events` |
| Grafana | 1 | 6 | 7 | `grafana_get_dashboard`, `grafana_list_datasources`, `grafana_get_datasource`, `grafana_list_alert_rules`, `grafana_query_prometheus`, `grafana_query_loki` |
| Dynatrace | 1 | 4 | 5 | `dynatrace_get_entity`, `dynatrace_list_problems`, `dynatrace_get_problem`, `dynatrace_query_metric` |
| SonarQube | 1 | 4 | 5 | `sonarqube_search_projects`, `sonarqube_get_project_measures`, `sonarqube_get_quality_gate`, `sonarqube_list_project_analyses` |
| Brave Search | 1 | 3 | 4 | `brave_news_search`, `brave_image_search`, `brave_video_search` |
| Firecrawl | 1 | 3 | 4 | `firecrawl_scrape_url`, `firecrawl_map_website`, `firecrawl_get_credit_usage` |
| AWS Documentation | 1 | 2 | 3 | `aws_search_documentation`, `aws_recommend_documentation` |
| arXiv | 1 | 2 | 3 | `arxiv_get_paper`, `arxiv_recent_papers` |
| Wikipedia | 1 | 3 | 4 | `wikipedia_get_article`, `wikipedia_article_history`, `wikipedia_article_links` |

## Runtime access and request boundaries

All handlers use the existing consumer connection context. Registration does not
grant access: runtime dispatch still requires the assigned active profile, selected
tool, approved access and the owner's matching product connection. Provider keys
come from that connection; there are no publisher-key or machine-credential
fallbacks. Public research connectors also require the matching profile context.

New tools carry `consumer`, the product ID and `resource:<product>` tags. Reads
carry `read`/`risk:low` and read-only/idempotent annotations. Firecrawl scrape/map
carry `billable`/`risk:high`, `readOnlyHint=false` and `idempotentHint=false` because
an explicit call may spend the user's credits. No new operation deletes data.
All tools have `openWorldHint=true`; these hints describe effects and do not replace
SecureMCP authorization or policies.

Public providers use fixed HTTPS origins, bounded secure outbound requests and no
redirect following. Grafana, Dynatrace and SonarQube retain the existing HTTPS
base-URL validation, public-address checks and DNS-pinned transport. The new
handlers construct fixed paths: clients cannot submit arbitrary HTTP requests,
headers, AWS operation names or proxy suffixes. Grafana query tools accept a data
source UID and fixed Prometheus/Loki query endpoints; the Grafana administrator's
data-source configuration controls its upstream connection.

New public HTTP responses are capped at 512 KiB. Existing custom-provider transport
retains its 2 MiB wire limit, followed by a 512 KiB result check in this module. AWS
results are also checked against 512 KiB. HTTP timeout is 20 seconds. AWS calls
reuse explicit regional endpoints and SigV4 credentials, including session tokens.
No helper automatically follows pagination or retries a failed billable request.
Pagination tokens are returned to the caller for a separate authorized call.

Before Firecrawl scrape/map, the starting target must resolve to public addresses
and use HTTPS without credentials, fragments or custom ports. After that DNS wait,
the handler rechecks the current profile client, live profile/tool access, connection/profile revisions and
runtime readiness before submitting the provider request. A disconnect, revision
change, removed tool, revoked client token or revoked readiness prevents the call. The target check does
not pin Firecrawl's own subsequent fetches: fetching and redirect handling within
Firecrawl remain provider-controlled. Browser actions, custom headers, login and
subdomain expansion are not exposed. Transport failures, malformed responses and
HTTP 5xx return an explicit unknown-charge-outcome error; callers must check
Firecrawl activity before resubmitting.

## Product contracts, permissions and exclusions

### AWS Core and CloudWatch

Uses the installed Boto3 service models for EC2, Resource Groups Tagging,
CloudWatch and CloudWatch Logs. Requires only the IAM operations selected by the
user: `tag:GetResources`, `ec2:DescribeRegions`, `ec2:DescribeInstances`,
`cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms`,
`logs:DescribeLogStreams` and `logs:FilterLogEvents` for the new handlers.

Inventory is regional. Tagged-resource lookup excludes resources that have never
had tags. EC2 pages are bounded to 5–100 reservations; other list limits are at
most 100, or 50 for log streams. Metric/log intervals are at most seven days;
metric statistics are limited to one metric, at most 30 dimensions and 1440
datapoints. These tools do not alter IAM, create/stop/delete infrastructure,
change alarms or retention, or start Logs Insights jobs.

Sources: [GetResources](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/API_GetResources.html),
[DescribeInstances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html),
[DescribeRegions](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeRegions.html),
[GetMetricStatistics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_GetMetricStatistics.html),
[DescribeAlarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_DescribeAlarms.html),
[DescribeLogStreams](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_DescribeLogStreams.html),
[FilterLogEvents](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_FilterLogEvents.html).

### Grafana

Uses the legacy Grafana HTTP API retained by current Grafana releases. These
routes are deprecated in Grafana 13, so migration to replacement APIs should be
reviewed before an incompatible server upgrade. Uses the owner's service-account
permissions for dashboards, data sources, alert rules and querying. No additional
Grafana administrator privileges are implied.

Data-source inventory returns UID/name/type/default status only, omitting URLs,
credentials and configuration. Alert summaries omit query and contact-point
configuration. Inventory endpoints have no pagination; local caps and truncation
flags are explicit. Prometheus queries allow at most seven days, 1440 points per
series and 100 series, with a 10-second evaluation timeout. Loki queries return at
most 100 log lines over seven days and reject metric-result responses. Both use
fixed data-source proxy suffixes and bounded response sizes. There are no generic
proxy, provisioning, dashboard-write or administration tools in this module.

Sources: [Data-source HTTP API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/data_source/),
[Dashboard HTTP API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/dashboard/),
[Alert provisioning API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/alerting_provisioning/),
[Prometheus HTTP API v1](https://prometheus.io/docs/prometheus/latest/querying/api/),
[Loki HTTP API v1](https://grafana.com/docs/loki/latest/reference/loki-http-api/).

### Dynatrace

Uses Environment API v2 with `entities.read`, `problems.read` and `metrics.read`
scopes for the corresponding tools. Problem continuation submits only
`nextPageKey`, as required by the API. Metric queries select one metric key and one
entity, over at most seven days with resolution targeting 120 points. The result
size cap remains authoritative. No arbitrary selector expressions, configuration
changes, problem acknowledgement or incident closure are exposed.

Sources: [Entity details](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/entity-v2/get-entity),
[Problem details](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/problems-v2/problems/get-problem-details),
[Metric data points](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/metric-v2/get-data-points).

### SonarQube

Uses the documented SonarQube Web API: components/search, measures/component,
qualitygates/project_status and project_analyses/search. Requires the user's Browse
permission on requested projects; branch availability depends on the server's
edition/version. Pages are at most 100 rows; measure reads accept 1–20 metric keys.
Does not change quality gates, administer projects, launch scans or modify code.

Sources: [SonarQube Web API](https://docs.sonarsource.com/sonarqube-server/2025.1/extension-guide/web-api),
[Metric definitions](https://docs.sonarsource.com/sonarqube-server/2025.4/user-guide/code-metrics/metrics-definition).

### Brave Search and Firecrawl

Brave uses Search API v1 news/images/videos routes and the user's subscription
token. Queries are capped at 400 characters and 50 words, returning at most 20
results. News freshness is an enumerated day/week/month/year filter. Tools return
search metadata and links, not downloaded media or generated answers. Calls may
count against the subscription's quota.

Firecrawl uses API v2. Scrape returns at most 50,000 Markdown characters from one
starting URL; map requests at most 100 links; credit usage only reads the current
team's credit balance. Scrape/map are separately selected billable operations.
There are no background crawls, batch jobs, browser sessions or autonomous agents.

Sources: [Brave API routes](https://api-dashboard.search.brave.com/documentation/resources/skills),
[Brave news search](https://api-dashboard.search.brave.com/app/documentation/news-search/get-started),
[Brave image search](https://api-dashboard.search.brave.com/api-reference/images/image_search),
[Firecrawl scrape](https://docs.firecrawl.dev/api-reference/endpoint/scrape),
[Firecrawl map](https://docs.firecrawl.dev/api-reference/endpoint/map),
[Firecrawl credit usage](https://docs.firecrawl.dev/api-reference/endpoint/credit-usage).

### AWS Documentation, arXiv and Wikipedia

AWS documentation search/recommendation requests follow the public API contract
used by the AWS Labs documentation MCP server. Search returns at most 20 matching
snippets. Recommendations require an official AWS documentation page URL. These
public services do not use AWS account credentials or perform cloud operations.
The public documentation endpoints are not versioned service APIs.

arXiv uses its Atom query API for identifier/version details and paginated recent
submissions in one category. Metadata includes abstracts, authors, dates and
links; no PDF downloads. Pages contain at most 20 papers and offsets are bounded
to 10,000. XML external entities/DTDs and API error feeds are rejected.

Wikipedia uses the English MediaWiki Action API (`formatversion=2`). Article reads
return at most 50,000 characters of wikitext with revision ID and timestamp;
history returns at most 50 revisions and links at most 100 entries. Continuation
is explicit. These tools do not edit pages, bulk export Wikipedia or automatically
fetch outbound links.

Sources: [AWS Labs documentation MCP](https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server),
[AWS Labs API implementation](https://github.com/awslabs/mcp/blob/main/src/aws-documentation-mcp-server/awslabs/aws_documentation_mcp_server/server_aws.py),
[arXiv API manual](https://info.arxiv.org/help/api/user-manual.html),
[MediaWiki Revisions](https://www.mediawiki.org/wiki/API:Revisions),
[MediaWiki Links](https://www.mediawiki.org/wiki/API:Links),
[MediaWiki Query](https://www.mediawiki.org/wiki/API:Query).

## Validation and remaining live checks

`tests/server/security/test_consumer_observability.py` covers every new operation's
exact HTTP or AWS request contract, matching-product isolation, invalid input,
bounded responses, credential omission, schema annotations/enums, Firecrawl
revocation and ambiguous billable failures. AWS cases also validate and sign
requests against real installed Botocore models without sending network traffic.

These are mocked provider tests. Live execution still needs each user's provider
credentials, scopes/IAM permissions, compatible data sources and approved profile
tool selection. No provider-account smoke test, production deployment or billable
provider call was performed as part of this module's test suite.
