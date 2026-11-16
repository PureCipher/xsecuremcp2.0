"""Typed test evidence for SecureMCP certification assurance.

Certification levels describe what a manifest qualifies for. Assurance tiers
describe the evidence used to support that decision. Keeping these concepts
separate prevents static validation from being presented as runtime or manual
assurance.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from fastmcp.server.security.contracts.crypto import (
    ContractCryptoHandler,
    SignatureInfo,
)

if TYPE_CHECKING:
    from fastmcp.server.security.certification.attestation import ValidationReport
    from fastmcp.server.security.certification.manifest import SecurityManifest


class AssuranceTier(Enum):
    """Depth of evidence supporting a certification decision."""

    STATIC_ANALYSIS = "static_analysis"
    STANDARD_TESTED = "standard_tested"
    PUBLISHER_TESTED = "publisher_tested"
    MANUAL_REVIEWED = "manual_reviewed"


class CertificationEvidenceSource(Enum):
    """Authority that produced a certification evidence record."""

    SECUREMCP = "securemcp"
    PUBLISHER = "publisher"
    REVIEWER = "reviewer"


class CertificationTestStatus(Enum):
    """Outcome of one certification test case."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CertificationTestResult:
    """Result of one stable test identifier within an evidence suite."""

    test_id: str
    status: CertificationTestStatus
    summary: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.test_id, str) or not self.test_id.strip():
            raise ValueError("test_id must be nonempty")
        if not isinstance(self.status, CertificationTestStatus):
            raise ValueError("status must be a CertificationTestStatus")
        if not isinstance(self.summary, str):
            raise ValueError("summary must be a string")

    def to_dict(self) -> dict[str, str]:
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class CertificationTestEvidence:
    """Manifest-bound evidence emitted by one certification test suite."""

    suite_id: str
    suite_version: str
    source: CertificationEvidenceSource
    runner_id: str
    manifest_digest: str
    validation_report_id: str
    results: tuple[CertificationTestResult, ...]
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    signature: SignatureInfo | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "suite_id",
            "suite_version",
            "runner_id",
            "manifest_digest",
            "evidence_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be nonempty")
        if not isinstance(self.source, CertificationEvidenceSource):
            raise ValueError("source must be a CertificationEvidenceSource")
        if not isinstance(self.validation_report_id, str):
            raise ValueError("validation_report_id must be a string")
        if (
            self.source is not CertificationEvidenceSource.PUBLISHER
            and not self.validation_report_id.strip()
        ):
            raise ValueError("validation_report_id must be nonempty")
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise ValueError("generated_at must be timezone-aware")
        object.__setattr__(self, "results", tuple(self.results))
        if not self.results:
            raise ValueError("results must contain at least one test result")
        if any(
            not isinstance(result, CertificationTestResult) for result in self.results
        ):
            raise ValueError("results must contain CertificationTestResult values")
        if self.signature is not None and not isinstance(self.signature, SignatureInfo):
            raise ValueError("signature must be a SignatureInfo")

    @property
    def passed(self) -> bool:
        """Whether every executed test completed without failure or error."""

        executed = [
            result
            for result in self.results
            if result.status is not CertificationTestStatus.SKIPPED
        ]
        return bool(executed) and all(
            result.status is CertificationTestStatus.PASSED for result in executed
        )

    @property
    def counts(self) -> dict[str, int]:
        return {
            status.value: sum(1 for result in self.results if result.status is status)
            for status in CertificationTestStatus
        }

    def signable_payload(self) -> dict[str, Any]:
        """Return the canonical publisher-runner signature payload."""

        return {
            "evidence_id": self.evidence_id,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "source": self.source.value,
            "runner_id": self.runner_id,
            "manifest_digest": self.manifest_digest,
            "validation_report_id": self.validation_report_id,
            "generated_at": self.generated_at.isoformat(),
            "results": [result.to_dict() for result in self.results],
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            **self.signable_payload(),
            "passed": self.passed,
            "counts": self.counts,
        }
        if self.signature is not None:
            payload["signature"] = {
                "algorithm": self.signature.algorithm.value,
                "signer_id": self.signature.signer_id,
                "signature": self.signature.signature,
                "key_id": self.signature.key_id,
            }
        return payload

    @property
    def digest(self) -> str:
        """Deterministic SHA-256 digest binding the complete evidence record."""

        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TrustedPublisherTestRunner:
    """Operator trust policy for one publisher functional-test runner."""

    runner_id: str
    signer_id: str
    crypto_handler: ContractCryptoHandler
    allowed_suite_ids: frozenset[str]
    key_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.runner_id, str) or not self.runner_id.strip():
            raise ValueError("runner_id must be nonempty")
        if not isinstance(self.signer_id, str) or not self.signer_id.strip():
            raise ValueError("signer_id must be nonempty")
        if not isinstance(self.crypto_handler, ContractCryptoHandler):
            raise ValueError("crypto_handler must be a ContractCryptoHandler")
        if isinstance(self.allowed_suite_ids, str):
            raise ValueError("allowed_suite_ids must be a collection of suite IDs")
        object.__setattr__(self, "allowed_suite_ids", frozenset(self.allowed_suite_ids))
        if not self.allowed_suite_ids or any(
            not isinstance(suite_id, str) or not suite_id.strip()
            for suite_id in self.allowed_suite_ids
        ):
            raise ValueError("allowed_suite_ids must contain nonempty strings")
        if not isinstance(self.key_id, str):
            raise ValueError("key_id must be a string")


