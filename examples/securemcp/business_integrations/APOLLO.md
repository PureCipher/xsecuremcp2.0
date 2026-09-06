# PureCipher Apollo.io — preparation draft

Three tools: prospect-preview search, company search, and authenticated user
profile. No email/phone enrichment, CRM writes, sequence enrollment or outreach.
The search endpoints use HTTP POST but perform read searches.

Authentication uses **Apollo partner OAuth**, not a shared publisher API key.
Apollo documents API keys as workspace identities; partner OAuth is user-specific.
Register the PureCipher application with Apollo and obtain approval before live
setup. This code preserves Apollo's fragment-based authorization URL and uses
its documented token exchange/refresh endpoint. Token verification calls the
profile endpoint; individual calls also require their granted OAuth scopes.
No plaintext secrets are packaged or placed in listing metadata.

Required environment variables:

- `PURECIPHER_APOLLO_CLIENT_ID`
- `PURECIPHER_APOLLO_CLIENT_SECRET`
- `PURECIPHER_APOLLO_BASE_URL` — HTTPS required, with an approved `/auth/callback`

Run from the installed repository root:

```
python -m examples.securemcp.business_integrations.apollo_server
```

The server binds loopback port 9116. There is no deployed public endpoint yet.

## Credit boundary

According to Apollo's documentation checked September 6, 2026:

- People API Search: zero credits; previews exclude email addresses and phone numbers.
- Organization Search: one credit per page.
- Current User Profile: zero credits.

Company search is disabled by default. An operator must explicitly set
`PURECIPHER_APOLLO_ENABLE_COMPANY_SEARCH=true` and register/grant the additional
`mixed_companies_search` OAuth scope to enable it. The tool description discloses
the cost. There is no automatic pagination or retry loop. No live API calls or
credits are used in preparation tests. Provider pricing can change; verify it
again when authorizing the production application.

## Security and publication gates

SecureMCP policy, consent, provenance, Reflexive controls and pre-execution gating
are enabled through `common.py`. Missing OAuth configuration, missing tool scopes,
unconsented calls and undeclared tools fail closed. Security-admin routes are not
public. Each request is restricted to one of three fixed Apollo endpoints;
credentials are never forwarded across redirects.

Before making the endpoint available, configure durable security and OAuth
storage, controlled consent enrollment, and production HTTPS routing. Verify
real OAuth exchange/refresh/revocation, profile response shape, user isolation,
provider permissions and rate limits. Complete certification and review. Mocked
tests are not live certification. The draft remains `deployment_ready=false`
and `live_tested=false`.

Import only this draft using the production registry runtime:

```
python import_draft.py /path/to/business_integrations apollo
```

## Official sources

- https://docs.apollo.io/reference/authentication
- https://docs.apollo.io/docs/use-oauth-20-authorization-flow-to-access-apollo-user-information-partners
- https://docs.apollo.io/reference/people-api-search
- https://docs.apollo.io/reference/organization-search
- https://docs.apollo.io/reference/get-current-user-profile
