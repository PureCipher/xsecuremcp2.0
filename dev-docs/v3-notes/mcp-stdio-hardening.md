# MCP stdio hardening — threat model & iteration plan

## Why this note exists

On May 1, 2026 VentureBeat published OX Security's audit of MCP's
STDIO transport ("MCP stdio flaw — 200,000 AI agent servers exposed").
The research produced 10+ high/critical CVEs across LiteLLM, LangFlow,
Flowise, Windsurf, Langchain-Chatchat, Bisheng, DocsGPT, GPT Researcher,
Agent Zero, LettaAI. Anthropic characterized the behavior as
"expected" and declined a protocol-level fix, updating SECURITY.md
nine days after initial contact to recommend caution with stdio
adapters but making no architectural changes.

Our position: treating STDIO as "developer's responsibility to
sanitize" is a distributed failure mode when thousands of downstream
implementers are expected to interpret a trust boundary consistently.
SecureMCP ships opinionated defaults — this note captures how those
defaults should evolve to address the class of issues OX named, and
lays out a sequenced iteration plan.

The plan is intentionally defensive. We are not publishing exploit
chains; we are defining controls SecureMCP operators can rely on.

## Threat model — four families, mapped to this codebase

OX grouped exploitation into four families. Each maps to concrete
surfaces already in the repo:

### F1. Unauthenticated command injection via framework UIs

Attacker reaches a public AI framework endpoint, the endpoint
forwards a user-influenced string into an STDIO adapter, and the
adapter executes it.

- **Surface in this repo:** `PolicyEnforcementMiddleware` at
  `src/fastmcp/server/security/middleware/policy_enforcement.py:59`
  defaults `bypass_stdio=True`. Any deployment that mounts SecureMCP
  over streamable-http but proxies through an STDIO upstream
  inherits this bypass unless the operator flips it. The proxy
  runtime at `src/purecipher/curation/proxy_runtime.py:459` already
  overrides this (good), but the default is the wrong direction.
- **Control:** Deny-by-default policy evaluation on stdio.
  Operators opt in to a documented bypass *per listing*.

### F2. Allowlist bypass via argument injection

OX bypassed Flowise/Upsonic command allowlists using `npx -c`
— the allowlist permitted `npx` but passed untrusted args through.
Same class: `sh -c`, `bash -c`, `node -e`, `python -c`,
`docker --entrypoint …`.

- **Surface in this repo:** `StdioTransport.__init__` at
  `src/fastmcp/client/transports/stdio.py:22` accepts `(command,
  args)` and forwards them to `stdio_client`. There's no argv
  inspector — `NpxStdioTransport` and `UvxStdioTransport` build
  their own argvs but neither validates that `args` doesn't later
  contain an interpreter-flag wedge.
- **Control:** `CommandSpec` validator that inspects the whole
  argv (command + args + env override flags) against a
  structured, per-launcher grammar. `npx` is allowed; `npx -c` is
  not. `docker run` is allowed; `docker run --entrypoint sh …`
  is not without an explicit attestation override.

### F3. Zero-click / low-interaction config-file RCE (IDE family)

Attacker-controlled HTML modifies local MCP config files
(`~/.cursor/mcp.json`, Windsurf equivalents, `~/.claude/*`,
Gemini-CLI paths). In Windsurf the change executes with no prompt;
in Cursor/Claude Code/Gemini-CLI the UI presents a config-key diff
that doesn't surface the resulting executed command.

- **Surface in this repo:** This is a client-side concern — SecureMCP
  runs server-side, but Claude Code *is* the IDE. Our hook is the
  config file schema and the approval UX. We should define a signed
  MCP config format (hashed launcher spec + attestation pointer) and
  surface the concrete resolved argv to the user, not the JSON delta.
- **Control:** Config file integrity + command-resolution preview on
  approval. The user approves "launch `npx -y @acme/tool@1.2.0`",
  not "updated mcp.servers.acme.command".

### F4. Malicious package distribution via registries

OX submitted a benign PoC to 11 MCP registries; 9 accepted without
review.

