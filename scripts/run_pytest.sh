#!/usr/bin/env bash
# Run pytest with repo root on PYTHONPATH (and optional venv activation).
# Usage: bash scripts/run_pytest.sh [pytest args...]

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

# If a local venv exists, activate it to pick up dependencies.
if [[ -f "${REPO_ROOT}/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/venv/bin/activate"
fi

pytest "$@"

