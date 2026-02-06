#!/usr/bin/env bash
# Run unit and integration tests in the repository with Poetry
# Default mode is LLM-friendly: quiet for passing tests, detailed for failures, comprehensive coverage
#
# NOTE: This script runs unit and integration tests only.
# E2E tests are excluded (too slow for regular runs).
# To run E2E tests, use: ./scripts/test_e2e.sh

set -e

echo "🧪 Running unit and integration tests..."
echo ""

# Track exit codes
EXIT_CODE=0

echo "📦 Testing quickscale_core..."
cd quickscale_core
# LLM-friendly output: -q (quiet passing tests), --tb=native (detailed failures), comprehensive coverage
# Skip E2E tests (run separately with ./scripts/test_e2e.sh)
# Use package name (not src/) to avoid double-counting with pyproject.toml addopts
poetry run pytest tests/ -m "not e2e" -q --tb=native -o "addopts=" --cov=quickscale_core --cov-report=term-missing --cov-report=html --cov-fail-under=90 || EXIT_CODE=$?
cd ..

echo ""
echo "📦 Testing quickscale_cli..."
cd quickscale_cli
# Skip E2E tests (run separately with ./scripts/test_e2e.sh)
# Use package name (not src/) to avoid double-counting with pyproject.toml addopts
poetry run pytest tests/ -m "not e2e" -q --tb=native -o "addopts=" --cov=quickscale_cli --cov-report=term-missing --cov-report=html --cov-fail-under=90 || EXIT_CODE=$?
cd ..

echo ""
echo "📦 Testing quickscale_modules..."
# Test modules using ROOT poetry environment (centralized dependencies)
# Modules are installed in editable mode via root pyproject.toml
# PYTHONPATH set to module dir so tests.settings is importable
if [ -d "quickscale_modules" ]; then
  for mod in quickscale_modules/*; do
    if [ -d "$mod" ]; then
      mod_name=$(basename "$mod")
      if [ -d "$mod/tests" ]; then
        echo "  → Testing module: $mod_name"
        # Package name format: quickscale_modules_<name> (underscores, not hyphens)
        pkg_name="quickscale_modules_${mod_name}"
        # Use ROOT poetry environment with PYTHONPATH pointing to module
        # Coverage uses package name (importable), not filesystem path
        PYTHONPATH="$mod:$mod/src" poetry run pytest "$mod/tests/" -q --tb=native \
          --cov="$pkg_name" --cov-report=term-missing --cov-fail-under=90 \
          -p pytest_django --ds=tests.settings || EXIT_CODE=$?
      else
        echo "  → Skipping $mod_name (no tests/ directory)"
      fi
    fi
  done
else
  echo "  → No quickscale_modules directory found"
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Tests passed!"
else
    echo "❌ Some tests failed!"
    exit $EXIT_CODE
fi
