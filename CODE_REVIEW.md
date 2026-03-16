# FastMCP v2.0 — Full Code Stack Review

**Date:** March 16, 2026
**Scope:** Complete codebase review of `src/fastmcp/` (334 Python files, ~90K lines) and `tests/` (401 files, ~121K lines)

---

## 1. Architecture Overview

FastMCP v2.0 is a comprehensive Python framework (≥3.10) for building Model Context Protocol servers and clients. The architecture is layered and modular:

```
┌─────────────────────────────────────────────────────┐
│                    CLI (cyclopts)                    │
├─────────────────────────────────────────────────────┤
│          Client SDK          │     Server SDK        │
│  (transports, auth, sampling)│  (FastMCP main class) │
├──────────────────────────────┼───────────────────────┤
│  Tools │ Resources │ Prompts │  Middleware Chain      │
├──────────────────────────────┼───────────────────────┤
│     Provider System          │  Auth / Security       │
│  (Local, Proxy, OpenAPI,     │  (OAuth, CIMD, JWT,    │
│   Aggregate, Skills)         │   Contracts, Reflexive)│
├──────────────────────────────┴───────────────────────┤
│         Background Tasks (Docket/Redis)              │
├─────────────────────────────────────────────────────┤
│       Utilities, Settings, Telemetry (OTEL)          │
└─────────────────────────────────────────────────────┘
```

The server class (`FastMCP`) uses a **mixin architecture** inheriting from `AggregateProvider`, `LifespanMixin`, `MCPOperationsMixin`, and `TransportMixin`. This separates concerns cleanly while keeping the main class as the single entry point for users.

---

## 2. Subsystem Summaries

### 2.1 Core Entry Point & Settings

The root `__init__.py` uses **lazy imports** (`__getattr__` hook) to avoid loading the client module for server-only deployments. `Settings` (Pydantic Settings) manages 60+ configuration options with environment variable support, nested delimiters, and `.env` file loading. Telemetry uses OpenTelemetry's API-only dependency pattern for zero-cost instrumentation when no SDK is installed.

### 2.2 Server

The server's request flow proceeds through: Transport → MCP Handler (MCPOperationsMixin) → Context creation → Middleware chain → Provider resolution → Component execution → Result serialization. The `Context` class provides request-scoped state via `ContextVar`, with session-scoped persistent state backed by async key-value stores. The dependency injection system (`dependencies.py`) bridges the legacy `ctx: Context` type-annotation pattern with the modern `Depends()` pattern from `uncalled-for`.

### 2.3 Provider System

Four provider types aggregate MCP components: `LocalProvider` (decorator-registered), `FastMCPProvider` (wraps another FastMCP server), `ProxyProvider` (proxies to remote servers via client), and `AggregateProvider` (combines multiple providers with namespacing). An OpenAPI provider auto-generates tools from API specs, and a Skills provider loads Claude-style skill definitions. Provider ordering determines resolution priority (first match wins).

### 2.4 Middleware

The middleware system uses a **functional chain-of-responsibility** pattern with `CallNext[T, R]` protocol. 11 middleware implementations cover error handling (with RFC-compliant error codes), rate limiting (token bucket + sliding window), structured logging, response caching (TTL-based with size limits), authorization enforcement, tool injection, schema dereferencing, timing, ping keep-alive, and response size limiting.

### 2.5 Authentication & Authorization

A three-level auth model: server-level (`AuthProvider`), component-level (per-tool/resource/prompt `AuthCheck`), and transport-specific behavior (STDIO skips auth). Supports full OAuth 2.0 authorization server, JWT verification, token introspection, and CIMD (Client ID Metadata Documents) for desktop/CLI client registration with SSRF protection, replay prevention, and private_key_jwt support. `MultiAuth` composes multiple verifiers.

### 2.6 Tools, Resources, Prompts

All three follow a consistent pattern: abstract base → function-based implementation → decorator API. Schema generation uses Pydantic `TypeAdapter` with output schema wrapping for MCP compliance (objects only). The `ToolTransform` system enables argument renaming, hiding, type changes, and default injection via `ArgTransform`, with a forwarding function pattern using context variables. Resource templates support RFC 6570 URI templates with regex-based matching and type coercion.

### 2.7 Client SDK

The `Client` class is generic over transport type, supports reentrant context managers with reference counting, and provides session monitoring to detect background HTTP errors. Transport inference auto-detects protocol from URLs, file paths, or config dicts. Handler registration covers roots, sampling (Anthropic/OpenAI/Google GenAI), logging, progress, and elicitation.

### 2.8 CLI

Two main modules (2,098 lines): `cli.py` provides server management (run, inspect, dev, install, auth), and `client.py` provides query/invoke commands (list, call, discover, generate-cli). Server resolution supports URLs, file paths, module names, config files, and discovered server names. Output formatting handles rich console and JSON modes.

