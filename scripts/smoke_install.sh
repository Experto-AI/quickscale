#!/usr/bin/env bash
# QuickScale installed-artifact smoke gate (SA110)
#
# Builds all wheels from per-run staged copies (never touches source
# pyproject.toml), installs them into a throwaway venv OUTSIDE the source
# tree (so ``parents[4]/quickscale_modules`` cannot resolve), and runs 20
# probes: 18 version/help commands assert exit 0 and no traceback; the 19th
# runs ``quickscale status`` outside a project and asserts exit 1, the
# expected diagnostic, and no traceback; the 20th runs ``quickscale plan`` from
# an external workdir with all 12 modules via scripted stdin, exercising the full
# module-implication graph (SA111a).  All probes execute from an external workdir
# with a sanitized environment.
#
# Stage isolation guarantees concurrent build/publish activity cannot share
# backups, rewritten metadata, or dist directories.
#
# --- SA109 negative regression proof (for QG use) ---
# The env var QS_SMOKE_REGRESSION_CORE can point to a disposable modified
# copy of quickscale_core.  When set, the smoke gate stages from that copy
# instead of the real source tree.  The QG uses this to prove the gate goes
# red when the installed-wheel bundled fallback is removed:
#
#   REGRESSION_DIR=$(mktemp -d)
#   cp -a quickscale_core/. "$REGRESSION_DIR/"
#   rm -rf "$REGRESSION_DIR/src/quickscale_core/data/manifests"
#   QS_SMOKE_REGRESSION_CORE="$REGRESSION_DIR" make smoke-install
#   # Expected: exit 1 — gate red, ImproperlyConfigured from discovery
#   # (same SA109 failure class), NOT an ImportError.
#   rm -rf "$REGRESSION_DIR"
#   make smoke-install
#   # Expected: exit 0 — gate green with SA109 fix in place.
#
# The manifests removal semantically disables the bundled-manifest fallback
# while preserving all Python import contracts (discover_bundled_module_names
# still exists and is importable).  Source-workspace discovery is unaffected
# because it resolves quickscale_modules/ from parent-directory traversal,
# not from the manifests directory.
#
# Must run from the repository root.
#
# Excludes state-changing / outward-facing commands:
#   up down shell manage logs ps deploy dr update push apply remove
#
# Usage:
#   ./scripts/smoke_install.sh
#
# Exit codes:
#   0 — all smoke tests passed
#   1 — one or more smoke tests failed

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./_python_requirement.sh
source "$ROOT/scripts/_python_requirement.sh"

VERSION_FILE="$ROOT/VERSION"
PYTHON_BIN=""
PYTHON_DISPLAY_VERSION=""
REQUIRED_PYTHON_SPEC="$(quickscale_requires_python_spec "$ROOT")"
REQUIRED_PYTHON_VERSION="$(quickscale_min_python_version "$ROOT")"

# Working directories (all temp, cleaned up on exit).
STAGE_DIR=""          # Per-run staged package copies for building
BUILD_VENVS_DIR=""    # Poetry build venvs (shared across staged builds)
SMOKE_VENV_DIR=""     # Throwaway venv for wheel installation
SMOKE_WORK_DIR=""     # External cwd for sanitized probe execution
WHEEL_COLLECT_DIR=""  # Collected built wheels from all staged builds

