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
#   --cleanup-scope S Clean only the exact labelled Docker scope S
#   --full            Show full pytest output (per-file lines)
#   --verbose         Alias for --full
#   --help            Show this help message
#
# Environment:
#   QS_E2E_PARALLEL=0          Run Core and CLI lanes serially (default: concurrent)
#   QS_E2E_XDIST_WORKERS=N     pytest-xdist workers per lane (default: heuristic; 0/1 = serial)
#   QS_E2E_NO_MEMORY_GUARD=1   Skip the low-memory preflight (preserve lane/worker settings)
#   QS_E2E_MIN_AVAIL_MB=N      Fall back to serial below N MB available RAM (default: 4096)
#   QS_E2E_COMFORT_AVAIL_MB=N  At/above N MB available RAM, ignore free swap entirely (default: 8192)
#   QS_E2E_MIN_SWAP_MB=N       Fall back to serial below N MB free swap, checked only
#                              when available RAM is under QS_E2E_COMFORT_AVAIL_MB (default: 3072)
#   QS_E2E_HEARTBEAT_INTERVAL=N  Seconds between "still running" progress lines (default: 60)
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
CLEANUP_SCOPE=""
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
        --cleanup-scope)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo "Error: --cleanup-scope requires a Docker-safe scope" >&2
                exit 2
            fi
            CLEANUP_SCOPE="$2"
            shift 2
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
            echo "  --cleanup-scope S Clean only the exact labelled Docker scope S"
            echo "  --full            Show full pytest output (per-file lines)"
            echo "  --verbose, -v     Alias for --full"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment:"
            echo "  QS_E2E_PARALLEL=0            Run Core and CLI lanes serially"
            echo "  QS_E2E_XDIST_WORKERS=N       pytest-xdist workers per lane (default: heuristic; 0/1 = serial)"
            echo "  QS_E2E_NO_MEMORY_GUARD=1     Skip the low-memory preflight"
            echo "  QS_E2E_MIN_AVAIL_MB=N        Serial fallback below N MB available RAM (default 4096)"
            echo "  QS_E2E_COMFORT_AVAIL_MB=N    Ignore free swap at/above N MB available RAM (default 8192)"
            echo "  QS_E2E_MIN_SWAP_MB=N         Serial fallback below N MB free swap, only when"
            echo "                               available RAM is under the comfort threshold (default 3072)"
            echo "  QS_E2E_HEARTBEAT_INTERVAL=N  Seconds between progress lines (default 60)"
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
    SERIAL_CAUSE="QS_E2E_PARALLEL=0"
else
    E2E_PARALLEL=true
    SERIAL_CAUSE=""
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

# _meminfo_kb  — read a /proc/meminfo field (KB) by name; prints 0 if absent.
_meminfo_kb() {
    local field="$1"
    awk -v f="$field:" '$1 == f { print $2; found = 1 } END { if (!found) print 0 }' \
        /proc/meminfo 2>/dev/null
}

# _require_mb  — abort unless a threshold override is a whole number of MB.
#
# A non-numeric threshold would make every `[ x -lt $threshold ]` below fail
# with "integer expression expected" and evaluate as false, silently disabling
# the very guard the operator was trying to tune.  Fail loudly instead.
#
# Called directly rather than via $(...) so the `exit` aborts the script rather
# than just a command-substitution subshell.
_require_mb() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: $name must be a whole number of MB (got '$value')${NC}" >&2
        exit 1
    fi
}

