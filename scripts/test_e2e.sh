#!/usr/bin/env bash

#
# test_e2e.sh - Run full E2E tests locally
#
# This script sets up the complete E2E testing environment:
# - Starts PostgreSQL containers
# - Installs Playwright browsers
# - Runs comprehensive Core and CLI E2E tests
# - Cleans up each lane's containers afterward
#
# Usage:
#   ./scripts/test_e2e.sh [OPTIONS]
#
# Options:
#   --headed          Run Playwright in headed mode (show browser)
#   --no-cleanup      Don't cleanup Docker containers (for debugging)
#   --full            Show full pytest output (per-file lines)
#   --verbose         Alias for --full
#   --help            Show this help message
#
# Environment:
#   QS_E2E_PARALLEL=0          Run Core and CLI lanes serially (default: concurrent)
#   QS_E2E_NO_MEMORY_GUARD=1   Skip the low-memory preflight (never auto-fall back to serial)
#   QS_E2E_MIN_AVAIL_MB=N      Fall back to serial below N MB available RAM (default: 4096)
#   QS_E2E_MIN_SWAP_MB=N       Fall back to serial below N MB free swap when swap exists (default: 3072)
#   QS_E2E_HEARTBEAT_INTERVAL=N  Seconds between "still running" progress lines (default: 15)
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
HEADED=""
CLEANUP=true
SHOW_FULL_OUTPUT=false
PYTEST_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headed)
            HEADED="--headed"
            shift
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --full|--verbose|-v)
            SHOW_FULL_OUTPUT=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --headed          Run Playwright in headed mode (show browser)"
            echo "  --no-cleanup      Don't cleanup Docker containers (for debugging)"
            echo "  --full            Show full pytest output (per-file lines)"
            echo "  --verbose, -v     Alias for --full"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment:"
            echo "  QS_E2E_PARALLEL=0            Run Core and CLI lanes serially"
            echo "  QS_E2E_NO_MEMORY_GUARD=1     Skip the low-memory preflight"
            echo "  QS_E2E_MIN_AVAIL_MB=N        Serial fallback below N MB available RAM (default 4096)"
            echo "  QS_E2E_MIN_SWAP_MB=N         Serial fallback below N MB free swap (default 3072)"
            echo "  QS_E2E_HEARTBEAT_INTERVAL=N  Seconds between progress lines (default 15)"
            exit 0
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CORE_DIR="$PROJECT_ROOT/quickscale_core"
CLI_DIR="$PROJECT_ROOT/quickscale_cli"

# Reuse the shared process join and deterministic replay helpers.
# shellcheck source=./_qs_jobs.sh
source "$SCRIPT_DIR/_qs_jobs.sh"

if [ ! -d "$CORE_DIR" ]; then
    echo -e "${RED}Error: quickscale_core directory not found${NC}"
    echo "Please run this script from the project root or scripts directory"
    exit 1
fi

cd "$PROJECT_ROOT"

sanitize_scope() {
    local value="$1"
    value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]_' '_')"
    value="${value#-}"
    value="${value%-}"
    printf '%s' "${value:-lane}"
}

find_free_port() {
    python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

validate_app_port() {
    local port="$1"
    case "$port" in
        *[!0-9]*|"")
            echo -e "${RED}Error: QS_E2E_APP_PORT must be a numeric host port${NC}" >&2
            return 1
            ;;
    esac
    if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        echo -e "${RED}Error: QS_E2E_APP_PORT must be between 1 and 65535${NC}" >&2
        return 1
    fi
}

if [ -n "${QS_E2E_APP_PORT:-}" ]; then
    validate_app_port "$QS_E2E_APP_PORT"
fi

if [ "${QS_E2E_PARALLEL:-1}" = "0" ]; then
    E2E_PARALLEL=false
else
    E2E_PARALLEL=true
fi

# _meminfo_kb  — read a /proc/meminfo field (KB) by name; prints 0 if absent.
_meminfo_kb() {
    local field="$1"
    awk -v f="$field:" '$1 == f { print $2; found = 1 } END { if (!found) print 0 }' \
        /proc/meminfo 2>/dev/null
}

