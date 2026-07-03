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
            echo "  3. Module-to-core compatibility (check_module_core_compatibility)"
            echo "  4. Module-core import linter (check_module_core_imports)"
            echo "  5. Type check (mypy)"
            echo "  6. Unit/integration tests (quickscale_core, quickscale_cli, modules)"
            echo "  7. E2E tests (optional, with --e2e flag)"
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

echo "[1/6] Installing dependencies..."
poetry install --with dev

echo ""
echo "[2/6] Running linters (ruff)..."
make lint -- --core --cli --modules
echo "✓ Linting passed"

echo ""
echo "[3/6] Running module-vs-core compatibility check..."
make check-core-compat || FAILED=true
if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Module-Core Compatibility Failed   ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Module-to-core compatibility passed"

echo ""
echo "[4/7] Running module-core import linter..."
make check-module-core-imports || FAILED=true
if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Module-Core Import Linter Failed   ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Module-core import linter passed"

echo ""
echo "[5/7] Running type checks (mypy)..."
make typecheck -- --core --cli --modules
echo "✓ Type checks passed"

echo ""
echo "[6/7] Running unit/integration tests..."
./scripts/test_unit.sh || FAILED=true

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
    echo "[7/7] Running E2E tests (this may take several minutes)..."
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
    echo "[7/7] Skipping E2E tests (use --e2e to include)"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   ✓ All CI Checks Passed!              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Ready to push to GitHub."
