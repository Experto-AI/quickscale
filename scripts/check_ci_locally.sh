#!/usr/bin/env bash
set -euo pipefail

# Local CI check script — the single pre-push script to verify the primary local
# development checks (install + lint + typecheck + unit tests + optional
# integration tests when PostgreSQL is available).
#
# Usage:
#   ./scripts/check_ci_locally.sh          # Standard check (lint + type + unit tests)
#   ./scripts/check_ci_locally.sh --e2e    # Full check including E2E tests (slow)
#   ./scripts/check_ci_locally.sh --help   # Show help

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# Reuse the worker-pool process-tree and deterministic replay helpers used by
# the integration runner. Signal traps below are installed only while the
# static fan-out owns background workers; serial and post-static commands stay
# foreground commands with the shell's normal signal semantics.
# shellcheck source=./_qs_jobs.sh
source "$ROOT/scripts/_qs_jobs.sh"

WORKER_TEMP_DIR=""
declare -a WORKER_PIDS=()
declare -a WORKER_ORDER=()
WORKER_TRAP_TERM=""
WORKER_TRAP_INT=""
WORKER_TRAP_HUP=""
WORKER_SIGNAL_HANDLING=false
WORKER_WAIT_PID=""

cleanup_temp_files() {
    if [ -n "${WORKER_TEMP_DIR:-}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
        rm -rf "$WORKER_TEMP_DIR"
    fi
}

trap cleanup_temp_files EXIT

save_worker_traps() {
    WORKER_TRAP_TERM=$(trap -p TERM)
    WORKER_TRAP_INT=$(trap -p INT)
    WORKER_TRAP_HUP=$(trap -p HUP)
    trap '_handle_static_gate_signal TERM 143' TERM
    trap '_handle_static_gate_signal INT 130' INT
    trap '_handle_static_gate_signal HUP 129' HUP
}

restore_worker_traps() {
    if [ -n "$WORKER_TRAP_TERM" ]; then
        eval "$WORKER_TRAP_TERM"
    else
        trap - TERM
    fi
    if [ -n "$WORKER_TRAP_INT" ]; then
        eval "$WORKER_TRAP_INT"
    else
        trap - INT
    fi
    if [ -n "$WORKER_TRAP_HUP" ]; then
        eval "$WORKER_TRAP_HUP"
    else
        trap - HUP
    fi
    WORKER_TRAP_TERM=""
    WORKER_TRAP_INT=""
    WORKER_TRAP_HUP=""
}

_worker_pid_is_active() {
    local pid="$1"
    local active_pid

    while read -r active_pid; do
        if [ "$active_pid" = "$pid" ]; then
            return 0
        fi
    done < <(jobs -pr)
    return 1
}

_worker_pid_is_owned() {
    local pid="$1"
    local owned_pid

    while read -r owned_pid; do
        if [ "$owned_pid" = "$pid" ]; then
            return 0
        fi
    done < <(jobs -p)
    return 1
}

_handle_static_gate_signal() {
    local signal_name="$1"
    local exit_code="$2"
    local pid
    local i

    # A second signal while this handler is reaping must not recursively
    # target a partially-cleared PID array.
    if [ "$WORKER_SIGNAL_HANDLING" = true ]; then
        return 0
    fi
    WORKER_SIGNAL_HANDLING=true
    echo "" >&2
    echo "⚠ Received SIG${signal_name}, terminating static gate workers..." >&2
    for pid in "${WORKER_PIDS[@]:-}"; do
        if [ -n "$pid" ] && _worker_pid_is_active "$pid"; then
            _kill_descendants "$pid" "$signal_name"
        fi
    done
    if [ -n "$WORKER_WAIT_PID" ] && _worker_pid_is_active "$WORKER_WAIT_PID"; then
        _kill_descendants "$WORKER_WAIT_PID" "$signal_name"
    fi
    for i in "${!WORKER_PIDS[@]}"; do
        pid="${WORKER_PIDS[$i]}"
        if [ -n "$pid" ] && _worker_pid_is_owned "$pid"; then
            wait "$pid" 2>/dev/null || true
        fi
        unset 'WORKER_PIDS[i]'
    done
    if [ -n "$WORKER_WAIT_PID" ] && _worker_pid_is_owned "$WORKER_WAIT_PID"; then
        wait "$WORKER_WAIT_PID" 2>/dev/null || true
    fi
    WORKER_WAIT_PID=""
    WORKER_PIDS=()
    WORKER_ORDER=()
    restore_worker_traps
    cleanup_temp_files
    WORKER_TEMP_DIR=""
    exit "$exit_code"
}

# Parse arguments
RUN_E2E=false
for arg in "$@"; do
    case $arg in
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/check_ci_locally.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --e2e     Include E2E tests (slow, requires Docker)"
            echo "  --help    Show this help message"
            echo ""
            echo "Environment:"
            echo "  QS_CI_PARALLEL=0  Run static stages serially (default: concurrent fan-out)"
            echo ""
            echo "This script runs the primary local development checks:"
            echo "  1. Install dependencies"
            echo "  2. Lint (ruff check + format)"
            echo "  3. Module-to-core compatibility (check_module_core_compatibility)"
            echo "  4. Module-core import linter (check_module_core_imports)"
            echo "  5. Manifest sync gate (sync_module_manifests)"
            echo "  6. Org-context primitives gate (check_org_context_primitives)"
            echo "  7. CSRF-exempt gate (check_csrf_exempt_gate)"
            echo "  8. Type check (mypy)"
            echo "  9. Coverage policy helper tests"
            echo " 10. Combined coverage checks (core + CLI + backups module with dual-threshold policy)"
            echo " 11. Integration tests (requires PostgreSQL)"
            echo " 12. E2E tests (optional, with --e2e flag)"
            exit 0
            ;;
    esac
done

echo "╔════════════════════════════════════════╗"
echo "║   QuickScale Local CI Check            ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Determine stage count: E2E adds one extra stage (12 total)
TOTAL_STAGES=11
if [ "$RUN_E2E" = true ]; then
    TOTAL_STAGES=12
fi

run_static_gates_serial() {
    # This is intentionally the pre-TP1 order and failure behaviour. It is
    # the debugging escape hatch selected by QS_CI_PARALLEL=0.
    local FAILED=false

    echo "[2/${TOTAL_STAGES}] Running linters (ruff)..."
    make lint -- --core --cli --modules --devtools
    echo "✓ Linting passed"

    echo ""
    echo "[3/${TOTAL_STAGES}] Running module-vs-core compatibility check..."
    make check-core-compat || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Module-Core Compatibility Failed   ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Module-to-core compatibility passed"

    echo ""
    echo "[4/${TOTAL_STAGES}] Running module-core import linter..."
    make check-module-core-imports || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Module-Core Import Linter Failed   ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Module-core import linter passed"

    echo ""
    echo "[5/${TOTAL_STAGES}] Running manifest sync gate..."
    make check-manifest-sync || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Manifest Sync Gate Failed          ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Manifest snapshots in sync"

    echo ""
    echo "[6/${TOTAL_STAGES}] Running org-context primitives gate..."
    make check-org-context-primitives || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Org-Context Primitives Gate Failed  ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ No direct external use of privatized org-context primitives"

    echo ""
    echo "[7/${TOTAL_STAGES}] Running CSRF-exempt gate..."
    make check-csrf-exempt || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ CSRF-Exempt Gate Failed            ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ All csrf_exempt callsites are protected"

    echo ""
    echo "[8/${TOTAL_STAGES}] Running type checks (mypy)..."
    make typecheck -- --core --cli --modules --devtools
    echo "✓ Type checks passed"

    echo ""
    echo "[9/${TOTAL_STAGES}] Running coverage policy helper tests..."
    make test-cov-policy || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Coverage Policy Helper Tests Failed║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Coverage policy helper tests passed"

    echo ""
    make test-integration-worker-pool || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Worker Pool Harness Tests Failed   ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Worker pool harness tests passed"
}

launch_static_gate() {
    local stage_id="$1"
    local stage_number="$2"
    local description="$3"
    local success_message="$4"
    local failure_label="$5"
    shift 5

    STATIC_STAGE_NAMES+=("$stage_id")
    STATIC_FAILURE_LABELS+=("$failure_label")
    WORKER_ORDER+=("$stage_id")
    (
        echo "[$stage_number/${TOTAL_STAGES}] $description"
        # run_static_gates_parallel is intentionally called in a conditional
        # so its aggregate status can be handled without set -e exiting before
        # all workers are joined. Capture each worker command explicitly.
        set +e
        "$@"
        gate_exit=$?
        set -e
        if [ "$gate_exit" -ne 0 ]; then
            exit "$gate_exit"
        fi
        echo "$success_message"
    ) > "$WORKER_TEMP_DIR/log_${stage_id}" 2>&1 &
    WORKER_PIDS+=("$!")
}

report_static_failure_banner() {
    case "$1" in
        lint)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Linting Failed                     ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        core-compat)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Module-Core Compatibility Failed   ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        module-core-imports)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Module-Core Import Linter Failed   ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        manifest-sync)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Manifest Sync Gate Failed          ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        org-context)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Org-Context Primitives Gate Failed  ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        csrf-exempt)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ CSRF-Exempt Gate Failed            ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        typecheck)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Type Checks Failed                 ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        coverage-policy)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Coverage Policy Helper Tests Failed║"
            echo "╚════════════════════════════════════════╝"
            ;;
        worker-pool)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Worker Pool Harness Tests Failed   ║"
            echo "╚════════════════════════════════════════╝"
            ;;
    esac
}

