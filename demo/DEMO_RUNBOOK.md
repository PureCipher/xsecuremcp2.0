# PureCipher Registry + SecureMCP — Live Demo Runbook

**Scenario:** An agent registers with the PureCipher Registry to access a published MCP server, and every tool call it makes is governed by SecureMCP.

**Audience:** Mixed technical + business. Run the live flow in a terminal while narrating the value on the console UI.

**Duration:** ~15–20 minutes.

---

## The one-sentence story

> A developer *publishes* an MCP server, a curator *approves* it into the registry, an *agent registers* and gets a scoped token, and from that moment **every** tool call the agent makes is checked against policy, recorded in a tamper-evident ledger, watched for anomalies, and validated against consent and contract — without changing a line of the agent's code.

The layering to keep in mind:

| Layer | Role | In the demo |
|-------|------|-------------|
| **FastMCP** | the engine — exposes capability (tools, resources, transports) | `demo_mcp_server.py` (5 plain tools) |
| **SecureMCP** | the secure server layer — governs capability | policy, provenance, consent, contracts, reflexive core |
| **PureCipher** | the product layer — Registry + Publisher | console UI, curator flow, client identities, proxy |

---

## What the audience will see

1. A plain MCP server with 5 tools, published into the registry.
2. A curator reviewing and approving the listing.
3. An **agent** registering as a client identity and receiving a one-time token.
4. The agent connecting **through the registry proxy** — not directly to the server.
5. Five governance controls enforced on every call, visible in the console:
   - **Allowlist policy** — only curator-observed tools are callable
   - **Provenance ledger** — every call recorded in a Merkle-tree audit log
   - **Reflexive core** — behavioral baselines + anomaly detection per actor
   - **Consent graph** — checked before execution
   - **Contract broker** — verifies an active contract covers the action

---

## Prerequisites

- Docker + Docker Compose
- The two repos cloned **beside each other**:
  - `xsecuremcp2.0/` — backend (SecureMCP + PureCipher Registry API)
  - `xregistry/` — Next.js console + public site
- Node 22+ (only if running the console outside Docker)
- A terminal with `curl` and `python3`

Ports used: registry API **8000**, console **3000**, public site **3001**, demo MCP server **9000**.

---

## Part 0 — Bring up the stack (do before the audience arrives)

> **Fastest path — one command.** For a hands-on demo (especially for a non-technical
> driver), skip the manual steps below and run:
>
> ```bash
> ./demo/start_demo.sh          # registry + servers + agent app + opens the browser
> ./demo/start_demo.sh --stop   # tear it all down
> ```
>
> It starts the registry with `--host-toolsets`, registers the demo servers, launches
> the guided agent app on :8800, and opens it. The manual steps below are for the full
> compose stack / console dashboards.

The fastest path is the full product stack from the `xregistry` repo, which builds the backend from the sibling `xsecuremcp2.0` clone.

```bash
cd xregistry
cp .env.compose.example .env          # SECUREMCP_REPO defaults to ../xsecuremcp2.0
export SECUREMCP_REPO=../xsecuremcp2.0
docker compose --env-file .env up --build
```

This starts the registry API (`:8000`), the console (`:3000`), and the public UI (`:3001`).

Then start the **demo MCP server** (the thing being published) from the backend repo:

```bash
cd ../xsecuremcp2.0
docker compose -f docker-compose.purecipher-registry.yml --profile demo up --build demo-mcp-server
```

Health checks before you start talking:

```bash
curl -s http://localhost:8000/registry/health        # registry API
curl -s http://localhost:9000/mcp -I                  # demo server reachable
open http://localhost:3000/registry/app               # console loads + you can sign in
```

