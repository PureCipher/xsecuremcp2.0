"""Integration tests for SecurityOrchestrator → SecurityContext → HTTP API.

Verifies that all components are wired end-to-end: config → orchestrator →
context fields populated → HTTP API returns real data (not 503).
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.config import (
    AlertConfig,
    ComplianceConfig,
    CRLConfig,
    FederationConfig,
    PolicyConfig,
    ProvenanceConfig,
    RegistryConfig,
    SandboxConfig,
    SecurityConfig,
    ToolMarketplaceConfig,
)
from fastmcp.server.security.orchestrator import SecurityContext, SecurityOrchestrator


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def full_config():
    """SecurityConfig with all layers enabled."""
    return SecurityConfig(
        alerts=AlertConfig(),
        policy=PolicyConfig(),
        provenance=ProvenanceConfig(),
        registry=RegistryConfig(),
        tool_marketplace=ToolMarketplaceConfig(),
        federation=FederationConfig(federation_id="test-node"),
        crl_config=CRLConfig(),
        compliance=ComplianceConfig(),
        sandbox=SandboxConfig(),
    )


@pytest.fixture()
def full_ctx(full_config):
    return SecurityOrchestrator.bootstrap(full_config, server_name="test-server")


# ── SecurityContext field population tests ─────────────────────


class TestContextFields:
    def test_event_bus_created(self, full_ctx):
        assert full_ctx.event_bus is not None

    def test_policy_engine_created(self, full_ctx):
        assert full_ctx.policy_engine is not None

    def test_provenance_ledger_created(self, full_ctx):
        assert full_ctx.provenance_ledger is not None

    def test_registry_created(self, full_ctx):
        assert full_ctx.registry is not None

    def test_tool_marketplace_created(self, full_ctx):
        assert full_ctx.tool_marketplace is not None

    def test_federation_created(self, full_ctx):
        assert full_ctx.federation is not None

    def test_crl_created(self, full_ctx):
        assert full_ctx.crl is not None

    def test_compliance_reporter_created(self, full_ctx):
        assert full_ctx.compliance_reporter is not None

    def test_sandbox_runner_created(self, full_ctx):
        assert full_ctx.sandbox_runner is not None

    def test_dashboard_created(self, full_ctx):
        assert full_ctx.dashboard is not None

    def test_middleware_populated(self, full_ctx):
        # At minimum: policy + provenance middleware
        assert len(full_ctx.middleware) >= 2


# ── Cross-component wiring tests ──────────────────────────────


class TestCrossWiring:
    def test_marketplace_has_registry(self, full_ctx):
        """ToolMarketplace should be wired to the same TrustRegistry."""
        assert full_ctx.tool_marketplace._trust_registry is full_ctx.registry

    def test_federation_has_crl(self, full_ctx):
        """TrustFederation should have the CRL wired."""
        assert full_ctx.federation.local_crl is full_ctx.crl

    def test_federation_has_registry(self, full_ctx):
        """TrustFederation should have the registry wired."""
        assert full_ctx.federation._local_registry is full_ctx.registry

    def test_dashboard_has_all_components(self, full_ctx):
        """Dashboard should be wired to all major components."""
        dash = full_ctx.dashboard
        assert dash._registry is full_ctx.registry
        assert dash._marketplace is full_ctx.tool_marketplace
        assert dash._federation is full_ctx.federation
        assert dash._crl is full_ctx.crl
        assert dash._compliance_reporter is full_ctx.compliance_reporter
        assert dash._sandbox_runner is full_ctx.sandbox_runner

    def test_sandbox_runner_has_crl(self, full_ctx):
        """SandboxedRunner should have CRL wired."""
        assert full_ctx.sandbox_runner._crl is full_ctx.crl

    def test_event_bus_propagated_to_registry(self, full_ctx):
        """Event bus should be injected into the registry."""
        assert full_ctx.registry._event_bus is full_ctx.event_bus

    def test_event_bus_propagated_to_marketplace(self, full_ctx):
        """Event bus should be injected into the tool marketplace."""
        assert full_ctx.tool_marketplace._event_bus is full_ctx.event_bus


# ── HTTP API integration tests ────────────────────────────────


class TestHTTPAPIIntegration:
    """Verify that SecurityAPI built from a fully-bootstrapped context
    returns real data instead of 503 errors."""

    @pytest.fixture()
    def api_from_ctx(self, full_ctx):
        from fastmcp.server.security.http.api import SecurityAPI

        return SecurityAPI(
            dashboard=full_ctx.dashboard,
            marketplace=full_ctx.tool_marketplace,
            registry=full_ctx.registry,
            compliance_reporter=full_ctx.compliance_reporter,
            provenance_ledger=full_ctx.provenance_ledger,
            federation=full_ctx.federation,
            crl=full_ctx.crl,
            event_bus=full_ctx.event_bus,
        )

    def test_dashboard_not_503(self, api_from_ctx):
        result = api_from_ctx.get_dashboard()
        assert result.get("status") != 503

    def test_marketplace_not_503(self, api_from_ctx):
        result = api_from_ctx.get_marketplace()
        assert result.get("status") != 503

    def test_trust_registry_not_503(self, api_from_ctx):
        result = api_from_ctx.get_trust_registry()
        assert result.get("status") != 503
        assert "total_tools" in result

    def test_compliance_not_503(self, api_from_ctx):
        result = api_from_ctx.get_compliance_report()
        assert result.get("status") != 503

    def test_federation_not_503(self, api_from_ctx):
        result = api_from_ctx.get_federation_status()
        assert result.get("status") != 503

    def test_revocations_not_503(self, api_from_ctx):
        result = api_from_ctx.get_revocations()
        assert result.get("status") != 503
        assert "total_entries" in result

    def test_provenance_not_503(self, api_from_ctx):
        result = api_from_ctx.get_provenance()
        assert result.get("status") != 503
        assert "total_records" in result

    def test_health_all_components(self, api_from_ctx):
        result = api_from_ctx.get_health()
        assert result["status"] == "healthy"
        assert result["component_count"] >= 7


# ── End-to-end data flow test ─────────────────────────────────


class TestEndToEndDataFlow:
    """Register a tool, publish it, verify it shows up in API responses."""

    def test_registered_tool_appears_in_trust_registry(self, full_ctx):
        from fastmcp.server.security.http.api import SecurityAPI

        # Register a tool
        full_ctx.registry.register("e2e-tool", tool_version="1.0.0", author="test")

        api = SecurityAPI(registry=full_ctx.registry)
        result = api.get_trust_registry()
        tool_names = [t["tool_name"] for t in result["tools"]]
        assert "e2e-tool" in tool_names

    def test_published_tool_appears_in_marketplace(self, full_ctx):
        from fastmcp.server.security.gateway.tool_marketplace import ToolCategory

        from fastmcp.server.security.http.api import SecurityAPI

        # Register + publish
        full_ctx.registry.register("e2e-tool-2", tool_version="1.0.0", author="test")
        full_ctx.tool_marketplace.publish(
            "e2e-tool-2",
            display_name="E2E Tool",
            description="End-to-end test tool.",
            version="1.0.0",
            author="test",
            categories={ToolCategory.UTILITY},
        )

        api = SecurityAPI(
            marketplace=full_ctx.tool_marketplace,
            registry=full_ctx.registry,
        )
        result = api.get_marketplace()
        assert result.get("status") != 503
        assert len(result.get("listings", [])) >= 1

    def test_provenance_event_appears_in_api(self, full_ctx):
        from fastmcp.server.security.provenance.records import ProvenanceAction

        from fastmcp.server.security.http.api import SecurityAPI

        full_ctx.provenance_ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="test-actor",
            resource_id="e2e-tool",
        )

        api = SecurityAPI(provenance_ledger=full_ctx.provenance_ledger)
        result = api.get_provenance(resource_id="e2e-tool")
        assert result["total_records"] >= 1

    def test_revocation_appears_in_api(self, full_ctx):
        from fastmcp.server.security.federation.crl import RevocationReason

        from fastmcp.server.security.http.api import SecurityAPI

        full_ctx.crl.revoke("bad-tool", reason=RevocationReason.POLICY_VIOLATION)

        api = SecurityAPI(crl=full_ctx.crl)
        result = api.is_revoked("bad-tool")
        assert result["is_revoked"] is True


# ── Partial config tests ──────────────────────────────────────


class TestPartialConfig:
    """Verify that partial configs work — only requested components are created."""

    def test_registry_only(self):
        config = SecurityConfig(registry=RegistryConfig())
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.registry is not None
        assert ctx.tool_marketplace is None
        assert ctx.federation is None
        assert ctx.dashboard is not None  # always created

    def test_marketplace_without_registry(self):
        config = SecurityConfig(tool_marketplace=ToolMarketplaceConfig())
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.tool_marketplace is not None
        assert ctx.registry is None
        # marketplace should still work without registry

    def test_empty_config(self):
        config = SecurityConfig()
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.registry is None
        assert ctx.tool_marketplace is None
        assert ctx.federation is None
        assert ctx.crl is None
        assert ctx.compliance_reporter is None
        assert ctx.sandbox_runner is None
        assert ctx.dashboard is not None  # always created


# ── _build_api_from_server test ───────────────────────────────


class TestBuildAPIFromServer:
    def test_auto_build_from_context(self, full_ctx):
        """Simulate what _build_api_from_server does."""
        from fastmcp import FastMCP

        from fastmcp.server.security.http.api import _build_api_from_server

        server = FastMCP("test")
        server._security_context = full_ctx

        api = _build_api_from_server(server)
        assert api.dashboard is full_ctx.dashboard
        assert api.marketplace is full_ctx.tool_marketplace
        assert api.registry is full_ctx.registry
        assert api.compliance_reporter is full_ctx.compliance_reporter
        assert api.provenance_ledger is full_ctx.provenance_ledger
        assert api.federation is full_ctx.federation
        assert api.crl is full_ctx.crl
        assert api.event_bus is full_ctx.event_bus