- **Surface in this repo:** `ToolMarketplace` at
  `src/fastmcp/server/security/gateway/tool_marketplace.py` handles
  publishing but the publish → review → live transition doesn't yet
  have an explicit security-review gate separate from certification.
  `CertificationPipeline` validates a manifest but doesn't gate
  listing visibility.
- **Control:** Formal submission-review stage with attestation
  requirement, reviewer sign-off recorded to `TrustRegistry`, digest
  pinning enforced at install time (digest ≠ attested ⇒ install
  refused).

## Load-bearing assumption we are rejecting

> "STDIO's execution model is a secure default; input sanitization is
> the developer's responsibility."

SecureMCP's position:

1. STDIO is a privileged execution surface. Treat it like shell access.
2. Cooperative sanitization fails at scale. Enforcement must be
   structural — at the protocol, not in each product.
3. OS-level containment (seccomp / landlock / Seatbelt / rootless
   containers) is the primary control. Python-level checks are a
   secondary layer, not the boundary.

Today our `SandboxedRunner` is cooperative by its own admission (see
the module-level warning at
`src/fastmcp/server/security/sandbox/enforcer.py:1`). That gap is the
single largest delta between the OX writeup and our posture.

## Iteration plan

Ordered by blast-radius reduction per unit of effort. Each iteration
is intended to ship independently; nothing here requires a protocol
fork.

### Iter 0 — Flip stdio bypass defaults (hotfix) — *shipped*

**Change (landed):**

- `PolicyEnforcementMiddleware`, `ContractValidationMiddleware`,
  `ConsentEnforcementMiddleware`, `ProvenanceRecordingMiddleware`,
  and `ReflexiveMiddleware` all default `bypass_stdio=False`.
- `SecuritySettings.policy_bypass_stdio` defaults to `False`, so
  the `SECUREMCP_POLICY_BYPASS_STDIO` env var needs to be set
  explicitly to opt back in to the old behavior.
- `SecurityOrchestrator.bootstrap(..., bypass_stdio=False)` is the
  new default and is propagated into every wired middleware.
- Docs updated: `docs/servers/security/settings.mdx` explains the
  default shift and points at this note.

**Tests added:**

- `test_orchestrator.py::TestBypassStdio::test_bypass_stdio_defaults_to_false`
- `test_settings.py::TestAttachSecuritySettings::test_attach_security_defaults_to_enforcing_stdio`
- `test_settings.py::TestAttachSecuritySettings::test_security_settings_defaults_to_enforcing_stdio`

The existing `test_attach_security_warns_about_stdio_bypass` test
already covers the loud warning that fires when an operator
explicitly re-enables the bypass.

**Why first:** one-line flip per middleware, broad blast-radius
reduction, no new components. Also anchors the narrative for the
rest of the series.

### Iter 1 — CommandSpec validator (argv-aware launcher allowlist)

**Change:** new `fastmcp.client.transports.stdio_policy` module with:

- `CommandSpec` — structured launcher descriptor (launcher kind,
  package spec, pinned version, optional attestation id).
- `LauncherGrammar` — per-launcher rules: allowed flags, denied
  flag-and-value patterns (e.g., `-c` + arbitrary string for `sh`,
  `bash`, `node`, `python`; `-c` / `--call` for `npx`).
- Validator runs at `StdioTransport.__init__` before the subprocess
  is spawned; failure raises `StdioPolicyError`.

**Tests:** exploit matrix from the OX writeup (npx -c, sh -c,
node -e, docker --entrypoint, env-wedged variables) all raise; the
happy path (`npx -y @acme/tool@1.2.0`) passes.

**Why second:** closes F2 without requiring OS-level plumbing.

### Iter 2 — SandboxBackend protocol + OS-level containment

**Change:** define a `SandboxBackend` protocol in
`src/fastmcp/server/security/sandbox/` with concrete implementations:

- `LandlockSandbox` (Linux 5.13+)
- `SeccompSandbox` (Linux, strict syscall filter)
- `SeatbeltSandbox` (macOS, `sandbox-exec` profile)
- `RootlessContainerSandbox` (wraps the existing docker path,
  hard-coded `--rm -i --read-only --cap-drop=ALL --network=none`
  unless the listing declares network access)
