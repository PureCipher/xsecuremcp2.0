"""Conformance tests for the PostgresBackend storage implementation.

Mirrors the SQLiteBackend suite: same behaviors (namespace isolation, upsert,
remove, append ordering, persistence-across-instances) verified against a real
PostgreSQL database provided by the ``registry_dsn`` fixture. Skips when no
PostgreSQL server is reachable.
"""

import pytest

from fastmcp.server.security.storage.postgres import PostgresBackend


@pytest.fixture()
def backend(registry_dsn):
    """A fresh PostgresBackend bound to a per-test database."""
    return PostgresBackend(registry_dsn)


class TestPostgresBackendProvenance:
    def test_append_and_load(self, backend):
        backend.append_provenance_record("ledger-1", {"record_id": "r1", "data": "x"})
        backend.append_provenance_record("ledger-1", {"record_id": "r2", "data": "y"})
        records = backend.load_provenance_records("ledger-1")
        assert len(records) == 2
        assert records[0]["record_id"] == "r1"
        assert records[1]["record_id"] == "r2"

    def test_load_empty(self, backend):
        assert backend.load_provenance_records("nonexistent") == []

    def test_namespace_isolation(self, backend):
        backend.append_provenance_record("a", {"id": "1"})
        backend.append_provenance_record("b", {"id": "2"})
        assert len(backend.load_provenance_records("a")) == 1
        assert len(backend.load_provenance_records("b")) == 1

    def test_persistence_across_instances(self, registry_dsn):
        b1 = PostgresBackend(registry_dsn)
        b1.append_provenance_record("l", {"record_id": "r1"})

        b2 = PostgresBackend(registry_dsn)
        records = b2.load_provenance_records("l")
        assert len(records) == 1
        assert records[0]["record_id"] == "r1"


class TestPostgresBackendExchange:
    def test_append_and_load(self, backend):
        backend.append_exchange_entry("log-1", {"entry_id": "e1"})
        backend.append_exchange_entry("log-1", {"entry_id": "e2"})
        assert len(backend.load_exchange_entries("log-1")) == 2

    def test_persistence(self, registry_dsn):
        PostgresBackend(registry_dsn).append_exchange_entry("log", {"entry_id": "e1"})
        assert len(PostgresBackend(registry_dsn).load_exchange_entries("log")) == 1


class TestPostgresBackendContracts:
    def test_save_and_load(self, backend):
        backend.save_contract("broker-1", "c1", {"status": "active"})
        backend.save_contract("broker-1", "c2", {"status": "pending"})
        assert len(backend.load_contracts("broker-1")) == 2

    def test_overwrite(self, backend):
        backend.save_contract("b", "c1", {"status": "active"})
        backend.save_contract("b", "c1", {"status": "revoked"})
        assert backend.load_contracts("b")["c1"]["status"] == "revoked"

    def test_remove(self, backend):
        backend.save_contract("b", "c1", {"status": "active"})
        backend.remove_contract("b", "c1")
        assert backend.load_contracts("b") == {}

    def test_persistence(self, registry_dsn):
        PostgresBackend(registry_dsn).save_contract("b", "c1", {"status": "active"})
        assert (
            PostgresBackend(registry_dsn).load_contracts("b")["c1"]["status"]
            == "active"
        )


class TestPostgresBackendBaselines:
    def test_save_and_load(self, backend):
        backend.save_baseline("a", "agent-1", "m1", {"mean": 5.0})
        backend.save_baseline("a", "agent-1", "m2", {"mean": 10.0})
        baselines = backend.load_baselines("a")
        assert baselines["agent-1"]["m1"]["mean"] == 5.0
        assert baselines["agent-1"]["m2"]["mean"] == 10.0

    def test_overwrite(self, backend):
        backend.save_baseline("a", "actor", "m", {"mean": 1.0})
        backend.save_baseline("a", "actor", "m", {"mean": 2.0})
        assert backend.load_baselines("a")["actor"]["m"]["mean"] == 2.0

    def test_remove_single(self, backend):
        backend.save_baseline("a", "actor", "m1", {"v": 1})
        backend.save_baseline("a", "actor", "m2", {"v": 2})
        backend.remove_baseline("a", "actor", "m1")
        baselines = backend.load_baselines("a")
        assert "m1" not in baselines.get("actor", {})
        assert baselines["actor"]["m2"]["v"] == 2

    def test_remove_all_for_actor(self, backend):
        backend.save_baseline("a", "actor", "m1", {"v": 1})
        backend.save_baseline("a", "actor", "m2", {"v": 2})
        backend.remove_baseline("a", "actor")
        assert "actor" not in backend.load_baselines("a")

    def test_persistence(self, registry_dsn):
        PostgresBackend(registry_dsn).save_baseline("a", "agent", "m", {"mean": 42.0})
        assert (
            PostgresBackend(registry_dsn).load_baselines("a")["agent"]["m"]["mean"]
            == 42.0
        )


