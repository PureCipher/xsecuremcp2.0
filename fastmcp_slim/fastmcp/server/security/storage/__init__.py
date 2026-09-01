"""Pluggable storage backends for SecureMCP.

Provides a ``StorageBackend`` protocol and three implementations:

- ``MemoryBackend``: In-memory (default, matches existing behavior).
- ``SQLiteBackend``: Single-file SQLite persistence.
- ``PostgresBackend``: PostgreSQL persistence (production).
"""

from fastmcp.server.security.storage.backend import StorageBackend
from fastmcp.server.security.storage.memory import MemoryBackend
from fastmcp.server.security.storage.postgres import PostgresBackend
from fastmcp.server.security.storage.sqlite import SQLiteBackend

__all__ = [
    "MemoryBackend",
    "PostgresBackend",
    "SQLiteBackend",
    "StorageBackend",
]
