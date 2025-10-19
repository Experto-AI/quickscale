#!/usr/bin/env bash
# Run all tests in the repository with Poetry
# Default mode is LLM-friendly: quiet for passing tests, detailed for failures, comprehensive coverage
#
# NOTE: This script runs unit and integration tests only.
# E2E tests are excluded (too slow for regular runs).
# To run E2E tests, use: ./scripts/test_e2e.sh

set -e

echo "🧪 Running all tests..."
echo ""

# Track exit codes
EXIT_CODE=0

echo "📦 Testing quickscale_core..."
cd quickscale_core
# LLM-friendly output: -q (quiet passing tests), --tb=native (detailed failures), comprehensive coverage
# Skip E2E tests (run separately with ./scripts/test_e2e.sh)
poetry run pytest tests/ -m "not e2e" -q --tb=native --cov=src/ --cov-report=term-missing --cov-report=html || EXIT_CODE=$?
cd ..

echo ""
echo "📦 Testing quickscale_cli..."
cd quickscale_cli
poetry run pytest tests/ -q --tb=native --cov=src/ --cov-report=term-missing --cov-report=html || EXIT_CODE=$?
cd ..

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed!"
    exit $EXIT_CODE
fi
