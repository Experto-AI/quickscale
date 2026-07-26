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
# shellcheck source=./_installed_wheel_venv.sh
source "$ROOT/scripts/_installed_wheel_venv.sh"

# Working directories (all temp, cleaned up on exit).
SMOKE_VENV_DIR=""     # Throwaway venv for wheel installation
SMOKE_WORK_DIR=""     # External cwd for sanitized probe execution


# ---- test helpers ----
# (provisioning helpers read_version, python_within_spec, smoke_select_python,
#  ensure_compatible_python_available, ensure_compatible_python_venv_available,
#  ensure_poetry_uses_compatible_python, build_with_poetry,
#  pip_install_isolated, stage_package, build_staged_package, and
#  iw_provision_installed_venv are provided by _installed_wheel_venv.sh)

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

    # STAGE_DIR, BUILD_VENVS_DIR, WHEEL_COLLECT_DIR are managed by the
    # iw_provision_installed_venv subshell EXIT trap; only caller-owned
    # dirs are cleaned here.
    if [[ -n "${SMOKE_VENV_DIR:-}" ]] && [[ -d "$SMOKE_VENV_DIR" ]]; then
        rm -rf "$SMOKE_VENV_DIR"
    fi

    if [[ -n "${SMOKE_WORK_DIR:-}" ]] && [[ -d "$SMOKE_WORK_DIR" ]]; then
        rm -rf "$SMOKE_WORK_DIR"
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

# ---- Provision installed venv (SA112) ----

echo "🏗️  Provisioning installed venv (SA112)..."
SMOKE_VENV_DIR="$(mktemp -d "/tmp/quickscale-smoke-venv-XXXXXX")"
SMOKE_QUICKSCALE="$(iw_provision_installed_venv "$SMOKE_VENV_DIR")"
echo "   ✅ Provisioned venv at $SMOKE_VENV_DIR"

# ---- Create external working directory for sanitized execution ----

SMOKE_WORK_DIR="$(mktemp -d "/tmp/quickscale-smoke-work-XXXXXX")"

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
