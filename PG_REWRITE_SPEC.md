# SQLite → PostgreSQL store conversion spec (Postgres-only)

You are converting a PureCipher registry store from `sqlite3` to PostgreSQL via
`psycopg` 3. The registry is now **Postgres-only** for durable persistence; each
store keeps its existing **in-memory fallback** for the non-persistent case.

## The shared connection helper (use this — do NOT open psycopg directly)

Module: `purecipher.pgdb` (thin re-export of `fastmcp.server.security.storage.pg_pool`).

```python
from purecipher.pgdb import connection, transaction, is_postgres_dsn, dict_row
```

- `connection(dsn, *, row_factory=tuple_row) -> ContextManager[psycopg.Connection]`
  Borrows a pooled connection. **Autocommit is ON** — every executed statement
  is durable immediately, so do NOT call `conn.commit()` and do NOT call
  `conn.close()` (the pool owns the connection).
- `transaction(dsn, *, row_factory=tuple_row)` — same, but wraps the block in an
  explicit transaction (commit on clean exit, rollback on exception). Use only
  when several statements must land atomically (e.g. delete-with-dependents).
- `is_postgres_dsn(value) -> bool` — True for `postgres://` / `postgresql://`.
- `dict_row` — pass as `row_factory=dict_row` when the code reads columns by
  name (e.g. `row["username"]`). Use the default (tuple rows) for positional
  reads (`row[0]`).

`conn.execute(sql, params)` returns a cursor; `.fetchone()` / `.fetchall()` work
as before. `conn.execute` is fine for single statements; use `conn.cursor()` only
if the existing code did.

## The persistence-vs-memory branch

Every store currently branches `if self._db_path: <sqlite> else: <memory>`.
Convert it to:

```python
if is_postgres_dsn(self._db_path):
    with connection(self._db_path, row_factory=dict_row) as conn:
        ...
else:
    <existing in-memory fallback, UNCHANGED>
```

**Preserve the in-memory fallback exactly** (same behavior, same data shapes).
Non-Postgres values (None, a file path, `:memory:`) all take the memory branch.
If a store has NO memory fallback today (it always connected), keep that: replace
the SQLite connect with the Postgres branch, and for a non-Postgres `db_path`
raise the same kind of error it would have raised before, OR — preferred — treat
it as "no persistence" only if the file already did so. Do not invent new behavior;
match the original semantics for the non-Postgres case as closely as possible.
When in doubt for a store that always required a DB, guard with
`if is_postgres_dsn(self._db_path):` for the DB path and leave a clear
`# no-op / in-memory when not configured for Postgres` else-branch mirroring any
existing None handling.

## Mechanical SQL translation rules

1. **Placeholders:** `?` → `%s` (every one).
2. **Upserts:** `INSERT OR REPLACE INTO t (cols...) VALUES (...)` →
   `INSERT INTO t (cols...) VALUES (...) ON CONFLICT (<pk cols>) DO UPDATE SET
   col = EXCLUDED.col, ...` for every non-PK column. Use the table's PRIMARY KEY
   column(s) in the `ON CONFLICT (...)` target. (The existing `ON CONFLICT(x) DO
   UPDATE SET ...` statements are already Postgres-compatible — just fix `?`→`%s`.)
3. **Autoincrement id:** columns declared `INTEGER PRIMARY KEY AUTOINCREMENT`
   become `BIGSERIAL PRIMARY KEY` in any `CREATE TABLE` you keep in the store.
4. **Float/time columns:** `REAL` → `DOUBLE PRECISION`. (Timestamps are
   `time.time()` floats — must be double precision, never `REAL`/float4.)
5. **JSON columns stay TEXT.** These stores `json.dumps(...)` into TEXT columns
   and `json.loads(...)` on read. **Keep that** — do NOT switch to JSONB. Only the
   SecureMCP StorageBackend uses JSONB; these bespoke stores keep TEXT + json.
6. **Booleans:** if any column stored 0/1 ints for bools, keep writing ints
   (`BOOLEAN`/`INTEGER` both accept 0/1 via psycopg only if column is INTEGER;
   keep the column INTEGER to match). Prefer leaving types as they were, mapped:
   TEXT→TEXT, INTEGER→BIGINT, REAL→DOUBLE PRECISION.
7. **Schema creation (`_ensure_*` / `_ensure_sqlite`):** rename to a neutral name
   (e.g. `_ensure_schema`) and issue Postgres DDL with `CREATE TABLE IF NOT
   EXISTS` using the type mapping above. This is a safety net; the Alembic chain
   normally owns the schema, but keeping an idempotent creator lets a store
   bootstrap its own table. Keep the `ensure_schema` constructor flag and only
   create when `is_postgres_dsn(self._db_path) and ensure_schema`.
8. **Remove** `conn.commit()` and `conn.close()` in the Postgres branch
   (autocommit + pooled). Use `with connection(...) as conn:`.
9. **Row access:** if code used `sqlite3.Row` / accessed columns by name, pass
   `row_factory=dict_row`. Wrap tuple positional reads with default tuple rows.
   Check how the file reads results and pick per call site.
10. **`sqlite3.connect(":memory:")` shared-connection tricks:** these were a
    SQLite way to get an isolated in-memory DB. Under Postgres-only, route them
    to the store's **in-memory Python fallback** (dict/deque), NOT to Postgres.
11. **Exceptions:** replace `except sqlite3.Error` / `sqlite3.OperationalError`
    with `except psycopg.Error` (import `psycopg`). Never use bare `except`.
12. **`INTEGER PRIMARY KEY` returning lastrowid:** if the code used
    `cursor.lastrowid`, use `INSERT ... RETURNING id` and read the value.
13. **`LIMIT ?`** works with `%s`. **`ORDER BY id DESC`** unchanged.
14. **`DELETE` / `UPDATE`** — just `?`→`%s`.

## Import cleanup

- Remove `import sqlite3` if no longer referenced. Add `import psycopg` only if you
  reference `psycopg.Error`. Add the `from purecipher.pgdb import ...` you use.
- Keep `import json`, `import time`, etc.

## Constraints

- Preserve every public method signature and return shape **exactly**.
- Preserve docstrings; update wording that says "SQLite" to "PostgreSQL" where it
  describes the persistence path.
- Do not change the in-memory fallback logic or data structures.
- The file MUST parse (`python3 -c "import ast; ast.parse(open(F).read())"`).
- Do not add new dependencies.
- Match the column names/types used by the Alembic migrations in
  `src/purecipher/migrations/versions/` (the schema source of truth). Read the
  relevant migration for your table(s) and mirror the columns exactly.

## After editing

Run: `python3 -c "import ast; ast.parse(open('<file>').read())"` and confirm OK.
Grep the file for leftover `sqlite3`, `?` placeholders inside SQL strings,
`INSERT OR REPLACE`, `AUTOINCREMENT`, `.commit()`, `.close()` in the Postgres
branch — none should remain in the Postgres path.
Report exactly which methods you changed and any place you were unsure.