class TestPostgresBackendDrift:
    def test_append_and_load(self, backend):
        backend.append_drift_event("a", {"event_id": "d1"})
        backend.append_drift_event("a", {"event_id": "d2"})
        assert len(backend.load_drift_history("a")) == 2

    def test_order_preserved(self, backend):
        for i in range(5):
            backend.append_drift_event("a", {"event_id": f"d{i}"})
        events = backend.load_drift_history("a")
        assert [e["event_id"] for e in events] == [f"d{i}" for i in range(5)]


class TestPostgresBackendEscalations:
    def test_append_and_load(self, backend):
        backend.append_escalation("eng", {"action": "alert"})
        backend.append_escalation("eng", {"action": "suspend"})
        assert len(backend.load_escalations("eng")) == 2

    def test_persistence(self, registry_dsn):
        PostgresBackend(registry_dsn).append_escalation("eng", {"action": "alert"})
        assert len(PostgresBackend(registry_dsn).load_escalations("eng")) == 1


class TestPostgresBackendConsent:
    def test_full_graph_lifecycle(self, backend):
        backend.save_consent_node("g", "n1", {"type": "user"})
        backend.save_consent_node("g", "n2", {"type": "agent"})
        backend.save_consent_edge("g", "e1", {"source": "n1", "target": "n2"})
        backend.save_consent_group("g", "grp1", ["n1", "n2"])
        backend.append_consent_audit("g", {"action": "grant"})

        graph = backend.load_consent_graph("g")
        assert len(graph["nodes"]) == 2
        assert "e1" in graph["edges"]
        assert graph["groups"]["grp1"] == ["n1", "n2"]
        assert len(graph["audit_log"]) == 1

    def test_remove_operations(self, backend):
        backend.save_consent_node("g", "n1", {"type": "user"})
        backend.save_consent_edge("g", "e1", {"source": "n1"})
        backend.save_consent_group("g", "grp1", ["n1"])

        backend.remove_consent_node("g", "n1")
        backend.remove_consent_edge("g", "e1")
        backend.remove_consent_group("g", "grp1")

        graph = backend.load_consent_graph("g")
        assert graph["nodes"] == {}
        assert graph["edges"] == {}
        assert graph["groups"] == {}

    def test_persistence(self, registry_dsn):
        b1 = PostgresBackend(registry_dsn)
        b1.save_consent_node("g", "n1", {"type": "user"})
        b1.save_consent_edge("g", "e1", {"src": "n1"})
        b1.append_consent_audit("g", {"action": "grant"})

        graph = PostgresBackend(registry_dsn).load_consent_graph("g")
        assert "n1" in graph["nodes"]
        assert "e1" in graph["edges"]
        assert len(graph["audit_log"]) == 1

    def test_empty_graph(self, backend):
        graph = backend.load_consent_graph("nonexistent")
        assert graph["nodes"] == {}
        assert graph["edges"] == {}
        assert graph["groups"] == {}
        assert graph["audit_log"] == []


