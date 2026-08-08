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

show_help() {
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
    echo "     Rendered frontend lint (when Node.js and pnpm are available)"
    echo " 10. Combined coverage checks (core + CLI + backups module with dual-threshold policy)"
    echo " 11. Integration tests (requires PostgreSQL)"
    echo " 12. E2E tests (optional, with --e2e flag)"
    exit 0
}

# Parse help before registry or interpreter bootstrap so documentation remains
# available even when contributor tooling is not installed yet.
RUN_E2E=false
for arg in "$@"; do
    case $arg in
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
    esac
done

# The registry is an input to local-CI execution. Keep this derivation in the
# declaration prefix so the parity observer executes the same inventory that
# the production entrypoint uses, without reaching the command-oriented tail.
GATE_REGISTRY="${GATE_REGISTRY:-$ROOT/scripts/gate_registry.json}"
if [ -n "${PYTHON3:-}" ]; then
    REGISTRY_PYTHON=("$PYTHON3")
elif command -v python3 >/dev/null 2>&1; then
    REGISTRY_PYTHON=("$(command -v python3)")
elif command -v poetry >/dev/null 2>&1; then
    REGISTRY_PYTHON=(poetry run python)
else
    echo "ERROR: unable to locate a supported Python interpreter for $GATE_REGISTRY" >&2
    exit 1
fi
declare -a LOCAL_CONFORMANCE_GATE_IDS=()
declare -a LOCAL_CONFORMANCE_GATE_TARGETS=()
declare -a LOCAL_CONFORMANCE_GATE_STAGES=()

load_local_conformance_gates() {
    local registry_rows
    if ! registry_rows=$("${REGISTRY_PYTHON[@]}" - "$GATE_REGISTRY" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as registry_file:
    registry = json.load(registry_file)

rows = []
for registry_index, gate in enumerate(registry["gates"]):
    bindings = gate["bindings"]
    target = bindings.get("make_target")
    stage = bindings.get("local_ci_stage")
    if (
        isinstance(target, str)
        and target
        and isinstance(stage, int)
        and not isinstance(stage, bool)
        and 3 <= stage <= 7
    ):
        rows.append((stage, registry_index, gate["id"], target))

for stage, _, gate_id, target in sorted(rows):
    print(f"{gate_id}\t{target}\t{stage}")
PY
    ); then
        echo "ERROR: unable to derive local conformance gates from $GATE_REGISTRY" >&2
        return 1
    fi

    while IFS=$'\t' read -r gate_id target stage; do
        if [ -z "$gate_id" ] || [ -z "$target" ] || [ -z "$stage" ]; then
            echo "ERROR: invalid local conformance gate row from $GATE_REGISTRY" >&2
            return 1
        fi
        LOCAL_CONFORMANCE_GATE_IDS+=("$gate_id")
        LOCAL_CONFORMANCE_GATE_TARGETS+=("$target")
        LOCAL_CONFORMANCE_GATE_STAGES+=("$stage")
    done <<< "$registry_rows"
}

load_local_conformance_gates

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

echo "╔════════════════════════════════════════╗"
echo "║   QuickScale Local CI Check            ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Determine stage count: E2E adds one extra stage (12 total)
TOTAL_STAGES=11
if [ "$RUN_E2E" = true ]; then
    TOTAL_STAGES=12
fi

run_frontend_lint() {
    if ! command -v node >/dev/null 2>&1; then
        echo "ℹ️ Skipping rendered frontend lint (Node.js is not available)."
        return 0
    fi
    if ! command -v pnpm >/dev/null 2>&1; then
        echo "ℹ️ Skipping rendered frontend lint (pnpm is not available)."
        return 0
    fi
    make lint-frontend
}

describe_local_conformance_gate() {
    local target="$1"

    case "$target" in
        check-core-compat)
            LOCAL_GATE_DESCRIPTION="Running module-vs-core compatibility check..."
            LOCAL_GATE_SUCCESS="✓ Module-to-core compatibility passed"
            LOCAL_GATE_FAILURE_LABEL="Module-Core Compatibility"
            ;;
        check-module-core-imports)
            LOCAL_GATE_DESCRIPTION="Running module-core import linter..."
            LOCAL_GATE_SUCCESS="✓ Module-core import linter passed"
            LOCAL_GATE_FAILURE_LABEL="Module-Core Import Linter"
            ;;
        check-manifest-sync)
            LOCAL_GATE_DESCRIPTION="Running manifest sync gate..."
            LOCAL_GATE_SUCCESS="✓ Manifest snapshots in sync"
            LOCAL_GATE_FAILURE_LABEL="Manifest Sync Gate"
            ;;
        check-org-context-primitives)
            LOCAL_GATE_DESCRIPTION="Running org-context primitives gate..."
            LOCAL_GATE_SUCCESS="✓ No direct external use of privatized org-context primitives"
            LOCAL_GATE_FAILURE_LABEL="Org-Context Primitives Gate"
            ;;
        check-csrf-exempt)
            LOCAL_GATE_DESCRIPTION="Running CSRF-exempt gate..."
            LOCAL_GATE_SUCCESS="✓ All csrf_exempt callsites are protected"
            LOCAL_GATE_FAILURE_LABEL="CSRF-Exempt Gate"
            ;;
        *)
            LOCAL_GATE_DESCRIPTION="Running $target..."
            LOCAL_GATE_SUCCESS="✓ $target passed"
            LOCAL_GATE_FAILURE_LABEL="$target"
            ;;
    esac
}