class PublisherEvidenceVerifier:
    """Verify publisher functional-test evidence against trusted CI runners.

    A publisher can submit evidence produced before the registry creates its
    validation report, so ``validation_report_id`` may be blank. The evidence
    must still be signed and bound to the exact manifest digest; the registry's
    signed attestation subsequently binds its digest to the generated report.
    """

    def __init__(
        self,
        runners: Iterable[TrustedPublisherTestRunner],
        *,
        max_evidence_age: timedelta = timedelta(hours=24),
        future_clock_skew: timedelta = timedelta(minutes=5),
        max_evidence_records: int = 8,
    ) -> None:
        runner_list = tuple(runners)
        if any(
            not isinstance(runner, TrustedPublisherTestRunner) for runner in runner_list
        ):
            raise ValueError("runners must contain TrustedPublisherTestRunner values")
        self._runners = {runner.runner_id: runner for runner in runner_list}
        if len(self._runners) != len(runner_list):
            raise ValueError("Trusted publisher runner IDs must be unique")
        if not self._runners:
            raise ValueError("At least one trusted publisher runner is required")
        if max_evidence_age <= timedelta(0):
            raise ValueError("max_evidence_age must be positive")
        if future_clock_skew < timedelta(0):
            raise ValueError("future_clock_skew cannot be negative")
        if max_evidence_records < 1:
            raise ValueError("max_evidence_records must be positive")
        self._max_evidence_age = max_evidence_age
        self._future_clock_skew = future_clock_skew
        self._max_evidence_records = max_evidence_records

    def verify_all(
        self,
        evidence: Iterable[CertificationTestEvidence],
        *,
        manifest_digest: str,
        validation_report_id: str,
        now: datetime | None = None,
    ) -> list[CertificationTestEvidence]:
        """Return verified evidence or reject the entire supplied batch."""

        items = list(evidence)
        if any(not isinstance(item, CertificationTestEvidence) for item in items):
            raise ValueError(
                "Publisher evidence must contain CertificationTestEvidence values"
            )
        if len(items) > self._max_evidence_records:
            raise ValueError("Too many publisher test evidence records")
        evidence_ids = [item.evidence_id for item in items]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Publisher test evidence IDs must be unique")
        checked_at = now or datetime.now(UTC)
        if (
            not isinstance(checked_at, datetime)
            or checked_at.tzinfo is None
            or checked_at.utcoffset() is None
        ):
            raise ValueError("Evidence verification time must be timezone-aware")
        return [
            self.verify(
                item,
                manifest_digest=manifest_digest,
                validation_report_id=validation_report_id,
                now=checked_at,
            )
            for item in items
        ]

    def verify(
        self,
        evidence: CertificationTestEvidence,
        *,
        manifest_digest: str,
        validation_report_id: str,
        now: datetime | None = None,
    ) -> CertificationTestEvidence:
        """Verify one evidence record without trusting publisher assertions."""

        if evidence.source is not CertificationEvidenceSource.PUBLISHER:
            raise ValueError("Publisher test evidence must use the publisher source")
        signature = evidence.signature
        if signature is None:
            raise ValueError("Publisher test evidence must be signed")
        runner = self._runners.get(evidence.runner_id)
        if runner is None:
            raise ValueError("Publisher test evidence runner is not trusted")
        if evidence.suite_id not in runner.allowed_suite_ids:
            raise ValueError("Publisher test evidence suite is not trusted")
        if signature.signer_id != runner.signer_id:
            raise ValueError("Publisher test evidence signer does not match the runner")
        if signature.algorithm is not runner.crypto_handler.algorithm:
            raise ValueError(
                "Publisher test evidence signature algorithm is not trusted"
            )
        if signature.key_id != runner.key_id:
            raise ValueError("Publisher test evidence key is not trusted")
        if evidence.manifest_digest != manifest_digest:
            raise ValueError("Publisher test evidence manifest binding does not match")
        if (
            evidence.validation_report_id
            and evidence.validation_report_id != validation_report_id
        ):
            raise ValueError("Publisher test evidence report binding does not match")

        checked_at = now or datetime.now(UTC)
        if (
            not isinstance(checked_at, datetime)
            or checked_at.tzinfo is None
            or checked_at.utcoffset() is None
        ):
            raise ValueError("Evidence verification time must be timezone-aware")
        if evidence.generated_at > checked_at + self._future_clock_skew:
            raise ValueError("Publisher test evidence generation time is in the future")
        if checked_at - evidence.generated_at > self._max_evidence_age:
            raise ValueError("Publisher test evidence has expired")
        if not runner.crypto_handler.verify(evidence.signable_payload(), signature):
            raise ValueError("Publisher test evidence signature is invalid")
        return evidence


