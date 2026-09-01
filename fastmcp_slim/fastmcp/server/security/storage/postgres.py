"""PostgreSQL storage backend for SecureMCP.

Production-grade persistence for all security layers, backed by PostgreSQL.
This is the durable counterpart to :class:`SQLiteBackend`: the schema and the
return shapes are identical, but state lives in a shared PostgreSQL database
so multiple registry processes can read and write concurrently.

Design
------
- **One document column per row.** Every layer stores a JSON document in a
  ``JSONB`` column, namespaced by its component id (``ledger_id``,
  ``graph_id``, …) — the same layout as the SQLite backend. psycopg adapts
  ``JSONB`` transparently: writes wrap the dict in :class:`psycopg.types.json.Jsonb`,
  reads come back as native ``dict``/``list`` (no ``json.loads``).
- **Append-only vs. mutable.** ``append_*`` tables use a ``BIGSERIAL`` ``seq``
  for stable ordering; mutable tables use ``INSERT ... ON CONFLICT DO UPDATE``.
- **Connection pooling.** All statements borrow from the process-wide pool in
  :mod:`purecipher.pgdb`, keyed by DSN, with autocommit on — mirroring the
  per-operation commit the SQLite backend performed.

Example::

    from fastmcp.server.security.storage import PostgresBackend

    backend = PostgresBackend("postgresql://user:pass@localhost:5432/purecipher")
"""

from __future__ import annotations

import time
from typing import Any

from psycopg.types.json import Jsonb

from fastmcp.server.security.storage.pg_pool import connection

__all__ = ["PostgresBackend"]


