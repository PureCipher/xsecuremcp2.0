"""Dependency and lifecycle regressions for federated-consent bootstrap."""

from __future__ import annotations

import pytest

from fastmcp.server.security.alerts.bus import SecurityEventBus
from fastmcp.server.security.config import (
    AlertConfig,
    ConsentConfig,
    FederatedConsentConfig,
    FederationConfig,
    SecurityConfig,
)
from fastmcp.server.security.consent.federation import FederatedConsentGraph
from fastmcp.server.security.consent.graph import ConsentGraph
from fastmcp.server.security.consent.models import (
    ConsentEdge,
    ConsentNode,
    FederatedConsentQuery,
    JurisdictionPolicy,
    NodeType,
)
from fastmcp.server.security.federation.federation import TrustFederation
from fastmcp.server.security.orchestrator import SecurityOrchestrator


def _add_local_grant(graph: ConsentGraph) -> ConsentEdge:
    graph.add_node(ConsentNode("owner", NodeType.AGENT, "Owner"))
    graph.add_node(ConsentNode("agent-1", NodeType.AGENT, "Agent"))
    return graph.grant("owner", "agent-1", {"read"})


def _peer_query() -> FederatedConsentQuery:
    return FederatedConsentQuery(
        source_id="owner",
        target_id="agent-1",
        scope="read",
        include_peers=True,
        require_all_jurisdictions=True,
    )


def test_local_consent_does_not_implicitly_enable_federated_consent():
    ctx = SecurityOrchestrator.bootstrap(SecurityConfig(consent=ConsentConfig()))

    assert ctx.consent_graph is not None
    assert ctx.federated_consent_graph is None
    assert ctx.federation is None


def test_federation_can_be_enabled_without_consent():
    ctx = SecurityOrchestrator.bootstrap(SecurityConfig(federation=FederationConfig()))

    assert ctx.federation is not None
    assert ctx.consent_graph is None
    assert ctx.federated_consent_graph is None


def test_consent_and_federation_remain_independent_without_bridge_config():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federation=FederationConfig(),
        )
    )

    assert ctx.consent_graph is not None
    assert ctx.federation is not None
    assert ctx.federated_consent_graph is None


def test_local_only_federated_consent_does_not_require_federation():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federated_consent=FederatedConsentConfig(
                enable_peer_coordination=False,
            ),
        )
    )

    assert ctx.federated_consent_graph is not None
    assert ctx.federated_consent_graph.local_graph is ctx.consent_graph
    assert ctx.federated_consent_graph.federation is None
    assert ctx.federated_consent_graph.peer_coordination_enabled is False


def test_peer_coordinated_consent_receives_live_federation_instance():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federation=FederationConfig(federation_id="node-a"),
            federated_consent=FederatedConsentConfig(institution_id="hospital-a"),
        )
    )

    assert ctx.federated_consent_graph is not None
    assert ctx.federated_consent_graph.local_graph is ctx.consent_graph
    assert ctx.federated_consent_graph.federation is ctx.federation
    assert ctx.federated_consent_graph.institution_id == "hospital-a"


def test_federated_consent_receives_configured_policies_and_event_bus():
    bus = SecurityEventBus()
    policy = JurisdictionPolicy(
        jurisdiction_id="eu-policy",
        jurisdiction_code="EU",
        required_consent_scopes=["read"],
    )
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            alerts=AlertConfig(event_bus=bus),
            consent=ConsentConfig(),
            federated_consent=FederatedConsentConfig(
                jurisdiction_policies={"EU": policy},
                enable_peer_coordination=False,
            ),
        )
    )

    assert ctx.federated_consent_graph is not None
    assert ctx.federated_consent_graph.get_jurisdiction_policy("EU") is policy
    assert ctx.federated_consent_graph._event_bus is bus


