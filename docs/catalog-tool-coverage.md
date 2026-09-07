# Full consumer catalog tool coverage — 0.4.0

Prepared and reviewed **2026-09-07**. The last audited production release had **85 definitions across 48 listings**. This local implementation has **279 registered definitions**: **247 native product/utility tools** and **32 backward-compatible connector helpers**. These counts come from actual runtime registration and generated schemas, not vendor marketing or Docker catalog counts. All previous tool names remain available.

The native surface is expanded for **29 products**, including Gmail, the other four Google Workspace products, business integrations, observability/research and Memory. Time, Fetch and Sequential Thinking retain their existing focused two/one/one-operation interfaces. They were reviewed; more names would not by themselves establish better coverage. Time converts/reads time, Fetch retrieves a bounded public URL, and Sequential Thinking records bounded stepwise thoughts; this release does not add branches, revisions or general workflow execution.

All **16 upstream connector products** now discover actual, individually selectable tool definitions from the owner's verified MCP endpoint. Their public count remains two helpers; their real private count depends on that endpoint, version and approved tool allowlist. No private schemas or credentials are published globally. A connector does not install an upstream server automatically.

**This is implemented common-operation coverage, not every vendor API endpoint.** The detailed records below state exclusions, API versions, permissions and sources. No live provider account has been certified by this change. The generated artifact is local; publishing/deploying and live account acceptance testing are separate steps.

## Every catalog entry

| Server | Previous definitions | Prepared definitions | Runtime inventory |
| --- | ---: | ---: | --- |
| Amazon CloudWatch | 2 | 6 | Native product operations |
| Apollo.io | 2 | 7 | Native product operations |
| ArXiv | 1 | 3 | Native product operations |
| ast-grep | 2 | 2 | 2 helpers + private tools discovered per connection |
| Atlassian | 2 | 7 | Native product operations |
| AWS Core | 1 | 4 | Native product operations |
| AWS Documentation | 1 | 3 | Native product operations |
| Brave Search | 1 | 4 | Native product operations |
| ClickHouse | 2 | 2 | 2 helpers + private tools discovered per connection |
| Desktop Commander | 2 | 2 | 2 helpers + private tools discovered per connection |
| Docker Hub | 2 | 2 | 2 helpers + private tools discovered per connection |
| Dynatrace | 1 | 5 | Native product operations |
| Fetch (Reference) | 1 | 1 | Native product operations |
| Filesystem (Reference) | 2 | 2 | 2 helpers + private tools discovered per connection |
| Firecrawl | 1 | 4 | Native product operations |
| Git (Reference) | 2 | 2 | 2 helpers + private tools discovered per connection |
| GitHub | 2 | 10 | Native product operations |
| GitHub (Reference) | 2 | 10 | Native product operations |
| Gmail | 3 | 26 | Native product operations |
| Google Calendar | 2 | 13 | Native product operations |
| Google Docs | 1 | 7 | Native product operations |
| Google Drive | 2 | 15 | Native product operations |
| Google Tasks | 2 | 12 | Native product operations |
| Grafana | 1 | 7 | Native product operations |
| Hugging Face | 2 | 7 | Native product operations |
| Jira | 1 | 7 | Native product operations |
| Kubernetes | 2 | 2 | 2 helpers + private tools discovered per connection |
| Markitdown | 2 | 2 | 2 helpers + private tools discovered per connection |
| Memory (Reference) | 2 | 9 | Native product operations |
| Microsoft OneDrive | 2 | 8 | Native product operations |
| Microsoft Outlook | 2 | 13 | Native product operations |
| MongoDB | 2 | 2 | 2 helpers + private tools discovered per connection |
| n8n | 1 | 6 | Native product operations |
| Node.js Sandbox | 2 | 2 | 2 helpers + private tools discovered per connection |
| Notion | 3 | 9 | Native product operations |
| Obsidian | 2 | 2 | 2 helpers + private tools discovered per connection |
| Playwright | 2 | 2 | 2 helpers + private tools discovered per connection |
| Private Web Search | 2 | 2 | 2 helpers + private tools discovered per connection |
| Puppeteer | 2 | 2 | 2 helpers + private tools discovered per connection |
| Redis | 2 | 2 | 2 helpers + private tools discovered per connection |
| Sequential Thinking (Reference) | 1 | 1 | Native product operations |
| Slack | 2 | 8 | Native product operations |
| Slack (Reference) | 2 | 8 | Native product operations |
| SonarQube | 1 | 5 | Native product operations |
| Stripe | 3 | 16 | Native product operations |
| Time (Reference) | 2 | 2 | Native product operations |
| Wikipedia | 1 | 4 | Native product operations |
| YouTube Transcripts | 2 | 2 | 2 helpers + private tools discovered per connection |