- `CooperativeFallback` — loud warning, returns the existing
  `SandboxedRunner` behavior.

Proxy runtime refuses to bootstrap with `CooperativeFallback` in
production unless `SECUREMCP_ALLOW_COOPERATIVE_SANDBOX=1` is set.

**Why third:** this is the most impactful control but also the most
work. Shipping Iter 0+1 first means operators get real benefit on
day 1 while this matures.

### Iter 3 — MCP config file integrity (IDE family)

**Change:** define a signed MCP config file schema. Writers embed a
canonical-JSON hash + optional attestation reference. Readers:

- Refuse to load configs without a signature unless the user is in
  an explicit "trust-on-first-use" mode.
- On diff, surface the *resolved command line* (what will actually
  be spawned) not the JSON delta.
- Reject diffs that introduce launcher kinds or arguments the
  existing config didn't have, without an interactive approval that
  shows the resolved argv.

**Why fourth:** primarily a client-side concern, but the schema
lives in this repo and the server is the source of truth for what
attestations exist.

### Iter 4 — Registry submission-review gate

**Change:** `ToolMarketplace.publish()` enters `PENDING_REVIEW`
instead of `LIVE`. `TrustRegistry` records reviewer identity and
attestation hash. `Marketplace.install()` refuses when the resolved
package digest ≠ the attested digest. Document the review checklist
in `docs/servers/security/registry-review.mdx`.

**Why fifth:** F4 is a real gap but small compared to F1/F2/F3. The
checklist is the deliverable; the code plumbing is modest.

### Iter 5 — Capability-bundle rules for stdio

**Change:** extend the default Rego + Cedar bundle at
`src/fastmcp/server/security/policy/capability/bundle.py` with:

- `deny[msg] { input.action == "spawn_stdio" ;
  input.command.launcher in {"sh","bash","zsh","pwsh","cmd",
  "node","python","deno"} ; input.command.has_eval_flag }`
- `require_approval` when the launcher spec diverges from the
  attested `CommandSpec` for a listing.
- `deny` when `input.command.attestation_id` is empty in
  production.

Both Rego and Cedar forms, per the "run both, AND their outputs"
invariant in `bundle.py`.

**Why sixth:** once `CommandSpec` (Iter 1) is in place and OS
sandboxing (Iter 2) exists, the capability bundle is where we
express "these things are never allowed" at the policy layer —
above the transport-level guard and below the sandbox.

### Iter 6 — Reflexive detections for stdio surface

**Change:** add detectors in `src/fastmcp/server/security/reflexive/`:

- Resolved-binary-path drift: same listing, different path ⇒
  `DriftType.PATH_SHADOW`.
- Argv divergence between `list_tools` introspection and
  `call_tool` invocations.
- Subprocess launch outside the declared `CommandSpec`.

Events carry structured argv fields for forensics, redacted by
default (argv-containing-secret heuristic), and surface on the
dashboard timeline.

**Why last:** detection complements prevention. Ship prevention
(Iter 0–5) first; add detection once those controls are producing
a stable signal baseline.

## Out of scope (for this plan)

- Protocol changes. Anthropic has declined. We stay compatible; we
  tighten our own defaults.
- Sandboxing the MCP *client* itself (i.e., the LLM agent). That's a
  separate conversation about agent containment.
- OS-level sandboxes on Windows. The current iteration plan covers
  Linux (landlock/seccomp/rootless-container), macOS (Seatbelt), and
  a cooperative fallback. Windows AppContainer is a follow-up.

## Tracking

See the session task list (`TaskList`) for the iteration queue.
Updates to this file should accompany each iteration's PR.

## Sources

- VentureBeat, "MCP stdio flaw — 200,000 AI agent servers exposed,
  OX Security audit," Louis Columbus, May 1, 2026.
- OX Security research note referenced by the article.
- Cloud Security Alliance independent confirmation (referenced in
  the VentureBeat piece).
- Anthropic's updated MCP `SECURITY.md` guidance (referenced in the
  VentureBeat piece as "didn't fix anything" by OX; credited by
  Carter Rees of Reputation as a meaningful first step).
