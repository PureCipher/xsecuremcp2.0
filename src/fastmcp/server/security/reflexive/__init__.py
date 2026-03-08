"""Reflexive Core for SecureMCP (Phase 4 + Phase 11).

Behavioral drift detection, anomaly analysis, escalation engine,
pluggable anomaly detectors, and actor profiling for monitoring
agent behavior patterns.
"""

from fastmcp.server.security.reflexive.analyzer import (
    BehavioralAnalyzer,
    EscalationEngine,
)
from fastmcp.server.security.reflexive.detectors import (
    AnomalyDetector,
    OperationPattern,
    PatternDetector,
    SlidingWindowDetector,
    WindowConfig,
)
from fastmcp.server.security.reflexive.models import (
    BehavioralBaseline,
    DriftEvent,
    DriftSeverity,
    DriftType,
    EscalationAction,
    EscalationRule,
)
from fastmcp.server.security.reflexive.profiles import (
    ActorProfile,
    ActorProfileManager,
)

__all__ = [
    "ActorProfile",
    "ActorProfileManager",
    "AnomalyDetector",
    "BehavioralAnalyzer",
    "BehavioralBaseline",
    "DriftEvent",
    "DriftSeverity",
    "DriftType",
    "EscalationAction",
    "EscalationEngine",
    "EscalationRule",
    "OperationPattern",
    "PatternDetector",
    "SlidingWindowDetector",
    "WindowConfig",
]
