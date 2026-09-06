# Catalog expansion — preparation, not activation

The 35 Docker catalog entries in `catalog-sources.json` are upstream references.
Their source commits and icon URLs were read from Docker's official registry on
2026-09-06. Image tags are reference metadata, **not verified image digests**.
Nothing in this package pulls or launches these images.

`catalog_adapter.create_server(service, auth, upstream, allowed_tools)` builds a
SecureMCP boundary around an operator-configured `fastmcp.Client`. The operator
must deploy and isolate the upstream, configure its credentials, review its tool
schemas and supply a nonempty allowlist. The adapter exposes two tools:

- `catalog_list_tools`: returns only approved upstream tool schemas.
- `catalog_call`: dispatches only names in the frozen allowlist, under SecureMCP
  consent, policy, provenance and pre-execution controls. It is explicitly marked
  potentially destructive; a generic upstream invocation is not read-only.

Unapproved names cannot be discovered or dispatched. No upstream resource,
prompt, executable command or caller-provided server URL is exposed. The caller
cannot expand the allowlist by mutating the original set after construction.
Use a separate authenticated, tenant-isolated deployment and upstream client for
each account; a shared service credential must not expose cross-tenant data.
The caller supplies arguments only to approved tools; upstream tool validation
and provider permissions remain necessary. Do not mark these wrappers certified
merely because the boundary tests pass.

Slack (Reference) is a separate pending reference and does not replace the existing
`purecipher-slack` OAuth integration. Slack (Reference), GitHub (Reference), and Puppeteer are blocked
unless the operator explicitly enables `allow_archived` after maintenance review.
Prefer the maintained Slack integration and Playwright where suitable.

Per-service requirements are in `catalog-sources.json`: browser isolation and
network destinations; fetch SSRF defenses; filesystem mount restrictions;
ClickHouse read-only accounts, query limits and external-access settings;
Memory persistence and tenancy; provider credentials and request budgets.

Before activation, also configure durable SecureMCP consent/provenance and OAuth
storage, enroll approved clients, provision controlled consent administration,
validate pinned upstream images and schemas, and perform authorized end-to-end
calls. These production listings stay **draft / integration_review_pending**.
They contain source packages, not running endpoints. Upstream tool counts and
live operation are not yet verified; the two declared tools are adapter tools.

Sources: https://github.com/docker/mcp-registry and each entry's `catalog_source`.

## Catalog browsing

The 48 PureCipher preparation drafts have product-only display names and explicit
categories. Existing listing IDs remain unchanged. Docker's archived classification
is upstream provenance only; it does not change PureCipher's draft status.

GET /registry/tools and the authenticated GET /registry/me/listings accept q,
category, configuration (secrets, none, oauth), trust (known), server_type (remote),
sort, limit and offset. Repeated filters are OR within a group, AND between groups.
Sorting supports newest, oldest, name_asc, name_desc, popularity and default.
Default is alphabetical; popularity uses this Registry's installation count.
Filtering occurs before pagination; facets use only the caller-visible dataset.
GET /registry/categories supplies the taxonomy, including automation.

Configuration describes declared provider requirements; unknown or additional
configuration is not classified as no configuration required. Remote describes the
planned authenticated HTTP SecureMCP wrapper, not deployment readiness. Known
publisher means an active registered publisher account, not certification or an
upstream affiliation. All drafts still require review, isolated deployment and
live validation before publication.