# ---- helpers ----

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

    echo "  📦 Staging $pkg_name..."

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

    echo "  🏗️  Building $pkg_name (staged)..."
    ensure_poetry_uses_compatible_python "$staged_dir"
    rm -rf "$staged_dir/dist"
    build_with_poetry "$staged_dir"

    # Collect the wheel into the shared collection directory.
    mkdir -p "$WHEEL_COLLECT_DIR"
    cp "$staged_dir"/dist/*.whl "$WHEEL_COLLECT_DIR"/
}

# Run a smoke test with environment and cwd sanitization.
# Every probe runs in a subshell with PYTHONPATH and PYTHONHOME unset,
# cwd set to the external SMOKE_WORK_DIR.
run_smoke_probe() {
    local description="$1"
    shift

    (
        # Prevent source-tree leakage through environment variables.
        unset PYTHONPATH
        unset PYTHONHOME

        # Run from the external workdir so source-tree parents cannot resolve.
        cd "$SMOKE_WORK_DIR"
        run_smoke_test "$description" "$@"
    )
}

run_smoke_test() {
    local description="$1"
    shift

    echo "    🔍 $description"

    # Capture combined stdout+stderr and actual exit code.
    local output=""
    local exit_code=0
    output="$("$@" 2>&1)" && exit_code=0 || exit_code=$?

    # Fail on any Python traceback in output (regardless of exit code).
    if echo "$output" | grep -q 'Traceback (most recent call last)'; then
        echo "      ❌ TRACEBACK DETECTED"
        echo "      Output:"
        echo "$output" | sed 's/^/        /'
        return 1
    fi

    # Check exit code expectations.
    # NOTE: avoid literal parentheses in the glob pattern — bash's [[ ==
    # *...* ]] with extglob can misparse *( as an extended-glob operator.
    if [[ "$description" == *"expect exit 1"* ]]; then
        if [[ $exit_code -ne 1 ]]; then
            echo "      ❌ Expected exit code 1 but got $exit_code"
            echo "      Output:"
            echo "$output" | sed 's/^/        /'
            return 1
        fi
    else
        if [[ $exit_code -ne 0 ]]; then
            echo "      ❌ Expected exit code 0 but got $exit_code"
            echo "      Output:"
            echo "$output" | sed 's/^/        /'
            return 1
        fi
    fi

    # For status outside project, verify expected diagnostic.
    if [[ "$description" == *"outside project"* ]]; then
        if ! echo "$output" | grep -q "Not in a QuickScale project directory"; then
            echo "      ❌ Expected diagnostic 'Not in a QuickScale project directory' not found"
            echo "      Output:"
            echo "$output" | sed 's/^/        /'
            return 1
        fi
    fi

    echo "      ✅ exit $exit_code, no traceback"
    return 0
}

# ---- cleanup ----

cleanup() {
    local status=$?

    # Stage and build dirs are per-run temp dirs — just remove them.
    if [[ -n "${STAGE_DIR:-}" ]] && [[ -d "$STAGE_DIR" ]]; then
        rm -rf "$STAGE_DIR"
    fi

    if [[ -n "${BUILD_VENVS_DIR:-}" ]] && [[ -d "$BUILD_VENVS_DIR" ]]; then
        rm -rf "$BUILD_VENVS_DIR"
    fi

    if [[ -n "${SMOKE_VENV_DIR:-}" ]] && [[ -d "$SMOKE_VENV_DIR" ]]; then
        rm -rf "$SMOKE_VENV_DIR"
    fi

    if [[ -n "${SMOKE_WORK_DIR:-}" ]] && [[ -d "$SMOKE_WORK_DIR" ]]; then
        rm -rf "$SMOKE_WORK_DIR"
    fi

    if [[ -n "${WHEEL_COLLECT_DIR:-}" ]] && [[ -d "$WHEEL_COLLECT_DIR" ]]; then
        rm -rf "$WHEEL_COLLECT_DIR"
    fi

    if [[ $status -eq 0 ]]; then
        echo ""
        echo "✅ Smoke install gate passed — all checks green."
    else
        echo ""
        echo "❌ Smoke install gate FAILED (exit $status)."
    fi

    exit "$status"
}

# ====== Main ======

VERSION="$(read_version)"
trap cleanup EXIT

echo "🔍 Smoke Install Gate (SA110) — version $VERSION"
echo ""

# ---- Prerequisites ----

echo "📋 Checking prerequisites..."
ensure_compatible_python_available
ensure_compatible_python_venv_available

if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is required but not installed."
    exit 1
fi

POETRY_VERSION="$(poetry --version)"
echo "   ✅ Python $PYTHON_DISPLAY_VERSION ($("$PYTHON_BIN" --version 2>&1)) at $PYTHON_BIN"
echo "   ✅ $POETRY_VERSION"
echo ""

# ---- Create per-run working directories ----
# These are cleaned up on exit by the trap; never persisted.

STAGE_DIR="$(mktemp -d "/tmp/quickscale-stage-XXXXXX")"
BUILD_VENVS_DIR="$(mktemp -d "/tmp/quickscale-build-venvs-XXXXXX")"
WHEEL_COLLECT_DIR="$(mktemp -d "/tmp/quickscale-wheels-XXXXXX")"

# ---- Stage and build all packages ----
# Order: quickscale_core → quickscale_cli (path dep on core) → quickscale

echo "🏗️  Staging and building wheel packages..."

# Stage packages with pyproject.toml modifications applied to copies.
stage_package "quickscale_core" "$VERSION" "no"   > /dev/null
stage_package "quickscale_cli"  "$VERSION" "yes"  > /dev/null
stage_package "quickscale"      "$VERSION" "no"   > /dev/null

echo ""

# Build from staged copies.  Each build collects its wheel into
# WHEEL_COLLECT_DIR so installation can reference one directory.
build_staged_package "quickscale_core"
build_staged_package "quickscale_cli"
build_staged_package "quickscale"

echo "   ✅ All packages built (wheels in $WHEEL_COLLECT_DIR)"
echo ""

# ---- Create throwaway venv outside the source tree ----

echo "📦 Creating throwaway venv outside source tree..."
SMOKE_VENV_DIR="$(mktemp -d "/tmp/quickscale-smoke-venv-XXXXXX")"
"$PYTHON_BIN" -m venv "$SMOKE_VENV_DIR"

# ---- Install wheels into throwaway venv ----

echo "📦 Installing wheels..."
pip_install_isolated "$SMOKE_VENV_DIR" \
    "$WHEEL_COLLECT_DIR/quickscale_core-"*.whl \
    "$WHEEL_COLLECT_DIR/quickscale_cli-"*.whl \
    "$WHEEL_COLLECT_DIR/quickscale-"*.whl
echo "   ✅ Installation complete"
echo ""

# ---- Create external working directory for sanitized execution ----

SMOKE_WORK_DIR="$(mktemp -d "/tmp/quickscale-smoke-work-XXXXXX")"
SMOKE_QUICKSCALE="$SMOKE_VENV_DIR/bin/quickscale"

# ---- Run smoke tests ----
# All probes go through run_smoke_probe which sanitizes PYTHONPATH, PYTHONHOME,
# and cds to SMOKE_WORK_DIR so the installed artifact cannot resolve back into
# the source tree.

echo "🔬 Running smoke tests..."

FAILED=0
SMOKE_COMMANDS=(
    "--version"
    "version"
    "--help"
)

# All registered top-level subcommands (from main.py), excluding
# state-changing/outward-facing commands.
SUBCOMMANDS=(
    "version"
    "up"
    "down"
    "shell"
    "manage"
    "logs"
    "ps"
    "deploy"
    "dr"
    "update"
    "push"
    "plan"
    "apply"
    "status"
    "remove"
)

# Root-level smoke tests (--version, version, --help).
for cmd in "${SMOKE_COMMANDS[@]}"; do
    if ! run_smoke_probe "quickscale $cmd" \
        "$SMOKE_QUICKSCALE" "$cmd"; then
        FAILED=1
    fi
done

# --help for every registered subcommand.
for sub in "${SUBCOMMANDS[@]}"; do
    if ! run_smoke_probe "quickscale $sub --help" \
        "$SMOKE_QUICKSCALE" "$sub" "--help"; then
        FAILED=1
    fi
done

# quickscale status from outside a project: exit 1, expected diagnostic, no traceback.
if ! run_smoke_probe "quickscale status (outside project, expect exit 1)" \
    "$SMOKE_QUICKSCALE" "status"; then
    FAILED=1
fi

# quickscale plan probe (SA111a): non-interactive with all 12 modules via
# scripted stdin, exercising the full module-implication graph from an
# installed context.  Must exit 0 with no traceback.
PLAN_TEST_DIR="$(mktemp -d -p "$SMOKE_WORK_DIR" quickscale-plan-test-XXXXXX)"
(
    cd "$PLAN_TEST_DIR"
    # Prevent source-tree leakage through environment variables (SA111a).
    unset PYTHONPATH
    unset PYTHONHOME
    echo "    🔍 quickscale plan testproj (all 12 modules, expect exit 0)"
    output="$(
        printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' | \
        "$SMOKE_QUICKSCALE" plan testproj 2>&1
    )" && exit_code=0 || exit_code=$?

    if echo "$output" | grep -q 'Traceback (most recent call last)'; then
        echo "      ❌ TRACEBACK DETECTED"
        echo "      Output:"
        echo "$output" | sed 's/^/        /'
        exit 1
    fi

    if [[ $exit_code -ne 0 ]]; then
        echo "      ❌ Expected exit code 0 but got $exit_code"
        echo "      Output:"
        echo "$output" | sed 's/^/        /'
        exit 1
    fi

    echo "      ✅ exit $exit_code, no traceback"
) || FAILED=1

echo ""

if [[ $FAILED -ne 0 ]]; then
    echo "❌ Smoke install gate: $FAILED test(s) failed."
    exit 1
fi

echo "✅ All smoke tests passed!"
exit 0
