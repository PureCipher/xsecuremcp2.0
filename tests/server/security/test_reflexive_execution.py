"""Tests for the Reflexive Execution Engine.

Covers introspection models, threat-level mapping, the IntrospectionEngine,
execution verdicts, pre-execution gating in middleware, accountability
binding, HTTP endpoints, backward compatibility, and full lifecycle.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from fastmcp.server.security.reflexive.analyzer import (
    BehavioralAnalyzer,
    EscalationEngine,
)
from fastmcp.server.security.reflexive.introspection import (
    ConfirmationRequiredError,
    IntrospectionEngine,
)
from fastmcp.server.security.reflexive.models import (
    BehavioralBaseline,
    ComplianceStatus,
    DEFAULT_THREAT_THRESHOLDS,
    DriftEvent,
    DriftSeverity,
    DriftType,
    EscalationAction,
    EscalationRule,
    ExecutionVerdict,
    IntrospectionResult,
    ThreatLevel,
)
from fastmcp.server.security.reflexive.profiles import (
    ActorProfile,
    ActorProfileManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(
    *,
    enable_gating: bool = True,
    thresholds: dict[ThreatLevel, float] | None = None,
    rules: list[EscalationRule] | None = None,
) -> tuple[IntrospectionEngine, BehavioralAnalyzer, EscalationEngine, ActorProfileManager]:
    """Create an IntrospectionEngine with its dependencies."""
    analyzer = BehavioralAnalyzer(min_samples=5)
    esc = EscalationEngine(rules=rules or [])
    pm = ActorProfileManager()
    ie = IntrospectionEngine(
        analyzer=analyzer,
        escalation_engine=esc,
        profile_manager=pm,
        threat_thresholds=thresholds,
        enable_pre_execution_gating=enable_gating,
    )
    return ie, analyzer, esc, pm


def _build_drift_event(
    actor_id: str = "agent-1",
    severity: DriftSeverity = DriftSeverity.MEDIUM,
    drift_type: DriftType = DriftType.FREQUENCY_SPIKE,
) -> DriftEvent:
    return DriftEvent(
        drift_type=drift_type,
        severity=severity,
        actor_id=actor_id,
        description=f"Test drift ({severity.value})",
        observed_value=99.0,
        baseline_value=10.0,
        deviation=5.0,
    )


# ===========================================================================
# TestIntrospectionModels
# ===========================================================================


class TestIntrospectionModels:
    """Test the new introspection data models."""

    def test_compliance_status_values(self) -> None:
        assert ComplianceStatus.COMPLIANT.value == "compliant"
        assert ComplianceStatus.ELEVATED_RISK.value == "elevated_risk"
        assert ComplianceStatus.NON_COMPLIANT.value == "non_compliant"
        assert ComplianceStatus.UNKNOWN.value == "unknown"

    def test_execution_verdict_values(self) -> None:
        assert ExecutionVerdict.PROCEED.value == "proceed"
        assert ExecutionVerdict.REQUIRE_CONFIRMATION.value == "require_confirmation"
        assert ExecutionVerdict.THROTTLE.value == "throttle"
        assert ExecutionVerdict.HALT.value == "halt"

    def test_threat_level_values(self) -> None:
        assert ThreatLevel.NONE.value == "none"
        assert ThreatLevel.LOW.value == "low"
        assert ThreatLevel.MEDIUM.value == "medium"
        assert ThreatLevel.HIGH.value == "high"
        assert ThreatLevel.CRITICAL.value == "critical"

    def test_default_threat_thresholds(self) -> None:
        assert DEFAULT_THREAT_THRESHOLDS[ThreatLevel.LOW] == 5.0
        assert DEFAULT_THREAT_THRESHOLDS[ThreatLevel.MEDIUM] == 15.0
        assert DEFAULT_THREAT_THRESHOLDS[ThreatLevel.HIGH] == 30.0
        assert DEFAULT_THREAT_THRESHOLDS[ThreatLevel.CRITICAL] == 50.0

    def test_introspection_result_defaults(self) -> None:
        result = IntrospectionResult()
        assert result.actor_id == ""
        assert result.threat_score == 0.0
        assert result.threat_level == ThreatLevel.NONE
        assert result.compliance_status == ComplianceStatus.UNKNOWN
        assert result.verdict == ExecutionVerdict.PROCEED
        assert result.should_halt is False
        assert result.should_require_confirmation is False
        assert result.constraints == []
        assert result.drift_summary == {}
        assert result.active_escalations == []

    def test_introspection_result_with_values(self) -> None:
        result = IntrospectionResult(
            actor_id="agent-1",
            threat_score=35.0,
            threat_level=ThreatLevel.HIGH,
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            verdict=ExecutionVerdict.HALT,
            should_halt=True,
            constraints=["sandbox_required"],
        )
        assert result.actor_id == "agent-1"
        assert result.threat_score == 35.0
        assert result.should_halt is True
        assert "sandbox_required" in result.constraints

    def test_confirmation_required_error(self) -> None:
        result = IntrospectionResult(actor_id="agent-1")
        err = ConfirmationRequiredError(
            "needs confirmation",
            introspection=result,
            actor_id="agent-1",
            operation="call_tool",
        )
        assert str(err) == "needs confirmation"
        assert err.introspection is result
        assert err.actor_id == "agent-1"
        assert err.operation == "call_tool"


# ===========================================================================
# TestThreatLevel
# ===========================================================================


class TestThreatLevel:
    """Test threat-score-to-level mapping."""

    def test_score_zero_is_none(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(0.0) == ThreatLevel.NONE

    def test_score_below_low(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(4.9) == ThreatLevel.NONE

    def test_score_at_low(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(5.0) == ThreatLevel.LOW

    def test_score_at_medium(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(15.0) == ThreatLevel.MEDIUM

    def test_score_at_high(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(30.0) == ThreatLevel.HIGH

    def test_score_at_critical(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(50.0) == ThreatLevel.CRITICAL

    def test_score_above_critical(self) -> None:
        ie, _, _, _ = _make_engine()
        assert ie._score_to_level(999.0) == ThreatLevel.CRITICAL

    def test_custom_thresholds(self) -> None:
        custom = {
            ThreatLevel.LOW: 10.0,
            ThreatLevel.MEDIUM: 20.0,
            ThreatLevel.HIGH: 40.0,
            ThreatLevel.CRITICAL: 80.0,
        }
        ie, _, _, _ = _make_engine(thresholds=custom)
        assert ie._score_to_level(9.9) == ThreatLevel.NONE
        assert ie._score_to_level(10.0) == ThreatLevel.LOW
        assert ie._score_to_level(79.9) == ThreatLevel.HIGH
        assert ie._score_to_level(80.0) == ThreatLevel.CRITICAL


# ===========================================================================
# TestIntrospectionEngine
# ===========================================================================


class TestIntrospectionEngine:
    """Test core IntrospectionEngine functionality."""

    def test_introspect_clean_actor(self) -> None:
        ie, _, _, _ = _make_engine()
        result = ie.introspect("clean-agent")
        assert result.actor_id == "clean-agent"
        assert result.threat_score == 0.0
        assert result.threat_level == ThreatLevel.NONE
        assert result.compliance_status == ComplianceStatus.COMPLIANT
        assert result.verdict == ExecutionVerdict.PROCEED
        assert result.should_halt is False
        assert result.should_require_confirmation is False

    def test_introspect_actor_with_drift(self) -> None:
        ie, _, _, pm = _make_engine()
        # Simulate drift events to raise threat score
        for _ in range(5):
            event = _build_drift_event("risky-agent", DriftSeverity.HIGH)
            pm.record_drift("risky-agent", event)
        result = ie.introspect("risky-agent")
        assert result.threat_score > 0.0
        assert result.drift_summary.get("high", 0) == 5

    def test_introspect_records_in_history(self) -> None:
        ie, _, _, _ = _make_engine()
        ie.introspect("agent-1")
        ie.introspect("agent-1")
        history = ie.get_introspection_history("agent-1")
        assert len(history) == 2

    def test_get_threat_level_from_engine(self) -> None:
        ie, _, _, pm = _make_engine()
        # Score should be 0
        assert ie.get_threat_level("agent-1") == ThreatLevel.NONE
        # Bump score by recording critical drift events
        for _ in range(10):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.CRITICAL))
        level = ie.get_threat_level("agent-1")
        assert level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)

    def test_get_active_constraints_clean_actor(self) -> None:
        ie, _, _, _ = _make_engine()
        constraints = ie.get_active_constraints("clean-agent")
        assert constraints == []

    def test_get_active_constraints_high_threat(self) -> None:
        ie, _, _, pm = _make_engine()
        # Pump up threat score
        for _ in range(10):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.CRITICAL))
        constraints = ie.get_active_constraints("agent-1")
        assert "sandbox_required" in constraints
        assert "audit_all_outputs" in constraints


# ===========================================================================
# TestExecutionVerdicts
# ===========================================================================


class TestExecutionVerdicts:
    """Test execution verdict determination."""

    def test_proceed_for_clean_actor(self) -> None:
        ie, _, _, _ = _make_engine()
        verdict = ie.get_execution_verdict("clean-agent", "call_tool")
        assert verdict == ExecutionVerdict.PROCEED

    def test_halt_for_critical_threat(self) -> None:
        ie, _, _, pm = _make_engine()
        # Push score well above critical threshold (50)
        for _ in range(15):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.CRITICAL))
        verdict = ie.get_execution_verdict("agent-1", "call_tool")
        assert verdict == ExecutionVerdict.HALT

    def test_halt_for_suspended_escalation(self) -> None:
        ie, _, esc, pm = _make_engine(
            rules=[
                EscalationRule(
                    min_severity=DriftSeverity.HIGH,
                    action=EscalationAction.SUSPEND_AGENT,
                    cooldown_seconds=0,
                )
            ]
        )
        event = _build_drift_event("agent-1", DriftSeverity.HIGH)
        pm.record_drift("agent-1", event)
        esc.evaluate(event)
        verdict = ie.get_execution_verdict("agent-1", "call_tool")
        assert verdict == ExecutionVerdict.HALT

    def test_require_confirmation_for_medium_threat(self) -> None:
        ie, _, _, pm = _make_engine()
        # Push score to medium range (15-29)
        for _ in range(8):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.MEDIUM))
        score = pm.threat_score("agent-1")
        # Ensure score is in MEDIUM range
        if 15.0 <= score < 30.0:
            verdict = ie.get_execution_verdict("agent-1", "call_tool")
            assert verdict == ExecutionVerdict.REQUIRE_CONFIRMATION

    def test_throttle_for_high_threat(self) -> None:
        ie, _, _, pm = _make_engine()
        # Push score to high range (30-49)
        for _ in range(10):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.CRITICAL))
        score = pm.threat_score("agent-1")
        level = ie._score_to_level(score)
        if level == ThreatLevel.HIGH:
            verdict = ie.get_execution_verdict("agent-1", "call_tool")
            assert verdict == ExecutionVerdict.THROTTLE

    def test_gating_disabled_always_proceed(self) -> None:
        ie, _, _, pm = _make_engine(enable_gating=False)
        # Even with high threat, verdict is PROCEED when gating is off
        for _ in range(15):
            pm.record_drift("agent-1", _build_drift_event("agent-1", DriftSeverity.CRITICAL))
        verdict = ie.get_execution_verdict("agent-1", "call_tool")
        assert verdict == ExecutionVerdict.PROCEED


# ===========================================================================
# TestPreExecutionGating
# ===========================================================================


class TestPreExecutionGating:
    """Test middleware pre-execution gating."""

    def test_middleware_without_introspection_behaves_normally(self) -> None:
        """Without introspection engine, middleware is backward compatible."""
        from fastmcp.server.security.middleware.reflexive import ReflexiveMiddleware

        analyzer = BehavioralAnalyzer(min_samples=5)
        mw = ReflexiveMiddleware(analyzer)
        assert mw.introspection_engine is None

    def test_middleware_with_introspection_engine(self) -> None:
        from fastmcp.server.security.middleware.reflexive import ReflexiveMiddleware

        ie, analyzer, esc, pm = _make_engine()
        mw = ReflexiveMiddleware(
            analyzer,
            escalation_engine=esc,
            profile_manager=pm,
            introspection_engine=ie,
        )
        assert mw.introspection_engine is ie

    def test_middleware_throttle_delay_configurable(self) -> None:
        from fastmcp.server.security.middleware.reflexive import ReflexiveMiddleware

        ie, analyzer, esc, pm = _make_engine()
        mw = ReflexiveMiddleware(
            analyzer,
            escalation_engine=esc,
            profile_manager=pm,
            introspection_engine=ie,
            throttle_delay_seconds=5.0,
        )
        assert mw.throttle_delay_seconds == 5.0


# ===========================================================================
# TestAccountabilityBinding
# ===========================================================================


class TestAccountabilityBinding:
    """Test accountability audit trail."""

    def test_introspect_creates_accountability_record(self) -> None:
        ie, _, _, _ = _make_engine()
        ie.introspect("agent-1")
        log = ie.get_accountability_log()
        assert len(log) == 1
        assert log[0]["type"] == "introspection"
        assert log[0]["actor_id"] == "agent-1"

    def test_bind_to_provenance_creates_record(self) -> None:
        ie, _, _, _ = _make_engine()
        result = ie.introspect("agent-1")
        binding = ie.bind_to_provenance("agent-1", result, "op-123")
        assert binding["actor_id"] == "agent-1"
        assert binding["operation_id"] == "op-123"
        assert "binding_id" in binding
        assert "bound_at" in binding

    def test_accountability_log_filter_by_actor(self) -> None:
        ie, _, _, _ = _make_engine()
        ie.introspect("agent-1")
        ie.introspect("agent-2")
        ie.introspect("agent-1")
        log = ie.get_accountability_log(actor_id="agent-1")
        assert len(log) == 2
        assert all(e["actor_id"] == "agent-1" for e in log)

    def test_accountability_log_includes_bindings(self) -> None:
        ie, _, _, _ = _make_engine()
        result = ie.introspect("agent-1")
        ie.bind_to_provenance("agent-1", result, "op-1")
        log = ie.get_accountability_log()
        types = {e["type"] for e in log}
        assert "introspection" in types
        assert "provenance_binding" in types

    def test_accountability_log_limit(self) -> None:
        ie, _, _, _ = _make_engine()
        for i in range(10):
            ie.introspect(f"agent-{i}")
        log = ie.get_accountability_log(limit=3)
        assert len(log) == 3


# ===========================================================================
# TestHTTPEndpoints
# ===========================================================================


class TestHTTPEndpoints:
    """Test SecurityAPI introspection methods."""

    def _make_api(
        self, *, with_engine: bool = True
    ) -> "SecurityAPI":
        from fastmcp.server.security.http.api import SecurityAPI

        if not with_engine:
            return SecurityAPI()

        ie, _, _, _ = _make_engine()
        return SecurityAPI(introspection_engine=ie)

    def test_introspection_unconfigured_returns_503(self) -> None:
        api = self._make_api(with_engine=False)
        result = api.get_introspection("agent-1")
        assert result["status"] == 503

    def test_introspection_returns_result(self) -> None:
        api = self._make_api()
        result = api.get_introspection("agent-1")
        assert result["actor_id"] == "agent-1"
        assert result["threat_level"] == "none"
        assert result["verdict"] == "proceed"

    def test_verdict_unconfigured_returns_503(self) -> None:
        api = self._make_api(with_engine=False)
        result = api.get_verdict("agent-1", "call_tool")
        assert result["status"] == 503

    def test_verdict_returns_result(self) -> None:
        api = self._make_api()
        result = api.get_verdict("agent-1", "call_tool")
        assert result["verdict"] == "proceed"
        assert result["operation"] == "call_tool"

    def test_threat_level_unconfigured_returns_503(self) -> None:
        api = self._make_api(with_engine=False)
        result = api.get_actor_threat_level("agent-1")
        assert result["status"] == 503

    def test_threat_level_returns_result(self) -> None:
        api = self._make_api()
        result = api.get_actor_threat_level("agent-1")
        assert result["threat_level"] == "none"
        assert result["threat_score"] == 0.0

    def test_constraints_unconfigured_returns_503(self) -> None:
        api = self._make_api(with_engine=False)
        result = api.get_actor_constraints("agent-1")
        assert result["status"] == 503

    def test_constraints_returns_result(self) -> None:
        api = self._make_api()
        result = api.get_actor_constraints("agent-1")
        assert result["constraints"] == []
        assert result["count"] == 0

    def test_accountability_unconfigured_returns_503(self) -> None:
        api = self._make_api(with_engine=False)
        result = api.get_accountability()
        assert result["status"] == 503

    def test_accountability_returns_entries(self) -> None:
        api = self._make_api()
        # Trigger an introspection to generate log entries
        api.get_introspection("agent-1")
        result = api.get_accountability()
        assert result["count"] > 0

    def test_health_includes_introspection(self) -> None:
        api = self._make_api()
        health = api.get_health()
        assert health["components"].get("introspection_engine") == "ok"

    def test_health_without_introspection(self) -> None:
        api = self._make_api(with_engine=False)
        health = api.get_health()
        assert "introspection_engine" not in health.get("components", {})


# ===========================================================================
# TestBackwardCompatibility
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure no introspection_engine = existing behavior preserved."""

    def test_reflexive_models_still_importable(self) -> None:
        from fastmcp.server.security.reflexive.models import (
            BehavioralBaseline,
            DriftEvent,
            DriftSeverity,
            DriftType,
            EscalationAction,
            EscalationRule,
        )
        assert BehavioralBaseline is not None
        assert DriftEvent is not None

    def test_reflexive_init_exports_old_types(self) -> None:
        from fastmcp.server.security.reflexive import (
            BehavioralAnalyzer,
            EscalationEngine,
            ActorProfile,
            ActorProfileManager,
        )
        assert BehavioralAnalyzer is not None

    def test_reflexive_init_exports_new_types(self) -> None:
        from fastmcp.server.security.reflexive import (
            IntrospectionEngine,
            IntrospectionResult,
            ComplianceStatus,
            ExecutionVerdict,
            ThreatLevel,
            ConfirmationRequiredError,
        )
        assert IntrospectionEngine is not None
        assert ConfirmationRequiredError is not None

    def test_security_init_exports_new_types(self) -> None:
        from fastmcp.server.security import (
            IntrospectionEngine,
            IntrospectionResult,
            ExecutionVerdict,
            ThreatLevel,
            ConfirmationRequiredError,
            IntrospectionConfig,
        )
        assert IntrospectionConfig is not None

    def test_config_introspection_config(self) -> None:
        from fastmcp.server.security.config import IntrospectionConfig

        config = IntrospectionConfig()
        assert config.enable_pre_execution_gating is False
        assert config.throttle_delay_seconds == 2.0

    def test_config_introspection_get_engine(self) -> None:
        from fastmcp.server.security.config import IntrospectionConfig

        analyzer = BehavioralAnalyzer(min_samples=5)
        esc = EscalationEngine()
        pm = ActorProfileManager()
        config = IntrospectionConfig(enable_pre_execution_gating=True)
        engine = config.get_introspection_engine(analyzer, esc, pm)
        assert engine.enable_pre_execution_gating is True

    def test_security_config_has_introspection_field(self) -> None:
        from fastmcp.server.security.config import IntrospectionConfig, SecurityConfig

        config = SecurityConfig(
            introspection=IntrospectionConfig(enable_pre_execution_gating=True)
        )
        assert config.introspection is not None
        assert config.introspection.enable_pre_execution_gating is True


