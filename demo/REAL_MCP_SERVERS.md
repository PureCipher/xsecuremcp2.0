# Real GitHub MCP servers for the demo

A curated set of well-known, GitHub-published MCP servers you can register into the
PureCipher Registry to make the demo concrete — recognizable names instead of the
toy `demo-mcp-server`.

## How the registry ingests them

The curator supports **four channels** (auto-detected from the prefix/scheme).
A raw GitHub URL is **not** a channel yet (it's reserved), but every server below
ships as an artifact that *is* supported:

| Channel | Reference format | Launched via | Example |
|--------|-------------------|--------------|---------|
| HTTP | `https://host/mcp` | direct connect | `https://mcp.deepwiki.com/mcp` |
| npm | `npm:pkg` / `npm:@scope/pkg@ver` | `npx` | `npm:@modelcontextprotocol/server-memory` |
| PyPI | `pypi:pkg@ver` | `uvx` | `pypi:mcp-server-fetch` |
| Docker | `docker:image:tag` | `docker run --rm -i` | `docker:ghcr.io/github/github-mcp-server:latest` |

Two things to know before you run it:

- **Submit re-introspects.** On `/registry/curate/submit` the registry launches the
  upstream and lists its tools. A server that exposes **zero** tools (the usual sign
  of a token-gated server hit anonymously) is **refused** — so credentialed servers
  must be registered *with* their token.
- **Launchers must be on PATH** inside the registry container (`npx`, `uvx`, `docker`),
  with outbound network for package/image pulls. The compose stack mounts the Docker
  socket, so the Docker channel works out of the box.

`hosting_mode` is either `catalog` (listed for browsing) or `proxy` (callable through
`/runtime/proxy/<listing_id>/mcp`). Credentials are passed **once** at submit time in an
`env` object and are never persisted, echoed, or logged.

---

## Credential-free (register unconditionally)

These are the cleanest picks for a live demo — nothing to configure, no secrets.

### DeepWiki — remote HTTP, no auth ⭐ best live pick
- **Ref:** `https://mcp.deepwiki.com/mcp`
- **Channel:** HTTP
- **Tools:** `read_wiki_structure`, `read_wiki_contents`, `ask_question` — ask natural-language
  questions about any public GitHub repo.
- **Why demo it:** it's a real, hosted, public MCP server. You can actually call
  `ask_question` live through the governance proxy and watch the call hit the provenance ledger.

### MCP Everything (reference)
- **Ref:** `npm:@modelcontextprotocol/server-everything`
- **Channel:** npm · **Tools:** exercises every MCP feature (tools, resources, prompts).
- **Why demo it:** shows the registry handling a rich capability surface — good for the allowlist story.

### MCP Memory
- **Ref:** `npm:@modelcontextprotocol/server-memory`
- **Channel:** npm · Knowledge-graph memory (persistent entities + relations).

### MCP Sequential Thinking
- **Ref:** `npm:@modelcontextprotocol/server-sequential-thinking`
- **Channel:** npm · Structured multi-step reasoning as a tool.

### MCP Fetch
- **Ref:** `pypi:mcp-server-fetch`
- **Channel:** PyPI (uvx) · Fetch a URL and convert content to markdown.
- **Why demo it:** exercises the PyPI/`uvx` channel — proves the registry isn't npm-only.

> **Also available, but need an argument** (configure in the Onboard wizard, not the script):
> `npm:@modelcontextprotocol/server-filesystem` (needs an allowed directory path) and
> `pypi:mcp-server-git` (needs `--repository <path>`). Great for showing scoped, parameterized
> access, but they don't introspect cleanly from a bare reference.

---

## Credentialed (register only with a token)

Recognizable, real-world servers. The script registers these **only** if the matching
environment variable is set, and threads the token into the one-shot introspection.

### GitHub (official) — Docker
- **Ref:** `docker:ghcr.io/github/github-mcp-server:latest`
- **Channel:** Docker · **Env:** `GITHUB_PERSONAL_ACCESS_TOKEN`
- **Tools:** repos, issues, pull requests, actions, code search (toolsets configurable).
- **Tip:** scope a fine-grained PAT to a single repo for the demo. `GITHUB_READ_ONLY=1`
  is a nice safety story if you want to mention it.

### Brave Search — npm
- **Ref:** `npm:@modelcontextprotocol/server-brave-search`
- **Channel:** npm · **Env:** `BRAVE_API_KEY`
- **Tools:** web / local / image / video / news search.
- **Note:** Brave also ships a newer first-party build at `npm:@brave/brave-search-mcp-server`.

---

## Running it

```bash
# from xsecuremcp2.0/, with the registry stack up (see DEMO_RUNBOOK.md Part 0)

# Credential-free only:
bash demo/register_real_servers.sh

# Include the credentialed ones:
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx \
BRAVE_API_KEY=BSA_xxx \
  bash demo/register_real_servers.sh

# List for browsing only (don't make them callable):
HOSTING_MODE=catalog bash demo/register_real_servers.sh
```

The script prints each listing's ID and proxy URL, then links to the catalog
(`/registry/servers`), the review queue, and the provenance dashboard.

## Tying it back to the agent demo

Registering these enriches the **catalog and curation** half of the story. To then have
your registered agent *call* one through governance, register a client
(`demo/onboard_demo.sh`), grant it consent for the target server's tools (mirror
`demo/seed_governance.py`), and point the MCP client at that server's proxy URL. The same
five controls — policy, provenance, reflexive, consent, contract — apply unchanged.

---

## Sources

- [@modelcontextprotocol/server-everything (npm)](https://www.npmjs.com/package/@modelcontextprotocol/server-everything)
- [@modelcontextprotocol/server-memory (npm)](https://www.npmjs.com/package/@modelcontextprotocol/server-memory)
- [@modelcontextprotocol/server-filesystem (npm)](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem)
- [modelcontextprotocol/servers (GitHub)](https://github.com/modelcontextprotocol/servers)
- [mcp-server-fetch (PyPI)](https://pypi.org/project/mcp-server-fetch/)
- [mcp-server-git (PyPI)](https://pypi.org/project/mcp-server-git/)
- [github/github-mcp-server (GitHub)](https://github.com/github/github-mcp-server)
- [@modelcontextprotocol/server-brave-search (npm)](https://www.npmjs.com/package/@modelcontextprotocol/server-brave-search)
- [brave/brave-search-mcp-server (GitHub)](https://github.com/brave/brave-search-mcp-server)
- [DeepWiki MCP — Devin docs](https://docs.devin.ai/work-with-devin/deepwiki-mcp)
