#!/usr/bin/env bash
set -euo pipefail

# Local CI check script — THE single pre-push script to verify the same steps
# as GitHub Actions (install + lint + typecheck + all package tests).
#
# Usage:
#   ./scripts/check_ci_locally.sh          # Standard check (lint + type + unit tests)
#   ./scripts/check_ci_locally.sh --e2e    # Full check including E2E tests (slow)
#   ./scripts/check_ci_locally.sh --help   # Show help

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# Parse arguments
RUN_E2E=false
for arg in "$@"; do
    case $arg in
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/check_ci_locally.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --e2e     Include E2E tests (slow, requires Docker)"
            echo "  --help    Show this help message"
            echo ""
            echo "This script runs all checks that GitHub Actions CI runs:"
            echo "  1. Install dependencies"
            echo "  2. Lint (ruff check + format)"
            echo "  3. Type check (mypy)"
            echo "  4. Unit/integration tests (quickscale_core, quickscale_cli, modules)"
            echo "  5. E2E tests (optional, with --e2e flag)"
            exit 0
            ;;
    esac
done

echo "╔════════════════════════════════════════╗"
echo "║   QuickScale Local CI Check            ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Track overall status
FAILED=false

echo "[1/5] Installing dependencies..."
poetry install --with dev

echo ""
echo "[2/5] Running linters (ruff)..."
poetry run ruff check quickscale_core quickscale_cli
poetry run ruff format quickscale_core quickscale_cli
poetry run ruff format --check quickscale_core quickscale_cli
echo "✓ Linting passed"

echo ""
echo "[3/5] Running type checks (mypy)..."
poetry run mypy quickscale_core/src/ quickscale_cli/src/
echo "✓ Type checks passed"

echo ""
echo "[4/5] Running unit/integration tests..."

echo "  → Testing quickscale_core..."
poetry run pytest quickscale_core -m "not e2e" --cov=quickscale_core --cov-report=term -q || FAILED=true

echo "  → Testing quickscale_cli..."
poetry run pytest quickscale_cli -m "not e2e" --cov=quickscale_cli --cov-report=term -q || FAILED=true

echo "  → Testing quickscale_modules..."
for mod in quickscale_modules/*; do
    if [ -d "$mod" ] && [ -d "$mod/tests" ]; then
        mod_name=$(basename "$mod")
        echo "    → Testing module: $mod_name"
        poetry run pytest "$mod" --cov="$mod/src" --cov-report=term -q || FAILED=true
    fi
done

if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Unit/Integration Tests Failed      ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ All unit/integration tests passed"

# Optional E2E tests
if [ "$RUN_E2E" = true ]; then
    echo ""
    echo "[5/5] Running E2E tests (this may take several minutes)..."
    ./scripts/test_e2e.sh || FAILED=true

    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ E2E Tests Failed                   ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ E2E tests passed"
else
    echo ""
    echo "[5/5] Skipping E2E tests (use --e2e to include)"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   ✓ All CI Checks Passed!              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Ready to push to GitHub."
