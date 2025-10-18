#!/usr/bin/env bash
# Install QuickScale globally from the codebase

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"

read_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        cat "$VERSION_FILE" | tr -d '\r' | sed -e 's/^\s*//' -e 's/\s*$//'
    else
        echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
        exit 1
    fi
}

copy_readme() {
    local pkg_dir="$1"
    if [[ -f "$ROOT/README.md" ]] && [[ ! -f "$pkg_dir/README.md" ]]; then
        cp "$ROOT/README.md" "$pkg_dir/README.md"
    fi
}

remove_readme() {
    local pkg_dir="$1"
    if [[ -f "$pkg_dir/README.md" ]]; then
        rm "$pkg_dir/README.md"
    fi
}

backup_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"

    if [[ -f "$pyproject" ]]; then
        cp "$pyproject" "$backup"
    fi
}

restore_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"

    if [[ -f "$backup" ]]; then
        mv "$backup" "$pyproject"
    fi
}

replace_path_deps_cli() {
    local pkg_dir="$1"
    local version="$2"
    local pyproject="$pkg_dir/pyproject.toml"

    # Replace: quickscale-core = {path = "../quickscale_core", develop = true}
    # With:    quickscale-core = "^VERSION"
    sed -i "s|quickscale-core = {path = \"../quickscale_core\", develop = true}|quickscale-core = \"^${version}\"|" "$pyproject"
}

VERSION=$(read_version)

echo "🚀 Installing QuickScale globally (version $VERSION)..."

# Build quickscale_core first
echo "📦 Building quickscale_core..."
cd "$ROOT/quickscale_core"
copy_readme "$ROOT/quickscale_core"
rm -rf dist/
poetry build
remove_readme "$ROOT/quickscale_core"

# Build quickscale_cli (with path dependency replaced)
echo "📦 Building quickscale_cli..."
cd "$ROOT/quickscale_cli"
copy_readme "$ROOT/quickscale_cli"
backup_pyproject "$ROOT/quickscale_cli"
replace_path_deps_cli "$ROOT/quickscale_cli" "$VERSION"
rm -rf dist/
poetry build
restore_pyproject "$ROOT/quickscale_cli"
remove_readme "$ROOT/quickscale_cli"

# Install both packages globally
echo "📦 Installing globally with pip..."
pip install "$ROOT/quickscale_core/dist/quickscale_core-"*.whl
pip install --force-reinstall --no-deps "$ROOT/quickscale_cli/dist/quickscale_cli-"*.whl

echo "✅ QuickScale installed globally. You can now run 'quickscale' from any directory."
echo ""
echo "🔄 To use the new version in this terminal session, run:"
echo "   hash -r && quickscale --version"