def test_federated_consent_requires_local_consent_config():
    config = SecurityConfig(
        federation=FederationConfig(),
        federated_consent=FederatedConsentConfig(),
    )

    with pytest.raises(ValueError, match="requires ConsentConfig"):
        SecurityOrchestrator.bootstrap(config)


def test_peer_coordination_requires_federation_config():
    config = SecurityConfig(
        consent=ConsentConfig(),
        federated_consent=FederatedConsentConfig(),
    )

    with pytest.raises(ValueError, match="requires FederationConfig"):
        SecurityOrchestrator.bootstrap(config)


def test_master_switch_disables_federated_dependency_validation():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            federated_consent=FederatedConsentConfig(),
            enabled=False,
        )
    )

    assert ctx.consent_graph is None
    assert ctx.federation is None
    assert ctx.federated_consent_graph is None


def test_prebuilt_federated_graph_is_preserved_when_dependencies_match():
    local_graph = ConsentGraph()
    federation = TrustFederation()
    federated_graph = FederatedConsentGraph(local_graph, federation)
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(graph=local_graph),
            federation=FederationConfig(federation=federation),
            federated_consent=FederatedConsentConfig(
                federated_graph=federated_graph,
            ),
        )
    )

    assert ctx.federated_consent_graph is federated_graph


def test_prebuilt_federated_graph_rejects_different_local_graph():
    configured_graph = ConsentGraph(graph_id="configured")
    federated_graph = FederatedConsentGraph(
        ConsentGraph(graph_id="different"),
        enable_peer_coordination=False,
    )
    config = SecurityConfig(
        consent=ConsentConfig(graph=configured_graph),
        federated_consent=FederatedConsentConfig(
            federated_graph=federated_graph,
        ),
    )

    with pytest.raises(ValueError, match="configured ConsentConfig graph"):
        SecurityOrchestrator.bootstrap(config)


def test_prebuilt_federated_graph_rejects_different_federation():
    local_graph = ConsentGraph()
    config = SecurityConfig(
        consent=ConsentConfig(graph=local_graph),
        federation=FederationConfig(federation=TrustFederation()),
        federated_consent=FederatedConsentConfig(
            federated_graph=FederatedConsentGraph(
                local_graph,
                TrustFederation(),
            ),
        ),
    )

    with pytest.raises(ValueError, match="configured FederationConfig instance"):
        SecurityOrchestrator.bootstrap(config)


def test_disabled_peer_coordination_ignores_and_does_not_propagate_to_peers():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federation=FederationConfig(),
            federated_consent=FederatedConsentConfig(
                enable_peer_coordination=False,
            ),
        )
    )
    assert ctx.consent_graph is not None
    assert ctx.federation is not None
    assert ctx.federated_consent_graph is not None
    edge = _add_local_grant(ctx.consent_graph)
    ctx.federation.add_peer("Partner", peer_id="peer-1")

    decision = ctx.federated_consent_graph.evaluate_federated_consent(_peer_query())

    assert decision.granted is True
    assert decision.peer_decisions == {}
    assert ctx.federated_consent_graph.propagate_consent(edge.edge_id) == {}


def test_federation_peer_state_affects_bootstrapped_consent_decision_end_to_end():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federation=FederationConfig(),
            federated_consent=FederatedConsentConfig(),
        )
    )
    assert ctx.consent_graph is not None
    assert ctx.federation is not None
    assert ctx.federated_consent_graph is not None
    edge = _add_local_grant(ctx.consent_graph)
    ctx.federation.add_peer("Partner", peer_id="peer-1")

    before_propagation = ctx.federated_consent_graph.evaluate_federated_consent(
        _peer_query()
    )
    propagation = ctx.federated_consent_graph.propagate_consent(edge.edge_id)
    after_propagation = ctx.federated_consent_graph.evaluate_federated_consent(
        _peer_query()
    )

    assert before_propagation.granted is False
    assert propagation == {"peer-1": True}
    assert after_propagation.granted is True
    assert after_propagation.peer_decisions["peer-1"].granted is True