## Operation names, schemas and sources

The complete machine-readable inventory is [submissions.json](../examples/securemcp/consumer_runtime/submissions.json): each listing's `metadata.introspection.tools` contains exact names, descriptions, JSON schemas and effect annotations. `tool_coverage` records version, review date, count and source. `bundle_sha256` binds the consumer runtime modules. This is generated from registered handlers by [generate.py](../examples/securemcp/consumer_runtime/generate.py).

- [Gmail: 26 tools](gmail-tool-coverage.md) — mailbox reads, attachments, threads, drafts, sending, labels and trash.
- [Other Google Workspace: 47 tools](google-workspace-tool-coverage.md) — Docs, Tasks, Calendar and Drive, permission modes and provider-specific revision/ETag requirements.
- [Business tools: 90 additions](business-tool-coverage.md) — GitHub/reference, Slack/reference, Notion, Jira, Confluence, Outlook, OneDrive, Stripe, Hugging Face, Apollo and n8n.
- [Observability and research: 34 additions](observability-tool-coverage.md) — AWS, CloudWatch, Grafana, Dynatrace, SonarQube, Brave, Firecrawl, AWS Documentation, arXiv and Wikipedia.
- [All 16 upstream connectors](connected-tool-coverage.md) — actual private tools, discovery, schema changes, profile approval and compatibility helpers.
- [Memory implementation](../src/purecipher/consumer_utilities.py) — 9 tools for encrypted per-connection entities, observations and relations. Old entity state remains readable; deleting entities removes their relations. Limits are 100 entities, 50 observations per entity, 500 relations and 2 MiB encrypted plaintext per state save. Values use the existing workspace persistence backend.

## End-user selection and SecureMCP behavior

Newly added servers start with **no selected tools**, so adding write operations to the catalog does not grant them automatically. Existing saved profiles keep their exact selected names. Individual upstream selections have stable aliases bound to the verified name, description and schema. Switching connections removes the previous private selections; changed definitions require reverification and new profile review. A client can receive a narrower selected subset within a profile.

Credentials stay in the owner's encrypted connection. All Google products default to the existing read-only or metadata-only scope; broader modes require new authorization. Tool calls still require the assigned active profile, current client token, connection readiness, selected operations and applicable SecureMCP policy, consent and contract approval. Descriptors and effect hints are not authorization. Runtime rechecks prevent revoked tokens or changed profile/connection access from continuing after discovery, OAuth refresh or multi-step request waits. Private tool identity is checked at final dispatch to prevent a public tool replacing it.

## Validation

- **718 focused backend tests passed; 2 existing skips.** Provider request contracts, input limits, response handling, mode/scope enforcement, profile HTTP calls, encrypted state compatibility, all 16 private connectors, namespace collisions, schema drift, ownership isolation and mid-request revocation.
- **48 frontend tests passed**, plus the production Next.js build. Browser checks at 1440px and 390px cover discovery/selection/search, saved aliases, connection switching, client subsets and all four added Google permission selectors. No hydration or page errors.
- Ruff, Python type checks, manifest parsing, every JSON input schema, descriptor/name equality and all runtime source hashes passed. All 85 previous names remain present. Private aliases are absent from the public artifact.
- Provider responses and upstream MCP endpoints in automated tests were mocked. Google OAuth application setup, owner credentials, provider plans/permissions and live upstream endpoints remain necessary for real account testing. There were no live sends, payments or destructive vendor operations in these tests.