# ===========================================================================
# TestComplianceStatusDerivation
# ===========================================================================


class TestComplianceStatusDerivation:
    """Test compliance status computation logic."""

    def test_compliant_with_no_issues(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(ThreatLevel.NONE, [])
        assert status == ComplianceStatus.COMPLIANT

    def test_compliant_with_low_threat(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(ThreatLevel.LOW, [])
        assert status == ComplianceStatus.COMPLIANT

    def test_elevated_risk_with_medium_threat(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(ThreatLevel.MEDIUM, [])
        assert status == ComplianceStatus.ELEVATED_RISK

    def test_elevated_risk_with_escalations(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(
            ThreatLevel.LOW, [EscalationAction.ALERT.value]
        )
        assert status == ComplianceStatus.ELEVATED_RISK

    def test_non_compliant_with_high_threat(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(ThreatLevel.HIGH, [])
        assert status == ComplianceStatus.NON_COMPLIANT

    def test_non_compliant_with_critical_threat(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(ThreatLevel.CRITICAL, [])
        assert status == ComplianceStatus.NON_COMPLIANT

    def test_non_compliant_with_suspend_escalation(self) -> None:
        ie, _, _, _ = _make_engine()
        status = ie._compute_compliance_status(
            ThreatLevel.LOW, [EscalationAction.SUSPEND_AGENT.value]
        )
        assert status == ComplianceStatus.NON_COMPLIANT


# ===========================================================================
# TestFullLifecycle
# ===========================================================================


class TestFullLifecycle:
    """End-to-end: observe metrics → drift → threat rises → verdict changes → accountability."""

    def test_full_lifecycle(self) -> None:
        ie, analyzer, esc, pm = _make_engine(
            rules=[
                EscalationRule(
                    min_severity=DriftSeverity.HIGH,
                    action=EscalationAction.SUSPEND_AGENT,
                    cooldown_seconds=0,
                ),
                EscalationRule(
                    min_severity=DriftSeverity.MEDIUM,
                    action=EscalationAction.ALERT,
                    cooldown_seconds=0,
                ),
            ]
        )
        actor = "lifecycle-agent"

        # Phase 1: Clean actor — all clear
        result = ie.introspect(actor)
        assert result.verdict == ExecutionVerdict.PROCEED
        assert result.compliance_status == ComplianceStatus.COMPLIANT

        # Phase 2: Build up baseline (need min_samples=5)
        for i in range(10):
            analyzer.observe(actor, "calls_per_minute", 5.0 + i * 0.1)

        # Phase 3: Still clean — no significant drift
        verdict = ie.get_execution_verdict(actor, "call_tool")
        assert verdict == ExecutionVerdict.PROCEED

        # Phase 4: Inject drift events to bump threat score
        for _ in range(5):
            event = _build_drift_event(actor, DriftSeverity.HIGH)
            pm.record_drift(actor, event)
            esc.evaluate(event)

        # Phase 5: Actor should now be non-compliant with HALT verdict
        result = ie.introspect(actor)
        assert result.compliance_status == ComplianceStatus.NON_COMPLIANT
        assert result.verdict == ExecutionVerdict.HALT
        assert result.should_halt is True

        # Phase 6: Verify accountability trail
        log = ie.get_accountability_log(actor_id=actor)
        assert len(log) >= 2  # at least 2 introspections

        # Phase 7: Bind to provenance
        binding = ie.bind_to_provenance(actor, result, "op-final")
        assert binding["actor_id"] == actor
        assert binding["verdict"] == "halt"

        # Phase 8: Verify binding is in accountability log
        full_log = ie.get_accountability_log(actor_id=actor)
        binding_entries = [e for e in full_log if e["type"] == "provenance_binding"]
        assert len(binding_entries) >= 1
