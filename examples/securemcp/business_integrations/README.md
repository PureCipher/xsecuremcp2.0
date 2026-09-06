# PureCipher business integrations — preparation iterations 2–6

These read-only SecureMCP 2.0 packages are preparation drafts. They are not live,
certified, or publicly published. Google Drive is iteration 1 in the sibling
`google_workspace` package. Google authorization remains deferred.

| Iteration | Integration | Initial capabilities | Preparation port |
| --- | --- | --- | --- |
| 2 | GitHub | Allowed public repositories: issues, pull requests, issue details | 9111 |
| 3 | Slack | Allowed public-channel history using a user token | 9112 |
| 4 | Jira | Issue search and details on a configured cloud site | 9113 |
| 5 | Outlook | Signed-in user's messages, message contents, calendar events | 9114 |
| 6 | OneDrive | Folder listing, file metadata and browser links | 9115 |

## Authentication and resource boundaries

Each server needs its own OAuth application credentials. Set
`PURECIPHER_<SERVICE>_CLIENT_ID`, `PURECIPHER_<SERVICE>_CLIENT_SECRET`, and
`PURECIPHER_<SERVICE>_BASE_URL` (SERVICE is GITHUB, SLACK, JIRA, OUTLOOK or ONEDRIVE).
Default base URLs are loopback on the ports above. Callback paths are
`/auth/callback`. Production routing and exact HTTPS callbacks remain to be configured.
No credentials are included in these files or the registry metadata.

- GitHub uses the native OAuth proxy, requesting `read:user`. This first version
  accesses explicitly allowed **public** repositories only; do not mistake this
  for private repository support. Set `PURECIPHER_GITHUB_REPOSITORIES` to comma-separated
  `owner/repository` entries. A fine-grained GitHub App flow is a future iteration.
- Slack requests **user** scopes `channels:read,channels:history`. Its nested user
  token is normalized by the OAuth adapter; bot tokens are rejected. Set
  `PURECIPHER_SLACK_CHANNELS` to allowed public-channel IDs. Private channels, DMs,
  channel search and message sending are outside this first scope. Provider rate
  limits are surfaced as errors; no automatic retry loops or history harvesting.
- Jira requires `PURECIPHER_JIRA_CLOUD_ID`; OAuth token verification checks the
  accessible resources list and `read:jira-work` grant for that exact site.
- Microsoft requires a separate `PURECIPHER_OUTLOOK_TENANT_ID` or
  `PURECIPHER_ONEDRIVE_TENANT_ID`. Configure delegated Graph permissions from the
  manifest. Identity is verified using `/me`; Graph enforces data permissions on
  every request. No Graph token claims are decoded or trusted locally. Graph
  pagination links must retain the exact host and resource path.
- OneDrive currently returns metadata, not file contents. Content retrieval needs
  separate size/type limits and review before implementation.

All tools use SecureMCP policy allowlists, deny execution without a consent grant,
and enable provenance, Reflexive controls and pre-execution gating. Security
administration routes are disabled. Requests use fixed provider origins and do
not forward bearer credentials through redirects. Remote content is untrusted
application data, never instructions to the server or registry.

## Running after configuration

From the repository root, using its installed environment:

```
python -m examples.securemcp.business_integrations.github_server
```

Replace `github` with the desired service. Servers fail startup without OAuth
credentials; GitHub and Slack also require explicit resource allowlists. Each
service is independent. Do not mount these under the registry's public routing
until the deployment gates below pass.

## Production draft upload

Upload the package and use the production registry runtime:

```
python import_draft.py /path/to/business_integrations github
```

Import each service individually. The importer verifies the entrypoint and shared
source hashes, permits only PureCipher-owned uncertified drafts, and reads back
from PostgreSQL. Reload the registry after an offline import. Never use this
operator script as a public upload endpoint. Keep a database backup before import.

## Remaining acceptance gates

These examples use initial security defaults. Before activating any endpoint:

1. Configure durable consent/provenance and OAuth storage and signing secrets.
2. Enroll actual authenticated principals with administrator-controlled consent.
3. Complete provider app setup, authorized login and real read tests.
4. Verify per-user and per-workspace isolation, refresh, expiry, revocation,
   unauthorized resource denial and persistence across restart end to end.
5. Complete registry certification/review and then publish the callable endpoint.

Offline tests exercise request mapping, authentication rejection, unconsented
execution, policy denial, resource allowlists, pagination URL validation, upstream
errors and provider OAuth/token normalization. They do not prove a successful
live OAuth round trip or runtime certification. Registry listings are explicitly
marked `deployment_ready=false` and `live_tested=false`.

## Official API references

- https://docs.github.com/en/rest/issues
- https://docs.github.com/en/rest/pulls/pulls
- https://docs.slack.dev/authentication/installing-with-oauth/
- https://docs.slack.dev/reference/methods/oauth.v2.access/
- https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/
- https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0

## Additional preparation packages

Apollo is documented in APOLLO.md. Stripe and Hugging Face use the read-only
implementations in STRIPE-HUGGINGFACE.md. The 15 upstream catalog adapters in
CATALOG.md are separate review-pending packages; their dispatcher may invoke
mutating tools and is not a read-only integration. None is activated by import.