run_static_gates_parallel() {
    local i
    local worker_exit
    local failed_count=0

    WORKER_TEMP_DIR="$(mktemp -d)"
    WORKER_PIDS=()
    WORKER_ORDER=()
    STATIC_STAGE_NAMES=()
    STATIC_FAILURE_LABELS=()
    STATIC_EXIT_CODES=()
    save_worker_traps

    # Every independent static gate is launched before any wait. The two
    # existing stage-9 harnesses are separate workers but retain the same
    # stage number and declaration order in replay/failure attribution.
    launch_static_gate lint 2 "Running linters (ruff)..." "✓ Linting passed" "Linting" \
        make lint -- --core --cli --modules --devtools
    launch_static_gate core-compat 3 "Running module-vs-core compatibility check..." \
        "✓ Module-to-core compatibility passed" "Module-Core Compatibility" \
        make check-core-compat
    launch_static_gate module-core-imports 4 "Running module-core import linter..." \
        "✓ Module-core import linter passed" "Module-Core Import Linter" \
        make check-module-core-imports
    launch_static_gate manifest-sync 5 "Running manifest sync gate..." \
        "✓ Manifest snapshots in sync" "Manifest Sync Gate" make check-manifest-sync
    launch_static_gate org-context 6 "Running org-context primitives gate..." \
        "✓ No direct external use of privatized org-context primitives" \
        "Org-Context Primitives Gate" make check-org-context-primitives
    launch_static_gate csrf-exempt 7 "Running CSRF-exempt gate..." \
        "✓ All csrf_exempt callsites are protected" "CSRF-Exempt Gate" make check-csrf-exempt
    launch_static_gate typecheck 8 "Running type checks (mypy)..." "✓ Type checks passed" \
        "Type Checks" make typecheck -- --core --cli --modules --devtools
    launch_static_gate coverage-policy 9 "Running coverage policy helper tests..." \
        "✓ Coverage policy helper tests passed" "Coverage Policy Helper Tests" \
        make test-cov-policy
    launch_static_gate worker-pool 9 "Running worker pool harness tests..." \
        "✓ Worker pool harness tests passed" "Worker Pool Harness Tests" \
        make test-integration-worker-pool

    # Join in declaration order so every worker exit code is retained even
    # when several gates fail. Output is replayed only after all joins.
    for i in "${!WORKER_PIDS[@]}"; do
        WORKER_WAIT_PID="${WORKER_PIDS[$i]}"
        # Remove the PID from the pending-worker set before wait. The signal
        # handler tracks this one separately and checks actual shell job
        # ownership, so a signal delivered after reap cannot target a stale
        # array entry or a later PID reuse.
        unset 'WORKER_PIDS[i]'
        worker_exit=0
        wait "$WORKER_WAIT_PID" || worker_exit=$?
        STATIC_EXIT_CODES[$i]="$worker_exit"
        WORKER_WAIT_PID=""
    done
    WORKER_PIDS=()
    restore_worker_traps

    _qs_replay_worker_logs "$WORKER_TEMP_DIR"

    for i in "${!STATIC_STAGE_NAMES[@]}"; do
        if [ "${STATIC_EXIT_CODES[$i]}" -ne 0 ]; then
            failed_count=$((failed_count + 1))
        fi
    done

    if [ "$failed_count" -ne 0 ]; then
        echo ""
        echo "Static gate failure attribution:"
        for i in "${!STATIC_STAGE_NAMES[@]}"; do
            if [ "${STATIC_EXIT_CODES[$i]}" -ne 0 ]; then
                echo "  ✗ ${STATIC_FAILURE_LABELS[$i]} (exit ${STATIC_EXIT_CODES[$i]})"
                report_static_failure_banner "${STATIC_STAGE_NAMES[$i]}"
            fi
        done
        echo ""
        echo "✗ ${failed_count} static CI gate(s) failed; database-dependent stages will not run."
        cleanup_temp_files
        WORKER_TEMP_DIR=""
        WORKER_ORDER=()
        return 1
    fi

    cleanup_temp_files
    WORKER_TEMP_DIR=""
    WORKER_ORDER=()
}

