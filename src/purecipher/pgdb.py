"""PostgreSQL connectivity for the PureCipher registry.

The registry persists to PostgreSQL in production. Every store (client
identities, OpenAPI toolsets, notifications, account security, …) shares the
single process-wide connection pool defined in the library layer
(:mod:`fastmcp.server.security.storage.pg_pool`) so we open one pool per
database rather than a connection per statement.

This module re-exports the shared pool helpers and adds the app-level
:func:`sqlalchemy_url` used by the Alembic migrations.

Only PostgreSQL DSNs are supported (``postgres://`` / ``postgresql://``). A
``None`` persistence target means "no persistence" and is handled by each
store's in-memory fallback — it never reaches this module.
"""

from __future__ import annotations

from fastmcp.server.security.storage.pg_pool import (
    close_all_pools,
    connection,
    dict_row,
    get_pool,
    is_postgres_dsn,
    normalize_dsn,
    transaction,
    tuple_row,
)

__all__ = [
    "is_postgres_dsn",
    "normalize_dsn",
    "sqlalchemy_url",
    "get_pool",
    "connection",
    "transaction",
    "close_all_pools",
    "dict_row",
    "tuple_row",
]


def sqlalchemy_url(value: str) -> str:
    """Return a SQLAlchemy URL that binds the psycopg (v3) driver.

    Alembic runs through SQLAlchemy; ``postgresql+psycopg://`` selects the
    psycopg 3 driver so we don't need psycopg2 installed as well.
    """
    dsn = normalize_dsn(value)
    if dsn.lower().startswith("postgresql+"):
        return dsn
    return "postgresql+psycopg://" + dsn[len("postgresql://") :]
