"""Policy provider protocol for SecureMCP.

Policy providers are pluggable sources of governance rules. They can be
hot-swapped at runtime without service downtime.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class PolicyDecision(Enum):
    """Result of a policy evaluation.

    Most providers use ALLOW / DENY / DEFER. Capability-aware providers
    (Rego, Cedar, CapabilityPolicy) may additionally return
    REQUIRE_APPROVAL to signal that the action is not forbidden but
    cannot execute without an explicit human approval ticket. The
    PolicyEngine short-circuits on REQUIRE_APPROVAL the same way it
    does on DENY — callers must re-submit with ``approval=true`` in
    the context to get ALLOW back.
    """

    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"
    REQUIRE_APPROVAL = "require_approval"


# Marker strings used by capability-aware providers. Kept loose so
# Rego/Cedar policies don't have to import the enum to classify risk.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

ENVIRONMENT_PRODUCTION = "production"
ENVIRONMENT_STAGING = "staging"
ENVIRONMENT_DEVELOPMENT = "development"


@dataclass(frozen=True)
class PolicyEvaluationContext:
    """Context passed to policy providers for evaluation.

    The core (actor_id/action/resource_id/metadata/timestamp/tags)
    predates capability-style authz and remains canonical — all
    providers can read from it.

    The capability fields (environment/risk/approval_*/principal_type/
    resource_type) were added when the kernel grew Rego/Cedar support.
    They default to values that make the capability-aware providers a
    no-op on legacy call sites: ``environment="production"`` errs
    safely toward deny-by-default when the caller forgot to plumb
    environment, and ``approval_granted=False`` means an action that
    would REQUIRE_APPROVAL stays required until the caller opts in.

    Providers that don't care about capability fields should just
    keep reading actor_id/action/resource_id/tags — they'll ignore
    the additions completely.

    Attributes:
        actor_id: Identifier of the agent/model making the request.
        action: The operation being performed (e.g., "call_tool", "read_resource").
        resource_id: The target component name or URI.
        metadata: Additional context (tool arguments, resource params, etc.).
        timestamp: When the request was received.
        tags: Tags on the component being accessed.
        principal_type: Classification of the actor (``agent``, ``user``,
            ``service``). Used by Cedar-style matchers.
        resource_type: Classification of the resource (``tool``,
            ``resource``, ``prompt``, ``database``, ``cluster``,
            ``secret``, ``deployment``). Used by Cedar-style matchers.
        environment: Deployment environment — ``production``,
            ``staging``, ``development``. Defaults to ``production``
            so unsecured call sites err safely.
        risk: Declared risk level — ``low``, ``medium``, ``high``,
            ``critical``. Capability providers may override this by
            pattern-matching on action/resource.
        approval_granted: Whether a human approver has countersigned
            the action. The CapabilityPolicy turns a ``REQUIRE_APPROVAL``
            into ALLOW when this is True *and* an ``approval_ticket``
            is present in metadata.
        approval_ticket: Opaque ticket id proving the approval is
            attached to this specific action. Audited.
    """

    actor_id: str | None
    action: str
    resource_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: frozenset[str] = field(default_factory=frozenset)
    principal_type: str = "agent"
    resource_type: str = "tool"
    environment: str = ENVIRONMENT_PRODUCTION
    risk: str = RISK_LOW
    approval_granted: bool = False
    approval_ticket: str | None = None
    # Server-supplied evidence; never populated from request metadata.
    ferpa_evidence: Any = None
    zero_trust_evidence: Any = None
    pci_evidence: Any = None
    ccpa_evidence: Any = None


@dataclass(frozen=True)
class Citation:
    """Structured reference to an official regulation or standard.

    Attached to compliance rules so that every ALLOW/DENY decision
    can be traced back to the exact authoritative text that motivated
    the rule. Audit entries carry the citation forward; downstream
    reporting can then aggregate denials by ``source``/``article``
    without reparsing free-text descriptions.

    The intent is mechanical queryability — writing the article
    reference the same way every time, with a URL operators can
    click through to read the source, and a version string so that
    when the underlying regulation is revised the audit trail still
    records which revision the rule was enforcing against.

    Attributes:
        source: Short regulation identifier — e.g. ``"GDPR"``,
            ``"HIPAA"``, ``"SOC2"``, ``"PCI-DSS"``, ``"ISO-27001"``,
            ``"NIST-800-53"``.
        article: Exact article/section/control reference, written the
            way the official text numbers it. Examples:
            ``"Article 6(1)(a)"``, ``"45 CFR 164.308(a)(3)"``,
            ``"A.8.2"``, ``"AC-6"``.
        url: Canonical URL to the authoritative source (EUR-Lex, HHS,
            AICPA, PCI SSC, ISO, NIST, etc.). URLs must point at the
            primary regulation body's own publication — not an
            aggregator or summary site.
        version: Version/edition of the regulation this rule was
            authored against. Examples: ``"2016/679"`` (GDPR),
            ``"v4.0"`` (PCI DSS), ``"2022"`` (ISO 27001),
            ``"Rev 5"`` (NIST 800-53).
        retrieved_at: ISO-8601 date the rule author last verified the
            cited text against the source. Empty string when unset.
    """

    source: str
    article: str
    url: str = ""
    version: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> dict[str, str]:
        """JSON-friendly projection. Empty fields are preserved so the
        shape is stable across rules (a query like
        ``entry.citations[0].version`` never hits a missing key).
        """
        return {
            "source": self.source,
            "article": self.article,
            "url": self.url,
            "version": self.version,
            "retrieved_at": self.retrieved_at,
        }


@dataclass(frozen=True)
class PolicyResult:
    """Result of a single policy evaluation.

    Attributes:
        decision: Whether the action is allowed, denied, or deferred.
        reason: Human-readable explanation for the decision.
        policy_id: Identifier of the policy that produced this result.
        evaluated_at: When the evaluation was performed.
        constraints: Any constraints that apply to the allowed action.
        citations: Structured regulation references attached by
            compliance providers. Empty for providers that aren't
            regulation-backed (e.g. allowlist, RBAC).
    """

    decision: PolicyDecision
    reason: str
    policy_id: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    constraints: list[str] = field(default_factory=list)
    citations: tuple[Citation, ...] = field(default_factory=tuple)


@runtime_checkable
class PolicyProvider(Protocol):
    """Protocol for pluggable policy providers.

    Implementations can be synchronous or asynchronous. The PolicyEngine
    handles both transparently.

    Example::

        class MyPolicy:
            async def evaluate(
                self, context: PolicyEvaluationContext
            ) -> PolicyResult:
                if "admin" in context.tags:
                    return PolicyResult(
                        decision=PolicyDecision.ALLOW,
                        reason="Admin access granted",
                        policy_id="my-policy-v1",
                    )
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason="Insufficient privileges",
                    policy_id="my-policy-v1",
                )

            async def get_policy_id(self) -> str:
                return "my-policy-v1"

            async def get_policy_version(self) -> str:
                return "1.0.0"
    """

    def evaluate(
        self, context: PolicyEvaluationContext
    ) -> PolicyResult | Awaitable[PolicyResult]: ...

    def get_policy_id(self) -> str | Awaitable[str]: ...

    def get_policy_version(self) -> str | Awaitable[str]: ...


class AllowAllPolicy:
    """A policy provider that allows all requests. Useful as a default."""

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Default allow-all policy",
            policy_id="allow-all",
        )

    async def get_policy_id(self) -> str:
        return "allow-all"

    async def get_policy_version(self) -> str:
        return "1.0.0"


class DenyAllPolicy:
    """A policy provider that denies all requests. Useful for lockdown scenarios."""

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason="Default deny-all policy",
            policy_id="deny-all",
        )

    async def get_policy_id(self) -> str:
        return "deny-all"

    async def get_policy_version(self) -> str:
        return "1.0.0"
