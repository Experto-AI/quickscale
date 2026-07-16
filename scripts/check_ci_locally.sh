#!/usr/bin/env bash
set -euo pipefail

# Local CI check script — the single pre-push script to verify the primary local
# development checks (install + lint + typecheck + unit tests + optional
# integration tests when PostgreSQL is available).
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
echo "This script runs the primary local development checks:"
echo "  1. Install dependencies"
echo "  2. Lint (ruff check + format)"
echo "  3. Module-to-core compatibility (check_module_core_compatibility)"
echo "  4. Module-core import linter (check_module_core_imports)"
echo "  5. Manifest sync gate (sync_module_manifests)"
echo "  6. Org-context primitives gate (check_org_context_primitives)"
echo "  7. CSRF-exempt gate (check_csrf_exempt_gate)"
echo "  8. Type check (mypy)"
echo "  9. Coverage policy helper tests"
echo " 10. Combined coverage checks (core + CLI + backups module with dual-threshold policy)"
echo " 11. Integration tests (requires PostgreSQL)"
echo " 12. E2E tests (optional, with --e2e flag)"
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

echo "[1/11] Installing dependencies..."
poetry install --with dev

echo ""
echo "[2/11] Running linters (ruff)..."
make lint -- --core --cli --modules
echo "✓ Linting passed"

echo ""
echo "[3/11] Running module-vs-core compatibility check..."
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
echo "[4/11] Running module-core import linter..."
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
echo "[5/11] Running manifest sync gate..."
make check-manifest-sync || FAILED=true
if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Manifest Sync Gate Failed          ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Manifest snapshots in sync"

echo ""
echo "[6/11] Running org-context primitives gate..."
make check-org-context-primitives || FAILED=true
if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Org-Context Primitives Gate Failed  ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ No direct external use of privatized org-context primitives"

echo ""
echo "[7/11] Running CSRF-exempt gate..."
make check-csrf-exempt || FAILED=true
if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ CSRF-Exempt Gate Failed            ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ All csrf_exempt callsites are protected"

echo ""
echo "[8/11] Running type checks (mypy)..."
make typecheck -- --core --cli --modules
echo "✓ Type checks passed"

echo ""
echo "[9/11] Running coverage policy helper tests..."
make test-cov-policy || FAILED=true

if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Coverage Policy Helper Tests Failed║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Coverage policy helper tests passed"

echo ""
make test-integration-worker-pool || FAILED=true

if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Worker Pool Harness Tests Failed   ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Worker pool harness tests passed"

echo ""
echo "[10/11] Running coverage checks (core + CLI + backups)..."
make test-cov REQUIRE_BACKUPS_COVERAGE=1 || FAILED=true

if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Coverage Checks Failed             ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Combined coverage checks passed (90% equal-weight package mean, 80% per-file)"

echo ""
echo "[11/11] Running integration tests..."
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -q 2>/dev/null; then
    echo "PostgreSQL is available — running integration tests..."
    ./scripts/test_integration.sh || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Integration Tests Failed           ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Integration tests passed"
else
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║   ✗ PostgreSQL Not Available                               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
  echo "  Integration tests require PostgreSQL 18 with a LOGIN CREATEDB"
  echo "  NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE role on localhost:5432."
    echo ""
    echo "  QuickScale uses a split test model to separate DB-free"
    echo "  unit tests from PostgreSQL-backed integration tests:"
    echo ""
    echo "    make test-unit           DB-free unit tests (core + CLI)"
    echo "    make test-integration    Integration tests (requires PostgreSQL)"
    echo ""
    echo "  To run checks locally without PostgreSQL, use:"
    echo "    make test-unit"
    echo ""
    echo "  To set up PostgreSQL and run the full suite, see"
    echo "  docs/technical/development.md for setup instructions,"
    echo "  then run make ci."
    echo ""
    exit 1
fi

# Optional E2E tests
if [ "$RUN_E2E" = true ]; then
    echo ""
    echo "[12/12] Running E2E tests (this may take several minutes)..."
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
    echo "[11/11] Skipping E2E tests (use --e2e to include)"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   ✓ All CI Checks Passed!              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Ready to push to GitHub."
