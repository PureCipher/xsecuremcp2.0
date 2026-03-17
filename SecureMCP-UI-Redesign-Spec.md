# SecureMCP Registry UI — Redesign Specification

**Prepared for:** Vamsi, PureCipher
**Date:** March 17, 2026
**Scope:** All remaining pillars (Topbar, Tools, Publish, Review, Listings, Publishers, Health, Settings)
**Status:** Design specification — no code changes

---

## 1. Design System Foundation

### 1.1 What We Established in the Policy Pillar

The Policy pillar redesign created a design language that should propagate across every pillar:

| Element | Old Pattern | New Pattern |
|---------|------------|-------------|
| Typography floor | `text-[10px]` (unreadable) | `text-[11px]` minimum, `text-xs` preferred |
| Card radius | Mixed `rounded-xl/2xl/3xl` | `rounded-3xl` for sections, `rounded-2xl` for nested cards |
| Browser dialogs | `window.confirm()`, `window.prompt()` | Styled `ConfirmModal` component |
| Page reload | `window.location.reload()` | `router.refresh()` + `useTransition` |
| Notifications | Inline text errors | `Banner` component (success/error tones) |
| Section headers | Inconsistent | `text-xs font-medium uppercase tracking-[0.18em] text-emerald-300` |
| Long pages | Endless scroll | Tab navigation with persistent stats |

### 1.2 SecureMCP Architecture Layer Labels

Each pillar maps to one or more of the six SecureMCP architecture layers. These labels should appear as subtle section headers throughout the UI so users understand *which trust machinery they're interacting with*:

| Layer | Label | Color Accent | Maps to UI Pillars |
|-------|-------|-------------|-------------------|
| Policy Kernel | `POLICY KERNEL` | Emerald | Policy, Settings |
| Context Broker | `CONTEXT BROKER` | Teal | Listings (data flows) |
| Provenance Ledger | `PROVENANCE LEDGER` | Cyan | Review (audit trail), Versions |
| Reflexive Core | `REFLEXIVE CORE` | Amber | Review (moderation decisions), Health |
| Consent Graph | `CONSENT GRAPH` | Violet | Publishers (trust scores) |
| API Gateway | `API GATEWAY` | Slate | Publish (submission pipeline), Health |

### 1.3 Certification Badge Color System

Currently every certification badge uses the same emerald tone regardless of level. We need color coding:

| Level | Background | Text | Rationale |
|-------|-----------|------|-----------|
| `certified` | `bg-emerald-500/20` | `text-emerald-200` | Full trust — green |
| `basic` | `bg-amber-500/20` | `text-amber-200` | Partial trust — amber |
| `unrated` | `bg-slate-500/20` | `text-slate-300` | Unknown — neutral gray |

This should be a shared utility function used by Tools, Listings, Review, and Publishers.

---

## 2. Topbar Navigation

### 2.1 Current Problems

- **No mobile menu**: Nav links use `hidden sm:flex`, so on phones there's no way to navigate
- **No link grouping**: Public links (Tools, Publishers, Health) and privileged links (Publish, Review, Policy, Settings) are mixed together with no visual separation
- **Active state too subtle**: `bg-emerald-800/80` blends into the dark background; hard to tell which page you're on
- **Branding is small**: The "PC" logo + "PureCipher" text doesn't communicate "SecureMCP" prominently enough
- **Stale reload pattern**: Sign-out uses `router.push("/login")` which is fine, but could use `useTransition` for better UX

### 2.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  [PC]  PureCipher                                                   │
│        SecureMCP Registry    Tools  Publishers  Health  │  Publish   │
│                                                         │  Review    │
│                                                         │  Policy    │
│                                                         │  Settings  │
│                              ───── public ─────    ── privileged ──  │
│                                                                      │
│                                        [Admin]  Signed in: vamsi  [Sign out] │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 Specific Changes