# Preflight memory guard.  Concurrent lanes launch two Docker + Playwright
# stacks at once; on a memory-tight host that peak can drive the session into
# swap thrash and get the run reaped by systemd-oomd (surfaces as a SIGTERM
# mid-run, not a test failure).  When resting headroom is already low we fall
# back to serial lanes, which roughly halves peak memory.  Thresholds are
# overridable; QS_E2E_NO_MEMORY_GUARD=1 disables the guard entirely.
#   QS_E2E_MIN_AVAIL_MB  minimum MemAvailable before fallback (default 4096)
#   QS_E2E_MIN_SWAP_MB   minimum SwapFree (when swap exists) before fallback (default 3072)
memory_preflight_guard() {
    [ "${QS_E2E_NO_MEMORY_GUARD:-0}" = "1" ] && return 0
    [ "$E2E_PARALLEL" = true ] || return 0
    [ -r /proc/meminfo ] || return 0

    local avail_mb swap_total_mb swap_free_mb min_avail_mb min_swap_mb reason=""
    avail_mb=$(( $(_meminfo_kb MemAvailable) / 1024 ))
    swap_total_mb=$(( $(_meminfo_kb SwapTotal) / 1024 ))
    swap_free_mb=$(( $(_meminfo_kb SwapFree) / 1024 ))
    min_avail_mb="${QS_E2E_MIN_AVAIL_MB:-4096}"
    min_swap_mb="${QS_E2E_MIN_SWAP_MB:-3072}"

    if [ "$avail_mb" -lt "$min_avail_mb" ]; then
        reason="available RAM ${avail_mb}MB < ${min_avail_mb}MB"
    elif [ "$swap_total_mb" -gt 0 ] && [ "$swap_free_mb" -lt "$min_swap_mb" ]; then
        reason="free swap ${swap_free_mb}MB < ${min_swap_mb}MB"
    fi

    if [ -n "$reason" ]; then
        E2E_PARALLEL=false
        echo -e "${YELLOW}⚠ Low memory headroom ($reason).${NC}" >&2
        echo -e "${YELLOW}  Falling back to serial lanes to avoid an out-of-memory kill (systemd-oomd).${NC}" >&2
        echo    "  Override with QS_E2E_NO_MEMORY_GUARD=1 to force concurrent lanes anyway." >&2
        echo "" >&2
    fi
}

memory_preflight_guard

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   QuickScale E2E Test Runner           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
if [ "$SHOW_FULL_OUTPUT" = true ]; then
    echo "Output mode: full"
else
    echo "Output mode: dots"
fi
if [ "$E2E_PARALLEL" = true ]; then
    echo "Lane mode: concurrent (Core + CLI)"
else
    echo "Lane mode: serial (QS_E2E_PARALLEL=0)"
fi
echo ""

# The parent owns only the worker logs. Containers are cleaned up by the lane
# that created them, so concurrent lanes never remove one another's services.
WORKER_TEMP_DIR="$(mktemp -d)"
declare -a WORKER_PIDS=()
declare -a WORKER_ORDER=()

HEARTBEAT_PID=""

# Stop the background progress ticker if one is running.  Safe to call when
# no heartbeat was started (empty PID) or when it has already exited.
stop_heartbeat() {
    if [ -n "$HEARTBEAT_PID" ]; then
        # Terminate the ticker and its in-flight `sleep` child together; killing
        # only the subshell would leave it blocked in `sleep`, deferring exit.
        _kill_descendants "$HEARTBEAT_PID" TERM 2>/dev/null || true
        wait "$HEARTBEAT_PID" 2>/dev/null || true
        HEARTBEAT_PID=""
    fi
}

