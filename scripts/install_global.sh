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
INSTALL_BASE_DIR=""
INSTALL_VENVS_DIR=""
INSTALL_VENV_DIR=""
INSTALL_CURRENT_LINK=""
INSTALL_BIN_DIR=""
INSTALL_SHIM_PATH=""
INSTALL_PENDING_VENV=""
PREVIOUS_INSTALL_VENV=""

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

ensure_compatible_python_venv_available() {
    if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import ensurepip
import venv
PY
    then
        return 0
    fi

    echo ""
    echo "❌ Compatible Python ${PYTHON_DISPLAY_VERSION:-$REQUIRED_PYTHON_VERSION} was found at $PYTHON_BIN, but its venv/ensurepip modules are unavailable."
    echo ""
    echo "Install the matching venv support and retry. For Ubuntu/Debian, for example:"
    echo "  sudo apt install -y python${PYTHON_DISPLAY_VERSION:-$REQUIRED_PYTHON_VERSION}-venv"
    echo ""
    echo "Then run:"
    echo "  make install"
    echo ""
    exit 1
}

configure_user_install_paths() {
    INSTALL_BASE_DIR="${QUICKSCALE_HOME:-$HOME/.local/share/quickscale}"
    INSTALL_VENVS_DIR="$INSTALL_BASE_DIR/venvs"
    INSTALL_VENV_DIR="$INSTALL_VENVS_DIR/quickscale-${VERSION}-$(date +%Y%m%d%H%M%S)"
    INSTALL_CURRENT_LINK="$INSTALL_BASE_DIR/current"
    INSTALL_BIN_DIR="${QUICKSCALE_BIN_DIR:-$HOME/.local/bin}"
    INSTALL_SHIM_PATH="$INSTALL_BIN_DIR/quickscale"
}

prepare_user_install_dirs() {
    mkdir -p "$INSTALL_VENVS_DIR" "$INSTALL_BIN_DIR"
}

record_previous_install() {
    if [[ -L "$INSTALL_CURRENT_LINK" ]]; then
        PREVIOUS_INSTALL_VENV="$(readlink -f "$INSTALL_CURRENT_LINK" 2>/dev/null || true)"
    else
        PREVIOUS_INSTALL_VENV=""
    fi
}

create_install_venv() {
    INSTALL_PENDING_VENV="$INSTALL_VENV_DIR"
    "$PYTHON_BIN" -m venv "$INSTALL_VENV_DIR"
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

    if [[ -n "${INSTALL_PENDING_VENV:-}" ]] && [[ -d "$INSTALL_PENDING_VENV" ]]; then
        rm -rf "$INSTALL_PENDING_VENV"
    fi

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

pip_install_isolated() {
    local venv_dir="$1"
    shift

    PYTHONWARNINGS=ignore::SyntaxWarning \
    "$venv_dir/bin/python" -m pip install \
        --disable-pip-version-check \
        --force-reinstall \
        "$@"
}

activate_installed_command() {
    if [[ -e "$INSTALL_CURRENT_LINK" ]] && [[ ! -L "$INSTALL_CURRENT_LINK" ]]; then
        echo "❌ Install location $INSTALL_CURRENT_LINK exists and is not a symlink."
        echo "   Move or remove it, then re-run make install."
        exit 1
    fi

    ln -sfnT "$INSTALL_VENV_DIR" "$INSTALL_CURRENT_LINK"
    ln -sfnT "$INSTALL_CURRENT_LINK/bin/quickscale" "$INSTALL_SHIM_PATH"
    INSTALL_PENDING_VENV=""

    if [[ -n "$PREVIOUS_INSTALL_VENV" ]] \
        && [[ "$PREVIOUS_INSTALL_VENV" != "$INSTALL_VENV_DIR" ]] \
        && [[ "$PREVIOUS_INSTALL_VENV" == "$INSTALL_VENVS_DIR"/quickscale-* ]] \
        && [[ -d "$PREVIOUS_INSTALL_VENV" ]]; then
        rm -rf "$PREVIOUS_INSTALL_VENV"
    fi
}

stage_install_wheelhouse() {
    # Retain the exact wheels this install was built from next to the venv.
    # A locally installed (unpublished) build must resolve quickscale-core
    # from these wheels; otherwise every generated project pins a PyPI
    # version that does not exist yet and `quickscale apply` fails at
    # `poetry lock`.  Read by quickscale_cli.utils.module_dependency_sync
    # via sys.prefix/quickscale_wheels.
    local wheelhouse="$INSTALL_VENV_DIR/quickscale_wheels"

    rm -rf "$wheelhouse"
    mkdir -p "$wheelhouse"
    cp "$ROOT/quickscale_core/dist/quickscale_core-"*.whl "$wheelhouse/"
    echo "📦 Staged local wheelhouse: $wheelhouse"
}

path_contains_dir() {
    local candidate="$1"
    local entry

    IFS=':' read -r -a path_entries <<< "${PATH:-}"
    for entry in "${path_entries[@]}"; do
        if [[ "$entry" == "$candidate" ]]; then
            return 0
        fi
    done

    return 1
}

VERSION=$(read_version)

trap cleanup_build_state EXIT

ensure_compatible_python_available
ensure_compatible_python_venv_available
configure_user_install_paths
prepare_user_install_dirs
record_previous_install
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

# Install both packages into an isolated user environment
echo "📦 Installing into isolated user environment: $INSTALL_VENV_DIR"
create_install_venv
pip_install_isolated "$INSTALL_VENV_DIR" \
    "$ROOT/quickscale_core/dist/quickscale_core-"*.whl \
    "$ROOT/quickscale_cli/dist/quickscale_cli-"*.whl
stage_install_wheelhouse
activate_installed_command

echo "✅ QuickScale installed for the current user. You can now run 'quickscale' from any directory."
echo "   Environment: $INSTALL_CURRENT_LINK"
echo "   Command shim: $INSTALL_SHIM_PATH"

if ! path_contains_dir "$INSTALL_BIN_DIR"; then
    echo ""
    echo "⚠️  $INSTALL_BIN_DIR is not on your PATH."
    echo "   Add it to your shell profile, for example:"
    echo "   export PATH=\"$INSTALL_BIN_DIR:\$PATH\""
fi

echo ""
echo "🔄 To use the new version in this terminal session, run:"
echo "   hash -r && quickscale --version"
