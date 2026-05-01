"""Tests for the SQLiteBackend storage implementation."""

import pytest

from fastmcp.server.security.storage.sqlite import SQLiteBackend


@pytest.fixture()
def db_path(tmp_path):
    """Provide a temp database path."""
    return str(tmp_path / "test.db")


@pytest.fixture()
def backend(db_path):
    """Provide a fresh SQLiteBackend."""
    b = SQLiteBackend(db_path)
    yield b
    b.close()


class TestSQLiteBackendProvenance:
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

    def test_persistence_across_instances(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.append_provenance_record("l", {"record_id": "r1"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        records = b2.load_provenance_records("l")
        b2.close()
        assert len(records) == 1
        assert records[0]["record_id"] == "r1"


class TestSQLiteBackendExchange:
    def test_append_and_load(self, backend):
        backend.append_exchange_entry("log-1", {"entry_id": "e1"})
        backend.append_exchange_entry("log-1", {"entry_id": "e2"})
        entries = backend.load_exchange_entries("log-1")
        assert len(entries) == 2

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.append_exchange_entry("log", {"entry_id": "e1"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        assert len(b2.load_exchange_entries("log")) == 1
        b2.close()


class TestSQLiteBackendContracts:
    def test_save_and_load(self, backend):
        backend.save_contract("broker-1", "c1", {"status": "active"})
        backend.save_contract("broker-1", "c2", {"status": "pending"})
        contracts = backend.load_contracts("broker-1")
        assert len(contracts) == 2

    def test_overwrite(self, backend):
        backend.save_contract("b", "c1", {"status": "active"})
        backend.save_contract("b", "c1", {"status": "revoked"})
        contracts = backend.load_contracts("b")
        assert contracts["c1"]["status"] == "revoked"

    def test_remove(self, backend):
        backend.save_contract("b", "c1", {"status": "active"})
        backend.remove_contract("b", "c1")
        assert backend.load_contracts("b") == {}

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save_contract("b", "c1", {"status": "active"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        assert b2.load_contracts("b")["c1"]["status"] == "active"
        b2.close()


class TestSQLiteBackendBaselines:
    def test_save_and_load(self, backend):
        backend.save_baseline("a", "agent-1", "m1", {"mean": 5.0})
        backend.save_baseline("a", "agent-1", "m2", {"mean": 10.0})
        baselines = backend.load_baselines("a")
        assert baselines["agent-1"]["m1"]["mean"] == 5.0
        assert baselines["agent-1"]["m2"]["mean"] == 10.0

    def test_overwrite(self, backend):
        backend.save_baseline("a", "actor", "m", {"mean": 1.0})
        backend.save_baseline("a", "actor", "m", {"mean": 2.0})
        baselines = backend.load_baselines("a")
        assert baselines["actor"]["m"]["mean"] == 2.0

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
        baselines = backend.load_baselines("a")
        assert "actor" not in baselines

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save_baseline("a", "agent", "m", {"mean": 42.0})
        b1.close()

        b2 = SQLiteBackend(db_path)
        assert b2.load_baselines("a")["agent"]["m"]["mean"] == 42.0
        b2.close()


class TestSQLiteBackendDrift:
    def test_append_and_load(self, backend):
        backend.append_drift_event("a", {"event_id": "d1"})
        backend.append_drift_event("a", {"event_id": "d2"})
        events = backend.load_drift_history("a")
        assert len(events) == 2

    def test_order_preserved(self, backend):
        for i in range(5):
            backend.append_drift_event("a", {"event_id": f"d{i}"})
        events = backend.load_drift_history("a")
        assert [e["event_id"] for e in events] == [f"d{i}" for i in range(5)]


class TestSQLiteBackendEscalations:
    def test_append_and_load(self, backend):
        backend.append_escalation("eng", {"action": "alert"})
        backend.append_escalation("eng", {"action": "suspend"})
        esc = backend.load_escalations("eng")
        assert len(esc) == 2

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.append_escalation("eng", {"action": "alert"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        assert len(b2.load_escalations("eng")) == 1
        b2.close()


class TestSQLiteBackendConsent:
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

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save_consent_node("g", "n1", {"type": "user"})
        b1.save_consent_edge("g", "e1", {"src": "n1"})
        b1.append_consent_audit("g", {"action": "grant"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        graph = b2.load_consent_graph("g")
        b2.close()
        assert "n1" in graph["nodes"]
        assert "e1" in graph["edges"]
        assert len(graph["audit_log"]) == 1

    def test_empty_graph(self, backend):
        graph = backend.load_consent_graph("nonexistent")
        assert graph["nodes"] == {}
        assert graph["edges"] == {}
        assert graph["groups"] == {}
        assert graph["audit_log"] == []


class TestSQLiteBackendMarketplace:
    def test_server_lifecycle(self, backend):
        backend.save_server_registration("mp", "srv1", {"name": "Test"})
        backend.append_marketplace_audit("mp", {"action": "register"})
        mp = backend.load_marketplace("mp")
        assert "srv1" in mp["servers"]
        assert len(mp["audit_log"]) == 1

    def test_remove_registration(self, backend):
        backend.save_server_registration("mp", "srv1", {"name": "Test"})
        backend.remove_server_registration("mp", "srv1")
        mp = backend.load_marketplace("mp")
        assert "srv1" not in mp["servers"]

    def test_persistence(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save_server_registration("mp", "srv1", {"name": "Test"})
        b1.append_marketplace_audit("mp", {"action": "register"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        mp = b2.load_marketplace("mp")
        b2.close()
        assert "srv1" in mp["servers"]
        assert len(mp["audit_log"]) == 1

    def test_empty_marketplace(self, backend):
        mp = backend.load_marketplace("nonexistent")
        assert mp["servers"] == {}
        assert mp["audit_log"] == []


class TestSQLiteBackendToolMarketplace:
    def test_listing_install_and_review_roundtrip(self, backend):
        backend.save_tool_listing("tools", "listing-1", {"tool_name": "weather"})
        backend.append_tool_install("tools", "listing-1", {"install_id": "i1"})
        backend.append_tool_review("tools", "listing-1", {"review_id": "r1"})

        data = backend.load_tool_marketplace("tools")

        assert data["listings"]["listing-1"]["tool_name"] == "weather"
        assert data["installs"]["listing-1"][0]["install_id"] == "i1"
        assert data["reviews"]["listing-1"][0]["review_id"] == "r1"

    def test_persistence_across_instances(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save_tool_listing("tools", "listing-1", {"tool_name": "weather"})
        b1.append_tool_install("tools", "listing-1", {"install_id": "i1"})
        b1.append_tool_review("tools", "listing-1", {"review_id": "r1"})
        b1.close()

        b2 = SQLiteBackend(db_path)
        data = b2.load_tool_marketplace("tools")
        b2.close()

        assert data["listings"]["listing-1"]["tool_name"] == "weather"
        assert data["installs"]["listing-1"][0]["install_id"] == "i1"
        assert data["reviews"]["listing-1"][0]["review_id"] == "r1"


class TestSQLiteBackendSchemaCreation:
    def test_creates_tables_on_init(self, db_path):
        import sqlite3

        backend = SQLiteBackend(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        backend.close()

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
        }
        assert expected.issubset(tables)

    def test_wal_mode(self, db_path):
        import sqlite3

        backend = SQLiteBackend(db_path)
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        backend.close()
        assert mode == "wal"


class TestSQLiteBackendThreadSafety:
    """The backend must give each thread its own sqlite3.Connection.

    Regression test for the bug where a single shared connection across
    threads risked SQLite's "Recursive use of cursors not allowed" and
    "SQLite objects created in a thread can only be used in that same
    thread" failures.
    """

    def test_each_thread_has_its_own_connection(self, backend):
        """Two threads must observe two distinct Connection objects."""
        import threading

        seen: dict[int, object] = {}
        barrier = threading.Barrier(2)

        def _grab(thread_id: int) -> None:
            barrier.wait(timeout=5)
            seen[thread_id] = backend._get_conn()

        threads = [
            threading.Thread(target=_grab, args=(i,), daemon=True) for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(seen) == 2
        assert seen[0] is not seen[1]

    def test_writes_from_multiple_threads_do_not_corrupt(self, backend):
        """50 concurrent threads writing 20 records each must all land."""
        import threading

        n_threads = 50
        per_thread = 20
        errors: list[BaseException] = []
        barrier = threading.Barrier(n_threads)

        def _writer(thread_id: int) -> None:
            try:
                # All threads start writing at the same moment.
                barrier.wait(timeout=10)
                for i in range(per_thread):
                    backend.append_provenance_record(
                        "shared",
                        {
                            "record_id": f"t{thread_id}-r{i}",
                            "thread_id": thread_id,
                            "i": i,
                        },
                    )
            except BaseException as exc:  # noqa: BLE001 — collect for assert
                errors.append(exc)

        threads = [
            threading.Thread(target=_writer, args=(tid,), daemon=True)
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"writer threads raised: {errors!r}"
        records = backend.load_provenance_records("shared")
        assert len(records) == n_threads * per_thread
        # Sanity check: every (thread_id, i) pair appears exactly once.
        pairs = {(r["thread_id"], r["i"]) for r in records}
        assert len(pairs) == n_threads * per_thread

    def test_reader_and_writer_can_share_a_database(self, backend):
        """WAL must allow a reader to make progress while a writer commits."""
        import threading
        import time

        stop = threading.Event()
        seen_counts: list[int] = []
        errors: list[BaseException] = []

        def _writer() -> None:
            try:
                for i in range(50):
                    backend.append_provenance_record(
                        "rw", {"record_id": f"r{i}", "i": i}
                    )
                    time.sleep(0)  # yield
            finally:
                stop.set()

        def _reader() -> None:
            try:
                while not stop.is_set():
                    seen_counts.append(len(backend.load_provenance_records("rw")))
                    time.sleep(0)
                # One final read after the writer is done.
                seen_counts.append(len(backend.load_provenance_records("rw")))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        writer = threading.Thread(target=_writer, daemon=True)
        reader = threading.Thread(target=_reader, daemon=True)
        writer.start()
        reader.start()
        writer.join(timeout=30)
        reader.join(timeout=30)

        assert errors == []
        assert seen_counts[-1] == 50  # eventually consistent

    def test_close_invalidates_all_thread_connections(self, db_path):
        """After close, any thread issuing a new query gets a fresh connection
        instead of hitting "Cannot operate on a closed database."""
        import threading

        backend = SQLiteBackend(db_path)
        try:
            backend.append_provenance_record("ns", {"record_id": "first"})

            # Warm a second thread's per-thread connection.
            warmed: list[object] = []
            done = threading.Event()

            def _warm() -> None:
                warmed.append(backend._get_conn())
                done.set()

            t = threading.Thread(target=_warm, daemon=True)
            t.start()
            assert done.wait(timeout=5)
            t.join(timeout=5)
            assert len(warmed) == 1

            # Close from the main thread closes every tracked connection,
            # including the second thread's.
            backend.close()

            # Issuing a new write from the main thread must succeed —
            # close() is non-final.
            backend.append_provenance_record("ns", {"record_id": "second"})

            # And another thread also reconnects transparently.
            errors: list[BaseException] = []
            results: list[list[dict]] = []

            def _read_after_close() -> None:
                try:
                    results.append(backend.load_provenance_records("ns"))
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            reader = threading.Thread(target=_read_after_close, daemon=True)
            reader.start()
            reader.join(timeout=5)
            assert errors == []
            assert len(results) == 1
            ids = sorted(r["record_id"] for r in results[0])
            assert ids == ["first", "second"]
        finally:
            backend.close()

    def test_busy_timeout_pragma_is_set(self, backend):
        """Each connection must come with PRAGMA busy_timeout applied."""
        conn = backend._get_conn()
        timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout_ms > 0

    def test_busy_timeout_configurable(self, db_path):
        """Constructor knob must propagate to the connection pragma."""
        backend = SQLiteBackend(db_path, busy_timeout_ms=12345)
        try:
            conn = backend._get_conn()
            timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert timeout_ms == 12345
        finally:
            backend.close()
