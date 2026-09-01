# PostgreSQL migration + dockerization

The PureCipher registry now persists to **PostgreSQL** (previously SQLite), and
the Docker stack ships a Postgres container. Persistence is built in: point the
registry at a Postgres DSN and published listings, client identities/tokens, the
provenance ledger, consent and contracts persist until withdrawn/unregistered.

## TL;DR — run it

```bash
# From xsecuremcp2.0/
docker compose -f docker-compose.purecipher-registry.yml up --build
# Registry:  http://localhost:8000/registry/health
# Postgres:  localhost:5432  (db/user/pass: purecipher/purecipher/purecipher)
```

The registry connects via `DATABASE_URL`, creates its schema automatically
(Alembic migrations run on startup), and stores data in the named `pgdata`
volume — it survives `docker compose down` (use `down -v` to wipe).

## What changed

**New**
- `src/fastmcp/server/security/storage/pg_pool.py` — shared psycopg 3 connection
  pool (one per DSN, autocommit), `is_postgres_dsn`, `connection`, `transaction`.
- `src/fastmcp/server/security/storage/postgres.py` — `PostgresBackend`, the
  SecureMCP `StorageBackend` over PostgreSQL with JSONB documents. Exported from
  `fastmcp.server.security.storage` and `fastmcp.server.security`.
- `src/purecipher/pgdb.py` — re-exports the pool helpers + `sqlalchemy_url` for
  Alembic.
- `tests/.../test_postgres_backend.py` — backend conformance suite.
- `tests/conftest.py` — `registry_dsn` fixture: a fresh, migrated database per
  test, auto-skips when Postgres is unreachable.
- `scripts/verify-postgres.sh` — end-to-end verification harness.

**Rewritten to psycopg (Postgres-only, in-memory fallback kept for `None`)**
- `notification_feed.py`, `account_activity.py`, `user_preferences.py`,
  `control_plane_settings.py`, `clients.py`, `account_security.py`,
  `openapi_store.py` — `?`→`%s`, `INSERT OR REPLACE`→`ON CONFLICT DO UPDATE`,
  `AUTOINCREMENT`→`BIGSERIAL`, timestamps `REAL`→`DOUBLE PRECISION`; JSON columns
  stay `TEXT` (json.dumps/loads). Connections come from the shared pool.

**Wiring**
- `cli.py` — new `--database-url` / `DATABASE_URL` (a Postgres DSN, preferred).
  `--database-path` still parses but only a Postgres DSN yields durable storage;
  anything else runs ephemeral (in-memory) with a stderr warning.
- `registry.py` — `_make_security_backend` returns `PostgresBackend` for a
  Postgres DSN, else `None` (ephemeral). Migrations run only for a Postgres DSN.
- `db_migrations.py` — `migrate_registry_database` runs Alembic against a
  Postgres DSN (`postgresql+psycopg://`).
- Alembic migration timestamp columns changed `sa.REAL()` → `sa.Float()` so PG
  uses double precision (float4 would truncate Unix timestamps).
- `pyproject.toml` — added `psycopg[binary]`, `psycopg-pool`.
- Docker: `Dockerfile.purecipher-registry` defaults to `DATABASE_URL`;
  `docker-compose.purecipher-registry.yml` adds a `postgres:16-alpine` service
  with healthcheck, `depends_on: service_healthy`, and a `pgdata` volume.

## IMPORTANT — do this on your machine

1. **Regenerate the lock file.** `pyproject.toml` gained psycopg, so `uv.lock` is
   stale and the Docker build's `uv sync --frozen` will fail until you run:
   ```bash
   uv lock && uv sync
   ```
   (This could not be done in the authoring environment — no network there.)

2. **Run the suite against Postgres.** The suite is now Postgres-backed for
   persistence tests:
   ```bash
   docker compose -f docker-compose.purecipher-registry.yml up -d postgres
   export PURECIPHER_TEST_DATABASE_URL=postgresql://purecipher:purecipher@localhost:5432/purecipher
   uv run pytest -n auto
   ```
   Or just: `./scripts/verify-postgres.sh`. Without a reachable Postgres, the
   persistence + backend tests **skip** (they don't fail), so contributors
   without Postgres aren't blocked; CI should run a `postgres` service and set
   `PURECIPHER_TEST_DATABASE_URL`.

3. **Static checks:** `uv run prek run --all-files` (ruff + ty). I kept imports
   tight, but only your toolchain can confirm ty/ruff are clean.

## Notes / things to review

- **This was authored without a running Postgres or network**, so the code is
  correct-by-construction (mirrors the clean SQLite reference; every file is
  AST-valid) but has **not been executed**. Step 2 above is the authoritative
  check. Most likely spots for a first-run fixup: a per-store `ON CONFLICT`
  column set, or a row read that expected a tuple vs. dict.
- **`:memory:` and file paths now mean "ephemeral"** for the registry. Tests that
  needed durability were moved to `registry_dsn`; tests that only needed a
  working ephemeral store still pass `:memory:`/`None`.
- **`test_sqlite_backend.py` is unchanged** — `SQLiteBackend` remains a supported
  library backend; the registry just no longer uses it.
- **CI:** add a `postgres:16` service and set `PURECIPHER_TEST_DATABASE_URL` in
  the workflow so the persistence suite runs (and doesn't silently skip).
- Reference specs used during the port (safe to delete once merged):
  `PG_REWRITE_SPEC.md`, `PG_TEST_REFACTOR.md`.
