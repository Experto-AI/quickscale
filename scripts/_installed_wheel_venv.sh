#!/usr/bin/env bash
# Sourceable library: installed-wheel venv provisioner (SA112)
#
# Provides:
#   iw_provision_installed_venv OUT_VENV_DIR  — provision a venv with
#     installed QuickScale wheels from staged source copies.
#
# Helper functions (extracted from scripts/smoke_install.sh):
#   read_version, python_within_spec, smoke_select_python,
#   ensure_compatible_python_available, ensure_compatible_python_venv_available,
#   ensure_poetry_uses_compatible_python, build_with_poetry,
#   pip_install_isolated, stage_package, build_staged_package
#
# Dependencies:
#   scripts/_python_requirement.sh (sourced automatically)

# Guard against double-source.
if [[ -n "${_QUICKSCALE_IW_VENV_LIB:-}" ]]; then
    return 0
fi
_QUICKSCALE_IW_VENV_LIB=1

# Source dependency.
_QS_IW_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_python_requirement.sh
source "$_QS_IW_LIB_DIR/_python_requirement.sh"

# ---- Shared default initialisation ---------------------------------
# Use caller values when already set; derive defaults otherwise.
# This lets a sourcing script pre-export ROOT, VERSION_FILE, etc.
# without competing with the library defaults.
ROOT="${ROOT:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}"
VERSION_FILE="${VERSION_FILE:-"$ROOT/VERSION"}"
REQUIRED_PYTHON_SPEC="${REQUIRED_PYTHON_SPEC:-"$(quickscale_requires_python_spec "$ROOT")"}"
REQUIRED_PYTHON_VERSION="${REQUIRED_PYTHON_VERSION:-"$(quickscale_min_python_version "$ROOT")"}"
PYTHON_BIN="${PYTHON_BIN:-}"
PYTHON_DISPLAY_VERSION="${PYTHON_DISPLAY_VERSION:-}"

# ========== Helper functions ==========

read_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        tr -d '\r' < "$VERSION_FILE" | sed -e 's/^\s*//' -e 's/\s*$//'
    else
        echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
        exit 1
    fi
}

# Check whether a Python interpreter satisfies the full requires-python spec
# (e.g. >=3.13,<3.15).  Returns 0 if the interpreter is within bounds, 1 if
# not.  Can be used as a filter predicate — does not call exit.
python_within_spec() {
    local python_bin="$1"
    local spec="$2"

    "$python_bin" -c "
import sys
spec = '$spec'
parts = [p.strip() for p in spec.split(',')]
min_str = parts[0].lstrip('>=')
max_str = parts[1].lstrip('<')
min_ver = tuple(int(x) for x in min_str.split('.'))
max_ver = tuple(int(x) for x in max_str.split('.'))
v = sys.version_info[:len(min_ver)]
sys.exit(0 if min_ver <= v < max_ver else 1)
"
}

# Read candidate Python interpreter paths from stdin (one per line), check
# each against the full requires-python spec, and return the first valid one.
# Continues past invalid candidates so a newer (e.g. 3.15) or too-old (e.g.
# 3.12) interpreter on the PATH does not prevent finding a valid one.
#
# Pipe-testable: passing known paths with controlled Python shims validates
# the selection order without needing actual 3.14/3.15 binaries.
#
#   printf '%s\n' /path/fake3.15 /path/python3.14 | smoke_select_python '>=3.13,<3.15'
smoke_select_python() {
    local spec="$1"
    local candidate
    local found=""

    while IFS= read -r candidate; do
        if [[ -z "$candidate" || ! -x "$candidate" ]]; then
            continue
        fi
        if python_within_spec "$candidate" "$spec"; then
            found="$candidate"
            break
        fi
    done

    if [[ -n "$found" ]]; then
        printf '%s\n' "$found"
        return 0
    fi
    return 1
}