echo "[1/${TOTAL_STAGES}] Installing dependencies..."
poetry install --with dev

if [ "${QS_CI_PARALLEL:-1}" = "0" ]; then
    run_static_gates_serial
else
    run_static_gates_parallel || exit 1
fi

# Track overall status for the serial stages that follow the static fan-out.
FAILED=false

echo ""
echo "[10/${TOTAL_STAGES}] Running coverage checks (core + CLI + backups)..."
make test-cov REQUIRE_BACKUPS_COVERAGE=1 || FAILED=true

if [ "$FAILED" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║   ✗ Coverage Checks Failed             ║"
    echo "╚════════════════════════════════════════╝"
    exit 1
fi
echo "✓ Combined coverage checks passed (90% equal-weight package mean, 80% per-file)"

echo ""
echo "[11/${TOTAL_STAGES}] Running integration tests..."
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -q 2>/dev/null; then
    echo "PostgreSQL is available — running integration tests..."
    ./scripts/test_integration.sh || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Integration Tests Failed           ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Integration tests passed"
else
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║   ✗ PostgreSQL Not Available                               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Integration tests require PostgreSQL 18 with a LOGIN CREATEDB"
    echo "  NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE role on localhost:5432."
    echo ""
    echo "  QuickScale uses a split test model to separate DB-free"
    echo "  unit tests from PostgreSQL-backed integration tests:"
    echo ""
    echo "    make test-unit           DB-free unit tests (core + CLI)"
    echo "    make test-integration    Integration tests (requires PostgreSQL)"
    echo ""
    echo "  To run checks locally without PostgreSQL, use:"
    echo "    make test-unit"
    echo ""
    echo "  To set up PostgreSQL and run the full suite, see"
    echo "  docs/technical/development.md for setup instructions,"
    echo "  then run make ci."
    echo ""
    exit 1
fi

# Optional E2E tests
if [ "$RUN_E2E" = true ]; then
    echo ""
    echo "[12/${TOTAL_STAGES}] Running E2E tests (this may take several minutes)..."
    ./scripts/test_e2e.sh || FAILED=true

    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ E2E Tests Failed                   ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ E2E tests passed"
else
    echo ""
    echo "Skipping E2E tests (use --e2e to include)"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   ✓ All CI Checks Passed!              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Ready to push to GitHub."
