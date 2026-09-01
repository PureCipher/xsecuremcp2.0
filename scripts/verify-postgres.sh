#!/usr/bin/env bash
# Verify the PostgreSQL migration end-to-end on your machine.
#
# This spins up the compose PostgreSQL container, points the test suite at it,
# and runs the persistence + backend conformance tests. It exists because the
# migration was authored in an environment without Postgres or network access,
# so the authoritative verification must run where Docker + PyPI are available.
#
# Usage:
#   ./scripts/verify-postgres.sh            # full: lock, sync, up, migrate, test
#   ./scripts/verify-postgres.sh test-only  # assume deps + postgres already up
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.purecipher-registry.yml"
TEST_DSN="${PURECIPHER_TEST_DATABASE_URL:-postgresql://purecipher:purecipher@localhost:5432/purecipher}"
MODE="${1:-full}"

if [[ "$MODE" != "test-only" ]]; then
  echo "==> Regenerating uv.lock (pyproject added psycopg)"
  uv lock

  echo "==> Installing dependencies"
  uv sync

  echo "==> Starting PostgreSQL container"
  $COMPOSE up -d postgres

  echo "==> Waiting for PostgreSQL to be healthy"
  for i in $(seq 1 30); do
    if $COMPOSE exec -T postgres pg_isready -U purecipher -d purecipher >/dev/null 2>&1; then
      echo "    postgres is ready"
      break
    fi
    sleep 1
  done
fi

echo "==> Running static checks (ruff + ty)"
uv run prek run --all-files || {
  echo "!! prek reported issues — review above before committing"; }

echo "==> Running the PostgreSQL-backed test suite"
echo "    PURECIPHER_TEST_DATABASE_URL=$TEST_DSN"
PURECIPHER_TEST_DATABASE_URL="$TEST_DSN" uv run pytest -n auto \
  tests/server/security/test_postgres_backend.py \
  tests/server/security/test_purecipher_notification_feed.py \
  tests/server/security/test_purecipher_migrations.py \
  tests/server/security/test_purecipher_auth.py \
  tests/server/security/test_purecipher_registry.py \
  tests/server/security/test_purecipher_openapi_store.py \
  tests/server/security/test_purecipher_openapi_proxy_runtime.py \
  tests/server/security/test_purecipher_cli.py

echo
echo "==> Full suite (recommended before committing):"
echo "    PURECIPHER_TEST_DATABASE_URL=$TEST_DSN uv run pytest -n auto"
echo "==> Done."
