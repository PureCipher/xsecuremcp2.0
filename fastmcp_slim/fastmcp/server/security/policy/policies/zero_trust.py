"""Exact grants and trusted per-request posture for Zero Trust authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fastmcp.server.security.policy.policies.ferpa_request import request_digest
from fastmcp.server.security.policy.provider import (
    Citation,
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)


@dataclass(frozen=True)
class ZeroTrustEvidence:
    issuer: str
    scope_id: str
    actor_id: str
    action: str
    resource_id: str
    request_digest: str
    verified_at: datetime
    expires_at: datetime
    session_active: bool
    device_compliant: bool
    risk_acceptable: bool


@dataclass(frozen=True)
class ZeroTrustGrant:
    actor_id: str
    resource_id: str
    actions: frozenset[str]

    def __post_init__(self) -> None:
        values = (self.actor_id, self.resource_id, *self.actions)
        if not self.actions or any(
            not isinstance(v, str) or not v.strip() or any(c in v for c in "*?[]")
            for v in values
        ):
            raise ValueError(
                "Zero Trust grants require exact nonempty identities, resources and actions; patterns are forbidden"
            )


@dataclass
class ZeroTrustPolicy:
    grants: tuple[ZeroTrustGrant, ...] = ()
    trusted_issuers: frozenset[str] = field(default_factory=frozenset)
    scope_id: str = ""
    max_evidence_age_seconds: int = 60
    policy_id: str = "zero-trust-request-validation"
    version: str = "2.0.0"

    def __post_init__(self) -> None:
        if (
            type(self.max_evidence_age_seconds) is not int
            or not 1 <= self.max_evidence_age_seconds <= 300
        ):
            raise ValueError("Evidence age must be between 1 and 300 seconds")

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(allowed: bool, reason: str) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"Zero Trust {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="NIST",
                        article="SP 800-207, Section 2.1",
                        url="https://doi.org/10.6028/NIST.SP.800-207",
                        version="August 2020",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        if not context.actor_id or not any(
            g.actor_id == context.actor_id
            and g.resource_id == context.resource_id
            and context.action in g.actions
            for g in self.grants
        ):
            return result(False, "No exact actor/resource/action grant")
        evidence = context.zero_trust_evidence
        if not isinstance(evidence, ZeroTrustEvidence):
            return result(False, "Trusted request evidence is required")
        if (
            not self.scope_id
            or evidence.scope_id != self.scope_id
            or evidence.issuer not in self.trusted_issuers
        ):
            return result(False, "Untrusted issuer or server/tenant scope")
        try:
            if (
                evidence.actor_id,
                evidence.resource_id,
                evidence.action,
                evidence.request_digest,
            ) != (
                context.actor_id,
                context.resource_id,
                context.action,
                request_digest(context.metadata),
            ):
                return result(False, "Evidence does not match request")
            times = (context.timestamp, evidence.verified_at, evidence.expires_at)
            if any(t.tzinfo is None or t.utcoffset() is None for t in times):
                return result(False, "Timezone-aware evidence is required")
            if (
                not evidence.verified_at <= context.timestamp < evidence.expires_at
                or context.timestamp - evidence.verified_at
                > timedelta(seconds=self.max_evidence_age_seconds)
            ):
                return result(False, "Expired, stale or future-dated evidence")
        except (TypeError, ValueError, OverflowError):
            return result(False, "Invalid request evidence")
        if (
            evidence.session_active is not True
            or evidence.device_compliant is not True
            or evidence.risk_acceptable is not True
        ):
            return result(False, "Session, device or risk conditions failed")
        return result(True, "Exact grant and current posture verified")

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version
