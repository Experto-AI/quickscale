#!/usr/bin/env bash
# Run all tests in the repository with Poetry
# Default mode is LLM-friendly: quiet for passing tests, detailed for failures, comprehensive coverage

set -e

echo "🧪 Running all tests..."
echo ""

echo "📦 Testing quickscale_core..."
cd quickscale_core
# LLM-friendly output: -q (quiet passing tests), --tb=native (detailed failures), comprehensive coverage
poetry run pytest tests/ -q --tb=native --cov=src/ --cov-report=term-missing --cov-report=html
cd ..

echo ""
echo "📦 Testing quickscale_cli..."
cd quickscale_cli
poetry run pytest tests/ -q --tb=native --cov=src/ --cov-report=term-missing --cov-report=html
cd ..

echo ""
echo "✅ All tests passed!"
