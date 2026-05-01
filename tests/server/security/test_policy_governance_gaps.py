"""Tests for policy governance gap closures.

Covers: PolicyValidator, PolicyGovernor, PolicyMonitor, constraint enforcement,
invariant wiring, and full orchestrator integration.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.governance import (
    PolicyGovernor,
    ProposalAction,
    ProposalStatus,
)
from fastmcp.server.security.policy.invariants import (
    Invariant,
    InvariantRegistry,
    InvariantSeverity,
)
from fastmcp.server.security.policy.monitoring import AlertLevel, PolicyMonitor
from fastmcp.server.security.policy.policies.allowlist import (
    AllowlistPolicy,
    DenylistPolicy,
)
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
    DenyAllPolicy,
    PolicyEvaluationContext,
)
from fastmcp.server.security.policy.simulation import Scenario
from fastmcp.server.security.policy.validator import (
    PolicyValidator,
)
from fastmcp.server.security.policy.versioning.manager import PolicyVersionManager
from fastmcp.server.security.storage.memory import MemoryBackend

# ── PolicyValidator Tests ─────────────────────────────────────


class TestValidatorSchemaValidation:
    """Tests for declarative policy schema validation."""

    def test_valid_allowlist(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "allowlist",
                "allowed": ["tool-a", "tool-b"],
            }
        )
        assert result.valid

    def test_valid_composite(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "composition": "all_of",
                "policies": [
                    {"type": "allowlist", "allowed": ["tool-*"]},
                    {"type": "denylist", "denied": ["admin-*"]},
                ],
            }
        )
        assert result.valid

    def test_missing_type(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"allowed": ["tool-a"]})
        assert not result.valid
        assert any(f.code == "E_MISSING_TYPE" for f in result.errors)

    def test_unknown_type(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "banana"})
        assert not result.valid
        assert any(f.code == "E_UNKNOWN_TYPE" for f in result.errors)

    def test_missing_required_field(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "allowlist"})
        assert not result.valid
        assert any(f.code == "E_MISSING_FIELD" for f in result.errors)

    def test_empty_allowlist_warning(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "allowlist", "allowed": []})
        assert result.valid  # Warning, not error
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "W_EMPTY_ALLOWLIST"

    def test_invalid_allowed_type(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "allowlist", "allowed": "not-a-list"})
        assert not result.valid

    def test_unknown_composition(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "composition": "banana_of",
                "policies": [],
            }
        )
        assert not result.valid
        assert any(f.code == "E_UNKNOWN_COMPOSITION" for f in result.errors)

    def test_not_requires_single_child(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "composition": "not",
                "policies": [
                    {"type": "allowlist", "allowed": ["a"]},
                    {"type": "allowlist", "allowed": ["b"]},
                ],
            }
        )
        assert not result.valid
        assert any(f.code == "E_NOT_SINGLE_CHILD" for f in result.errors)

    def test_depth_limit(self) -> None:
        v = PolicyValidator(max_composition_depth=2)
        deep = {
            "composition": "all_of",
            "policies": [
                {
                    "composition": "all_of",
                    "policies": [
                        {
                            "composition": "all_of",
                            "policies": [{"type": "allow_all"}],
                        }
                    ],
                }
            ],
        }
        result = v.validate_declarative(deep)
        assert not result.valid
        assert any(f.code == "E_DEPTH_EXCEEDED" for f in result.errors)

    def test_rate_limit_validation(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "rate_limit",
                "max_requests": -1,
            }
        )
        assert not result.valid

    def test_time_based_invalid_day(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "time_based",
                "allowed_days": [0, 7],  # 7 is invalid
            }
        )
        assert not result.valid

    def test_time_based_invalid_hour(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "time_based",
                "start_hour": 25,
            }
        )
        assert not result.valid

    def test_rbac_invalid_mappings_type(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "rbac",
                "role_mappings": "not-a-dict",
            }
        )
        assert not result.valid

    def test_rbac_invalid_decision(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative(
            {
                "type": "rbac",
                "role_mappings": {"admin": ["*"]},
                "default_decision": "banana",
            }
        )
        assert not result.valid

    def test_valid_allow_all(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "allow_all"})
        assert result.valid

    def test_to_dict(self) -> None:
        v = PolicyValidator()
        result = v.validate_declarative({"type": "banana"})
        d = result.to_dict()
        assert d["valid"] is False
        assert d["error_count"] >= 1
        assert len(d["findings"]) >= 1


class TestValidatorSemanticValidation:
    """Tests for semantic validation of provider lists."""

    def test_contradicting_patterns(self) -> None:
        v = PolicyValidator()
        result = v.validate_providers(
            [
                AllowlistPolicy(allowed={"tool-a", "tool-b"}),
                DenylistPolicy(denied={"tool-a", "tool-c"}),
            ]
        )
        assert not result.valid
        assert any(f.code == "E_CONTRADICTING_RULES" for f in result.errors)

    def test_allow_all_plus_deny_all(self) -> None:
        v = PolicyValidator()
        result = v.validate_providers([AllowAllPolicy(), DenyAllPolicy()])
        assert not result.valid
        assert any(f.code == "E_ALLOW_DENY_ALL" for f in result.errors)

    def test_deny_all_shadows_others(self) -> None:
        v = PolicyValidator()
        result = v.validate_providers(
            [
                AllowlistPolicy(allowed={"tool-a"}),
                DenyAllPolicy(),
            ]
        )
        assert any(f.code == "W_DENY_ALL_SHADOWS" for f in result.warnings)

    def test_too_many_providers(self) -> None:
        v = PolicyValidator(max_providers=2)
        providers = [AllowAllPolicy() for _ in range(5)]
        result = v.validate_providers(providers)
        assert any(f.code == "W_TOO_MANY_PROVIDERS" for f in result.warnings)

    def test_no_issues(self) -> None:
        v = PolicyValidator()
        result = v.validate_providers(
            [
                AllowlistPolicy(allowed={"tool-a"}),
                DenylistPolicy(denied={"admin-*"}),
            ]
        )
        assert result.valid

    def test_validate_full(self) -> None:
        v = PolicyValidator()
        result = v.validate_full(
            config={"type": "banana"},
            providers=[AllowAllPolicy(), DenyAllPolicy()],
        )
        assert not result.valid
        # Should have errors from both schema and semantic
        assert len(result.errors) >= 2


# ── PolicyGovernor Tests ──────────────────────────────────────


class TestGovernorWorkflow:
    """Tests for the policy governance workflow."""

    @staticmethod
    def _make_versioned_engine() -> PolicyEngine:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        engine.attach_version_manager(
            PolicyVersionManager(
                policy_set_id="test-governance",
                backend=MemoryBackend(),
            )
        )
        return engine

    def test_propose_add(self) -> None:
        engine = self._make_versioned_engine()
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
            author="test-user",
            description="Add allowlist",
        )
        assert proposal.status == ProposalStatus.DRAFT
        assert proposal.action == ProposalAction.ADD
        assert proposal.author == "test-user"
        assert proposal.base_version_number == 1

    def test_propose_swap(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_swap(
            0,
            AllowlistPolicy(allowed={"tool-a"}),
            author="test-user",
        )
        assert proposal.action == ProposalAction.SWAP
        assert proposal.target_index == 0

    def test_propose_swap_invalid_index(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine)
        with pytest.raises(IndexError):
            gov.propose_swap(5, AllowAllPolicy())

    def test_propose_remove(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy(), DenyAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_remove(1, author="test-user")
        assert proposal.action == ProposalAction.REMOVE

    def test_propose_replace_chain(self) -> None:
        engine = self._make_versioned_engine()
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_replace_chain(
            [
                DenylistPolicy(denied={"admin-*"}),
                AllowlistPolicy(allowed={"tool:*"}),
            ],
            author="test-user",
            description="Import a reviewed chain",
        )
        assert proposal.action == ProposalAction.REPLACE_CHAIN
        assert proposal.replacement_providers is not None
        assert len(proposal.replacement_providers) == 2

    def test_validate_catches_errors(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(DenyAllPolicy())
        result = gov.validate_proposal(proposal.proposal_id)
        # AllowAll + DenyAll should flag contradiction
        assert not result.valid
        assert proposal.status == ProposalStatus.VALIDATION_FAILED

    def test_validate_passes(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
        )
        result = gov.validate_proposal(proposal.proposal_id)
        assert result.valid
        assert proposal.status == ProposalStatus.VALIDATED

    @pytest.mark.anyio
    async def test_simulate_proposal(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
        )
        gov.validate_proposal(proposal.proposal_id)

        scenarios = [
            Scenario(resource_id="tool-a"),
            Scenario(resource_id="tool-b"),
        ]
        report = await gov.simulate_proposal(proposal.proposal_id, scenarios)
        assert report.total == 2
        assert proposal.status == ProposalStatus.SIMULATED

    def test_approve_after_validation(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
        )
        gov.validate_proposal(proposal.proposal_id)
        gov.approve(proposal.proposal_id, approver="ciso")
        assert proposal.status == ProposalStatus.APPROVED
        assert proposal.approved_by == "ciso"

    def test_approve_requires_simulation_when_enabled(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=True)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
        )
        gov.validate_proposal(proposal.proposal_id)
        with pytest.raises(ValueError, match="Simulation is required"):
            gov.approve(proposal.proposal_id)

    def test_reject(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(AllowlistPolicy(allowed={"x"}))
        gov.reject(proposal.proposal_id, reason="Not needed")
        assert proposal.status == ProposalStatus.REJECTED

    def test_withdraw(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine)
        proposal = gov.propose_add(AllowlistPolicy(allowed={"x"}))
        gov.withdraw(proposal.proposal_id)
        assert proposal.status == ProposalStatus.WITHDRAWN

    @pytest.mark.anyio
    async def test_deploy_add(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_add(
            AllowlistPolicy(allowed={"tool-a"}),
        )
        gov.validate_proposal(proposal.proposal_id)
        gov.approve(proposal.proposal_id)
        await gov.deploy(proposal.proposal_id)
        assert proposal.status == ProposalStatus.DEPLOYED
        assert len(engine.providers) == 2

    @pytest.mark.anyio
    async def test_deploy_swap(self) -> None:
        old_policy = AllowAllPolicy()
        engine = PolicyEngine(providers=[old_policy])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        new_policy = AllowlistPolicy(allowed={"tool-a"})
        proposal = gov.propose_swap(0, new_policy)
        gov.validate_proposal(proposal.proposal_id)
        gov.approve(proposal.proposal_id)
        await gov.deploy(proposal.proposal_id)
        assert proposal.status == ProposalStatus.DEPLOYED
        assert engine.providers[0] is new_policy

    @pytest.mark.anyio
    async def test_deploy_remove(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy(), DenyAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        proposal = gov.propose_remove(1)
        gov.validate_proposal(proposal.proposal_id)
        gov.approve(proposal.proposal_id)
        await gov.deploy(proposal.proposal_id)
        assert len(engine.providers) == 1

    @pytest.mark.anyio
    async def test_deploy_requires_approval(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(
            engine=engine, require_approval=True, require_simulation=False
        )
        proposal = gov.propose_add(AllowlistPolicy(allowed={"x"}))
        gov.validate_proposal(proposal.proposal_id)
        with pytest.raises(ValueError, match="Must be approved"):
            await gov.deploy(proposal.proposal_id)

    def test_proposals_listing(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        gov.propose_add(AllowlistPolicy(allowed={"a"}))
        gov.propose_add(AllowlistPolicy(allowed={"b"}))
        assert len(gov.proposals) == 2

    def test_pending_proposals(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine, require_simulation=False)
        p1 = gov.propose_add(AllowlistPolicy(allowed={"a"}))
        p2 = gov.propose_add(AllowlistPolicy(allowed={"b"}))
        gov.reject(p1.proposal_id, reason="no")
        assert len(gov.pending_proposals) == 1
        assert gov.pending_proposals[0].proposal_id == p2.proposal_id

    def test_proposal_to_dict(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine)
        proposal = gov.propose_add(AllowlistPolicy(allowed={"a"}), author="me")
        d = proposal.to_dict()
        assert d["status"] == "draft"
        assert d["author"] == "me"

    def test_get_unknown_proposal(self) -> None:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        gov = PolicyGovernor(engine=engine)
        with pytest.raises(KeyError):
            gov.validate_proposal("nonexistent")

    @pytest.mark.anyio
    async def test_stale_proposal_cannot_be_approved(self) -> None:
        engine = self._make_versioned_engine()
        gov = PolicyGovernor(engine=engine, require_simulation=False)

        stale = gov.propose_add(AllowlistPolicy(allowed={"tool-a"}))
        gov.validate_proposal(stale.proposal_id)

        live = gov.propose_add(DenylistPolicy(denied={"admin-*"}))
        gov.validate_proposal(live.proposal_id)
        gov.approve(live.proposal_id)
        await gov.deploy(live.proposal_id)

        with pytest.raises(ValueError, match="based on policy version 1"):
            gov.approve(stale.proposal_id)


# ── PolicyMonitor Tests ───────────────────────────────────────


class TestMonitoring:
    """Tests for the policy monitoring system."""

    def test_record_and_metrics(self) -> None:
        monitor = PolicyMonitor()
        for _ in range(10):
            monitor.record_decision(decision="allow", resource_id="tool-a")
        for _ in range(5):
            monitor.record_decision(decision="deny", resource_id="tool-b")

        metrics = monitor.get_metrics()
        assert metrics["window"]["total"] == 15
        assert metrics["window"]["denied"] == 5
        assert metrics["window"]["allowed"] == 10
        assert metrics["lifetime"]["total_decisions"] == 15

    def test_deny_rate_warning(self) -> None:
        monitor = PolicyMonitor(deny_rate_warning=0.3, deny_rate_critical=0.6)
        # 4 denials out of 10 = 40% > 30% warning threshold
        for _ in range(6):
            monitor.record_decision(decision="allow", resource_id="x")
        for _ in range(4):
            monitor.record_decision(decision="deny", resource_id="x")

        alerts = monitor.check_anomalies()
        assert len(alerts) >= 1
        assert any(a.level == AlertLevel.WARNING for a in alerts)

    def test_deny_rate_critical(self) -> None:
        monitor = PolicyMonitor(deny_rate_warning=0.3, deny_rate_critical=0.6)
        # 7 denials out of 10 = 70% > 60% critical threshold
        for _ in range(3):
            monitor.record_decision(decision="allow", resource_id="x")
        for _ in range(7):
            monitor.record_decision(decision="deny", resource_id="x")

        alerts = monitor.check_anomalies()
        assert any(a.level == AlertLevel.CRITICAL for a in alerts)

    def test_burst_detection(self) -> None:
        monitor = PolicyMonitor(burst_threshold=5)
        for _ in range(10):
            monitor.record_decision(decision="deny", resource_id="x")

        alerts = monitor.check_anomalies()
        assert any(a.metric == "deny_burst" for a in alerts)

    def test_resource_concentration(self) -> None:
        monitor = PolicyMonitor(burst_threshold=10)
        for _ in range(6):
            monitor.record_decision(decision="deny", resource_id="admin-panel")
        for _ in range(10):
            monitor.record_decision(decision="allow", resource_id="tool-a")

        alerts = monitor.check_anomalies()
        assert any(a.metric == "resource_deny_burst" for a in alerts)

    def test_no_alerts_normal_operation(self) -> None:
        monitor = PolicyMonitor()
        for _ in range(100):
            monitor.record_decision(decision="allow", resource_id="x")

        alerts = monitor.check_anomalies()
        assert len(alerts) == 0

    def test_alert_cooldown(self) -> None:
        monitor = PolicyMonitor(deny_rate_warning=0.1)
        for _ in range(5):
            monitor.record_decision(decision="deny", resource_id="x")

        alerts1 = monitor.check_anomalies()
        alerts2 = monitor.check_anomalies()  # Should be empty due to cooldown
        assert len(alerts1) >= 1
        assert len(alerts2) == 0

    def test_recent_alerts(self) -> None:
        monitor = PolicyMonitor(deny_rate_warning=0.1)
        for _ in range(5):
            monitor.record_decision(decision="deny", resource_id="x")
        monitor.check_anomalies()

        recent = monitor.get_recent_alerts()
        assert len(recent) >= 1
        assert "level" in recent[0]

    def test_empty_window(self) -> None:
        monitor = PolicyMonitor()
        alerts = monitor.check_anomalies()
        assert len(alerts) == 0

    def test_top_denied_resources(self) -> None:
        monitor = PolicyMonitor()
        for i in range(5):
            monitor.record_decision(decision="deny", resource_id=f"tool-{i}")
        for _ in range(3):
            monitor.record_decision(decision="deny", resource_id="tool-0")

        metrics = monitor.get_metrics()
        top = metrics["window"]["top_denied_resources"]
        assert len(top) > 0
        assert top[0]["resource_id"] == "tool-0"

    def test_event_bus_integration(self) -> None:
        bus = MagicMock()
        monitor = PolicyMonitor(event_bus=bus, deny_rate_warning=0.1)
        for _ in range(5):
            monitor.record_decision(decision="deny", resource_id="x")
        monitor.check_anomalies()
        assert bus.emit.called


# ── Invariant Wiring Tests ────────────────────────────────────


class TestInvariantWiring:
    """Tests for invariant verification wired into engine."""

    @pytest.mark.anyio
    async def test_engine_accepts_invariant_registry(self) -> None:
        registry = InvariantRegistry()
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        engine._invariant_registry = registry
        assert engine.invariant_registry is registry

    @pytest.mark.anyio
    async def test_invariant_checked_on_hot_swap(self) -> None:
        registry = InvariantRegistry()
        registry.register(
            Invariant(
                id="min-providers",
                description="Must have at least 1 provider",
                expression="provider_count >= 1",
                severity=InvariantSeverity.CRITICAL,
            )
        )

        engine = PolicyEngine(providers=[AllowAllPolicy()])
        engine._invariant_registry = registry

        new_policy = AllowlistPolicy(allowed={"tool-a"})
        await engine.hot_swap(0, new_policy, reason="test")

        # Give the fire-and-forget task a moment to complete
        await asyncio.sleep(0.1)

        results = registry.recent_results
        assert len(results) >= 1
        assert results[0].satisfied is True

    @pytest.mark.anyio
    async def test_invariant_failure_doesnt_block_swap(self) -> None:
        registry = InvariantRegistry()
        registry.register(
            Invariant(
                id="always-fail",
                description="Always fails",
                expression="False",
            )
        )

        engine = PolicyEngine(providers=[AllowAllPolicy()])
        engine._invariant_registry = registry

        new_policy = AllowlistPolicy(allowed={"tool-a"})
        # Should not raise even though invariant fails
        await engine.hot_swap(0, new_policy, reason="test")
        assert engine.providers[0] is new_policy


# ── Monitor Wiring in Engine ──────────────────────────────────


class TestMonitorWiringInEngine:
    """Tests for monitor wired into PolicyEngine evaluation."""

    @pytest.mark.anyio
    async def test_engine_feeds_monitor(self) -> None:
        monitor = PolicyMonitor()
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        engine._monitor = monitor

        ctx = PolicyEvaluationContext(
            actor_id="test",
            action="call_tool",
            resource_id="tool-a",
        )
        await engine.evaluate(ctx)

        metrics = monitor.get_metrics()
        assert metrics["lifetime"]["total_decisions"] == 1

    @pytest.mark.anyio
    async def test_engine_feeds_monitor_on_deny(self) -> None:
        monitor = PolicyMonitor()
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        engine._monitor = monitor

        ctx = PolicyEvaluationContext(
            actor_id="test",
            action="call_tool",
            resource_id="admin",
        )
        await engine.evaluate(ctx)

        metrics = monitor.get_metrics()
        assert metrics["lifetime"]["total_denials"] == 1


# ── Constraint Enforcement Tests ──────────────────────────────


class TestConstraintEnforcement:
    """Tests for constraint enforcement in the middleware."""

    def test_max_args_constraint_import(self) -> None:
        """Verify the enforcement middleware imports cleanly."""
        from fastmcp.server.security.middleware.policy_enforcement import (
            PolicyEnforcementMiddleware,
        )

        assert PolicyEnforcementMiddleware is not None


# ── Orchestrator Integration Tests ────────────────────────────


class TestOrchestratorGovernanceWiring:
    """Tests for governance components wired through orchestrator."""

    def test_validator_wired(self) -> None:
        from fastmcp.server.security.config import PolicyConfig, SecurityConfig
        from fastmcp.server.security.orchestrator import SecurityOrchestrator

        config = SecurityConfig(
            policy=PolicyConfig(
                enable_validation=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_validator is not None
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.validator is not None

    def test_monitor_wired(self) -> None:
        from fastmcp.server.security.config import PolicyConfig, SecurityConfig
        from fastmcp.server.security.orchestrator import SecurityOrchestrator

        config = SecurityConfig(
            policy=PolicyConfig(
                enable_monitoring=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_monitor is not None
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.monitor is not None

    def test_governor_wired(self) -> None:
        from fastmcp.server.security.config import PolicyConfig, SecurityConfig
        from fastmcp.server.security.orchestrator import SecurityOrchestrator

        config = SecurityConfig(
            policy=PolicyConfig(
                enable_governance=True,
                enable_validation=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_governor is not None

    def test_invariant_registry_wired(self) -> None:
        from fastmcp.server.security.config import PolicyConfig, SecurityConfig
        from fastmcp.server.security.orchestrator import SecurityOrchestrator

        registry = InvariantRegistry()
        config = SecurityConfig(
            policy=PolicyConfig(
                invariant_registry=registry,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.invariant_registry is registry

    def test_disabled_features_not_wired(self) -> None:
        from fastmcp.server.security.config import PolicyConfig, SecurityConfig
        from fastmcp.server.security.orchestrator import SecurityOrchestrator

        config = SecurityConfig(
            policy=PolicyConfig(
                enable_validation=False,
                enable_monitoring=False,
                enable_governance=False,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_validator is None
        assert ctx.policy_monitor is None
        assert ctx.policy_governor is None


# ── SecurityAPI Integration Tests ─────────────────────────────


class TestSecurityAPIGovernance:
    """Tests for new governance/monitoring/validation API endpoints."""

    def _make_api(self, *, validator=True, monitor=True, governor=True):
        from fastmcp.server.security.http.api import SecurityAPI

        engine = PolicyEngine(providers=[AllowAllPolicy()])
        version_manager = PolicyVersionManager(
            policy_set_id="test-policy-api",
            backend=MemoryBackend(),
        )
        engine.attach_version_manager(version_manager)
        api = SecurityAPI(policy_engine=engine)
        api.policy_version_manager = version_manager

        if validator:
            api.policy_validator = PolicyValidator()
        if monitor:
            api.policy_monitor = PolicyMonitor()
        if governor:
            gov = PolicyGovernor(engine=engine, require_simulation=False)
            api.policy_governor = gov

        return api

    def test_export_policy_snapshot(self) -> None:
        api = self._make_api()

        exported = api.export_policy_snapshot()

        assert exported["status"] == "exported"
        assert exported["kind"] == "live"
        assert exported["snapshot"]["format"] == "securemcp-policy-set/v1"
        assert len(exported["snapshot"]["providers"]) == 1

        version_export = api.export_policy_snapshot(version_number=1)
        assert version_export["status"] == "exported"
        assert version_export["kind"] == "version"
        assert version_export["version_number"] == 1
        assert (
            version_export["snapshot"]["providers"] == exported["snapshot"]["providers"]
        )

    def test_get_policy_bundles(self) -> None:
        api = self._make_api()

        bundles = api.get_policy_bundles()

        assert bundles["count"] >= 1
        assert bundles["bundles"][0]["provider_count"] >= 1

    def test_compliance_bundles_are_registered(self) -> None:
        api = self._make_api()
        bundles = api.get_policy_bundles()
        bundle_ids = {b["bundle_id"] for b in bundles["bundles"]}

        assert "gdpr-data-protection" in bundle_ids
        assert "hipaa-health-data" in bundle_ids
        assert "soc2-trust-services" in bundle_ids
        assert "zero-trust-lockdown" in bundle_ids
        assert "pci-dss-cardholder-data" in bundle_ids
        assert "ccpa-consumer-privacy" in bundle_ids
        assert "ferpa-student-records" in bundle_ids

    def test_gdpr_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("gdpr-data-protection")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "compliance" in bundle["tags"]
        assert "gdpr" in bundle["tags"]
        assert bundle["provider_count"] == 4

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "compliance_rule" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "rate_limit" in provider_types

        core = bundle["providers"][0]
        assert core["type"] == "compliance_rule"
        assert core["framework"] == "GDPR"
        assert len(core["rules"]) >= 1
        assert core["rules"][0]["name"] == "legal_basis_required"

    def test_hipaa_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("hipaa-health-data")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "hipaa" in bundle["tags"]
        assert bundle["provider_count"] == 5

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "compliance_rule" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "time_based" in provider_types
        assert "rate_limit" in provider_types

        core = bundle["providers"][0]
        assert core["type"] == "compliance_rule"
        assert core["framework"] == "HIPAA"
        assert len(core["rules"]) >= 1
        assert core["rules"][0]["name"] == "authorized_role_required"

    def test_soc2_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("soc2-trust-services")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "soc2" in bundle["tags"]
        assert bundle["provider_count"] == 5

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "allowlist" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "time_based" in provider_types
        assert "rate_limit" in provider_types

    def test_zero_trust_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("zero-trust-lockdown")
        assert bundle is not None
        assert bundle["risk_posture"] == "locked_down"
        assert "zero-trust" in bundle["tags"]
        assert bundle["provider_count"] == 5

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "resource_scoped" in provider_types
        assert "rbac" in provider_types
        assert "abac" in provider_types
        assert "denylist" in provider_types
        assert "rate_limit" in provider_types

    def test_pci_dss_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("pci-dss-cardholder-data")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "pci-dss" in bundle["tags"]
        assert bundle["provider_count"] == 5

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "compliance_rule" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "time_based" in provider_types
        assert "rate_limit" in provider_types

        core = bundle["providers"][0]
        assert core["type"] == "compliance_rule"
        assert core["framework"] == "PCI DSS"
        assert len(core["rules"]) >= 1
        assert core["rules"][0]["name"] == "cardholder_data_protection"

    def test_ccpa_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("ccpa-consumer-privacy")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "ccpa" in bundle["tags"]
        assert bundle["provider_count"] == 4

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "compliance_rule" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "rate_limit" in provider_types

        core = bundle["providers"][0]
        assert core["type"] == "compliance_rule"
        assert core["framework"] == "CCPA/CPRA"
        assert len(core["rules"]) == 2
        assert core["rules"][0]["name"] == "processing_purpose_required"
        assert core["rules"][1]["name"] == "opt_out_check"

    def test_ferpa_bundle_structure(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("ferpa-student-records")
        assert bundle is not None
        assert bundle["risk_posture"] == "strict"
        assert "ferpa" in bundle["tags"]
        assert bundle["provider_count"] == 4

        provider_types = [p.get("type") for p in bundle["providers"]]
        assert "compliance_rule" in provider_types
        assert "rbac" in provider_types
        assert "denylist" in provider_types
        assert "rate_limit" in provider_types

        core = bundle["providers"][0]
        assert core["type"] == "compliance_rule"
        assert core["framework"] == "FERPA"
        assert len(core["rules"]) == 2
        assert core["rules"][0]["name"] == "educational_interest_required"
        assert core["rules"][1]["name"] == "directory_information_exception"
        assert core.get("require_all_rules") is False

    def test_all_bundles_have_required_fields(self) -> None:
        from fastmcp.server.security.policy.workbench import list_policy_bundles

        required_fields = {
            "bundle_id",
            "title",
            "summary",
            "description",
            "risk_posture",
            "recommended_environments",
            "tags",
            "provider_count",
            "providers",
            "provider_summaries",
        }
        for bundle in list_policy_bundles():
            missing = required_fields - set(bundle.keys())
            assert not missing, (
                f"Bundle {bundle['bundle_id']} missing fields: {missing}"
            )
            assert bundle["provider_count"] >= 1
            assert len(bundle["providers"]) == bundle["provider_count"]
            assert len(bundle["provider_summaries"]) == bundle["provider_count"]

    def test_compliance_bundles_recommend_staging_or_production(self) -> None:
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        for bundle_id in (
            "gdpr-data-protection",
            "hipaa-health-data",
            "soc2-trust-services",
            "pci-dss-cardholder-data",
            "ccpa-consumer-privacy",
            "ferpa-student-records",
        ):
            bundle = get_policy_bundle(bundle_id)
            assert bundle is not None
            envs = set(bundle["recommended_environments"])
            assert envs & {"staging", "production"}, (
                f"{bundle_id} should recommend staging or production"
            )

    def test_total_bundle_count(self) -> None:
        from fastmcp.server.security.policy.workbench import list_policy_bundles

        bundles = list_policy_bundles()
        assert len(bundles) == 10

    @pytest.mark.anyio
    async def test_save_stage_and_delete_private_policy_pack(self) -> None:
        api = self._make_api()

        saved = await api.save_policy_pack(
            title="Team baseline",
            summary="Reusable private pack",
            description="Keep a private baseline for reviewers.",
            source_version_number=1,
            author="reviewer",
            recommended_environments=["development", "staging"],
            tags=["private", "baseline"],
        )

        assert saved["status"] == "saved"
        pack = saved["pack"]
        pack_id = pack["pack_id"]
        assert pack["visibility"] == "private"
        assert pack["revision_count"] == 1

        packs = api.get_policy_packs()
        assert packs["count"] == 1
        assert packs["packs"][0]["pack_id"] == pack_id

        staged = await api.stage_policy_pack(
            pack_id,
            author="reviewer",
            description="Roll out the saved private pack",
        )
        assert staged["status"] == "no_changes"
        assert staged["pack"]["pack_id"] == pack_id

        deleted = api.delete_policy_pack(pack_id)
        assert deleted["status"] == "deleted"
        assert api.get_policy_packs()["count"] == 0

    def test_get_policy_environment_profiles(self) -> None:
        api = self._make_api()

        environments = api.get_policy_environment_profiles()

        assert environments["count"] >= 1
        assert {item["environment_id"] for item in environments["environments"]} >= {
            "development",
            "staging",
            "production",
        }

    def test_get_policy_analytics(self) -> None:
        api = self._make_api()

        analytics = api.get_policy_analytics()

        assert analytics["overview"]["provider_count"] == 1
        assert "blocked" in analytics
        assert "risks" in analytics
        assert analytics["history"]["sample_count"] >= 1

    @pytest.mark.anyio
    async def test_policy_analytics_history_tracks_state_changes(self) -> None:
        api = self._make_api()

        first = api.get_policy_analytics()
        assert first["history"]["sample_count"] >= 1

        created = await api.create_governance_proposal(
            action="add",
            config={"type": "denylist", "denied": ["admin-*"]},
            target_index=None,
            description="Track pending proposal history",
            author="reviewer",
        )
        assert created["status"] == "created"

        second = api.get_policy_analytics()
        assert second["history"]["sample_count"] >= 2
        assert second["history"]["deltas"]["pending_proposals"] >= 1

    def test_preview_policy_migration(self) -> None:
        api = self._make_api()

        preview = api.preview_policy_migration(
            source_version_number=1,
            target_environment="production",
        )

        assert preview["environment"]["environment_id"] == "production"
        assert preview["source"]["version_number"] == 1
        assert preview["summary"]["source_provider_count"] == 1

    @pytest.mark.anyio
    async def test_stage_and_deploy_environment_promotion(self) -> None:
        api = self._make_api()

        captured_staging = api.capture_policy_environment(
            "staging",
            actor="reviewer",
            source_version_number=1,
            note="Seed staging from the current baseline.",
        )
        assert captured_staging["status"] == "captured"
        assert captured_staging["environment"]["current_version_number"] == 1

        created = await api.create_governance_proposal(
            action="add",
            config={"type": "denylist", "denied": ["admin-*"]},
            target_index=None,
            description="Harden the policy chain in development",
            author="reviewer",
        )
        proposal_id = created["proposal"]["proposal_id"]
        api.approve_governance_proposal(proposal_id, approver="admin")
        deployed = await api.deploy_governance_proposal(proposal_id, actor="admin")
        assert deployed["versions"]["current_version"] == 2

        captured_development = api.capture_policy_environment(
            "development",
            actor="reviewer",
            source_version_number=2,
            note="Development is ready for promotion.",
        )
        assert captured_development["status"] == "captured"
        assert captured_development["environment"]["current_version_number"] == 2

        staged = await api.stage_policy_promotion(
            source_environment="development",
            target_environment="staging",
            author="reviewer",
            description="Promote development into staging",
        )
        assert staged["status"] == "imported"
        promotion_proposal_id = staged["proposal"]["proposal_id"]
        assert staged["proposal"]["metadata"]["workbench_kind"] == "promotion"
        assert staged["promotions"]["count"] == 1

        approved = api.approve_governance_proposal(
            promotion_proposal_id,
            approver="admin",
            note="Promotion approved.",
        )
        assert approved["status"] == "approved"

        deployed_promotion = await api.deploy_governance_proposal(
            promotion_proposal_id,
            actor="admin",
            note="Promoting development to staging.",
        )
        assert deployed_promotion["status"] == "deployed"
        assert deployed_promotion["versions"]["current_version"] == 3

        environments = api.get_policy_environment_profiles()
        staging = next(
            item
            for item in environments["environments"]
            if item["environment_id"] == "staging"
        )
        assert staging["current_version_number"] == 3
        assert staging["current_source_label"] == "promotion from development"

        promotions = api.get_policy_promotions()
        assert promotions["count"] == 1
        assert promotions["promotions"][0]["status"] == "deployed"
        assert promotions["promotions"][0]["deployed_version_number"] == 3

    def test_validate_policy_success(self) -> None:
        api = self._make_api()
        result = api.validate_policy({"type": "allow_all"})
        assert result["valid"] is True

    def test_validate_policy_failure(self) -> None:
        api = self._make_api()
        result = api.validate_policy({"type": "banana"})
        assert result["valid"] is False

    def test_validate_providers(self) -> None:
        api = self._make_api()
        result = api.validate_providers()
        assert result["valid"] is True

    def test_get_metrics(self) -> None:
        api = self._make_api()
        assert api.policy_monitor is not None
        api.policy_monitor.record_decision(decision="allow", resource_id="x")
        metrics = api.get_policy_metrics()
        assert "window" in metrics
        assert "lifetime" in metrics

    def test_get_alerts(self) -> None:
        api = self._make_api()
        result = api.get_policy_alerts()
        assert "alerts" in result

    def test_get_governance_proposals(self) -> None:
        api = self._make_api()
        result = api.get_governance_proposals()
        assert result["total_proposals"] == 0

    def test_get_governance_proposal_not_found(self) -> None:
        api = self._make_api()
        result = api.get_governance_proposal("nonexistent")
        assert result["status"] == 404

    @pytest.mark.anyio
    async def test_create_governance_proposal(self) -> None:
        api = self._make_api()

        result = await api.create_governance_proposal(
            action="add",
            config={"type": "denylist", "denied": ["admin-*"]},
            target_index=None,
            description="Protect admin tools",
            author="reviewer",
        )

        assert result["status"] == "created"
        assert result["proposal"]["status"] == "validated"
        assert result["proposal"]["provider"]["config"]["type"] == "denylist"
        assert result["governance"]["pending_count"] == 1

    @pytest.mark.anyio
    async def test_approve_and_deploy_governance_proposal(self) -> None:
        api = self._make_api()
        created = await api.create_governance_proposal(
            action="add",
            config={"type": "denylist", "denied": ["admin-*"]},
            target_index=None,
            description="Protect admin tools",
            author="reviewer",
        )
        proposal_id = created["proposal"]["proposal_id"]

        assigned = api.assign_governance_proposal(
            proposal_id,
            reviewer="reviewer",
            actor="admin",
            note="Reviewer owns the rollout.",
        )
        assert assigned["status"] == "assigned"
        assert assigned["proposal"]["assigned_reviewer"] == "reviewer"

        approved = api.approve_governance_proposal(
            proposal_id,
            approver="admin",
            note="Looks safe to release.",
        )
        assert approved["status"] == "approved"
        assert approved["proposal"]["status"] == "approved"

        deployed = await api.deploy_governance_proposal(
            proposal_id,
            actor="admin",
            note="Deploying after reviewer sign-off.",
        )
        assert deployed["status"] == "deployed"
        assert deployed["proposal"]["status"] == "deployed"
        assert deployed["policy"]["provider_count"] == 2
        trail = deployed["proposal"]["decision_trail"]
        events = [item["event"] for item in trail]
        assert "assigned" in events
        assert events[-3:] == ["assigned", "approved", "deployed"]
        assert trail[-2]["event"] == "approved"
        assert trail[-2]["note"] == "Looks safe to release."
        assert trail[-1]["event"] == "deployed"
        assert trail[-1]["note"] == "Deploying after reviewer sign-off."

    @pytest.mark.anyio
    async def test_approve_and_deploy_replace_chain_proposal(self) -> None:
        api = self._make_api()

        created = await api.import_policy_snapshot(
            {
                "format": "securemcp-policy-set/v1",
                "providers": [
                    {"type": "denylist", "denied": ["admin-*"]},
                    {"type": "allowlist", "allowed": ["tool:*"]},
                ],
            },
            author="reviewer",
            description_prefix="Imported reviewed chain",
        )
        proposal_id = created["proposal"]["proposal_id"]

        approved = api.approve_governance_proposal(
            proposal_id,
            approver="admin",
            note="Batch import looks safe.",
        )
        assert approved["status"] == "approved"

        deployed = await api.deploy_governance_proposal(
            proposal_id,
            actor="admin",
            note="Applying imported chain.",
        )
        assert deployed["status"] == "deployed"
        assert deployed["proposal"]["action"] == "replace_chain"
        assert deployed["proposal"]["replacement_provider_count"] == 2
        assert deployed["policy"]["provider_count"] == 2
        assert deployed["versions"]["current_version"] == 2

    @pytest.mark.anyio
    async def test_simulate_governance_proposal(self) -> None:
        api = self._make_api()
        created = await api.create_governance_proposal(
            action="add",
            config={"type": "allowlist", "allowed": ["tool:*"]},
            target_index=None,
            description="Limit access to named tools",
            author="reviewer",
        )
        proposal_id = created["proposal"]["proposal_id"]

        simulated = await api.simulate_governance_proposal(
            proposal_id,
            scenarios_data=[
                {
                    "resource_id": "tool:weather-lookup",
                    "label": "Published tool",
                },
                {
                    "resource_id": "admin-panel",
                    "label": "Admin surface",
                },
            ],
        )

        assert simulated["status"] == "simulated"
        assert simulated["proposal"]["status"] == "simulated"
        assert simulated["simulation"]["total"] == 2
        assert simulated["simulation"]["denied"] == 1

    @pytest.mark.anyio
    async def test_import_policy_snapshot_creates_replace_chain_proposal(self) -> None:
        api = self._make_api()

        baseline = api.export_policy_snapshot()
        no_change = await api.import_policy_snapshot(
            baseline["snapshot"],
            author="reviewer",
            description_prefix="Imported baseline",
        )
        assert no_change["status"] == "no_changes"

        imported_snapshot = {
            "format": "securemcp-policy-set/v1",
            "providers": [
                {"type": "allow_all"},
                {"type": "denylist", "denied": ["admin-*"]},
            ],
        }
        imported = await api.import_policy_snapshot(
            imported_snapshot,
            author="reviewer",
            description_prefix="Imported denylist",
        )

        assert imported["status"] == "imported"
        assert imported["summary"]["created"] == 1
        assert imported["summary"]["added"] == 1
        assert imported["proposal"]["action"] == "replace_chain"
        assert imported["proposal"]["replacement_provider_count"] == 2
        assert imported["proposal"]["description"].startswith("Imported denylist")

    @pytest.mark.anyio
    async def test_import_policy_snapshot_allows_multi_change_batch(self) -> None:
        api = self._make_api()

        imported = await api.import_policy_snapshot(
            {
                "format": "securemcp-policy-set/v1",
                "providers": [
                    {"type": "denylist", "denied": ["admin-*"]},
                    {"type": "allowlist", "allowed": ["tool:*"]},
                ],
            },
            author="reviewer",
            description_prefix="Large import",
        )

        assert imported["status"] == "imported"
        assert imported["proposal"]["action"] == "replace_chain"
        assert imported["summary"]["created"] == 1
        assert imported["summary"]["changed"] == 1
        assert imported["summary"]["added"] == 1

    @pytest.mark.anyio
    async def test_stage_policy_bundle_creates_replace_chain_proposal(self) -> None:
        api = self._make_api()

        staged = await api.stage_policy_bundle(
            "registry-balanced",
            author="reviewer",
            description="Stage a recommended baseline bundle",
        )

        assert staged["status"] == "imported"
        assert staged["bundle"]["bundle_id"] == "registry-balanced"
        assert staged["proposal"]["action"] == "replace_chain"

    @pytest.mark.anyio
    async def test_reject_governance_proposal(self) -> None:
        api = self._make_api()
        created = await api.create_governance_proposal(
            action="remove",
            config=None,
            target_index=0,
            description="Remove baseline rule",
            author="reviewer",
        )
        proposal_id = created["proposal"]["proposal_id"]

        rejected = api.reject_governance_proposal(
            proposal_id,
            reason="Keep the baseline rule.",
        )

        assert rejected["status"] == "rejected"
        assert rejected["proposal"]["status"] == "rejected"
        assert rejected["proposal"]["rejection_reason"] == "Keep the baseline rule."
        assert rejected["proposal"]["decision_trail"][-1]["event"] == "rejected"
        assert rejected["proposal"]["decision_trail"][-1]["actor"] == "api"

    def test_assign_requires_reviewer_name(self) -> None:
        api = self._make_api()
        assert api.policy_governor is not None
        proposal = api.policy_governor.propose_add(
            DenylistPolicy(denied={"admin-*"}),
            author="reviewer",
            description="Protect admin tools",
        )

        assigned = api.assign_governance_proposal(
            proposal.proposal_id,
            reviewer="   ",
            actor="admin",
        )

        assert assigned["status"] == 400
        assert "reviewer username" in assigned["error"]

    def test_not_configured_returns_503(self) -> None:
        from fastmcp.server.security.http.api import SecurityAPI

        api = SecurityAPI()
        assert api.validate_policy({})["status"] == 503
        assert api.get_policy_metrics()["status"] == 503
        assert api.get_policy_alerts()["status"] == 503
        assert api.get_governance_proposals()["status"] == 503

    def test_health_includes_new_components(self) -> None:
        api = self._make_api()
        health = api.get_health()
        assert health["components"].get("policy_validator") == "ok"
        assert health["components"].get("policy_monitor") == "ok"
        assert health["components"].get("policy_governor") == "ok"