ensure_compatible_python_available() {
    local python_bin

    # Iterate through all system candidates and pick the first one that
    # satisfies the full >=3.13,<3.15 spec.  Unlike the upstream helper
    # (which only checks the minimum), this continues past invalid
    # candidates so a 3.15 on PATH does not block finding a valid 3.14.
    python_bin="$(smoke_select_python "$REQUIRED_PYTHON_SPEC" \
        < <(quickscale_python_candidates "$ROOT"))" || {
        local found_ver=""
        # Try to extract a version from any candidate for the error message.
        local probe
        while IFS= read -r probe; do
            if [[ -n "$probe" ]] && [[ -x "$probe" ]]; then
                found_ver="$("$probe" --version 2>&1 || echo "unknown")"
                break
            fi
        done < <(quickscale_python_candidates "$ROOT" 2>/dev/null || printf '')
        echo ""
        echo "❌ No Python interpreter satisfies requires-python spec: ${REQUIRED_PYTHON_SPEC}"
        if [[ -n "$found_ver" ]]; then
            echo "   Closest candidate: ${found_ver}"
            echo "   (rejected — outside the required range)"
        fi
        echo ""
        exit 1
    }

    PYTHON_BIN="$python_bin"
    PYTHON_DISPLAY_VERSION="$(quickscale_python_major_minor "$PYTHON_BIN")"
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
    exit 1
}

ensure_poetry_uses_compatible_python() {
    local pkg_dir="$1"

    (
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$BUILD_VENVS_DIR" \
        poetry env use "$PYTHON_BIN" >/dev/null 2>&1
    )
}

build_with_poetry() {
    local pkg_dir="$1"
    local venv_path

    venv_path="$(
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$BUILD_VENVS_DIR" \
        poetry env info -p
    )"

    (
        cd "$pkg_dir"
        VIRTUAL_ENV="$venv_path" \
        PATH="$venv_path/bin:$PATH" \
        POETRY_ACTIVE=1 \
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$BUILD_VENVS_DIR" \
        poetry build
    )
}

pip_install_isolated() {
    local venv_dir="$1"
    shift

    "$venv_dir/bin/python" -E -m pip install \
        --disable-pip-version-check \
        --force-reinstall \
        "$@"
}

# Stage a package: copy its directory to the per-run staging area with
# pyproject.toml modifications applied to the copy (never touches the
# source tree).  Returns the path to the staged copy.
stage_package() {
    local pkg_name="$1"       # directory basename under ROOT
    local version="$2"
    local needs_path_fix="$3" # "yes" to replace path deps; "no" otherwise

    # Allow a disposable modified core source for SA109 regression testing.
    # Normal production use omits this env var entirely.
    local src_dir
    if [[ "$pkg_name" == "quickscale_core" && -n "${QS_SMOKE_REGRESSION_CORE:-}" ]]; then
        src_dir="$QS_SMOKE_REGRESSION_CORE"
    else
        src_dir="$ROOT/$pkg_name"
    fi
    local dst_dir="$STAGE_DIR/$pkg_name"

    echo "  📦 Staging $pkg_name..." >&2

    # Copy the full package directory (excluding heavy build artifacts).
    # Using cp -a preserves symlinks and metadata.
    mkdir -p "$dst_dir"
    cp -a "$src_dir/." "$dst_dir/"

    # Remove artifacts that would bloat the stage and are not needed for build.
    rm -rf "$dst_dir/dist" "$dst_dir/__pycache__" "$dst_dir/.venv"
    find "$dst_dir" -name '*.pyc' -delete 2>/dev/null || true
    rm -f "$dst_dir/.quickscale_tmp_readme" "$dst_dir/.quickscale_tmp_pyproject_backup"
    rm -f "$dst_dir/pyproject.toml.backup"

    # Fix readme path so poetry can find README.md in the package dir.
    if [[ -f "$dst_dir/pyproject.toml" ]]; then
        sed -i 's|readme = "\.\./README\.md"|readme = "README.md"|' "$dst_dir/pyproject.toml"
    fi

    # Replace path dependencies with versioned ones for clean wheel builds.
    if [[ "$needs_path_fix" == "yes" ]]; then
        sed -Ei \
            "s|quickscale-core = \{path = \"\.\./quickscale_core\"(, develop = true)?\}|quickscale-core = \"^${version}\"|" \
            "$dst_dir/pyproject.toml"
    fi

    # Copy root README if the package does not have its own.
    if [[ -f "$ROOT/README.md" ]] && [[ ! -f "$dst_dir/README.md" ]]; then
        cp "$ROOT/README.md" "$dst_dir/README.md"
    fi

    printf '%s' "$dst_dir"
}

