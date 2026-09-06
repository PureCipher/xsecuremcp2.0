# End-user profiles

Users register at `/register` and receive the existing viewer role. This grants a
private workspace, not publisher or administrator privileges. Usernames must be
canonical and cannot collide with an existing account's client-owner slug.
Existing password hashing, account sessions, client identities, token revocation,
suspension, and SecureMCP middleware are reused.

`/registry/profiles` provides Profiles and My clients tabs. Register each client
installation separately; its token is shown once. Profiles select specific client
IDs and published server listing IDs, with explicit tool-name allowlists. Create,
edit, duplicate, activate, deactivate, delete, and search are available. Saving
edits deactivates the profile; activation checks client status, server publication,
verification, readiness, and tool inspection. Preparation drafts are not eligible.

Profiles and permanent client ownership bindings are stored in PostgreSQL by
migration `20260906_0005`. Owner checks apply to all profile operations. Revision
checks prevent stale updates. Deleting a profile does not remove its clients or
allow those clients to bypass profile access. Client tokens remain revocable.

Clients connect to `/mcp/profiles/{profile_id}` using `Authorization: Bearer pcc_…`.
Every HTTP request checks the profile, client assignment, account status and
current readiness. MCP discovery is filtered and calls outside the allowlist are
rejected before the existing SecureMCP control planes. Direct registry, toolset,
and curator gateway routes reject workspace client tokens. Other registered
legacy clients keep their existing routes. Profiles expose selected tools only;
resources, prompts, tasks, and other MCP capabilities are not implicitly granted.
Already-running calls are not cancelled when a profile is deactivated; subsequent
requests are denied. Multiple profiles can be active; the endpoint selects one.

Profiles do not deploy upstream servers or substitute for provider OAuth, policy,
contract, and consent requirements. Provider credentials are not stored in profile
JSON. This release configures access to tools exposed by the registry's SecureMCP
runtime; it does not install or edit software on an end user's computer.

API: `POST /registry/register`; `GET /registry/workspace`;
`POST /registry/workspace/clients`; `POST /registry/workspace/profiles`;
`PUT` and `DELETE /registry/workspace/profiles/{id}`. Token and client suspension
operations reuse the existing owner-authorized client APIs. Registration is rate
limited with the existing throttle. Deploy behind the intended ingress; the
console proxies registrations, so its backend source address shares a bucket.
