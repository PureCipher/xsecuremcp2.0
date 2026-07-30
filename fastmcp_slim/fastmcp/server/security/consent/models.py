"""Data models for the Consent Graph.

Defines consent nodes, edges, scopes, and delegation rules
for federated access-rights management.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConsentStatus(Enum):
    """Status of a consent grant."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class NodeType(Enum):
    """Types of nodes in the consent graph."""

    AGENT = "agent"
    RESOURCE = "resource"
    SCOPE = "scope"
    GROUP = "group"
    INSTITUTION = "institution"


class ConsentScope(Enum):
    """Common consent scopes for MCP operations."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    LIST = "list"
    ADMIN = "admin"
    DELEGATE = "delegate"


@dataclass
class ConsentCondition:
    """A condition that must be met for consent to be valid.

    Attributes:
        condition_id: Unique identifier.
        expression: A string expression evaluated at access time.
        description: Human-readable explanation.
        metadata: Additional context for evaluation.
    """

    condition_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    expression: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate the condition against a context dict.

        Uses a restricted eval for simple expressions. Returns False
        on any evaluation error (fail-closed).
        """
        if not self.expression:
            return True
        try:
            allowed_builtins = {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "all": all,
                "any": any,
                "True": True,
                "False": False,
                "None": None,
            }
            return bool(
                eval(self.expression, {"__builtins__": allowed_builtins}, context)
            )
        except Exception:
            return False


@dataclass(frozen=True)
class ConsentNode:
    """A node in the consent graph.

    Represents an agent, resource, scope, or group that participates
    in consent relationships.

    Attributes:
        node_id: Unique identifier for this node.
        node_type: The type of entity this node represents.
        label: Human-readable label.
        metadata: Additional properties.
    """

    node_id: str = ""
    node_type: NodeType = NodeType.AGENT
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsentEdge:
    """A directed consent grant from one node to another.

    Represents that the source grants the target access under
    specific scopes, conditions, and time constraints.

    Attributes:
        edge_id: Unique identifier.
        source_id: The granting node.
        target_id: The node receiving access.
        scopes: Set of granted scopes.
        status: Current status of this consent.
        conditions: Conditions that must be met.
        granted_at: When consent was granted.
        expires_at: When consent expires (None = no expiry).
        granted_by: Who authorized this consent.
        delegatable: Whether the target can further delegate.
        max_delegation_depth: How many levels of delegation are allowed.
        delegation_depth: Current delegation depth (0 = direct grant).
        parent_edge_id: If delegated, the edge this was delegated from.
        metadata: Additional context.
    """

    edge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_id: str = ""
    target_id: str = ""
    scopes: set[str] = field(default_factory=set)
    status: ConsentStatus = ConsentStatus.ACTIVE
    conditions: list[ConsentCondition] = field(default_factory=list)
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    granted_by: str = ""
    delegatable: bool = False
    max_delegation_depth: int = 0
    delegation_depth: int = 0
    parent_edge_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid(self, now: datetime | None = None) -> bool:
        """Check if this consent edge is currently valid."""
        if self.status != ConsentStatus.ACTIVE:
            return False
        if self.expires_at is not None:
            check_time = now or datetime.now(timezone.utc)
            if check_time >= self.expires_at:
                return False
        return True

    def can_delegate(self) -> bool:
        """Check if this consent can be further delegated."""
        if not self.delegatable:
            return False
        if self.max_delegation_depth > 0:
            return self.delegation_depth < self.max_delegation_depth
        return True

    def check_conditions(self, context: dict[str, Any]) -> bool:
        """Evaluate all conditions. All must pass (AND logic)."""
        return all(c.evaluate(context) for c in self.conditions)


@dataclass
class ConsentQuery:
    """A query to check consent in the graph.

    Attributes:
        source_id: The node granting access (e.g., resource owner).
        target_id: The node requesting access (e.g., agent).
        scope: The scope being requested.
        context: Additional context for condition evaluation.
        allow_delegation: Whether to follow delegation chains.
    """

    source_id: str = ""
    target_id: str = ""
    scope: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    allow_delegation: bool = True


@dataclass
class ConsentDecision:
    """Result of a consent evaluation.

    Attributes:
        granted: Whether consent was granted.
        path: The chain of edges that granted consent (empty if denied).
        reason: Explanation for the decision.
        evaluated_at: When the decision was made.
    """

    granted: bool = False
    path: list[ConsentEdge] = field(default_factory=list)
    reason: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Federated Consent Graph models
# ---------------------------------------------------------------------------


