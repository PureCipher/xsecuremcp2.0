"""Behavioral analyzer for the Reflexive Core.

Monitors agent behavior, maintains baselines, detects drift,
and triggers escalation when anomalies are found.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastmcp.server.security.reflexive.models import (
    BehavioralBaseline,
    DriftEvent,
    DriftSeverity,
    DriftType,
    EscalationAction,
    EscalationRule,
)

logger = logging.getLogger(__name__)


# Default severity thresholds (in standard deviations)
_DEFAULT_SIGMA_THRESHOLDS: dict[DriftSeverity, float] = {
    DriftSeverity.LOW: 2.0,
    DriftSeverity.MEDIUM: 3.0,
    DriftSeverity.HIGH: 4.0,
    DriftSeverity.CRITICAL: 5.0,
}


class BehavioralAnalyzer:
    """Monitors agent behavior and detects anomalous patterns.

    Maintains per-actor baselines for various metrics and raises
    drift events when observed values deviate significantly from
    the established baseline.

    Example::

        analyzer = BehavioralAnalyzer()

        # Record observations
        analyzer.observe("agent-1", "calls_per_minute", 5.0)
        analyzer.observe("agent-1", "calls_per_minute", 6.0)
        # ... many observations to build baseline ...

        # Check for drift
        events = analyzer.observe("agent-1", "calls_per_minute", 50.0)
        if events:
            print(f"Drift detected: {events[0].severity}")

    Args:
        sigma_thresholds: Custom sigma thresholds for severity levels.
        min_samples: Minimum observations before drift detection activates.
    """

    def __init__(
        self,
        *,
        sigma_thresholds: dict[DriftSeverity, float] | None = None,
        min_samples: int = 10,
    ) -> None:
        self._baselines: dict[str, dict[str, BehavioralBaseline]] = defaultdict(dict)
        self._sigma_thresholds = sigma_thresholds or dict(_DEFAULT_SIGMA_THRESHOLDS)
        self._min_samples = min_samples
        self._drift_history: list[DriftEvent] = []

    def observe(
        self,
        actor_id: str,
        metric_name: str,
        value: float,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[DriftEvent]:
        """Record a behavioral observation and check for drift.

        Args:
            actor_id: The agent being observed.
            metric_name: Name of the metric.
            value: The observed value.
            metadata: Additional context.

        Returns:
            List of DriftEvent instances if drift was detected.
        """
        # Get or create baseline
        if metric_name not in self._baselines[actor_id]:
            self._baselines[actor_id][metric_name] = BehavioralBaseline(
                metric_name=metric_name,
                actor_id=actor_id,
            )

        baseline = self._baselines[actor_id][metric_name]

        # Check for drift before updating (so we compare against existing baseline)
        events: list[DriftEvent] = []
        if baseline.sample_count >= self._min_samples:
            deviation = baseline.compute_deviation(value)
            severity = self._classify_severity(deviation)

            if severity is not None:
                event = DriftEvent(
                    drift_type=DriftType.FREQUENCY_SPIKE,
                    severity=severity,
                    actor_id=actor_id,
                    description=(
                        f"Metric '{metric_name}' deviated {deviation:.1f} sigma "
                        f"from baseline (observed={value:.2f}, "
                        f"mean={baseline.mean:.2f}, std={baseline.std_dev:.2f})"
                    ),
                    observed_value=value,
                    baseline_value=baseline.mean,
                    deviation=deviation,
                    metadata={
                        "metric_name": metric_name,
                        **(metadata or {}),
                    },
                )
                events.append(event)
                self._drift_history.append(event)

                logger.warning(
                    "Drift detected for %s/%s: %s sigma (%s)",
                    actor_id,
                    metric_name,
                    f"{deviation:.1f}",
                    severity.value,
                )

        # Update baseline with new observation
        baseline.update(value)

        return events

    def _classify_severity(self, deviation: float) -> DriftSeverity | None:
        """Classify deviation into a severity level.

        Returns None if deviation is within normal range.
        """
        result = None
        for severity in [
            DriftSeverity.LOW,
            DriftSeverity.MEDIUM,
            DriftSeverity.HIGH,
            DriftSeverity.CRITICAL,
        ]:
            threshold = self._sigma_thresholds.get(severity, float("inf"))
            if deviation >= threshold:
                result = severity
        return result

    def get_baseline(
        self, actor_id: str, metric_name: str
    ) -> BehavioralBaseline | None:
        """Get the current baseline for a specific metric."""
        return self._baselines.get(actor_id, {}).get(metric_name)

    def get_actor_baselines(self, actor_id: str) -> dict[str, BehavioralBaseline]:
        """Get all baselines for an actor."""
        return dict(self._baselines.get(actor_id, {}))

    def get_drift_history(
        self,
        *,
        actor_id: str | None = None,
        severity: DriftSeverity | None = None,
        limit: int = 100,
    ) -> list[DriftEvent]:
        """Query drift event history."""
        results: list[DriftEvent] = []
        for event in reversed(self._drift_history):
            if actor_id is not None and event.actor_id != actor_id:
                continue
            if severity is not None and event.severity != severity:
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return results

    @property
    def total_drift_count(self) -> int:
        """Total number of drift events recorded."""
        return len(self._drift_history)

    def reset_baseline(self, actor_id: str, metric_name: str | None = None) -> None:
        """Reset baselines for an actor.

        Args:
            actor_id: The actor to reset.
            metric_name: If provided, reset only this metric.
                If None, reset all metrics for the actor.
        """
        if metric_name is not None:
            self._baselines[actor_id].pop(metric_name, None)
        else:
            self._baselines.pop(actor_id, None)


class EscalationEngine:
    """Processes drift events and triggers appropriate escalation actions.

    Evaluates drift events against configured rules, respects cooldown
    periods, and tracks escalation history.

    Example::

        engine = EscalationEngine(rules=[
            EscalationRule(
                min_severity=DriftSeverity.HIGH,
                action=EscalationAction.SUSPEND_AGENT,
            ),
            EscalationRule(
                min_severity=DriftSeverity.MEDIUM,
                action=EscalationAction.ALERT,
            ),
        ])

        actions = engine.evaluate(drift_event)
        for action, rule in actions:
            print(f"Escalation: {action.value}")

    Args:
        rules: List of escalation rules.
        on_escalation: Optional async callback invoked on each escalation.
    """

    def __init__(
        self,
        rules: list[EscalationRule] | None = None,
        *,
        on_escalation: Any = None,
    ) -> None:
        self.rules = list(rules or [])
        self._on_escalation = on_escalation
        self._escalation_history: list[tuple[DriftEvent, EscalationRule, EscalationAction]] = []
        self._last_trigger: dict[str, datetime] = {}
        self._trigger_counts: dict[str, int] = defaultdict(int)

    def evaluate(self, event: DriftEvent) -> list[tuple[EscalationAction, EscalationRule]]:
        """Evaluate a drift event against all rules.

        Args:
            event: The drift event to evaluate.

        Returns:
            List of (action, rule) tuples for triggered escalations.
        """
        triggered: list[tuple[EscalationAction, EscalationRule]] = []

        for rule in self.rules:
            if not rule.matches(event):
                continue

            # Check cooldown
            last = self._last_trigger.get(rule.rule_id)
            if last is not None:
                elapsed = (datetime.now(timezone.utc) - last).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            # Check threshold count
            key = f"{event.actor_id}:{rule.rule_id}"
            self._trigger_counts[key] += 1
            if self._trigger_counts[key] < rule.threshold_count:
                continue

            # Trigger!
            self._last_trigger[rule.rule_id] = datetime.now(timezone.utc)
            self._escalation_history.append((event, rule, rule.action))
            triggered.append((rule.action, rule))

            logger.warning(
                "Escalation triggered: %s (rule %s) for actor %s",
                rule.action.value,
                rule.rule_id,
                event.actor_id,
            )

        return triggered

    def add_rule(self, rule: EscalationRule) -> None:
        """Add an escalation rule."""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an escalation rule by ID. Returns True if found."""
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                self.rules.pop(i)
                return True
        return False

    @property
    def escalation_count(self) -> int:
        """Total escalations triggered."""
        return len(self._escalation_history)

    def get_escalation_history(
        self, *, limit: int = 100
    ) -> list[tuple[DriftEvent, EscalationRule, EscalationAction]]:
        """Get recent escalation history."""
        return list(reversed(self._escalation_history[-limit:]))
