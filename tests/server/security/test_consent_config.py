"""Tests for Consent Graph configuration."""

from __future__ import annotations

from fastmcp.server.security.config import (
    ConsentConfig,
    SecurityConfig,
)
from fastmcp.server.security.consent.graph import ConsentGraph


class TestConsentConfig:
    def test_default_config(self):
        config = ConsentConfig()
        assert config.graph is None
        assert config.graph_id == "default"
        assert config.resource_owner == "server"

    def test_get_graph_default(self):
        config = ConsentConfig()
        graph = config.get_graph()
        assert isinstance(graph, ConsentGraph)
        assert graph.graph_id == "default"

    def test_get_graph_custom_id(self):
        config = ConsentConfig(graph_id="my-graph")
        graph = config.get_graph()
        assert graph.graph_id == "my-graph"

    def test_get_graph_uses_existing(self):
        custom = ConsentGraph(graph_id="custom")
        config = ConsentConfig(graph=custom)
        assert config.get_graph() is custom


class TestSecurityConfigConsent:
    def test_consent_not_enabled_by_default(self):
        config = SecurityConfig()
        assert not config.is_consent_enabled()

    def test_consent_enabled(self):
        config = SecurityConfig(consent=ConsentConfig())
        assert config.is_consent_enabled()

    def test_consent_disabled_by_master_switch(self):
        config = SecurityConfig(
            consent=ConsentConfig(),
            enabled=False,
        )
        assert not config.is_consent_enabled()
