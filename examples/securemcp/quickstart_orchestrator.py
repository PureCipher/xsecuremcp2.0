"""SecureMCP Quickstart — Orchestrator pattern.

Demonstrates bootstrapping a fully trust-native MCP server using the
SecurityOrchestrator.  This is the recommended approach for new
projects: define a SecurityConfig, call bootstrap(), and let the
orchestrator wire all components with correct dependency ordering.

For a manual-wiring variant see ``quickstart.py``.

Run::

    uv run python examples/securemcp/quickstart_orchestrator.py

Then visit:
    http://localhost:8000/security/health
    http://localhost:8000/security/dashboard
    http://localhost:8000/security/marketplace
    http://localhost:8000/security/trust
    http://localhost:8000/security/compliance
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.security.config import (
    AlertConfig,
    ComplianceConfig,
    CRLConfig,
    FederationConfig,
    ProvenanceConfig,
    RegistryConfig,
    SecurityConfig,
    ToolMarketplaceConfig,
)
from fastmcp.server.security.gateway.tool_marketplace import ToolCategory
from fastmcp.server.security.http import SecurityAPI, mount_security_routes
from fastmcp.server.security.orchestrator import SecurityOrchestrator
from fastmcp.server.security.provenance.records import ProvenanceAction

# ── 1. Create an MCP server ─────────────────────────────────────

server = FastMCP("securemcp-demo")

# ── 2. Define the security config ───────────────────────────────
#
# Each sub-config enables a component.  Omit any you don't need —
# the orchestrator only creates components that are configured.

config = SecurityConfig(
    alerts=AlertConfig(),
    provenance=ProvenanceConfig(),
    registry=RegistryConfig(),
    tool_marketplace=ToolMarketplaceConfig(),
    federation=FederationConfig(),
    crl_config=CRLConfig(),
    compliance=ComplianceConfig(),
)

# ── 3. Bootstrap all components at once ──────────────────────────

ctx = SecurityOrchestrator.bootstrap(config, server_name="securemcp-demo")

# That single call created and wired:
#   - event_bus (shared across all components)
#   - provenance_ledger (with middleware)
#   - registry (trust scores)
#   - crl (certificate revocation)
#   - federation (cross-instance trust, wired to registry + crl)
#   - tool_marketplace (wired to registry)
#   - compliance_reporter
#   - dashboard (auto-wired to all of the above)

# ── 4. Register a tool in the trust registry ─────────────────────

ctx.registry.register(
    "weather-lookup",
    tool_version="1.2.0",
    author="demo-author",
    tags={"weather", "api"},
)

# ── 5. Publish to the marketplace ───────────────────────────────

ctx.tool_marketplace.publish(
    "weather-lookup",
    display_name="Weather Lookup",
    description="Look up current weather for a city.",
    version="1.2.0",
    author="demo-author",
    categories={ToolCategory.UTILITY},
    tags={"weather", "api"},
    tool_license="MIT",
)

# ── 6. Record a provenance event ────────────────────────────────

ctx.provenance_ledger.record(
    action=ProvenanceAction.TOOL_CALLED,
    actor_id="agent-1",
    resource_id="weather-lookup",
    metadata={"city": "San Francisco"},
)

# ── 7. Mount the HTTP API (auto-wired from the SecurityContext) ──

api = SecurityAPI.from_context(ctx)
mount_security_routes(server, api=api)

# ── 8. Install middleware from the orchestrator ──────────────────
#
# The orchestrator builds middleware in the correct order
# (policy → contracts → provenance → reflexive → consent).

for mw in ctx.middleware:
    server.add_middleware(mw)


# ── 9. Add a regular MCP tool ───────────────────────────────────

@server.tool()
def weather_lookup(city: str) -> str:
    """Look up current weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"


# ── 10. Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run(transport="streamable-http")
