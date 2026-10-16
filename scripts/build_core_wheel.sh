#!/usr/bin/env bash
# SA285 (b) — the one shared quickscale_core wheel build step.
#
# Materializes the bundled module manifests (scripts/sync_module_manifests.py)
# and builds the quickscale_core wheel with Poetry.  Every build entrypoint
# routes its core build through this script — directly or through
# `make build-core` — and scripts/check_core_build_routing.py fails when a
# shell entrypoint, the Makefile, or a workflow runs `poetry build` for the
# core package outside it.
#
# Usage:
#   scripts/build_core_wheel.sh [--root PATH] [--package-dir PATH]
#                               [--python PATH]
#                               [--materialize-only | --build-only]
#
#   --root PATH          Repository root whose bundled module manifests are
#                        materialized (default: this script's repository root).
#   --package-dir PATH   Package directory to build
#                        (default: <root>/quickscale_core).
#   --python PATH        Interpreter that runs the manifest materializer
#                        (default: the first python3 on PATH).
#   --materialize-only   Run only the materialization phase.
#   --build-only         Run only the build phase; the caller has already
#                        materialized or staged the package tree.
#
# Each caller keeps its own staging around the call: a README copy and
# pyproject rewrite (scripts/publish.sh), a selected compatible-Python Poetry
# environment (scripts/install_global.sh), or a per-run staged package copy
# (scripts/_installed_wheel_venv.sh).  The build phase runs `poetry build` in
# --package-dir with the caller's environment.
#
# Exit codes:
#   0 — the requested phases completed
#   2 — usage or configuration error
#   otherwise — the materializer's or Poetry's own exit status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$DEFAULT_ROOT"
PACKAGE_DIR=""
PYTHON_BIN=""
RUN_MATERIALIZE=1
RUN_BUILD=1
PHASE=""

usage() {
    echo "Usage: scripts/build_core_wheel.sh [--root PATH] [--package-dir PATH]" >&2
    echo "                                   [--python PATH]" >&2
    echo "                                   [--materialize-only | --build-only]" >&2
    echo "" >&2
    echo "Materializes the bundled module manifests and builds the quickscale_core" >&2
    echo "wheel; see the script header for the full contract." >&2
}

require_value() {
    local option="$1"
    if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ERROR: $option requires a value" >&2
        usage
        exit 2
    fi
}

materialize_bundled_manifests() {
    local materializer="$ROOT/scripts/sync_module_manifests.py"
    if [[ ! -f "$materializer" ]]; then
        echo "ERROR: bundled-manifest materializer not found: $materializer" >&2
        exit 2
    fi
    if [[ -z "$PYTHON_BIN" ]]; then
        PYTHON_BIN="$(command -v python3 || true)"
    fi
    if [[ -z "$PYTHON_BIN" ]]; then
        echo "ERROR: no python3 interpreter found for the bundled-manifest materializer" >&2
        exit 2
    fi
    "$PYTHON_BIN" "$materializer" "$ROOT"
}

build_core_wheel() {
    local package_dir="${PACKAGE_DIR:-$ROOT/quickscale_core}"
    if [[ ! -f "$package_dir/pyproject.toml" ]]; then
        echo "ERROR: no pyproject.toml to build in $package_dir" >&2
        exit 2
    fi
    (cd "$package_dir" && poetry build)
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            require_value "$1" "${2:-}"
            ROOT="$2"
            shift 2
            ;;
        --package-dir)
            require_value "$1" "${2:-}"
            PACKAGE_DIR="$2"
            shift 2
            ;;
        --python)
            require_value "$1" "${2:-}"
            PYTHON_BIN="$2"
            shift 2
            ;;
        --materialize-only|--build-only)
            if [[ -n "$PHASE" && "$PHASE" != "$1" ]]; then
                echo "ERROR: $1 conflicts with $PHASE" >&2
                exit 2
            fi
            PHASE="$1"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

case "$PHASE" in
    --materialize-only) RUN_BUILD=0 ;;
    --build-only) RUN_MATERIALIZE=0 ;;
    "") ;;
esac

if [[ "$RUN_MATERIALIZE" == "1" ]]; then
    materialize_bundled_manifests
fi
if [[ "$RUN_BUILD" == "1" ]]; then
    build_core_wheel
fi
