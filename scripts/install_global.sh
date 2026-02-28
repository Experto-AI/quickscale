#!/usr/bin/env bash
# Install QuickScale globally from the codebase

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"

ensure_python_314_available() {
    if command -v python3.14 >/dev/null 2>&1; then
        return 0
    fi

    echo ""
    echo "❌ Python 3.14 is required to build/install QuickScale (current project constraint: ^3.14)."
    echo ""
    echo "Install Python 3.14 and retry:"
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa -y"
    echo "  sudo apt update"
    echo "  sudo apt install -y python3.14 python3.14-venv"
    echo "  # Or install Python 3.14 via pyenv / your distro package manager"
    echo ""
    echo "Then run:"
    echo "  make install"
    echo ""
    exit 1
}

ensure_poetry_uses_python_314() {
    local pkg_dir="$1"

    (
        cd "$pkg_dir"
        poetry env use python3.14 >/dev/null
    )
}

read_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        tr -d '\r' < "$VERSION_FILE" | sed -e 's/^\s*//' -e 's/\s*$//'
    else
        echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
        exit 1
    fi
}

copy_readme() {
    local pkg_dir="$1"
    if [[ -f "$ROOT/README.md" ]] && [[ ! -f "$pkg_dir/README.md" ]]; then
        cp "$ROOT/README.md" "$pkg_dir/README.md"
        touch "$pkg_dir/.quickscale_tmp_readme"
    fi
}

remove_readme() {
    local pkg_dir="$1"
    if [[ -f "$pkg_dir/.quickscale_tmp_readme" ]] && [[ -f "$pkg_dir/README.md" ]]; then
        rm "$pkg_dir/README.md"
        rm -f "$pkg_dir/.quickscale_tmp_readme"
    fi
}

# Fix readme path in pyproject.toml for build (../README.md -> README.md)
fix_readme_path() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    sed -i 's|readme = "\.\./README\.md"|readme = "README.md"|' "$pyproject"
}

backup_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"
    local marker="$pkg_dir/.quickscale_tmp_pyproject_backup"

    if [[ -f "$pyproject" ]]; then
        cp "$pyproject" "$backup"
        touch "$marker"
    fi
}

restore_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"
    local marker="$pkg_dir/.quickscale_tmp_pyproject_backup"

    if [[ -f "$backup" ]] && [[ -f "$marker" ]]; then
        mv "$backup" "$pyproject"
    fi

    rm -f "$marker"
}

cleanup_build_state() {
    restore_pyproject "$ROOT/quickscale_core" || true
    restore_pyproject "$ROOT/quickscale_cli" || true
    remove_readme "$ROOT/quickscale_core" || true
    remove_readme "$ROOT/quickscale_cli" || true
}

replace_path_deps_cli() {
    local pkg_dir="$1"
    local version="$2"
    local pyproject="$pkg_dir/pyproject.toml"

    # Replace path dependency with a versioned dependency for wheel build
    # With:    quickscale-core = "^VERSION"
    sed -Ei "s|quickscale-core = \{path = \"\.\./quickscale_core\"(, develop = true)?\}|quickscale-core = \"^${version}\"|" "$pyproject"
}

VERSION=$(read_version)

trap cleanup_build_state EXIT

ensure_python_314_available

echo "🚀 Installing QuickScale globally (version $VERSION)..."

# Build quickscale_core first
echo "📦 Building quickscale_core..."
cd "$ROOT/quickscale_core"
ensure_poetry_uses_python_314 "$ROOT/quickscale_core"
copy_readme "$ROOT/quickscale_core"
backup_pyproject "$ROOT/quickscale_core"
fix_readme_path "$ROOT/quickscale_core"
rm -rf dist/
poetry build

# Build quickscale_cli (with path dependency replaced)
echo "📦 Building quickscale_cli..."
cd "$ROOT/quickscale_cli"
ensure_poetry_uses_python_314 "$ROOT/quickscale_cli"
copy_readme "$ROOT/quickscale_cli"
backup_pyproject "$ROOT/quickscale_cli"
fix_readme_path "$ROOT/quickscale_cli"
replace_path_deps_cli "$ROOT/quickscale_cli" "$VERSION"
rm -rf dist/
poetry build

# Install both packages globally
echo "📦 Installing globally with pip..."
python3.14 -m pip install --upgrade "click>=8.3.1,<9.0.0"
python3.14 -m pip install --force-reinstall "$ROOT/quickscale_core/dist/quickscale_core-"*.whl
python3.14 -m pip install --force-reinstall --no-deps "$ROOT/quickscale_cli/dist/quickscale_cli-"*.whl

echo "✅ QuickScale installed globally. You can now run 'quickscale' from any directory."
echo ""
echo "🔄 To use the new version in this terminal session, run:"
echo "   hash -r && quickscale --version"
