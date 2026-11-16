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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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

    def __post_init__(self) -> None:
        for field_name in (
            "suite_id",
            "suite_version",
            "runner_id",
            "manifest_digest",
            "validation_report_id",
            "evidence_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be nonempty")
        if (
            not isinstance(self.source, CertificationEvidenceSource)
            or not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            if not isinstance(self.source, CertificationEvidenceSource):
                raise ValueError("source must be a CertificationEvidenceSource")
            raise ValueError("generated_at must be timezone-aware")
        object.__setattr__(self, "results", tuple(self.results))
        if not self.results:
            raise ValueError("results must contain at least one test result")
        if any(
            not isinstance(result, CertificationTestResult) for result in self.results
        ):
            raise ValueError("results must contain CertificationTestResult values")

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "source": self.source.value,
            "runner_id": self.runner_id,
            "manifest_digest": self.manifest_digest,
            "validation_report_id": self.validation_report_id,
            "generated_at": self.generated_at.isoformat(),
            "passed": self.passed,
            "counts": self.counts,
            "results": [result.to_dict() for result in self.results],
        }

    @property
    def digest(self) -> str:
        """Deterministic SHA-256 digest binding the complete evidence record."""

        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


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

    if not evidence or not all(item.passed for item in evidence):
        return AssuranceTier.STATIC_ANALYSIS

    sources = {item.source for item in evidence}
    if CertificationEvidenceSource.REVIEWER in sources:
        return AssuranceTier.MANUAL_REVIEWED
    if CertificationEvidenceSource.PUBLISHER in sources:
        return AssuranceTier.PUBLISHER_TESTED
    if CertificationEvidenceSource.SECUREMCP in sources:
        return AssuranceTier.STANDARD_TESTED
    return AssuranceTier.STATIC_ANALYSIS


__all__ = [
    "AssuranceTier",
    "CertificationEvidenceSource",
    "CertificationTestEvidence",
    "CertificationTestResult",
    "CertificationTestStatus",
    "CertificationTestSuite",
    "StandardCertificationTestSuite",
    "assurance_tier_for_evidence",
]
