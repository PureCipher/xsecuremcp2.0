"""Certification score percentages and manifest-bound assurance evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
    PublisherEvidenceVerifier,
    TrustedPublisherTestRunner,
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
from fastmcp.server.security.config import CertificationConfig
from fastmcp.server.security.contracts.crypto import (
    ContractCryptoHandler,
    SigningAlgorithm,
    compute_digest,
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


def _publisher_crypto() -> ContractCryptoHandler:
    return ContractCryptoHandler(
        algorithm=SigningAlgorithm.HMAC_SHA256,
        secret_key=b"trusted-publisher-runner-key",
    )


def _publisher_verifier() -> PublisherEvidenceVerifier:
    return PublisherEvidenceVerifier(
        (
            TrustedPublisherTestRunner(
                runner_id="acme-ci",
                signer_id="purecipher-ci/acme",
                crypto_handler=_publisher_crypto(),
                allowed_suite_ids=frozenset({"acme-functional"}),
            ),
        )
    )


def _publisher_evidence(
    manifest: SecurityManifest,
    *,
    status: CertificationTestStatus = CertificationTestStatus.PASSED,
    generated_at: datetime | None = None,
) -> CertificationTestEvidence:
    evidence = CertificationTestEvidence(
        suite_id="acme-functional",
        suite_version="1.0.0",
        source=CertificationEvidenceSource.PUBLISHER,
        runner_id="acme-ci",
        manifest_digest=compute_digest(manifest.to_dict()),
        validation_report_id="",
        generated_at=generated_at or datetime.now(UTC),
        results=(
            CertificationTestResult(
                test_id="weather-round-trip",
                status=status,
                summary="Publisher integration test result",
            ),
        ),
    )
    signature = _publisher_crypto().sign(
        evidence.signable_payload(),
        signer_id="purecipher-ci/acme",
    )
    return replace(evidence, signature=signature)


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


def test_trusted_publisher_evidence_promotes_assurance_tier():
    manifest = _manifest()
    pipeline = CertificationPipeline(
        crypto_handler=_crypto(),
        publisher_evidence_verifier=_publisher_verifier(),
    )

    result = pipeline.certify(
        manifest,
        publisher_evidence=(_publisher_evidence(manifest),),
    )

    assert result.assurance_tier is AssuranceTier.PUBLISHER_TESTED
    assert len(result.report.test_evidence) == 2
    publisher_evidence = result.report.test_evidence[1]
    assert publisher_evidence.source is CertificationEvidenceSource.PUBLISHER
    assert publisher_evidence.signature is not None
    assert publisher_evidence.to_dict()["signature"]["signer_id"] == (
        "purecipher-ci/acme"
    )
    assert result.attestation.assurance_tier is AssuranceTier.PUBLISHER_TESTED
    assert pipeline.verify_attestation(result.attestation, manifest).valid is True


def test_certification_config_propagates_publisher_evidence_verifier():
    manifest = _manifest()
    pipeline = CertificationConfig(
        crypto_handler=_crypto(),
        publisher_evidence_verifier=_publisher_verifier(),
    ).get_pipeline()

    result = pipeline.certify(
        manifest,
        publisher_evidence=(_publisher_evidence(manifest),),
    )

    assert result.assurance_tier is AssuranceTier.PUBLISHER_TESTED


def test_failed_publisher_tests_do_not_erase_standard_assurance():
    manifest = _manifest()
    result = CertificationPipeline(
        crypto_handler=_crypto(),
        publisher_evidence_verifier=_publisher_verifier(),
    ).certify(
        manifest,
        publisher_evidence=(
            _publisher_evidence(
                manifest,
                status=CertificationTestStatus.FAILED,
            ),
        ),
    )

    assert result.assurance_tier is AssuranceTier.STANDARD_TESTED
    assert result.report.test_evidence[0].passed is True
    assert result.report.test_evidence[1].passed is False


def test_publisher_evidence_is_rejected_without_a_trust_policy():
    manifest = _manifest()

    with pytest.raises(ValueError, match="not enabled"):
        CertificationPipeline(crypto_handler=_crypto()).certify(
            manifest,
            publisher_evidence=(_publisher_evidence(manifest),),
        )


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda evidence: replace(evidence, suite_version="tampered"),
            "signature is invalid",
        ),
        (
            lambda evidence: replace(evidence, manifest_digest="0" * 64),
            "manifest binding does not match",
        ),
        (
            lambda evidence: replace(evidence, runner_id="untrusted-ci"),
            "runner is not trusted",
        ),
        (
            lambda evidence: replace(evidence, validation_report_id="wrong-report"),
            "report binding does not match",
        ),
    ],
)
def test_publisher_evidence_tampering_fails_closed(mutate, error):
    manifest = _manifest()
    evidence = mutate(_publisher_evidence(manifest))

    with pytest.raises(ValueError, match=error):
        CertificationPipeline(
            crypto_handler=_crypto(),
            publisher_evidence_verifier=_publisher_verifier(),
        ).certify(manifest, publisher_evidence=(evidence,))


def test_expired_publisher_evidence_is_rejected():
    manifest = _manifest()
    evidence = _publisher_evidence(
        manifest,
        generated_at=datetime.now(UTC) - timedelta(days=2),
    )

    with pytest.raises(ValueError, match="expired"):
        CertificationPipeline(
            crypto_handler=_crypto(),
            publisher_evidence_verifier=_publisher_verifier(),
        ).certify(manifest, publisher_evidence=(evidence,))


def test_manual_review_is_chained_into_a_resigned_attestation():
    manifest = _manifest()
    pipeline = CertificationPipeline(crypto_handler=_crypto())
    result = pipeline.certify(manifest)
    automated_digest = result.attestation.test_evidence_digest

    evidence = pipeline.record_manual_review(
        result.attestation,
        reviewer_id="reviewer-1",
        summary="Risk exception reviewed and approved.",
    )

    assert evidence.source is CertificationEvidenceSource.REVIEWER
    assert evidence.manifest_digest == result.manifest_digest
    assert evidence.validation_report_id == result.report.report_id
    assert result.attestation.assurance_tier is AssuranceTier.MANUAL_REVIEWED
    assert result.attestation.test_evidence_digest != automated_digest
    assert result.report.assurance_tier is AssuranceTier.MANUAL_REVIEWED
    assert result.report.test_evidence[-1] == evidence
    assert pipeline.verify_attestation(result.attestation, manifest).valid is True


def test_manual_review_works_after_validation_report_is_not_in_memory():
    manifest = _manifest()
    result = CertificationPipeline(crypto_handler=_crypto()).certify(manifest)
    restarted_pipeline = CertificationPipeline(crypto_handler=_crypto())

    evidence = restarted_pipeline.record_manual_review(
        result.attestation,
        reviewer_id="reviewer-after-restart",
    )

    assert evidence.passed is True
    assert result.attestation.assurance_tier is AssuranceTier.MANUAL_REVIEWED
    assert (
        restarted_pipeline.verify_attestation(
            result.attestation,
            manifest,
        ).valid
        is True
    )


def test_manual_review_rejects_tampered_or_static_attestations():
    manifest = _manifest()
    pipeline = CertificationPipeline(crypto_handler=_crypto())
    result = pipeline.certify(manifest)
    result.attestation.author = "tampered"

    with pytest.raises(ValueError, match="verifiable"):
        pipeline.record_manual_review(
            result.attestation,
            reviewer_id="reviewer-1",
        )

    static = CertificationPipeline(
        crypto_handler=_crypto(),
        test_suites=(),
    ).certify(manifest)
    with pytest.raises(ValueError, match="standard test evidence"):
        pipeline.record_manual_review(
            static.attestation,
            reviewer_id="reviewer-1",
        )


def test_manual_review_rejects_a_different_certification_issuer():
    manifest = _manifest()
    result = CertificationPipeline(
        issuer_id="issuer-a",
        crypto_handler=_crypto(),
    ).certify(manifest)
    other_issuer = CertificationPipeline(
        issuer_id="issuer-b",
        crypto_handler=_crypto(),
    )

    with pytest.raises(ValueError, match="issuer"):
        other_issuer.record_manual_review(
            result.attestation,
            reviewer_id="reviewer-1",
        )
