#!/usr/bin/env bash
# Sync src/ to u/admin/research_lib and push to Windmill
# Usage: bash scripts/sync_windmill.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

TARGET_DIR="u/admin/research_lib"

echo "Syncing src/ to ${TARGET_DIR}..."

# Remove existing directory/symlink
if [ -e "${TARGET_DIR}" ]; then
  echo "Removing existing ${TARGET_DIR}..."
  rm -rf "${TARGET_DIR}"
fi

# Create parent directory if it doesn't exist
mkdir -p "u/admin"

# Copy src/ to u/admin/research_lib
echo "Copying src/ to ${TARGET_DIR}..."
cp -r src "${TARGET_DIR}"

# Create __init__.py files to make u/ and u/admin/ proper Python packages
echo "Creating __init__.py files for package structure..."
touch "u/__init__.py"
touch "u/admin/__init__.py"

# Remove any auto-generated script metadata for __init__ files
# These are needed for Python imports but shouldn't be Windmill scripts
rm -f "u/__init__.script.yaml" "u/__init__.script.lock"
rm -f "u/admin/__init__.script.yaml" "u/admin/__init__.script.lock"

echo "Pushing to Windmill..."
wmill sync push --yes

echo "Sync complete. u/admin/research_lib now contains a copy of src/"