1. **Active tab pill**: Change from `bg-emerald-800/80` to `bg-emerald-500 text-emerald-950 font-semibold` — matches Policy tab bar
2. **Visual separator**: Add a thin `w-px h-4 bg-emerald-700/50` divider between public and privileged nav groups
3. **Mobile hamburger**: Add a hamburger icon button for `sm:hidden` that toggles a dropdown panel with all nav links
4. **Branding**: Make "SecureMCP" the primary text, "PureCipher" the secondary label above it
5. **Role badge**: Keep the Admin/Reviewer/Publisher badge but bump from `text-[10px]` to `text-[11px]`
6. **Logout**: Wrap in `useTransition` for non-blocking UX

---

## 3. Tools Catalog (App Pillar)

### 3.1 Current Problems

- **Duplicate info**: "Signed in as" and "Browse publishers →" are in the header, but the topbar already shows both
- **Developer language**: "Listings below are rendered from the existing Python registry backend via the Next.js frontend" — this is implementation detail, not user-facing copy
- **No summary stats**: User can't quickly see how many tools are certified vs. basic vs. unrated
- **Flat certification badges**: All badges look the same regardless of trust level
- **No search or filtering**: With many tools, there's no way to find what you need

### 3.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  API GATEWAY · TOOL DIRECTORY                                        │
│                                                                      │
│  Trusted Tool Directory                                              │
│  Discover verified, security-conscious MCP tools. Every listing      │
│  passes through the SecureMCP guardrail pipeline.                    │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ 12       │  │ 8        │  │ 3        │  │ 5        │            │
│  │ Total    │  │ Certified│  │ Basic    │  │ Categories│            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
│                                                                      │
│  [ Search tools... ]                                                 │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ Weather Lookup          │  │ Code Analyzer            │          │
│  │ weather-tool · v1.2     │  │ code-scan · v2.0         │          │
│  │ [CERTIFIED]             │  │ [BASIC]                  │          │
│  │                         │  │                          │          │
│  │ Fetches weather data    │  │ Scans code repos for     │          │
│  │ from trusted APIs...    │  │ vulnerabilities...       │          │
│  │                         │  │                          │          │
│  │ [network] [utility]     │  │ [security] [dev-tools]   │          │
│  │ Publisher: acme-tools → │  │ Publisher: secops →      │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Specific Changes

1. **Remove duplicate header info** (signed-in user, publisher link) — topbar handles these
2. **Replace developer copy** with trust-native language: "Discover verified, security-conscious MCP tools. Every listing passes through the SecureMCP guardrail pipeline."
3. **Add stats bar** (reuse `StatsBar` from Policy): total tools, certified count, basic count, category count
4. **Color-code certification badges** per the shared badge system (Section 1.3)
5. **Add publisher link** on each card: "Publisher: acme-tools →" linking to their profile
6. **Optional: Add a search input** for filtering tools by name/category (client-side filter since this is a server component — or a simple query param approach)
7. **Architecture label**: `API GATEWAY · TOOL DIRECTORY` as the section header

---

## 4. Publish Pillar

### 4.1 Current Problems

- **Wall of JSON**: Two large textareas side-by-side with minimal guidance
- **No progressive disclosure**: User sees everything at once — metadata, manifest, runtime, preflight results
- **Preflight results are cramped**: Findings are shown in tiny text with minimal visual hierarchy
- **No template help**: The starter manifest is hardcoded in state; no button to insert a fresh template
- **Error states are bare**: Just red text, no structured banner

### 4.2 Proposed Layout — Stepped Wizard

Instead of showing everything at once, break the submission into clear steps:

