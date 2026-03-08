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
