"""Deterministic manual-review routing for registry submissions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastmcp.server.security.certification.attestation import (
    CertificationLevel,
    ValidationReport,
)
from fastmcp.server.security.certification.evidence import (
    AssuranceTier,
    CertificationEvidenceSource,
)
from fastmcp.server.security.certification.manifest import (
    DataClassification,
    PermissionScope,
    SecurityManifest,
)
from fastmcp.server.security.gateway.tool_marketplace import AttestationKind


class ManualReviewMode(Enum):
    """Operator policy for routing accepted submissions to human review."""

    DISABLED = "disabled"
    ALL = "all"
    RISK_BASED = "risk_based"


class ManualReviewRisk(Enum):
    """Priority assigned by the deterministic review assessment."""

    ROUTINE = "routine"
    ELEVATED = "elevated"
    HIGH = "high"


_HIGH_RISK_PERMISSIONS = frozenset(
    {
        PermissionScope.WRITE_RESOURCE,
        PermissionScope.FILE_SYSTEM_WRITE,
        PermissionScope.SUBPROCESS_EXEC,
        PermissionScope.SENSITIVE_DATA,
    }
)
_ELEVATED_PERMISSIONS = frozenset(
    {
        PermissionScope.CALL_TOOL,
        PermissionScope.FILE_SYSTEM_READ,
        PermissionScope.ENVIRONMENT_READ,
        PermissionScope.CROSS_ORIGIN,
    }
)
_HIGH_RISK_CLASSIFICATIONS = frozenset(
    {
        DataClassification.RESTRICTED,
        DataClassification.PII,
        DataClassification.PHI,
        DataClassification.FINANCIAL,
    }
)
_ELEVATED_CLASSIFICATIONS = frozenset({DataClassification.CONFIDENTIAL})


@dataclass(frozen=True)
class ManualReviewAssessment:
    """Risk signal and policy decision for one certified submission."""

    mode: ManualReviewMode
    risk: ManualReviewRisk
    recommended: bool
    required: bool
    reasons: tuple[str, ...]
    score_percent: int
    score_threshold_percent: int
    requested_level: str
    effective_level: str
    assurance_tier: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "risk": self.risk.value,
            "recommended": self.recommended,
            "required": self.required,
            "reasons": list(self.reasons),
            "score_percent": self.score_percent,
            "score_threshold_percent": self.score_threshold_percent,
            "requested_level": self.requested_level,
            "effective_level": self.effective_level,
            "assurance_tier": self.assurance_tier,
            "status": "pending" if self.required else "not_required",
        }


def resolve_manual_review_mode(
    *,
    require_moderation: bool,
    manual_review_mode: ManualReviewMode | str | None,
) -> ManualReviewMode:
    """Resolve the legacy all-review switch and the explicit review mode."""

    if manual_review_mode is None:
        return ManualReviewMode.ALL if require_moderation else ManualReviewMode.DISABLED
    mode = (
        manual_review_mode
        if isinstance(manual_review_mode, ManualReviewMode)
        else ManualReviewMode(manual_review_mode)
    )
    if require_moderation and mode is not ManualReviewMode.ALL:
        raise ValueError(
            "`require_moderation=True` conflicts with an explicit manual review "
            f"mode of `{mode.value}`"
        )
    return mode


def assess_manual_review(
    manifest: SecurityManifest,
    report: ValidationReport,
    *,
    mode: ManualReviewMode,
    requested_level: CertificationLevel,
    effective_level: CertificationLevel,
    attestation_kind: AttestationKind = AttestationKind.AUTHOR,
    score_threshold_percent: int = 85,
    exception_requested: bool = False,
) -> ManualReviewAssessment:
    """Assess risk without allowing publisher metadata to lower the result."""

    if isinstance(score_threshold_percent, bool) or not isinstance(
        score_threshold_percent, int
    ):
        raise ValueError("score_threshold_percent must be an integer")
    if not 0 <= score_threshold_percent <= 100:
        raise ValueError("score_threshold_percent must be between 0 and 100")

    high_reasons: set[str] = set()
    elevated_reasons: set[str] = set()

    for permission in manifest.permissions:
        if permission in _HIGH_RISK_PERMISSIONS:
            high_reasons.add(f"high_risk_permission:{permission.value}")
        elif permission in _ELEVATED_PERMISSIONS:
            elevated_reasons.add(f"elevated_permission:{permission.value}")

    classifications = {flow.classification for flow in manifest.data_flows} | {
        access.classification for access in manifest.resource_access
    }
    for classification in classifications:
        if classification in _HIGH_RISK_CLASSIFICATIONS:
            high_reasons.add(f"sensitive_data_classification:{classification.value}")
        elif classification in _ELEVATED_CLASSIFICATIONS:
            elevated_reasons.add(f"elevated_data_classification:{classification.value}")

    if attestation_kind is not AttestationKind.AUTHOR:
        high_reasons.add(f"non_author_attestation:{attestation_kind.value}")
    if report.score_percent < score_threshold_percent:
        elevated_reasons.add("validation_score_below_review_threshold")

    level_order = list(CertificationLevel)
    if level_order.index(effective_level) < level_order.index(requested_level):
        elevated_reasons.add("requested_certification_level_not_achieved")

    publisher_evidence = [
        evidence
        for evidence in report.test_evidence
        if evidence.source is CertificationEvidenceSource.PUBLISHER
    ]
    if publisher_evidence and not all(
        evidence.passed for evidence in publisher_evidence
    ):
        elevated_reasons.add("publisher_functional_tests_not_passing")
    if exception_requested:
        elevated_reasons.add("publisher_requested_exception_review")

    reasons = tuple(sorted(high_reasons | elevated_reasons))
    if high_reasons:
        risk = ManualReviewRisk.HIGH
    elif elevated_reasons:
        risk = ManualReviewRisk.ELEVATED
    else:
        risk = ManualReviewRisk.ROUTINE
    recommended = bool(reasons)
    required = mode is ManualReviewMode.ALL or (
        mode is ManualReviewMode.RISK_BASED and recommended
    )

    assurance_tier = report.assurance_tier
    if not isinstance(assurance_tier, AssuranceTier):
        assurance_tier = AssuranceTier.STATIC_ANALYSIS
    return ManualReviewAssessment(
        mode=mode,
        risk=risk,
        recommended=recommended,
        required=required,
        reasons=reasons,
        score_percent=report.score_percent,
        score_threshold_percent=score_threshold_percent,
        requested_level=requested_level.value,
        effective_level=effective_level.value,
        assurance_tier=assurance_tier.value,
    )


__all__ = [
    "ManualReviewAssessment",
    "ManualReviewMode",
    "ManualReviewRisk",
    "assess_manual_review",
    "resolve_manual_review_mode",
]