```
  Step 1          Step 2          Step 3          Step 4
  [Metadata]  →   [Manifest]  →   [Runtime]   →   [Preflight & Publish]
  ────●────────────○────────────────○────────────────○────

┌──────────────────────────────────────────────────────────────────────┐
│  POLICY KERNEL · TOOL SUBMISSION                                     │
│                                                                      │
│  Share Your Tool                                                     │
│  Describe your tool, paste its manifest, and let the SecureMCP       │
│  guardrail pipeline evaluate trust and compliance before publishing.  │
│                                                                      │
│  ═══ STEP 1: METADATA ═══════════════════════════════════════════    │
│                                                                      │
│  Display name     [ Weather Lookup              ]                    │
│  Categories       [ network, utility            ]                    │
│                                                                      │
│                                              [Next: Manifest →]      │
└──────────────────────────────────────────────────────────────────────┘
```

**Step 4 — Preflight Results:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  ═══ STEP 4: PREFLIGHT & PUBLISH ════════════════════════════════    │
│                                                                      │
│  The guardrail pipeline will check your manifest against the         │
│  registry's policy chain, validate data flows, and compute your      │
│  certification level.                                                │
│                                                                      │
│  [Run Preflight Check]                                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  ✓ Ready to publish            Certification: [CERTIFIED]    │    │
│  │                                 Registry min:  [BASIC]       │    │
│  │  "Manifest passes all guardrails. No policy violations."     │    │
│  │                                                              │    │
│  │  Findings:                                                   │    │
│  │  🟢 INFO    Data flows declared for all endpoints            │    │
│  │  🟡 WARNING No rate-limit policy covers this tool            │    │
│  │  🟢 INFO    Permissions are minimal and scoped               │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  [← Back]                                          [Publish Tool]    │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 Specific Changes

1. **Stepper UX**: 4 steps with a visual progress indicator (numbered circles connected by lines, filled/outlined to show progress)
2. **Progressive disclosure**: Only show one step at a time; "Next" / "Back" navigation
3. **Template button**: "Insert starter manifest" button in Step 2 that populates a clean template
4. **Manifest helper text**: Brief explanation of what each manifest field does (permissions, data_flows, resource_access, tags)
5. **Severity color coding** in preflight findings: critical = rose, warning = amber, info = emerald
6. **Certification badge color** matching the shared system
7. **Banner pattern** for success/error messages (reuse from Policy)
8. **Architecture label**: `POLICY KERNEL · TOOL SUBMISSION`

---

## 5. Review Pillar

### 5.1 Current Problems

- **`window.location.reload()`**: Full page reload after every moderation action — user loses scroll position and any expanded reason fields
- **No confirmation for approve**: Approving a tool is a trust decision that should have at least a lightweight confirmation
- **All action buttons look the same**: Approve (trust-positive) and Reject (trust-negative) use identical emerald-bordered buttons
- **No stats overview**: User doesn't see at a glance how many tools need attention
- **Tiny text**: `text-[10px]` throughout makes the moderation log hard to read
- **No architecture context**: This is the Reflexive Core — where the system decides to trust or block — and the UI doesn't communicate that

### 5.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  REFLEXIVE CORE · TRUST GATE                                         │
│                                                                      │
│  Review Shared Tools                                                 │
│  Approve, reject, or suspend tools before they enter the trusted     │
│  catalog. Every decision is recorded in the provenance ledger.       │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │ 3        │  │ 8        │  │ 1        │                          │
│  │ Pending  │  │ Live     │  │ Paused   │                          │
│  └──────────┘  └──────────┘  └──────────┘                          │
│                                                                      │
│  ┌── Pending ────────┐  ┌── Live ────────────┐  ┌── Paused ─────┐  │
│  │                    │  │                    │  │                │  │
│  │  Weather Lookup    │  │  Code Analyzer     │  │  Data Scraper  │  │
│  │  v1.2 [CERTIFIED]  │  │  v2.0 [BASIC]      │  │  v0.9 [UNRATED]│  │
│  │  publisher: acme   │  │  publisher: secops  │  │  publisher: x  │  │
│  │                    │  │                    │  │                │  │
│  │  [✓ Approve]       │  │  Last: approved by │  │  Last: suspended│  │
│  │  [✗ Reject]        │  │  admin-1 — "Looks  │  │  by mod-2 —    │  │
│  │  [⏸ Suspend]       │  │  good, certified." │  │  "Pending fix." │  │
│  │                    │  │                    │  │                │  │
│  │                    │  │  [⏸ Suspend]       │  │  [↩ Republish] │  │
│  └────────────────────┘  └────────────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Specific Changes