@runtime_checkable
class CertificationTestSuite(Protocol):
    """Operator-configured suite that emits manifest-bound test evidence."""

    suite_id: str
    suite_version: str
    source: CertificationEvidenceSource
    runner_id: str

    def run(
        self,
        manifest: SecurityManifest,
        report: ValidationReport,
        *,
        manifest_digest: str,
    ) -> CertificationTestEvidence:
        """Run the suite and return evidence for the exact manifest digest."""


_STANDARD_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("required_fields", "structure"),
    ("permission_consistency", "permissions"),
    ("data_flow_safety", "data_flow"),
    ("resource_access", "resource_access"),
    ("security_practices", "best_practices"),
)


@dataclass(frozen=True)
class StandardCertificationTestSuite:
    """Stable SecureMCP suite over the built-in manifest validation domains.

    The suite deliberately evaluates the already-produced validation report
    instead of executing publisher code or contacting publisher endpoints.
    Runtime and publisher-supplied functional tests belong to higher assurance
    tiers and require a separately trusted runner.
    """

    suite_id: str = "securemcp-standard"
    suite_version: str = "1.0.0"
    source: CertificationEvidenceSource = CertificationEvidenceSource.SECUREMCP
    runner_id: str = "securemcp.certification.standard"

    def run(
        self,
        manifest: SecurityManifest,
        report: ValidationReport,
        *,
        manifest_digest: str,
    ) -> CertificationTestEvidence:
        del manifest
        results: list[CertificationTestResult] = []
        blocking_severities = {"error", "critical"}

        internal_findings = [
            finding for finding in report.findings if finding.category == "internal"
        ]
        results.append(
            CertificationTestResult(
                test_id="suite_integrity",
                status=(
                    CertificationTestStatus.ERROR
                    if internal_findings
                    else CertificationTestStatus.PASSED
                ),
                summary=(
                    f"{len(internal_findings)} validation rule error(s) occurred"
                    if internal_findings
                    else "All configured validation rules completed"
                ),
            )
        )

        for test_id, category in _STANDARD_CATEGORIES:
            findings = [
                finding for finding in report.findings if finding.category == category
            ]
            blockers = [
                finding
                for finding in findings
                if finding.severity.value in blocking_severities
            ]
            advisory_count = len(findings) - len(blockers)
            if blockers:
                status = CertificationTestStatus.FAILED
                summary = f"{len(blockers)} blocking finding(s)"
            elif advisory_count:
                status = CertificationTestStatus.PASSED
                summary = f"Passed with {advisory_count} advisory finding(s)"
            else:
                status = CertificationTestStatus.PASSED
                summary = "Passed without findings"
            results.append(
                CertificationTestResult(
                    test_id=test_id,
                    status=status,
                    summary=summary,
                )
            )

        return CertificationTestEvidence(
            suite_id=self.suite_id,
            suite_version=self.suite_version,
            source=self.source,
            runner_id=self.runner_id,
            manifest_digest=manifest_digest,
            validation_report_id=report.report_id,
            results=tuple(results),
        )


def assurance_tier_for_evidence(
    evidence: list[CertificationTestEvidence],
) -> AssuranceTier:
    """Return the highest fully passing operator-provided evidence tier."""

    standard = [
        item
        for item in evidence
        if item.source is CertificationEvidenceSource.SECUREMCP
    ]
    if not standard or not all(item.passed for item in standard):
        return AssuranceTier.STATIC_ANALYSIS

    publisher = [
        item
        for item in evidence
        if item.source is CertificationEvidenceSource.PUBLISHER
    ]
    reviewer = [
        item for item in evidence if item.source is CertificationEvidenceSource.REVIEWER
    ]
    if reviewer and all(item.passed for item in reviewer):
        return AssuranceTier.MANUAL_REVIEWED
    if publisher and all(item.passed for item in publisher):
        return AssuranceTier.PUBLISHER_TESTED
    return AssuranceTier.STANDARD_TESTED


__all__ = [
    "AssuranceTier",
    "CertificationEvidenceSource",
    "CertificationTestEvidence",
    "CertificationTestResult",
    "CertificationTestStatus",
    "CertificationTestSuite",
    "PublisherEvidenceVerifier",
    "StandardCertificationTestSuite",
    "TrustedPublisherTestRunner",
    "assurance_tier_for_evidence",
]
