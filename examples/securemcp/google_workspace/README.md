# PureCipher Google Workspace — SecureMCP 2.0 preparation

Four read-only source packages and draft listings have been uploaded to production.
They are not certified, publicly published, running Google endpoints, or live-Google-tested.

## Publisher and production drafts

Production account: `purecipher`, display name `PureCipher`, role `publisher`.
Listing ownership uses the exact account username `purecipher`. The supplied
`publisher-profile.json` contains the PureCipher name, website and description;
it is also included in each draft's metadata. No account credentials are packaged.

The production registry persists accounts and listings in PostgreSQL. All four
drafts were read back after a registry restart, verified in `/api/me/listings`
under the publisher account, and their authenticated detail pages returned 200:

- `purecipher-google-gmail`
- `purecipher-google-docs`
- `purecipher-google-tasks`
- `purecipher-google-calendar`

Production source bundle location:
`/home/vamsi/services/purecipher/uploads/google-workspace-alpha1`.
A database backup was taken before importing the drafts. The operator-only
`import_production_drafts.py` imports through the marketplace persistence API,
checks source hashes, refuses non-draft overwrites, and issues no attestations.
The running registry must reload after this offline import to see new records.

Public publisher pages include active registered publisher accounts, even before
their first published listing. PureCipher appears with zero published tools;
the four drafts remain visible only in authenticated listing views.

## Implemented read tools

| Server | Tools | Google scope | Preparation port |
| --- | --- | --- | --- |
| Gmail | Profile, list messages, get message | `gmail.readonly` | 9101 |
| Docs | Get document by ID, including all tabs | `documents.readonly` | 9102 |
| Tasks | List task lists, list tasks | `tasks.readonly` | 9103 |
| Calendar | List calendars, list events | `calendar.readonly` | 9104 |

All four construct `securemcp.SecureMCP` with GoogleProvider OAuth, per-request
upstream tokens, fail-closed tool policies, a Consent Graph, provenance recording,
Reflexive controls and pre-execution gating. Public security administration is
disabled. There are no send, edit, create or delete tools.

57 preparation tests passed: tool discovery, read-only annotations, unauthorized
HTTP rejection, missing-scope denial, unconsented call rejection, allowlist policy,
Google request mocking, resource ID validation, pagination and tool request mapping.
These tests do not establish successful authorized end-to-end Google operation.

## Remaining deployment gates

Google authorization is deferred at the user's request. Before enabling endpoints:

1. Configure the Google OAuth web application and enable the relevant Google APIs.
2. Wire durable consent, provenance and OAuth storage; the current server examples
   use in-memory security defaults.
3. Provide a controlled administrator enrollment flow for consent grants to the
   actual authenticated principal. Google login alone must not grant execution.
4. Configure production routing, base URLs and exact OAuth callback URLs.
5. Test authorized reads, token renewal, isolation between users, persistence,
   consent rejection and revocation through the registry connection path.
6. Complete registry preflight, certification and publication review.

For development only, set `PURECIPHER_GOOGLE_CLIENT_ID` and
`PURECIPHER_GOOGLE_CLIENT_SECRET`, plus `PURECIPHER_<SERVICE>_BASE_URL` if needed
(where SERVICE is GMAIL, DOCS, TASKS or CALENDAR), then run the respective
`<service>_server.py`. Missing credentials stop startup. The default bind address
is loopback; default callbacks use `http://127.0.0.1:<port>/auth/callback`.

No production endpoint is advertised in the draft manifests. Source hashes pin
the uploaded preparation files. Further source changes require regenerated hashes.
These are PureCipher integrations with Google, not Google-published or endorsed servers.

## Official references

- https://developers.google.com/workspace/guides/create-credentials
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get
- https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/list
- https://developers.google.com/workspace/calendar/api/v3/reference/events/list
