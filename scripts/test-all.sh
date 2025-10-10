#!/usr/bin/env bash
# Run all tests in the repository with Poetry

set -e

echo "🧪 Running all tests..."
echo ""

echo "📦 Testing quickscale_core..."
cd quickscale_core
poetry run pytest tests/ -v
cd ..

echo ""
echo "📦 Testing quickscale_cli..."
cd quickscale_cli
poetry run pytest tests/ -v
cd ..

echo ""
echo "✅ All tests passed!"
