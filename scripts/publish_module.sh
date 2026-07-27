#!/usr/bin/env bash
# Publish module changes to split branches (F2.8 provenance-aware wrapper).
#
# This script is a thin compatibility shim that delegates to the
# provenance-aware Python wrapper at scripts/publish_module.py.
# The Python wrapper uses the helper surface from
# quickscale_core.utils.git_utils for module-path and branch resolution,
# replacing the hardcoded conventions that previously lived here.
#
# Phase 4 (SA117): All mutating single-module publish calls require
# ``--expected-remote-sha <40hex|ABSENT>``.  Use via Makefile:
#   make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<sha|ABSENT>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ensure we are running from the repository root (the Python wrapper
# resolves paths relative to the repo root).
if [ ! -d "$REPO_ROOT/quickscale_modules" ]; then
    echo "❌ quickscale_modules directory not found. Are you in the QuickScale repository root?" >&2
    exit 1
fi

exec poetry run python "$SCRIPT_DIR/publish_module.py" "$@"