class PostgresBackend:
    """PostgreSQL-backed persistent storage for SecureMCP.

    Args:
        dsn: PostgreSQL connection string
            (``postgresql://user:pass@host:port/dbname``). ``postgres://`` is
            accepted and normalized.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)
        self._ensure_schema()

    # ── Schema ────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provenance_records (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_prov_ns
                    ON provenance_records(namespace);

                CREATE TABLE IF NOT EXISTS exchange_entries (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exch_ns
                    ON exchange_entries(namespace);

                CREATE TABLE IF NOT EXISTS contracts (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS baselines (
                    namespace TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, actor_id, metric_name)
                );

                CREATE TABLE IF NOT EXISTS drift_events (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_drift_ns
                    ON drift_events(namespace);

                CREATE TABLE IF NOT EXISTS escalations (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_esc_ns
                    ON escalations(namespace);

                CREATE TABLE IF NOT EXISTS consent_nodes (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS consent_edges (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS consent_groups (
                    namespace TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    members JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, group_id)
                );

                CREATE TABLE IF NOT EXISTS consent_audit_log (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_consent_audit_ns
                    ON consent_audit_log(namespace);

                CREATE TABLE IF NOT EXISTS server_registrations (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS marketplace_audit_log (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mp_audit_ns
                    ON marketplace_audit_log(namespace);

                CREATE TABLE IF NOT EXISTS tool_listings (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS tool_installs (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tool_installs_ns
                    ON tool_installs(namespace);

                CREATE TABLE IF NOT EXISTS tool_reviews (
                    seq BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tool_reviews_ns
                    ON tool_reviews(namespace);

                CREATE TABLE IF NOT EXISTS policy_proposals (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (namespace, item_id)
                );

                CREATE TABLE IF NOT EXISTS policy_versions (
                    policy_set_id TEXT NOT NULL PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                );

                CREATE TABLE IF NOT EXISTS policy_workbench (
                    policy_set_id TEXT NOT NULL PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                );
                """
            )

    def close(self) -> None:
        """No-op for API parity with :class:`SQLiteBackend`.

        The underlying connection pool is process-wide and shared across
        backends and stores, so an individual backend does not close it.
        Use :func:`purecipher.pgdb.close_all_pools` at process shutdown.
        """

    # ── Provenance ────────────────────────────────────────────────

    def append_provenance_record(
        self, ledger_id: str, record_data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO provenance_records (namespace, item_id, data, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (
                    ledger_id,
                    record_data.get("record_id", ""),
                    Jsonb(record_data),
                    time.time(),
                ),
            )

    def load_provenance_records(self, ledger_id: str) -> list[dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT data FROM provenance_records WHERE namespace = %s ORDER BY seq",
                (ledger_id,),
            )
            return [row[0] for row in cur.fetchall()]

    # ── Exchange Log ──────────────────────────────────────────────

    def append_exchange_entry(self, log_id: str, entry_data: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO exchange_entries (namespace, item_id, data, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (
                    log_id,
                    entry_data.get("entry_id", ""),
                    Jsonb(entry_data),
                    time.time(),
                ),
            )

    def load_exchange_entries(self, log_id: str) -> list[dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT data FROM exchange_entries WHERE namespace = %s ORDER BY seq",
                (log_id,),
            )
            return [row[0] for row in cur.fetchall()]

    # ── Contracts ─────────────────────────────────────────────────

    def save_contract(
        self, broker_id: str, contract_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO contracts (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (broker_id, contract_id, Jsonb(data), time.time()),
            )

    def remove_contract(self, broker_id: str, contract_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM contracts WHERE namespace = %s AND item_id = %s",
                (broker_id, contract_id),
            )

    def load_contracts(self, broker_id: str) -> dict[str, dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT item_id, data FROM contracts WHERE namespace = %s",
                (broker_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    # ── Baselines ─────────────────────────────────────────────────

    def save_baseline(
        self,
        analyzer_id: str,
        actor_id: str,
        metric_name: str,
        data: dict[str, Any],
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO baselines "
                "(namespace, actor_id, metric_name, data, updated_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (namespace, actor_id, metric_name) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (analyzer_id, actor_id, metric_name, Jsonb(data), time.time()),
            )

    def remove_baseline(
        self, analyzer_id: str, actor_id: str, metric_name: str | None = None
    ) -> None:
        with connection(self._dsn) as conn:
            if metric_name is None:
                conn.execute(
                    "DELETE FROM baselines WHERE namespace = %s AND actor_id = %s",
                    (analyzer_id, actor_id),
                )
            else:
                conn.execute(
                    "DELETE FROM baselines "
                    "WHERE namespace = %s AND actor_id = %s AND metric_name = %s",
                    (analyzer_id, actor_id, metric_name),
                )

    def load_baselines(self, analyzer_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT actor_id, metric_name, data FROM baselines WHERE namespace = %s",
                (analyzer_id,),
            )
            result: dict[str, dict[str, dict[str, Any]]] = {}
            for actor_id, metric_name, data in cur.fetchall():
                result.setdefault(actor_id, {})[metric_name] = data
            return result

    # ── Drift History ─────────────────────────────────────────────

    def append_drift_event(self, analyzer_id: str, event_data: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO drift_events (namespace, item_id, data, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (
                    analyzer_id,
                    event_data.get("event_id", ""),
                    Jsonb(event_data),
                    time.time(),
                ),
            )

    def load_drift_history(self, analyzer_id: str) -> list[dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT data FROM drift_events WHERE namespace = %s ORDER BY seq",
                (analyzer_id,),
            )
            return [row[0] for row in cur.fetchall()]

    # ── Escalation History ────────────────────────────────────────

    def append_escalation(self, engine_id: str, data: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO escalations (namespace, data, created_at) "
                "VALUES (%s, %s, %s)",
                (engine_id, Jsonb(data), time.time()),
            )

    def load_escalations(self, engine_id: str) -> list[dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT data FROM escalations WHERE namespace = %s ORDER BY seq",
                (engine_id,),
            )
            return [row[0] for row in cur.fetchall()]

    # ── Consent Graph ─────────────────────────────────────────────

    def save_consent_node(
        self, graph_id: str, node_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO consent_nodes (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (graph_id, node_id, Jsonb(data), time.time()),
            )

    def remove_consent_node(self, graph_id: str, node_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM consent_nodes WHERE namespace = %s AND item_id = %s",
                (graph_id, node_id),
            )

    def save_consent_edge(
        self, graph_id: str, edge_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO consent_edges (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (graph_id, edge_id, Jsonb(data), time.time()),
            )

    def remove_consent_edge(self, graph_id: str, edge_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM consent_edges WHERE namespace = %s AND item_id = %s",
                (graph_id, edge_id),
            )

    def save_consent_group(
        self, graph_id: str, group_id: str, members: list[str]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO consent_groups (namespace, group_id, members, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, group_id) DO UPDATE SET "
                "members = EXCLUDED.members, updated_at = EXCLUDED.updated_at",
                (graph_id, group_id, Jsonb(members), time.time()),
            )

    def remove_consent_group(self, graph_id: str, group_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM consent_groups WHERE namespace = %s AND group_id = %s",
                (graph_id, group_id),
            )

    def append_consent_audit(self, graph_id: str, entry: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO consent_audit_log (namespace, data, created_at) "
                "VALUES (%s, %s, %s)",
                (graph_id, Jsonb(entry), time.time()),
            )

    def load_consent_graph(self, graph_id: str) -> dict[str, Any]:
        with connection(self._dsn) as conn:
            nodes: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM consent_nodes WHERE namespace = %s",
                (graph_id,),
            ).fetchall():
                nodes[row[0]] = row[1]

            edges: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM consent_edges WHERE namespace = %s",
                (graph_id,),
            ).fetchall():
                edges[row[0]] = row[1]

            groups: dict[str, list[str]] = {}
            for row in conn.execute(
                "SELECT group_id, members FROM consent_groups WHERE namespace = %s",
                (graph_id,),
            ).fetchall():
                groups[row[0]] = row[1]

            audit_log = [
                row[0]
                for row in conn.execute(
                    "SELECT data FROM consent_audit_log WHERE namespace = %s ORDER BY seq",
                    (graph_id,),
                ).fetchall()
            ]

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
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO server_registrations (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (mp_id, server_id, Jsonb(data), time.time()),
            )

    def remove_server_registration(self, mp_id: str, server_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM server_registrations WHERE namespace = %s AND item_id = %s",
                (mp_id, server_id),
            )

    def append_marketplace_audit(self, mp_id: str, entry: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO marketplace_audit_log (namespace, data, created_at) "
                "VALUES (%s, %s, %s)",
                (mp_id, Jsonb(entry), time.time()),
            )

    def load_marketplace(self, mp_id: str) -> dict[str, Any]:
        with connection(self._dsn) as conn:
            servers: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM server_registrations WHERE namespace = %s",
                (mp_id,),
            ).fetchall():
                servers[row[0]] = row[1]

            audit_log = [
                row[0]
                for row in conn.execute(
                    "SELECT data FROM marketplace_audit_log WHERE namespace = %s ORDER BY seq",
                    (mp_id,),
                ).fetchall()
            ]

        return {
            "servers": servers,
            "audit_log": audit_log,
        }

    # ── Tool Marketplace ──────────────────────────────────────────

    def save_tool_listing(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO tool_listings (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (mp_id, listing_id, Jsonb(data), time.time()),
            )

    def remove_tool_listing(self, mp_id: str, listing_id: str) -> None:
        with connection(self._dsn) as conn, conn.transaction():
            conn.execute(
                "DELETE FROM tool_listings WHERE namespace = %s AND item_id = %s",
                (mp_id, listing_id),
            )
            conn.execute(
                "DELETE FROM tool_installs WHERE namespace = %s AND item_id = %s",
                (mp_id, listing_id),
            )
            conn.execute(
                "DELETE FROM tool_reviews WHERE namespace = %s AND item_id = %s",
                (mp_id, listing_id),
            )

    def append_tool_install(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO tool_installs (namespace, item_id, data, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (mp_id, listing_id, Jsonb(data), time.time()),
            )

    def append_tool_review(
        self, mp_id: str, listing_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO tool_reviews (namespace, item_id, data, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (mp_id, listing_id, Jsonb(data), time.time()),
            )

    def load_tool_marketplace(self, mp_id: str) -> dict[str, Any]:
        with connection(self._dsn) as conn:
            listings: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM tool_listings WHERE namespace = %s",
                (mp_id,),
            ).fetchall():
                listings[row[0]] = row[1]

            installs: dict[str, list[dict[str, Any]]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM tool_installs WHERE namespace = %s ORDER BY seq",
                (mp_id,),
            ).fetchall():
                installs.setdefault(row[0], []).append(row[1])

            reviews: dict[str, list[dict[str, Any]]] = {}
            for row in conn.execute(
                "SELECT item_id, data FROM tool_reviews WHERE namespace = %s ORDER BY seq",
                (mp_id,),
            ).fetchall():
                reviews.setdefault(row[0], []).append(row[1])

        return {
            "listings": listings,
            "installs": installs,
            "reviews": reviews,
        }

    # ── Policy Proposals ────────────────────────────────────────

    def save_policy_proposal(
        self, governor_id: str, proposal_id: str, data: dict[str, Any]
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO policy_proposals (namespace, item_id, data, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (namespace, item_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (governor_id, proposal_id, Jsonb(data), time.time()),
            )

    def remove_policy_proposal(self, governor_id: str, proposal_id: str) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM policy_proposals WHERE namespace = %s AND item_id = %s",
                (governor_id, proposal_id),
            )

    def load_policy_proposals(self, governor_id: str) -> dict[str, dict[str, Any]]:
        with connection(self._dsn) as conn:
            cur = conn.execute(
                "SELECT item_id, data FROM policy_proposals WHERE namespace = %s",
                (governor_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    # ── Policy Versioning ────────────────────────────────────────

    def save_policy_version(self, policy_set_id: str, data: dict[str, Any]) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO policy_versions (policy_set_id, data, updated_at) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (policy_set_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (policy_set_id, Jsonb(data), time.time()),
            )

    def load_policy_versions(self, policy_set_id: str) -> dict[str, Any] | None:
        with connection(self._dsn) as conn:
            row = conn.execute(
                "SELECT data FROM policy_versions WHERE policy_set_id = %s",
                (policy_set_id,),
            ).fetchone()
        if row is None:
            return None
        return row[0]

    def save_policy_workbench_state(
        self,
        policy_set_id: str,
        data: dict[str, Any],
    ) -> None:
        with connection(self._dsn) as conn:
            conn.execute(
                "INSERT INTO policy_workbench (policy_set_id, data, updated_at) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (policy_set_id) DO UPDATE SET "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (policy_set_id, Jsonb(data), time.time()),
            )

    def load_policy_workbench_state(
        self,
        policy_set_id: str,
    ) -> dict[str, Any] | None:
        with connection(self._dsn) as conn:
            row = conn.execute(
                "SELECT data FROM policy_workbench WHERE policy_set_id = %s",
                (policy_set_id,),
            ).fetchone()
        if row is None:
            return None
        return row[0]
