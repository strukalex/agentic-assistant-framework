#!/usr/bin/env bash
# Reset local infra, re-create the DB schema, and set PYTHONPATH for tooling.
# Usage: bash scripts/reset_dev_env.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Prefer docker compose plugin, fall back to docker-compose binary
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose (or docker-compose) is required but not found." >&2
  exit 1
fi

# Ensure Python can import from paias when running alembic/tests
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

echo "Stopping containers..."
"${COMPOSE_CMD[@]}" down || true
echo "Removing containers and volumes..."
"${COMPOSE_CMD[@]}" down -v || true

echo "Starting infra..."
"${COMPOSE_CMD[@]}" up -d

echo "Waiting for postgres to become healthy..."
for i in {1..30}; do
  if "${COMPOSE_CMD[@]}" exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
    echo "Postgres is ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "Postgres did not become ready in time." >&2
    exit 1
  fi
  sleep 1
done

echo "Applying migrations (alembic upgrade head)..."
alembic upgrade head

echo "Waiting for Windmill to become healthy..."
for i in {1..60}; do
  if curl -sf http://localhost:8100/api/version >/dev/null 2>&1; then
    echo "Windmill is ready."
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "Windmill did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

echo "Configuring Windmill workspace..."
# Wait a bit more for Windmill to fully initialize
sleep 5

# Try to add workspace with --create flag
# This will prompt for interactive login if needed
echo "Adding Windmill workspace (you may need to authenticate)..."
wmill workspace add default http://localhost:8100 --create || {
  echo "⚠️  Workspace configuration failed. You can configure it manually later."
  echo "   Run: wmill workspace add default http://localhost:8100 --create"
}

echo ""
echo "Syncing scripts to Windmill workspace..."
bash "${SCRIPT_DIR}/sync_windmill.sh" || {
  echo "⚠️  Sync failed. You can sync manually later with: npm run sync:windmill"
}

echo ""
echo "✅ Reset complete. PYTHONPATH is set to: ${PYTHONPATH}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Windmill is ready at: http://localhost:8100"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Default credentials: admin / changeme"
echo "  Scripts deployed to: f/research/run_research"
echo ""
echo "  To test the workflow:"
echo "    1. Open http://localhost:8100"
echo "    2. Go to Scripts → f/research/run_research"
echo "    3. Run with sample data"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

