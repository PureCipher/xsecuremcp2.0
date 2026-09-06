# Consumer runtime connections

`PURECIPHER_CONSUMER_RUNTIME_ENABLED=true` registers runtime paths for all 48 product entries. This is implementation coverage, not evidence that every external account or service has been tested live. There are 32 native integrations and 16 authenticated upstream connectors. Every invocation requires an assigned active profile and the owner's verified connection; existing SecureMCP controls still apply.

## Native integrations

Google Gmail, Docs, Drive, Tasks and Calendar use the existing publisher-app OAuth flow and separate encrypted user grants. Configure the publisher app securely as documented below; users never provide the publisher's client secret.

Stripe, GitHub (including Reference), Slack (including Reference), Hugging Face, Apollo, Notion, Firecrawl, Grafana, SonarQube, n8n, Jira Cloud, Confluence Cloud and Dynatrace use consumer-owned tokens. Verification tests identity or a minimal read endpoint. Individual tools may need additional read permissions. Stripe summaries exclude payment client secrets; n8n summaries omit node configurations and credentials. Microsoft Outlook and OneDrive currently accept a delegated Graph access token: automatic sign-in and token refresh are not implemented for Microsoft. Replace expired tokens.

AWS Core and CloudWatch use explicit consumer access keys and optional temporary session tokens. They never use the host credential chain, proxy settings or environment endpoint overrides. Replace expired temporary credentials. CloudWatch requires appropriate read IAM actions.

Time, Wikipedia, arXiv, public HTTPS Fetch, AWS documentation, Memory and Sequential Thinking provide native utility functions. Memory and caller-provided reasoning steps are encrypted in the connection record and deleted with it. Sequential Thinking stores the caller's steps; it does not invoke a model. Public fetches are bounded and reject private addresses and redirects. Utility verification enables the local runtime; it does not prove that every future public URL is reachable.

## Upstream connectors

The following integrations connect to an existing consumer-owned MCP service: ast-grep, ClickHouse, Desktop Commander, Docker Hub, Private Web Search (DuckDuckGo), Filesystem, Git, Kubernetes, MarkItDown, MongoDB, Node.js Sandbox, Obsidian, Playwright, Puppeteer, Redis and YouTube Transcripts.

The Registry does **not** install or operate these upstream services. This is a SecureMCP connector implementation, not a native replacement for each upstream product. Configure product credentials, volumes, database permissions, browser isolation and resource limits on that upstream service. Use the product documentation linked in the setup UI. Local stdio services require an authenticated HTTPS MCP gateway. The endpoint must be publicly reachable; private/internal networks are blocked by the Registry's outbound policy.

Each connection requires an endpoint, a gateway access token and an explicit list of approved upstream tool names. Verification performs MCP initialization and tool discovery, validates schemas and stores the approved definitions encrypted under the owner. The UI displays these actual private tool definitions. Each product exposes `*_list_approved_tools` and `*_call_approved_tool` to profile clients. These are connector tools; the public catalog does not claim that it has independently validated every upstream tool implementation. Calls validate arguments and rediscover schemas before execution; changes require reverification. The call tool is marked as potentially destructive because an approved upstream tool may write or execute. Approval applies only to the named tools. DNS pinning, HTTPS checks, response limits and private-address blocking apply to every request. No arbitrary upstream processes run on the Registry host.

## Google application setup

Set `PURECIPHER_GOOGLE_CLIENT_ID`, mount a private secret file using `PURECIPHER_GOOGLE_CLIENT_SECRET_FILE`, and set `PURECIPHER_CONSUMER_OAUTH_REDIRECT_URI=https://registry.purecipher.com/api/workspace/oauth/callback`. Register that exact redirect in Google Cloud and enable the five APIs. Omit OAuth callback query strings from ingress logs before enabling real authorization.

OAuth grants are encrypted and owner-bound. State is expiring and single-use, with PKCE and an initiating-session check. Refresh writes use revision checks; a disconnect wins over concurrent refresh. Disconnect removes the local grant or verification, not the user's entire provider consent. Multiple workers can race refresh and return a retryable failure.

## Validation and status

Fixture tests cover actual profile requests for every credential-based product and every connector binding, provider request construction, ownership, revocation, schema changes, protected-network denial and encrypted utility state. They do not prove live account access for unconfigured services. Listings retain `live_tested=false`; connection readiness is individual to each user. Native credentials and upstream services must be supplied and tested before operational use.

Profile readiness also checks active client contracts and execute consent using the client's Registry slug. Missing approvals are shown before activation. A Registry administrator must grant the appropriate contract and consent; setup does not silently grant or bypass them. A full-stack test certifies a Time listing, demonstrates refusal before approval, invokes it successfully with an explicit tool-scoped contract and consent, and verifies that revocation blocks later requests.
