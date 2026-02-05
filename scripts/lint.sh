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
				LINT_ARGS=("$mod/src/")
				if [ -d "$mod/tests" ]; then
					LINT_ARGS+=("$mod/tests/")
				fi

				echo "    → Running ruff check..."
				poetry run ruff check --fix "${LINT_ARGS[@]}"
				echo "    → Running ruff format..."
				poetry run ruff format "${LINT_ARGS[@]}"
				echo "    → Running mypy..."
				poetry run mypy "$mod/src/"
			else
				echo "  → Skipping $mod_name (no src/ directory)"
			fi
		fi
	done
else
	echo "  → No quickscale_modules directory found"
fi

echo ""
echo "📝 Checking general file formatting..."

# Define files to check (all text files that should have standard formatting)
# We exclude hidden directories and specifically generated/binary files
FILES_TO_CHECK=$(find . -type f \
	\( -name "*.md" -o -name "*.py" -o -name "*.sh" -o -name "*.yml" -o -name "*.yaml" -o -name "*.toml" -o -name "*.json" \) \
	-not -path "*/.git/*" \
	-not -path "*/.venv/*" \
	-not -path "*/__pycache__/*" \
	-not -path "*/node_modules/*" \
	-not -path "*/htmlcov/*" \
	-not -path "*/.ruff_cache/*" \
	-not -path "*/.pytest_cache/*" \
	-not -path "*/.mypy_cache/*" \
	-not -path "*/dist/*" \
	-not -path "*/build/*" \
	-not -path "*/.coverage*" \
)

if [ -z "$FILES_TO_CHECK" ]; then
	echo "  ⚠️ No files found to check."
else
	echo "  → Checking for trailing whitespace..."
	# Use temporary file to handle list of files safely
	TMP_FILES=$(mktemp)
	echo "$FILES_TO_CHECK" > "$TMP_FILES"

	if xargs grep -l '[[:space:]]$' < "$TMP_FILES" > /dev/null 2>&1; then
		echo "  ❌ Trailing whitespace found in some files."
		echo "  → Fixing trailing whitespace..."
		xargs sed -i 's/[[:space:]]*$//' < "$TMP_FILES"
		echo "  ✅ Fixed trailing whitespace"
	else
		echo "  ✅ No trailing whitespace found"
	fi

	echo "  → Checking for proper end-of-file newlines..."
	MISSING_NEWLINE=""
	# Check for missing newlines
	while IFS= read -r f; do
		if [ -f "$f" ] && [ -n "$(tail -c 1 "$f" 2>/dev/null)" ]; then
			MISSING_NEWLINE="$MISSING_NEWLINE$f "
		fi
	done < "$TMP_FILES"

	if [ -n "$MISSING_NEWLINE" ]; then
		echo "  ❌ Files missing final newline found."
		echo "  → Fixing end-of-file newlines..."
		echo "$MISSING_NEWLINE" | xargs -n 1 sh -c 'echo >> "$1"' --
		echo "  ✅ Fixed end-of-file newlines"
	else
		echo "  ✅ All files have proper end-of-file newlines"
	fi

	rm "$TMP_FILES"
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
