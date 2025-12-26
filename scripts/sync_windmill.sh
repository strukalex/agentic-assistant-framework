#!/usr/bin/env bash
# Sync Windmill scripts to workspace
# Usage: bash scripts/sync_windmill.sh
#
# Note: With the custom Windmill Docker image, paias is pre-installed,
# so we no longer need to copy src/ to u/admin/research_lib/

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "Syncing Windmill scripts..."

# Clean up old u/admin/research_lib if it exists (from previous approach)
if [ -e "u/admin/research_lib" ]; then
  echo "Removing old u/admin/research_lib directory (no longer needed)..."
  rm -rf "u/admin/research_lib"
fi

# Clean up old __init__.py files
if [ -e "u/__init__.py" ]; then
  rm -f "u/__init__.py" "u/__init__.script.yaml" "u/__init__.script.lock"
fi
if [ -e "u/admin/__init__.py" ]; then
  rm -f "u/admin/__init__.py" "u/admin/__init__.script.yaml" "u/admin/__init__.script.lock"
fi

# Remove u/admin directory if it's now empty
if [ -d "u/admin" ] && [ -z "$(ls -A u/admin)" ]; then
  rmdir "u/admin"
fi

# Remove u/ directory if it's now empty
if [ -d "u" ] && [ -z "$(ls -A u)" ]; then
  rmdir "u"
fi

echo "Pushing to Windmill..."
wmill sync push --yes

echo "Sync complete. Scripts pushed to Windmill."
echo "Note: paias package is pre-installed in the custom Windmill worker image."
