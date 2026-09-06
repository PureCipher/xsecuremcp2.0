"""Verified publication and read-only effects for tool catalog access."""

import re
from dataclasses import dataclass, replace

from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustEvidence,
    ZeroTrustPolicy,
)
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)


@dataclass(frozen=True)
class PublishedToolEvidence(ZeroTrustEvidence):
    listing_id: str
    listing_version: str
    manifest_digest: str
    publication_status: str
    revoked: bool
    signature_valid: bool
    component_binding_verified: bool
    effects: frozenset[str]


@dataclass
class PublishedToolsPolicy(ZeroTrustPolicy):
    policy_id: str = "published-tools-only"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(allowed: bool, reason: str) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"Published Tools {self.version}: {reason}",
                policy_id=self.policy_id,
            )

        if context.action not in {"call_tool", "list_tools"}:
            return result(
                False, "This pack permits tool discovery and read-only tool calls only"
            )
        e = context.published_tool_evidence
        if not isinstance(e, PublishedToolEvidence):
            return result(False, "Trusted publication evidence is required")
        admission = await super().evaluate(replace(context, zero_trust_evidence=e))
        if admission.decision != PolicyDecision.ALLOW:
            return result(False, admission.reason.split(": ", 1)[-1])
        if any(
            not isinstance(v, str) or not v.strip()
            for v in (e.listing_id, e.listing_version)
        ):
            return result(False, "Exact listing identity and version are required")
        if (
            not isinstance(e.manifest_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", e.manifest_digest) is None
        ):
            return result(False, "A verified SHA-256 manifest digest is required")
        if e.publication_status != "published" or e.revoked is not False:
            return result(False, "Listing is unpublished or revoked")
        if e.signature_valid is not True or e.component_binding_verified is not True:
            return result(
                False,
                "Signature and exact component-to-manifest binding must be verified",
            )
        if (
            not isinstance(e.effects, frozenset)
            or not e.effects
            or not e.effects <= {"read", "compute"}
        ):
            return result(False, "Unknown or mutating effects are not permitted")
        return result(True, "Published, verified, read-only tool authorized")