# Build a staged package and copy the resulting wheel into the collection
# directory.  Modifies the staged copy in-place (which is temp and
# per-run — no source mutation).
build_staged_package() {
    local pkg_name="$1"
    local staged_dir="$STAGE_DIR/$pkg_name"

    echo "  🏗️  Building $pkg_name (staged)..." >&2
    ensure_poetry_uses_compatible_python "$staged_dir"
    rm -rf "$staged_dir/dist"
    build_with_poetry "$staged_dir"

    # Collect the wheel into the shared collection directory.
    mkdir -p "$WHEEL_COLLECT_DIR"
    cp "$staged_dir"/dist/*.whl "$WHEEL_COLLECT_DIR"/
}

# ========== Public API ==========

# Provision a Python venv with installed QuickScale wheels built from
# per-run staged source copies.
#
# Usage:
#   VENV_DIR="$(mktemp -d /tmp/my-venv-XXXXXX)"
#   QS_BIN="$(iw_provision_installed_venv "$VENV_DIR")"
#   "$QS_BIN" --version
#   rm -rf "$VENV_DIR"
#
# The function runs in a subshell so all internal state (STAGE_DIR,
# BUILD_VENVS_DIR, WHEEL_COLLECT_DIR) is scoped.  Its EXIT trap cleans
# up internal temp dirs without touching caller-owned OUT_VENV_DIR or
# clobbering caller traps.
#
# stdout: the installed quickscale binary path (one line)
# stderr: all build/provision chatter
# Exit codes:
#   0 — success
#   1 — provisioning failure (e.g. Python not available, poetry error)
#   2 — usage error (missing or empty argument)
iw_provision_installed_venv() (
    # Require exactly one nonempty argument.
    if [[ $# -ne 1 || -z "$1" ]]; then
        echo "ERROR: usage: iw_provision_installed_venv OUT_VENV_DIR" >&2
        return 2
    fi

    local OUT_VENV_DIR="$1"

    # Internal paths — initialised empty so subshell EXIT cleanup
    # does not delete unrelated directories.
    STAGE_DIR=""
    BUILD_VENVS_DIR=""
    WHEEL_COLLECT_DIR=""

    # Subshell-only EXIT trap: cleans up internal temp dirs without
    # clobbering caller traps.  Uses a function so $_s captures the
    # subshell exit status before cleanup runs.
    _iw_exit_cleanup() {
        local _s=$?
        [[ -n "$STAGE_DIR" && -d "$STAGE_DIR" ]] && rm -rf "$STAGE_DIR"
        [[ -n "$BUILD_VENVS_DIR" && -d "$BUILD_VENVS_DIR" ]] && rm -rf "$BUILD_VENVS_DIR"
        [[ -n "$WHEEL_COLLECT_DIR" && -d "$WHEEL_COLLECT_DIR" ]] && rm -rf "$WHEEL_COLLECT_DIR"
        exit "$_s"
    }
    trap _iw_exit_cleanup EXIT

    # Create per-run working directories (managed by EXIT trap above;
    # never persisted).  Exact temp-name families required by SA112 contract.
    STAGE_DIR="$(mktemp -d /tmp/quickscale-iw-stage-XXXXXX)"
    BUILD_VENVS_DIR="$(mktemp -d /tmp/quickscale-iw-build-venvs-XXXXXX)"
    WHEEL_COLLECT_DIR="$(mktemp -d /tmp/quickscale-iw-wheels-XXXXXX)"

    # Ensure compatible Python interpreter and venv support.
    ensure_compatible_python_available
    ensure_compatible_python_venv_available

    local version
    version="$(read_version)"

    # Stage packages (chatter >&2).
    stage_package "quickscale_core" "$version" "no"   >&2
    stage_package "quickscale_cli"  "$version" "yes"  >&2
    stage_package "quickscale"      "$version" "no"   >&2

    # Build staged packages (chatter >&2).
    build_staged_package "quickscale_core" >&2
    build_staged_package "quickscale_cli"  >&2
    build_staged_package "quickscale"      >&2

    # Create OUT venv.
    "$PYTHON_BIN" -m venv "$OUT_VENV_DIR" >&2

    # Install wheels into OUT venv (chatter >&2).
    pip_install_isolated "$OUT_VENV_DIR" >&2 \
        "$WHEEL_COLLECT_DIR/quickscale_core-"*.whl \
        "$WHEEL_COLLECT_DIR/quickscale_cli-"*.whl \
        "$WHEEL_COLLECT_DIR/quickscale-"*.whl

    # stdout: exactly the installed quickscale binary path, one line.
    printf '%s\n' "$OUT_VENV_DIR/bin/quickscale"

    # EXIT trap runs here, cleaning up internal temp dirs.
)
