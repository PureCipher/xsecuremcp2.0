"""Validate externally authorized changes without implementing approval workflows."""

from dataclasses import dataclass, field, replace
from datetime import datetime

from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustEvidence,
    ZeroTrustPolicy,
)
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

CHANGE_ACTIONS = frozenset({"submit_listing", "review_listing", "manage_policy"})
MCP_ACTIONS = frozenset(
    {
        "call_tool",
        "read_resource",
        "get_prompt",
        "list_tools",
        "list_resources",
        "list_resource_templates",
        "list_prompts",
    }
)
READ_EFFECTS = frozenset({"read", "compute"})
CHANGE_EFFECTS = frozenset({"write", "delete", "configure", "deploy"})


@dataclass(frozen=True)
class ChangeEvidence(ZeroTrustEvidence):
    effects: frozenset[str]
    facts: frozenset[str] = field(default_factory=frozenset)
    approval_id: str = ""
    requester_id: str = ""
    approver_id: str = ""
    approval_request_digest: str = ""
    approval_action: str = ""
    approval_resource_id: str = ""
    approval_revoked: bool = True
    approval_issued_at: datetime | None = None
    approval_expires_at: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@dataclass
class StrictChangePolicy(ZeroTrustPolicy):
    policy_id: str = "strict-change-control"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(allowed: bool, reason: str) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"Strict Change Control {self.version}: {reason}",
                policy_id=self.policy_id,
            )

        if context.action not in CHANGE_ACTIONS | MCP_ACTIONS:
            return result(False, "Unknown operation is not permitted")
        e = context.change_evidence
        if not isinstance(e, ChangeEvidence):
            return result(False, "Trusted operation evidence is required")
        admission = await super().evaluate(replace(context, zero_trust_evidence=e))
        if admission.decision != PolicyDecision.ALLOW:
            return result(False, admission.reason.split(": ", 1)[-1])
        if (
            not isinstance(e.effects, frozenset)
            or not e.effects
            or not e.effects <= READ_EFFECTS | CHANGE_EFFECTS
        ):
            return result(False, "Complete operation effects must be classified")
        if (
            not isinstance(e.facts, frozenset)
            or not {
                "complete_effect_and_target_scope_verified",
                "audit_capture_available",
            }
            <= e.facts
        ):
            return result(False, "Target scope and audit capture must be verified")
        if context.action not in CHANGE_ACTIONS and e.effects <= READ_EFFECTS:
            return result(
                True, "Exact read/compute access verified; no change approval required"
            )
        if any(
            not isinstance(v, str) or not v.strip()
            for v in (e.approval_id, e.requester_id, e.approver_id)
        ):
            return result(
                False,
                "Change requires an identified requester and independent approver",
            )
        if e.approver_id in {context.actor_id, e.requester_id}:
            return result(False, "Self-approval is not permitted")
        if e.approval_revoked is not False:
            return result(False, "Approval is revoked or its status is unknown")
        if (e.approval_request_digest, e.approval_action, e.approval_resource_id) != (
            e.request_digest,
            context.action,
            context.resource_id,
        ):
            return result(False, "Approval does not cover this exact request")
        times = (
            e.approval_issued_at,
            e.approval_expires_at,
            e.window_start,
            e.window_end,
        )
        if any(
            not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None
            for t in times
        ):
            return result(
                False, "Timezone-aware approval and execution-window times are required"
            )
        assert e.approval_issued_at is not None and e.approval_expires_at is not None
        assert e.window_start is not None and e.window_end is not None
        if not (
            e.approval_issued_at <= context.timestamp < e.approval_expires_at
            and e.window_start <= context.timestamp < e.window_end
        ):
            return result(
                False, "Approval is not current or the execution window is closed"
            )
        required = {
            "approver_authority_verified",
            "separation_of_duties_verified",
            "approved_change_scope_verified",
            "change_validation_verified",
            "recovery_controls_verified",
        }
        if not required <= e.facts:
            return result(
                False,
                "Approval authority, independence, validation or recovery evidence is missing",
            )
        return result(
            True, "Exact authorized change is within its verified execution window"
        )
