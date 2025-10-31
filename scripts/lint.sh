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
echo "📦 Checking quickscale_modules (if any)..."
# Auto-detect any modules under quickscale_modules/ and run ruff/mypy where applicable
if [ -d "quickscale_modules" ]; then
	for mod in quickscale_modules/*; do
		if [ -d "$mod" ]; then
			echo "  → Found module: $(basename "$mod")"
			if [ -d "$mod/src" ]; then
				cd "$mod"
				echo "    → Running ruff format..."
				poetry run ruff format src/ || true
				echo "    → Running ruff check..."
				poetry run ruff check src/ tests/ --fix || true
				echo "    → Running mypy..."
				poetry run mypy src/ || true
				cd - > /dev/null
			else
				echo "    → Skipping $(basename "$mod") (no src/ directory)"
			fi
		fi
	done
fi

echo ""
echo "✅ All code quality checks passed!"