cleanup_temp_files() {
    stop_heartbeat
    if [ -n "${WORKER_TEMP_DIR:-}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
        rm -rf "$WORKER_TEMP_DIR"
    fi
}

# _e2e_heartbeat  — emit a periodic "still running" line while lanes execute.
#
# The lane logs are buffered and only replayed after both lanes join, so the
# [3/4] phase would otherwise print nothing for several minutes.  This ticker
# reports elapsed time and per-lane state (a lane is "done" once it has written
# its status_<lane> file) without touching the buffered lane output, keeping the
# deterministic replay intact.  Interval is configurable via
# QS_E2E_HEARTBEAT_INTERVAL (seconds; default 15).
_e2e_heartbeat() {
    # Drop the inherited worker/cleanup traps: this ticker owns nothing, so a
    # kill from stop_heartbeat should end it immediately rather than run the
    # lane-cleanup signal handler or delete the shared temp dir.
    trap - INT TERM HUP EXIT
    local start elapsed mm ss core_state cli_state interval
    start="$(date +%s)"
    interval="${QS_E2E_HEARTBEAT_INTERVAL:-15}"
    while true; do
        sleep "$interval"
        elapsed=$(( $(date +%s) - start ))
        mm=$(( elapsed / 60 ))
        ss=$(( elapsed % 60 ))
        if [ -f "$WORKER_TEMP_DIR/status_core" ]; then core_state="done"; else core_state="running"; fi
        if [ -f "$WORKER_TEMP_DIR/status_cli" ]; then cli_state="done"; else cli_state="running"; fi
        printf '  \xe2\x8f\xb1  still running — %dm%02ds elapsed (Core: %s, CLI: %s)\n' \
            "$mm" "$ss" "$core_state" "$cli_state"
    done
}

trap cleanup_temp_files EXIT
trap '_handle_worker_signal TERM 143' TERM
trap '_handle_worker_signal INT 130' INT
trap '_handle_worker_signal HUP 129' HUP

cleanup_scoped_containers() {
    local compose_project="$1"
    local container_prefix="$2"
    local container_ids

    container_ids="$(docker ps -aq --filter "label=com.docker.compose.project=$compose_project" 2>/dev/null || true)"
    if [ -n "$container_ids" ]; then
        printf '%s\n' "$container_ids" | xargs -r docker rm -f 2>/dev/null || true
    fi
    container_ids="$(docker ps -aq --filter "name=$container_prefix" 2>/dev/null || true)"
    if [ -n "$container_ids" ]; then
        printf '%s\n' "$container_ids" | xargs -r docker rm -f 2>/dev/null || true
    fi
}

run_e2e_lane() {
    local lane="$1"
    local lane_label
    local lane_pythonpath
    local lane_tests
    local lane_rootdir
    local lane_prefix_base
    local lane_compose_base
    local lane_container_prefix
    local lane_compose_project
    local lane_app_port
    local lane_cleanup_done=false
    local lane_tests_passed=false
    local -a pytest_cmd

    if [ "$lane" = "core" ]; then
        lane_label="Core"
        lane_pythonpath="$CORE_DIR:$CORE_DIR/src"
        lane_tests="$CORE_DIR/tests/"
        lane_rootdir="$CORE_DIR"
    else
        lane_label="CLI"
        lane_pythonpath="$CLI_DIR:$CLI_DIR/src"
        lane_tests="$CLI_DIR/tests/"
        lane_rootdir="$CLI_DIR"
    fi

    # Every lane gets its own Compose project, container-name prefix, and host
    # port.  In serial mode an explicitly requested port remains unchanged;
    # in concurrent mode it is reserved for Core and CLI receives a free port.
    lane_prefix_base="$(sanitize_scope "${QS_E2E_CONTAINER_PREFIX:-qs-e2e}-${lane}")"
    lane_prefix_base="${lane_prefix_base:0:35}"
    lane_container_prefix="$(sanitize_scope "${lane_prefix_base}-${BASHPID}")"
    lane_container_prefix="${lane_container_prefix:0:50}"
    lane_compose_base="$(sanitize_scope "${QS_E2E_COMPOSE_PROJECT_NAME:-$lane_prefix_base}")"
    lane_compose_base="${lane_compose_base:0:35}"
    lane_compose_project="$(sanitize_scope "${lane_compose_base}-${BASHPID}")"
    lane_compose_project="${lane_compose_project:0:50}"

    if [ -n "${QS_E2E_APP_PORT:-}" ] && { [ "$E2E_PARALLEL" = false ] || [ "$lane" = "core" ]; }; then
        lane_app_port="$QS_E2E_APP_PORT"
    else
        lane_app_port="$(find_free_port)"
    fi

    export QS_E2E_LANE="$lane"
    export QS_E2E_CONTAINER_PREFIX="$lane_container_prefix"
    export QS_E2E_COMPOSE_PROJECT_NAME="$lane_compose_project"
    export QS_E2E_APP_PORT="$lane_app_port"
    export COMPOSE_PROJECT_NAME="$lane_compose_project"

    cleanup_lane() {
        if [ "$lane_cleanup_done" = true ]; then
            return
        fi
        lane_cleanup_done=true
        if [ "$CLEANUP" = true ]; then
            echo -e "\n${YELLOW}[$lane_label] Cleaning up Docker containers (pytest-docker handles this)...${NC}"
            (cd "$CORE_DIR/tests" && docker compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true)
            cleanup_scoped_containers "$lane_compose_project" "$lane_container_prefix"
            echo -e "${GREEN}[$lane_label] ✓ Cleanup complete${NC}"
        else
            echo -e "\n${YELLOW}[$lane_label] Skipping cleanup (--no-cleanup specified)${NC}"
            echo -e "${BLUE}[$lane_label] To manually cleanup this lane, run:${NC}"
            echo "  docker ps -aq --filter label=com.docker.compose.project=$lane_compose_project | xargs -r docker rm -f"
            echo "  docker ps -aq --filter name=$lane_container_prefix | xargs -r docker rm -f"
        fi
    }

    trap 'cleanup_lane; exit 143' TERM
    trap 'cleanup_lane; exit 130' INT
    trap 'cleanup_lane; exit 129' HUP

    echo -e "${BLUE}[$lane_label] Lane: $QS_E2E_LANE${NC}"
    echo "[$lane_label] App host port: $QS_E2E_APP_PORT"
    echo "[$lane_label] Docker scope: $QS_E2E_COMPOSE_PROJECT_NAME"
    echo ""

    echo -e "${BLUE}[$lane_label] Cleaning up any orphaned test containers...${NC}"
    cleanup_scoped_containers "$lane_compose_project" "$lane_container_prefix"
    echo -e "${GREEN}[$lane_label] ✓ Pre-cleanup complete${NC}"
    echo ""

    echo -e "${BLUE}[$lane_label] Running $lane_label E2E tests...${NC}"
    echo -e "${YELLOW}[$lane_label] pytest-docker will automatically start PostgreSQL${NC}"
    echo ""

    pytest_cmd=(poetry run pytest "$lane_tests" -m e2e "--rootdir=$lane_rootdir" -o addopts= --tb=long -ra)
    if [ "$SHOW_FULL_OUTPUT" = false ]; then
        pytest_cmd+=(-q)
    fi
    if [ "$lane" = "core" ] && [ -n "$HEADED" ]; then
        pytest_cmd+=("$HEADED")
    fi
    if [ "${#PYTEST_ARGS[@]}" -gt 0 ]; then
        pytest_cmd+=("${PYTEST_ARGS[@]}")
    fi

    printf '%s' "[$lane_label] Command: PYTHONPATH=$lane_pythonpath"
    printf ' %q' "${pytest_cmd[@]}"
    printf '\n\n'

    lane_tests_passed=false
    if PYTHONPATH="$lane_pythonpath" "${pytest_cmd[@]}"; then
        echo -e "${GREEN}[$lane_label] ✓ $lane_label E2E tests passed${NC}"
        lane_tests_passed=true
    else
        echo -e "${RED}[$lane_label] ✗ $lane_label E2E tests failed${NC}"
    fi

    echo ""
    if [ "$lane_tests_passed" = true ]; then
        cleanup_lane
        return 0
    fi
    cleanup_lane
    return 1
}

launch_lane() {
    local lane="$1"
    local log_file="${2:-}"
    local status_file="$WORKER_TEMP_DIR/status_$lane"

    if [ -n "$log_file" ]; then
        (
            set +e
            run_e2e_lane "$lane"
            lane_status=$?
            printf '%s\n' "$lane_status" > "$status_file"
            exit "$lane_status"
        ) > "$log_file" 2>&1 &
    else
        (
            set +e
            run_e2e_lane "$lane"
            lane_status=$?
            printf '%s\n' "$lane_status" > "$status_file"
            exit "$lane_status"
        ) &
    fi
    WORKER_PIDS+=("$!")
}

read_lane_status() {
    local lane="$1"
    local status_file="$WORKER_TEMP_DIR/status_$lane"
    if [ -f "$status_file" ]; then
        read -r status < "$status_file"
        printf '%s' "$status"
    else
        printf '1'
    fi
}

run_lanes_serial() {
    local lane
    local lane_status
    local failed=false

    for lane in core cli; do
        WORKER_PIDS=()
        WORKER_ORDER=("$lane")
        launch_lane "$lane"
        if ! _qs_join_workers; then
            failed=true
        fi
        lane_status="$(read_lane_status "$lane")"
        if [ "$lane_status" -ne 0 ]; then
            failed=true
        fi
        WORKER_PIDS=()
    done

    [ "$failed" = false ]
}

run_lanes_parallel() {
    local lane_status
    local failed=false

    WORKER_PIDS=()
    WORKER_ORDER=(core cli)
    launch_lane core "$WORKER_TEMP_DIR/log_core"
    launch_lane cli "$WORKER_TEMP_DIR/log_cli"

    if ! _qs_join_workers; then
        failed=true
    fi

    # Replay complete lane logs only after both workers have joined.  This
    # keeps output deterministic even though the actual tests run concurrently.
    _qs_replay_worker_logs "$WORKER_TEMP_DIR"
    for lane in core cli; do
        lane_status="$(read_lane_status "$lane")"
        if [ "$lane_status" -ne 0 ]; then
            failed=true
        fi
    done
    WORKER_PIDS=()

    [ "$failed" = false ]
}

echo -e "${BLUE}[1/4] Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

echo -e "${BLUE}[2/4] Installing Playwright browsers...${NC}"
echo -e "${YELLOW}Note: This may prompt for sudo password to install system dependencies${NC}"
if ! poetry run playwright install chromium; then
    echo -e "${YELLOW}Warning: Playwright browser installation had issues${NC}"
    echo "Continuing anyway..."
fi
echo -e "${GREEN}✓ Playwright browsers ready${NC}"
echo ""

echo -e "${BLUE}[3/4] Running Core and CLI E2E lanes...${NC}"
if [ "$E2E_PARALLEL" = true ]; then
    # Concurrent lanes buffer their output and replay it only after both join,
    # so without a ticker this phase prints nothing for several minutes.
    echo "  (lane output is buffered and replayed below once both lanes finish)"
    _e2e_heartbeat &
    HEARTBEAT_PID=$!
    run_lanes_parallel || LANES_FAILED=true
    stop_heartbeat
else
    # Serial lanes stream their output live, so progress is already visible and
    # no heartbeat is needed.
    run_lanes_serial || LANES_FAILED=true
fi

echo ""
if [ "${LANES_FAILED:-false}" = true ]; then
    echo "E2E failure attribution:"
    suspected_oom=false
    for lane in core cli; do
        lane_status="$(read_lane_status "$lane")"
        if [ "$lane_status" -ne 0 ]; then
            if [ "$lane" = "core" ]; then
                lane_label="Core"
            else
                lane_label="CLI"
            fi
            echo "  ✗ $lane_label E2E tests (exit $lane_status)"
            # 143 = 128+SIGTERM (oomd's default action), 137 = 128+SIGKILL
            # (kernel OOM killer). Either strongly implies the OS reaped the
            # lane under memory pressure rather than a genuine test failure.
            if [ "$lane_status" -eq 143 ] || [ "$lane_status" -eq 137 ]; then
                suspected_oom=true
            fi
        fi
    done
    echo ""
    if [ "$suspected_oom" = true ]; then
        echo -e "${YELLOW}⚠ A lane exited on SIGTERM/SIGKILL (143/137) — this usually means the OS${NC}"
        echo -e "${YELLOW}  killed the run under memory pressure, not a real test failure.${NC}"
        if command -v systemctl >/dev/null 2>&1 && \
           [ "$(systemctl is-active systemd-oomd 2>/dev/null)" = "active" ]; then
            echo    "  systemd-oomd is active on this host and is the likely reaper."
        fi
        echo    "  Retry with QS_E2E_PARALLEL=0 (serial lanes) or free memory/swap first."
        echo ""
    fi
fi
echo -e "${BLUE}[4/4] Final E2E results${NC}"
if [ "${LANES_FAILED:-false}" != true ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✓ All E2E Tests Passed!              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    exit 0
fi

echo -e "${RED}╔════════════════════════════════════════╗${NC}"
echo -e "${RED}║   ✗ E2E Tests Failed                   ║${NC}"
echo -e "${RED}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Debugging tips:${NC}"
echo "  • Run with --headed to see browser actions (Core tests)"
echo "  • Run with --full for detailed output"
echo "  • Run with --no-cleanup to inspect containers"
echo "  • Check screenshots in failed test output"
echo "  • Ensure Docker is running and accessible"
exit 1
