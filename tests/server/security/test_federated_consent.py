"""Tests for the Federated Consent Graph pillar.

Covers jurisdiction policies, geographic context, federated evaluation,
multi-institutional compliance propagation, access rights computation,
consent propagation, and HTTP endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.consent.federation import FederatedConsentGraph
from fastmcp.server.security.consent.graph import ConsentGraph
from fastmcp.server.security.consent.models import (
    AccessRights,
    ConsentCondition,
    ConsentDecision,
    ConsentEdge,
    ConsentNode,
    ConsentQuery,
    ConsentScope,
    FederatedConsentDecision,
    FederatedConsentQuery,
    GeographicContext,
    JurisdictionPolicy,
    JurisdictionResult,
    NodeType,
)
from fastmcp.server.security.federation.federation import (
    FederationPeer,
    PeerStatus,
    TrustFederation,
)


# ── Helpers ───────────────────────────────────────────────────────

def _make_graph() -> ConsentGraph:
    """Create a consent graph with basic nodes."""
    g = ConsentGraph(graph_id="test")
    g.add_node(ConsentNode("owner", NodeType.AGENT, "Owner"))
    g.add_node(ConsentNode("agent-1", NodeType.AGENT, "Agent 1"))
    g.add_node(ConsentNode("data-resource", NodeType.RESOURCE, "Data"))
    return g


def _make_federation() -> TrustFederation:
    """Create a basic federation."""
    return TrustFederation(federation_id="test-fed")


def _eu_policy() -> JurisdictionPolicy:
    return JurisdictionPolicy(
        jurisdiction_id="eu-001",
        jurisdiction_code="EU",
        applicable_regulations=["GDPR"],
        required_consent_scopes=["read", "execute"],
        requires_explicit_consent=True,
    )


def _us_ca_policy() -> JurisdictionPolicy:
    return JurisdictionPolicy(
        jurisdiction_id="us-ca-001",
        jurisdiction_code="US-CA",
        applicable_regulations=["CCPA"],
        required_consent_scopes=["read"],
    )


# ── JurisdictionPolicy tests ─────────────────────────────────────


class TestJurisdictionPolicy:
    def test_create_policy(self):
        p = _eu_policy()
        assert p.jurisdiction_code == "EU"
        assert "GDPR" in p.applicable_regulations
        assert p.required_consent_scopes == ["read", "execute"]
        assert p.requires_explicit_consent is True

    def test_policy_defaults(self):
        p = JurisdictionPolicy()
        assert p.jurisdiction_id == ""
        assert p.jurisdiction_code == ""
        assert p.applicable_regulations == []
        assert p.required_consent_scopes == []
        assert p.data_residency_required is None

    def test_policy_with_data_residency(self):
        p = JurisdictionPolicy(
            jurisdiction_code="EU",
            data_residency_required="EU",
            applicable_regulations=["GDPR"],
        )
        assert p.data_residency_required == "EU"

    def test_policy_metadata(self):
        p = JurisdictionPolicy(
            jurisdiction_code="JP",
            metadata={"notes": "APPI compliance"},
        )
        assert p.metadata["notes"] == "APPI compliance"


# ── GeographicContext tests ───────────────────────────────────────


class TestGeographicContext:
    def test_applicable_jurisdictions(self):
        geo = GeographicContext(
            source_jurisdiction="EU",
            target_jurisdiction="US-CA",
        )
        assert geo.applicable_jurisdictions() == {"EU", "US-CA"}

    def test_applicable_with_data_residency(self):
        geo = GeographicContext(
            source_jurisdiction="EU",
            target_jurisdiction="US-CA",
            data_residency="EU",
            processing_location="US-NY",
        )
        assert geo.applicable_jurisdictions() == {"EU", "US-CA", "US-NY"}

    def test_empty_context(self):
        geo = GeographicContext()
        assert geo.applicable_jurisdictions() == set()

    def test_deduplication(self):
        geo = GeographicContext(
            source_jurisdiction="EU",
            target_jurisdiction="EU",
            data_residency="EU",
        )
        assert geo.applicable_jurisdictions() == {"EU"}

    def test_partial_context(self):
        geo = GeographicContext(source_jurisdiction="JP")
        assert geo.applicable_jurisdictions() == {"JP"}


# ── FederatedConsentGraph init tests ──────────────────────────────


class TestFederatedConsentGraphInit:
    def test_create_basic(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="test-inst")
        assert fed.local_graph is g
        assert fed.federation is None
        assert fed.institution_id == "test-inst"
        assert fed.jurisdiction_count == 0
        assert fed.institution_count == 0

    def test_create_with_federation(self):
        g = _make_graph()
        f = _make_federation()
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        assert fed.federation is f

    def test_create_with_initial_policies(self):
        g = _make_graph()
        policies = {"EU": _eu_policy(), "US-CA": _us_ca_policy()}
        fed = FederatedConsentGraph(
            g, jurisdiction_policies=policies, institution_id="inst-a"
        )
        assert fed.jurisdiction_count == 2
        assert fed.get_jurisdiction_policy("EU") is not None
        assert fed.get_jurisdiction_policy("JP") is None

    def test_register_institution(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        node = fed.register_institution(
            "hospital-a", "EU", label="Hospital A"
        )
        assert node.node_type == NodeType.INSTITUTION
        assert node.node_id == "hospital-a"
        assert node.metadata["jurisdiction_code"] == "EU"
        assert fed.institution_count == 1
        assert fed.get_institution_jurisdiction("hospital-a") == "EU"

    def test_register_multiple_institutions(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_institution("inst-a", "EU")
        fed.register_institution("inst-b", "US-CA")
        fed.register_institution("inst-c", "JP")
        assert fed.institution_count == 3
        assert fed.list_institutions() == {
            "inst-a": "EU",
            "inst-b": "US-CA",
            "inst-c": "JP",
        }

    def test_register_jurisdiction_policy(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        assert fed.jurisdiction_count == 1
        pol = fed.get_jurisdiction_policy("EU")
        assert pol is not None
        assert pol.applicable_regulations == ["GDPR"]

    def test_list_jurisdiction_policies(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        fed.register_jurisdiction_policy(_us_ca_policy())
        policies = fed.list_jurisdiction_policies()
        assert "EU" in policies
        assert "US-CA" in policies


# ── Jurisdiction evaluation tests ─────────────────────────────────


class TestJurisdictionEvaluation:
    def test_single_jurisdiction_satisfied(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read", "execute"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="EU"),
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert "EU" in decision.jurisdiction_results
        assert decision.jurisdiction_results["EU"].satisfied is True

    def test_single_jurisdiction_missing_scope(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})  # Missing "execute"
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="EU"),
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is False
        jr = decision.jurisdiction_results["EU"]
        assert jr.satisfied is False
        assert "execute" in jr.missing_scopes

    def test_multi_jurisdiction_all_satisfied(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read", "execute"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        fed.register_jurisdiction_policy(_us_ca_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert decision.jurisdiction_results["EU"].satisfied is True
        assert decision.jurisdiction_results["US-CA"].satisfied is True

    def test_multi_jurisdiction_one_fails(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})  # EU needs execute too
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        fed.register_jurisdiction_policy(_us_ca_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
            require_all_jurisdictions=True,
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is False
        assert decision.jurisdiction_results["US-CA"].satisfied is True
        assert decision.jurisdiction_results["EU"].satisfied is False

    def test_multi_jurisdiction_any_mode(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        fed.register_jurisdiction_policy(_us_ca_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
            require_all_jurisdictions=False,
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        # US-CA only needs "read", which is granted
        assert decision.granted is True

    def test_unknown_jurisdiction_fails_closed(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        # No policy registered for "JP"

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="JP"),
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is False
        assert "JP" in decision.jurisdiction_results
        assert "No policy registered" in decision.jurisdiction_results["JP"].reason

    def test_no_jurisdictions_grants(self):
        """No geographic context means no jurisdiction checks needed."""
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert len(decision.jurisdiction_results) == 0

    def test_explicit_jurisdiction_filter(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_us_ca_policy())
        fed.register_jurisdiction_policy(_eu_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            jurisdictions=["US-CA"],  # Only check US-CA
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert "US-CA" in decision.jurisdiction_results
        assert "EU" not in decision.jurisdiction_results


# ── Federated evaluation tests ────────────────────────────────────


class TestFederatedEvaluation:
    def test_local_deny_denies_regardless(self):
        g = _make_graph()
        # No consent granted
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is False
        assert "Local consent denied" in decision.reason

    def test_decision_has_local_decision(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.local_decision is not None
        assert decision.local_decision.granted is True

    def test_peer_consent_propagation_enables_grant(self):
        """When peers have propagated consent, it should be found."""
        g = _make_graph()
        g.grant("owner", "agent-1", {"read", "execute"})
        f = _make_federation()
        peer = f.add_peer("partner", peer_id="peer-1", trust_weight=0.8)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        fed.register_jurisdiction_policy(_us_ca_policy())

        # Pre-seed peer consent cache
        fed._peer_consent_cache["peer-1"] = [
            {
                "source_id": "owner",
                "target_id": "agent-1",
                "scopes": ["read", "execute"],
            }
        ]

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="US-CA"),
            include_peers=True,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert "peer-1" in decision.peer_decisions
        assert decision.peer_decisions["peer-1"].granted is True

    def test_peer_no_matching_consent(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-1", trust_weight=0.8)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        fed.register_jurisdiction_policy(_us_ca_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="US-CA"),
            include_peers=True,
            require_all_jurisdictions=True,
        )
        decision = fed.evaluate_federated_consent(query)
        # Local consent + jurisdiction pass, but peer says no with require_all
        assert decision.granted is False

    def test_peer_no_matching_consent_any_mode(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-1", trust_weight=0.8)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        fed.register_jurisdiction_policy(_us_ca_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context=GeographicContext(source_jurisdiction="US-CA"),
            include_peers=True,
            require_all_jurisdictions=False,
        )
        decision = fed.evaluate_federated_consent(query)
        # In any mode, peer denial doesn't block (local + jurisdiction pass)
        assert decision.granted is True

    def test_inactive_peers_skipped(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        peer = f.add_peer("partner", peer_id="peer-1")
        f.update_peer_status("peer-1", PeerStatus.SUSPENDED)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=True,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert len(decision.peer_decisions) == 0


# ── Access rights computation tests ───────────────────────────────


class TestAccessRightsComputation:
    def test_basic_access_rights(self):
        g = _make_graph()
        g.grant("data-resource", "agent-1", {"read", "execute"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        rights = fed.compute_access_rights(
            "agent-1", "data-resource", scopes=["read", "execute", "write"]
        )
        assert "read" in rights.allowed_scopes
        assert "execute" in rights.allowed_scopes
        assert "write" not in rights.allowed_scopes
        assert rights.agent_id == "agent-1"
        assert rights.resource_id == "data-resource"

    def test_access_rights_with_jurisdictions(self):
        g = _make_graph()
        g.grant("data-resource", "agent-1", {"read", "execute"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_us_ca_policy())

        rights = fed.compute_access_rights(
            "agent-1",
            "data-resource",
            geographic_context=GeographicContext(source_jurisdiction="US-CA"),
            scopes=["read"],
        )
        assert "read" in rights.allowed_scopes
        assert "US-CA" in rights.jurisdiction_constraints

    def test_access_rights_with_expiry(self):
        g = _make_graph()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        g.grant(
            "data-resource",
            "agent-1",
            {"read"},
            expires_at=future,
        )
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        rights = fed.compute_access_rights(
            "agent-1", "data-resource", scopes=["read"]
        )
        assert rights.expires_at is not None
        assert rights.expires_at == future

    def test_access_rights_with_conditions(self):
        g = _make_graph()
        g.grant(
            "data-resource",
            "agent-1",
            {"read"},
            conditions=[
                ConsentCondition(
                    expression="True",
                    description="Must be within business hours",
                )
            ],
        )
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        rights = fed.compute_access_rights(
            "agent-1", "data-resource", scopes=["read"]
        )
        assert "Must be within business hours" in rights.conditions

    def test_access_rights_grant_sources(self):
        g = _make_graph()
        g.grant("data-resource", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="hospital-a")

        rights = fed.compute_access_rights(
            "agent-1", "data-resource", scopes=["read"]
        )
        assert "hospital-a" in rights.grant_sources


# ── Consent propagation tests ─────────────────────────────────────


class TestConsentPropagation:
    def test_propagate_consent_to_peers(self):
        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner-a", peer_id="peer-a")
        f.add_peer("partner-b", peer_id="peer-b")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        results = fed.propagate_consent(edge.edge_id)
        assert results["peer-a"] is True
        assert results["peer-b"] is True

    def test_propagate_to_specific_peers(self):
        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner-a", peer_id="peer-a")
        f.add_peer("partner-b", peer_id="peer-b")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        results = fed.propagate_consent(edge.edge_id, target_peers=["peer-a"])
        assert "peer-a" in results
        assert "peer-b" not in results

    def test_propagate_skips_inactive_peers(self):
        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("active", peer_id="peer-a")
        f.add_peer("suspended", peer_id="peer-b")
        f.update_peer_status("peer-b", PeerStatus.SUSPENDED)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        results = fed.propagate_consent(edge.edge_id)
        assert "peer-a" in results
        assert "peer-b" not in results

    def test_propagate_nonexistent_edge(self):
        g = _make_graph()
        f = _make_federation()
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        results = fed.propagate_consent("nonexistent")
        assert results == {}

    def test_propagate_without_federation(self):
        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        results = fed.propagate_consent(edge.edge_id)
        assert results == {}

    def test_receive_consent_propagation(self):
        g = _make_graph()
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-a")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        edge = fed.receive_consent_propagation(
            "peer-a",
            {
                "source_id": "remote-owner",
                "target_id": "agent-1",
                "scopes": ["read", "execute"],
                "metadata": {},
            },
        )
        assert edge is not None
        assert edge.source_id == "remote-owner"
        assert edge.target_id == "agent-1"
        assert edge.scopes == {"read", "execute"}
        assert edge.metadata["propagated_from"] == "peer-a"

    def test_receive_from_invalid_peer(self):
        g = _make_graph()
        f = _make_federation()
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        edge = fed.receive_consent_propagation(
            "unknown-peer",
            {"source_id": "x", "target_id": "y", "scopes": ["read"]},
        )
        assert edge is None

    def test_receive_from_suspended_peer(self):
        g = _make_graph()
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-a")
        f.update_peer_status("peer-a", PeerStatus.SUSPENDED)
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        edge = fed.receive_consent_propagation(
            "peer-a",
            {"source_id": "x", "target_id": "y", "scopes": ["read"]},
        )
        assert edge is None

    def test_receive_without_federation(self):
        g = _make_graph()
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        edge = fed.receive_consent_propagation(
            "peer-a",
            {"source_id": "x", "target_id": "y", "scopes": ["read"]},
        )
        assert edge is None


# ── Backward compatibility tests ──────────────────────────────────


class TestBackwardCompatibility:
    def test_no_federation_local_only(self):
        """Without federation, evaluation uses only local graph."""
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert len(decision.peer_decisions) == 0

    def test_no_jurisdictions_no_checks(self):
        """Without geographic context, no jurisdiction checks."""
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        decision = fed.evaluate_federated_consent(query)
        assert decision.granted is True
        assert len(decision.jurisdiction_results) == 0

    def test_institution_node_type(self):
        """INSTITUTION is a valid NodeType."""
        assert NodeType.INSTITUTION.value == "institution"


# ── Audit log tests ───────────────────────────────────────────────


class TestAuditLog:
    def test_evaluation_logged(self):
        g = _make_graph()
        g.grant("owner", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")

        query = FederatedConsentQuery(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            include_peers=False,
        )
        fed.evaluate_federated_consent(query)
        log = fed.get_audit_log()
        assert len(log) >= 1
        entry = log[-1]
        assert entry["action"] == "federated_consent_evaluated"
        assert entry["source_id"] == "owner"
        assert entry["granted"] is True

    def test_propagation_logged(self):
        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-a")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        fed.propagate_consent(edge.edge_id)
        log = fed.get_audit_log()
        prop_entries = [e for e in log if e["action"] == "consent_propagated"]
        assert len(prop_entries) == 1
        assert "peer-a" in prop_entries[0]["target_peers"]

    def test_receive_logged(self):
        g = _make_graph()
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-a")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")

        fed.receive_consent_propagation(
            "peer-a",
            {"source_id": "x", "target_id": "y", "scopes": ["read"]},
        )
        log = fed.get_audit_log()
        recv_entries = [e for e in log if e["action"] == "consent_received"]
        assert len(recv_entries) == 1


# ── HTTP endpoint tests ──────────────────────────────────────────


class TestHTTPEndpoints:
    def _make_api(self, *, with_fed=True):
        from fastmcp.server.security.http.api import SecurityAPI

        if not with_fed:
            return SecurityAPI()

        g = _make_graph()
        g.grant("owner", "agent-1", {"read", "execute"})
        f = _make_federation()
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        fed.register_jurisdiction_policy(_eu_policy())
        fed.register_jurisdiction_policy(_us_ca_policy())
        fed.register_institution("inst-a", "EU", label="Institution A")
        return SecurityAPI(federated_consent_graph=fed)

    def test_evaluate_endpoint(self):
        api = self._make_api()
        result = api.evaluate_federated_consent(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context={
                "source_jurisdiction": "US-CA",
            },
        )
        assert result["granted"] is True
        assert "US-CA" in result["jurisdiction_results"]

    def test_evaluate_denied(self):
        api = self._make_api()
        result = api.evaluate_federated_consent(
            source_id="owner",
            target_id="agent-1",
            scope="read",
            geographic_context={
                "source_jurisdiction": "JP",
            },
        )
        assert result["granted"] is False

    def test_evaluate_not_configured(self):
        api = self._make_api(with_fed=False)
        result = api.evaluate_federated_consent(
            source_id="owner",
            target_id="agent-1",
            scope="read",
        )
        assert result["status"] == 503

    def test_access_rights_endpoint(self):
        from fastmcp.server.security.http.api import SecurityAPI

        g = _make_graph()
        g.grant("data-resource", "agent-1", {"read"})
        fed = FederatedConsentGraph(g, institution_id="inst-a")
        api = SecurityAPI(federated_consent_graph=fed)

        result = api.get_access_rights("agent-1", "data-resource")
        assert "read" in result["allowed_scopes"]

    def test_access_rights_not_configured(self):
        api = self._make_api(with_fed=False)
        result = api.get_access_rights("agent-1", "resource-1")
        assert result["status"] == 503

    def test_list_jurisdictions_endpoint(self):
        api = self._make_api()
        result = api.list_jurisdictions()
        assert result["count"] == 2
        assert "EU" in result["jurisdictions"]
        assert "US-CA" in result["jurisdictions"]

    def test_list_institutions_endpoint(self):
        api = self._make_api()
        result = api.list_institutions()
        assert result["count"] == 1
        assert "inst-a" in result["institutions"]

    def test_propagate_endpoint(self):
        from fastmcp.server.security.http.api import SecurityAPI

        g = _make_graph()
        edge = g.grant("owner", "agent-1", {"read"})
        f = _make_federation()
        f.add_peer("partner", peer_id="peer-1")
        fed = FederatedConsentGraph(g, f, institution_id="inst-a")
        api = SecurityAPI(federated_consent_graph=fed)

        result = api.propagate_consent_endpoint(edge.edge_id)
        assert result["peers_notified"] == 1

    def test_propagate_not_configured(self):
        api = self._make_api(with_fed=False)
        result = api.propagate_consent_endpoint("some-edge")
        assert result["status"] == 503


# ── Full lifecycle test ───────────────────────────────────────────


class TestFullLifecycle:
    def test_end_to_end(self):
        """Full lifecycle: register institutions → set policies → grant
        consent → evaluate → compute rights → propagate → receive."""

        # Setup
        g = ConsentGraph(graph_id="lifecycle")
        f = TrustFederation(federation_id="lifecycle-fed")
        fed = FederatedConsentGraph(g, f, institution_id="hospital-a")

        # 1. Register institutions
        fed.register_institution("hospital-a", "EU", label="Hospital A")
        fed.register_institution("hospital-b", "US-CA", label="Hospital B")
        assert fed.institution_count == 2

        # 2. Register jurisdiction policies
        fed.register_jurisdiction_policy(JurisdictionPolicy(
            jurisdiction_id="eu-gdpr",
            jurisdiction_code="EU",
            applicable_regulations=["GDPR"],
            required_consent_scopes=["read"],
        ))
        fed.register_jurisdiction_policy(JurisdictionPolicy(
            jurisdiction_id="us-ca-ccpa",
            jurisdiction_code="US-CA",
            applicable_regulations=["CCPA"],
            required_consent_scopes=["read"],
        ))
        assert fed.jurisdiction_count == 2

        # 3. Add nodes and grant consent
        g.add_node(ConsentNode("patient-data", NodeType.RESOURCE, "Patient Data"))
        g.add_node(ConsentNode("ml-agent", NodeType.AGENT, "ML Agent"))
        edge = g.grant(
            "patient-data",
            "ml-agent",
            {"read", "execute"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )

        # 4. Add a federation peer
        peer = f.add_peer("hospital-b-registry", peer_id="peer-b", trust_weight=0.8)

        # 5. Evaluate federated consent (cross-jurisdiction)
        decision = fed.evaluate_federated_consent(FederatedConsentQuery(
            source_id="patient-data",
            target_id="ml-agent",
            scope="read",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
            include_peers=False,  # Peers don't have consent yet
        ))
        assert decision.granted is True
        assert decision.jurisdiction_results["EU"].satisfied is True
        assert decision.jurisdiction_results["US-CA"].satisfied is True
        assert decision.access_rights is not None
        assert "read" in decision.access_rights.allowed_scopes

        # 6. Compute access rights
        rights = fed.compute_access_rights(
            "ml-agent",
            "patient-data",
            geographic_context=GeographicContext(
                source_jurisdiction="EU",
                target_jurisdiction="US-CA",
            ),
            scopes=["read", "execute", "admin"],
        )
        assert "read" in rights.allowed_scopes
        assert "execute" in rights.allowed_scopes
        assert "admin" not in rights.allowed_scopes
        assert rights.expires_at is not None

        # 7. Propagate consent to peer
        results = fed.propagate_consent(edge.edge_id)
        assert results.get("peer-b") is True

        # 8. Simulate receiving consent from peer
        received = fed.receive_consent_propagation(
            "peer-b",
            {
                "source_id": "remote-resource",
                "target_id": "ml-agent",
                "scopes": ["read"],
                "metadata": {"origin": "hospital-b"},
            },
        )
        assert received is not None
        assert received.metadata["propagated_from"] == "peer-b"

        # 9. Verify audit trail
        log = fed.get_audit_log()
        actions = [e["action"] for e in log]
        assert "federated_consent_evaluated" in actions
        assert "consent_propagated" in actions
        assert "consent_received" in actions
