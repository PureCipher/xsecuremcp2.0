#!/usr/bin/env bash
# One command to run the whole demo.
#
#   ./demo/start_demo.sh           # start everything, open the browser
#   ./demo/start_demo.sh --auth    # same, but with registry auth on (admin/admin123)
#   ./demo/start_demo.sh --stop    # stop everything this launcher started
#
# It will:
#   1. start the registry on :8001 with --host-toolsets (required for tool calls),
#   2. wait for it to be healthy,
#   3. register the credential-free servers (DeepWiki + reference servers),
#   4. start the agent client app on :8800,
#   5. open http://localhost:8800 in your browser.
#
# Re-running is safe: anything already up is reused, not duplicated.
set -uo pipefail

# Resolve repo root from this script's location (works from anywhere).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/.demo_logs"
mkdir -p "$LOG_DIR"

REGISTRY_PORT="${REGISTRY_PORT:-8001}"
APP_PORT="${CLIENT_APP_PORT:-8800}"
REGISTRY_URL="http://localhost:$REGISTRY_PORT"
APP_URL="http://localhost:$APP_PORT"
AUTH=0

for arg in "$@"; do
  case "$arg" in
    --auth) AUTH=1 ;;
    --stop) STOP=1 ;;
  esac
done

open_browser() { command -v open >/dev/null 2>&1 && open "$1" || (command -v xdg-open >/dev/null 2>&1 && xdg-open "$1") || true; }
health() { curl -s -o /dev/null -w "%{http_code}" "$1/registry/health" 2>/dev/null; }
port_up() { curl -s -o /dev/null -w "%{http_code}" "http://localhost:$1" 2>/dev/null; }

# ---------------------------------------------------------------- stop
if [ "${STOP:-0}" = "1" ]; then
  echo "Stopping demo…"
  for name in registry client_app github_bridge; do
    pf="$LOG_DIR/$name.pid"
    if [ -f "$pf" ]; then
      pid="$(cat "$pf" 2>/dev/null || true)"
      [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null && echo "  stopped $name (pid $pid)"
      rm -f "$pf"
    fi
  done
  # Belt-and-suspenders: free the ports if anything is still bound.
  for p in "$REGISTRY_PORT" "$APP_PORT"; do
    pids="$(lsof -ti tcp:"$p" 2>/dev/null || true)"
    [ -n "$pids" ] && echo "  freeing port $p" && kill $pids 2>/dev/null || true
  done
  echo "Done."
  exit 0
fi

cd "$REPO_ROOT"

echo "==================================================="
echo " PureCipher demo launcher"
echo " repo:     $REPO_ROOT"
echo " registry: $REGISTRY_URL   app: $APP_URL   auth: $([ $AUTH = 1 ] && echo on || echo off)"
echo "==================================================="
echo ""

# ---------------------------------------------------------------- registry
if [ "$(health "$REGISTRY_URL")" = "200" ]; then
  echo "[1/4] Registry already healthy at $REGISTRY_URL — reusing it."
  echo "      (If tool calls fail with 'Session terminated', it was started"
  echo "       without --host-toolsets. Run './demo/start_demo.sh --stop' first.)"
else
  echo "[1/4] Starting registry on :$REGISTRY_PORT (with --host-toolsets)…"
  REG_ENV="PURECIPHER_SIGNING_SECRET=dev PURECIPHER_HOST_TOOLSETS=true"
  if [ "$AUTH" = "1" ]; then
    REG_ENV="$REG_ENV PURECIPHER_ENABLE_AUTH=true PURECIPHER_BOOTSTRAP_ADMIN_PASSWORD=admin123"
  fi
  # shellcheck disable=SC2086
  env $REG_ENV nohup uv run purecipher-registry --port "$REGISTRY_PORT" --host-toolsets \
    > "$LOG_DIR/registry.log" 2>&1 &
  echo $! > "$LOG_DIR/registry.pid"

  printf "      waiting for registry to come up"
  ok=0
  for _ in $(seq 1 90); do
    if [ "$(health "$REGISTRY_URL")" = "200" ]; then ok=1; break; fi
    printf "."; sleep 1
  done
  echo ""
  if [ "$ok" != "1" ]; then
    echo "      ERROR: registry did not become healthy. Last log lines:"
    tail -n 20 "$LOG_DIR/registry.log" 2>/dev/null | sed 's/^/        /'
    exit 1
  fi
  echo "      registry is up."
fi
echo ""

# ---------------------------------------------------------------- register servers
echo "[2/4] Registering demo servers…"
if [ "$AUTH" = "1" ]; then
  REGISTRY_URL="$REGISTRY_URL" ADMIN_USER=admin ADMIN_PASS=admin123 \
    bash "$SCRIPT_DIR/register_real_servers.sh" 2>&1 | sed 's/^/      /' | grep -E "✓|✗|→|SUMMARY|—" || true
else
  REGISTRY_URL="$REGISTRY_URL" bash "$SCRIPT_DIR/register_real_servers.sh" 2>&1 \
    | sed 's/^/      /' | grep -E "✓|✗|→|SUMMARY|—" || true
fi
echo ""

# ---------------------------------------------------------------- client app
if [ "$(port_up "$APP_PORT")" != "000" ]; then
  echo "[3/4] Agent app already running at $APP_URL — reusing it."
else
  echo "[3/4] Starting the agent app on :$APP_PORT…"
  REGISTRY_URL="$REGISTRY_URL" CLIENT_APP_PORT="$APP_PORT" \
    nohup uv run python "$SCRIPT_DIR/client_app/app.py" > "$LOG_DIR/client_app.log" 2>&1 &
  echo $! > "$LOG_DIR/client_app.pid"
  printf "      waiting for the app"
  for _ in $(seq 1 30); do
    if [ "$(port_up "$APP_PORT")" != "000" ]; then break; fi
    printf "."; sleep 1
  done
  echo ""
fi
echo ""

# ---------------------------------------------------------------- open
echo "[4/4] Opening $APP_URL …"
open_browser "$APP_URL"
echo ""
echo "==================================================="
echo " Demo is up."
echo "   Agent app:  $APP_URL"
echo "   Registry:   $REGISTRY_URL/registry/health"
echo "   Console UI: http://localhost:3000/registry   (start separately in xregistry if you want the dashboards)"
echo ""
echo " Logs:  $LOG_DIR/*.log"
echo " Stop:  ./demo/start_demo.sh --stop"
echo "==================================================="
