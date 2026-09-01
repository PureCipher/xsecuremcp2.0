# Design — Live-run route, reachability health, and persistence

## 0. Are published MCP servers persisted?

**Yes — to SQLite, when the registry runs with a database path.** The registry
wires a single `SQLiteBackend(persistence_path)` into every store, so when
`--database-path` (or env `PURECIPHER_REGISTRY_DB`) is set, all of this survives
restarts:

- **Listings** (the published/curated MCP servers) — the tool marketplace
- **Client identities + issued tokens**
- **Provenance ledger** (every governed call)
- **Consent graph** and **contracts** (context broker)
- **Reflexive baselines / escalation** state

The compose stack sets `PURECIPHER_REGISTRY_DB=/data/purecipher-registry.db` on a
mounted volume, so the demo persists across restarts. **Caveat:** if you run
`uv run purecipher-registry` with **no** database path, `persistence_path` is
`None` → everything is **in-memory** and lost on restart. For any real or demo
use, always set `PURECIPHER_REGISTRY_DB` (or pass `--database-path`).

> Recommendation: bake `PURECIPHER_REGISTRY_DB` into `start_demo.sh` so the demo
> never silently runs ephemeral.

---

## 1. Reachability health

### Endpoint
`GET /registry/tools/{tool_name}/health` — public, read-only.

### What it checks (by channel)
- **HTTP / proxy listing:** open a bounded MCP session to the server (or its
  proxy mount) and issue a cheap `initialize` + `list_tools`, measuring latency.
- **stdio (npm / PyPI / Docker):** a real spawn is too heavy for an on-demand
  check — report `unknown` and fall back to the activity signal (below).

### Response
```json
{ "status": "operational" | "degraded" | "offline" | "unknown",
  "checked_at": "2026-07-01T12:00:00Z",
  "latency_ms": 142 }
```
- `operational` — responded within budget
- `degraded` — responded but slow (e.g. > 1.5s) or partial
- `offline` — timed out / connection refused
- `unknown` — not checkable on-demand (stdio) → UI uses activity instead

### Safety / performance
- **Hard timeout** ~3s, run off the event loop (thread / `asyncio.wait_for`) so a
  slow upstream never blocks the server.
- **TTL cache** per listing (~30–60s) so the page doesn't hammer upstreams; store
  `last_status` + `last_checked_at` (optionally persisted).
- **Rate-limit** health checks per IP; only for published listings.

### UI wiring
`ServerDetail` fetches `/health` client-side after mount and sets the header dot:
`Operational` (green) · `Degraded` (amber) · `Offline` (red) · `Checking…`.
If `unknown`, keep the current **activity-based "Active"** pill (already live from
the ledger). No fake states.

---

## 2. Live-run execution route ("Try a tool")

The rule: **never bypass governance.** The try route is itself a *governed
client* — it calls the tool **through the curator proxy**, so all five controls
(policy allowlist, provenance, reflexive, consent, contract) apply automatically.

### Endpoint
`POST /registry/tools/{tool_name}/try` — body `{ "tool": "...", "arguments": { … } }`
(Next BFF `/api/public/try/[toolName]` just forwards to it.)

### Identity — ephemeral demo client
- Mint (or reuse) a **demo client** scoped to **this listing's allowlisted tools
  only**, `kind: "demo"`, so demo traffic is distinguishable in provenance.
- **Short-lived token** (≈5 min) and **low rate limit** (e.g. 5 calls/min/IP).
- The route uses `fastmcp.Client` → `/runtime/proxy/{listing_id}/mcp` with that
  token — the exact governed path a real agent uses.

### Guards
- **Allowlist only** (policy also enforces this).
- **Timeout** ~10s, **argument size** + **response size** caps, output sanitised
  before render.
- **Per-IP + per-listing rate limits**, global concurrency cap.
- **Opt-in per listing/tool:** only expose "Try" when the publisher marks the
  server (or specific tools) as **safe to invoke publicly** — default off for
  anything with side effects. A `try_enabled` flag (+ optional per-tool
  `read_only`) on the listing.
- **Access model interplay:**
  - `open` / free → public try allowed.
  - `byok` / `oauth` → try requires the *user's* key/OAuth (never spend the
    publisher's quota); or disable public try.
  - `metered` → optional limited free trial, metered like any call.

### Response
```json
{ "ok": true, "tool": "ask_question",
  "result": { "text": "…", "structured": { … } },
  "recorded": true }
```
Recorded in the provenance ledger like any call — so "Try" traffic is auditable
and shows up in usage.

### UI wiring
The playground `Run` posts to the BFF, shows the result + a "✓ governed call
recorded" line. The playground card only renders when `try_enabled` (and the
access model permits it); otherwise the tools accordion + recipes stand alone.

---

## Suggested build order
1. **Persistence guard** — set `PURECIPHER_REGISTRY_DB` in `start_demo.sh` (tiny, prevents silent data loss).
2. **Health endpoint** — bounded check + TTL cache + `ServerDetail` dot. Low risk, high signal.
3. **Live-run** — behind a `try_enabled` publisher flag, ephemeral demo token, rate limits, opt-in per access model. Ship guarded.