# Preflight memory guard.  Concurrent lanes launch two Docker + Playwright
# stacks at once; on a memory-tight host that peak can drive the session into
# swap thrash and get the run reaped by systemd-oomd (surfaces as a SIGTERM
# mid-run, not a test failure).  When resting headroom is already low we fall
# back to serial lanes, which roughly halves peak memory.  Thresholds are
# overridable; QS_E2E_NO_MEMORY_GUARD=1 disables the guard entirely.
#
# Low SwapFree on its own is not a fallback reason.  A desktop with plenty of
# RAM routinely accumulates gigabytes of swapped-out idle browser/editor pages
# (vm.swappiness evicts cold anonymous memory even when RAM is abundant), and
# those pages never come back on their own.  Swap only matters as a secondary
# cushion when RAM headroom is already mediocre, so the swap check is gated on
# MemAvailable sitting below the comfort threshold.
#   QS_E2E_MIN_AVAIL_MB     hard floor on MemAvailable before fallback (default 4096)
#   QS_E2E_COMFORT_AVAIL_MB MemAvailable at/above which swap is ignored (default 8192)
#   QS_E2E_MIN_SWAP_MB      minimum SwapFree, checked only below comfort (default 3072)
memory_preflight_guard() {
    [ "${QS_E2E_NO_MEMORY_GUARD:-0}" = "1" ] && return 0
    [ "$E2E_PARALLEL" = true ] || return 0
    [ -r /proc/meminfo ] || return 0

    local avail_mb swap_total_mb swap_free_mb reason=""
    local min_avail_mb comfort_avail_mb min_swap_mb
    avail_mb=$(( $(_meminfo_kb MemAvailable) / 1024 ))
    swap_total_mb=$(( $(_meminfo_kb SwapTotal) / 1024 ))
    swap_free_mb=$(( $(_meminfo_kb SwapFree) / 1024 ))
    min_avail_mb="${QS_E2E_MIN_AVAIL_MB:-4096}"
    comfort_avail_mb="${QS_E2E_COMFORT_AVAIL_MB:-8192}"
    min_swap_mb="${QS_E2E_MIN_SWAP_MB:-3072}"
    _require_mb QS_E2E_MIN_AVAIL_MB "$min_avail_mb"
    _require_mb QS_E2E_COMFORT_AVAIL_MB "$comfort_avail_mb"
    _require_mb QS_E2E_MIN_SWAP_MB "$min_swap_mb"

    # Comfort must never sit below the hard floor, or the swap check would
    # apply to a window that cannot exist.
    if [ "$comfort_avail_mb" -lt "$min_avail_mb" ]; then
        comfort_avail_mb="$min_avail_mb"
    fi

    if [ "$avail_mb" -lt "$min_avail_mb" ]; then
        reason="available RAM ${avail_mb}MB < ${min_avail_mb}MB"
    elif [ "$avail_mb" -lt "$comfort_avail_mb" ] \
        && [ "$swap_total_mb" -gt 0 ] \
        && [ "$swap_free_mb" -lt "$min_swap_mb" ]; then
        reason="available RAM ${avail_mb}MB < ${comfort_avail_mb}MB and free swap ${swap_free_mb}MB < ${min_swap_mb}MB"
    fi

    if [ -n "$reason" ]; then
        E2E_PARALLEL=false
        E2E_XDIST_WORKERS=1
        SERIAL_CAUSE="low-memory guard: $reason"
        echo -e "${YELLOW}⚠ Low memory headroom ($reason).${NC}" >&2
        echo -e "${YELLOW}  Falling back to serial lanes; pytest will run serially in each lane to avoid an out-of-memory kill (systemd-oomd).${NC}" >&2
        echo    "  Override with QS_E2E_NO_MEMORY_GUARD=1 to force concurrent lanes anyway." >&2
        echo "" >&2
    fi
}

memory_preflight_guard

