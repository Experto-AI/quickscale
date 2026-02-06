#!/usr/bin/env bash
# Lint React theme templates by rendering them to a temporary directory
# and running ESLint + TypeScript checks on the output.
#
# Prerequisites: Node.js 18+ and pnpm installed
# Usage: ./scripts/lint_frontend.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
THEME_DIR="$ROOT/quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react"

echo "🔍 Running React theme lint checks..."
echo ""

# Check prerequisites
if ! command -v node &> /dev/null; then
	echo "❌ Node.js is required but not installed."
	echo "   Install Node.js 18+ from https://nodejs.org/"
	exit 1
fi

NODE_VERSION=$(node --version | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
	echo "❌ Node.js 18+ is required (found v$(node --version))"
	exit 1
fi

# Require pnpm (official package manager per decisions.md)
if ! command -v pnpm &> /dev/null; then
	echo "❌ pnpm is required but not installed."
	echo "   Install pnpm: npm install -g pnpm"
	exit 1
fi

echo "  Using pnpm as package manager"
echo ""

# Create a persistent cache directory for faster re-runs
CACHE_DIR="$ROOT/.quickscale/frontend_lint_cache"
WORK_DIR="$CACHE_DIR/rendered"
mkdir -p "$WORK_DIR"

# Clean rendered source files but keep node_modules for caching
find "$WORK_DIR" -mindepth 1 -maxdepth 1 -not -name "node_modules" -exec rm -rf {} + 2>/dev/null || true

echo "📦 Rendering React theme templates..."

# Render .j2 templates by stripping Jinja2 syntax
# Replace {{ project_name }} / {{ package_name }} with dummy values
render_template() {
	local src="$1"
	local dest="$2"

	mkdir -p "$(dirname "$dest")"

	# Strip Jinja2 directives and replace template variables
	sed \
		-e 's/{%[[:space:]]*raw[[:space:]]*%}//g' \
		-e 's/{%[[:space:]]*endraw[[:space:]]*%}//g' \
		-e 's/{{[[:space:]]*project_name[[:space:]]*}}/myapp/g' \
		-e 's/{{[[:space:]]*package_name[[:space:]]*}}/myapp/g' \
		-e 's/{{[[:space:]]*project_description[[:space:]]*}}/A QuickScale project/g' \
		"$src" > "$dest"
}

# Walk through theme directory and render all files
while IFS= read -r -d '' src_file; do
	rel_path="${src_file#"$THEME_DIR/"}"

	# Skip README.md at root (theme docs, not project file)
	if [ "$rel_path" = "README.md" ]; then
		continue
	fi

	# Skip templates/ directory (Django templates, not React code)
	if [[ "$rel_path" == templates/* ]]; then
		continue
	fi

	# Skip e2e/ directory (Playwright tests require browser, not relevant for lint)
	if [[ "$rel_path" == e2e/* ]]; then
		continue
	fi

	if [[ "$src_file" == *.j2 ]]; then
		# Template file: render and strip .j2 extension
		dest_file="$WORK_DIR/${rel_path%.j2}"
		render_template "$src_file" "$dest_file"
	else
		# Regular file: copy as-is
		dest_file="$WORK_DIR/$rel_path"
		mkdir -p "$(dirname "$dest_file")"
		cp "$src_file" "$dest_file"
	fi
done < <(find "$THEME_DIR" -type f -print0)

echo "  ✅ Templates rendered to cache directory"
echo ""

# Install dependencies (cached via node_modules)
echo "📦 Installing dependencies (cached)..."
cd "$WORK_DIR"

# Only reinstall if package.json changed
PACKAGE_HASH=$(md5sum "$WORK_DIR/package.json" 2>/dev/null | cut -d' ' -f1)
CACHED_HASH=""
if [ -f "$CACHE_DIR/.package_hash" ]; then
	CACHED_HASH=$(cat "$CACHE_DIR/.package_hash")
fi

if [ "$PACKAGE_HASH" != "$CACHED_HASH" ] || [ ! -d "$WORK_DIR/node_modules" ]; then
	echo "  → Dependencies changed, installing..."
	pnpm install
	echo "$PACKAGE_HASH" > "$CACHE_DIR/.package_hash"
	echo "  ✅ Dependencies installed"
else
	echo "  ✅ Dependencies cached (no changes)"
fi
echo ""

# Run ESLint
echo "🔍 Running ESLint..."
if pnpm exec eslint . --max-warnings 0; then
	echo "  ✅ ESLint passed"
else
	echo "  ❌ ESLint found issues"
	EXIT_CODE=1
fi
echo ""

# Run TypeScript type checking
echo "🔍 Running TypeScript type check..."
if pnpm exec tsc --noEmit; then
	echo "  ✅ TypeScript check passed"
else
	echo "  ❌ TypeScript found type errors"
	EXIT_CODE=1
fi
echo ""

# Return to root
cd "$ROOT"

if [ "${EXIT_CODE:-0}" -ne 0 ]; then
	echo "❌ React theme lint checks failed!"
	exit 1
fi

echo "✅ All React theme lint checks passed!"
