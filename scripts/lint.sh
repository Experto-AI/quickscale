#!/usr/bin/env bash
# Lint all Python code in the repository with Poetry

set -e

echo "🔍 Running code quality checks..."
echo ""

echo "📦 Checking quickscale_core..."
cd quickscale_core
echo "  → Running black..."
poetry run black --check src/ tests/
echo "  → Running ruff..."
poetry run ruff check src/ tests/
cd ..

echo ""
echo "📦 Checking quickscale_cli..."
cd quickscale_cli
echo "  → Running black..."
poetry run black --check src/ tests/
echo "  → Running ruff..."
poetry run ruff check src/ tests/
cd ..

echo ""
echo "✅ All code quality checks passed!"