# Provenance banner.  `make ci-e2e` can run for hours, and it is routinely
# launched from a git worktree pinned to an older commit while fixes land on
# the integration branch in a sibling tree.  A run that began before a fix
# existed will never pick it up — bash executes the script text it was started
# with.  Printing the checkout, HEAD, and how far behind the integration branch
# it is makes such a run self-evidently out of date in its own log, instead
# of something reconstructed later by comparing message wording to source.
#
# Deliberately worded "out of date", never "stale": in this project "stale"
# means a wedged/stuck lane (see the heartbeat's quiet-time reporting), which
# is an unrelated condition.  Conflating the two has already misdirected one
# diagnosis.
#   QS_E2E_INTEGRATION_REF  ref to measure out-of-dateness against (default v87)
print_provenance() {
    local head_sha dirty="" behind="" integration_ref
    integration_ref="${QS_E2E_INTEGRATION_REF:-v87}"

    if ! git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
        echo "Checkout: $PROJECT_ROOT (not a git checkout)"
        return 0
    fi

    head_sha="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    # Compare against HEAD, not the index: `git diff --quiet` alone ignores
    # staged-but-uncommitted edits, which are exactly as absent from a running
    # script as unstaged ones.
    git -C "$PROJECT_ROOT" diff --quiet HEAD 2>/dev/null || dirty=" +local-changes"

    echo "Checkout: $PROJECT_ROOT"
    if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$integration_ref" >/dev/null 2>&1; then
        behind="$(git -C "$PROJECT_ROOT" rev-list --count "HEAD..$integration_ref" 2>/dev/null || echo 0)"
        if [ "${behind:-0}" -gt 0 ]; then
            echo -e "Script rev: ${head_sha}${dirty} ${YELLOW}(OUT OF DATE — $behind commit(s) behind $integration_ref)${NC}"
            echo -e "${YELLOW}  This run uses the script as of ${head_sha}; anything fixed on $integration_ref since then is NOT in effect.${NC}"
            echo -e "${YELLOW}  Sync with: git -C $PROJECT_ROOT merge $integration_ref${NC}"
        else
            echo "Script rev: ${head_sha}${dirty} (up to date with $integration_ref)"
        fi
    else
        echo "Script rev: ${head_sha}${dirty}"
    fi
}

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   QuickScale E2E Test Runner           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo "Started: $(date '+%F %T %Z')"
print_provenance
if [ "$SHOW_FULL_OUTPUT" = true ]; then
    echo "Output mode: full"
else
    echo "Output mode: dots"
fi
if [ "$E2E_PARALLEL" = true ]; then
    echo "Lane mode: concurrent (Core + CLI)"
else
    echo "Lane mode: serial (${SERIAL_CAUSE:-unknown cause})"
fi
if [ "${E2E_XDIST_WORKERS:-0}" -ge 2 ]; then
    echo "Xdist: ${E2E_XDIST_WORKERS} per lane (total $(( E2E_XDIST_WORKERS * 2 )) across 2 lanes)"
else
    echo "Xdist: serial"
fi
echo ""

# The parent owns only the worker logs. Containers are cleaned up by the lane
# that created them, so concurrent lanes never remove one another's services.
# Scope is deliberately empty until the temp allocation succeeds; signal/EXIT
# cleanup is armed below before Docker can be touched.
WORKER_TEMP_DIR=""
RUN_SCOPE=""
CORE_APP_PORT=""
CLI_APP_PORT=""
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

validate_scope() {
    local scope="$1"
    if [[ ! "$scope" =~ ^[a-z0-9][a-z0-9_-]{0,62}$ ]]; then
        echo -e "${RED}Error: Docker scope must be lowercase and Docker-safe${NC}" >&2
        return 1
    fi
}

label_filter_args() {
    local scope="$1"
    LABEL_FILTER_ARGS=(
        --filter "label=com.quickscale.owner=quickscale"
        --filter "label=com.quickscale.lifecycle=e2e"
        --filter "label=com.quickscale.scope=$scope"
    )
}

resource_ids() {
    local resource_type="$1" scope="$2"
    label_filter_args "$scope"
    case "$resource_type" in
        container) docker ps -aq "${LABEL_FILTER_ARGS[@]}" ;;
        volume) docker volume ls -q "${LABEL_FILTER_ARGS[@]}" ;;
        network) docker network ls -q "${LABEL_FILTER_ARGS[@]}" ;;
        image) docker image ls -aq "${LABEL_FILTER_ARGS[@]}" --filter dangling=false ;;
        *) echo "Unknown Docker resource type: $resource_type" >&2; return 2 ;;
    esac
}

