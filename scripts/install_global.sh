#!/usr/bin/env bash
# Install QuickScale globally from the codebase

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=./_python_requirement.sh
source "$ROOT/scripts/_python_requirement.sh"

VERSION_FILE="$ROOT/VERSION"
PYTHON_BIN=""
PYTHON_DISPLAY_VERSION=""
REQUIRED_PYTHON_SPEC="$(quickscale_requires_python_spec "$ROOT")"
REQUIRED_PYTHON_VERSION="$(quickscale_min_python_version "$ROOT")"
POETRY_BUILD_VENVS_DIR=""

ensure_compatible_python_available() {
    if PYTHON_BIN="$(quickscale_find_compatible_python "$ROOT")"; then
        PYTHON_DISPLAY_VERSION="$(quickscale_python_major_minor "$PYTHON_BIN")"
        return 0
    fi

    echo ""
    echo "❌ Python ${REQUIRED_PYTHON_VERSION} or newer is required to build/install QuickScale (project constraint: ${REQUIRED_PYTHON_SPEC})."
    echo ""
    echo "Install a compatible interpreter and retry. For Ubuntu/Debian, for example:"
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa -y"
    echo "  sudo apt update"
    echo "  sudo apt install -y python${REQUIRED_PYTHON_VERSION} python${REQUIRED_PYTHON_VERSION}-venv"
    echo "  # Or install Python ${REQUIRED_PYTHON_VERSION}+ via pyenv / your distro package manager"
    echo ""
    echo "Then run:"
    echo "  make install"
    echo ""
    exit 1
}

ensure_compatible_python_pip_available() {
    if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    echo ""
    echo "❌ Compatible Python ${PYTHON_DISPLAY_VERSION:-$REQUIRED_PYTHON_VERSION} was found at $PYTHON_BIN, but its pip module is unavailable."
    echo ""
    echo "Install the matching pip/venv support and retry. For Ubuntu/Debian, for example:"
    echo "  sudo apt install -y python${PYTHON_DISPLAY_VERSION:-$REQUIRED_PYTHON_VERSION}-venv python3-pip"
    echo "  # Or run: $PYTHON_BIN -m ensurepip --upgrade"
    echo ""
    echo "Then run:"
    echo "  make install"
    echo ""
    exit 1
}

ensure_poetry_uses_compatible_python() {
    local pkg_dir="$1"

    (
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$POETRY_BUILD_VENVS_DIR" \
        poetry env use "$PYTHON_BIN" >/dev/null 2>&1
    )
}

build_with_poetry_compatible_python() {
    local pkg_dir="$1"
    local venv_path

    venv_path="$(
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$POETRY_BUILD_VENVS_DIR" \
        poetry env info -p
    )"

    (
        cd "$pkg_dir"
        VIRTUAL_ENV="$venv_path" \
        PATH="$venv_path/bin:$PATH" \
        POETRY_ACTIVE=1 \
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$POETRY_BUILD_VENVS_DIR" \
        poetry build
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

    if [[ -n "${POETRY_BUILD_VENVS_DIR:-}" ]] && [[ -d "$POETRY_BUILD_VENVS_DIR" ]]; then
        rm -rf "$POETRY_BUILD_VENVS_DIR"
    fi
}

replace_path_deps_cli() {
    local pkg_dir="$1"
    local version="$2"
    local pyproject="$pkg_dir/pyproject.toml"

    # Replace path dependency with a versioned dependency for wheel build
    # With:    quickscale-core = "^VERSION"
    sed -Ei "s|quickscale-core = \{path = \"\.\./quickscale_core\"(, develop = true)?\}|quickscale-core = \"^${version}\"|" "$pyproject"
}

pip_install_user() {
    PYTHONWARNINGS=ignore::SyntaxWarning \
    "$PYTHON_BIN" -m pip install \
        --user \
        --disable-pip-version-check \
        --force-reinstall \
        "$@"
}

VERSION=$(read_version)

trap cleanup_build_state EXIT

ensure_compatible_python_available
ensure_compatible_python_pip_available
POETRY_BUILD_VENVS_DIR="$(mktemp -d)"

echo "🚀 Installing QuickScale globally (version $VERSION)..."

# Build quickscale_core first
echo "📦 Building quickscale_core..."
cd "$ROOT/quickscale_core"
ensure_poetry_uses_compatible_python "$ROOT/quickscale_core"
copy_readme "$ROOT/quickscale_core"
backup_pyproject "$ROOT/quickscale_core"
fix_readme_path "$ROOT/quickscale_core"
rm -rf dist/
build_with_poetry_compatible_python "$ROOT/quickscale_core"

# Build quickscale_cli (with path dependency replaced)
echo "📦 Building quickscale_cli..."
cd "$ROOT/quickscale_cli"
ensure_poetry_uses_compatible_python "$ROOT/quickscale_cli"
copy_readme "$ROOT/quickscale_cli"
backup_pyproject "$ROOT/quickscale_cli"
fix_readme_path "$ROOT/quickscale_cli"
replace_path_deps_cli "$ROOT/quickscale_cli" "$VERSION"
rm -rf dist/
build_with_poetry_compatible_python "$ROOT/quickscale_cli"

# Install both packages globally
echo "📦 Installing globally with pip ($(basename "$PYTHON_BIN") --user)..."
pip_install_user \
    "$ROOT/quickscale_core/dist/quickscale_core-"*.whl \
    "$ROOT/quickscale_cli/dist/quickscale_cli-"*.whl

echo "✅ QuickScale installed globally. You can now run 'quickscale' from any directory."
echo ""
echo "🔄 To use the new version in this terminal session, run:"
echo "   hash -r && quickscale --version"
