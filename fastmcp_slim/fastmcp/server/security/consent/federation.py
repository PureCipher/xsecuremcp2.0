"""Federated Consent Graph for SecureMCP.

Bridges the local ConsentGraph with the TrustFederation system to enable
dynamic computation of access rights across institutions and geographic
jurisdictions.  Model input and execution proceed only when every relevant
jurisdiction's policies are satisfied.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastmcp.server.security.consent.graph import ConsentGraph
from fastmcp.server.security.consent.models import (
    AccessRights,
    ConsentDecision,
    ConsentEdge,
    ConsentNode,
    ConsentQuery,
    FederatedConsentDecision,
    FederatedConsentQuery,
    GeographicContext,
    JurisdictionPolicy,
    JurisdictionResult,
    NodeType,
)
from fastmcp.server.security.federation.federation import (
    PeerStatus,
    TrustFederation,
)

if TYPE_CHECKING:
    from fastmcp.server.security.alerts.bus import SecurityEventBus

logger = logging.getLogger(__name__)


class FederatedConsentGraph:
    """Bridges ConsentGraph and TrustFederation for cross-institutional consent.

    Evaluates consent queries by first checking the local graph, then
    verifying that all applicable jurisdiction policies are satisfied,
    and optionally coordinating with federated peers.

    Example::

        fed = FederatedConsentGraph(
            local_graph=graph,
            federation=federation,
            institution_id="hospital-a",
        )

        # Register jurisdictions
        fed.register_jurisdiction_policy(JurisdictionPolicy(
            jurisdiction_id="eu-gdpr",
            jurisdiction_code="EU",
            applicable_regulations=["GDPR"],
            required_consent_scopes=["read", "execute"],
        ))

        # Register institutions
        fed.register_institution("hospital-a", "EU", label="Hospital A")
        fed.register_institution("hospital-b", "US-CA", label="Hospital B")

        # Evaluate federated consent
        decision = fed.evaluate_federated_consent(FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
        ))

    Args:
        local_graph: The local ConsentGraph instance.
        federation: The TrustFederation instance for peer coordination.
        jurisdiction_policies: Initial jurisdiction policies to register.
        institution_id: This institution's identifier.
        event_bus: Optional event bus for audit events.
    """

    def __init__(
        self,
        local_graph: ConsentGraph,
        federation: TrustFederation | None = None,
        *,
        jurisdiction_policies: dict[str, JurisdictionPolicy] | None = None,
        institution_id: str = "default",
        event_bus: SecurityEventBus | None = None,
    ) -> None:
        self._local_graph = local_graph
        self._federation = federation
        self._institution_id = institution_id
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._jurisdiction_policies: dict[str, JurisdictionPolicy] = dict(
            jurisdiction_policies or {}
        )
        # institution_id → jurisdiction_code mapping for quick lookups
        self._institution_jurisdictions: dict[str, str] = {}
        # Consent decisions received from peers: peer_id → list[dict]
        self._peer_consent_cache: dict[str, list[dict[str, Any]]] = {}
        # Audit trail of federated decisions
        self._audit_log: list[dict[str, Any]] = []

    # ── Properties ────────────────────────────────────────────────

    @property
    def local_graph(self) -> ConsentGraph:
        """The underlying local consent graph."""
        return self._local_graph

    @property
    def federation(self) -> TrustFederation | None:
        """The federation instance, if configured."""
        return self._federation

    @property
    def institution_id(self) -> str:
        """This institution's identifier."""
        return self._institution_id

    @property
    def jurisdiction_count(self) -> int:
        """Number of registered jurisdiction policies."""
        return len(self._jurisdiction_policies)

    @property
    def institution_count(self) -> int:
        """Number of registered institutions."""
        return len(self._institution_jurisdictions)

    # ── Institution management ────────────────────────────────────

    def register_institution(
        self,
        institution_id: str,
        jurisdiction_code: str,
        *,
        label: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConsentNode:
        """Register an institutional node in the consent graph.

        Creates an ``INSTITUTION``-type node and records its jurisdiction
        for later policy lookups.

        Args:
            institution_id: Unique institution identifier.
            jurisdiction_code: ISO 3166 code (e.g., ``"EU"``, ``"US-CA"``).
            label: Human-readable label.
            metadata: Additional institution data.

        Returns:
            The created ConsentNode.
        """
        node_meta = dict(metadata or {})
        node_meta["jurisdiction_code"] = jurisdiction_code
        node = ConsentNode(
            node_id=institution_id,
            node_type=NodeType.INSTITUTION,
            label=label or institution_id,
            metadata=node_meta,
        )
        self._local_graph.add_node(node)
        with self._lock:
            self._institution_jurisdictions[institution_id] = jurisdiction_code
        logger.info(
            "Institution registered: %s (jurisdiction=%s)",
            institution_id,
            jurisdiction_code,
        )
        return node

    def get_institution_jurisdiction(self, institution_id: str) -> str | None:
        """Get the jurisdiction code for a registered institution."""
        return self._institution_jurisdictions.get(institution_id)

    def list_institutions(self) -> dict[str, str]:
        """Return a mapping of institution_id → jurisdiction_code."""
        return dict(self._institution_jurisdictions)

    # ── Jurisdiction policy management ────────────────────────────

    def register_jurisdiction_policy(self, policy: JurisdictionPolicy) -> None:
        """Register or update a jurisdiction's compliance policy.

        Args:
            policy: The jurisdiction policy to register.
        """
        with self._lock:
            self._jurisdiction_policies[policy.jurisdiction_code] = policy
        logger.info(
            "Jurisdiction policy registered: %s (regulations=%s)",
            policy.jurisdiction_code,
            policy.applicable_regulations,
        )

    def get_jurisdiction_policy(
        self, jurisdiction_code: str
    ) -> JurisdictionPolicy | None:
        """Retrieve a jurisdiction's policy by code."""
        return self._jurisdiction_policies.get(jurisdiction_code)

    def list_jurisdiction_policies(self) -> dict[str, JurisdictionPolicy]:
        """Return all registered jurisdiction policies."""
        return dict(self._jurisdiction_policies)

    # ── Core evaluation ───────────────────────────────────────────

    def evaluate_federated_consent(
        self,
        query: FederatedConsentQuery,
    ) -> FederatedConsentDecision:
        """Evaluate consent across institutions and jurisdictions.

        Algorithm:
            1. Determine applicable jurisdictions from geographic context.
            2. Evaluate the local consent graph.
            3. Collect granted scopes from the local decision's edge path.
            4. For each jurisdiction, check that its required scopes are
               satisfied — producing a ``JurisdictionResult`` per jurisdiction.
            5. If ``include_peers`` is True, query active federation peers.
            6. Merge: if ``require_all_jurisdictions`` is True, ALL
               jurisdiction results must be satisfied; otherwise ANY suffices.
            7. If granted, compute ``AccessRights``.
            8. Log an audit entry.

        Args:
            query: The federated consent query.

        Returns:
            A ``FederatedConsentDecision`` capturing the full evaluation.
        """
        now = datetime.now(timezone.utc)

        # 1. Determine applicable jurisdictions
        jurisdictions = self._applicable_jurisdictions_for_query(query)

        # 2. Evaluate local consent graph
        local_query = ConsentQuery(
            source_id=query.source_id,
            target_id=query.target_id,
            scope=query.scope,
            context=query.context,
            allow_delegation=query.allow_delegation,
        )
        local_decision = self._local_graph.evaluate(local_query)

        # 3. Collect granted scopes from local decision
        granted_scopes: set[str] = set()
        if local_decision.granted:
            for edge in local_decision.path:
                granted_scopes.update(edge.scopes)

        # 4. Evaluate jurisdiction policies
        jurisdiction_results = self._evaluate_jurisdiction_policies(
            granted_scopes, jurisdictions
        )

        # 5. Query peers (if configured and requested)
        peer_decisions: dict[str, ConsentDecision] = {}
        if query.include_peers and self._federation is not None:
            peer_decisions = self._query_peers_for_consent(query)

        # 6. Merge into final decision
        granted = self._merge_decision(
            local_decision=local_decision,
            jurisdiction_results=jurisdiction_results,
            peer_decisions=peer_decisions,
            require_all=query.require_all_jurisdictions,
        )

        # 7. Compute access rights if granted
        access_rights: AccessRights | None = None
        if granted:
            access_rights = self._build_access_rights(
                query=query,
                granted_scopes=granted_scopes,
                jurisdiction_results=jurisdiction_results,
                peer_decisions=peer_decisions,
                local_decision=local_decision,
            )

        reason = self._build_reason(
            granted, local_decision, jurisdiction_results, peer_decisions
        )

        decision = FederatedConsentDecision(
            granted=granted,
            local_decision=local_decision,
            jurisdiction_results=jurisdiction_results,
            peer_decisions=peer_decisions,
            access_rights=access_rights,
            reason=reason,
            evaluated_at=now,
        )

        # 8. Audit
        self._audit_decision(query, decision)

        return decision

    # ── Access rights computation ─────────────────────────────────

    def compute_access_rights(
        self,
        agent_id: str,
        resource_id: str,
        *,
        geographic_context: GeographicContext | None = None,
        scopes: list[str] | None = None,
    ) -> AccessRights:
        """Dynamically compute what an agent can do with a resource.

        Evaluates each requested scope individually and filters by
        jurisdiction constraints.

        Args:
            agent_id: The requesting actor.
            resource_id: The target resource.
            geographic_context: Jurisdiction context for the data flow.
            scopes: Scopes to check (defaults to all ``ConsentScope`` values).

        Returns:
            An ``AccessRights`` object describing allowed operations.
        """
        from fastmcp.server.security.consent.models import ConsentScope

        check_scopes = scopes or [s.value for s in ConsentScope]
        geo = geographic_context or GeographicContext()
        allowed: list[str] = []
        jurisdiction_constraints: dict[str, list[str]] = {}
        conditions: list[str] = []
        expires_at: datetime | None = None
        grant_sources: list[str] = [self._institution_id]

        for scope in check_scopes:
            query = FederatedConsentQuery(
                source_id=resource_id,
                target_id=agent_id,
                scope=scope,
                geographic_context=geo,
                require_all_jurisdictions=True,
                include_peers=False,
            )
            decision = self.evaluate_federated_consent(query)
            if decision.granted:
                allowed.append(scope)
                # Track jurisdiction constraints
                for jcode, jresult in decision.jurisdiction_results.items():
                    if jcode not in jurisdiction_constraints:
                        jurisdiction_constraints[jcode] = []
                    jurisdiction_constraints[jcode].append(scope)
                # Track conditions from edges
                if decision.local_decision and decision.local_decision.path:
                    for edge in decision.local_decision.path:
                        for cond in edge.conditions:
                            if cond.description and cond.description not in conditions:
                                conditions.append(cond.description)
                        if edge.expires_at is not None:
                            if expires_at is None or edge.expires_at < expires_at:
                                expires_at = edge.expires_at

        return AccessRights(
            agent_id=agent_id,
            resource_id=resource_id,
            allowed_scopes=allowed,
            jurisdiction_constraints=jurisdiction_constraints,
            expires_at=expires_at,
            conditions=conditions,
            grant_sources=grant_sources,
        )

    # ── Consent propagation ───────────────────────────────────────

    def propagate_consent(
        self,
        edge_id: str,
        target_peers: list[str] | None = None,
    ) -> dict[str, bool]:
        """Share a consent grant with federated peers.

        Serializes the edge and delivers it to the specified peers
        (or all active peers if ``target_peers`` is None).

        Args:
            edge_id: The consent edge to propagate.
            target_peers: Specific peer IDs, or None for all active.

        Returns:
            Dict of ``peer_id → success``.
        """
        edge = self._local_graph.get_edge(edge_id)
        if edge is None:
            return {}

        if self._federation is None:
            return {}

        edge_data = self._edge_to_propagation_dict(edge)
        results: dict[str, bool] = {}

        peers = self._federation.get_all_peers()
        for peer in peers:
            if peer.status != PeerStatus.ACTIVE:
                continue
            if target_peers is not None and peer.peer_id not in target_peers:
                continue
            # Store propagation data for the peer
            with self._lock:
                if peer.peer_id not in self._peer_consent_cache:
                    self._peer_consent_cache[peer.peer_id] = []
                self._peer_consent_cache[peer.peer_id].append(edge_data)
            results[peer.peer_id] = True
            logger.info(
                "Consent edge %s propagated to peer %s",
                edge_id,
                peer.peer_id,
            )

        self._audit_log.append(
            {
                "action": "consent_propagated",
                "edge_id": edge_id,
                "target_peers": list(results.keys()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        return results

    def receive_consent_propagation(
        self,
        peer_id: str,
        edge_data: dict[str, Any],
    ) -> ConsentEdge | None:
        """Accept a consent edge from a federated peer.

        Validates the peer is active and trusted, then inserts the edge
        into the local graph with propagation metadata.

        Args:
            peer_id: The sending peer.
            edge_data: Serialized consent edge data.

        Returns:
            The created ConsentEdge, or None if the peer is invalid.
        """
        if self._federation is None:
            return None

        peer = self._federation.get_peer(peer_id)
        if peer is None or peer.status != PeerStatus.ACTIVE:
            logger.warning(
                "Rejected consent propagation from invalid/inactive peer: %s",
                peer_id,
            )
            return None

        # Create the edge in the local graph with propagation metadata
        source_id = edge_data.get("source_id", "")
        target_id = edge_data.get("target_id", "")
        scopes = set(edge_data.get("scopes", []))
        metadata = dict(edge_data.get("metadata", {}))
        metadata["propagated_from"] = peer_id
        metadata["propagated_at"] = datetime.now(timezone.utc).isoformat()

        # Ensure nodes exist
        for nid in [source_id, target_id]:
            if self._local_graph.get_node(nid) is None:
                self._local_graph.add_node(
                    ConsentNode(node_id=nid, node_type=NodeType.AGENT, label=nid)
                )

        edge = self._local_graph.grant(
            source_id=source_id,
            target_id=target_id,
            scopes=scopes,
            metadata=metadata,
        )

        self._audit_log.append(
            {
                "action": "consent_received",
                "edge_id": edge.edge_id,
                "peer_id": peer_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        return edge

    # ── Audit ─────────────────────────────────────────────────────

    def get_audit_log(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent federated consent audit entries."""
        return list(self._audit_log[-limit:])

    # ── Private helpers ───────────────────────────────────────────

    def _applicable_jurisdictions_for_query(
        self,
        query: FederatedConsentQuery,
    ) -> set[str]:
        """Determine which jurisdictions apply to a query."""
        if query.jurisdictions is not None:
            return set(query.jurisdictions)
        return query.geographic_context.applicable_jurisdictions()

    def _evaluate_jurisdiction_policies(
        self,
        granted_scopes: set[str],
        jurisdictions: set[str],
    ) -> dict[str, JurisdictionResult]:
        """Check required scopes against each jurisdiction's policy."""
        results: dict[str, JurisdictionResult] = {}

        for jcode in jurisdictions:
            policy = self._jurisdiction_policies.get(jcode)
            if policy is None:
                # No policy registered — fail-closed
                results[jcode] = JurisdictionResult(
                    jurisdiction_code=jcode,
                    satisfied=False,
                    reason=f"No policy registered for jurisdiction {jcode}",
                )
                continue

            required = set(policy.required_consent_scopes)
            satisfied = granted_scopes & required
            missing = required - granted_scopes

            results[jcode] = JurisdictionResult(
                jurisdiction_code=jcode,
                satisfied=len(missing) == 0,
                required_scopes=sorted(required),
                satisfied_scopes=sorted(satisfied),
                missing_scopes=sorted(missing),
                applicable_regulations=list(policy.applicable_regulations),
                reason=(
                    "All required scopes satisfied"
                    if len(missing) == 0
                    else f"Missing scopes: {', '.join(sorted(missing))}"
                ),
            )

        return results

    def _query_peers_for_consent(
        self,
        query: FederatedConsentQuery,
    ) -> dict[str, ConsentDecision]:
        """Simulate querying peers for consent decisions.

        In a real deployment this would make network calls to peers.
        For now, we check the peer consent cache for any pre-stored
        decisions.
        """
        if self._federation is None:
            return {}

        decisions: dict[str, ConsentDecision] = {}
        for peer in self._federation.get_all_peers():
            if peer.status not in (PeerStatus.ACTIVE, PeerStatus.SYNCING):
                continue
            cached = self._peer_consent_cache.get(peer.peer_id, [])
            # Check if any cached edge matches the query
            for entry in cached:
                if (
                    entry.get("source_id") == query.source_id
                    and entry.get("target_id") == query.target_id
                    and query.scope in entry.get("scopes", [])
                ):
                    decisions[peer.peer_id] = ConsentDecision(
                        granted=True,
                        reason=f"Peer {peer.peer_id} granted via propagated consent",
                    )
                    break
            else:
                decisions[peer.peer_id] = ConsentDecision(
                    granted=False,
                    reason=f"Peer {peer.peer_id} has no matching consent",
                )

        return decisions

    def _merge_decision(
        self,
        *,
        local_decision: ConsentDecision,
        jurisdiction_results: dict[str, JurisdictionResult],
        peer_decisions: dict[str, ConsentDecision],
        require_all: bool,
    ) -> bool:
        """Merge local, jurisdiction, and peer decisions into a final grant/deny."""
        # Local consent is always required
        if not local_decision.granted:
            return False

        # Check jurisdictions
        if jurisdiction_results:
            if require_all:
                if not all(jr.satisfied for jr in jurisdiction_results.values()):
                    return False
            else:
                if not any(jr.satisfied for jr in jurisdiction_results.values()):
                    return False

        # Peer decisions: if peers were queried and require_all, all must grant
        # If no peers were queried (empty dict), this is a pass
        if peer_decisions and require_all:
            if not all(pd.granted for pd in peer_decisions.values()):
                return False

        return True

    def _build_access_rights(
        self,
        *,
        query: FederatedConsentQuery,
        granted_scopes: set[str],
        jurisdiction_results: dict[str, JurisdictionResult],
        peer_decisions: dict[str, ConsentDecision],
        local_decision: ConsentDecision,
    ) -> AccessRights:
        """Build AccessRights from a successful evaluation."""
        constraints: dict[str, list[str]] = {}
        for jcode, jresult in jurisdiction_results.items():
            constraints[jcode] = list(jresult.satisfied_scopes)

        conditions: list[str] = []
        expires_at: datetime | None = None
        if local_decision.path:
            for edge in local_decision.path:
                for cond in edge.conditions:
                    if cond.description:
                        conditions.append(cond.description)
                if edge.expires_at is not None:
                    if expires_at is None or edge.expires_at < expires_at:
                        expires_at = edge.expires_at

        sources = [self._institution_id]
        for peer_id, pd in peer_decisions.items():
            if pd.granted:
                sources.append(peer_id)

        return AccessRights(
            agent_id=query.target_id,
            resource_id=query.source_id,
            allowed_scopes=sorted(granted_scopes),
            jurisdiction_constraints=constraints,
            expires_at=expires_at,
            conditions=conditions,
            grant_sources=sources,
        )

    def _build_reason(
        self,
        granted: bool,
        local_decision: ConsentDecision,
        jurisdiction_results: dict[str, JurisdictionResult],
        peer_decisions: dict[str, ConsentDecision],
    ) -> str:
        """Build a human-readable reason string."""
        if not local_decision.granted:
            return f"Local consent denied: {local_decision.reason}"

        failed_jurisdictions = [
            jcode for jcode, jr in jurisdiction_results.items() if not jr.satisfied
        ]
        if failed_jurisdictions:
            return (
                f"Jurisdiction policy not satisfied: {', '.join(failed_jurisdictions)}"
            )

        failed_peers = [pid for pid, pd in peer_decisions.items() if not pd.granted]
        if failed_peers and not granted:
            return f"Peer consent denied: {', '.join(failed_peers)}"

        if granted:
            parts = ["Local consent granted"]
            if jurisdiction_results:
                parts.append(f"{len(jurisdiction_results)} jurisdiction(s) satisfied")
            if peer_decisions:
                peer_ok = sum(1 for pd in peer_decisions.values() if pd.granted)
                parts.append(f"{peer_ok}/{len(peer_decisions)} peer(s) granted")
            return "; ".join(parts)

        return "Access denied"

    def _edge_to_propagation_dict(self, edge: ConsentEdge) -> dict[str, Any]:
        """Serialize a consent edge for propagation."""
        return {
            "edge_id": edge.edge_id,
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "scopes": sorted(edge.scopes),
            "granted_at": edge.granted_at.isoformat(),
            "expires_at": (edge.expires_at.isoformat() if edge.expires_at else None),
            "metadata": dict(edge.metadata),
            "institution_id": self._institution_id,
        }

    def _audit_decision(
        self,
        query: FederatedConsentQuery,
        decision: FederatedConsentDecision,
    ) -> None:
        """Log a federated consent decision."""
        entry = {
            "action": "federated_consent_evaluated",
            "source_id": query.source_id,
            "target_id": query.target_id,
            "scope": query.scope,
            "granted": decision.granted,
            "reason": decision.reason,
            "jurisdictions_checked": list(decision.jurisdiction_results.keys()),
            "peers_checked": list(decision.peer_decisions.keys()),
            "timestamp": decision.evaluated_at.isoformat(),
        }
        self._audit_log.append(entry)