inspect_resource_labels() {
    local resource_type="$1" resource_id="$2" scope="$3" output
    case "$resource_type" in
        container) output="$(docker container inspect --format '{{index .Config.Labels "com.quickscale.owner"}}|{{index .Config.Labels "com.quickscale.lifecycle"}}|{{index .Config.Labels "com.quickscale.scope"}}' "$resource_id")" ;;
        volume|network) output="$(docker "$resource_type" inspect --format '{{index .Labels "com.quickscale.owner"}}|{{index .Labels "com.quickscale.lifecycle"}}|{{index .Labels "com.quickscale.scope"}}' "$resource_id")" ;;
        image) output="$(docker image inspect --format '{{index .Config.Labels "com.quickscale.owner"}}|{{index .Config.Labels "com.quickscale.lifecycle"}}|{{index .Config.Labels "com.quickscale.scope"}}' "$resource_id")" ;;
        *) return 2 ;;
    esac
    [ "$output" = "quickscale|e2e|$scope" ]
}

cleanup_scoped_images() {
    local scope="$1" digest="${2:-}" image_ids image_id output
    # A missing digest means the stable image contract was not allocated by
    # this process.  It is safer to retain images than to guess.
    [ -n "$digest" ] || return 0
    image_ids="$(docker image ls -aq \
        --filter "label=com.quickscale.owner=quickscale" \
        --filter "label=com.quickscale.image-contract=sa142" \
        --filter "label=com.quickscale.image-digest=$digest" \
        --filter dangling=true 2>/dev/null)" || return 1
    for image_id in $image_ids; do
        output="$(docker image inspect --format '{{index .Config.Labels "com.quickscale.owner"}}|{{index .Config.Labels "com.quickscale.image-contract"}}|{{index .Config.Labels "com.quickscale.image-digest"}}|{{json .RepoTags}}' "$image_id")" || return 1
        # Tagged stable images are never removable, even if a daemon ignores
        # the dangling filter.  Any label mismatch fails closed.
        case "$output" in
            "quickscale|sa142|$digest|[]") docker image rm "$image_id" || return 1 ;;
            *) echo "Refusing image cleanup for mismatched or tagged image $image_id" >&2; return 1 ;;
        esac
    done
}

cleanup_scoped_resources() {
    local scope="$1" resource_type ids resource_id
    local -A cleanup_ids=()
    local -a ids_array=()
    validate_scope "$scope" || return 1
    for resource_type in container volume network image; do
        if ! ids="$(resource_ids "$resource_type" "$scope")"; then
            echo "Unable to enumerate labelled $resource_type resources for scope $scope" >&2
            return 1
        fi
        for resource_id in $ids; do
            if ! inspect_resource_labels "$resource_type" "$resource_id" "$scope"; then
                echo "Refusing cleanup: $resource_type $resource_id failed label reinspection" >&2
                return 1
            fi
        done
        cleanup_ids[$resource_type]="$ids"
    done

    # Deletion is fixed-argv and ordered so dependent resources disappear
    # before volumes and networks.  No Compose project/name selector is used.
    if [ -n "${cleanup_ids[container]:-}" ]; then
        mapfile -t ids_array <<< "${cleanup_ids[container]}"
        docker rm -f "${ids_array[@]}" || return 1
    fi
    if [ -n "${cleanup_ids[image]:-}" ]; then
        mapfile -t ids_array <<< "${cleanup_ids[image]}"
        docker image rm "${ids_array[@]}" || return 1
    fi
    if [ -n "${cleanup_ids[volume]:-}" ]; then
        mapfile -t ids_array <<< "${cleanup_ids[volume]}"
        docker volume rm -f "${ids_array[@]}" || return 1
    fi
    if [ -n "${cleanup_ids[network]:-}" ]; then
        mapfile -t ids_array <<< "${cleanup_ids[network]}"
        docker network rm "${ids_array[@]}" || return 1
    fi

    for resource_type in container volume network image; do
        if ! ids="$(resource_ids "$resource_type" "$scope")"; then
            return 1
        fi
        if [ -n "$ids" ]; then
            echo "Labelled $resource_type resources remain in scope $scope: $ids" >&2
            return 1
        fi
    done
}