@dataclass
class JurisdictionPolicy:
    """Compliance policy for a geographic jurisdiction.

    Defines which regulations apply and what consent scopes must be
    satisfied before data processing or model execution can proceed
    within or across this jurisdiction.

    Attributes:
        jurisdiction_id: Unique identifier (e.g., ``"eu-001"``).
        jurisdiction_code: ISO 3166-1/2 region code (e.g., ``"EU"``, ``"US-CA"``).
        applicable_regulations: Regulation names (e.g., ``["GDPR"]``).
        required_consent_scopes: Scopes that must be granted before access.
        requires_explicit_consent: Whether consent must be explicit (opt-in).
        data_residency_required: If set, processing must occur in this
            jurisdiction code.
        metadata: Additional policy data.
    """

    jurisdiction_id: str = ""
    jurisdiction_code: str = ""
    applicable_regulations: list[str] = field(default_factory=list)
    required_consent_scopes: list[str] = field(default_factory=list)
    requires_explicit_consent: bool = True
    data_residency_required: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeographicContext:
    """Geographic context for a consent evaluation.

    Identifies all jurisdictions involved in a data flow so the
    federated consent engine can determine which policies must be
    satisfied.

    Attributes:
        source_jurisdiction: Where data originates (e.g., ``"EU"``).
        target_jurisdiction: Where the agent/processor is located.
        data_residency: Where data must be stored/processed.
        processing_location: Where actual computation occurs.
        metadata: Additional context.
    """

    source_jurisdiction: str = ""
    target_jurisdiction: str = ""
    data_residency: str | None = None
    processing_location: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def applicable_jurisdictions(self) -> set[str]:
        """Return all unique, non-empty jurisdictions in this context."""
        result: set[str] = set()
        for val in [
            self.source_jurisdiction,
            self.target_jurisdiction,
            self.data_residency,
            self.processing_location,
        ]:
            if val:
                result.add(val)
        return result


@dataclass
class JurisdictionResult:
    """Result of evaluating one jurisdiction's policy.

    Attributes:
        jurisdiction_code: Which jurisdiction was evaluated.
        satisfied: Whether policy requirements are met.
        required_scopes: Scopes the policy requires.
        satisfied_scopes: Scopes that were granted.
        missing_scopes: Scopes still needed.
        applicable_regulations: Regulations in effect.
        reason: Human-readable explanation.
    """

    jurisdiction_code: str = ""
    satisfied: bool = False
    required_scopes: list[str] = field(default_factory=list)
    satisfied_scopes: list[str] = field(default_factory=list)
    missing_scopes: list[str] = field(default_factory=list)
    applicable_regulations: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class AccessRights:
    """Computed access rights for an agent on a resource.

    Produced by the federated consent engine after evaluating all
    applicable jurisdiction policies and peer consent decisions.

    Attributes:
        agent_id: The requesting actor.
        resource_id: The target resource.
        allowed_scopes: Scopes this agent may exercise.
        jurisdiction_constraints: Per-jurisdiction scope restrictions.
        expires_at: When these rights expire.
        conditions: Human-readable conditions that apply.
        grant_sources: Which institutions/peers contributed to the grant.
    """

    agent_id: str = ""
    resource_id: str = ""
    allowed_scopes: list[str] = field(default_factory=list)
    jurisdiction_constraints: dict[str, list[str]] = field(default_factory=dict)
    expires_at: datetime | None = None
    conditions: list[str] = field(default_factory=list)
    grant_sources: list[str] = field(default_factory=list)


@dataclass
class FederatedConsentQuery:
    """Query for federated consent evaluation.

    Extends the local ``ConsentQuery`` with geographic context and
    federation parameters so the engine can coordinate across
    institutions and jurisdictions.

    Attributes:
        source_id: Node granting access (resource owner).
        target_id: Node requesting access (agent).
        scope: The scope being requested.
        context: Evaluation context for conditions.
        geographic_context: Jurisdiction information for the data flow.
        jurisdictions: Explicit jurisdiction filter (``None`` = auto-detect).
        require_all_jurisdictions: If ``True``, ALL jurisdictions must
            approve; if ``False``, ANY is sufficient.
        allow_delegation: Follow delegation chains in local graph.
        include_peers: Query federated peers for their consent decisions.
    """

    source_id: str = ""
    target_id: str = ""
    scope: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    geographic_context: GeographicContext = field(default_factory=GeographicContext)
    jurisdictions: list[str] | None = None
    require_all_jurisdictions: bool = True
    allow_delegation: bool = True
    include_peers: bool = True


@dataclass
class FederatedConsentDecision:
    """Result of a federated consent evaluation.

    Captures the local decision, per-jurisdiction results, peer
    decisions, and the computed access rights when granted.

    Attributes:
        granted: Whether access is allowed.
        local_decision: ``ConsentDecision`` from the local graph.
        jurisdiction_results: Per-jurisdiction evaluation results.
        peer_decisions: ``ConsentDecision`` objects from federated peers.
        access_rights: Computed access rights (populated when granted).
        reason: Explanation of the decision.
        evaluated_at: Timestamp of evaluation.
    """

    granted: bool = False
    local_decision: ConsentDecision | None = None
    jurisdiction_results: dict[str, JurisdictionResult] = field(default_factory=dict)
    peer_decisions: dict[str, ConsentDecision] = field(default_factory=dict)
    access_rights: AccessRights | None = None
    reason: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
