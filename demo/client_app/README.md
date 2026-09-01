# PureCipher Agent Client (UI demo)

A small UI-based agent application that connects to the **Secured MCP Registry**
and calls governed MCP servers through the registry's governance proxy.

It shows the consumer side of the story (the publish/curate side is in
`../onboard_demo.sh` and `../register_real_servers.sh`):

1. **Register this agent** — creates a client identity (`kind=agent`) and issues a one-time token.
2. **Pick a server** — browse the registry's proxy-hosted listings.
3. **Connect & discover** — open an MCP session to the server's proxy URL with the agent token.
4. **Call a tool** — invoke it; the registry enforces the allowlist and records the call.

The browser never speaks MCP directly. A thin Starlette backend uses the real
`fastmcp.Client` against `/runtime/proxy/<listing_id>/mcp` — the same governed
path the rest of the demo narrates — which also avoids CORS.

## Run

**Easiest — one command (recommended for demos):**

```bash
./demo/start_demo.sh
```

This starts the registry with the right flags, registers the demo servers, launches
this app, and opens your browser. Stop everything with `./demo/start_demo.sh --stop`.
Add `--auth` to run with registry auth on (admin/admin123).

**Manual:**

```bash
# from the repo root, with the registry (started with --host-toolsets) + a server up
uv run python demo/client_app/app.py
# open http://localhost:8800
```

Environment (all optional):

| Var | Default | Notes |
|-----|---------|-------|
| `REGISTRY_URL` | `http://localhost:8000` | Auto-detects `:8001` (CLI default) if `:8000` is down. |
| `CLIENT_APP_PORT` | `8800` | UI port. |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin123` | For live registration when auth is on. Ignored if auth is disabled. |

Have a server registered first (e.g. `bash demo/register_real_servers.sh`), then
DeepWiki / the reference servers will appear in step 2.

> **The registry must run with `--host-toolsets`** (or `PURECIPHER_HOST_TOOLSETS=true`)
> for tool calls to work. That flag mounts the `/runtime/proxy/<id>/mcp` endpoint the
> agent connects to. Without it, listings still register and appear in the catalog, but
> **Connect** fails with `McpError: Session terminated`. The compose stack sets it; a
> plain `uv run purecipher-registry` does not.

## Calling the GitHub MCP server

**Short answer: yes — with the right setup.** The agent app calls any proxy-hosted
listing the same way; what matters is how GitHub gets registered, because GitHub
needs a credential.

Important limitation: the registry's proxy hosting for **npm / PyPI / Docker**
listings spawns the upstream per session **without** injecting credentials — the
token you pass at submit time is used only for one-shot introspection and is never
persisted. So "register `docker:ghcr.io/github/github-mcp-server` with a PAT and let
the registry run it" will introspect but **won't be authenticated at call time**.

### Recommended path (works today): the bundled bridge

`docker:ghcr.io/github/github-mcp-server` will NOT register directly — the
registry's introspector runs the image with no command, but it needs the `stdio`
subcommand, so the container exits ("McpError: Connection closed"). The bundled
**`demo/github_http_bridge.py`** fixes this: it runs the GitHub stdio server (with
the `stdio` arg + your token) and re-exposes it as a local HTTP MCP. You then
register that loopback URL — the registry forwards to it, your token stays in the
bridge process, and allowlist + provenance still govern every call.

```bash
# 1) Run the bridge with a fresh, scoped PAT
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_new
uv run python demo/github_http_bridge.py        # serves http://localhost:9100/mcp

# 2) Register that local endpoint as a proxy listing (loopback HTTP is allowed)
curl -s -X POST http://localhost:8001/registry/curate/submit \
  -H "Content-Type: application/json" \
  -d '{"upstream":"http://localhost:9100/mcp","hosting_mode":"proxy",
       "attestation_kind":"curator","tool_name":"github-local",
       "display_name":"GitHub (local HTTP)","version":"1.0.0"}'
# approve in the review queue if needed, then it shows up in the agent app.
```

Then in the app: pick **GitHub (local HTTP)**, connect, and call e.g.
`search_repositories` (`{"query":"fastmcp"}`) or `get_issue`. You're now inquiring
about GitHub *through* the governed registry.

Sanity check the image first if the bridge errors:
`docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_new ghcr.io/github/github-mcp-server stdio`
should start and wait (Ctrl-C to exit). If it exits immediately, the token is
invalid or lacks scopes.

### Zero-credential alternative: DeepWiki

If you just want to "ask about a GitHub repo" with no token, register **DeepWiki**
(`https://mcp.deepwiki.com/mcp`, already in `register_real_servers.sh`) and call
`ask_question` with `{"repoName":"owner/repo","question":"..."}`. Works out of the box.

### Want the registry to host GitHub directly with your PAT?

That requires threading a per-listing runtime credential into the proxy's client
factory (`src/purecipher/curation/proxy_runtime.py`) and a small encrypted credential
store. It's a real registry feature, not a config flag — ask and it can be scoped.

## Notes

- Consent and contract enforcement are **opt-in per listing**; the allowlist and
  provenance ledger are always on. So calls to script-registered servers succeed and
  are recorded without granting consent first.
- The governance panel in step 4 reads the agent's `/registry/clients/<slug>/governance`
  snapshot so you can watch the ledger count climb as you make calls.