# _fmt_duration  — humanize a second count for a run measured in hours.
#
# Pure (no state), so calling it via $(...) is safe.  Past an hour "125m00s" is
# hard to read at a glance, which matters because these ticks are the operator's
# only progress signal on a multi-hour run.
_fmt_duration() {
    local secs="$1"
    if [ "$secs" -ge 3600 ]; then
        printf '%dh%02dm' $(( secs / 3600 )) $(( (secs % 3600) / 60 ))
    else
        printf '%dm%02ds' $(( secs / 60 )) $(( secs % 60 ))
    fi
}

# _e2e_heartbeat  — emit a periodic "still running" line while lanes execute.
#
# The lane logs are buffered and only replayed after both lanes join, so the
# [3/4] phase would otherwise print nothing for several minutes.  This ticker
# reports elapsed time and per-lane state (a lane is "done" once it has written
# its status_<lane> file) without touching the buffered lane output, keeping the
# deterministic replay intact.  Interval is configurable via
# QS_E2E_HEARTBEAT_INTERVAL (seconds; default 60).
#
# A bare "running" tick cannot distinguish a lane making progress from one that
# has wedged — both look identical, which is useless for deciding whether to let
# a long run continue or abort it.  Each tick therefore reports how long the
# lane's buffered log has been silent: a lane whose log is still growing is
# working, while a lane silent for many minutes is the one to investigate.  A
# quiet stretch is not proof of a hang (a Docker image build or pnpm install is
# legitimately silent for minutes), so this reports the observation and leaves
# the judgement to the operator.
_e2e_heartbeat() {
    # Drop the inherited worker/cleanup traps: this ticker owns nothing, so a
    # kill from stop_heartbeat should end it immediately rather than run the
    # lane-cleanup signal handler or delete the shared temp dir.
    trap - INT TERM HUP EXIT
    local start now elapsed interval lane
    local -A last_size=() last_change=()
    start="$(date +%s)"
    interval="${QS_E2E_HEARTBEAT_INTERVAL:-60}"
    for lane in core cli; do
        last_size[$lane]=0
        last_change[$lane]="$start"
    done

    # _lane_report  — set LANE_STATE for one lane, updating its progress memo.
    # Assigns to a global rather than echoing, because the caller must invoke it
    # directly: inside $(...) the last_size/last_change updates would be made in
    # a subshell and lost, freezing every lane at "quiet" forever.
    _lane_report() {
        local lane="$1" now="$2" size quiet
        if [ -f "$WORKER_TEMP_DIR/status_$lane" ]; then
            LANE_STATE="done"
            return
        fi
        size="$(stat -c %s "$WORKER_TEMP_DIR/log_$lane" 2>/dev/null || echo 0)"
        if [ "$size" -ne "${last_size[$lane]}" ]; then
            last_size[$lane]="$size"
            last_change[$lane]="$now"
            LANE_STATE="running"
            return
        fi
        quiet=$(( now - last_change[$lane] ))
        if [ "$quiet" -lt 60 ]; then
            LANE_STATE="running"
        else
            LANE_STATE="running, quiet $(_fmt_duration "$quiet")"
        fi
    }

    local core_state cli_state
    while true; do
        sleep "$interval"
        now="$(date +%s)"
        elapsed=$(( now - start ))
        _lane_report core "$now"; core_state="$LANE_STATE"
        _lane_report cli  "$now"; cli_state="$LANE_STATE"
        printf '  \xe2\x8f\xb1  still running — %s elapsed (Core: %s | CLI: %s)\n' \
            "$(_fmt_duration "$elapsed")" "$core_state" "$cli_state"
    done
}

trap cleanup_temp_files EXIT
trap '_handle_worker_signal TERM 143' TERM
trap '_handle_worker_signal INT 130' INT
trap '_handle_worker_signal HUP 129' HUP