1. **Replace `window.location.reload()`** with `router.refresh()` + `useTransition`
2. **Stats bar** above the lanes: counts for Pending, Live, Paused
3. **Differentiate action button colors**:
   - Approve: `bg-emerald-500 text-emerald-950` (trust-positive, primary)
   - Reject: `border-rose-500/70 text-rose-200` (trust-negative, outlined)
   - Suspend: `border-amber-500/70 text-amber-200` (caution, outlined)
   - Republish: `border-emerald-500/70 text-emerald-200` (restore, outlined)
4. **Confirmation for approve**: Lightweight confirmation panel (not a full modal — just an inline "Are you sure? This tool will be visible in the public catalog." with Confirm/Cancel)
5. **Confirmation for reject/suspend**: Keep the existing reason textarea but style it better — rose background tint for reject, amber for suspend
6. **Show publisher_id** on each card when available
7. **Certification badge colors** per shared system
8. **Bump typography**: `text-[10px]` → `text-[11px]`, `text-[11px]` → `text-xs`
9. **Architecture label**: `REFLEXIVE CORE · TRUST GATE`
10. **Audit trail hint**: Add "Every decision is recorded in the provenance ledger" in the description

---

## 6. Listings Pillar (Tool Detail)

### 6.1 Current Problems

- **No architecture context**: This page shows data flows, verification, and install recipes — it's where the Context Broker and Provenance Ledger layers are most visible, but there's no framing
- **Verification section is buried**: Signature validity and manifest match are critical trust signals but appear as a small nested box
- **Data flows are listed plainly**: These are the core of SecureMCP's promise (knowing what data goes where) but they look like an afterthought
- **Recipe groups use tiny text**: Installation instructions at `text-[11px]` in a 3-column grid can be hard to read

### 6.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Tools / acme-tools / Weather Lookup                                 │
│                                                                      │
│  Weather Lookup                              [CERTIFIED]             │
│  weather-tool · v1.2.0 · Acme Tools Inc.                            │
│                                                                      │
│  ┌── CONTEXT BROKER · Overview ───────┐  ┌── PROVENANCE · Trust ──┐ │
│  │                                     │  │                        │ │
│  │  Fetches weather data from trusted  │  │  ┌─ Verification ────┐│ │
│  │  APIs with geographic scoping and   │  │  │ Signature: ✓ Valid ││ │
│  │  rate limiting.                     │  │  │ Manifest:  ✓ Match ││ │
│  │                                     │  │  │ Issues: None       ││ │
│  │  [network] [utility] [weather]      │  │  └────────────────────┘│ │
│  │                                     │  │                        │ │
│  │  ┌─ Data Flows ──────────────────┐  │  │  ┌─ Start Here ──────┐│ │
│  │  │                               │  │  │  │                   ││ │
│  │  │  🔵 external:                 │  │  │  │  pip install ...  ││ │
│  │  │     user-query → weather-api  │  │  │  │                   ││ │
│  │  │     "Sends location to API"   │  │  │  └───────────────────┘│ │
│  │  │                               │  │  │                        │ │
│  │  │  🟢 internal:                 │  │  └────────────────────────┘ │
│  │  │     cache → response          │  │                             │
│  │  │     "Caches API responses"    │  │                             │
│  │  └───────────────────────────────┘  │                             │
│  └─────────────────────────────────────┘                             │
│                                                                      │
│  ═══ INSTALLATION RECIPES ═══════════════════════════════════════    │
│                                                                      │
│  ┌── Client Setup ──┐  ┌── Docker ──────┐  ┌── Verification ───┐   │
│  │ MCP HTTP Client   │  │ Docker Compose │  │ Attestation Check  │   │
│  │ ...               │  │ ...            │  │ ...                │   │
│  └───────────────────┘  └────────────────┘  └────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.3 Specific Changes

