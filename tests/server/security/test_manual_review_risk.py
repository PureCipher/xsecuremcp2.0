"""Risk-based manual-review routing policy."""

from __future__ import annotations

from typing import Any, cast

import pytest

from fastmcp.server.security.certification.attestation import (
    CertificationLevel,
    ValidationReport,
)
from fastmcp.server.security.certification.evidence import (
    AssuranceTier,
    CertificationEvidenceSource,
    CertificationTestEvidence,
    CertificationTestResult,
    CertificationTestStatus,
)
from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    SecurityManifest,
)
from fastmcp.server.security.gateway.tool_marketplace import AttestationKind
from purecipher.review_risk import (
    ManualReviewMode,
    ManualReviewRisk,
    assess_manual_review,
    resolve_manual_review_mode,
)


def _manifest(**overrides) -> SecurityManifest:
    values: dict[str, Any] = {
        "tool_name": "review-routing-tool",
        "version": "1.0.0",
        "author": "acme",
        "permissions": {PermissionScope.READ_RESOURCE},
        "data_flows": [
            DataFlowDeclaration(
                source="input.query",
                destination="output.result",
                classification=DataClassification.PUBLIC,
            )
        ],
    }
    values.update(overrides)
    return SecurityManifest(**cast(Any, values))


def _report(*, score: float = 1.0) -> ValidationReport:
    return ValidationReport(
        score=score,
        max_certification_level=CertificationLevel.STRICT,
        assurance_tier=AssuranceTier.STANDARD_TESTED,
    )


def _assess(
    manifest: SecurityManifest,
    *,
    report: ValidationReport | None = None,
    mode: ManualReviewMode = ManualReviewMode.RISK_BASED,
    requested: CertificationLevel = CertificationLevel.BASIC,
    effective: CertificationLevel = CertificationLevel.BASIC,
    kind: AttestationKind = AttestationKind.AUTHOR,
    exception_requested: bool = False,
):
    return assess_manual_review(
        manifest,
        report or _report(),
        mode=mode,
        requested_level=requested,
        effective_level=effective,
        attestation_kind=kind,
        exception_requested=exception_requested,
    )


def test_routine_submission_bypasses_risk_based_review():
    assessment = _assess(_manifest())

    assert assessment.risk is ManualReviewRisk.ROUTINE
    assert assessment.recommended is False
    assert assessment.required is False
    assert assessment.reasons == ()


def test_high_risk_permissions_and_data_require_review():
    assessment = _assess(
        _manifest(
            permissions={
                PermissionScope.READ_RESOURCE,
                PermissionScope.FILE_SYSTEM_WRITE,
            },
            data_flows=[
                DataFlowDeclaration(
                    source="input.patient",
                    destination="storage.record",
                    classification=DataClassification.PHI,
                )
            ],
        )
    )

    assert assessment.risk is ManualReviewRisk.HIGH
    assert assessment.required is True
    assert "high_risk_permission:file_system_write" in assessment.reasons
    assert "sensitive_data_classification:phi" in assessment.reasons


def test_disabled_mode_reports_risk_without_forcing_review():
    assessment = _assess(
        _manifest(permissions={PermissionScope.SUBPROCESS_EXEC}),
        mode=ManualReviewMode.DISABLED,
    )

    assert assessment.recommended is True
    assert assessment.required is False
    assert assessment.risk is ManualReviewRisk.HIGH


def test_all_mode_routes_even_routine_submissions():
    assessment = _assess(_manifest(), mode=ManualReviewMode.ALL)

    assert assessment.risk is ManualReviewRisk.ROUTINE
    assert assessment.recommended is False
    assert assessment.required is True


def test_certification_shortfall_curator_and_exception_are_review_signals():
    assessment = _assess(
        _manifest(),
        requested=CertificationLevel.STRICT,
        effective=CertificationLevel.BASIC,
        kind=AttestationKind.CURATOR,
        exception_requested=True,
    )

    assert assessment.risk is ManualReviewRisk.HIGH
    assert assessment.required is True
    assert "requested_certification_level_not_achieved" in assessment.reasons
    assert "non_author_attestation:curator" in assessment.reasons
    assert "publisher_requested_exception_review" in assessment.reasons


def test_failed_publisher_functional_evidence_routes_to_review():
    report = _report()
    report.test_evidence.append(
        CertificationTestEvidence(
            suite_id="publisher-functional",
            suite_version="1.0.0",
            source=CertificationEvidenceSource.PUBLISHER,
            runner_id="trusted-runner",
            manifest_digest="a" * 64,
            validation_report_id="",
            results=(
                CertificationTestResult(
                    test_id="round-trip",
                    status=CertificationTestStatus.FAILED,
                ),
            ),
        )
    )

    assessment = _assess(_manifest(), report=report)

    assert assessment.risk is ManualReviewRisk.ELEVATED
    assert assessment.required is True
    assert "publisher_functional_tests_not_passing" in assessment.reasons


def test_legacy_moderation_switch_resolves_to_all_mode():
    assert (
        resolve_manual_review_mode(
            require_moderation=True,
            manual_review_mode=None,
        )
        is ManualReviewMode.ALL
    )
    with pytest.raises(ValueError, match="conflicts"):
        resolve_manual_review_mode(
            require_moderation=True,
            manual_review_mode=ManualReviewMode.RISK_BASED,
        )


def test_review_score_threshold_must_be_an_integer_percentage():
    with pytest.raises(ValueError, match="integer"):
        assess_manual_review(
            _manifest(),
            _report(),
            mode=ManualReviewMode.RISK_BASED,
            requested_level=CertificationLevel.BASIC,
            effective_level=CertificationLevel.BASIC,
            score_threshold_percent=True,
        )