# Arm obligations before allocating the run scope.  The scope is frozen once
# from the unique temp directory and is never recomputed during cleanup.
WORKER_TEMP_DIR="$(mktemp -d)"
RUN_SCOPE="$(sanitize_scope "qs-e2e-${WORKER_TEMP_DIR##*/}")"
RUN_SCOPE="${RUN_SCOPE:0:63}"
validate_scope "$RUN_SCOPE"
export QS_E2E_RUN_SCOPE="$RUN_SCOPE"

# Allocate lane ports in the parent before concurrent workers are launched.
# Asking the kernel for a free port independently inside each worker can return
# the same just-released ephemeral port to both lanes, making otherwise
# isolated Compose projects contend for one host socket.
if [ -n "${QS_E2E_APP_PORT:-}" ]; then
    CORE_APP_PORT="$QS_E2E_APP_PORT"
else
    CORE_APP_PORT="$(find_free_port)"
fi
if [ "$E2E_PARALLEL" = false ] && [ -n "${QS_E2E_APP_PORT:-}" ]; then
    CLI_APP_PORT="$QS_E2E_APP_PORT"
else
    CLI_APP_PORT="$(find_free_port)"
    while [ "$CLI_APP_PORT" = "$CORE_APP_PORT" ]; do
        CLI_APP_PORT="$(find_free_port)"
    done
fi
validate_app_port "$CORE_APP_PORT"
validate_app_port "$CLI_APP_PORT"

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
    local lane_resource_scope
    local lane_pid
    local lane_app_port
    local lane_image_digest
    local lane_cleanup_done=false
    local lane_tests_passed=false
    local -a pytest_cmd

    if [ "$lane" = "core" ]; then
        lane_label="Core"
        lane_pythonpath="$PROJECT_ROOT:$CORE_DIR:$CORE_DIR/src"
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
    # Capture the lane shell PID before command substitution. BASHPID changes
    # inside each $(...), which previously minted different resource and Compose
    # suffixes while the log presented them as one Docker scope.
    lane_pid="$BASHPID"
    lane_prefix_base="$(sanitize_scope "${RUN_SCOPE}-${lane}")"
    lane_prefix_base="${lane_prefix_base:0:48}"
    lane_resource_scope="$(sanitize_scope "${lane_prefix_base}-${lane_pid}")"
    lane_resource_scope="${lane_resource_scope:0:63}"
    lane_container_prefix="$lane_resource_scope"
    lane_compose_base="$(sanitize_scope "${QS_E2E_COMPOSE_PROJECT_NAME:-$lane_prefix_base}")"
    lane_compose_base="${lane_compose_base:0:48}"
    lane_compose_project="$(sanitize_scope "${lane_compose_base}-${lane_pid}")"
    lane_compose_project="${lane_compose_project:0:63}"
    lane_image_digest="${QUICKSCALE_BACKEND_IMAGE_DIGEST:-}"

    if [ "$lane" = "core" ]; then
        lane_app_port="$CORE_APP_PORT"
    else
        lane_app_port="$CLI_APP_PORT"
    fi

    export QS_E2E_LANE="$lane"
    export QS_E2E_RUN_SCOPE="$RUN_SCOPE"
    export QS_E2E_RESOURCE_SCOPE="$lane_resource_scope"
    export QS_E2E_CONTAINER_PREFIX="$lane_container_prefix"
    export QS_E2E_COMPOSE_PROJECT_NAME="$lane_compose_project"
    export QS_E2E_LIFECYCLE="e2e"
    if [ "$CLEANUP" = true ]; then
        export QS_E2E_NO_CLEANUP=0
    else
        export QS_E2E_NO_CLEANUP=1
    fi
    export QUICKSCALE_RESOURCE_PREFIX="$lane_resource_scope"
    export QS_E2E_APP_PORT="$lane_app_port"
    export COMPOSE_PROJECT_NAME="$lane_compose_project"

    lane_exact_scopes() {
        local worker_index
        printf '%s\n' "$lane_resource_scope"
        if [ "${E2E_XDIST_WORKERS:-0}" -ge 2 ]; then
            for ((worker_index = 0; worker_index < E2E_XDIST_WORKERS; worker_index++)); do
                printf '%s-gw%s\n' "$lane_resource_scope" "$worker_index"
            done
        fi
    }

    cleanup_lane() {
        local exact_scope
        if [ "$lane_cleanup_done" = true ]; then
            return
        fi
        lane_cleanup_done=true
        if [ "$CLEANUP" = true ]; then
            echo -e "\n${YELLOW}[$lane_label] Cleaning up labelled Docker scopes rooted at $lane_resource_scope...${NC}"
            while IFS= read -r exact_scope; do
                cleanup_scoped_images "$exact_scope" "$lane_image_digest" || cleanup_status=$?
                cleanup_scoped_resources "$exact_scope" || cleanup_status=$?
            done < <(lane_exact_scopes)
            if [ "${cleanup_status:-0}" -ne 0 ]; then
                echo -e "${RED}[$lane_label] ✗ Cleanup failed for scopes rooted at $lane_resource_scope${NC}" >&2
                while IFS= read -r exact_scope; do
                    echo "[$lane_label] Cleanup command: $SCRIPT_DIR/test_e2e.sh --cleanup-scope $exact_scope" >&2
                done < <(lane_exact_scopes)
                return 1
            fi
            echo -e "${GREEN}[$lane_label] ✓ Cleanup complete${NC}"
        else
            echo -e "\n${YELLOW}[$lane_label] Skipping cleanup (--no-cleanup specified)${NC}"
            echo -e "${BLUE}[$lane_label] Diagnostic scopes:${NC}"
            while IFS= read -r exact_scope; do
                echo "  $exact_scope"
                echo "    docker ps -a --filter label=com.quickscale.owner=quickscale --filter label=com.quickscale.lifecycle=e2e --filter label=com.quickscale.scope=$exact_scope"
                echo "    $SCRIPT_DIR/test_e2e.sh --cleanup-scope $exact_scope"
            done < <(lane_exact_scopes)
        fi
    }

    trap 'cleanup_lane; exit 143' TERM
    trap 'cleanup_lane; exit 130' INT
    trap 'cleanup_lane; exit 129' HUP

    echo -e "${BLUE}[$lane_label] Lane: $QS_E2E_LANE${NC}"
    echo "[$lane_label] App host port: $QS_E2E_APP_PORT"
    echo "[$lane_label] Docker scope: $QS_E2E_RESOURCE_SCOPE"
    echo ""

    echo -e "${BLUE}[$lane_label] Cleaning up any orphaned test containers...${NC}"
    if [ "$CLEANUP" = true ]; then
        if ! cleanup_scoped_images "$lane_resource_scope" "$lane_image_digest" || \
            ! cleanup_scoped_resources "$lane_resource_scope"; then
            echo -e "${RED}[$lane_label] ✗ Pre-clean failed; pytest will not run${NC}" >&2
            lane_cleanup_done=true
            return 1
        fi
    fi
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
    if [ "$CLEANUP" = false ]; then
        # Diagnostics must stop at the first failing test so retained state
        # describes one failure rather than a later cascade.
        pytest_cmd+=(--maxfail=1)
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
        if cleanup_lane; then
            return 0
        fi
        echo -e "${RED}[$lane_label] ✗ Tests passed but cleanup failed${NC}" >&2
        return 1
    fi
    cleanup_lane || echo "[$lane_label] Cleanup failed after primary test failure; preserving test exit" >&2
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

if [ -n "$CLEANUP_SCOPE" ]; then
    validate_scope "$CLEANUP_SCOPE"
    echo -e "${BLUE}Cleaning labelled E2E resources in scope $CLEANUP_SCOPE${NC}"
    cleanup_scoped_resources "$CLEANUP_SCOPE"
    exit $?
fi

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