class TestPostgresBackendMarketplace:
    def test_server_lifecycle(self, backend):
        backend.save_server_registration("mp", "srv1", {"name": "Test"})
        backend.append_marketplace_audit("mp", {"action": "register"})
        mp = backend.load_marketplace("mp")
        assert "srv1" in mp["servers"]
        assert len(mp["audit_log"]) == 1

    def test_remove_registration(self, backend):
        backend.save_server_registration("mp", "srv1", {"name": "Test"})
        backend.remove_server_registration("mp", "srv1")
        assert "srv1" not in backend.load_marketplace("mp")["servers"]

    def test_persistence(self, registry_dsn):
        b1 = PostgresBackend(registry_dsn)
        b1.save_server_registration("mp", "srv1", {"name": "Test"})
        b1.append_marketplace_audit("mp", {"action": "register"})

        mp = PostgresBackend(registry_dsn).load_marketplace("mp")
        assert "srv1" in mp["servers"]
        assert len(mp["audit_log"]) == 1

    def test_empty_marketplace(self, backend):
        mp = backend.load_marketplace("nonexistent")
        assert mp["servers"] == {}
        assert mp["audit_log"] == []


class TestPostgresBackendToolMarketplace:
    def test_listing_install_and_review_roundtrip(self, backend):
        backend.save_tool_listing("tools", "listing-1", {"tool_name": "weather"})
        backend.append_tool_install("tools", "listing-1", {"install_id": "i1"})
        backend.append_tool_review("tools", "listing-1", {"review_id": "r1"})

        data = backend.load_tool_marketplace("tools")
        assert data["listings"]["listing-1"]["tool_name"] == "weather"
        assert data["installs"]["listing-1"][0]["install_id"] == "i1"
        assert data["reviews"]["listing-1"][0]["review_id"] == "r1"

    def test_remove_listing_cascades(self, backend):
        backend.save_tool_listing("tools", "listing-1", {"tool_name": "weather"})
        backend.append_tool_install("tools", "listing-1", {"install_id": "i1"})
        backend.append_tool_review("tools", "listing-1", {"review_id": "r1"})
        backend.remove_tool_listing("tools", "listing-1")

        data = backend.load_tool_marketplace("tools")
        assert "listing-1" not in data["listings"]
        assert "listing-1" not in data["installs"]
        assert "listing-1" not in data["reviews"]

    def test_persistence_across_instances(self, registry_dsn):
        b1 = PostgresBackend(registry_dsn)
        b1.save_tool_listing("tools", "listing-1", {"tool_name": "weather"})
        b1.append_tool_install("tools", "listing-1", {"install_id": "i1"})
        b1.append_tool_review("tools", "listing-1", {"review_id": "r1"})

        data = PostgresBackend(registry_dsn).load_tool_marketplace("tools")
        assert data["listings"]["listing-1"]["tool_name"] == "weather"
        assert data["installs"]["listing-1"][0]["install_id"] == "i1"
        assert data["reviews"]["listing-1"][0]["review_id"] == "r1"


class TestPostgresBackendPolicy:
    def test_versions_roundtrip(self, backend):
        assert backend.load_policy_versions("ps") is None
        backend.save_policy_version("ps", {"versions": [1, 2, 3]})
        assert backend.load_policy_versions("ps") == {"versions": [1, 2, 3]}

    def test_workbench_roundtrip(self, backend):
        assert backend.load_policy_workbench_state("ps") is None
        backend.save_policy_workbench_state("ps", {"draft": True})
        assert backend.load_policy_workbench_state("ps") == {"draft": True}

    def test_proposals_lifecycle(self, backend):
        backend.save_policy_proposal("gov", "p1", {"status": "open"})
        backend.save_policy_proposal("gov", "p2", {"status": "open"})
        assert len(backend.load_policy_proposals("gov")) == 2
        backend.remove_policy_proposal("gov", "p1")
        proposals = backend.load_policy_proposals("gov")
        assert "p1" not in proposals
        assert "p2" in proposals


class TestPostgresBackendSchemaCreation:
    def test_creates_tables_on_init(self, registry_dsn):
        import psycopg

        PostgresBackend(registry_dsn)
        with psycopg.connect(registry_dsn) as conn:
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ).fetchall()
        tables = {row[0] for row in rows}
        expected = {
            "provenance_records",
            "exchange_entries",
            "contracts",
            "baselines",
            "drift_events",
            "escalations",
            "consent_nodes",
            "consent_edges",
            "consent_groups",
            "consent_audit_log",
            "server_registrations",
            "marketplace_audit_log",
            "tool_listings",
            "tool_installs",
            "tool_reviews",
            "policy_proposals",
            "policy_versions",
            "policy_workbench",
        }
        assert expected.issubset(tables)