### 2.9 Security Subsystem

A comprehensive, layered security framework with 12+ modules: policy engine (RBAC/ABAC), context broker (contract negotiation with crypto signing), provenance ledger (Merkle tree audit), reflexive analyzer (behavioral drift detection with sigma-based thresholds), consent graph, API gateway/marketplace, tool certification, trust registry, real-time alerts (pub/sub event bus), compliance reporting (GDPR/HIPAA/SOC2/ISO27001), sandbox execution, and federation.

### 2.10 Tasks Subsystem

Background task support per MCP SEP-1686, backed by Docket/Redis. Task lifecycle: submission → Docket queue → worker execution → result retrieval. Features include Redis-based notification queues (LPUSH/BRPOP), elicitation for user input during background tasks, access token snapshotting for worker authentication, and session-scoped task key isolation.

### 2.11 Test Suite

401 test files totaling ~121K lines, organized to mirror the source tree. Test infrastructure includes isolated settings per test (tmp_path homes), fast Docket polling (10ms for tests vs 50ms production), Windows event loop compatibility, auto-marking of integration tests, OpenTelemetry in-memory exporter, and xdist parallel support. The 5-second default timeout enforces fast test execution.

---

## 3. Strengths

**Architecture & Design:**
- Clean separation of concerns via mixins, providers, and middleware
- Consistent component model across tools/resources/prompts (base → function → decorator)
- Lazy imports for performance in server-only deployments
- Generic types preserve transport specificity in the client
- Reference-counted lifespan management handles ASGI concurrency correctly

**Developer Experience:**
- Decorator-based API (`@tool`, `@resource`, `@prompt`) makes simple cases trivial
- Settings-driven configuration with environment variable support
- Rich CLI with auto-detection of server specs and discovery across multiple IDE integrations
- Comprehensive deprecation messages guide migration from v1 patterns

**Security:**
- Fail-closed auth model with three enforcement levels
- SSRF protection in CIMD fetching with private IP blocking
- JWT replay protection with JTI tracking
- Hash-chain audit logs for tamper-evident non-repudiation
- Behavioral drift detection with configurable escalation

**Quality:**
- Extensive test coverage (~121K lines of tests for ~90K lines of source)
- Static analysis enforced (Ruff, ty, pre-commit hooks)
- File size limits via loq prevent monolithic modules
- 5-second test timeout catches performance regressions

---

## 4. Potential Issues & Risks

### 4.1 Security Concerns

1. **STDIO Security Bypass**: Both `ContractValidationMiddleware` and `ReflexiveMiddleware` default `bypass_stdio=True`, completely skipping security checks for local subprocess connections. This is intentional for simplicity but means local attackers can invoke tools without contracts or monitoring.

2. **Contract Signature Verification Not Enforced**: The `ContractValidationMiddleware` checks contract existence but doesn't verify cryptographic signatures before execution. The `verify()` method exists in `crypto.py` but appears unused in the broker flow.

3. **Default Term Evaluator Accepts All**: If no `term_evaluator` is configured on the broker, all proposed contract terms are auto-accepted. An agent can propose any terms and they'll pass.

4. **Threat Score Decay**: Reflexive analyzer threat scores decay exponentially (~10-minute half-life). A critical incident's score disappears quickly with no permanent blacklist mechanism for persistent threat actors.

5. **Token Truncation for Agent ID**: Agent identity derived by truncating tokens to first 8 characters — weak anonymization that could cause cross-agent tracking misattribution.

6. **Cached Response + Auth Ordering**: No documented middleware ordering. If caching runs before auth filtering, cached list responses could bypass authorization and serve unfiltered results to unauthorized clients.

7. **Access Token Exposure in Background Tasks**: Tokens are snapshotted in Redis (`fastmcp:task:{session_id}:{server_task_id}:access_token`) with no refresh mechanism. Tokens exposed in distributed cache longer than synchronous requests, and may expire during task execution.

### 4.2 Architectural Concerns

8. **Middleware Ordering Not Documented**: The middleware chain is composable but ordering matters significantly for correctness (auth before caching, error handling outermost, etc.). No built-in ordering validation or documented best practices.

9. **Provider Resolution Ambiguity**: First-provider-wins resolution means provider ordering silently determines behavior. Namespace collisions across providers default to parent preference with no warnings.

10. **ContextVar Leakage in Stateful Proxy Clients**: `StatefulProxyClient` reuses sessions across requests, but `ReceiveLoopTask` retains stale ContextVars from the first request. Mitigated by `_proxy_rc_ref` stash but fragile.

11. **Unbounded Provenance Ledger**: No retention policy or pruning mechanism for the append-only provenance ledger. Could grow indefinitely in long-running servers.

