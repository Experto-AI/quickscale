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
#   QS_E2E_PARALLEL=0              Run Core and CLI lanes serially (default: concurrent)
#   QS_E2E_XDIST_WORKERS=N         pytest-xdist workers per lane (default: heuristic; 0/1=serial)
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
            echo "  QS_E2E_PARALLEL=0              Run Core and CLI lanes serially"
            echo "  QS_E2E_XDIST_WORKERS=N         pytest-xdist workers per lane (default: heuristic; 0/1=serial)"
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

# Resolve QS_E2E_XDIST_WORKERS: non-negative integer, default via heuristic.
# Values 0 or 1 skip pytest-xdist flags; values >=2 append -n N --dist loadscope.
E2E_XDIST_WORKERS="${QS_E2E_XDIST_WORKERS:-}"
if [ -z "$E2E_XDIST_WORKERS" ]; then
    # Default: min(max(1,floor(nproc/2)), max(1,floor(MemAvailable_GiB/4)), 4)
    _NPROC_VAL=$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)
    _NPROC_VAL=${_NPROC_VAL:-1}
    _MEM_AVAIL_GB=$(awk '/MemAvailable/{printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
    _MEM_AVAIL_GB=${_MEM_AVAIL_GB:-0}
    _HALF_NPROC=$(( _NPROC_VAL / 2 ))
    [ "$_HALF_NPROC" -lt 1 ] && _HALF_NPROC=1
    _QUART_MEM=1
    if [ "$_MEM_AVAIL_GB" -ge 4 ]; then
        _QUART_MEM=$(( _MEM_AVAIL_GB / 4 ))
    fi
    _CANDIDATE=$_HALF_NPROC
    [ "$_QUART_MEM" -lt "$_CANDIDATE" ] && _CANDIDATE=$_QUART_MEM
    [ "$_CANDIDATE" -gt 4 ] && _CANDIDATE=4
    E2E_XDIST_WORKERS=$_CANDIDATE
fi
case "$E2E_XDIST_WORKERS" in
    *[!0-9]*)
        echo -e "${RED}Error: QS_E2E_XDIST_WORKERS must be a non-negative integer (got: $E2E_XDIST_WORKERS)${NC}" >&2
        exit 1
        ;;
esac

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
if [ "${E2E_XDIST_WORKERS:-0}" -ge 2 ]; then
    echo "Xdist: ${E2E_XDIST_WORKERS} per lane (total $(( E2E_XDIST_WORKERS * 2 )) across 2 lanes)"
else
    echo "Xdist: serial"
fi
echo ""

# The parent owns only the worker logs. Containers are cleaned up by the lane
# that created them, so concurrent lanes never remove one another's services.
WORKER_TEMP_DIR="$(mktemp -d)"
declare -a WORKER_PIDS=()
declare -a WORKER_ORDER=()

cleanup_temp_files() {
    if [ -n "${WORKER_TEMP_DIR:-}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
        rm -rf "$WORKER_TEMP_DIR"
    fi
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
    if [ "${E2E_XDIST_WORKERS:-0}" -ge 2 ]; then
        pytest_cmd+=(-n "$E2E_XDIST_WORKERS" --dist loadscope)
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
    run_lanes_parallel || LANES_FAILED=true
else
    run_lanes_serial || LANES_FAILED=true
fi

echo ""
if [ "${LANES_FAILED:-false}" = true ]; then
    echo "E2E failure attribution:"
    for lane in core cli; do
        lane_status="$(read_lane_status "$lane")"
        if [ "$lane_status" -ne 0 ]; then
            if [ "$lane" = "core" ]; then
                lane_label="Core"
            else
                lane_label="CLI"
            fi
            echo "  ✗ $lane_label E2E tests (exit $lane_status)"
        fi
    done
    echo ""
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
