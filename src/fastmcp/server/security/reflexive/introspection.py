"""Introspection Engine for the Reflexive Execution Engine.

Enables self-examination during inference: operations can query their
own deviation, threat score, compliance status, and active constraints
before execution proceeds. Produces accountability records that link
reflexive state to specific operations for non-repudiation.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastmcp.server.security.reflexive.models import (
    ComplianceStatus,
    DEFAULT_THREAT_THRESHOLDS,
    DriftSeverity,
    EscalationAction,
    ExecutionVerdict,
    IntrospectionResult,
    ThreatLevel,
)

if TYPE_CHECKING:
    from fastmcp.server.security.reflexive.analyzer import (
        BehavioralAnalyzer,
        EscalationEngine,
    )
    from fastmcp.server.security.reflexive.profiles import ActorProfileManager

logger = logging.getLogger(__name__)


class ConfirmationRequiredError(Exception):
    """Raised when an operation requires human confirmation before proceeding.

    Carries the introspection result so callers can inspect why
    confirmation is needed.

    Attributes:
        introspection: The IntrospectionResult that triggered the requirement.
        actor_id: The actor whose operation needs confirmation.
        operation: The operation that was attempted.
    """

    def __init__(
        self,
        message: str,
        *,
        introspection: IntrospectionResult | None = None,
        actor_id: str = "",
        operation: str = "",
    ) -> None:
        super().__init__(message)
        self.introspection = introspection
        self.actor_id = actor_id
        self.operation = operation


class IntrospectionEngine:
    """Core engine for reflexive self-examination.

    Queries the current threat score, drift history, escalation state,
    and computes compliance status, execution verdicts, and dynamic
    constraints for any actor.

    Example::

        engine = IntrospectionEngine(
            analyzer=analyzer,
            escalation_engine=escalation_engine,
            profile_manager=profile_manager,
        )

        # Full introspection
        result = engine.introspect("agent-1")
        if result.should_halt:
            print("Agent should be halted!")

        # Quick verdict check
        verdict = engine.get_execution_verdict("agent-1", "call_tool")
        if verdict == ExecutionVerdict.PROCEED:
            # safe to continue
            pass

    Args:
        analyzer: BehavioralAnalyzer for drift history.
        escalation_engine: EscalationEngine for escalation history.
        profile_manager: ActorProfileManager for threat scores and profiles.
        threat_thresholds: Custom score boundaries for threat-level
            classification. If None, defaults are used.
        enable_pre_execution_gating: If True, ``get_execution_verdict``
            returns non-PROCEED verdicts. If False, always returns PROCEED
            (useful for dry-run / monitoring-only mode).
    """

    def __init__(
        self,
        analyzer: BehavioralAnalyzer,
        escalation_engine: EscalationEngine,
        profile_manager: ActorProfileManager,
        *,
        threat_thresholds: dict[ThreatLevel, float] | None = None,
        enable_pre_execution_gating: bool = True,
    ) -> None:
        self.analyzer = analyzer
        self.escalation_engine = escalation_engine
        self.profile_manager = profile_manager
        self._threat_thresholds = threat_thresholds or dict(DEFAULT_THREAT_THRESHOLDS)
        self.enable_pre_execution_gating = enable_pre_execution_gating

        # Append-only accountability log: list of dicts
        self._accountability_log: list[dict[str, Any]] = []

        # Introspection history per actor (most recent first)
        self._introspection_history: dict[str, list[IntrospectionResult]] = defaultdict(
            list
        )

    # ── Core introspection ────────────────────────────────────────

    def introspect(self, actor_id: str) -> IntrospectionResult:
        """Perform a full self-examination for an actor.

        Queries current threat score, drift history, escalation state,
        computes compliance status and execution verdict, and records
        the introspection for accountability.

        Args:
            actor_id: The agent to examine.

        Returns:
            An IntrospectionResult capturing the actor's current state.
        """
        threat_score = self.profile_manager.threat_score(actor_id)
        threat_level = self.get_threat_level(actor_id)
        drift_summary = self._build_drift_summary(actor_id)
        active_escalations = self._get_active_escalations(actor_id)
        compliance_status = self._compute_compliance_status(
            threat_level, active_escalations
        )
        verdict = self._determine_verdict(threat_level, active_escalations)
        constraints = self.get_active_constraints(actor_id)

        result = IntrospectionResult(
            actor_id=actor_id,
            threat_score=threat_score,
            threat_level=threat_level,
            drift_summary=drift_summary,
            active_escalations=active_escalations,
            compliance_status=compliance_status,
            verdict=verdict,
            should_halt=verdict == ExecutionVerdict.HALT,
            should_require_confirmation=verdict == ExecutionVerdict.REQUIRE_CONFIRMATION,
            constraints=constraints,
        )

        self.record_introspection(actor_id, result)
        return result

    def get_execution_verdict(
        self,
        actor_id: str,
        operation: str = "",
        resource_id: str = "",
    ) -> ExecutionVerdict:
        """Quick pre-execution check returning the appropriate verdict.

        When ``enable_pre_execution_gating`` is False, always returns
        PROCEED (monitoring-only mode).

        Args:
            actor_id: The requesting actor.
            operation: The operation type (e.g., ``"call_tool"``).
            resource_id: Optional target resource identifier.

        Returns:
            The recommended ExecutionVerdict.
        """
        if not self.enable_pre_execution_gating:
            return ExecutionVerdict.PROCEED

        threat_level = self.get_threat_level(actor_id)
        active_escalations = self._get_active_escalations(actor_id)
        return self._determine_verdict(
            threat_level, active_escalations, operation=operation
        )

    def get_threat_level(self, actor_id: str) -> ThreatLevel:
        """Map an actor's threat score to a discrete ThreatLevel.

        Args:
            actor_id: The actor to classify.

        Returns:
            The current ThreatLevel for the actor.
        """
        score = self.profile_manager.threat_score(actor_id)
        return self._score_to_level(score)

    def get_active_constraints(self, actor_id: str) -> list[str]:
        """Compute dynamic operational constraints for an actor.

        Returns a list of constraint strings that should be enforced
        during the next operation, based on current threat level and
        escalation state.

        Args:
            actor_id: The actor to constrain.

        Returns:
            List of constraint identifiers (e.g., ``"sandbox_required"``).
        """
        constraints: list[str] = []
        threat_level = self.get_threat_level(actor_id)
        escalations = self._get_active_escalations(actor_id)

        if threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            constraints.append("sandbox_required")
            constraints.append("audit_all_outputs")

        if threat_level == ThreatLevel.CRITICAL:
            constraints.append("human_confirmation_required")

        if EscalationAction.THROTTLE.value in escalations:
            constraints.append("rate_limited")

        if EscalationAction.REQUIRE_CONFIRMATION.value in escalations:
            constraints.append("human_confirmation_required")

        if threat_level in (ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            constraints.append("enhanced_logging")

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for c in constraints:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    # ── Accountability ────────────────────────────────────────────

    def record_introspection(
        self, actor_id: str, result: IntrospectionResult
    ) -> None:
        """Record an introspection result for accountability.

        Appends to both the per-actor history and the global
        accountability log.

        Args:
            actor_id: The actor examined.
            result: The introspection result to record.
        """
        self._introspection_history[actor_id].insert(0, result)

        self._accountability_log.append(
            {
                "type": "introspection",
                "actor_id": actor_id,
                "threat_score": result.threat_score,
                "threat_level": result.threat_level.value,
                "compliance_status": result.compliance_status.value,
                "verdict": result.verdict.value,
                "constraints": list(result.constraints),
                "timestamp": result.assessed_at.isoformat(),
            }
        )

        logger.debug(
            "Introspection recorded for %s: level=%s, verdict=%s",
            actor_id,
            result.threat_level.value,
            result.verdict.value,
        )

    def bind_to_provenance(
        self,
        actor_id: str,
        introspection_result: IntrospectionResult,
        operation_id: str = "",
    ) -> dict[str, Any]:
        """Create an accountability record linking reflexive state to an operation.

        Produces a dict that can be attached to a provenance record
        to demonstrate that reflexive self-examination occurred and
        what the system's assessment was at the time.

        Args:
            actor_id: The actor involved.
            introspection_result: The introspection snapshot.
            operation_id: An external operation identifier to bind to.

        Returns:
            An accountability binding dict.
        """
        binding_id = str(uuid.uuid4())[:12]
        record = {
            "binding_id": binding_id,
            "actor_id": actor_id,
            "operation_id": operation_id or str(uuid.uuid4())[:12],
            "threat_score": introspection_result.threat_score,
            "threat_level": introspection_result.threat_level.value,
            "compliance_status": introspection_result.compliance_status.value,
            "verdict": introspection_result.verdict.value,
            "constraints": list(introspection_result.constraints),
            "assessed_at": introspection_result.assessed_at.isoformat(),
            "bound_at": datetime.now(timezone.utc).isoformat(),
        }

        self._accountability_log.append(
            {
                "type": "provenance_binding",
                **record,
            }
        )

        return record

    def get_accountability_log(
        self,
        *,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query the accountability log.

        Args:
            actor_id: Filter to this actor (None = all).
            limit: Maximum entries to return.

        Returns:
            List of accountability records, most recent first.
        """
        results: list[dict[str, Any]] = []
        for entry in reversed(self._accountability_log):
            if actor_id is not None and entry.get("actor_id") != actor_id:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def get_introspection_history(
        self,
        actor_id: str,
        *,
        limit: int = 50,
    ) -> list[IntrospectionResult]:
        """Get recent introspection results for an actor.

        Args:
            actor_id: The actor to query.
            limit: Maximum results to return.

        Returns:
            List of IntrospectionResult, most recent first.
        """
        return self._introspection_history.get(actor_id, [])[:limit]

    # ── Private helpers ───────────────────────────────────────────

    def _score_to_level(self, score: float) -> ThreatLevel:
        """Map a numeric threat score to a discrete ThreatLevel."""
        result = ThreatLevel.NONE
        for level in [
            ThreatLevel.LOW,
            ThreatLevel.MEDIUM,
            ThreatLevel.HIGH,
            ThreatLevel.CRITICAL,
        ]:
            threshold = self._threat_thresholds.get(level, float("inf"))
            if score >= threshold:
                result = level
        return result

    def _build_drift_summary(self, actor_id: str) -> dict[str, int]:
        """Build a count-by-severity summary of recent drift events."""
        profile = self.profile_manager.get_profile(actor_id)
        if profile is None:
            return {}
        counts: dict[str, int] = defaultdict(int)
        for event in profile.drift_events:
            counts[event.severity.value] += 1
        return dict(counts)

    def _get_active_escalations(self, actor_id: str) -> list[str]:
        """Get the most recent escalation actions for an actor.

        Looks at the escalation engine's history and returns unique
        action values for this actor.
        """
        actions: list[str] = []
        seen: set[str] = set()
        for event, rule, action in self.escalation_engine.get_escalation_history():
            if event.actor_id != actor_id:
                continue
            if action.value not in seen:
                seen.add(action.value)
                actions.append(action.value)
        return actions

    def _compute_compliance_status(
        self,
        threat_level: ThreatLevel,
        active_escalations: list[str],
    ) -> ComplianceStatus:
        """Derive compliance status from threat level and escalations."""
        if threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            return ComplianceStatus.NON_COMPLIANT

        if threat_level == ThreatLevel.MEDIUM:
            return ComplianceStatus.ELEVATED_RISK

        # Check for serious escalation actions even at low threat
        serious = {
            EscalationAction.SUSPEND_AGENT.value,
            EscalationAction.REVOKE_CONTRACT.value,
            EscalationAction.SHUTDOWN.value,
        }
        if serious & set(active_escalations):
            return ComplianceStatus.NON_COMPLIANT

        if active_escalations:
            return ComplianceStatus.ELEVATED_RISK

        if threat_level in (ThreatLevel.NONE, ThreatLevel.LOW):
            return ComplianceStatus.COMPLIANT

        return ComplianceStatus.UNKNOWN

    def _determine_verdict(
        self,
        threat_level: ThreatLevel,
        active_escalations: list[str],
        operation: str = "",
    ) -> ExecutionVerdict:
        """Determine the execution verdict from threat level and escalations."""
        # HALT conditions
        halt_actions = {
            EscalationAction.SUSPEND_AGENT.value,
            EscalationAction.SHUTDOWN.value,
        }
        if halt_actions & set(active_escalations):
            return ExecutionVerdict.HALT

        if threat_level == ThreatLevel.CRITICAL:
            return ExecutionVerdict.HALT

        # THROTTLE conditions
        if threat_level == ThreatLevel.HIGH:
            return ExecutionVerdict.THROTTLE

        if EscalationAction.THROTTLE.value in active_escalations:
            return ExecutionVerdict.THROTTLE

        # REQUIRE_CONFIRMATION conditions
        if threat_level == ThreatLevel.MEDIUM:
            return ExecutionVerdict.REQUIRE_CONFIRMATION

        if EscalationAction.REQUIRE_CONFIRMATION.value in active_escalations:
            return ExecutionVerdict.REQUIRE_CONFIRMATION

        return ExecutionVerdict.PROCEED