12. **Session Timeout Uses Wall Clock**: Contract session timeouts use `datetime.now()` rather than monotonic time, making them vulnerable to system clock adjustments (NTP, VM migration).

### 4.3 Task System Issues

13. **Lost Notifications on Session Disconnect**: When sessions crash, notification queues have no TTL-based cleanup — stale queues accumulate in Redis.

14. **Elicitation Timeout Mismatch**: Elicitation has a 1-hour TTL, but the worker task may timeout before the response arrives. Behavior is undefined when these timers conflict.

15. **Task Key Parsing Fragility**: Keys use colon-delimited format, and while component identifiers are URI-encoded, the fallback parsing using rsplit on `@` creates ambiguity with URIs containing `@`.

### 4.4 Minor Issues

16. **Logging Payload Leakage**: `LoggingMiddleware` can include request payloads in logs with no built-in filtering for sensitive data (API keys, tokens).

17. **Scope Claim Handling**: `require_scopes()` checks `token.scopes` (a list), but JWT tokens commonly use space-separated scope strings. If conversion is missing in a verifier, scopes appear empty and auth fails silently.

18. **Reflexive Analyzer Min-Samples Bypass**: Drift detection is skipped until `min_samples` (default 10) observations are reached. A new agent's first anomalous operations go undetected.

---

## 5. Test Coverage Assessment

The test suite is comprehensive and well-organized:

| Area | Test Files | Notable Coverage |
|------|-----------|-----------------|
| Server core | 30+ | Dependencies, auth integration, pagination, versioning |
| Middleware | 12 | All middleware types including nested chains |
| Auth | 15+ | OAuth proxy, OIDC, JWT providers, introspection, authorization |
| Tasks | 20+ | Lifecycle, mount, proxy, dependencies, elicitation, TTL |
| Security | 10+ | Certification, policy gaps, marketplace gaps, storage |
| Tools | 12 | Transforms, timeouts, output schemas, content types |
| Resources | 7 | Templates, query params, file resources, standalone decorator |
| Prompts | 5+ | Function prompts, standalone decorator |
| Client | 15+ | Transports, auth, sampling, tasks, telemetry |
| CLI | 8+ | Run, generate, apps |
| Utilities | 10+ | OpenAPI, JSON schema, transitive references |
| Experimental | 3 | Code mode transforms |

**Gaps observed:**
- Security middleware integration tests (policy + contracts + reflexive together) appear limited
- Cross-layer security-tasks interaction tests not prominent
- Edge cases around middleware ordering not explicitly tested

---

## 6. Recommendations

### High Priority

1. **Document and validate middleware ordering** — Add ordering constraints or a built-in ordering mechanism to prevent auth/caching/error-handling misordering.

2. **Enforce contract signature verification** — Wire the existing `verify()` method into `ContractValidationMiddleware` before allowing contract execution.

3. **Implement permanent actor flagging** — Add a blacklist or permanent flag mechanism separate from decaying threat scores for persistent bad actors.

4. **Add token refresh for background tasks** — Implement token refresh or short-lived task-specific credentials for Docket workers to handle long-running tasks.

5. **Clean up stale notification queues** — Add TTL to Redis notification queues and implement cleanup on session disconnect.

### Medium Priority

6. **Use monotonic clock for session timeouts** — Replace `datetime.now()` with `time.monotonic()` in contract session management.

7. **Add sensitive data filtering to logging middleware** — Built-in redaction of common sensitive patterns (tokens, API keys) in payload logging.

8. **Add provenance ledger retention policy** — Implement configurable retention and pruning for the append-only ledger.

9. **Strengthen agent ID derivation** — Use full token hash or a dedicated claim instead of 8-character prefix truncation.

10. **Add STDIO security opt-in** — Make STDIO bypass explicit via allowlist rather than blanket default.

### Low Priority

11. **Add middleware ordering tests** — Explicitly test critical ordering scenarios (auth before caching, error handling outermost).

12. **Document provider resolution semantics** — Clarify first-match-wins behavior and namespace collision handling.

13. **Add elicitation timeout coordination** — Define behavior when elicitation TTL and task execution TTL conflict.

---

## 7. Summary

FastMCP v2.0 is a mature, well-architected framework with excellent developer ergonomics and comprehensive feature coverage. The codebase demonstrates strong engineering practices: consistent patterns across component types, thorough type annotations, extensive test coverage, and thoughtful performance optimizations. The security subsystem is ambitious and feature-rich, though some integration gaps between layers (particularly contract verification enforcement and middleware ordering) warrant attention before production deployment of security-sensitive applications. The task system provides a solid foundation for background execution but needs hardening around token lifecycle and notification cleanup for production reliability.
