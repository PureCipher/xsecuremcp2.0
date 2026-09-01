# PureCipher Secure MCP Registry
## Hosting Options & Sales Sheet

**Document version:** Draft — June 2026  
**Audience:** Sales, solutions engineering, customer-facing teams  
**Status:** Proposed offering — pricing requires leadership sign-off before quoting  

**Product stack (two repos):**

| Repository | Role |
|------------|------|
| **[xsecuremcp2.0](https://github.com/PureCipher/xsecuremcp2.0)** | SecureMCP engine + `purecipher-registry` API (certification, governance planes, proxy runtime) |
| **[xregistry](https://github.com/PureCipher/xregistry)** | Next.js product UI — operator console, publisher workflows, public catalog |

---

# PAGE 1 — HOSTING OPTIONS SHEET

## Overview

Every deployment runs the same logical stack:

```
┌─────────────────────────────────────────────────────────────────┐
│  END USERS / MCP CLIENTS                                        │
│  (Claude Desktop, Claude Code, Cursor, custom agents, CI bots)│
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────────────────────┐
│ Public Catalog  │ │ Operator      │ │ Registry API            │
│ (xregistry)     │ │ Console       │ │ (xsecuremcp2.0)         │
│ Port 3001       │ │ (xregistry)   │ │ Port 8000               │
│ Discovery,      │ │ Port 3000     │ │ Certification, policy,  │
│ install recipes │ │ Publish,      │ │ moderation, proxy       │
│                 │ │ govern, audit │ │ gateways, persistence   │
└────────┬────────┘ └───────┬───────┘ └────────────┬────────────┘
         │                  │                      │
         └──────────────────┴──────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ Upstream MCP servers        │
              │ (customer-owned or 3rd-party)│
              │ HTTP · PyPI · npm · Docker  │
              └─────────────────────────────┘
```

**Full stack launch (Docker):** clone `xregistry` beside `xsecuremcp2.0`, then:

```bash
export SECUREMCP_REPO=../xsecuremcp2.0
docker compose --env-file .env.compose.example up --build
```

| Surface | Default URL | Purpose |
|---------|-------------|---------|
| Operator console | `http://localhost:3000` | Publishers, reviewers, admins |
| Public catalog | `http://localhost:3001` | End-user discovery & install guidance |
| Registry API | `http://localhost:8000/registry/*` | Backend + optional proxy MCP endpoints |

---

## Hosting Mode A — CATALOG (customer runs MCP servers)

**What it is:** The registry is the **trust and discovery control plane**. Listings include signed manifests, certification level, attestation, and install recipes. MCP clients connect **directly to the upstream** server (PyPI package, npm package, Docker image, or HTTP endpoint).

**Best for:**
- Customers who already host MCP servers internally
- Regulated environments where runtime must stay in the customer VPC
- First-phase rollouts (fastest time-to-value)
- Air-gapped or on-prem deployments

**PureCipher operates:** Registry API + UI only  
**Customer operates:** All MCP server runtimes  

**Sales note:** This is the **default MVP story** and matches the product docs: *“verified registry, not full hosted runtime.”*

---

## Hosting Mode B — PROXY (registry-hosted SecureMCP gateway)

**What it is:** For selected listings, the registry mounts a **SecureMCP gateway** in front of the upstream. Clients connect to a registry URL (e.g. `/runtime/proxy/{listing_id}/mcp`). The gateway enforces the listing’s manifest — tool allowlists, policy, consent, and contracts at the edge.

**Best for:**
- “No direct upstream URLs for agents” policies
- Central enforcement without re-writing every MCP server
- Curator-onboarded third-party tools (npm/PyPI/Docker) where the original author is not involved
- Pilot customers who want governance before committing to self-hosting every server

**PureCipher operates:** Registry + proxy gateway layer (when managed)  
**Customer operates:** Upstream servers (or approves curator-pinned upstreams)  

**Sales note:** **Built and demo-ready** (full flow: onboard → approve → register client → connect via proxy). Position as **design-partner / controlled rollout** until multi-tenant proxy ops are hardened at scale.

---

## Deployment Option 1 — Customer Self-Hosted

| Attribute | Detail |
|-----------|--------|
| **Who runs it** | Customer infrastructure team |
| **Delivery** | Docker Compose (full stack) or Kubernetes manifests (customer-built) |
| **Data residency** | 100% customer-controlled |
| **Components** | `purecipher-registry` image + `xregistry` console + public UI |
| **Persistence** | SQLite (default) or customer-managed volume; PostgreSQL path available via custom deployment |
| **Secrets** | Customer manages `PURECIPHER_SIGNING_SECRET`, `PURECIPHER_JWT_SECRET`, user directory |
| **Typical buyer** | Financial services, healthcare, defense, large enterprise platform teams |
| **PureCipher revenue** | Software license + optional support/implementation |

**Minimum requirements (full product stack):**
- Linux host or K8s cluster with Docker
- 2 vCPU / 4 GB RAM (dev); 4 vCPU / 8 GB RAM+ (production — scales with listings and proxy traffic)
- Outbound network for curator introspection (npm, PyPI, Docker pull) unless air-gapped workflow
- TLS termination at customer load balancer or ingress

**Optional profile — control-plane only:** Run registry API without hosted toolset gateways (`control-plane-only` Docker profile). Use when customer wants governance UI but zero proxy hosting on the registry node.

---

## Deployment Option 2 — PureCipher Managed — Single-Tenant (Dedicated)

| Attribute | Detail |
|-----------|--------|
| **Who runs it** | PureCipher SRE / platform team |
| **Isolation** | Dedicated namespace or VPC per customer |
| **URL pattern** | `{customer}.registry.purecipher.io` (example — confirm branding) |
| **Components** | Same three-service stack, customer-specific secrets and DB |
| **Data residency** | Region-selectable (US/EU — confirm availability) |
| **Typical buyer** | Mid-market to enterprise wanting fast rollout without ops burden |
| **PureCipher revenue** | Monthly platform fee + implementation |

**Included in managed single-tenant:**
- Registry API + console + public catalog
- Automated backups of registry DB
- TLS, health checks, uptime monitoring
- Moderation + governance planes enabled per SKU
- Customer SSO integration (when available — confirm roadmap)

---

## Deployment Option 3 — PureCipher Managed — Multi-Tenant (Shared Platform)

| Attribute | Detail |
|-----------|--------|
| **Who runs it** | PureCipher |
| **Isolation** | Logical tenant isolation (auth, data, signing keys per org) |
| **Typical buyer** | SMB, agencies, MSPs reselling governed MCP catalogs |
| **Status** | **Future / not lead SKU today** — requires additional ops and security hardening |
| **PureCipher revenue** | Lower per-seat or per-org subscription |

**Sales guidance:** Do not lead with multi-tenant unless explicitly requested. Offer single-tenant managed or self-hosted first.

---

## Deployment Option 4 — Hybrid

| Attribute | Detail |
|-----------|--------|
| **Pattern** | Control plane self-hosted in customer VPC; proxy gateways in PureCipher-managed edge **or** reverse |
| **Typical buyer** | Regulated customers needing data in-house but wanting PureCipher to operate proxy scaling |
| **PureCipher revenue** | Platform license + managed proxy add-on |

**Example:** Customer runs catalog + governance in their VPC. PureCipher operates PROXY gateways in a connected subnet for approved third-party listings only.

---

## Deployment Option 5 — Air-Gapped / On-Premises License

| Attribute | Detail |
|-----------|--------|
| **Delivery** | Offline image bundle + installation runbook |
| **Curator introspection** | Limited to pre-approved artifact mirrors (no public npm/PyPI) |
| **Updates** | Quarterly or on-demand patch bundles |
| **Premium** | +30–50% over equivalent cloud/SaaS tier |
| **Typical buyer** | Government, critical infrastructure, classified networks |

---

## Hosting Mode × Deployment Matrix

|  | Self-Hosted | Managed Single-Tenant | Hybrid | Air-Gapped |
|--|-------------|----------------------|--------|------------|
| **CATALOG only** | ✅ Primary | ✅ Primary | ✅ | ✅ |
| **CATALOG + PROXY** | ✅ (customer ops proxy) | ✅ (PureCipher ops proxy) | ✅ Best fit | ⚠️ Limited (no live introspection) |
| **Control-plane only** | ✅ Docker profile | ✅ | ✅ | ✅ |
| **Public catalog site** | ✅ xregistry `:3001` | ✅ Custom domain | ✅ | ⚠️ Internal-only URL |
| **Curator onboard (npm/PyPI/Docker)** | ✅ Needs Docker socket / outbound | ✅ | ✅ | ❌ Manual manifest only |

---

## Environment Topology (Recommended for Enterprise)

| Environment | Purpose | Typical config |
|-------------|---------|----------------|
| **Development** | Publisher testing, policy drafts | Moderation optional; lower cert bar |
| **Staging** | Reviewer simulation, pre-prod proxy tests | Mirror of prod policy; fake upstreams |
| **Production** | Live catalog + governed client connections | Moderation required; minimum cert = Basic or Standard |

Each environment = separate registry instance (separate DB, signing secret, JWT issuer). Policy promotion workflows in the console support staging → production migration previews.

---

## Technical Prerequisites (Hand to Solutions Engineering)

| Requirement | Detail |
|-------------|--------|
| **Backend** | Python 3.12 container (`Dockerfile.purecipher-registry`) |
| **Frontend** | Node.js 22+ (`xregistry` Next.js App Router) |
| **Auth** | JWT (built-in); map to customer IdP via future SSO or API gateway |
| **Roles** | Viewer · Publisher · Reviewer · Admin |
| **Upstream channels** | HTTP/SSE, PyPI (`uvx`), npm (`npx`), Docker |
| **Certification levels** | Uncertified → Self-attested → Basic → Standard → Strict |
| **Attestation kinds** | AUTHOR (publisher signs) · CURATOR (reviewer vouches for third-party) |
| **Listing lifecycle** | Draft → Pending review → Published → Suspended |

---

## Hosting Decision Guide (for sales calls)

**Ask the customer:**

1. *“Do MCP servers need to stay inside your network, or can a gateway sit in front?”*  
   → Inside only = **CATALOG + self-hosted**  
   → Gateway OK = **PROXY** add-on

2. *“Who will operate the registry — your platform team or us?”*  
   → Their team = **Self-hosted**  
   → PureCipher = **Managed single-tenant**

3. *“Do you need a public-facing tool directory for employees, or admin-only?”*  
   → Employees = enable **public catalog UI**  
   → Admins only = console-only deployment

4. *“Are you approving tools your teams built, tools from the ecosystem, or both?”*  
   → Built = **Publisher (author) path**  
   → Ecosystem = **Curator onboard path**

---

# PAGE 2+ — COMPREHENSIVE SALES SHEET

## Product Name & Tagline

**PureCipher Secure MCP Registry**

*Find a tool fast. Verify it once. Install — or connect — with confidence.*

Enterprise private registry for MCP tools: signed manifests, certification, human moderation, optional governed proxy, and full SecureMCP control planes behind a modern operator console.

---

## The Problem We Solve

Organizations adopting MCP face a governance gap:

| Without PureCipher | With PureCipher |
|--------------------|-----------------|
| Agents connect to arbitrary MCP endpoints | Approved catalog with certification tiers |
| No central record of what tools declare vs. do | Signed `SecurityManifest` + attestation verification |
| Security learns about new tools after deployment | Moderation queue before publish |
| No stable client identity across audit logs | Registered MCP clients with API tokens |
| Policy is documentation, not enforcement | Policy Kernel with simulate → approve → deploy |
| No tamper-evident audit trail | Provenance Ledger (hash-linked records) |

**Trigger events for buyers:** AI governance program launch · MCP pilot scaling beyond one team · security review blocking “connect any MCP server” · compliance audit asking “what can agents access?”

---

## What We Sell (Capability Layers)

### Layer 1 — Trusted Catalog (all SKUs)
- Searchable verified tool directory
- Publisher profiles and listing detail pages
- Install recipes (Claude Desktop, Claude Code, Docker, HTTP)
- Attestation verification (`POST /registry/verify`)
- Public discovery site (xregistry public UI)
- Publisher CLI: `init` · `check` · `package` · `publish`

### Layer 2 — Governance & Moderation (Business tier+)
- Human review queue (approve · reject · request changes · suspend)
- Certification pipeline (Basic / Standard / Strict)
- Minimum certification policy (registry-wide floor)
- Policy Kernel — declarative rules, proposals, simulation, version diff, rollback
- Provenance Ledger — per-client activity and audit trail
- Role-based access (viewer / publisher / reviewer / admin)

### Layer 3 — Runtime Control (Enterprise / Proxy add-on)
- **PROXY hosting mode** — registry-hosted SecureMCP gateway
- Client identity registry — register agents, issue tokens, per-client governance dashboard
- Contract Broker — capability contracts between tools and callers
- Consent Graph — permission grants with delegation
- Reflexive Core — behavioral drift detection and escalation
- Access Studio — simulate tool eligibility before clients connect

### Layer 5 SecureMCP Control Planes (admin-togglable)
All five planes ship enabled by default; customers can opt out per plane for cost/simplicity:

1. Policy  
2. Contracts  
3. Consent  
4. Provenance  
5. Reflexive  

---

## Two Onboarding Paths (Key Differentiator)

### Path A — Publisher (Author)
*The team that built the MCP server publishes it.*

1. Scaffold project (`purecipher-publisher init`) or paste manifest in console  
2. Connect running server (HTTP, PyPI, npm, Docker) for introspection  
3. Preflight validation → submit → **Pending review**  
4. Reviewer approves → **Published** with AUTHOR attestation  

### Path B — Curator (Third-Party Vouch)
*Security/platform team vouches for an external MCP server the org wants to use.*

1. Paste upstream (npm / PyPI / Docker / HTTP URL)  
2. Registry introspects tools, drafts manifest  
3. Curator selects hosting mode (Catalog or Proxy), signs listing  
4. Same review queue → **Published** with CURATOR attestation  

**Sales angle:** Curator path solves *“we want `@modelcontextprotocol/server-filesystem` but need it governed”* without waiting for the upstream author.

---

## Competitive Positioning

| Alternative | What it is | PureCipher difference |
|-------------|------------|----------------------|
| **[GitHub MCP Registry](https://github.com/mcp)** | Public open registry / discovery | We are **private, governed, certifiable** — enterprise trust boundary |
| **Prefect Horizon** | Managed FastMCP hosting + org registry | Horizon optimizes **deploy & host**; we optimize **trust, policy, audit, proxy enforcement** |
| **DIY internal wiki + allowlist** | Spreadsheet of approved URLs | **Executable governance** — manifests, simulation, provenance, not static docs |
| **Client-side MCP config only** | Each user edits `mcp.json` | **Central catalog**, moderation, install recipes, client identity |

**Do not compete on:** “fastest way to deploy any Python MCP server.”  
**Do compete on:** “only approved, attested, auditable MCP tools reach your agents.”

---

## Packaging & Proposed Pricing

> **Important:** All figures are **proposed starting points**. Confirm with leadership before issuing quotes. Use **pilot SOW** for first customers.

### Tier 1 — Starter · Private Catalog
**Target:** Single team / innovation lab / first MCP rollout  

| | |
|--|--|
| **Monthly** | $2,500 – $5,000 |
| **Annual (prepaid)** | $25,000 – $40,000 |
| **Listings** | Up to 25 published |
| **Users** | Up to 50 |
| **Environments** | 1 |
| **Includes** | Catalog, moderation, certification (Basic/Standard), public catalog UI, publisher CLI |
| **Hosting** | Self-hosted included; managed +$1,500/mo |
| **Proxy** | Not included |
| **Support** | Email, business hours |

---

### Tier 2 — Business · Governed Registry ⭐ *Default enterprise SKU*
**Target:** Platform, security, or AI governance teams rolling out MCP org-wide  

| | |
|--|--|
| **Monthly** | $8,000 – $15,000 |
| **Annual (prepaid)** | $80,000 – $150,000 |
| **Listings** | Up to 100 |
| **Users** | Up to 200 |
| **Environments** | Dev + Production |
| **Includes** | Everything in Starter + Policy Kernel, Provenance, Client identity, Contracts, Consent, Reflexive, Access Studio |
| **Hosting** | Managed single-tenant included **or** self-hosted with premium support |
| **Proxy** | Up to 5 listings (pilot quota) |
| **Implementation** | $15,000 – $40,000 one-time (policy templates, SSO prep, first 10 listings) |
| **Support** | Priority, 4-hr response SLA (business hours) |

---

### Tier 3 — Enterprise · Governed + Proxy at Scale
**Target:** Large orgs, regulated industries, MSP/strategic accounts  

| | |
|--|--|
| **Monthly** | $20,000 – $40,000+ (custom) |
| **Annual** | Custom MSAs |
| **Listings / users** | Unlimited (fair use) |
| **Environments** | Dev + Staging + Production + DR |
| **Includes** | Full stack, dedicated CSM, quarterly governance review, Strict certification workflows |
| **Proxy** | 10+ listings included; +$500 – $1,500/listing/mo additional |
| **Usage option** | +$0.002 – $0.01 per proxied tool call (optional meter) |
| **Support** | 24×7 option, dedicated Slack channel |

---

### Pilot / Design Partner (First 3–5 Logos)

| | |
|--|--|
| **Fixed fee** | $15,000 – $25,000 for 90 days |
| **Scope** | 1 production environment, Catalog + Governance, up to 5 proxy listings, weekly check-in |
| **Conversion** | 100% credit toward Year 1 if signed within 30 days of pilot end |

---

### Add-On Menu

| Add-on | Price guide |
|--------|-------------|
| Extra environment (staging) | $1,500 – $3,000/mo |
| Additional proxy listing | $500 – $1,500/mo each |
| Professional services (curator onboarding) | $200 – $350/hr or fixed SOW |
| Publisher / CI workshop | $5,000 fixed |
| Air-gapped / on-prem license premium | +30 – 50% |
| Annual support renewal (self-hosted) | 20% of license |

---

## Ideal Customer Profile (ICP)

**Strong fit:**
- 500+ employees with an active AI/agent initiative
- Existing security governance function (GRC, AppSec, AI risk)
- Platform team evaluating MCP at scale
- Regulated industry (finance, healthcare, energy, public sector)
- Already blocked or slowed by “agents connecting to unknown MCP servers”

**Weak fit (qualify out early):**
- Solo developer wanting free public hosting
- Buyer only wants generic LLM chat — no tool/integration angle
- Needs only one MCP server with no approval workflow

---

## Buyer Personas & Messages

| Persona | Pain | Message |
|---------|------|---------|
| **CISO / GRC** | Uncontrolled agent tool access | “Every MCP tool is attested, reviewable, and auditable before agents reach it.” |
| **Platform / DevOps** | Fragmented MCP configs | “One catalog, install recipes, client identity — stop emailing `mcp.json` snippets.” |
| **AI / Innovation lead** | Security blocking pilots | “Give security a registry they can approve; unblock teams with a governed catalog.” |
| **Enterprise architect** | Integration sprawl | “Curator-onboard npm/PyPI/Docker servers without rewriting them as SecureMCP.” |

---

## Sales Call Talk Track (5 minutes)

1. **Hook (30 sec):** “Your teams are connecting AI clients to MCP tools. Who approved those endpoints, and can you prove what they declared?”

2. **Product (60 sec):** “PureCipher Secure MCP Registry is your private MCP app store with certification, moderation, and optional governed proxy. Built on SecureMCP — the trust-native layer on FastMCP.”

3. **Demo story (90 sec):** “A curator onboards a third-party npm MCP server. The registry introspects it, drafts a manifest, human reviewer approves, you register Claude Code as a client identity, and agents connect through a proxy that enforces policy — full audit in the provenance ledger.”

4. **Hosting (60 sec):** “Catalog mode if you host servers yourself. Proxy mode if you want us — or the registry — sitting in front. Self-hosted, our managed single-tenant, or hybrid.”

5. **Commercial (60 sec):** “Business tier for governed registry is typically eight to fifteen K a month, or we run a ninety-day pilot for fifteen to twenty-five K fixed. Implementation helps you stand up policy and your first ten listings.”

6. **Close (30 sec):** “Who owns MCP governance on your side — security, platform, or the AI team? Can we schedule a thirty-minute demo with them?”

---

## Objection Handling

| Objection | Response |
|-----------|----------|
| “GitHub already has an MCP registry.” | “That’s public discovery. We’re your **private trust boundary** — moderation, certification, audit, optional proxy inside your org.” |
| “We’ll build this ourselves.” | “You can — the engine is SecureMCP. Most teams underestimate policy simulation, provenance, curator introspection, and client identity. We deliver a working console today.” |
| “We don’t want another SaaS.” | “Self-hosted and air-gapped licenses are first-class. Same product, your VPC.” |
| “Proxy sounds risky.” | “Start with **Catalog only** — zero runtime in our boundary. Add Proxy for specific third-party tools when ready.” |
| “What about Horizon / other hosts?” | “Horizon is great for deploying servers. We govern **which tools agents may use** and **prove what happened** — complementary, not identical.” |

---

## Proof Points & Demo Readiness

| Claim | Evidence |
|-------|----------|
| Product exists | `xregistry` + `xsecuremcp2.0` docker-compose full stack |
| End-to-end proxy flow | `demo/onboard_demo.sh` — onboard → approve → client token → proxy URL |
| Governance UI | Policy, Provenance, Clients, Contracts, Consent, Reflexive in console nav |
| Publisher tooling | `purecipher-publisher` CLI in xsecuremcp2.0 |
| Sales deck | `scripts/build_registry_deck.js` (10-slide narrative) |

**Demo command (SE prep):**
```bash
# Terminal 1 — from xregistry repo
export SECUREMCP_REPO=../xsecuremcp2.0
docker compose --env-file .env.compose.example --profile demo up --build
# Console: localhost:3000 | Public: localhost:3001 | API: localhost:8000
```

---

## What to Say vs. What to Hold

| ✅ Safe to mention now | ⚠️ Position carefully | ❌ Do not promise yet |
|------------------------|----------------------|---------------------|
| Private governed catalog | Multi-tenant shared SaaS | Unlimited proxy without sizing |
| Catalog + Proxy hosting modes | SSO/SAML (if not shipped) | Public `registry.purecipher.com` unless live |
| Self-hosted Docker stack | Strict cert for all listings day one | Beating Horizon on raw deploy speed |
| 90-day pilot program | Consumption pricing (optional) | Full FedRAMP (unless pursued) |
| Curator third-party onboard | Docker socket security trade-offs in prod | |

---

## Implementation Timeline (Typical Business Tier)

| Week | Milestone |
|------|-----------|
| 0–1 | Kickoff, hosting decision, secrets, IdP plan |
| 1–2 | Deploy stack (managed or self-hosted), auth + roles |
| 2–3 | Policy templates, minimum cert level, moderation workflow |
| 3–4 | First 3–5 listings (author or curator path) |
| 4–6 | Client identities, pilot user group, provenance review |
| 6–8 | Production cutover, optional proxy listings |

---

## Contacts & Internal Routing

| Need | Route to |
|------|----------|
| Technical demo | Solutions engineering + `xregistry` / `xsecuremcp2.0` demo env |
| Pricing approval | Leadership / finance |
| Security questionnaire | Engineering + GRC template (create if missing) |
| Custom MSA / air-gap | Legal + engineering scoping call |

---

## Document Control

| Field | Value |
|-------|-------|
| Product | PureCipher Secure MCP Registry |
| Backend repo | PureCipher/xsecuremcp2.0 |
| UI repo | PureCipher/xregistry |
| Pricing status | **DRAFT — not approved for external quotes** |
| Next review | After first 2 pilot conversations |

---

*PureCipher · Secure MCP Registry · Confidential — Internal & Partner Sales Use*
