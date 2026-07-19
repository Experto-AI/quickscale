#!/usr/bin/env bash
# QS_INTEGRATION_JOBS validation helper (SA91).
#
# Source this script to use qs_validate_jobs() and _kill_descendants().
# These are shared between test_integration.sh and the harness test suite.

# ---------------------------------------------------------------------------
# qs_validate_jobs  — parse, validate, and cap QS_INTEGRATION_JOBS
#
# Usage: qs_validate_jobs <raw_value> [max_workers]
#   raw_value   the env var value (empty string is treated as 0 / unlimited)
#   max_workers   optional upper bound; positive values exceeding it are
#                 capped silently (caller is expected to log the cap).
# Returns: validated non-negative integer via stdout, or exits 1 on error.
#
# Rules:
#   - Unset / empty / 0 → 0 (unlimited)
#   - Must be decimal digits only, no sign prefix
#   - No leading zeros (except the single digit "0")
#   - Must not exceed bash signed-64-bit integer range for arithmetic safety
#   - An explicit huge value (>= 2^63) is rejected as overflow
# ---------------------------------------------------------------------------
qs_validate_jobs() {
    local raw_value="$1"
    local max_workers="${2:-}"
    local value

    # Default unset/empty/0 → 0
    if [[ -z "${raw_value:-}" || "$raw_value" == "0" ]]; then
        printf '0'
        return 0
    fi

    value="$raw_value"

    # Reject non-digit characters (no sign, no leading whitespace, no decimals)
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        echo "Error: QS_INTEGRATION_JOBS must be a non-negative integer, got: '${raw_value}'" >&2
        return 1
    fi

    # Reject leading zeros (e.g. "01", "007") — the bare digit "0" is already
    # handled above, so any match here means a multi-digit value starting with 0.
    if [[ "$value" =~ ^0.+$ ]]; then
        echo "Error: QS_INTEGRATION_JOBS must not have leading zeros, got: '${raw_value}'" >&2
        return 1
    fi

    # Reject values that exceed bash's full signed-64-bit range using a
    # lexical (string-length) check before any arithmetic context.
    # Max safe value:  9223372036854775807 (19 digits)
    # Values >= 2^63 overflow when bash interprets them as signed 64-bit.
    # String-length check: any 20+-digit value is definitely overflow;
    # a 19-digit value must be lexically <= the max sentinel.
    # This runs before any arithmetic comparison so that absurdly large
    # digit strings are rejected deterministically rather than depending
    # on signed-integer overflow behavior in bash.
    if [ "${#value}" -gt 19 ] || { [ "${#value}" -eq 19 ] && [ "$value" \> "9223372036854775807" ]; }; then
        echo "Error: QS_INTEGRATION_JOBS value overflows signed 64-bit integer, got: '${value}'" >&2
        return 1
    fi

    # Validate that the value is non-negative in a safe arithmetic context.
    # At this point we know 0 <= value <= 9223372036854775807, which is
    # guaranteed safe for signed-64-bit arithmetic.
    if [[ "$value" -lt 0 ]] 2>/dev/null; then
        echo "Error: QS_INTEGRATION_JOBS value must not be negative, got: '$value'" >&2
        return 1
    fi

    # Cap positive values at max_workers when provided
    if [ -n "$max_workers" ] && [ "$value" -gt "$max_workers" ] 2>/dev/null; then
        printf '%s' "$max_workers"
        return 0
    fi

    printf '%s' "$value"
}

# ---------------------------------------------------------------------------
# Worker-pool helpers — shared between test_integration.sh and the harness
# test suite.  These narrow functions encapsulate the reusable scheduling
# logic so tests exercise production code rather than copied snippets.
# ---------------------------------------------------------------------------

