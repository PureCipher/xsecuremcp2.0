"""Local consent API wiring and live context lifecycle regressions."""

from starlette.testclient import TestClient

from fastmcp.server.security.config import (
    ConsentConfig,
    FederatedConsentConfig,
    SecurityConfig,
)
from fastmcp.server.security.consent.graph import ConsentGraph
from fastmcp.server.security.consent.models import ConsentQuery
from fastmcp.server.security.http.api import SecurityAPI
from fastmcp.server.security.orchestrator import SecurityOrchestrator
from purecipher import PureCipherRegistry


def test_local_api_grant_reaches_the_enforcement_graph_without_federation():
    registry = PureCipherRegistry(signing_secret="test-consent-integration-secret")
    ctx = registry._required_context()
    assert ctx.consent_graph is not None
    with TestClient(registry.http_app()) as client:
        before = client.get("/security/consent/graph").json()
        assert before["graph_id"] == ctx.consent_graph.graph_id
        grant = client.post(
            "/security/consent/grant",
            json={"source_id": "resource", "target_id": "agent", "scopes": ["read"]},
        ).json()
        assert grant["granted"] is True
        assert client.get("/security/consent/graph").json()["edge_count"] == 1
        assert (
            client.get("/security/consent/federated/jurisdictions").json()["status"]
            == 503
        )
    graph = ctx.consent_graph
    assert graph is not None
    assert graph.evaluate(
        ConsentQuery(source_id="resource", target_id="agent", scope="read")
    ).granted
    assert not graph.evaluate(
        ConsentQuery(source_id="resource", target_id="agent", scope="write")
    ).granted
    assert ctx.federated_consent_graph is None


def test_mounted_api_tracks_disable_and_reenable_without_stale_graph():
    registry = PureCipherRegistry(signing_secret="test-consent-integration-secret")
    with TestClient(registry.http_app()) as client:
        original = registry._required_context().consent_graph
        assert original is not None
        registry.disable_plane("consent")
        assert client.get("/security/consent/graph").json()["status"] == 503
        assert (
            client.post(
                "/security/consent/grant", json={"source_id": "r", "target_id": "a"}
            ).json()["status"]
            == 503
        )
        assert original.edge_count == 0
        registry.enable_plane("consent")
        assert client.get("/security/consent/graph").json()["edge_count"] == 0
        assert registry._required_context().consent_graph is not original


def test_context_bridge_is_unavailable_after_local_graph_replaced():
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federated_consent=FederatedConsentConfig(enable_peer_coordination=False),
        )
    )
    api = SecurityAPI.from_context(ctx)
    assert "jurisdictions" in api.list_jurisdictions()
    ctx.consent_graph = ConsentGraph(graph_id="replacement")
    assert api.get_consent_graph_status()["graph_id"] == "replacement"
    assert api.list_jurisdictions()["status"] == 503
    assert api.evaluate_federated_consent("r", "a", "read")["status"] == 503


def test_explicit_api_accepts_local_or_legacy_bridge_graph():
    local = ConsentGraph(graph_id="local")
    assert (
        SecurityAPI(consent_graph=local).get_consent_graph_status()["graph_id"]
        == "local"
    )
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            consent=ConsentConfig(),
            federated_consent=FederatedConsentConfig(enable_peer_coordination=False),
        )
    )
    assert ctx.consent_graph is not None
    api = SecurityAPI(federated_consent_graph=ctx.federated_consent_graph)
    assert api.get_consent_graph_status()["graph_id"] == ctx.consent_graph.graph_id
    assert SecurityAPI().get_consent_graph_status()["status"] == 503


def test_registry_summary_reports_configured_and_detached_bridge():
    registry = PureCipherRegistry(signing_secret="test-consent-integration-secret")
    assert registry._summarize_consent_federation()["available"] is False
    ctx = registry._required_context()
    assert ctx.consent_graph is not None
    from fastmcp.server.security.consent.federation import FederatedConsentGraph

    ctx.federated_consent_graph = FederatedConsentGraph(
        local_graph=ctx.consent_graph,
        enable_peer_coordination=False,
    )
    summary = registry._summarize_consent_federation()
    assert summary["available"] is True
    assert summary["peer_coordination_enabled"] is False
    assert summary["federation_connected"] is False
    registry.disable_plane("consent")
    assert registry._summarize_consent_federation()["available"] is False
