"""Shared PostgreSQL connection pooling for SecureMCP storage.

A single process-wide connection pool per DSN backs the
:class:`~fastmcp.server.security.storage.postgres.PostgresBackend` and any
higher-level stores (e.g. the PureCipher registry) that persist to the same
database. Opening one pool per database — rather than a connection per
statement — keeps PostgreSQL connection counts bounded under concurrency.

This module lives in the ``fastmcp`` library layer so it carries no
dependency on application packages. Autocommit is enabled on pooled
connections, reproducing the per-operation durability the SQLite backend
provided; use :func:`transaction` when several statements must be atomic.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row, tuple_row
from psycopg_pool import ConnectionPool

__all__ = [
    "is_postgres_dsn",
    "normalize_dsn",
    "get_pool",
    "connection",
    "transaction",
    "close_all_pools",
    "dict_row",
    "tuple_row",
]

_POSTGRES_SCHEMES = ("postgresql://", "postgres://")

_POOLS: dict[str, ConnectionPool] = {}
_POOLS_LOCK = threading.Lock()


def is_postgres_dsn(value: str | None) -> bool:
    """Return True if ``value`` looks like a PostgreSQL connection string."""
    if not value:
        return False
    return value.strip().lower().startswith(_POSTGRES_SCHEMES)


def normalize_dsn(value: str) -> str:
    """Normalize a DSN to the ``postgresql://`` form psycopg expects."""
    dsn = value.strip()
    if dsn.lower().startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://") :]
    return dsn


def _pool_max_size() -> int:
    raw = (os.getenv("PURECIPHER_PG_POOL_MAX") or "").strip()
    try:
        return max(1, int(raw)) if raw else 10
    except ValueError:
        return 10


def get_pool(dsn: str) -> ConnectionPool:
    """Return (creating on first use) the shared connection pool for ``dsn``."""
    key = normalize_dsn(dsn)
    with _POOLS_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            pool = ConnectionPool(
                conninfo=key,
                min_size=1,
                max_size=_pool_max_size(),
                kwargs={"autocommit": True},
                open=True,
            )
            _POOLS[key] = pool
        return pool


@contextmanager
def connection(
    dsn: str,
    *,
    row_factory: Any = tuple_row,
) -> Iterator[psycopg.Connection]:
    """Borrow a pooled connection with the requested row factory.

    Returned to the pool on exit. With autocommit on, each executed
    statement is durable immediately.
    """
    pool = get_pool(dsn)
    with pool.connection() as conn:
        conn.row_factory = row_factory
        yield conn


@contextmanager
def transaction(
    dsn: str,
    *,
    row_factory: Any = tuple_row,
) -> Iterator[psycopg.Connection]:
    """Borrow a pooled connection wrapped in an explicit transaction.

    Commits on clean exit, rolls back on exception. Use when several
    statements must land atomically.
    """
    pool = get_pool(dsn)
    with pool.connection() as conn:
        conn.row_factory = row_factory
        with conn.transaction():
            yield conn


def close_all_pools() -> None:
    """Close every open pool. Intended for test teardown / shutdown hooks."""
    with _POOLS_LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()
    for pool in pools:
        try:
            pool.close()
        except Exception:  # noqa: BLE001 - teardown must not raise
            pass
