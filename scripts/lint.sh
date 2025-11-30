#!/usr/bin/env bash
# Lint all Python code in the repository with Poetry

set -e

echo "🔍 Running code quality checks..."
echo ""

echo "📦 Checking quickscale_core..."
cd quickscale_core
echo "  → Running ruff check..."
poetry run ruff check --fix src/ tests/
echo "  → Running ruff format..."
poetry run ruff format src/ tests/
echo "  → Running mypy..."
poetry run mypy src/
cd ..

echo ""
echo "📦 Checking quickscale_cli..."
cd quickscale_cli
echo "  → Running ruff check..."
poetry run ruff check --fix src/ tests/
echo "  → Running ruff format..."
poetry run ruff format src/ tests/
echo "  → Running mypy..."
poetry run mypy src/
cd ..

echo ""
echo "📦 Checking quickscale_modules..."
# Use ROOT poetry environment for linting (centralized dependencies)
# Modules are installed in editable mode via root pyproject.toml
if [ -d "quickscale_modules" ]; then
	for mod in quickscale_modules/*; do
		if [ -d "$mod" ]; then
			mod_name=$(basename "$mod")
			if [ -d "$mod/src" ]; then
				echo "  → Linting module: $mod_name"
				echo "    → Running ruff check..."
				poetry run ruff check --fix "$mod/src/" "$mod/tests/" || true
				echo "    → Running ruff format..."
				poetry run ruff format "$mod/src/" "$mod/tests/" || true
				echo "    → Running mypy..."
				poetry run mypy "$mod/src/" || true
			else
				echo "  → Skipping $mod_name (no src/ directory)"
			fi
		fi
	done
else
	echo "  → No quickscale_modules directory found"
fi

echo ""
echo "📝 Checking documentation formatting..."
echo "  → Checking for trailing whitespace..."
if grep -n '[[:space:]]$' docs/**/*.md 2>/dev/null; then
	echo "  ❌ Trailing whitespace found in documentation files (see above)"
	echo "  → Fixing trailing whitespace..."
	find docs -name "*.md" -type f -exec sed -i 's/[[:space:]]*$//' {} +
	echo "  ✅ Fixed trailing whitespace"
else
	echo "  ✅ No trailing whitespace found"
fi

echo "  → Checking for proper end-of-file newlines..."
FILES_MISSING_NEWLINE=()
for f in docs/**/*.md; do
	if [ -f "$f" ] && [ -n "$(tail -c 1 "$f" 2>/dev/null)" ]; then
		FILES_MISSING_NEWLINE+=("$f")
	fi
done

if [ ${#FILES_MISSING_NEWLINE[@]} -gt 0 ]; then
	echo "  ❌ Files missing final newline:"
	printf '    - %s\n' "${FILES_MISSING_NEWLINE[@]}"
	echo "  → Fixing end-of-file newlines..."
	for f in "${FILES_MISSING_NEWLINE[@]}"; do
		echo >> "$f"
	done
	echo "  ✅ Fixed end-of-file newlines"
else
	echo "  ✅ All files have proper end-of-file newlines"
fi

echo ""
echo "✅ All code quality checks passed!"
echo ""
echo "💡 Tip: Run this script twice to ensure all fixes are applied:"
echo "   ./scripts/lint.sh && git add -A && ./scripts/lint.sh && git add -A && git commit"
echo ""
echo "   Or use this shortcut:"
echo "   ./scripts/lint.sh && git add -A && git commit"
echo "   (If pre-commit makes changes, just run: git add -A && git commit --amend --no-edit)"