> **Run with auth enabled (recommended).** The full governed story — curation under
> an admin, agent identities, consent — needs auth on. If you start the registry
> directly (not via compose), use **port 8000** and bootstrap an admin:
>
> ```bash
> PURECIPHER_SIGNING_SECRET=dev \
> PURECIPHER_ENABLE_AUTH=true \
> PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123 \
> PURECIPHER_HOST_TOOLSETS=true \
>   uv run purecipher-registry --port 8000 --host-toolsets
> ```
>
> **`--host-toolsets` is required** for the `/runtime/proxy/<id>/mcp` endpoint to
> exist. Without it the registry runs in plain mode, listings register fine but
> calling one through the proxy fails with `McpError: Session terminated` (the
> proxy route isn't mounted). The compose stack sets this for you.
>
> Two gotchas: the CLI **defaults to port 8001**, and **`admin/admin123` only exists
> if you set `PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD`**. All demo scripts auto-detect an
> 8001 registry and fall back to tokenless calls if auth is disabled, but the
> agent-registration narrative is strongest with auth on. With auth *disabled*, the
> console's listing-detail pages require the `[toolName]/page.tsx` null-session fix
> (see the xregistry PR) or they 500.

> **Backstage note:** the curator introspects the upstream server before listing it. With Docker-channel onboarding the registry container needs the host Docker socket (already wired in `docker-compose.purecipher-registry.yml`). `PURECIPHER_ALLOW_HTTP_HOSTS=demo-mcp-server` lets the proxy reach the demo server by its compose hostname.

---

## Part 1 — "Here is an ordinary MCP server" (2 min)

Open `demo/demo_mcp_server.py` and show that it is **plain FastMCP** — no security code:

```python
from fastmcp import FastMCP
mcp = FastMCP("Demo MCP Tools")

@mcp.tool
def get_weather(city: str) -> dict: ...
@mcp.tool
def calculate(expression: str) -> dict: ...
@mcp.tool
def lookup_company(name: str) -> dict: ...
@mcp.tool
def generate_uuid() -> str: ...
@mcp.tool
def echo(message: str) -> str: ...
```

**Talking point (business):** This is what most teams ship today — capability with no governance. Anyone with the URL can call anything. SecureMCP adds the controls *around* this without the developer rewriting it.

---

## Part 2 — Publish & curate the server (4 min)

You have two ways to show this. Pick one for the live run; mention the other exists.

### Option A — Publisher CLI (developer's view)

```bash
cd xsecuremcp2.0
uv run purecipher-publisher init weather-lookup --template http
cd weather-lookup
uv run purecipher-publisher check      # validates the security manifest
uv run purecipher-publisher package    # builds a signed package
uv run purecipher-publisher publish    # submits to the registry
```

**Talking point (technical):** `check` validates the explicit security manifest; `package` produces a signed, attestable artifact. Publishing is provenance-bearing from the first step.

### Option B — Curator flow via the console (curator's view)

Walk the console: **`/registry/onboard/wizard`** → enter the upstream URL `http://demo-mcp-server:9000/mcp`, choose **hosting mode = proxy**. The curator **introspects** the live server and records exactly which tools it observed — this becomes the allowlist.

Then the review queue at **`/registry/review`** → approve the listing with a reason.

### Or run it all scripted (fastest, repeatable)

`demo/onboard_demo.sh` does authenticate → submit (curator, proxy) → approve → register client → issue token → print connection config in one shot:

```bash
REGISTRY_URL=http://localhost:8000 ADMIN_USER=admin ADMIN_PASS=admin123 \
  bash demo/onboard_demo.sh
```

> Keep the script's output on screen — it prints the **listing ID**, the **agent token**, and the **proxy endpoint** you'll use next.

**Talking point (business):** The curator decides what enters the registry. A server isn't trusted because someone posted a URL — it's trusted because it was introspected, reviewed, and approved. That observed tool set becomes the enforced allowlist.

### Optional — register real, recognizable servers (2 min)

To make the catalog feel real instead of a single toy server, register a set of
well-known GitHub MCP servers (DeepWiki, the official reference servers, GitHub,
Brave). They ingest through the npm / PyPI / Docker / HTTP channels — see
[REAL_MCP_SERVERS.md](REAL_MCP_SERVERS.md) for the full catalog.

```bash
# credential-free set (DeepWiki + reference servers)
bash demo/register_real_servers.sh
# include credentialed ones
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx BRAVE_API_KEY=BSA_xxx bash demo/register_real_servers.sh
```

Show the populated catalog at **`/registry/servers`**, then open **DeepWiki** — a real,
public, hosted MCP server now under PureCipher governance. To take a server back out:

```bash
bash demo/deregister_servers.sh deepwiki        # one server
bash demo/deregister_servers.sh                 # the whole demo set
```

**Talking point:** the registry isn't limited to servers you wrote — it curates the
*existing* MCP ecosystem (npm/PyPI/Docker/remote) and puts governance in front of it.

---

## Part 3 — The agent registers (3 min) ⭐ core of the demo

This is the moment the request is really about: an **agent** becoming a known, scoped identity in the registry.

If you didn't use the script, register the client from the console at **`/registry/clients/onboard`**, or via API:

```bash
TOKEN=$(curl -sf -X POST http://localhost:8000/registry/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -sf -X POST http://localhost:8000/registry/clients \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "display_name": "Claude Code Demo",
    "slug": "claude-code-demo",
    "kind": "agent",
    "intended_use": "Integration testing of the full governance pipeline.",
    "issue_initial_token": true,
    "token_name": "demo-token"
  }'
```

The response includes a **`secret`** — the agent's bearer token, **shown only once**. Show the new identity in the console at **`/registry/clients/claude-code-demo`**.

**Talking points:**
- *(business)* The agent now has an identity the registry can reason about — who it is, what it's for, what it's allowed to touch. Access is granted to a *registered* party, not an anonymous caller.
- *(technical)* `kind: "agent"` distinguishes non-human callers. The token is scoped to this client; the registry binds every downstream call to this identity for policy, consent, and audit.

---

## Part 4 — The agent connects through the proxy (3 min)

The agent does **not** talk to `:9000` directly. It connects to the registry's governance proxy:

```
http://localhost:8000/runtime/proxy/<LISTING_ID>/mcp
```

Drop-in MCP client config (e.g. Claude Code), using the token from Part 3:

```json
{
  "mcpServers": {
    "demo-tools": {
      "type": "streamable-http",
      "url": "http://localhost:8000/runtime/proxy/<LISTING_ID>/mcp",
      "headers": { "Authorization": "Bearer <CLIENT_SECRET>" }
    }
  }
}
```

Then make the agent call some tools. The simplest live option is the seeding script, which connects as the registered agent and exercises the pipeline (consent grant, contract negotiation, policy evaluations, and ~7 real tool calls through the proxy):

```bash
docker exec xsecuremcp20-purecipher-registry-1 \
  uv run --no-sync python /app/demo/seed_governance.py
```

> The script prints the final state — ledger record count, policy evals/denies, monitored actors, consent edges, active contracts — which mirrors what the dashboards show.

**Talking point:** Same MCP protocol, same client code — the only change is the URL points at the registry instead of the server. Governance is inserted transparently in the path.

### Or use the UI agent client (most visual)

For a screen-friendly version of this step, run the bundled agent app
([client_app/](client_app/README.md)) and do steps 3–5 in a browser:

```bash
uv run python demo/client_app/app.py    # http://localhost:8800
```

It registers an agent, lists the registry's proxy servers, connects, calls a tool,
and shows the ledger count climbing as you go. It can call DeepWiki, the demo server,
or a locally-run GitHub MCP server (see the client_app README for the GitHub path).

---

## Part 5 — Show the governance (5 min) — the payoff

Walk these five console dashboards. Each call the agent made in Part 4 lit them up.

| Control | Console route | What to say |
|---------|---------------|-------------|
| **Policy (allowlist)** | `/registry/policy` | Only the 5 curator-observed tools are callable. A call to anything else is denied at the proxy — show the deny count. |
| **Provenance ledger** | `/registry/provenance` | Every call is a record in a Merkle-tree log. Tamper-evident audit trail — you can prove what the agent did and that the record wasn't altered. |
| **Reflexive core** | `/registry/reflexive` | Per-actor behavioral baselines + anomaly detection. The registry learns what *normal* looks like for this agent and flags deviations. |
| **Consent graph** | `/registry/consent` | The agent was granted `execute`/`read` on each tool; the proxy checks the consent graph before running anything. Grants can expire. |
| **Contracts** | `/registry/contracts` | An active contract governs the relationship — allowed tools, rate limits (100/min), provenance-required. The proxy validates the action is covered. |

Finish on the client's combined view: **`/registry/clients/claude-code-demo`** (governance summary for this one agent).

**Closing line (business):** Capability without governance is a liability. PureCipher turns "an agent called a tool" into "a *known* agent made an *authorized*, *recorded*, *in-policy* call — and we can prove it." **FastMCP exposes capability; SecureMCP governs it; PureCipher distributes it with trust.**

---

## Optional — Show enforcement by breaking a rule

To make the controls tangible, trigger a denial. Have the agent attempt a tool **not** in the allowlist (or one with consent revoked):

```bash
# Simulate an out-of-policy action for the registered client
curl -sf -X POST http://localhost:8000/registry/clients/claude-code-demo/simulate \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"tool_call","resource_id":"delete_everything","metadata":{"demo":true}}'
```

Expect `policy.decision = deny` with a blocker. Then show the deny surfaced on `/registry/policy` and `/registry/provenance`. **Talking point:** the deny is itself recorded — you have an audit trail of attempts, not just successes.

---

## Reset between runs

```bash
# Stop the stack
cd xregistry && docker compose --env-file .env down
cd ../xsecuremcp2.0 && docker compose -f docker-compose.purecipher-registry.yml --profile demo down

# Wipe registry state (listings, clients, ledger) for a clean run
rm -rf xsecuremcp2.0/.data/purecipher-registry

# Bring everything back up (Part 0) and re-run onboard_demo.sh
```

If you only want to remove the real servers you registered (without wiping
everything), deregister them instead — calls then return HTTP 410 and the
listings drop from the catalog, but the provenance record of the deregister is kept:

```bash
bash demo/deregister_servers.sh            # the demo real-server set
bash demo/:      # every listing (prompts to confirm)
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Console can't reach backend | Confirm `REGISTRY_BACKEND_URL` (console) points at `http://localhost:8000`; check `/registry/health`. |
| Curator introspect fails ("Cannot connect to the Docker daemon") | Ensure the Docker socket is mounted (it is in `docker-compose.purecipher-registry.yml`). |
| Proxy can't reach demo server | Confirm `PURECIPHER_ALLOW_HTTP_HOSTS` includes `demo-mcp-server` and the `demo` profile is up. |
| `onboard_demo.sh` 401 | Wrong `ADMIN_USER`/`ADMIN_PASS`, or auth disabled — defaults are `admin` / `admin123`. |
| Login fails: "auth is disabled" | Expected when auth is off — scripts proceed tokenless automatically. For the full story, start with `PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123`. |
| Scripts hit the wrong port | CLI defaults to **8001**; compose maps **8000**. Scripts auto-detect, or set `REGISTRY_URL=http://localhost:8001`. |
| Listing detail page 500s (`can_admin` of null) | Auth is disabled and the console is missing the `[toolName]/page.tsx` null-session fix — apply the xregistry PR, or run with auth enabled. |
| Connecting to a proxy server fails with `McpError: Session terminated` | The registry was started without `--host-toolsets`, so `/runtime/proxy/<id>/mcp` isn't mounted. Restart with `--host-toolsets` (or `PURECIPHER_HOST_TOOLSETS=true`). Listings persist in the DB. |
| `register_real_servers.sh` marks a server ✗ | Its launcher (`npx`/`uvx`/`docker`) isn't on PATH in the registry, no network for the pull, or a credentialed server was submitted without its token. |
| Token lost | It's shown once. Issue a new one from `/registry/clients/claude-code-demo` or re-run the script. |

---

## Quick reference — the whole flow in 6 commands

```bash
# 1. Stack up (from xregistry, sibling to xsecuremcp2.0)
docker compose --env-file .env.compose.example up --build
# 2. Demo server up (from xsecuremcp2.0)
docker compose -f docker-compose.purecipher-registry.yml --profile demo up --build demo-mcp-server
# 3. Publish + curate + approve + register agent + issue token (scripted)
bash demo/onboard_demo.sh
# 4. Agent makes governed calls through the proxy
docker exec xsecuremcp20-purecipher-registry-1 uv run --no-sync python /app/demo/seed_governance.py
# 5. Show dashboards: /registry/policy /provenance /reflexive /consent /contracts
# 6. Reset:  rm -rf .data/purecipher-registry && docker compose ... down
```
