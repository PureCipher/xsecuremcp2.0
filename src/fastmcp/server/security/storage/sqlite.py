"""SQLite storage backend for SecureMCP.

Provides durable, single-file persistence for all security layers.
Zero-config: just provide a file path (defaults to ``securemcp.db``).
Uses Python's built-in ``sqlite3`` module — no external dependencies.

Thread safety: ``sqlite3.Connection`` objects are not safe to share
across threads, so the backend keeps a per-thread connection in
:class:`threading.local` storage. Concurrent writers are serialized at
the file level by SQLite's own locking; ``PRAGMA busy_timeout`` is set
on every connection so contended writers wait briefly instead of
raising ``OperationalError: database is locked``. WAL mode permits
multiple concurrent readers alongside a writer.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

# Default per-statement wait when another writer holds the SQLite write lock.
# 5 seconds is generous for the kinds of small INSERT/UPDATE/DELETE statements
# this backend issues; it keeps async event loops from raising under burst
# contention while still surfacing real deadlocks within a reasonable window.
_DEFAULT_BUSY_TIMEOUT_MS = 5_000


class SQLiteBackend:
    """SQLite-backed persistent storage for SecureMCP.

    All data is stored in a single SQLite database file. Tables are
    auto-created on first use. Each security layer's data is namespaced
    by its component ID (ledger_id, graph_id, etc.).

    Each calling thread receives its own ``sqlite3.Connection``. The
    backend tracks every open connection so :meth:`close` can shut them
    all down deterministically (e.g. on test teardown). After
    :meth:`close`, any thread calling a backend method again receives a
    freshly-opened connection — close is non-destructive to the backend
    object itself.

    Example::

        from fastmcp.server.security.storage import SQLiteBackend

        backend = SQLiteBackend("securemcp.db")

    Args:
        path: Path to the SQLite database file. Defaults to
            ``securemcp.db`` in the current directory.
        busy_timeout_ms: Per-connection ``PRAGMA busy_timeout`` value.
            Controls how long a write blocks waiting for a contended
            file lock before raising. Default 5000ms.
    """

    def __init__(
        self,
        path: str = "securemcp.db",
        *,
        busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self._path = str(path)
        self._busy_timeout_ms = int(busy_timeout_ms)
        # Per-thread connection storage. ``threading.local`` guarantees
        # each thread sees its own ``conn`` attribute.
        self._local = threading.local()
        # All connections we've ever opened, regardless of thread, so
        # ``close()`` can close them all without iterating thread state.
        self._connections: list[sqlite3.Connection] = []
        self._tracking_lock = threading.Lock()
        # Bumped on each ``close()``. Threads compare their cached
        # generation to this; if stale, they reopen.
        self._generation = 0
        self._ensure_schema()

    def _new_connection(self) -> sqlite3.Connection:
        """Open a fresh SQLite connection with the right pragmas applied."""
        # check_same_thread=True (default) is correct here: each thread owns
        # its own connection, so the safety check stays useful.
        conn = sqlite3.connect(self._path)
        # PRAGMA journal_mode=WAL is persisted on the database file itself,
        # but we still issue it on every connection so that a freshly-created
        # database file is set to WAL on first use.
        conn.execute("PRAGMA journal_mode=WAL")
        # foreign_keys is per-connection, not persisted.
        conn.execute("PRAGMA foreign_keys=ON")
        # busy_timeout is per-connection. Without it, two threads issuing
        # writes simultaneously will hit "database is locked" instead of
        # waiting briefly.
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        with self._tracking_lock:
            self._connections.append(conn)
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        """Return this thread's connection, opening it on first use.

        If the backend has been closed since this thread last connected
        the cached connection is stale; open a new one and update the
        thread-local generation marker.
        """
        cached_gen = getattr(self._local, "generation", None)
        if cached_gen != self._generation or not hasattr(self._local, "conn"):
            self._local.conn = self._new_connection()
            self._local.generation = self._generation
        return self._local.conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS provenance_records (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_prov_ns
                ON provenance_records(namespace);

            CREATE TABLE IF NOT EXISTS exchange_entries (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_exch_ns
                ON exchange_entries(namespace);

            CREATE TABLE IF NOT EXISTS contracts (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS baselines (
                namespace TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, actor_id, metric_name)
            );

            CREATE TABLE IF NOT EXISTS drift_events (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_drift_ns
                ON drift_events(namespace);

            CREATE TABLE IF NOT EXISTS escalations (
                namespace TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_esc_ns
                ON escalations(namespace);

            CREATE TABLE IF NOT EXISTS consent_nodes (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS consent_edges (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS consent_groups (
                namespace TEXT NOT NULL,
                group_id TEXT NOT NULL,
                members TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, group_id)
            );

            CREATE TABLE IF NOT EXISTS consent_audit_log (
                namespace TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_consent_audit_ns
                ON consent_audit_log(namespace);

            CREATE TABLE IF NOT EXISTS server_registrations (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS marketplace_audit_log (
                namespace TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_mp_audit_ns
                ON marketplace_audit_log(namespace);

            CREATE TABLE IF NOT EXISTS tool_listings (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS tool_installs (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_tool_installs_ns
                ON tool_installs(namespace);

            CREATE TABLE IF NOT EXISTS tool_reviews (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT
            );
            CREATE INDEX IF NOT EXISTS idx_tool_reviews_ns
                ON tool_reviews(namespace);

            CREATE TABLE IF NOT EXISTS policy_proposals (
                namespace TEXT NOT NULL,
                item_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, item_id)
            );

            CREATE TABLE IF NOT EXISTS policy_versions (
                policy_set_id TEXT NOT NULL PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS policy_workbench (
                policy_set_id TEXT NOT NULL PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
        """
        )
        conn.commit()

    def close(self) -> None:
        """Close every per-thread connection opened by this backend.

        After ``close()``, the backend object is still usable: subsequent
        method calls from any thread will transparently open a fresh
        connection. This is intentional so test teardown patterns
        (``backend.close()`` followed by re-instantiation against the
        same path) keep working unchanged.
        """
        with self._tracking_lock:
            connections = self._connections
            self._connections = []
            self._generation += 1
        for conn in connections:
            try:
                conn.close()
            except sqlite3.Error:
                # An already-closed connection or a connection the OS
                # has lost (e.g. file removed) shouldn't prevent us from
                # closing the others.
                pass
        # Drop the calling thread's cached connection so the next call
        # on this thread doesn't briefly observe a stale handle before
        # the generation check kicks in.
        if hasattr(self._local, "conn"):
            del self._local.conn
        if hasattr(self._local, "generation"):
            del self._local.generation

    # ── Provenance ────────────────────────────────────────────────

    def append_provenance_record(
        self, ledger_id: str, record_data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO provenance_records (namespace, item_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                ledger_id,
                record_data.get("record_id", ""),
                json.dumps(record_data),
                time.time(),
            ),
        )
        conn.commit()

    def load_provenance_records(self, ledger_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT data FROM provenance_records WHERE namespace = ? ORDER BY seq",
            (ledger_id,),
        )
        return [json.loads(row[0]) for row in cursor.fetchall()]

    # ── Exchange Log ──────────────────────────────────────────────

    def append_exchange_entry(self, log_id: str, entry_data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO exchange_entries (namespace, item_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                log_id,
                entry_data.get("entry_id", ""),
                json.dumps(entry_data),
                time.time(),
            ),
        )
        conn.commit()

    def load_exchange_entries(self, log_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT data FROM exchange_entries WHERE namespace = ? ORDER BY seq",
            (log_id,),
        )
        return [json.loads(row[0]) for row in cursor.fetchall()]

    # ── Contracts ─────────────────────────────────────────────────

    def save_contract(
        self, broker_id: str, contract_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO contracts (namespace, item_id, data, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (broker_id, contract_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_contract(self, broker_id: str, contract_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM contracts WHERE namespace = ? AND item_id = ?",
            (broker_id, contract_id),
        )
        conn.commit()

    def load_contracts(self, broker_id: str) -> dict[str, dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT item_id, data FROM contracts WHERE namespace = ?",
            (broker_id,),
        )
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

    # ── Baselines ─────────────────────────────────────────────────

    def save_baseline(
        self,
        analyzer_id: str,
        actor_id: str,
        metric_name: str,
        data: dict[str, Any],
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO baselines "
            "(namespace, actor_id, metric_name, data, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (analyzer_id, actor_id, metric_name, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_baseline(
        self, analyzer_id: str, actor_id: str, metric_name: str | None = None
    ) -> None:
        conn = self._get_conn()
        if metric_name is None:
            conn.execute(
                "DELETE FROM baselines WHERE namespace = ? AND actor_id = ?",
                (analyzer_id, actor_id),
            )
        else:
            conn.execute(
                "DELETE FROM baselines "
                "WHERE namespace = ? AND actor_id = ? AND metric_name = ?",
                (analyzer_id, actor_id, metric_name),
            )
        conn.commit()

    def load_baselines(self, analyzer_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT actor_id, metric_name, data FROM baselines WHERE namespace = ?",
            (analyzer_id,),
        )
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for actor_id, metric_name, data_str in cursor.fetchall():
            result.setdefault(actor_id, {})[metric_name] = json.loads(data_str)
        return result

    # ── Drift History ─────────────────────────────────────────────

    def append_drift_event(self, analyzer_id: str, event_data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO drift_events (namespace, item_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                analyzer_id,
                event_data.get("event_id", ""),
                json.dumps(event_data),
                time.time(),
            ),
        )
        conn.commit()

    def load_drift_history(self, analyzer_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT data FROM drift_events WHERE namespace = ? ORDER BY seq",
            (analyzer_id,),
        )
        return [json.loads(row[0]) for row in cursor.fetchall()]

    # ── Escalation History ────────────────────────────────────────

    def append_escalation(self, engine_id: str, data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO escalations (namespace, data, created_at) VALUES (?, ?, ?)",
            (engine_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def load_escalations(self, engine_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT data FROM escalations WHERE namespace = ? ORDER BY seq",
            (engine_id,),
        )
        return [json.loads(row[0]) for row in cursor.fetchall()]

    # ── Consent Graph ─────────────────────────────────────────────

    def save_consent_node(
        self, graph_id: str, node_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO consent_nodes "
            "(namespace, item_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (graph_id, node_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_consent_node(self, graph_id: str, node_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM consent_nodes WHERE namespace = ? AND item_id = ?",
            (graph_id, node_id),
        )
        conn.commit()

    def save_consent_edge(
        self, graph_id: str, edge_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO consent_edges "
            "(namespace, item_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (graph_id, edge_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_consent_edge(self, graph_id: str, edge_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM consent_edges WHERE namespace = ? AND item_id = ?",
            (graph_id, edge_id),
        )
        conn.commit()

    def save_consent_group(
        self, graph_id: str, group_id: str, members: list[str]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO consent_groups "
            "(namespace, group_id, members, updated_at) VALUES (?, ?, ?, ?)",
            (graph_id, group_id, json.dumps(members), time.time()),
        )
        conn.commit()

    def remove_consent_group(self, graph_id: str, group_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM consent_groups WHERE namespace = ? AND group_id = ?",
            (graph_id, group_id),
        )
        conn.commit()

    def append_consent_audit(self, graph_id: str, entry: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO consent_audit_log (namespace, data, created_at) "
            "VALUES (?, ?, ?)",
            (graph_id, json.dumps(entry), time.time()),
        )
        conn.commit()

    def load_consent_graph(self, graph_id: str) -> dict[str, Any]:
        conn = self._get_conn()

        nodes: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM consent_nodes WHERE namespace = ?",
            (graph_id,),
        ).fetchall():
            nodes[row[0]] = json.loads(row[1])

        edges: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM consent_edges WHERE namespace = ?",
            (graph_id,),
        ).fetchall():
            edges[row[0]] = json.loads(row[1])

        groups: dict[str, list[str]] = {}
        for row in conn.execute(
            "SELECT group_id, members FROM consent_groups WHERE namespace = ?",
            (graph_id,),
        ).fetchall():
            groups[row[0]] = json.loads(row[1])

        audit_log: list[dict[str, Any]] = []
        for row in conn.execute(
            "SELECT data FROM consent_audit_log WHERE namespace = ? ORDER BY seq",
            (graph_id,),
        ).fetchall():
            audit_log.append(json.loads(row[0]))

        return {
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
            "audit_log": audit_log,
        }

    # ── Marketplace ───────────────────────────────────────────────

    def save_server_registration(
        self, mp_id: str, server_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO server_registrations "
            "(namespace, item_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (mp_id, server_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_server_registration(self, mp_id: str, server_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM server_registrations WHERE namespace = ? AND item_id = ?",
            (mp_id, server_id),
        )
        conn.commit()

    def append_marketplace_audit(self, mp_id: str, entry: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO marketplace_audit_log (namespace, data, created_at) "
            "VALUES (?, ?, ?)",
            (mp_id, json.dumps(entry), time.time()),
        )
        conn.commit()

    def load_marketplace(self, mp_id: str) -> dict[str, Any]:
        conn = self._get_conn()

        servers: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM server_registrations WHERE namespace = ?",
            (mp_id,),
        ).fetchall():
            servers[row[0]] = json.loads(row[1])

        audit_log: list[dict[str, Any]] = []
        for row in conn.execute(
            "SELECT data FROM marketplace_audit_log WHERE namespace = ? ORDER BY seq",
            (mp_id,),
        ).fetchall():
            audit_log.append(json.loads(row[0]))

        return {
            "servers": servers,
            "audit_log": audit_log,
        }

    # ── Tool Marketplace ──────────────────────────────────────────

    def save_tool_listing(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO tool_listings "
            "(namespace, item_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (mp_id, listing_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_tool_listing(self, mp_id: str, listing_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM tool_listings WHERE namespace = ? AND item_id = ?",
            (mp_id, listing_id),
        )
        conn.execute(
            "DELETE FROM tool_installs WHERE namespace = ? AND item_id = ?",
            (mp_id, listing_id),
        )
        conn.execute(
            "DELETE FROM tool_reviews WHERE namespace = ? AND item_id = ?",
            (mp_id, listing_id),
        )
        conn.commit()

    def append_tool_install(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO tool_installs (namespace, item_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (mp_id, listing_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def append_tool_review(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO tool_reviews (namespace, item_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (mp_id, listing_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def load_tool_marketplace(self, mp_id: str) -> dict[str, Any]:
        conn = self._get_conn()

        listings: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM tool_listings WHERE namespace = ?",
            (mp_id,),
        ).fetchall():
            listings[row[0]] = json.loads(row[1])

        installs: dict[str, list[dict[str, Any]]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM tool_installs WHERE namespace = ? ORDER BY seq",
            (mp_id,),
        ).fetchall():
            installs.setdefault(row[0], []).append(json.loads(row[1]))

        reviews: dict[str, list[dict[str, Any]]] = {}
        for row in conn.execute(
            "SELECT item_id, data FROM tool_reviews WHERE namespace = ? ORDER BY seq",
            (mp_id,),
        ).fetchall():
            reviews.setdefault(row[0], []).append(json.loads(row[1]))

        return {
            "listings": listings,
            "installs": installs,
            "reviews": reviews,
        }

    # ── Policy Proposals ────────────────────────────────────────

    def save_policy_proposal(
        self, governor_id: str, proposal_id: str, data: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO policy_proposals "
            "(namespace, item_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (governor_id, proposal_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def remove_policy_proposal(self, governor_id: str, proposal_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM policy_proposals WHERE namespace = ? AND item_id = ?",
            (governor_id, proposal_id),
        )
        conn.commit()

    def load_policy_proposals(self, governor_id: str) -> dict[str, dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT item_id, data FROM policy_proposals WHERE namespace = ?",
            (governor_id,),
        )
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

    # ── Policy Versioning ────────────────────────────────────────

    def save_policy_version(self, policy_set_id: str, data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO policy_versions (policy_set_id, data, updated_at) "
            "VALUES (?, ?, ?)",
            (policy_set_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def load_policy_versions(self, policy_set_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data FROM policy_versions WHERE policy_set_id = ?",
            (policy_set_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def save_policy_workbench_state(
        self,
        policy_set_id: str,
        data: dict[str, Any],
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO policy_workbench (policy_set_id, data, updated_at) "
            "VALUES (?, ?, ?)",
            (policy_set_id, json.dumps(data), time.time()),
        )
        conn.commit()

    def load_policy_workbench_state(
        self,
        policy_set_id: str,
    ) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data FROM policy_workbench WHERE policy_set_id = ?",
            (policy_set_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
