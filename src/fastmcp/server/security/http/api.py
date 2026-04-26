"""Security HTTP API — Starlette-based endpoints for the SecureMCP platform.

Registers JSON routes on a FastMCP server to serve dashboard, marketplace,
compliance, audit, trust, and provenance data to frontends.

Usage with FastMCP::

    from fastmcp import FastMCP
    from fastmcp.server.security import SecurityConfig, attach_security
    from fastmcp.server.security.http import mount_security_routes

    server = FastMCP("my-server")
    attach_security(server, SecurityConfig(...))
    mount_security_routes(server)
    # Now GET /security/dashboard, /security/marketplace, etc. are live.

Standalone usage::

    api = SecurityAPI(
        dashboard=security_dashboard,
        marketplace=marketplace,
        registry=registry,
        compliance_reporter=reporter,
        provenance_ledger=ledger,
        event_bus=bus,
    )
    data = api.get_dashboard()
    data = api.get_marketplace()
"""

from __future__ import annotations

import functools
import hmac
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp.server.security.http.policy_routes import mount_policy_routes
from fastmcp.server.security.integration import get_security_context
from fastmcp.server.security.policy.serialization import (
    describe_policy_provider,
    policy_provider_from_config,
    policy_snapshot,
    providers_from_snapshot,
)
from fastmcp.server.security.policy.workbench import (
    build_environment_recommendations,
    build_policy_risks,
    get_policy_bundle,
    get_policy_environment,
    list_policy_bundles,
    list_policy_environments,
    summarize_policy_chain_delta,
)
from fastmcp.server.security.policy.workbench_store import PolicyWorkbenchStore

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.server.security.alerts.bus import SecurityEventBus
    from fastmcp.server.security.contracts.broker import ContextBroker
    from fastmcp.server.security.compliance.reports import ComplianceReporter
    from fastmcp.server.security.dashboard.snapshot import SecurityDashboard
    from fastmcp.server.security.federation.crl import CertificateRevocationList
    from fastmcp.server.security.federation.federation import TrustFederation
    from fastmcp.server.security.gateway.tool_marketplace import ToolMarketplace
    from fastmcp.server.security.policy.audit import PolicyAuditLog
    from fastmcp.server.security.policy.engine import PolicyEngine
    from fastmcp.server.security.policy.governance import PolicyGovernor
    from fastmcp.server.security.policy.monitoring import PolicyMonitor
    from fastmcp.server.security.policy.validator import PolicyValidator
    from fastmcp.server.security.policy.versioning.manager import PolicyVersionManager
    from fastmcp.server.security.consent.federation import FederatedConsentGraph
    from fastmcp.server.security.provenance.ledger import ProvenanceLedger
    from fastmcp.server.security.reflexive.introspection import IntrospectionEngine
    from fastmcp.server.security.registry.registry import TrustRegistry

logger = logging.getLogger(__name__)