run_serial_conformance_gate() {
    local gate_id="$1"
    local stage_number="$2"
    local target="$3"
    : "$gate_id"

    describe_local_conformance_gate "$target"
    echo ""
    echo "[$stage_number/${TOTAL_STAGES}] $LOCAL_GATE_DESCRIPTION"
    if ! make "$target"; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        case "$target" in
            check-core-compat)
                echo "║   ✗ Module-Core Compatibility Failed   ║"
                ;;
            check-module-core-imports)
                echo "║   ✗ Module-Core Import Linter Failed   ║"
                ;;
            check-manifest-sync)
                echo "║   ✗ Manifest Sync Gate Failed          ║"
                ;;
            check-org-context-primitives)
                echo "║   ✗ Org-Context Primitives Gate Failed  ║"
                ;;
            check-csrf-exempt)
                echo "║   ✗ CSRF-Exempt Gate Failed            ║"
                ;;
            *)
                printf '║   ✗ %-36s║\n' "$target Failed"
                ;;
        esac
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "$LOCAL_GATE_SUCCESS"
}

run_static_gates_serial() {
    # This is intentionally the pre-TP1 order and failure behaviour. It is
    # the debugging escape hatch selected by QS_CI_PARALLEL=0.
    local FAILED=false

    echo "[2/${TOTAL_STAGES}] Running linters (ruff)..."
    make lint -- --core --cli --modules --devtools
    echo "✓ Linting passed"

    local i
    for i in "${!LOCAL_CONFORMANCE_GATE_TARGETS[@]}"; do
        run_serial_conformance_gate \
            "${LOCAL_CONFORMANCE_GATE_IDS[$i]}" \
            "${LOCAL_CONFORMANCE_GATE_STAGES[$i]}" \
            "${LOCAL_CONFORMANCE_GATE_TARGETS[$i]}"
    done

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

    echo ""
    echo "[9/${TOTAL_STAGES}] Running rendered frontend lint..."
    run_frontend_lint || FAILED=true
    if [ "$FAILED" = true ]; then
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║   ✗ Frontend Lint Failed               ║"
        echo "╚════════════════════════════════════════╝"
        exit 1
    fi
    echo "✓ Rendered frontend lint passed"
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
        core-compat|check-core-compat)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Module-Core Compatibility Failed   ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        module-core-imports|check-module-core-imports)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Module-Core Import Linter Failed   ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        manifest-sync|check-manifest-sync)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Manifest Sync Gate Failed          ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        org-context|check-org-context-primitives)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Org-Context Primitives Gate Failed  ║"
            echo "╚════════════════════════════════════════╝"
            ;;
        csrf-exempt|check-csrf-exempt)
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
        frontend-lint)
            echo "╔════════════════════════════════════════╗"
            echo "║   ✗ Frontend Lint Failed               ║"
            echo "╚════════════════════════════════════════╝"
            ;;
    esac
}

run_static_gates_parallel() {
    local i
    local target
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
    # existing stage-9 harnesses and frontend lint are separate workers but retain the same
    # stage number and declaration order in replay/failure attribution.
    launch_static_gate lint 2 "Running linters (ruff)..." "✓ Linting passed" "Linting" \
        make lint -- --core --cli --modules --devtools
    for i in "${!LOCAL_CONFORMANCE_GATE_TARGETS[@]}"; do
        target="${LOCAL_CONFORMANCE_GATE_TARGETS[$i]}"
        describe_local_conformance_gate "$target"
        launch_static_gate "$target" "${LOCAL_CONFORMANCE_GATE_STAGES[$i]}" \
            "$LOCAL_GATE_DESCRIPTION" "$LOCAL_GATE_SUCCESS" "$LOCAL_GATE_FAILURE_LABEL" \
            make "$target"
    done
    launch_static_gate typecheck 8 "Running type checks (mypy)..." "✓ Type checks passed" \
        "Type Checks" make typecheck -- --core --cli --modules --devtools
    launch_static_gate coverage-policy 9 "Running coverage policy helper tests..." \
        "✓ Coverage policy helper tests passed" "Coverage Policy Helper Tests" \
        make test-cov-policy
    launch_static_gate worker-pool 9 "Running worker pool harness tests..." \
        "✓ Worker pool harness tests passed" "Worker Pool Harness Tests" \
        make test-integration-worker-pool
    launch_static_gate frontend-lint 9 "Running rendered frontend lint..." \
        "✓ Rendered frontend lint passed" "Frontend Lint" run_frontend_lint

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