# _qs_build_worker_order  — populate WORKER_ORDER from a module directory
#
# Usage: _qs_build_worker_order <modules_dir>
#   modules_dir  path to the quickscale_modules directory
# Sets global array WORKER_ORDER to sorted directory names that have tests/
_qs_build_worker_order() {
    local modules_dir="$1"
    WORKER_ORDER=()
    for mod in "$modules_dir"/*; do
        if [ -d "$mod" ]; then
            local mod_name
            mod_name=$(basename "$mod")
            if [ -d "$mod/tests" ]; then
                WORKER_ORDER+=("$mod_name")
            fi
        fi
    done
}

# _qs_enforce_worker_bound  — wait for the oldest worker when at concurrency
#                             limit
#
# Usage: _qs_enforce_worker_bound <qs_jobs>
#   qs_jobs  the concurrency limit (0 = unlimited)
# Uses globals: WORKER_PIDS, WORKER_NAMES (may remove oldest entry)
# Returns: exit status of wait (0 on success, non-zero if worker failed)
_qs_enforce_worker_bound() {
    local qs_jobs="$1"
    local ret=0
    if [ "$qs_jobs" -gt 0 ] && [ "${#WORKER_PIDS[@]}" -ge "$qs_jobs" ] 2>/dev/null; then
        wait "${WORKER_PIDS[0]}" 2>/dev/null || ret=$?
        WORKER_PIDS=("${WORKER_PIDS[@]:1}")
        WORKER_NAMES=("${WORKER_NAMES[@]:1}")
    fi
    return "$ret"
}

# _qs_cap_at_eligible  — cap QS_JOBS at the eligible-worker count
#
# Usage: _qs_cap_at_eligible <eligible_count>
#   eligible_count  number of eligible workers
# Modifies global QS_JOBS when a cap is needed; logs the cap to stderr.
_qs_cap_at_eligible() {
    local eligible_count="$1"
    if [ "$QS_JOBS" -gt 0 ] && [ "$QS_JOBS" -gt "$eligible_count" ] 2>/dev/null; then
        echo "  → QS_INTEGRATION_JOBS=$QS_JOBS capped to eligible module count ($eligible_count)" >&2
        QS_JOBS=$eligible_count
    fi
}

# _qs_merge_worker_results  — concatenate per-worker coverage results in
#                             discovery order
#
# Usage: _qs_merge_worker_results <work_dir> <output_file>
#   work_dir     temp directory with per-worker results_<mod_name> files
#   output_file  path to write merged results
# Uses global: WORKER_ORDER array
_qs_merge_worker_results() {
    local work_dir="$1"
    local output_file="$2"
    : > "$output_file"
    for mod_name in "${WORKER_ORDER[@]}"; do
        local worker_results="$work_dir/results_${mod_name}"
        if [ -f "$worker_results" ]; then
            cat "$worker_results" >> "$output_file"
        fi
    done
}

# _qs_replay_worker_logs  — replay worker stdout/stderr in discovery order
#
# Usage: _qs_replay_worker_logs <work_dir>
#   work_dir  temp directory with per-worker log_<mod_name> files
# Uses global: WORKER_ORDER array
_qs_replay_worker_logs() {
    local work_dir="$1"
    for mod_name in "${WORKER_ORDER[@]}"; do
        local worker_log="$work_dir/log_${mod_name}"
        if [ -f "$worker_log" ]; then
            cat "$worker_log"
        fi
    done
}

# _qs_join_workers  — wait for remaining workers and return failure status
#
# Usage: _qs_join_workers
# Uses globals: WORKER_PIDS, WORKER_WAIT_PID
# Returns 0 if all workers exited successfully, 1 if any failed.
_qs_join_workers() {
    local exit_code=0
    local worker_pid

    # Remove each PID from the pending set before waiting for it.  The PID
    # being waited on is tracked separately so a signal handler can still
    # terminate an active join without retaining a reaped PID that could be
    # recycled for an unrelated process.
    WORKER_WAIT_PID=""
    while [ "${#WORKER_PIDS[@]}" -gt 0 ]; do
        worker_pid="${WORKER_PIDS[0]}"
        WORKER_PIDS=("${WORKER_PIDS[@]:1}")
        WORKER_WAIT_PID="$worker_pid"
        wait "$worker_pid" 2>/dev/null || exit_code=1
        WORKER_WAIT_PID=""
    done

    return "$exit_code"
}

# ---------------------------------------------------------------------------
# _kill_descendants  — terminate a process and all its descendants
#
# Usage: _kill_descendants <pid> [signal_name]
#   pid     the root process whose tree to terminate
#   signal  signal name/number (default TERM)
#
# Walks the process tree breadth-first from the given PID and sends the
# signal to every descendant, then to the PID itself.  Silently ignores
# nonexistent PIDs and processes that vanish during traversal.
# ---------------------------------------------------------------------------
_kill_descendants() {
    local pid="$1"
    local signal="${2:-TERM}"

    local children
    children=$(pgrep -P "$pid" 2>/dev/null || true)
    if [ -n "$children" ]; then
        # Iterate over each child line to handle multi-line pgrep output
        # when a parent has multiple children.  Without iteration, word-
        # splitting would pass extra PIDs as positional arguments and
        # only the first would be traversed.
        while IFS= read -r child; do
            [ -n "$child" ] && _kill_descendants "$child" "$signal"
        done <<< "$children"
    fi
    kill "-$signal" "$pid" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# _handle_worker_signal  — INT/TERM/HUP handler for the worker-pool loop
#
# Usage: trap '_handle_worker_signal TERM 143' TERM
#
# Kills all tracked worker subprocess trees, waits for reaping, runs temp
# cleanup, then exits with the signal-derived code.
# ---------------------------------------------------------------------------
_qs_worker_pid_is_active() {
    local pid="$1"
    local active_pid

    while read -r active_pid; do
        if [ "$active_pid" = "$pid" ]; then
            return 0
        fi
    done < <(jobs -pr)
    return 1
}

_qs_worker_pid_is_owned() {
    local pid="$1"
    local owned_pid

    while read -r owned_pid; do
        if [ "$owned_pid" = "$pid" ]; then
            return 0
        fi
    done < <(jobs -p)
    return 1
}

_handle_worker_signal() {
    local signal_name="$1"
    local exit_code="$2"
    local pid
    local wait_pid="${WORKER_WAIT_PID:-}"

    echo ""
    echo "⚠ Received SIG${signal_name}, terminating worker subprocesses..." >&2
    for pid in "${WORKER_PIDS[@]:-}"; do
        if [ -n "$pid" ] && _qs_worker_pid_is_active "$pid"; then
            _kill_descendants "$pid" "$signal_name"
        fi
    done
    if [ -n "$wait_pid" ] && _qs_worker_pid_is_active "$wait_pid"; then
        _kill_descendants "$wait_pid" "$signal_name"
    fi
    # Reap only jobs still owned by this shell.  A PID that has already been
    # reaped must not be waited on or signalled after a possible PID recycle.
    for pid in "${WORKER_PIDS[@]:-}"; do
        if [ -n "$pid" ] && _qs_worker_pid_is_owned "$pid"; then
            wait "$pid" 2>/dev/null || true
        fi
    done
    if [ -n "$wait_pid" ] && _qs_worker_pid_is_owned "$wait_pid"; then
        wait "$wait_pid" 2>/dev/null || true
    fi
    WORKER_WAIT_PID=""
    WORKER_PIDS=()
    cleanup_temp_files
    exit "$exit_code"
}