@dataclass
class SecurityAPI:
    """Facade for all SecureMCP HTTP API endpoints.

    Each method returns a plain dict (ready for JSON serialization).
    The ``mount_security_routes`` helper wires these to Starlette routes.

    Attributes:
        dashboard: SecurityDashboard for snapshot generation.
        marketplace: ToolMarketplace for listing/search.
        registry: TrustRegistry for trust score lookups.
        compliance_reporter: ComplianceReporter for report generation.
        provenance_ledger: ProvenanceLedger for audit trail queries.
        federation: TrustFederation for peer status.
        crl: CertificateRevocationList for revocation queries.
        event_bus: SecurityEventBus for recent events.
    """

    dashboard: SecurityDashboard | None = None
    marketplace: ToolMarketplace | None = None
    registry: TrustRegistry | None = None
    compliance_reporter: ComplianceReporter | None = None
    provenance_ledger: ProvenanceLedger | None = None
    federation: TrustFederation | None = None
    crl: CertificateRevocationList | None = None
    event_bus: SecurityEventBus | None = None
    policy_engine: PolicyEngine | None = None
    policy_audit_log: PolicyAuditLog | None = None
    policy_version_manager: PolicyVersionManager | None = None
    policy_validator: PolicyValidator | None = None
    policy_monitor: PolicyMonitor | None = None
    policy_governor: PolicyGovernor | None = None
    broker: ContextBroker | None = None
    federated_consent_graph: FederatedConsentGraph | None = None
    introspection_engine: IntrospectionEngine | None = None
    _policy_workbench_store: PolicyWorkbenchStore | None = field(
        default=None,
        init=False,
        repr=False,
    )

    @classmethod
    def from_context(cls, ctx: Any) -> SecurityAPI:
        """Create a SecurityAPI from a SecurityContext.

        This is the recommended way to construct a SecurityAPI when
        using the SecurityOrchestrator::

            ctx = SecurityOrchestrator.bootstrap(config)
            api = SecurityAPI.from_context(ctx)
            mount_security_routes(server, api=api)

        Args:
            ctx: A SecurityContext returned by SecurityOrchestrator.bootstrap().

        Returns:
            A SecurityAPI wired to all components in the context.
        """
        return cls(
            dashboard=getattr(ctx, "dashboard", None),
            marketplace=getattr(ctx, "tool_marketplace", None),
            registry=getattr(ctx, "registry", None),
            compliance_reporter=getattr(ctx, "compliance_reporter", None),
            provenance_ledger=getattr(ctx, "provenance_ledger", None),
            federation=getattr(ctx, "federation", None),
            crl=getattr(ctx, "crl", None),
            event_bus=getattr(ctx, "event_bus", None),
            policy_engine=getattr(ctx, "policy_engine", None),
            policy_audit_log=getattr(ctx, "policy_audit_log", None),
            policy_version_manager=getattr(ctx, "policy_version_manager", None),
            policy_validator=getattr(ctx, "policy_validator", None),
            policy_monitor=getattr(ctx, "policy_monitor", None),
            policy_governor=getattr(ctx, "policy_governor", None),
            broker=getattr(ctx, "broker", None),
            federated_consent_graph=getattr(ctx, "federated_consent_graph", None),
            introspection_engine=getattr(ctx, "introspection_engine", None),
        )

    # ── Dashboard ─────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """Generate full dashboard JSON for the React frontend."""
        if self.dashboard is None:
            return {"error": "Dashboard not configured", "status": 503}

        from fastmcp.server.security.dashboard.data_bridge import DashboardDataBridge

        bridge = DashboardDataBridge(dashboard=self.dashboard)
        return bridge.export()

    # ── Marketplace ───────────────────────────────────────────

    def get_marketplace(
        self,
        query: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Generate marketplace JSON for the React frontend."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        from fastmcp.server.security.gateway.marketplace_bridge import (
            MarketplaceDataBridge,
        )

        bridge = MarketplaceDataBridge(
            marketplace=self.marketplace,
            trust_registry=self.registry,
        )
        return bridge.export()

    def get_marketplace_listing(self, listing_id: str) -> dict[str, Any]:
        """Get detail view for a single marketplace listing."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        from fastmcp.server.security.gateway.marketplace_bridge import (
            MarketplaceDataBridge,
        )

        bridge = MarketplaceDataBridge(
            marketplace=self.marketplace,
            trust_registry=self.registry,
        )
        detail = bridge.build_listing_detail(listing_id)
        if detail is None:
            return {"error": "Listing not found", "status": 404}
        return detail

    def marketplace_install(
        self,
        listing_id: str,
        *,
        installer_id: str = "",
        version: str | None = None,
        verify_signature: bool = False,
    ) -> dict[str, Any]:
        """Install a tool from the marketplace."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        record = self.marketplace.install(
            listing_id,
            installer_id=installer_id,
            version=version,
            verify_signature=verify_signature,
        )
        if record is None:
            return {
                "error": "Install failed — listing not found or signature verification failed",
                "status": 400,
            }

        return {
            "install_id": record.install_id,
            "listing_id": listing_id,
            "version": record.version,
            "signature_verified": record.signature_verified,
            "installed_at": record.installed_at.isoformat(),
        }

    def marketplace_uninstall(
        self,
        listing_id: str,
        *,
        installer_id: str = "",
    ) -> dict[str, Any]:
        """Uninstall a tool."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        success = self.marketplace.uninstall(listing_id, installer_id=installer_id)
        return {"success": success, "listing_id": listing_id}

    def marketplace_moderate(
        self,
        listing_id: str,
        *,
        moderator_id: str,
        action: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Moderate a tool listing."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        from fastmcp.server.security.gateway.tool_marketplace import ModerationAction

        try:
            mod_action = ModerationAction(action)
        except ValueError:
            return {"error": f"Invalid moderation action: {action}", "status": 400}

        decision = self.marketplace.moderate(
            listing_id,
            moderator_id=moderator_id,
            action=mod_action,
            reason=reason,
        )
        if decision is None:
            return {"error": "Listing not found", "status": 404}

        return decision.to_dict()

    def marketplace_moderation_queue(self) -> dict[str, Any]:
        """Get the moderation queue."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        from fastmcp.server.security.gateway.marketplace_bridge import (
            MarketplaceDataBridge,
        )

        bridge = MarketplaceDataBridge(
            marketplace=self.marketplace,
            trust_registry=self.registry,
        )
        return {"queue": bridge.build_moderation_queue()}

    def marketplace_version_history(self, listing_id: str) -> dict[str, Any]:
        """Get version history for a listing."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        from fastmcp.server.security.gateway.marketplace_bridge import (
            MarketplaceDataBridge,
        )

        bridge = MarketplaceDataBridge(
            marketplace=self.marketplace,
            trust_registry=self.registry,
        )
        return {"versions": bridge.build_version_history(listing_id)}

    def marketplace_yank_version(
        self,
        listing_id: str,
        version: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Yank a specific version."""
        if self.marketplace is None:
            return {"error": "Marketplace not configured", "status": 503}

        success = self.marketplace.yank_version(listing_id, version, reason=reason)
        return {"success": success, "listing_id": listing_id, "version": version}

    # ── Compliance ────────────────────────────────────────────

    def get_compliance_report(self, report_type: str = "full") -> dict[str, Any]:
        """Generate a compliance report."""
        if self.compliance_reporter is None:
            return {"error": "Compliance reporter not configured", "status": 503}

        from fastmcp.server.security.compliance.reports import ReportType

        type_map = {
            "full": ReportType.FULL,
            "summary": ReportType.SUMMARY,
            "findings": ReportType.FINDINGS_ONLY,
            "executive": ReportType.EXECUTIVE,
        }
        rt = type_map.get(report_type, ReportType.FULL)
        report = self.compliance_reporter.generate_report(report_type=rt)
        return report.to_dict()

    # ── Trust Registry ────────────────────────────────────────

    def get_trust_registry(self) -> dict[str, Any]:
        """Get trust registry overview."""
        if self.registry is None:
            return {"error": "Registry not configured", "status": 503}

        records = self.registry.get_all()
        tools = []
        for record in records:
            tools.append(
                {
                    "tool_name": record.tool_name,
                    "trust_score": round(record.trust_score.overall, 3),
                    "is_certified": record.is_certified,
                    "registered_at": record.registered_at.isoformat(),
                    "tags": sorted(record.tags) if record.tags else [],
                }
            )
        tools.sort(key=lambda t: t["trust_score"], reverse=True)

        return {
            "total_tools": self.registry.record_count,
            "tools": tools,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_trust_score(self, tool_name: str) -> dict[str, Any]:
        """Get trust score for a specific tool."""
        if self.registry is None:
            return {"error": "Registry not configured", "status": 503}

        score = self.registry.get_trust_score(tool_name)
        if score is None:
            return {"error": f"Tool '{tool_name}' not found", "status": 404}

        return {
            "tool_name": tool_name,
            "overall": round(score.overall, 3),
            "certification_component": round(score.certification_component, 3),
            "reputation_component": round(score.reputation_component, 3),
            "age_component": round(score.age_component, 3),
        }

    # ── Federation ────────────────────────────────────────────

    def get_federation_status(self) -> dict[str, Any]:
        """Get federation peer status."""
        if self.federation is None:
            return {"error": "Federation not configured", "status": 503}

        return self.federation.get_federation_status()

    # ── CRL ───────────────────────────────────────────────────

    def get_revocations(self) -> dict[str, Any]:
        """Get certificate revocation list."""
        if self.crl is None:
            return {"error": "CRL not configured", "status": 503}

        entries = self.crl.get_all_entries()
        return {
            "total_entries": len(entries),
            "entries": [e.to_dict() for e in entries],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def is_revoked(self, tool_name: str) -> dict[str, Any]:
        """Check if a tool is revoked."""
        if self.crl is None:
            return {"error": "CRL not configured", "status": 503}

        revoked = self.crl.is_revoked(tool_name)
        return {"tool_name": tool_name, "is_revoked": revoked}

    # ── Provenance ────────────────────────────────────────────

    def get_provenance(
        self,
        resource_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query provenance records."""
        if self.provenance_ledger is None:
            return {"error": "Provenance ledger not configured", "status": 503}

        from fastmcp.server.security.provenance.records import ProvenanceAction

        action_filter = None
        if action:
            try:
                action_filter = ProvenanceAction(action)
            except ValueError:
                pass

        records = self.provenance_ledger.get_records(
            resource_id=resource_id,
            actor_id=actor_id,
            action=action_filter,
            limit=limit,
        )
        return {
            "total_records": self.provenance_ledger.record_count,
            "returned": len(records),
            "records": [r.to_dict() for r in records],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_provenance_chain_status(self) -> dict[str, Any]:
        """Get provenance chain integrity status."""
        if self.provenance_ledger is None:
            return {"error": "Provenance ledger not configured", "status": 503}

        ledger = self.provenance_ledger
        return {
            "ledger_id": ledger.ledger_id,
            "record_count": ledger.record_count,
            "chain_valid": ledger.verify_chain(),
            "tree_valid": ledger.verify_tree(),
            "root_hash": ledger.root_hash,
            "chain_digest": ledger.get_chain_digest(),
            "scheme": ledger.get_scheme_status(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_provenance_proof(self, record_id: str) -> dict[str, Any]:
        """Get a verification bundle for a specific record."""
        if self.provenance_ledger is None:
            return {"error": "Provenance ledger not configured", "status": 503}

        try:
            bundle = self.provenance_ledger.export_verification_bundle(record_id)
            return {"bundle": bundle, "status": "ok"}
        except KeyError:
            return {"error": f"Record '{record_id}' not found", "status": 404}

    def get_provenance_export(self) -> dict[str, Any]:
        """Export full chain dump for external audit."""
        if self.provenance_ledger is None:
            return {"error": "Provenance ledger not configured", "status": 503}

        from fastmcp.server.security.provenance.export import export_chain_dump

        return export_chain_dump(
            records=self.provenance_ledger.all_records,
            root_hash=self.provenance_ledger.root_hash,
            genesis_hash=self.provenance_ledger.genesis_hash,
        )

    def verify_provenance_bundle(self, bundle_data: dict[str, Any]) -> dict[str, Any]:
        """Verify an externally-provided verification bundle."""
        from fastmcp.server.security.provenance.export import verify_bundle

        return verify_bundle(bundle_data)

    def get_provenance_actions(self) -> dict[str, Any]:
        """List all available provenance action types."""
        from fastmcp.server.security.provenance.records import ProvenanceAction

        return {
            "actions": [
                {"value": a.value, "name": a.name} for a in ProvenanceAction
            ],
        }

    # ── Policy ────────────────────────────────────────────────

    def get_policy_status(self) -> dict[str, Any]:
        """Get policy engine status and provider list."""
        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        providers = []
        for index, provider in enumerate(self.policy_engine.providers):
            providers.append(describe_policy_provider(provider, index=index))

        versioning: dict[str, Any] | None = None
        if self.policy_version_manager is not None:
            current = self.policy_version_manager.current_version
            versioning = {
                "enabled": True,
                "policy_set_id": self.policy_version_manager.policy_set_id,
                "version_count": self.policy_version_manager.version_count,
                "current_version": current.version_number if current else None,
            }

        governance: dict[str, Any] | None = None
        if self.policy_governor is not None:
            governance = {
                "enabled": True,
                "proposal_count": len(self.policy_governor.proposals),
                "pending_count": len(self.policy_governor.pending_proposals),
                "require_simulation": self.policy_governor.require_simulation,
                "require_approval": self.policy_governor.require_approval,
            }

        return {
            "evaluation_count": self.policy_engine.evaluation_count,
            "deny_count": self.policy_engine.deny_count,
            "fail_closed": self.policy_engine.fail_closed,
            "allow_hot_swap": self.policy_engine.allow_hot_swap,
            "provider_count": len(providers),
            "providers": providers,
            "has_audit_log": self.policy_audit_log is not None,
            "versioning": versioning,
            "governance": governance,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_audit(
        self,
        actor_id: str | None = None,
        resource_id: str | None = None,
        decision: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query the policy audit log."""
        if self.policy_audit_log is None:
            return {"error": "Policy audit log not configured", "status": 503}

        from fastmcp.server.security.policy.provider import PolicyDecision

        decision_filter = None
        if decision is not None:
            decision_map = {
                "allow": PolicyDecision.ALLOW,
                "deny": PolicyDecision.DENY,
                "defer": PolicyDecision.DEFER,
            }
            decision_filter = decision_map.get(decision.lower())

        entries = self.policy_audit_log.query(
            actor_id=actor_id,
            resource_id=resource_id,
            decision=decision_filter,
            limit=limit,
        )

        return {
            "total_entries": len(entries),
            "entries": [e.to_dict() for e in entries],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_audit_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics from the policy audit log."""
        if self.policy_audit_log is None:
            return {"error": "Policy audit log not configured", "status": 503}

        return self.policy_audit_log.get_statistics()

    async def simulate_policy(self, scenarios_data: list[dict]) -> dict[str, Any]:
        """Run a policy simulation against the current engine."""
        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        from fastmcp.server.security.policy.simulation import simulate

        scenarios = self._build_scenarios(scenarios_data)
        report = await simulate(self.policy_engine, scenarios)
        return report.to_dict()

    def get_policy_schema(
        self,
        *,
        jurisdiction: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Get the declarative policy schema for the editor UI.

        Optionally filter by jurisdiction or category.
        """
        from fastmcp.server.security.policy.declarative import dump_policy_schema

        return dump_policy_schema(jurisdiction=jurisdiction, category=category)

    def _policy_workbench(self) -> PolicyWorkbenchStore:
        """Return the persistent workbench store for the active policy set."""

        if self._policy_workbench_store is None:
            policy_set_id = (
                self.policy_version_manager.policy_set_id
                if self.policy_version_manager is not None
                else "securemcp-policy"
            )
            backend = (
                self.policy_version_manager.backend
                if self.policy_version_manager is not None
                else None
            )
            self._policy_workbench_store = PolicyWorkbenchStore(
                policy_set_id,
                backend=backend,
            )
        return self._policy_workbench_store

    def _merge_environment_profiles(self) -> list[dict[str, Any]]:
        """Combine static environment profiles with captured live state."""

        captured = {
            str(item.get("environment_id")): item
            for item in self._policy_workbench().list_environment_states()
        }
        promotions = self._policy_workbench().list_promotions(limit=100)
        merged: list[dict[str, Any]] = []
        for environment in list_policy_environments():
            env_id = str(environment.get("environment_id", ""))
            state = captured.get(env_id, {})
            current = (
                state.get("current", {})
                if isinstance(state.get("current"), dict)
                else {}
            )
            last_promotion = next(
                (
                    promotion
                    for promotion in promotions
                    if promotion.get("target_environment") == env_id
                ),
                None,
            )
            merged.append(
                {
                    **environment,
                    "capture_count": int(state.get("capture_count", 0) or 0),
                    "current_version_number": current.get("version_number"),
                    "current_provider_count": current.get("provider_count"),
                    "current_source_label": current.get("source_label"),
                    "captured_at": current.get("captured_at"),
                    "captured_by": current.get("captured_by"),
                    "last_capture_note": current.get("note"),
                    "last_promotion": last_promotion,
                }
            )
        return merged

    def get_policy_bundles(self) -> dict[str, Any]:
        """Return reusable policy bundle metadata for the workbench UI."""

        bundles = list_policy_bundles()
        return {
            "count": len(bundles),
            "bundles": bundles,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_packs(self) -> dict[str, Any]:
        """Return private reusable packs saved by the policy team."""

        packs = self._policy_workbench().list_saved_packs()
        return {
            "count": len(packs),
            "packs": packs,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_environment_profiles(self) -> dict[str, Any]:
        """Return named environment profiles for migration guidance."""

        environments = self._merge_environment_profiles()
        return {
            "count": len(environments),
            "environments": environments,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_promotions(self) -> dict[str, Any]:
        """Return recent promotion records across environments."""

        promotions = self._policy_workbench().list_promotions(limit=30)
        return {
            "count": len(promotions),
            "promotions": promotions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def export_policy_snapshot(
        self,
        *,
        version_number: int | None = None,
    ) -> dict[str, Any]:
        """Export the live policy chain or a saved version as JSON."""
        if version_number is not None:
            if self.policy_version_manager is None:
                return {"error": "Policy versioning not configured", "status": 503}

            for version in self.policy_version_manager.list_versions():
                if version.version_number == version_number:
                    return {
                        "status": "exported",
                        "kind": "version",
                        "version_number": version.version_number,
                        "snapshot": version.policy_data,
                        "suggested_filename": (
                            f"securemcp-policy-v{version.version_number}.json"
                        ),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }

            return {
                "error": f"Policy version not found: {version_number}",
                "status": 404,
            }

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        current_version = (
            self.policy_version_manager.current_version
            if self.policy_version_manager is not None
            else None
        )
        snapshot = policy_snapshot(
            list(self.policy_engine.providers),
            metadata={
                "source": "policy_export",
                "current_version": (
                    current_version.version_number
                    if current_version is not None
                    else None
                ),
            },
        )
        return {
            "status": "exported",
            "kind": "live",
            "version_number": (
                current_version.version_number if current_version is not None else None
            ),
            "snapshot": snapshot,
            "suggested_filename": (
                "securemcp-policy-live.json"
                if current_version is None
                else f"securemcp-policy-live-v{current_version.version_number}.json"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def stage_policy_bundle(
        self,
        bundle_id: str,
        *,
        author: str = "api",
        description: str = "",
    ) -> dict[str, Any]:
        """Create a governance proposal from a reusable bundle."""

        bundle = get_policy_bundle(bundle_id)
        if bundle is None:
            return {"error": f"Policy bundle not found: {bundle_id}", "status": 404}

        snapshot = {
            "format": "securemcp-policy-set/v1",
            "providers": bundle["providers"],
            "metadata": {"source": "policy_bundle", "bundle_id": bundle_id},
        }
        payload = await self.import_policy_snapshot(
            snapshot,
            author=author,
            description_prefix=description or f"Apply bundle: {bundle['title']}",
            metadata={
                "workbench_kind": "starter_bundle",
                "bundle_id": bundle_id,
                "bundle_title": bundle.get("title"),
            },
        )
        if payload.get("status") in {"imported", "no_changes"}:
            payload["bundle"] = bundle
        return payload

    async def save_policy_pack(
        self,
        *,
        title: str,
        summary: str = "",
        description: str = "",
        snapshot: dict[str, Any] | list[Any] | None = None,
        source_version_number: int | None = None,
        author: str = "api",
        pack_id: str | None = None,
        tags: list[str] | None = None,
        recommended_environments: list[str] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Save a private reusable pack from live policy JSON or one version."""
        resolved_label = "pack: live policy"
        if snapshot is not None:
            normalized = self._normalize_import_snapshot(snapshot)
        else:
            resolved = self._resolve_policy_snapshot(
                snapshot=None,
                version_number=source_version_number,
                label_prefix="pack",
            )
            if "error" in resolved:
                resolved["status"] = resolved.get("status", 400)
                return resolved
            resolved_label = str(resolved.get("label", resolved_label))
            snapshot_data = resolved.get("snapshot", {})
            if not isinstance(snapshot_data, dict):
                return {
                    "error": "Unable to resolve a valid policy snapshot.",
                    "status": 400,
                }
            normalized = self._normalize_import_snapshot(snapshot_data)
        if normalized.get("status") == 400:
            return normalized

        raw_providers = normalized.get("providers", [])
        if not isinstance(raw_providers, list) or not raw_providers:
            return {
                "error": "Saved packs require at least one provider.",
                "status": 400,
            }
        for raw_provider in raw_providers:
            if not isinstance(raw_provider, dict):
                return {
                    "error": "Each saved pack provider must be a JSON object.",
                    "status": 400,
                }
            if (
                self.policy_validator is not None
                and raw_provider.get("type") != "python_class"
            ):
                result = self.policy_validator.validate_declarative(raw_provider)
                if not result.valid:
                    return {
                        "error": "Saved pack failed validation.",
                        "status": 400,
                        "validation": result.to_dict(),
                    }

        pack = self._policy_workbench().save_pack(
            title=title,
            summary=summary,
            description=description,
            snapshot=normalized,
            author=author,
            tags=tags,
            recommended_environments=recommended_environments,
            pack_id=pack_id,
            note=note or resolved_label,
        )
        return {
            "status": "saved",
            "pack": pack,
            "packs": self.get_policy_packs(),
        }

    def delete_policy_pack(self, pack_id: str) -> dict[str, Any]:
        """Delete one private saved pack."""

        deleted = self._policy_workbench().delete_pack(pack_id)
        if not deleted:
            return {"error": f"Policy pack not found: {pack_id}", "status": 404}
        return {
            "status": "deleted",
            "pack_id": pack_id,
            "packs": self.get_policy_packs(),
        }

    async def stage_policy_pack(
        self,
        pack_id: str,
        *,
        author: str = "api",
        description: str = "",
    ) -> dict[str, Any]:
        """Stage a saved private pack as a governance proposal."""

        pack = self._policy_workbench().get_saved_pack(pack_id)
        if pack is None:
            return {"error": f"Policy pack not found: {pack_id}", "status": 404}
        payload = await self.import_policy_snapshot(
            pack.get("snapshot", {}),
            author=author,
            description_prefix=description or f"Apply pack: {pack.get('title', pack_id)}",
            metadata={
                "workbench_kind": "saved_pack",
                "pack_id": pack_id,
                "pack_title": pack.get("title"),
            },
        )
        if payload.get("status") in {"imported", "no_changes"}:
            payload["pack"] = pack
        return payload
    
    def capture_policy_environment(
        self,
        environment_id: str,
        *,
        actor: str = "api",
        note: str = "",
        source_snapshot: dict[str, Any] | None = None,
        source_version_number: int | None = None,
    ) -> dict[str, Any]:
        """Capture the current live chain or one version into an environment."""

        environment = get_policy_environment(environment_id)
        if environment is None:
            return {
                "error": f"Unknown policy environment: {environment_id}",
                "status": 400,
            }
        source = self._resolve_policy_snapshot(
            snapshot=source_snapshot,
            version_number=source_version_number,
            label_prefix=f"environment {environment_id}",
        )
        if "error" in source:
            source["status"] = source.get("status", 400)
            return source

        snapshot_data = source.get("snapshot", {})
        if not isinstance(snapshot_data, dict):
            return {"error": "Unable to resolve environment snapshot.", "status": 400}

        state = self._policy_workbench().capture_environment(
            environment_id=environment_id,
            snapshot=snapshot_data,
            actor=actor,
            source_label=str(source.get("label", environment_id)),
            version_number=source.get("version_number"),
            note=note,
        )
        return {
            "status": "captured",
            "environment": {
                **environment,
                **{
                    "capture_count": state.get("capture_count", 0),
                    "current_version_number": state.get("current", {}).get("version_number"),
                    "current_provider_count": state.get("current", {}).get("provider_count"),
                    "current_source_label": state.get("current", {}).get("source_label"),
                    "captured_at": state.get("current", {}).get("captured_at"),
                    "captured_by": state.get("current", {}).get("captured_by"),
                    "last_capture_note": state.get("current", {}).get("note"),
                },
            },
            "environments": self.get_policy_environment_profiles(),
        }

    async def stage_policy_promotion(
        self,
        *,
        source_environment: str,
        target_environment: str,
        author: str = "api",
        description: str = "",
    ) -> dict[str, Any]:
        """Create a promotion proposal from one environment into another."""

        source_state = self._policy_workbench().get_environment_state(source_environment)
        if source_state is None:
            return {
                "error": f"No captured policy baseline found for {source_environment}.",
                "status": 400,
            }
        target_profile = get_policy_environment(target_environment)
        if target_profile is None:
            return {
                "error": f"Unknown policy environment: {target_environment}",
                "status": 400,
            }

        current = source_state.get("current", {})
        snapshot = current.get("snapshot")
        if not isinstance(snapshot, dict):
            return {
                "error": f"{source_environment} does not have a captured snapshot to promote.",
                "status": 400,
            }

        payload = await self.import_policy_snapshot(
            snapshot,
            author=author,
            description_prefix=(
                description
                or f"Promote policy from {source_environment} to {target_environment}"
            ),
            metadata={
                "workbench_kind": "promotion",
                "source_environment": source_environment,
                "target_environment": target_environment,
                "source_version_number": current.get("version_number"),
            },
            force=True,
        )
        proposal = payload.get("proposal", {})
        proposal_id = proposal.get("proposal_id")
        if payload.get("status") == "imported" and isinstance(proposal_id, str):
            self._policy_workbench().record_promotion(
                source_environment=source_environment,
                target_environment=target_environment,
                actor=author,
                note=description,
                proposal_id=proposal_id,
                source_version_number=current.get("version_number"),
                target_version_number=None,
            )
            payload["promotions"] = self.get_policy_promotions()
        return payload

    # ── Policy Versioning ────────────────────────────────────

    def get_policy_versions(self) -> dict[str, Any]:
        """List all policy versions."""
        if self.policy_version_manager is None:
            return {"error": "Policy versioning not configured", "status": 503}

        from fastmcp.server.security.policy.versioning.models import (
            policy_version_to_dict,
        )

        versions = self.policy_version_manager.list_versions()
        current = self.policy_version_manager.current_version

        return {
            "policy_set_id": self.policy_version_manager.policy_set_id,
            "version_count": len(versions),
            "current_version": current.version_number if current else None,
            "versions": [policy_version_to_dict(v) for v in versions],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def rollback_policy_version(
        self, version_number: int, reason: str = ""
    ) -> dict[str, Any]:
        """Rollback to a specific policy version.

        Args:
            version_number: The 1-based version number to rollback to.
            reason: Reason for the rollback.
        """
        if self.policy_version_manager is None:
            return {"error": "Policy versioning not configured", "status": 503}

        from fastmcp.server.security.policy.versioning.models import (
            policy_version_to_dict,
        )

        try:
            version = self.policy_version_manager.rollback_to(
                version_number=version_number,
                reason=reason,
            )
        except ValueError as e:
            return {"error": str(e), "status": 400}

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        try:
            await self.policy_engine.restore_version(version.policy_data, reason=reason)
        except Exception as e:
            return {"error": str(e), "status": 400}

        return {
            "status": "rolled_back",
            "version": policy_version_to_dict(version),
            "policy": self.get_policy_status(),
        }

    async def add_policy_provider(
        self,
        config: dict[str, Any],
        *,
        reason: str = "",
        author: str = "api",
    ) -> dict[str, Any]:
        """Add a new live policy provider from a config object."""

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        validation_error = self._validate_policy_mutation(
            action="add",
            config=config,
            target_index=None,
        )
        if validation_error is not None:
            return validation_error

        provider = policy_provider_from_config(config)
        await self.policy_engine.add_provider(
            provider,
            reason=reason or "API add",
            author=author,
        )
        providers = self.get_policy_status().get("providers", [])
        created = providers[-1] if providers else None
        return {
            "status": "created",
            "provider": created,
            "policy": self.get_policy_status(),
        }

    async def update_policy_provider(
        self,
        index: int,
        config: dict[str, Any],
        *,
        reason: str = "",
        author: str = "api",
    ) -> dict[str, Any]:
        """Replace a live provider at a specific index."""

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        validation_error = self._validate_policy_mutation(
            action="swap",
            config=config,
            target_index=index,
        )
        if validation_error is not None:
            return validation_error

        provider = policy_provider_from_config(config)
        try:
            record = await self.policy_engine.hot_swap(
                index,
                provider,
                reason=reason or "API edit",
                author=author,
            )
        except IndexError as e:
            return {"error": str(e), "status": 400}

        provider_payload = self.get_policy_status().get("providers", [])
        updated = provider_payload[index] if index < len(provider_payload) else None
        return {
            "status": "updated",
            "swap": {
                "old_policy_id": record.old_policy_id,
                "old_version": record.old_version,
                "new_policy_id": record.new_policy_id,
                "new_version": record.new_version,
                "reason": record.reason,
                "swapped_at": record.swapped_at.isoformat(),
            },
            "provider": updated,
            "policy": self.get_policy_status(),
        }

    async def delete_policy_provider(
        self,
        index: int,
        *,
        reason: str = "",
        author: str = "api",
    ) -> dict[str, Any]:
        """Remove a live provider by index."""

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        validation_error = self._validate_policy_mutation(
            action="remove",
            config=None,
            target_index=index,
        )
        if validation_error is not None:
            return validation_error

        try:
            removed = await self.policy_engine.remove_provider(
                index,
                reason=reason or "API delete",
                author=author,
            )
        except IndexError as e:
            return {"error": str(e), "status": 400}

        return {
            "status": "deleted",
            "provider": describe_policy_provider(removed, index=index),
            "policy": self.get_policy_status(),
        }

    def diff_policy_versions(self, v1: int, v2: int) -> dict[str, Any]:
        """Get differences between two policy versions.

        Args:
            v1: First version number (1-based).
            v2: Second version number (1-based).
        """
        if self.policy_version_manager is None:
            return {"error": "Policy versioning not configured", "status": 503}

        try:
            diff = self.policy_version_manager.diff(v1, v2)
        except ValueError as e:
            return {"error": str(e), "status": 400}

        return {
            "v1": v1,
            "v2": v2,
            "diff": diff,
            "summary": self._summarize_version_delta(v1, v2),
        }

    async def import_policy_snapshot(
        self,
        snapshot: dict[str, Any] | list[Any],
        *,
        author: str = "api",
        description_prefix: str = "Imported policy snapshot",
        metadata: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Import policy JSON by creating one batch governance proposal."""
        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        normalized = self._normalize_import_snapshot(snapshot)
        if normalized.get("status") == 400:
            return normalized

        try:
            imported_providers = providers_from_snapshot(normalized)
        except (TypeError, ValueError) as exc:
            return {"error": str(exc), "status": 400}

        raw_providers = normalized.get("providers", [])
        if not isinstance(raw_providers, list):
            return {
                "error": "Imported snapshot is missing a provider list.",
                "status": 400,
            }

        imported_configs: list[dict[str, Any]] = []
        for raw_provider in raw_providers:
            if not isinstance(raw_provider, dict):
                return {
                    "error": "Each imported provider must be a JSON object.",
                    "status": 400,
                }
            if (
                self.policy_validator is not None
                and raw_provider.get("type") != "python_class"
            ):
                result = self.policy_validator.validate_declarative(raw_provider)
                if not result.valid:
                    return {
                        "error": "Imported policy snapshot failed validation.",
                        "status": 400,
                        "validation": result.to_dict(),
                    }
            imported_configs.append(raw_provider)
        current_configs = [
            describe_policy_provider(provider, index=index)["config"]
            for index, provider in enumerate(self.policy_engine.providers)
        ]

        if current_configs == imported_configs and not force:
            return {
                "status": "no_changes",
                "summary": {
                    "created": 0,
                    "added": 0,
                    "changed": 0,
                    "removed": 0,
                    "imported_provider_count": len(imported_providers),
                    "current_provider_count": len(current_configs),
                },
                "governance": self.get_governance_proposals(),
            }

        try:
            proposal = self.policy_governor.propose_replace_chain(
                imported_providers,
                author=author,
                description=description_prefix,
                metadata=metadata,
            )
            validation = self.policy_governor.validate_proposal(proposal.proposal_id)
        except (IndexError, KeyError, ValueError) as exc:
            return {"error": str(exc), "status": 400}

        added = max(0, len(imported_configs) - len(current_configs))
        removed = max(0, len(current_configs) - len(imported_configs))
        changed = sum(
            1
            for index in range(min(len(current_configs), len(imported_configs)))
            if current_configs[index] != imported_configs[index]
        )

        return {
            "status": "imported",
            "summary": {
                "created": 1,
                "added": added,
                "changed": changed,
                "removed": removed,
                "imported_provider_count": len(imported_providers),
                "current_provider_count": len(current_configs),
            },
            "proposal": self._serialize_governance_proposal(proposal),
            "validation": validation.to_dict(),
            "governance": self.get_governance_proposals(),
        }

    def get_policy_analytics(self) -> dict[str, Any]:
        """Return blocked/changed/risk summaries for the policy workbench."""

        policy = self.get_policy_status()
        governance = self.get_governance_proposals()
        audit_stats = (
            self.get_policy_audit_statistics()
            if self.policy_audit_log is not None
            else {"status": 503}
        )
        recent_denials = (
            self.get_policy_audit(decision="deny", limit=5)
            if self.policy_audit_log is not None
            else {"entries": []}
        )
        monitor_metrics = (
            self.get_policy_metrics()
            if self.policy_monitor is not None
            else {"status": 503}
        )
        alerts = (
            self.get_policy_alerts(limit=5)
            if self.policy_monitor is not None
            else {"alerts": []}
        )

        current_version = (
            self.policy_version_manager.current_version
            if self.policy_version_manager is not None
            else None
        )
        previous_version_number = None
        latest_change_summary: dict[str, Any] | None = None
        if (
            self.policy_version_manager is not None
            and current_version is not None
            and current_version.version_number > 1
        ):
            previous_version_number = current_version.version_number - 1
            latest_change_summary = self._summarize_version_delta(
                previous_version_number,
                current_version.version_number,
            )

        providers = policy.get("providers", [])
        provider_configs = [
            provider["config"]
            for provider in providers
            if isinstance(provider, dict) and isinstance(provider.get("config"), dict)
        ]
        deny_rate = 0.0
        if isinstance(audit_stats, dict):
            deny_rate = float(audit_stats.get("deny_rate", 0.0) or 0.0)
        recent_alerts = alerts.get("alerts", []) if isinstance(alerts, dict) else []
        risk_items = build_policy_risks(
            provider_configs=provider_configs,
            pending_count=int(governance.get("pending_count", 0) or 0),
            stale_count=int(governance.get("stale_count", 0) or 0),
            deny_rate=deny_rate,
            recent_alert_count=len(recent_alerts),
            changed_count=(
                int(latest_change_summary.get("changed_count", 0))
                if latest_change_summary is not None
                else 0
            ),
        )
        history = self._policy_workbench().record_analytics_snapshot(
            {
                "current_version": (
                    current_version.version_number if current_version is not None else None
                ),
                "provider_count": policy.get("provider_count"),
                "evaluation_count": policy.get("evaluation_count"),
                "deny_count": policy.get("deny_count"),
                "deny_rate": deny_rate,
                "pending_proposals": governance.get("pending_count"),
                "stale_proposals": governance.get("stale_count"),
                "risk_count": len(risk_items),
                "alert_count": len(recent_alerts),
            }
        )
        history_start = history[0] if history else {}
        history_end = history[-1] if history else {}

        return {
            "overview": {
                "provider_count": policy.get("provider_count"),
                "evaluation_count": policy.get("evaluation_count"),
                "deny_count": policy.get("deny_count"),
                "current_version": (
                    current_version.version_number
                    if current_version is not None
                    else None
                ),
                "pending_proposals": governance.get("pending_count"),
                "stale_proposals": governance.get("stale_count"),
            },
            "blocked": {
                "audit": audit_stats,
                "recent_denials": recent_denials.get("entries", [])
                if isinstance(recent_denials, dict)
                else [],
                "monitor": monitor_metrics,
                "alerts": recent_alerts,
            },
            "changes": {
                "latest_version_from": previous_version_number,
                "latest_version_to": (
                    current_version.version_number
                    if current_version is not None
                    else None
                ),
                "latest_version_summary": latest_change_summary,
                "recent_deployments": [
                    proposal
                    for proposal in governance.get("proposals", [])
                    if proposal.get("status") == "deployed"
                ][:5],
            },
            "history": {
                "snapshots": history,
                "sample_count": len(history),
                "deltas": {
                    "evaluation_count": int(history_end.get("evaluation_count", 0) or 0)
                    - int(history_start.get("evaluation_count", 0) or 0),
                    "deny_count": int(history_end.get("deny_count", 0) or 0)
                    - int(history_start.get("deny_count", 0) or 0),
                    "pending_proposals": int(
                        history_end.get("pending_proposals", 0) or 0
                    )
                    - int(history_start.get("pending_proposals", 0) or 0),
                    "risk_count": int(history_end.get("risk_count", 0) or 0)
                    - int(history_start.get("risk_count", 0) or 0),
                },
                "recent_promotions": self._policy_workbench().list_promotions(limit=6),
            },
            "risks": risk_items,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def preview_policy_migration(
        self,
        *,
        source_snapshot: dict[str, Any] | None = None,
        source_version_number: int | None = None,
        target_version_number: int | None = None,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        """Preview promotion between live/versioned chains and named environments."""

        environment = get_policy_environment(target_environment)
        if environment is None:
            return {
                "error": f"Unknown policy environment: {target_environment}",
                "status": 400,
            }

        source = self._resolve_policy_snapshot(
            snapshot=source_snapshot,
            version_number=source_version_number,
            label_prefix="source",
        )
        if "error" in source:
            source["status"] = source.get("status", 400)
            return source

        target = self._resolve_policy_snapshot(
            version_number=target_version_number,
            label_prefix="target",
        )
        if "error" in target:
            target["status"] = target.get("status", 400)
            return target

        source_snapshot_data = source["snapshot"]
        target_snapshot_data = target["snapshot"]
        source_providers = source_snapshot_data.get("providers", [])
        target_providers = target_snapshot_data.get("providers", [])
        if not isinstance(source_providers, list) or not isinstance(
            target_providers, list
        ):
            return {
                "error": "Policy migration preview requires provider lists on both sides.",
                "status": 400,
            }

        source_configs = [item for item in source_providers if isinstance(item, dict)]
        target_configs = [item for item in target_providers if isinstance(item, dict)]
        summary = summarize_policy_chain_delta(source_configs, target_configs)
        risks = build_policy_risks(
            provider_configs=source_configs,
            changed_count=int(summary.get("changed_count", 0)),
        )
        risks.extend(
            [
                {
                    "level": "medium",
                    "title": "Target environment requires stronger controls",
                    "detail": recommendation,
                }
                for recommendation in build_environment_recommendations(
                    environment_id=target_environment,
                    provider_configs=source_configs,
                )
                if recommendation
                != "This chain already lines up well with the selected environment profile."
            ]
        )

        return {
            "source": {
                "label": source["label"],
                "version_number": source.get("version_number"),
                "provider_count": len(source_configs),
            },
            "target": {
                "label": target["label"],
                "version_number": target.get("version_number"),
                "provider_count": len(target_configs),
            },
            "environment": environment,
            "summary": summary,
            "recommendations": build_environment_recommendations(
                environment_id=target_environment,
                provider_configs=source_configs,
            ),
            "risks": risks,
            "suggested_snapshot": {
                "format": source_snapshot_data.get("format", "securemcp-policy-set/v1"),
                "providers": source_configs,
                "metadata": {
                    **dict(source_snapshot_data.get("metadata", {})),
                    "target_environment": target_environment,
                    "migration_source": source["label"],
                    "migration_target": target["label"],
                },
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Validation ─────────────────────────────────────────────

    def validate_policy(self, config: dict) -> dict[str, Any]:
        """Validate a declarative policy config.

        Args:
            config: The policy dict to validate.

        Returns:
            ValidationResult as a dict.
        """
        if self.policy_validator is None:
            return {"error": "Policy validator not configured", "status": 503}

        result = self.policy_validator.validate_declarative(config)
        return result.to_dict()

    def _resolve_policy_snapshot(
        self,
        *,
        snapshot: dict[str, Any] | None = None,
        version_number: int | None = None,
        label_prefix: str,
    ) -> dict[str, Any]:
        if snapshot is not None:
            normalized = self._normalize_import_snapshot(snapshot)
            if normalized.get("status") == 400:
                return normalized
            return {
                "label": f"{label_prefix}: imported snapshot",
                "version_number": None,
                "snapshot": normalized,
            }

        exported = self.export_policy_snapshot(version_number=version_number)
        if exported.get("error"):
            return exported
        return {
            "label": (
                f"{label_prefix}: live policy"
                if version_number is None
                else f"{label_prefix}: version {version_number}"
            ),
            "version_number": exported.get("version_number"),
            "snapshot": exported.get("snapshot", {}),
        }

    def _summarize_version_delta(self, v1: int, v2: int) -> dict[str, Any] | None:
        if self.policy_version_manager is None:
            return None

        versions = {
            version.version_number: version
            for version in self.policy_version_manager.list_versions()
        }
        source_version = versions.get(v1)
        target_version = versions.get(v2)
        if source_version is None or target_version is None:
            return None

        source_snapshot = source_version.policy_data
        target_snapshot = target_version.policy_data
        source_providers = source_snapshot.get("providers", [])
        target_providers = target_snapshot.get("providers", [])
        if not isinstance(source_providers, list) or not isinstance(
            target_providers, list
        ):
            return None

        summary = summarize_policy_chain_delta(
            [item for item in source_providers if isinstance(item, dict)],
            [item for item in target_providers if isinstance(item, dict)],
        )
        summary["from_version"] = v1
        summary["to_version"] = v2
        return summary

    def _normalize_import_snapshot(
        self,
        snapshot: dict[str, Any] | list[Any],
    ) -> dict[str, Any]:
        """Normalize imported JSON into the stored policy snapshot format."""
        if isinstance(snapshot, list):
            if not all(isinstance(item, dict) for item in snapshot):
                return {
                    "error": "Imported provider lists must contain only objects.",
                    "status": 400,
                }
            return {
                "format": "securemcp-policy-set/v1",
                "providers": snapshot,
                "metadata": {"source": "policy_import"},
            }

        if not isinstance(snapshot, dict):
            return {
                "error": "Imported policy must be a JSON object or provider list.",
                "status": 400,
            }

        if isinstance(snapshot.get("policy_data"), dict):
            policy_data = snapshot["policy_data"]
            if isinstance(policy_data.get("providers"), list):
                return policy_data

        if isinstance(snapshot.get("providers"), list):
            normalized = dict(snapshot)
            normalized.setdefault("format", "securemcp-policy-set/v1")
            normalized.setdefault("metadata", {"source": "policy_import"})
            return normalized

        if "type" in snapshot or "composition" in snapshot:
            return {
                "format": "securemcp-policy-set/v1",
                "providers": [snapshot],
                "metadata": {"source": "policy_import", "shape": "single_provider"},
            }

        return {
            "error": (
                "Imported JSON must be a policy snapshot, a provider list, "
                "or a single policy config."
            ),
            "status": 400,
        }

    def _validate_policy_mutation(
        self,
        *,
        action: str,
        config: dict[str, Any] | None,
        target_index: int | None,
    ) -> dict[str, Any] | None:
        """Validate a proposed live mutation before applying it."""

        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        current = list(self.policy_engine.providers)
        action_name = action.strip().lower()

        new_provider = None
        if config is not None:
            if (
                self.policy_validator is not None
                and config.get("type") != "python_class"
            ):
                result = self.policy_validator.validate_declarative(config)
                if not result.valid:
                    return {
                        "error": "Policy config failed validation.",
                        "status": 400,
                        "validation": result.to_dict(),
                    }
            try:
                new_provider = policy_provider_from_config(config)
            except Exception as exc:
                return {"error": str(exc), "status": 400}

        try:
            if action_name == "add":
                assert new_provider is not None
                current.append(new_provider)
            elif action_name == "swap":
                if target_index is None:
                    raise ValueError("Missing target index for swap.")
                assert new_provider is not None
                current[target_index] = new_provider
            elif action_name == "remove":
                if target_index is None:
                    raise ValueError("Missing target index for remove.")
                current.pop(target_index)
            else:
                raise ValueError(f"Unsupported mutation action: {action}")
        except (IndexError, ValueError) as exc:
            return {"error": str(exc), "status": 400}

        if self.policy_validator is None:
            return None

        semantic_result = self.policy_validator.validate_providers(current)
        if semantic_result.valid:
            return None

        return {
            "error": "Policy set failed semantic validation.",
            "status": 400,
            "validation": semantic_result.to_dict(),
        }

    def validate_providers(self) -> dict[str, Any]:
        """Validate the current engine providers for semantic issues."""
        if self.policy_validator is None:
            return {"error": "Policy validator not configured", "status": 503}
        if self.policy_engine is None:
            return {"error": "Policy engine not configured", "status": 503}

        result = self.policy_validator.validate_providers(self.policy_engine.providers)
        return result.to_dict()

    # ── Monitoring ────────────────────────────────────────────

    def get_policy_metrics(self) -> dict[str, Any]:
        """Get current policy monitoring metrics."""
        if self.policy_monitor is None:
            return {"error": "Policy monitor not configured", "status": 503}

        return self.policy_monitor.get_metrics()

    def get_policy_alerts(self, limit: int = 50) -> dict[str, Any]:
        """Get recent monitoring alerts.

        Args:
            limit: Maximum number of alerts to return.
        """
        if self.policy_monitor is None:
            return {"error": "Policy monitor not configured", "status": 503}

        alerts = self.policy_monitor.get_recent_alerts(limit=limit)
        return {
            "total_alerts": len(alerts),
            "alerts": alerts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Governance ────────────────────────────────────────────

    def get_governance_proposals(self) -> dict[str, Any]:
        """List all governance proposals."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        proposals = self.policy_governor.proposals
        current_version = (
            self.policy_version_manager.current_version
            if self.policy_version_manager is not None
            else None
        )
        serialized = [self._serialize_governance_proposal(p) for p in proposals]
        terminal_statuses = {"deployed", "rejected", "withdrawn"}
        return {
            "total_proposals": len(proposals),
            "pending_count": len(self.policy_governor.pending_proposals),
            "require_simulation": self.policy_governor.require_simulation,
            "require_approval": self.policy_governor.require_approval,
            "current_version": (
                current_version.version_number if current_version is not None else None
            ),
            "stale_count": sum(
                1
                for proposal in serialized
                if proposal.get("is_stale") is True
                and proposal.get("status") not in terminal_statuses
            ),
            "proposals": serialized,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_governance_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Get a single proposal by ID."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        proposal = self.policy_governor.get_proposal(proposal_id)
        if proposal is None:
            return {"error": f"Proposal not found: {proposal_id}", "status": 404}

        return self._serialize_governance_proposal(proposal)

    async def create_governance_proposal(
        self,
        *,
        action: str,
        config: dict[str, Any] | None,
        target_index: int | None,
        description: str = "",
        author: str = "api",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and validate a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        provider: Any = None
        action_name = action.strip().lower()

        if action_name in {"add", "swap"}:
            if config is None:
                return {
                    "error": "`config` is required for add and swap proposals.",
                    "status": 400,
                }

            if (
                self.policy_validator is not None
                and config.get("type") != "python_class"
            ):
                result = self.policy_validator.validate_declarative(config)
                if not result.valid:
                    return {
                        "error": "Policy config failed validation.",
                        "status": 400,
                        "validation": result.to_dict(),
                    }
            try:
                provider = policy_provider_from_config(config)
            except Exception as exc:
                return {"error": str(exc), "status": 400}

        try:
            if action_name == "add":
                assert provider is not None
                proposal = self.policy_governor.propose_add(
                    provider,
                    author=author,
                    description=description,
                    metadata=metadata,
                )
            elif action_name == "swap":
                if target_index is None:
                    raise ValueError("`target_index` is required for swap proposals.")
                assert provider is not None
                proposal = self.policy_governor.propose_swap(
                    target_index,
                    provider,
                    author=author,
                    description=description,
                    metadata=metadata,
                )
            elif action_name == "remove":
                if target_index is None:
                    raise ValueError("`target_index` is required for remove proposals.")
                proposal = self.policy_governor.propose_remove(
                    target_index,
                    author=author,
                    description=description,
                    metadata=metadata,
                )
            elif action_name == "replace_chain":
                if config is None:
                    raise ValueError(
                        "`config` is required for replace_chain proposals."
                    )
                normalized = self._normalize_import_snapshot(config)
                if normalized.get("status") == 400:
                    return normalized
                providers = providers_from_snapshot(normalized)
                proposal = self.policy_governor.propose_replace_chain(
                    providers,
                    author=author,
                    description=description,
                    metadata=metadata,
                )
            else:
                raise ValueError(f"Unsupported proposal action: {action}")
            validation = self.policy_governor.validate_proposal(proposal.proposal_id)
        except (IndexError, KeyError, ValueError) as exc:
            return {"error": str(exc), "status": 400}

        return {
            "status": "created",
            "proposal": self._serialize_governance_proposal(proposal),
            "validation": validation.to_dict(),
            "governance": self.get_governance_proposals(),
        }

    def _sync_workbench_proposal_state(
        self,
        proposal: Any,
        *,
        status: str,
        actor: str,
        note: str = "",
    ) -> None:
        """Reflect proposal lifecycle changes into the workbench store."""

        metadata = (
            proposal.metadata
            if isinstance(getattr(proposal, "metadata", None), dict)
            else {}
        )
        if metadata.get("workbench_kind") != "promotion":
            return

        deployed_version_number = None
        if status == "deployed":
            current_version = (
                self.policy_version_manager.current_version
                if self.policy_version_manager is not None
                else None
            )
            deployed_version_number = (
                current_version.version_number if current_version is not None else None
            )
            target_environment = str(metadata.get("target_environment", "")).strip()
            source_environment = str(metadata.get("source_environment", "")).strip()
            if target_environment and self.policy_engine is not None:
                snapshot = policy_snapshot(
                    list(self.policy_engine.providers),
                    metadata={
                        "source": "promotion",
                        "source_environment": source_environment,
                        "target_environment": target_environment,
                        "proposal_id": proposal.proposal_id,
                    },
                )
                self._policy_workbench().capture_environment(
                    environment_id=target_environment,
                    snapshot=snapshot,
                    actor=actor,
                    source_label=(
                        f"promotion from {source_environment}"
                        if source_environment
                        else "promotion"
                    ),
                    version_number=deployed_version_number,
                    note=note or proposal.description,
                )

        self._policy_workbench().update_promotion_from_proposal(
            proposal_id=proposal.proposal_id,
            status=status,
            actor=actor,
            note=note,
            deployed_version_number=deployed_version_number,
        )

    def approve_governance_proposal(
        self,
        proposal_id: str,
        *,
        approver: str = "api",
        note: str = "",
    ) -> dict[str, Any]:
        """Approve a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        try:
            proposal = self.policy_governor.approve(
                proposal_id,
                approver=approver,
                note=note,
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        self._sync_workbench_proposal_state(
            proposal,
            status="approved",
            actor=approver,
            note=note,
        )
        return {
            "status": "approved",
            "proposal": self._serialize_governance_proposal(proposal),
            "governance": self.get_governance_proposals(),
        }

    async def deploy_governance_proposal(
        self,
        proposal_id: str,
        *,
        actor: str = "api",
        note: str = "",
    ) -> dict[str, Any]:
        """Deploy an approved governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        try:
            proposal = await self.policy_governor.deploy(
                proposal_id,
                actor=actor,
                note=note,
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        self._sync_workbench_proposal_state(
            proposal,
            status="deployed",
            actor=actor,
            note=note,
        )
        return {
            "status": "deployed",
            "proposal": self._serialize_governance_proposal(proposal),
            "policy": self.get_policy_status(),
            "versions": self.get_policy_versions(),
            "governance": self.get_governance_proposals(),
        }

    async def simulate_governance_proposal(
        self,
        proposal_id: str,
        *,
        scenarios_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run simulation for a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        scenarios = self._build_scenarios(scenarios_data)
        try:
            report = await self.policy_governor.simulate_proposal(
                proposal_id, scenarios
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        proposal = self.policy_governor.get_proposal(proposal_id)
        payload: dict[str, Any] = {
            "status": "simulated",
            "simulation": report.to_dict(),
            "governance": self.get_governance_proposals(),
        }
        if proposal is not None:
            self._sync_workbench_proposal_state(
                proposal,
                status="simulated",
                actor="policy-simulator",
                note=f"Ran {report.total} scenarios.",
            )
            payload["proposal"] = self._serialize_governance_proposal(proposal)
        return payload

    def reject_governance_proposal(
        self,
        proposal_id: str,
        *,
        reason: str = "",
        actor: str = "api",
    ) -> dict[str, Any]:
        """Reject a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        try:
            proposal = self.policy_governor.reject(
                proposal_id,
                reason=reason,
                actor=actor,
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        self._sync_workbench_proposal_state(
            proposal,
            status="rejected",
            actor=actor,
            note=reason,
        )
        return {
            "status": "rejected",
            "proposal": self._serialize_governance_proposal(proposal),
            "governance": self.get_governance_proposals(),
        }

    def withdraw_governance_proposal(
        self,
        proposal_id: str,
        *,
        actor: str = "api",
        note: str = "",
    ) -> dict[str, Any]:
        """Withdraw a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        try:
            proposal = self.policy_governor.withdraw(
                proposal_id,
                actor=actor,
                note=note,
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        self._sync_workbench_proposal_state(
            proposal,
            status="withdrawn",
            actor=actor,
            note=note,
        )
        return {
            "status": "withdrawn",
            "proposal": self._serialize_governance_proposal(proposal),
            "governance": self.get_governance_proposals(),
        }

    def assign_governance_proposal(
        self,
        proposal_id: str,
        *,
        reviewer: str,
        actor: str = "api",
        note: str = "",
    ) -> dict[str, Any]:
        """Assign ownership of a governance proposal."""
        if self.policy_governor is None:
            return {"error": "Policy governance not configured", "status": 503}

        try:
            proposal = self.policy_governor.assign(
                proposal_id,
                reviewer=reviewer,
                actor=actor,
                note=note,
            )
        except KeyError as exc:
            return {"error": str(exc), "status": 404}
        except ValueError as exc:
            return {"error": str(exc), "status": 400}

        return {
            "status": "assigned",
            "proposal": self._serialize_governance_proposal(proposal),
            "governance": self.get_governance_proposals(),
        }

    def _serialize_governance_proposal(self, proposal: Any) -> dict[str, Any]:
        """Return a UI-friendly governance proposal payload."""
        payload = proposal.to_dict()
        current_version = (
            self.policy_version_manager.current_version
            if self.policy_version_manager is not None
            else None
        )
        live_version_number = (
            current_version.version_number if current_version is not None else None
        )
        payload["live_version_number"] = live_version_number
        payload["is_stale"] = (
            payload.get("base_version_number") is not None
            and live_version_number is not None
            and payload["base_version_number"] != live_version_number
        )
        if proposal.new_provider is not None:
            payload["provider"] = describe_policy_provider(
                proposal.new_provider,
                index=proposal.target_index
                if proposal.target_index is not None
                else -1,
            )
        if proposal.replacement_providers is not None:
            payload["provider_set"] = [
                describe_policy_provider(provider, index=index)
                for index, provider in enumerate(proposal.replacement_providers)
            ]
        return payload

    @staticmethod
    def _build_scenarios(scenarios_data: list[dict[str, Any]]) -> list[Any]:
        """Convert plain payloads to simulation scenarios."""
        from fastmcp.server.security.policy.simulation import Scenario

        scenarios: list[Scenario] = []
        for item in scenarios_data:
            scenarios.append(
                Scenario(
                    resource_id=str(item.get("resource_id", "unknown")),
                    action=str(item.get("action", "call_tool")),
                    actor_id=str(item.get("actor_id", "sim-actor")),
                    metadata=dict(item.get("metadata", {})),
                    tags=frozenset(item.get("tags", [])),
                    label=str(item.get("label", "")),
                )
            )
        return scenarios

    # ── Contracts ─────────────────────────────────────────────

    async def negotiate_contract(
        self,
        request_body: dict[str, Any],
    ) -> dict[str, Any]:
        """Initiate or continue a contract negotiation.

        Expects a JSON body with ``agent_id``, optional ``session_id``
        (to continue), ``proposed_terms`` list, and optional ``context``.
        """
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        from fastmcp.server.security.contracts.schema import (
            ContractNegotiationRequest,
            ContractTerm,
            TermType,
        )

        raw_terms = request_body.get("proposed_terms", [])
        terms: list[ContractTerm] = []
        for raw in raw_terms:
            term_type_str = raw.get("term_type", "custom")
            try:
                term_type = TermType(term_type_str)
            except ValueError:
                term_type = TermType.CUSTOM
            terms.append(
                ContractTerm(
                    term_id=raw.get("term_id", ""),
                    term_type=term_type,
                    description=raw.get("description", ""),
                    constraint=raw.get("constraint", {}),
                    required=raw.get("required", False),
                    metadata=raw.get("metadata", {}),
                )
            )

        request = ContractNegotiationRequest(
            session_id=request_body.get("session_id", ""),
            agent_id=request_body.get("agent_id", ""),
            proposed_terms=terms,
            context=request_body.get("context", {}),
        )
        response = await self.broker.negotiate(request)

        result: dict[str, Any] = {
            "request_id": response.request_id,
            "session_id": response.session_id,
            "status": response.status.value,
            "reason": response.reason,
        }
        if response.contract is not None:
            result["contract"] = response.contract.to_dict()
            result["contract"]["signatures"] = dict(response.contract.signatures)
        if response.counter_terms is not None:
            result["counter_terms"] = [
                {
                    "term_id": t.term_id,
                    "term_type": t.term_type.value,
                    "description": t.description,
                    "constraint": t.constraint,
                    "required": t.required,
                }
                for t in response.counter_terms
            ]
        return result

    async def agent_sign_contract_endpoint(
        self,
        contract_id: str,
        signature_body: dict[str, Any],
    ) -> dict[str, Any]:
        """Accept an agent's countersignature on a pending contract."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        from fastmcp.server.security.contracts.crypto import (
            SignatureInfo,
            SigningAlgorithm,
        )

        try:
            sig = SignatureInfo(
                algorithm=SigningAlgorithm(signature_body["algorithm"]),
                signer_id=signature_body["signer_id"],
                signature=signature_body["signature"],
                key_id=signature_body.get("key_id", ""),
            )
        except (KeyError, ValueError) as exc:
            return {"error": f"Invalid signature payload: {exc}", "status": 400}

        success, error = await self.broker.agent_sign_contract(contract_id, sig)
        if success:
            contract = self.broker.get_contract(contract_id)
            return {
                "success": True,
                "contract_id": contract_id,
                "status": contract.status.value if contract else "active",
            }
        return {"error": error, "status": 400}

    def get_contract_details(self, contract_id: str) -> dict[str, Any]:
        """Return details for a single contract."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        contract = self.broker.get_contract(contract_id)
        if contract is None:
            return {"error": "Contract not found", "status": 404}

        return {
            "contract": contract.to_dict(),
            "signatures": dict(contract.signatures),
            "is_valid": contract.is_valid(),
            "is_mutually_signed": (
                contract.server_id in contract.signatures
                and contract.agent_id in contract.signatures
            ),
        }

    def list_agent_contracts(self, agent_id: str) -> dict[str, Any]:
        """List active contracts for an agent."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        contracts = self.broker.get_active_contracts_for_agent(agent_id)
        return {
            "agent_id": agent_id,
            "contracts": [c.to_dict() for c in contracts],
            "count": len(contracts),
        }

    async def revoke_contract_endpoint(
        self,
        contract_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Revoke a contract."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        success = await self.broker.revoke_contract(contract_id, reason=reason)
        if success:
            return {"success": True, "contract_id": contract_id}
        return {"error": "Contract not found", "status": 404}

    def get_exchange_log_entries(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Export exchange log entries, optionally filtered by session."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        entries = self.broker.exchange_log.export_entries(session_id=session_id)
        return {
            "session_id": session_id,
            "entries": entries,
            "count": len(entries),
        }

    def verify_exchange_chain(self, session_id: str) -> dict[str, Any]:
        """Verify hash-chain integrity and return session summary."""
        if self.broker is None:
            return {"error": "Contracts not configured", "status": 503}

        summary = self.broker.exchange_log.get_session_summary(session_id)
        return summary

    # ── Federated Consent ────────────────────────────────────

    def evaluate_federated_consent(
        self,
        source_id: str,
        target_id: str,
        scope: str,
        *,
        geographic_context: dict[str, Any] | None = None,
        jurisdictions: list[str] | None = None,
        require_all_jurisdictions: bool = True,
    ) -> dict[str, Any]:
        """Evaluate consent with federation and jurisdiction awareness."""
        if self.federated_consent_graph is None:
            return {"error": "Federated consent not configured", "status": 503}

        from fastmcp.server.security.consent.models import (
            FederatedConsentQuery,
            GeographicContext,
        )

        geo = GeographicContext(
            source_jurisdiction=(geographic_context or {}).get(
                "source_jurisdiction", ""
            ),
            target_jurisdiction=(geographic_context or {}).get(
                "target_jurisdiction", ""
            ),
            data_residency=(geographic_context or {}).get("data_residency"),
            processing_location=(geographic_context or {}).get(
                "processing_location"
            ),
        )
        query = FederatedConsentQuery(
            source_id=source_id,
            target_id=target_id,
            scope=scope,
            geographic_context=geo,
            jurisdictions=jurisdictions,
            require_all_jurisdictions=require_all_jurisdictions,
        )
        decision = self.federated_consent_graph.evaluate_federated_consent(query)
        return {
            "granted": decision.granted,
            "reason": decision.reason,
            "local_decision": {
                "granted": decision.local_decision.granted
                if decision.local_decision
                else False,
                "reason": decision.local_decision.reason
                if decision.local_decision
                else "",
            },
            "jurisdiction_results": {
                jcode: {
                    "jurisdiction_code": jr.jurisdiction_code,
                    "satisfied": jr.satisfied,
                    "required_scopes": jr.required_scopes,
                    "satisfied_scopes": jr.satisfied_scopes,
                    "missing_scopes": jr.missing_scopes,
                    "applicable_regulations": jr.applicable_regulations,
                    "reason": jr.reason,
                }
                for jcode, jr in decision.jurisdiction_results.items()
            },
            "peer_decisions": {
                pid: {"granted": pd.granted, "reason": pd.reason}
                for pid, pd in decision.peer_decisions.items()
            },
            "access_rights": (
                {
                    "agent_id": decision.access_rights.agent_id,
                    "resource_id": decision.access_rights.resource_id,
                    "allowed_scopes": decision.access_rights.allowed_scopes,
                    "jurisdiction_constraints": decision.access_rights.jurisdiction_constraints,
                    "conditions": decision.access_rights.conditions,
                    "grant_sources": decision.access_rights.grant_sources,
                }
                if decision.access_rights
                else None
            ),
            "evaluated_at": decision.evaluated_at.isoformat(),
        }

    def get_access_rights(
        self,
        agent_id: str,
        resource_id: str,
        *,
        geographic_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute dynamic access rights for an agent on a resource."""
        if self.federated_consent_graph is None:
            return {"error": "Federated consent not configured", "status": 503}

        from fastmcp.server.security.consent.models import GeographicContext

        geo = (
            GeographicContext(
                source_jurisdiction=geographic_context.get(
                    "source_jurisdiction", ""
                ),
                target_jurisdiction=geographic_context.get(
                    "target_jurisdiction", ""
                ),
                data_residency=geographic_context.get("data_residency"),
                processing_location=geographic_context.get(
                    "processing_location"
                ),
            )
            if geographic_context
            else None
        )
        rights = self.federated_consent_graph.compute_access_rights(
            agent_id, resource_id, geographic_context=geo
        )
        return {
            "agent_id": rights.agent_id,
            "resource_id": rights.resource_id,
            "allowed_scopes": rights.allowed_scopes,
            "jurisdiction_constraints": rights.jurisdiction_constraints,
            "expires_at": rights.expires_at.isoformat()
            if rights.expires_at
            else None,
            "conditions": rights.conditions,
            "grant_sources": rights.grant_sources,
        }

    def list_jurisdictions(self) -> dict[str, Any]:
        """List all registered jurisdiction policies."""
        if self.federated_consent_graph is None:
            return {"error": "Federated consent not configured", "status": 503}

        policies = self.federated_consent_graph.list_jurisdiction_policies()
        return {
            "jurisdictions": {
                jcode: {
                    "jurisdiction_id": p.jurisdiction_id,
                    "jurisdiction_code": p.jurisdiction_code,
                    "applicable_regulations": p.applicable_regulations,
                    "required_consent_scopes": p.required_consent_scopes,
                    "requires_explicit_consent": p.requires_explicit_consent,
                    "data_residency_required": p.data_residency_required,
                }
                for jcode, p in policies.items()
            },
            "count": len(policies),
        }

    def list_institutions(self) -> dict[str, Any]:
        """List all registered institutions."""
        if self.federated_consent_graph is None:
            return {"error": "Federated consent not configured", "status": 503}

        institutions = self.federated_consent_graph.list_institutions()
        return {
            "institutions": {
                iid: {"jurisdiction_code": jcode}
                for iid, jcode in institutions.items()
            },
            "count": len(institutions),
        }

    def propagate_consent_endpoint(
        self,
        edge_id: str,
        target_peers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Propagate a consent grant to federation peers."""
        if self.federated_consent_graph is None:
            return {"error": "Federated consent not configured", "status": 503}

        results = self.federated_consent_graph.propagate_consent(
            edge_id, target_peers
        )
        return {
            "edge_id": edge_id,
            "propagation_results": results,
            "peers_notified": sum(1 for v in results.values() if v),
        }

    # ── Reflexive Introspection ────────────────────────────────

    def get_introspection(self, actor_id: str) -> dict[str, Any]:
        """Full introspection result for an actor."""
        if self.introspection_engine is None:
            return {"error": "Introspection engine not configured", "status": 503}

        result = self.introspection_engine.introspect(actor_id)
        return {
            "actor_id": result.actor_id,
            "threat_score": result.threat_score,
            "threat_level": result.threat_level.value,
            "drift_summary": result.drift_summary,
            "active_escalations": result.active_escalations,
            "compliance_status": result.compliance_status.value,
            "verdict": result.verdict.value,
            "should_halt": result.should_halt,
            "should_require_confirmation": result.should_require_confirmation,
            "constraints": result.constraints,
            "assessed_at": result.assessed_at.isoformat(),
        }

    def get_verdict(self, actor_id: str, operation: str) -> dict[str, Any]:
        """Execution verdict for a specific operation."""
        if self.introspection_engine is None:
            return {"error": "Introspection engine not configured", "status": 503}

        verdict = self.introspection_engine.get_execution_verdict(
            actor_id, operation
        )
        return {
            "actor_id": actor_id,
            "operation": operation,
            "verdict": verdict.value,
        }

    def get_actor_threat_level(self, actor_id: str) -> dict[str, Any]:
        """Current threat level for an actor."""
        if self.introspection_engine is None:
            return {"error": "Introspection engine not configured", "status": 503}

        level = self.introspection_engine.get_threat_level(actor_id)
        score = self.introspection_engine.profile_manager.threat_score(actor_id)
        return {
            "actor_id": actor_id,
            "threat_level": level.value,
            "threat_score": score,
        }

    def get_actor_constraints(self, actor_id: str) -> dict[str, Any]:
        """Active operational constraints for an actor."""
        if self.introspection_engine is None:
            return {"error": "Introspection engine not configured", "status": 503}

        constraints = self.introspection_engine.get_active_constraints(actor_id)
        return {
            "actor_id": actor_id,
            "constraints": constraints,
            "count": len(constraints),
        }

    def get_accountability(
        self, actor_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """Accountability audit trail for introspection records."""
        if self.introspection_engine is None:
            return {"error": "Introspection engine not configured", "status": 503}

        entries = self.introspection_engine.get_accountability_log(
            actor_id=actor_id, limit=limit
        )
        return {
            "entries": entries,
            "count": len(entries),
        }

    # ── Health ────────────────────────────────────────────────

    def get_health(self) -> dict[str, Any]:
        """Quick health check for the security layer."""
        components: dict[str, str] = {}

        if self.dashboard:
            components["dashboard"] = "ok"
        if self.marketplace:
            components["marketplace"] = "ok"
        if self.registry:
            components["registry"] = "ok"
        if self.compliance_reporter:
            components["compliance"] = "ok"
        if self.federation:
            components["federation"] = "ok"
        if self.crl:
            components["crl"] = "ok"
        if self.provenance_ledger:
            components["provenance"] = "ok"
        if self.event_bus:
            components["event_bus"] = "ok"
        if self.policy_engine:
            components["policy_engine"] = "ok"
        if self.policy_audit_log:
            components["policy_audit_log"] = "ok"
        if self.policy_version_manager:
            components["policy_versioning"] = "ok"
        if self.policy_validator:
            components["policy_validator"] = "ok"
        if self.policy_monitor:
            components["policy_monitor"] = "ok"
        if self.policy_governor:
            components["policy_governor"] = "ok"
        if self.broker:
            components["contracts"] = "ok"
        if self.federated_consent_graph:
            components["federated_consent"] = "ok"
        if self.introspection_engine:
            components["introspection_engine"] = "ok"

        return {
            "status": "healthy" if components else "unconfigured",
            "components": components,
            "component_count": len(components),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Route mounting ──────────────────────────────────────────────


SecurityAuthVerifier = Callable[
    [Request, str], "Awaitable[dict[str, Any] | None] | dict[str, Any] | None"
]
"""Callable that verifies a bearer token.

Receives the Starlette ``Request`` and the bearer token string. Returns
a non-empty principal dict on success (recorded as the request's
authenticated actor) or ``None`` on failure. Sync and async return
values are both accepted.
"""


def _make_bearer_token_verifier(expected_token: str) -> SecurityAuthVerifier:
    """Build a verifier that does a constant-time compare against a single token."""
    expected = expected_token.encode("utf-8")

    def _verify(_request: Request, presented: str) -> dict[str, Any] | None:
        if hmac.compare_digest(expected, presented.encode("utf-8")):
            return {"actor": "shared-secret", "auth": "bearer-token"}
        return None

    return _verify


async def _resolve_principal(
    verifier: SecurityAuthVerifier,
    request: Request,
    token: str,
) -> dict[str, Any] | None:
    result = verifier(request, token)
    if inspect.isawaitable(result):
        result = await result
    if result and isinstance(result, dict):
        return result
    return None


def mount_security_routes(
    server: FastMCP,
    *,
    api: SecurityAPI | None = None,
    prefix: str = "/security",
    require_auth: bool = True,
    bearer_token: str | None = None,
    auth_verifier: SecurityAuthVerifier | None = None,
) -> SecurityAPI:
    """Mount SecureMCP HTTP routes on a FastMCP server.

    All routes are authenticated by default. The destructive endpoints
    (policy import, version rollback, marketplace moderation, contract
    signing, etc.) require a verified bearer token before any handler
    runs. There are three ways to configure auth, in order of precedence:

    1. ``auth_verifier``: a callable returning a principal dict on
       success or ``None`` on failure. Use this for custom JWT, OAuth
       introspection, or signed-request integrations.
    2. ``bearer_token``: a static shared secret. Requests must present
       ``Authorization: Bearer <bearer_token>``. Constant-time compared.
    3. ``require_auth=False``: explicit opt-out. Mounting routes
       unauthenticated logs a CRITICAL-tier warning. Use only in
       single-tenant local-development scenarios.

    Configuring ``require_auth=True`` (the default) without supplying
    either ``auth_verifier`` or ``bearer_token`` raises ``RuntimeError``
    at mount time — the mount fails closed rather than silently
    accepting all callers.

    Args:
        server: The FastMCP server instance.
        prefix: URL prefix for all security routes (default ``/security``).
        api: Optional pre-configured SecurityAPI. If None, built from
            the server's security context.
        require_auth: If True (default), enforce auth on every route.
        bearer_token: Static bearer-token secret for the simple shared-
            secret pattern. Mutually compatible with ``auth_verifier``;
            if both are passed, ``auth_verifier`` takes precedence.
        auth_verifier: Custom token verifier. See :data:`SecurityAuthVerifier`.

    Returns:
        The SecurityAPI instance (for further customization).

    Example::

        from fastmcp import FastMCP
        from fastmcp.server.security import SecurityConfig, attach_security
        from fastmcp.server.security.http import mount_security_routes

        server = FastMCP("secure-server")
        attach_security(server, SecurityConfig(...))
        api = mount_security_routes(
            server,
            bearer_token=os.environ["SECUREMCP_API_TOKEN"],
        )
        server.run(transport="streamable-http")
    """
    if api is None:
        api = _build_api_from_server(server)

    verifier: SecurityAuthVerifier | None
    if auth_verifier is not None:
        verifier = auth_verifier
    elif bearer_token is not None:
        verifier = _make_bearer_token_verifier(bearer_token)
    else:
        verifier = None

    if require_auth and verifier is None:
        raise RuntimeError(
            "mount_security_routes requires authentication but no "
            "bearer_token or auth_verifier was supplied. Pass one, or "
            "explicitly set require_auth=False to mount unauthenticated "
            "routes (development only)."
        )

    if not require_auth:
        logger.warning(
            "mount_security_routes(require_auth=False): security HTTP API "
            "is exposed without authentication. Destructive endpoints "
            "(/policy/import, /policy/versions/rollback, "
            "/marketplace/{id}/moderate, /contracts/{id}/sign, ...) are "
            "callable by any HTTP client that can reach the server."
        )

    async def _enforce_auth(request: Request) -> JSONResponse | None:
        if not require_auth:
            return None
        assert verifier is not None  # require_auth=True implies verifier is set
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "Missing 'Authorization: Bearer <token>' header"},
                status_code=401,
            )
        token = header[7:].strip()
        if not token:
            return JSONResponse(
                {"error": "Empty bearer token"},
                status_code=401,
            )
        principal = await _resolve_principal(verifier, request, token)
        if principal is None:
            return JSONResponse(
                {"error": "Invalid or expired token"},
                status_code=401,
            )
        # Stash on request.state for handlers that need to attribute writes.
        request.state.security_principal = principal
        return None

    def _secured_route(path: str, *, methods: list[str]):
        """Wrap the user's route handler with the auth gate."""

        def decorator(handler):
            @functools.wraps(handler)
            async def wrapped(request: Request):
                denial = await _enforce_auth(request)
                if denial is not None:
                    return denial
                return await handler(request)

            return server.custom_route(path, methods=methods)(wrapped)

        return decorator

    # Dashboard
    @_secured_route(f"{prefix}/dashboard", methods=["GET"])
    async def dashboard_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_dashboard())

    # Marketplace
    @_secured_route(f"{prefix}/marketplace", methods=["GET"])
    async def marketplace_endpoint(request: Request) -> JSONResponse:
        query = request.query_params.get("q")
        category = request.query_params.get("category")
        return JSONResponse(api.get_marketplace(query=query, category=category))

    @_secured_route(f"{prefix}/marketplace/{{listing_id}}", methods=["GET"])
    async def marketplace_detail_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        return JSONResponse(api.get_marketplace_listing(lid))

    @_secured_route(
        f"{prefix}/marketplace/{{listing_id}}/install", methods=["POST"]
    )
    async def marketplace_install_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(
            api.marketplace_install(
                lid,
                installer_id=body.get("installer_id", ""),
                version=body.get("version"),
                verify_signature=body.get("verify_signature", False),
            )
        )

    @_secured_route(
        f"{prefix}/marketplace/{{listing_id}}/uninstall", methods=["POST"]
    )
    async def marketplace_uninstall_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(
            api.marketplace_uninstall(lid, installer_id=body.get("installer_id", ""))
        )

    @_secured_route(
        f"{prefix}/marketplace/{{listing_id}}/moderate", methods=["POST"]
    )
    async def marketplace_moderate_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(
            api.marketplace_moderate(
                lid,
                moderator_id=body.get("moderator_id", ""),
                action=body.get("action", ""),
                reason=body.get("reason", ""),
            )
        )

    @_secured_route(f"{prefix}/marketplace/moderation", methods=["GET"])
    async def marketplace_moderation_queue_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.marketplace_moderation_queue())

    @_secured_route(
        f"{prefix}/marketplace/{{listing_id}}/versions", methods=["GET"]
    )
    async def marketplace_versions_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        return JSONResponse(api.marketplace_version_history(lid))

    @_secured_route(
        f"{prefix}/marketplace/{{listing_id}}/versions/{{version}}/yank",
        methods=["POST"],
    )
    async def marketplace_yank_endpoint(request: Request) -> JSONResponse:
        lid = request.path_params.get("listing_id", "")
        ver = request.path_params.get("version", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(
            api.marketplace_yank_version(lid, ver, reason=body.get("reason", ""))
        )

    # Compliance
    @_secured_route(f"{prefix}/compliance", methods=["GET"])
    async def compliance_endpoint(request: Request) -> JSONResponse:
        report_type = request.query_params.get("type", "full")
        return JSONResponse(api.get_compliance_report(report_type=report_type))

    # Trust registry
    @_secured_route(f"{prefix}/trust", methods=["GET"])
    async def trust_registry_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_trust_registry())

    @_secured_route(f"{prefix}/trust/{{tool_name}}", methods=["GET"])
    async def trust_score_endpoint(request: Request) -> JSONResponse:
        name = request.path_params.get("tool_name", "")
        return JSONResponse(api.get_trust_score(name))

    # Federation
    @_secured_route(f"{prefix}/federation", methods=["GET"])
    async def federation_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_federation_status())

    # CRL
    @_secured_route(f"{prefix}/revocations", methods=["GET"])
    async def revocations_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_revocations())

    @_secured_route(f"{prefix}/revocations/{{tool_name}}", methods=["GET"])
    async def revocation_check_endpoint(request: Request) -> JSONResponse:
        name = request.path_params.get("tool_name", "")
        return JSONResponse(api.is_revoked(name))

    # Provenance
    @_secured_route(f"{prefix}/provenance", methods=["GET"])
    async def provenance_endpoint(request: Request) -> JSONResponse:
        resource = request.query_params.get("resource")
        actor = request.query_params.get("actor")
        action = request.query_params.get("action")
        limit = int(request.query_params.get("limit", "50"))
        return JSONResponse(
            api.get_provenance(
                resource_id=resource, actor_id=actor, action=action, limit=limit
            )
        )

    @_secured_route(f"{prefix}/provenance/chain-status", methods=["GET"])
    async def provenance_chain_status_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_provenance_chain_status())

    @_secured_route(f"{prefix}/provenance/actions", methods=["GET"])
    async def provenance_actions_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_provenance_actions())

    @_secured_route(
        f"{prefix}/provenance/proof/{{record_id}}", methods=["GET"]
    )
    async def provenance_proof_endpoint(request: Request) -> JSONResponse:
        record_id = request.path_params.get("record_id", "")
        return JSONResponse(api.get_provenance_proof(record_id))

    @_secured_route(f"{prefix}/provenance/export", methods=["GET"])
    async def provenance_export_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_provenance_export())

    @_secured_route(f"{prefix}/provenance/verify", methods=["POST"])
    async def provenance_verify_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(api.verify_provenance_bundle(body))

    mount_policy_routes(server, api, prefix, route_decorator=_secured_route)

    # Health
    # Contracts
    @_secured_route(f"{prefix}/contracts/negotiate", methods=["POST"])
    async def contracts_negotiate_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(await api.negotiate_contract(body))

    @_secured_route(
        f"{prefix}/contracts/{{contract_id}}/sign", methods=["POST"]
    )
    async def contracts_sign_endpoint(request: Request) -> JSONResponse:
        cid = request.path_params.get("contract_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(await api.agent_sign_contract_endpoint(cid, body))

    @_secured_route(f"{prefix}/contracts/{{contract_id}}", methods=["GET"])
    async def contracts_detail_endpoint(request: Request) -> JSONResponse:
        cid = request.path_params.get("contract_id", "")
        return JSONResponse(api.get_contract_details(cid))

    @_secured_route(f"{prefix}/contracts", methods=["GET"])
    async def contracts_list_endpoint(request: Request) -> JSONResponse:
        agent_id = request.query_params.get("agent_id", "")
        return JSONResponse(api.list_agent_contracts(agent_id))

    @_secured_route(
        f"{prefix}/contracts/{{contract_id}}/revoke", methods=["POST"]
    )
    async def contracts_revoke_endpoint(request: Request) -> JSONResponse:
        cid = request.path_params.get("contract_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        return JSONResponse(
            await api.revoke_contract_endpoint(cid, reason=body.get("reason", ""))
        )

    @_secured_route(f"{prefix}/contracts/exchange-log", methods=["GET"])
    async def contracts_exchange_log_endpoint(request: Request) -> JSONResponse:
        session_id = request.query_params.get("session_id")
        return JSONResponse(api.get_exchange_log_entries(session_id=session_id))

    @_secured_route(
        f"{prefix}/contracts/exchange-log/{{session_id}}/verify",
        methods=["GET"],
    )
    async def contracts_verify_chain_endpoint(request: Request) -> JSONResponse:
        sid = request.path_params.get("session_id", "")
        return JSONResponse(api.verify_exchange_chain(sid))

    # Federated Consent
    @_secured_route(
        f"{prefix}/consent/federated/evaluate", methods=["POST"]
    )
    async def federated_consent_evaluate(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            api.evaluate_federated_consent(
                source_id=body.get("source_id", ""),
                target_id=body.get("target_id", ""),
                scope=body.get("scope", ""),
                geographic_context=body.get("geographic_context"),
                jurisdictions=body.get("jurisdictions"),
                require_all_jurisdictions=body.get(
                    "require_all_jurisdictions", True
                ),
            )
        )

    @_secured_route(
        f"{prefix}/consent/federated/access-rights/{{agent_id}}/{{resource_id}}",
        methods=["GET"],
    )
    async def federated_access_rights(request: Request) -> JSONResponse:
        agent_id = request.path_params.get("agent_id", "")
        resource_id = request.path_params.get("resource_id", "")
        geo_param = request.query_params.get("geographic_context")
        geo: dict[str, Any] | None = None
        if geo_param:
            import json as _json

            try:
                geo = _json.loads(geo_param)
            except Exception:
                geo = None
        return JSONResponse(
            api.get_access_rights(
                agent_id, resource_id, geographic_context=geo
            )
        )

    @_secured_route(
        f"{prefix}/consent/federated/propagate", methods=["POST"]
    )
    async def federated_consent_propagate(request: Request) -> JSONResponse:
        body = await request.json()
        return JSONResponse(
            api.propagate_consent_endpoint(
                edge_id=body.get("edge_id", ""),
                target_peers=body.get("target_peers"),
            )
        )

    @_secured_route(
        f"{prefix}/consent/federated/jurisdictions", methods=["GET"]
    )
    async def federated_jurisdictions(request: Request) -> JSONResponse:
        return JSONResponse(api.list_jurisdictions())

    @_secured_route(
        f"{prefix}/consent/federated/institutions", methods=["GET"]
    )
    async def federated_institutions(request: Request) -> JSONResponse:
        return JSONResponse(api.list_institutions())

    # Reflexive Introspection
    @_secured_route(
        f"{prefix}/reflexive/introspect/{{actor_id}}", methods=["GET"]
    )
    async def reflexive_introspect(request: Request) -> JSONResponse:
        actor_id = request.path_params.get("actor_id", "")
        return JSONResponse(api.get_introspection(actor_id))

    @_secured_route(
        f"{prefix}/reflexive/verdict/{{actor_id}}/{{operation}}", methods=["GET"]
    )
    async def reflexive_verdict(request: Request) -> JSONResponse:
        actor_id = request.path_params.get("actor_id", "")
        operation = request.path_params.get("operation", "")
        return JSONResponse(api.get_verdict(actor_id, operation))

    @_secured_route(
        f"{prefix}/reflexive/threat-level/{{actor_id}}", methods=["GET"]
    )
    async def reflexive_threat_level(request: Request) -> JSONResponse:
        actor_id = request.path_params.get("actor_id", "")
        return JSONResponse(api.get_actor_threat_level(actor_id))

    @_secured_route(
        f"{prefix}/reflexive/constraints/{{actor_id}}", methods=["GET"]
    )
    async def reflexive_constraints(request: Request) -> JSONResponse:
        actor_id = request.path_params.get("actor_id", "")
        return JSONResponse(api.get_actor_constraints(actor_id))

    @_secured_route(
        f"{prefix}/reflexive/accountability", methods=["GET"]
    )
    async def reflexive_accountability(request: Request) -> JSONResponse:
        actor_id = request.query_params.get("actor_id")
        limit = int(request.query_params.get("limit", "100"))
        return JSONResponse(api.get_accountability(actor_id=actor_id, limit=limit))

    # Health
    @_secured_route(f"{prefix}/health", methods=["GET"])
    async def health_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_health())

    logger.info("SecureMCP HTTP routes mounted at %s/*", prefix)
    return api


def _build_api_from_server(server: FastMCP) -> SecurityAPI:
    """Auto-construct a SecurityAPI from a FastMCP server's security context."""
    ctx = get_security_context(server)
    if ctx is None:
        logger.warning("No security context found on server; API will be empty")
        return SecurityAPI()

    # The SecurityContext has real fields for all components.
    # Use ctx.dashboard (auto-created by bootstrap) or build one.
    dashboard = getattr(ctx, "dashboard", None)

    return SecurityAPI(
        dashboard=dashboard,
        marketplace=getattr(ctx, "tool_marketplace", None),
        registry=getattr(ctx, "registry", None),
        compliance_reporter=getattr(ctx, "compliance_reporter", None),
        provenance_ledger=getattr(ctx, "provenance_ledger", None),
        federation=getattr(ctx, "federation", None),
        crl=getattr(ctx, "crl", None),
        event_bus=getattr(ctx, "event_bus", None),
        policy_engine=getattr(ctx, "policy_engine", None),
        policy_audit_log=getattr(ctx, "policy_audit_log", None),
        policy_version_manager=getattr(ctx, "policy_version_manager", None),
        policy_validator=getattr(ctx, "policy_validator", None),
        policy_monitor=getattr(ctx, "policy_monitor", None),
        policy_governor=getattr(ctx, "policy_governor", None),
        introspection_engine=getattr(ctx, "introspection_engine", None),
    )
