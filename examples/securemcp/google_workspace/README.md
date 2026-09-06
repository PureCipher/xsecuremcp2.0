# PureCipher Google Workspace — SecureMCP 2.0 rollout

Status: iteration 1, Gmail preparation. Not published, certified, or live-Google-tested.

## Publisher

Local registry account: `purecipher`, display name `PureCipher`, role `publisher`.
Generated local credentials are stored outside this package in xregistry's ignored
`secrets/purecipher-publisher.local.json`, with owner-only permissions. The registry
currently stores accounts and listings in memory. Restore or persist them before
another restart. Public publisher profiles are derived from published listings:
the profile will appear after the first approved listing with author `PureCipher`.

## Gmail implementation

`gmail_server.py` constructs `securemcp.SecureMCP`, not a bare FastMCP server.

- GoogleProvider OAuth; `gmail.readonly`, OpenID and email identity scopes.
- Per-request upstream Google token; no shared publisher mailbox credentials.
- Fail-closed Policy Kernel: only the three declared read tools may execute.
- Local Consent Graph requires an explicit grant before execution.
- Provenance recording and Reflexive pre-execution gating enabled.
- No public security-admin API, send-email, delete, or modification tools.
- Tools: `gmail_profile`, `gmail_list_messages`, `gmail_get_message`.

The first release is read-only. Future write actions need an explicit product
scope, OAuth scopes and approval behavior, and their own negative tests.

### Start after OAuth setup

Create a Google OAuth Web application; enable Gmail API. Configure callback
`http://127.0.0.1:9101/auth/callback` for this local setup. Set (without committing):

- `PURECIPHER_GOOGLE_CLIENT_ID`
- `PURECIPHER_GOOGLE_CLIENT_SECRET`
- optional `PURECIPHER_GMAIL_BASE_URL` (defaults to `http://127.0.0.1:9101`)

From the xsecuremcp2.0 repository:

```
.venv/bin/python examples/securemcp/google_workspace/gmail_server.py
```

MCP endpoint: `http://127.0.0.1:9101/mcp`. Missing OAuth credentials stop startup.
Google login alone does not bypass SecureMCP consent. Before live tests, provision
consent for the authenticated principal via a controlled administrator flow;
never auto-grant every Google user. Durable consent/provenance/OAuth storage and
reviewed grant management remain prerequisites for deployment. The initial
preparation uses the repository's in-memory security defaults.

## Iterations and acceptance gates

1. **Preparation (current):** publisher account, Gmail implementation, mocked
   Google API tests, unauthenticated and unconsented execution rejection.
2. **Gmail integration:** durable storage, controlled consent enrollment, OAuth
   authorization (when requested), real read test, registry preflight, certification,
   moderation, and public listing/connection verification. Verify per-user OAuth
   through the registry connection path before publishing a callable endpoint.
3. **Google Docs:** read document by ID and Drive-based document discovery;
   precise scopes and the same SecureMCP negative tests.
4. **Google Tasks:** task lists and task reads; separate server and scope.
5. **Google Calendar:** calendar and event reads; separate server and scope.
6. **Additional Google services/write operations:** separately scoped iterations.

A listing is not evidence of a working or certified integration. Publish only
when its authentication, consent, security tests, and real provider tests pass.
Use author `PureCipher`; describe these as PureCipher integrations with Google,
not Google-published or Google-endorsed servers.

Official OAuth setup: https://developers.google.com/workspace/guides/create-credentials
Gmail scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