1. **Elevate Verification**: Move it from a nested box to a prominent "Trust Signals" section at the top-right with clear checkmark/cross icons
2. **Elevate Data Flows**: Give them their own visually distinct section with color-coded classification:
   - `external` flows: blue accent (data leaves the system)
   - `internal` flows: green accent (data stays internal)
   - `sensitive` flows: amber accent (personal/regulated data)
3. **Architecture labels**: `CONTEXT BROKER · OVERVIEW` for the description/data-flows section, `PROVENANCE LEDGER · TRUST` for verification
4. **Recipe layout**: Increase `max-h` on code blocks, bump text to `text-xs`, use 2-column grid on medium screens instead of 3
5. **Certification badge**: Color-coded per shared system, larger and more prominent in the header
6. **Breadcrumb**: Keep the existing breadcrumb but bump typography

---

## 7. Publishers Pillar

### 7.1 Current Problems

- **Trust score is underplayed**: The most important signal — the trust score — is just a small pill badge
- **No breakdown of trust**: What contributes to the score? Users can't tell
- **Profile detail page is sparse**: Just "About" text and a tool list
- **No architecture context**: Publishers represent the Consent Graph layer (identity + trust computation)

### 7.2 Proposed Layout — Directory Page

```
┌──────────────────────────────────────────────────────────────────────┐
│  CONSENT GRAPH · PUBLISHER DIRECTORY                                 │
│                                                                      │
│  People and Teams Behind the Tools                                   │
│  Browse publishers with live listings. Trust scores are computed      │
│  from certification levels, moderation history, and data flow         │
│  declarations.                                                       │
│                                                                      │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │ Acme Tools Inc.              │  │ SecOps Research              │ │
│  │                              │  │                              │ │
│  │ ████████░░ Trust 8.2         │  │ ██████░░░░ Trust 6.0         │ │
│  │                              │  │                              │ │
│  │ "Enterprise-grade weather    │  │ "Open-source security        │ │
│  │ and geolocation tools..."    │  │ scanning tools..."           │ │
│  │                              │  │                              │ │
│  │ 5 tools · 4 certified        │  │ 3 tools · 1 certified        │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.3 Proposed Layout — Profile Detail Page

```
┌──────────────────────────────────────────────────────────────────────┐
│  CONSENT GRAPH · PUBLISHER PROFILE                                   │
│                                                                      │
│  Acme Tools Inc.                        Trust Score: 8.2 / 10        │
│  acme-tools · 5 tools in this registry                               │
│                                                                      │
│  ┌── About ────────────────────┐  ┌── Trust Snapshot ─────────────┐ │
│  │                              │  │                               │ │
│  │  Enterprise-grade weather    │  │  Tools:          5            │ │
│  │  and geolocation tools for   │  │  Certified:      4            │ │
│  │  AI agent pipelines.         │  │  Basic:          1            │ │
│  │                              │  │  Avg data flows: 3.2 per tool │ │
│  └──────────────────────────────┘  │  Moderation:     0 suspensions│ │
│                                     └─────────────────────────────┘ │
│                                                                      │
│  ═══ TOOLS FROM THIS PUBLISHER ═════════════════════════════════    │
│  (tool cards with certification badges, same as Tools catalog)       │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.4 Specific Changes

