#!/usr/bin/env bash
# Lint all Python code in the repository with Poetry

set -e

echo "🔍 Running code quality checks..."
echo ""

echo "📦 Checking quickscale_core..."
cd quickscale_core
echo "  → Running ruff format..."
poetry run ruff format .
echo "  → Running ruff check..."
poetry run ruff check src/ tests/ --fix
echo "  → Running mypy..."
poetry run mypy src/
cd ..

echo ""
echo "📦 Checking quickscale_cli..."
cd quickscale_cli
echo "  → Running ruff format..."
poetry run ruff format .
echo "  → Running ruff check..."
poetry run ruff check src/ tests/ --fix
echo "  → Running mypy..."
poetry run mypy src/
cd ..

echo ""
echo "✅ All code quality checks passed!"
