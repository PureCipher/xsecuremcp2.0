"""Certification score percentages and manifest-bound assurance evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from fastmcp.server.security.certification.attestation import (
    ToolAttestation,
    ValidationReport,
    score_to_percent,
)
from fastmcp.server.security.certification.evidence import (
    AssuranceTier,
    CertificationEvidenceSource,
    CertificationTestEvidence,
    CertificationTestResult,
    CertificationTestStatus,
    assurance_tier_for_evidence,
)
from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    ResourceAccessDeclaration,
    SecurityManifest,
)
from fastmcp.server.security.certification.pipeline import CertificationPipeline
from fastmcp.server.security.contracts.crypto import (
    ContractCryptoHandler,
    SigningAlgorithm,
)
from fastmcp.server.security.gateway.tool_marketplace import ToolMarketplace


def _manifest(**overrides: Any) -> SecurityManifest:
    values: dict[str, Any] = {
        "tool_name": "evidence-tool",
        "version": "1.0.0",
        "author": "acme",
        "description": "A tool used to exercise certification evidence.",
        "permissions": {PermissionScope.READ_RESOURCE},
        "data_flows": [
            DataFlowDeclaration(
                source="input.query",
                destination="output.result",
                classification=DataClassification.INTERNAL,
                description="Query to result",
            )
        ],
        "resource_access": [
            ResourceAccessDeclaration(
                resource_pattern="docs://knowledge/*",
                access_type="read",
                description="Read the knowledge base",
            )
        ],
    }
    values.update(overrides)
    return SecurityManifest(**values)


def _crypto() -> ContractCryptoHandler:
    return ContractCryptoHandler(
        algorithm=SigningAlgorithm.HMAC_SHA256,
        secret_key=b"certification-evidence-test-key",
    )


@pytest.mark.parametrize(
    "score, expected",
    [(-1.0, 0), (0.0, 0), (0.846, 85), (1.0, 100), (2.0, 100)],
)
def test_normalized_scores_are_exposed_as_bounded_percentages(score, expected):
    report = ValidationReport(score=score)
    attestation = ToolAttestation(validation_score=score)

    assert score_to_percent(score) == expected
    assert report.score_percent == expected
    assert report.to_dict()["score_percent"] == expected
    assert attestation.validation_score_percent == expected
    assert attestation.to_dict()["validation_score_percent"] == expected


@pytest.mark.parametrize("score", [True, float("inf"), float("nan"), "0.5"])
def test_invalid_scores_cannot_be_presented_as_percentages(score):
    with pytest.raises((TypeError, ValueError)):
        score_to_percent(score)


def test_standard_suite_emits_signed_manifest_bound_evidence():
    pipeline = CertificationPipeline(crypto_handler=_crypto())

    result = pipeline.certify(_manifest())

    assert result.assurance_tier is AssuranceTier.STANDARD_TESTED
    assert result.report.score_percent >= 80
    assert len(result.report.test_evidence) == 1
    evidence = result.report.test_evidence[0]
    assert evidence.suite_id == "securemcp-standard"
    assert evidence.source is CertificationEvidenceSource.SECUREMCP
    assert evidence.manifest_digest == result.manifest_digest
    assert evidence.validation_report_id == result.report.report_id
    assert evidence.passed is True
    assert len(evidence.digest) == 64
    assert result.attestation.assurance_tier is AssuranceTier.STANDARD_TESTED
    assert len(result.attestation.test_evidence_digest) == 64
    assert pipeline.verify_attestation(result.attestation, _manifest()).valid is False

    # The same manifest object remains bound to the signed attestation.
    manifest = _manifest()
    bound_result = pipeline.certify(manifest)
    assert pipeline.verify_attestation(bound_result.attestation, manifest).valid is True


def test_blocking_validation_findings_do_not_claim_standard_test_assurance():
    pipeline = CertificationPipeline(crypto_handler=_crypto())

    result = pipeline.certify(SecurityManifest())

    assert result.assurance_tier is AssuranceTier.STATIC_ANALYSIS
    assert result.report.test_evidence[0].passed is False
    assert any(
        item.status is CertificationTestStatus.FAILED
        for item in result.report.test_evidence[0].results
    )


def test_suite_failures_are_recorded_without_leaking_exception_text():
    class BrokenSuite:
        suite_id = "broken-suite"
        suite_version = "1.0.0"
        source = CertificationEvidenceSource.SECUREMCP
        runner_id = "tests.broken"

        def run(self, manifest, report, *, manifest_digest):
            del manifest, report, manifest_digest
            raise RuntimeError("secret runner detail")

    pipeline = CertificationPipeline(
        crypto_handler=_crypto(),
        test_suites=(BrokenSuite(),),
    )

    result = pipeline.certify(_manifest())

    evidence = result.report.test_evidence[0]
    assert result.assurance_tier is AssuranceTier.STATIC_ANALYSIS
    assert evidence.passed is False
    assert evidence.results[0].status is CertificationTestStatus.ERROR
    assert "RuntimeError" in evidence.results[0].summary
    assert "secret runner detail" not in evidence.results[0].summary


def test_mismatched_suite_binding_fails_closed_as_error_evidence():
    class MismatchedSuite:
        suite_id = "mismatched-suite"
        suite_version = "1.0.0"
        source = CertificationEvidenceSource.SECUREMCP
        runner_id = "tests.mismatched"

        def run(self, manifest, report, *, manifest_digest):
            del manifest, manifest_digest
            return CertificationTestEvidence(
                suite_id=self.suite_id,
                suite_version=self.suite_version,
                source=self.source,
                runner_id=self.runner_id,
                manifest_digest="wrong-digest",
                validation_report_id=report.report_id,
                results=(
                    CertificationTestResult(
                        test_id="false-pass",
                        status=CertificationTestStatus.PASSED,
                    ),
                ),
            )

    result = CertificationPipeline(
        crypto_handler=_crypto(),
        test_suites=(MismatchedSuite(),),
    ).certify(_manifest())

    evidence = result.report.test_evidence[0]
    assert result.assurance_tier is AssuranceTier.STATIC_ANALYSIS
    assert evidence.manifest_digest == result.manifest_digest
    assert evidence.results[0].status is CertificationTestStatus.ERROR


def test_evidence_digest_and_assurance_tier_are_covered_by_signature():
    manifest = _manifest()
    pipeline = CertificationPipeline(crypto_handler=_crypto())
    result = pipeline.certify(manifest)

    assert pipeline.verify_attestation(result.attestation, manifest).valid is True

    result.attestation.test_evidence_digest = "0" * 64
    verification = pipeline.verify_attestation(result.attestation, manifest)

    assert verification.valid is False
    assert verification.signature_valid is False
    assert "Signature verification failed" in verification.issues


def test_static_only_pipeline_preserves_legacy_signable_payload_shape():
    manifest = _manifest()
    pipeline = CertificationPipeline(
        crypto_handler=_crypto(),
        test_suites=(),
    )
    result = pipeline.certify(manifest)

    payload = result.attestation.signable_payload()
    serialized = result.attestation.to_dict()
    restored = ToolMarketplace._deserialize_attestation(serialized)

    assert result.assurance_tier is AssuranceTier.STATIC_ANALYSIS
    assert result.report.test_evidence == []
    assert "assurance_tier" not in payload
    assert "test_evidence_digest" not in payload
    assert serialized["assurance_tier"] == "static_analysis"
    assert serialized["test_evidence_digest"] == ""
    assert restored is not None
    assert pipeline.verify_attestation(restored, manifest).valid is True


def test_marketplace_round_trip_preserves_evidence_binding():
    result = CertificationPipeline(crypto_handler=_crypto()).certify(_manifest())

    restored = ToolMarketplace._deserialize_attestation(result.attestation.to_dict())

    assert restored is not None
    assert restored.assurance_tier is AssuranceTier.STANDARD_TESTED
    assert restored.test_evidence_digest == result.attestation.test_evidence_digest
    assert restored.validation_score_percent == result.score_percent


def test_duplicate_suite_ids_are_rejected():
    class Suite:
        suite_id = "duplicate"
        suite_version = "1.0.0"
        source = CertificationEvidenceSource.SECUREMCP
        runner_id = "tests.duplicate"

        def run(self, manifest, report, *, manifest_digest):
            raise AssertionError("not called")

    with pytest.raises(ValueError, match="unique"):
        CertificationPipeline(test_suites=(Suite(), Suite()))


def test_evidence_requires_timezone_aware_generation_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        CertificationTestEvidence(
            suite_id="suite",
            suite_version="1.0.0",
            source=CertificationEvidenceSource.SECUREMCP,
            runner_id="runner",
            manifest_digest="digest",
            validation_report_id="report",
            generated_at=datetime.now(),
            results=(
                CertificationTestResult(
                    test_id="case",
                    status=CertificationTestStatus.PASSED,
                ),
            ),
        )


def test_skipped_only_evidence_does_not_pass():
    evidence = CertificationTestEvidence(
        suite_id="suite",
        suite_version="1.0.0",
        source=CertificationEvidenceSource.PUBLISHER,
        runner_id="runner",
        manifest_digest="digest",
        validation_report_id="report",
        generated_at=datetime.now(UTC),
        results=(
            CertificationTestResult(
                test_id="case",
                status=CertificationTestStatus.SKIPPED,
            ),
        ),
    )

    assert evidence.passed is False
    assert replace(evidence).to_dict() == evidence.to_dict()


def test_one_failed_evidence_record_prevents_tier_promotion():
    def evidence(status: CertificationTestStatus) -> CertificationTestEvidence:
        return CertificationTestEvidence(
            suite_id=f"suite-{status.value}",
            suite_version="1.0.0",
            source=CertificationEvidenceSource.SECUREMCP,
            runner_id="runner",
            manifest_digest="digest",
            validation_report_id="report",
            results=(CertificationTestResult(test_id="case", status=status),),
        )

    assert (
        assurance_tier_for_evidence(
            [
                evidence(CertificationTestStatus.PASSED),
                evidence(CertificationTestStatus.FAILED),
            ]
        )
        is AssuranceTier.STATIC_ANALYSIS
    )
