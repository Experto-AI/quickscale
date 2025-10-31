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
