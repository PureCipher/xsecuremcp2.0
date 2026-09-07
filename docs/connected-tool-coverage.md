# Connected upstream tool coverage

Reviewed 2026-09-07. This document covers the 16 products registered by `consumer_bridge.PRODUCTS`. Their tool inventory comes from the owner's verified upstream MCP service; the registry does not invent a fixed vendor tool count or deploy those upstream services as part of connection verification.

| Product | Product ID |
| --- | --- |
| ast-grep | `ast-grep` |
| ClickHouse | `clickhouse` |
| Desktop Commander | `desktop-commander` |
| Docker Hub | `docker-hub` |
| Private Web Search / DuckDuckGo | `duckduckgo` |
| Filesystem | `filesystem` |
| Git | `git` |
| Kubernetes | `kubernetes` |
| MarkItDown | `markitdown` |
| MongoDB | `mongodb` |
| Node.js Sandbox | `nodejs-sandbox` |
| Obsidian | `obsidian` |
| Playwright | `playwright` |
| Puppeteer | `puppeteer` |
| Redis | `redis` |
| YouTube Transcripts | `youtube-transcripts` |

## Public catalog versus private product tools

Each public connector listing exposes two backward-compatible helpers, with hyphens in the product ID replaced by underscores:

- `<product>_list_approved_tools`: read the names, descriptions and input schemas approved for the caller's connection.
- `<product>_call_approved_tool`: invoke any tool approved on that connection using its upstream name and schema-valid arguments.

Thus these listings contain **32 public helper definitions**, not 32 vendor operations. The actual product tool count depends on the deployed upstream service, version, permissions and owner-approved name list. It is unknown before verification. For example, a connection that verifies eight approved upstream definitions can offer eight individually selectable private tools; another connection to the same product can offer a different inventory.

The broad call helper remains compatible with existing profiles. Selecting it delegates the ability to call **any currently approved tool on that connection**, potentially including writes, deletion or execution. It does not provide the narrower per-operation boundary of selecting individual aliases. Profiles should select individual product tools when they need distinct operation or client permissions. The helper still validates upstream schemas, owner access, connection readiness and the existing SecureMCP security checks.

MCP defines discovery through `tools/list`, invocation through `tools/call`, and tool metadata containing a name, description and JSON input schema. Tool annotations from an upstream service are not inherently trusted. See the [official MCP tools specification, revision 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/server/tools).

## Connection and profile lifecycle

1. The end user creates their own product connection with a public HTTPS MCP endpoint, its access token, and 1–100 explicit approved upstream tool names. Endpoint credentials belong to that user. The connection cannot borrow another user's or publisher's stored token.
2. Verification initializes an authenticated upstream MCP session, lists its tools with bounded pagination, and resolves every approved name. Missing names, invalid or oversized schemas, external schema references and excessive catalogs are rejected. Verification discovers definitions; it does not call business tools.
3. The verified names, descriptions and schemas are encrypted into the owner's connection. A successful verification records a digest of its saved settings. Changing endpoint, token or approved names invalidates readiness until verified again.
4. The owner selects the connection, specific product tools and registered MCP clients in a profile. Optional per-client tool restrictions must be subsets of that profile's selection. The profile retains the exact selected aliases and connection IDs.
5. The owner reviews the resulting scope and requests the existing access approval. Required consent, administrator approval, contracts, policies and readiness checks still apply before the profile becomes active. Adding or changing selected capabilities does not silently reuse approval for a different scope.
6. The assigned MCP client connects to the profile endpoint with its own registry token. `tools/list` returns only its allowed tools. Invocations run through the existing SecureMCP middleware chain and then through the connection-specific upstream dispatch.

## Identity, effects and persistence

Every private operation has an alias shaped like `up_<descriptor-hash>_<readable-name>`. The hash binds the product, upstream name, description and input schema. The original upstream name is exposed as a display title; clients call the alias. Arguments are validated against the approved schema before upstream execution.

These descriptors are resolved per authenticated profile and are **not registered globally**. Private connection views reveal them to the owner; assigned clients see their selected subset. Other accounts and the public catalog cannot enumerate them. The existing administrator approval view can show selected tool labels and profile scope to authorized administrators; it does not turn private connection schemas into public catalog entries.

Each private tool receives conservative registry-controlled effects: not read-only, potentially destructive, non-idempotent, open-world and high risk. Upstream annotations and security tags do not lower these effects. This may cause read-only policies to deny even an upstream operation described as a read. Conservative effects are intentional until a trustworthy product-specific effect classification is available.

Credentials and approved descriptors are encrypted with an envelope bound to owner, connection ID and product. They use the existing workspace store: PostgreSQL persistence when configured, otherwise the in-memory development store. Stable registry signing-secret configuration is required to decrypt persisted records after restart. Profile selections, client bindings, status and revisions use that same workspace persistence. Tokens are not included in descriptor responses or public metadata. Disconnect invalidates runtime readiness; cached encrypted definitions can remain available as setup information until the connection is removed or verified again.

## Runtime checks and limitations

- Before an invocation, the current upstream definitions must still match the approved snapshot. A changed name, description or input schema stops the call. Reverification derives new aliases for changed definitions, requiring affected profile selections and approval to be reviewed again. Newly discovered but unapproved upstream tools never become selectable automatically.
- Profile ownership, active status, client assignment, applicable governance, selected tool, connection settings and revisions are checked. After awaited upstream discovery, the registry reauthenticates the client token and repeats profile and connection checks before the business call. Revocation during discovery therefore prevents dispatch.
- The `up_` namespace cannot be substituted by a static/public tool. Conflicting advertised names block activation or execution; identity checks also run at final tool resolution so publication during middleware cannot replace a private operation. Ambiguous aliases from multiple selected connections fail closed.
- Connections require a **public HTTPS endpoint**. Secure outbound handling enforces network destination restrictions. This connector does not start local processes, run Docker containers, mount the registry's filesystem, or grant access to its host merely because a product such as Filesystem or Desktop Commander is listed. The upstream service must already provide an appropriate remote MCP transport and authentication.
- MCP calls use bounded responses, timeouts and schema/argument sizes. No automatic business-call retries are added. Tool effects ultimately depend on the upstream implementation and its granted credentials; verification is not a guarantee that an upstream service behaves as its description claims.

Validation used mocked upstream MCP services and real local registry/profile HTTP requests for all 16 connector products. Tests cover discovery, exact schemas, profile/client selection, owner isolation, schema drift, namespace collisions including a dispatch race, disconnection and token revocation during discovery. **No live vendor account or deployed third-party MCP endpoint was validated by these tests.** Production acceptance still requires each user's configured upstream service and credentials.

Implementation: `consumer_bridge.py`, `consumer_bridge_tools.py`, `product_connections.py`, `workspace.py` and `middleware/profile_access.py`. Regression tests: `test_consumer_bridge.py`, `test_connected_tools.py` and `test_connected_tool_identity.py`.