1. **Trust score visualization**: Add a simple progress bar or segmented bar (████████░░ 8.2) instead of just a number
2. **Trust breakdown** on detail page: Show what contributes — certified tool %, data flow coverage, moderation history
3. **Architecture label**: `CONSENT GRAPH · PUBLISHER DIRECTORY` / `CONSENT GRAPH · PUBLISHER PROFILE`
4. **Enhanced tool cards** on profile: Reuse the same card component as Tools catalog (with certification colors)
5. **Bump typography** consistently

---

## 8. Health Pillar

### 8.1 Current Problems

- **Just 3 boxes**: Status, Policy, Counts — very sparse
- **No visual status indicator**: "Healthy" is just text; should be a prominent green/red indicator
- **No connection to architecture layers**: This page should show health across all six layers
- **Timestamp is buried**: Last-updated time is easy to miss

### 8.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  REFLEXIVE CORE · REGISTRY HEALTH                                    │
│                                                                      │
│  SecureMCP Registry Status                                           │
│  Live snapshot of the guardrail pipeline, authentication, and        │
│  registry counts.                        Last checked: 2 min ago     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │              ● HEALTHY                                       │    │
│  │  All systems operational. Guardrail pipeline responding.     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌── Registry ───────┐  ┌── Policy ──────────┐  ┌── Auth ────────┐ │
│  │                    │  │                    │  │                 │ │
│  │  Registered: 12    │  │  Min. cert: BASIC  │  │  Auth: Enabled  │ │
│  │  Verified:    8    │  │  Moderation: Yes   │  │  Issuer: pc-01  │ │
│  │  Pending:     3    │  │                    │  │                 │ │
│  └────────────────────┘  └────────────────────┘  └─────────────────┘ │
│                                                                      │
│  ┌── Architecture Layer Health ──────────────────────────────────┐   │
│  │  ● Policy Kernel     Active · 3 rules in live chain          │   │
│  │  ● Context Broker    Active · Processing requests            │   │
│  │  ● Provenance Ledger Active · 847 events recorded            │   │
│  │  ● Reflexive Core    Active · 0 escalations today            │   │
│  │  ● Consent Graph     Active · 4 publishers registered        │   │
│  │  ● API Gateway       Active · Auth enabled                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 8.3 Specific Changes

1. **Prominent status indicator**: Large green dot + "HEALTHY" in a full-width banner card at the top
2. **Architecture layer health**: New section showing each of the 6 SecureMCP layers with a green/amber/red dot and one-line status
3. **Relative timestamp**: "Last checked: 2 min ago" instead of raw ISO timestamp
4. **Architecture label**: `REFLEXIVE CORE · REGISTRY HEALTH`
5. **3-column grid** for Registry/Policy/Auth stays but with improved spacing and typography

---

## 9. Settings Pillar

### 9.1 Current Problems

- **Mostly redundant**: Overlaps heavily with Health page
- **Read-only but doesn't explain why**: Users might expect to edit settings here
- **Links to Policy and Health are buried** in footnote text

### 9.2 Proposed Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  POLICY KERNEL · CONFIGURATION                                       │
│                                                                      │
│  Registry Configuration                                              │
│  Read-only view of how this SecureMCP registry is configured.        │
│  To change policy rules, go to the Policy page.                      │
│                                                                      │
│  ┌── Certification & Moderation ──┐  ┌── Authentication ──────────┐ │
│  │                                 │  │                            │ │
│  │  Minimum level:   BASIC         │  │  Auth enabled:   Yes       │ │
│  │  Moderation:      Required      │  │  Issuer ID:      pc-reg-01│ │
│  │                                 │  │                            │ │
│  └─────────────────────────────────┘  └────────────────────────────┘ │
│                                                                      │
│  ┌── Quick Links ────────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  [→ Manage Policy Rules]    [→ View Registry Health]          │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.3 Specific Changes

1. **Architecture label**: `POLICY KERNEL · CONFIGURATION`
2. **Clarify read-only nature**: "Read-only view" in the description, with a direct link to Policy for edits
3. **Elevate quick links**: Make Policy and Health links into prominent card-style buttons instead of footnote text
4. **Bump typography** throughout
5. **Consider merging** into Health page as a tab if the team wants fewer top-level nav items

