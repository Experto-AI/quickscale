#!/usr/bin/env bash
# Lint React theme templates by rendering them to a temporary directory
# and running ESLint + TypeScript checks on the output.
#
# Prerequisites: Node.js 24+ and pnpm installed
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
	echo "   Install Node.js 24+ from https://nodejs.org/"
	exit 1
fi

NODE_VERSION=$(node --version | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 24 ]; then
	echo "❌ Node.js 24+ is required (found v$(node --version))"
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

# Render .j2 templates using Python/Jinja2 for proper handling of
# all constructs: {% if %}, {% for %}, {% set %}, {% raw %}...{% endraw %},
# whitespace control, and {{ variables }}.
render_template() {
	local src="$1"
	local dest="$2"

	python3 "$SCRIPT_DIR/render_j2_template.py" "$src" "$dest"
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

install_signature() {
	if [ -f "$WORK_DIR/pnpm-lock.yaml" ]; then
		md5sum "$WORK_DIR/package.json" "$WORK_DIR/pnpm-lock.yaml" | md5sum | cut -d' ' -f1
	else
		md5sum "$WORK_DIR/package.json" | cut -d' ' -f1
	fi
}

frontend_toolchain_ready() {
	[ -d "$WORK_DIR/node_modules" ] &&
	[ -e "$WORK_DIR/node_modules/.bin/eslint" ] &&
	[ -e "$WORK_DIR/node_modules/.bin/tsc" ] &&
	[ -e "$WORK_DIR/node_modules/eslint/package.json" ] &&
	[ -e "$WORK_DIR/node_modules/typescript/package.json" ]
}

# Install dependencies (cached via node_modules)
echo "📦 Installing dependencies (cached)..."
cd "$WORK_DIR"

# Reinstall if the manifest changed or the cached pnpm layout is incomplete.
PACKAGE_HASH=$(install_signature)
CACHED_HASH=""
if [ -f "$CACHE_DIR/.package_hash" ]; then
	CACHED_HASH=$(cat "$CACHE_DIR/.package_hash")
fi


if [ "$PACKAGE_HASH" != "$CACHED_HASH" ] || ! frontend_toolchain_ready; then
	if [ "$PACKAGE_HASH" != "$CACHED_HASH" ]; then
		echo "  → Dependencies changed, installing..."
	else
		echo "  → Cached dependencies look incomplete, reinstalling..."
	fi
	rm -rf "$WORK_DIR/node_modules"
	pnpm install
	if ! frontend_toolchain_ready; then
		echo "  ❌ pnpm install completed but eslint/tsc are still unavailable"
		exit 1
	fi
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

echo ""
echo "📦 Rendering no-social variant (selected_modules without 'social')..."
NO_SOCIAL_DIR="$WORK_DIR/no_social"
rm -rf "$NO_SOCIAL_DIR"
mkdir -p "$NO_SOCIAL_DIR"

# Build the no-social selected_modules list (all modules except 'social')
NO_SOCIAL_MODULES='["auth","blog","listings","crm","forms","storage","backups","notifications","analytics","billing"]'

render_template_no_social() {
	local src="$1"
	local dest="$2"
	SELECTED_MODULES="$NO_SOCIAL_MODULES" python3 "$SCRIPT_DIR/render_j2_template.py" "$src" "$dest"
}

# Walk through theme directory and render all files with no-social context
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
		dest_file="$NO_SOCIAL_DIR/${rel_path%.j2}"
		render_template_no_social "$src_file" "$dest_file"
	else
		# Regular file: copy as-is
		dest_file="$NO_SOCIAL_DIR/$rel_path"
		mkdir -p "$(dirname "$dest_file")"
		cp "$src_file" "$dest_file"
	fi
done < <(find "$THEME_DIR" -type f -print0)

echo "  ✅ No-social variant rendered to $NO_SOCIAL_DIR"
echo ""

# Install dependencies for the no-social variant (fast cache hit from store)
echo "📦 Installing dependencies for no-social variant (cached)..."
cd "$NO_SOCIAL_DIR"
# Copy lockfile and workspace config from main render if available.
# On a cold cache the lockfile exists (generated by the first install);
# on a warm-cache rerun the cleanup may have removed it before the
# main install step was skipped (cached).  Fall back to resolved
# install, which still hits the pnpm store for speed.
if [ -f "$WORK_DIR/pnpm-lock.yaml" ]; then
    cp "$WORK_DIR/pnpm-lock.yaml" "$NO_SOCIAL_DIR/pnpm-lock.yaml"
fi
if [ -f "$WORK_DIR/pnpm-workspace.yaml" ]; then
    cp "$WORK_DIR/pnpm-workspace.yaml" "$NO_SOCIAL_DIR/pnpm-workspace.yaml"
fi
if [ -f "$NO_SOCIAL_DIR/pnpm-lock.yaml" ]; then
    pnpm install --frozen-lockfile --prefer-offline
else
    echo "  → No cached lockfile available; installing resolved..."
    pnpm install --prefer-offline
fi
echo "  ✅ No-social dependencies ready"
echo ""

# Run ESLint on no-social variant
echo "🔍 Running ESLint on no-social variant..."
if pnpm exec eslint . --max-warnings 0; then
	echo "  ✅ ESLint (no-social) passed"
else
	echo "  ❌ ESLint (no-social) found issues"
	EXIT_CODE=1
fi
echo ""

# Run TypeScript type checking on no-social variant
echo "🔍 Running TypeScript type check on no-social variant..."
if pnpm exec tsc --noEmit; then
	echo "  ✅ TypeScript check (no-social) passed"
else
	echo "  ❌ TypeScript (no-social) found type errors"
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
