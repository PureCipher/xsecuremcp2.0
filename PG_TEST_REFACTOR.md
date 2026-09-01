# Persistence test refactor: SQLite tmp_path → `registry_dsn` (Postgres)

The registry is now **Postgres-only** for durable persistence. Tests that used a
SQLite file under `tmp_path` for persistence must use the new session-provided
`registry_dsn` fixture (defined in `tests/conftest.py`), which yields a fresh,
migrated PostgreSQL database per test and drops it afterward. It auto-skips when
no Postgres server is reachable.

## The rule

Any test that constructs a registry store or `PureCipherRegistry` with a
persistence path derived from `tmp_path` (a `*.db` file) must instead take the
`registry_dsn` fixture and pass that DSN.

### Before
```python
def test_something(tmp_path) -> None:
    db_path = str(tmp_path / "reg.db")
    store = RegistryClientStore(db_path)
    ...
    # reopen to check persistence
    store2 = RegistryClientStore(db_path)
```

### After
```python
def test_something(registry_dsn) -> None:
    store = RegistryClientStore(registry_dsn)
    ...
    # reopen to check persistence — same DSN, same database
    store2 = RegistryClientStore(registry_dsn)
```

## Mechanics

1. Replace the `tmp_path` parameter with `registry_dsn` **only when** `tmp_path`
   was used solely for the persistence db path. If `tmp_path` is also used for
   other files, keep both params: `def test_x(tmp_path, registry_dsn)`.
2. Delete the `db_path = str(tmp_path / "...")` line; use `registry_dsn` directly
   wherever `db_path` was passed.
3. **Persistence-across-reopen tests still work**: constructing a second store on
   the same `registry_dsn` sees the same database, so "write, reopen, read"
   assertions are preserved.
4. `PureCipherRegistry(persistence_path=registry_dsn, ...)` — pass the DSN as
   `persistence_path`. The registry migrates + selects PostgresBackend by scheme.
5. If a test constructed the store with `ensure_schema=...`, leave that argument
   as-is; the DSN database is already migrated by the fixture.
6. Do NOT change assertions or test logic — only the persistence wiring.

## What NOT to touch

- `tests/server/security/test_sqlite_backend.py` — tests the library-level
  `SQLiteBackend` directly; SQLite remains a supported library backend. Leave it.
- Tests that use `tmp_path` for non-persistence reasons (config files, exports,
  spec files) — leave those uses alone.
- `:memory:` / in-memory fallback tests — a test that deliberately checks the
  in-memory (no-persistence) behavior by passing `None` should keep passing
  `None`. Only migrate the ones that used a real SQLite file for durability.

## Migration-specific tests

`tests/server/security/test_purecipher_migrations.py` tests
`migrate_registry_database`. It should now assert the Postgres path: call
`migrate_registry_database(registry_dsn)` and verify the expected tables exist by
querying `information_schema.tables` (via `psycopg.connect(registry_dsn)`), rather
than checking for a SQLite file on disk. If a test asserted a `.db` file was
created, convert it to assert the tables exist in the database.

## After editing each file

- `python3 -c "import ast; ast.parse(open('<file>').read())"` must pass. Bash path
  mapping: mac `/Users/purecipher/code/xsecuremcp2.0/...` = bash
  `/sessions/lucid-exciting-johnson/mnt/xsecuremcp2.0/...`.
- Grep the file for leftover `tmp_path / "` used as a db path and `.db"` — none
  should remain for persistence.
- Report which test functions you changed and any test whose intent was unclear.