---

## 10. Cross-Cutting UX Improvements

### 10.1 Shared Components to Extract

| Component | Used By | Purpose |
|-----------|---------|---------|
| `CertificationBadge` | Tools, Listings, Review, Publishers | Color-coded certification level pill |
| `StatsBar` | Tools, Review, Health (already exists in Policy) | Horizontal stat cards |
| `Banner` | Publish, Review (already exists in Policy) | Success/error notification |
| `ConfirmModal` | Review (already exists in Policy) | Styled confirmation dialog |
| `ArchitectureLabel` | All pillars | `text-xs font-medium uppercase tracking-[0.18em]` section header with layer name |

### 10.2 Typography Standards

| Use Case | Class | Size |
|----------|-------|------|
| Page title | `text-2xl font-semibold text-emerald-50` | 24px |
| Section heading | `text-xl font-semibold text-emerald-50` | 20px |
| Architecture label | `text-xs font-medium uppercase tracking-[0.18em] text-emerald-300` | 12px |
| Body text | `text-xs text-emerald-100/90` | 12px |
| Small labels | `text-[11px] text-emerald-200/90` | 11px |
| **Never use** | ~~`text-[10px]`~~ | ~~10px~~ |

### 10.3 Interaction Patterns

| Action | Old Pattern | New Pattern |
|--------|------------|-------------|
| Page refresh after mutation | `window.location.reload()` | `router.refresh()` + `useTransition` |
| Dangerous confirmation | `window.confirm()` | `ConfirmModal` component |
| Text input prompt | `window.prompt()` | Inline form or `ConfirmModal` with children |
| Error display | Inline `<p className="text-rose-300">` | `Banner` component with `tone="error"` |
| Success feedback | Inline `<p className="text-emerald-200">` | `Banner` component with `tone="success"` |

### 10.4 Color Palette Consistency

| Element | Current | Proposed |
|---------|---------|----------|
| Card background | `bg-emerald-900/40` | `bg-emerald-900/40` (keep) |
| Card border | `ring-1 ring-emerald-700/60` | `ring-1 ring-emerald-700/60` (keep) |
| Nested card | `bg-emerald-950/70 ring-1 ring-emerald-700/70` | Keep (good contrast) |
| Primary button | `bg-emerald-400 text-emerald-950` | `bg-emerald-500 text-emerald-950` (slightly richer) |
| Danger button | Same as primary | `border-rose-500/70 text-rose-200` |
| Warning button | Same as primary | `border-amber-500/70 text-amber-200` |

---

## 11. Implementation Priority

| Priority | Pillar | Effort | Impact |
|----------|--------|--------|--------|
| 1 | **Review** | Medium | High — trust gate, `window.location.reload()` removal |
| 2 | **Topbar** | Low | High — mobile nav, active state, affects every page |
| 3 | **Publish** | Medium | High — publisher-facing, preflight UX |
| 4 | **Listings** | Low | Medium — trust signal visibility |
| 5 | **Tools** | Low | Medium — first page users see |
| 6 | **Health** | Low | Low-Medium — architecture layer visibility |
| 7 | **Publishers** | Low | Low — trust score visualization |
| 8 | **Settings** | Very Low | Low — minor polish |

---

## 12. Note on Already-Modified Files

During this session, automated agents modified the following files before the design-only instruction was received:

- `topbar.tsx` (130 → 270 lines)
- `app/page.tsx` (95 → 146 lines)
- `review/page.tsx` and `ReviewActions.tsx`
- `publish/page.tsx` and `PublisherForm.tsx`

These changes implement some of the patterns described above but were not reviewed against this design spec. They should be evaluated against this document before being accepted, and reverted if they don't match the approved design direction.
