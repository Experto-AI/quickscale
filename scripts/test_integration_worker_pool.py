"""
Focused tests for the SA91 parallel-worker-pool.

Tests ``qs_validate_jobs()``, ``_kill_descendants()``, and the worker-pool
helpers (``_qs_build_worker_order``, ``_qs_enforce_worker_bound``,
``_qs_merge_worker_results``, ``_qs_replay_worker_logs``) from the shared
helper script ``_qs_jobs.sh``.  All tests exercise production code — no
copied snippets.

Test matrix
-----------
*qs_validate_jobs()* — unset -> 0, "0" -> 0, "1" -> 1, "5" -> 5, malformed
  (non-numeric) -> error, leading zeros -> error, overflow -> error, capping
  at eligible worker count.

*Lexical overflow rejection* — max-safe value accepted; max+1, 2^64, and
  much longer digit strings rejected by string-length check before any
  arithmetic context.

*Worker-pool helpers* — order building, bound enforcement, result merge,
  output replay all exercise the production functions in ``_qs_jobs.sh``.
  Max-active-workers respects the concurrency limit; failure propagation
  and deterministic replay/merge order are verified.

*Process-tree management* — ``_kill_descendants`` terminates single-child,
  multi-child, and multi-level branched trees; handles nonexistent PIDs;
  exact exit codes for TERM/INT/HUP signal handlers.

These tests are fast, self-contained, and do not require PostgreSQL.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_QS_JOBS_HELPER = os.path.join(os.path.dirname(__file__), "_qs_jobs.sh")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bash(script: str, **kwargs) -> subprocess.CompletedProcess:
    """Run *script* under ``bash`` and return the completed process."""
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        **kwargs,
    )


def _source_and_call(func_call: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """
    Source ``_qs_jobs.sh`` and call *func_call*.

    The function call's stdout is the result; any error message goes to stderr
    and the exit code signals success/failure.
    """
    cmd = f"""
set -e
source "{_QS_JOBS_HELPER}"
{func_call}
"""
    return _bash(cmd, env=env)


# ---------------------------------------------------------------------------
# qs_validate_jobs — parsing & validation
# ---------------------------------------------------------------------------


class TestQsValidateJobsParsing:
    """QS_INTEGRATION_JOBS decimal validation rules."""

    # -- Default / zero behaviour -------------------------------------------

    def test_unset_yields_zero(self) -> None:
        """Unset value (no env var) -> prints 0, exits 0."""
        result = _source_and_call('qs_validate_jobs ""')
        assert result.returncode == 0
        assert result.stdout.strip() == "0"

    def test_explicit_zero_yields_zero(self) -> None:
        """``0`` -> prints 0."""
        result = _source_and_call('qs_validate_jobs "0"')
        assert result.returncode == 0
        assert result.stdout.strip() == "0"

    # -- Positive integer behaviour -----------------------------------------

    def test_one_yields_one(self) -> None:
        """``1`` -> prints 1."""
        result = _source_and_call('qs_validate_jobs "1"')
        assert result.returncode == 0
        assert result.stdout.strip() == "1"

    def test_five_yields_five(self) -> None:
        """``5`` -> prints 5."""
        result = _source_and_call('qs_validate_jobs "5"')
        assert result.returncode == 0
        assert result.stdout.strip() == "5"

    def test_large_but_safe_value(self) -> None:
        """A large but non-overflowing value -> accepted."""
        result = _source_and_call('qs_validate_jobs "2147483647"')
        assert result.returncode == 0
        assert result.stdout.strip() == "2147483647"

    # -- Malformed / non-numeric ------------------------------------------

    def test_non_numeric_rejected(self) -> None:
        """A non-numeric string -> exits 1 with error message."""
        result = _source_and_call('qs_validate_jobs "abc"')
        assert result.returncode != 0
        assert "must be a non-negative integer" in result.stderr

    def test_negative_sign_rejected(self) -> None:
        """A negative signed value -> exits 1 (minus sign is not a digit)."""
        result = _source_and_call('qs_validate_jobs "-1"')
        assert result.returncode != 0
        assert "must be a non-negative integer" in result.stderr

    def test_decimal_fraction_rejected(self) -> None:
        """A decimal fraction ``3.5`` -> exits 1 (non-digit char '.')."""
        result = _source_and_call('qs_validate_jobs "3.5"')
        assert result.returncode != 0
        assert "must be a non-negative integer" in result.stderr

    def test_blank_not_zero_rejected(self) -> None:
        r"""Non-digit whitespace ``" "`` -> exits 1."""
        result = _source_and_call('qs_validate_jobs " "')
        assert result.returncode != 0
        assert "must be a non-negative integer" in result.stderr

    # -- Leading zeros ------------------------------------------------------

    def test_leading_zero_rejected(self) -> None:
        """``01`` -> exits 1 (leading zeros not allowed)."""
        result = _source_and_call('qs_validate_jobs "01"')
        assert result.returncode != 0
        assert "leading zeros" in result.stderr

    def test_multi_leading_zeros_rejected(self) -> None:
        """``007`` -> exits 1 (multiple leading zeros)."""
        result = _source_and_call('qs_validate_jobs "007"')
        assert result.returncode != 0
        assert "leading zeros" in result.stderr

    # -- Overflow (lexical rejection before arithmetic) ----------------------

    def test_overflow_rejected(self) -> None:
        """A value >= 2^63 -> exits 1 (lexical overflow check)."""
        # 2^63 = 9223372036854775808, caught by lexical length check
        result = _source_and_call('qs_validate_jobs "9223372036854775808"')
        assert result.returncode != 0
        assert "overflow" in result.stderr.lower()

    def test_max_safe_value_accepted(self) -> None:
        """Max safe value 9223372036854775807 -> accepted."""
        result = _source_and_call('qs_validate_jobs "9223372036854775807"')
        assert result.returncode == 0
        assert result.stdout.strip() == "9223372036854775807"

    def test_two_to_64_rejected(self) -> None:
        """2^64 (18446744073709551616) -> rejected by lexical check."""
        # 2^64 has 20 digits, caught by string-length check before any
        # arithmetic context that would silently wrap to 0.
        result = _source_and_call('qs_validate_jobs "18446744073709551616"')
        assert result.returncode != 0
        assert "overflow" in result.stderr.lower()

    def test_huge_digit_string_rejected(self) -> None:
        """A 30-digit value -> rejected by string-length check."""
        result = _source_and_call('qs_validate_jobs "999999999999999999999999999999"')
        assert result.returncode != 0
        assert "overflow" in result.stderr.lower()

    # -- Capping at max_workers -------------------------------------------

    def test_capped_at_max_workers(self) -> None:
        """Value exceeding max_workers -> silently capped to max."""
        result = _source_and_call('qs_validate_jobs "100" "12"')
        assert result.returncode == 0
        assert result.stdout.strip() == "12"

    def test_below_max_not_capped(self) -> None:
        """Value below max_workers -> unchanged."""
        result = _source_and_call('qs_validate_jobs "8" "12"')
        assert result.returncode == 0
        assert result.stdout.strip() == "8"

    def test_zero_not_capped(self) -> None:
        """0 (unlimited) -> 0, unaffected by max_workers."""
        result = _source_and_call('qs_validate_jobs "0" "12"')
        assert result.returncode == 0
        assert result.stdout.strip() == "0"

    def test_cap_at_one(self) -> None:
        """Value=5 with max=1 -> prints 1 (serial)."""
        result = _source_and_call('qs_validate_jobs "5" "1"')
        assert result.returncode == 0
        assert result.stdout.strip() == "1"


# ---------------------------------------------------------------------------
# Worker-pool helpers — production seam tests
# ---------------------------------------------------------------------------


class TestWorkerOrderBuilding:
    """_qs_build_worker_order discovers modules in sorted order."""

    def test_discovery_order(self) -> None:
        """WORKER_ORDER preserves directory sorted order."""
        tmpdir = tempfile.mkdtemp()
        try:
            mods_dir = os.path.join(tmpdir, "quickscale_modules")
            os.makedirs(os.path.join(mods_dir, "z_last", "tests"))
            os.makedirs(os.path.join(mods_dir, "a_first", "tests"))
            os.makedirs(os.path.join(mods_dir, "m_mid", "tests"))

            result = _source_and_call(
                f'_qs_build_worker_order "{mods_dir}" && echo "${{WORKER_ORDER[@]}}"'
            )
            assert result.returncode == 0
            names = result.stdout.strip().split()
            assert names[0] == "a_first", f"Expected a_first first, got {names}"
            assert names[1] == "m_mid", f"Expected m_mid second, got {names}"
            assert names[2] == "z_last", f"Expected z_last last, got {names}"
        finally:
            _rmrf(tmpdir)

    def test_skips_modules_without_tests(self) -> None:
        """Directories without tests/ are excluded."""
        tmpdir = tempfile.mkdtemp()
        try:
            mods_dir = os.path.join(tmpdir, "quickscale_modules")
            os.makedirs(os.path.join(mods_dir, "has_tests", "tests"))
            os.makedirs(os.path.join(mods_dir, "no_tests"))

            result = _source_and_call(
                f'_qs_build_worker_order "{mods_dir}" && echo "${{WORKER_ORDER[@]}}"'
            )
            assert result.returncode == 0
            names = result.stdout.strip().split()
            assert names == ["has_tests"]
        finally:
            _rmrf(tmpdir)


class TestEnforceWorkerBound:
    """_qs_enforce_worker_bound limits concurrent workers."""

    def test_max_active_workers_respects_bound(self) -> None:
        """At most QS_JOBS workers are active simultaneously."""
        tmpdir = tempfile.mkdtemp()
        try:
            active_file = os.path.join(tmpdir, "active_counts")
            result = _source_and_call(
                f"""
QS_JOBS=2
WORKER_TEMP_DIR="{tmpdir}/wt"
mkdir -p "$WORKER_TEMP_DIR"
declare -a WORKER_PIDS=()
declare -a WORKER_NAMES=()
ACTIVE_FILE="{active_file}"

for i in a b c d e; do
  (
    echo "$(date +%s%N) START $i" >> "$ACTIVE_FILE"
    sleep 0.3
    echo "$(date +%s%N) END $i" >> "$ACTIVE_FILE"
  ) &
  WORKER_NAMES+=("$i")
  WORKER_PIDS+=($!)

  _qs_enforce_worker_bound "$QS_JOBS" || true
done

wait 2>/dev/null || true

# Compute max concurrency from the activity log
python3 -c "
lines = open('$ACTIVE_FILE').read().strip().splitlines()
if not lines:
    exit(1)
active = 0
max_active = 0
events = []
for line in lines:
    ts, kind, name = line.split(None, 2)
    events.append((int(ts), kind, name))
events.sort()
for ts, kind, name in events:
    if kind == 'START':
        active += 1
        max_active = max(max_active, active)
    elif kind == 'END':
        active -= 1
print(max_active)
"
"""
            )
            assert result.returncode == 0
            max_active = int(result.stdout.strip())
            assert max_active == 2, f"Expected max 2 active workers, got {max_active}"
        finally:
            _rmrf(tmpdir)

    def test_bound_unlimited_when_zero(self) -> None:
        """With QS_JOBS=0, _qs_enforce_worker_bound is a no-op."""
        result = _source_and_call(
            """
QS_JOBS=0
declare -a WORKER_PIDS=(100 200)
declare -a WORKER_NAMES=(a b)
_qs_enforce_worker_bound "$QS_JOBS" || true
echo "COUNT=${#WORKER_PIDS[@]}"
echo "FIRST=${WORKER_PIDS[0]}"
"""
        )
        assert result.returncode == 0
        assert "COUNT=2" in result.stdout
        assert "FIRST=100" in result.stdout


class TestCapAtEligible:
    """_qs_cap_at_eligible caps QS_JOBS at the eligible-worker count."""

    def test_cap_at_eligible_count_logs_and_caps(self) -> None:
        """QS_JOBS above eligible -> capped to eligible count with log."""
        result = _source_and_call(
            """
QS_JOBS=100
_qs_cap_at_eligible 12
echo "QS_JOBS=$QS_JOBS"
"""
        )
        assert result.returncode == 0
        assert "QS_JOBS=12" in result.stdout
        assert "capped" in result.stderr

    def test_below_eligible_unchanged(self) -> None:
        """QS_JOBS below eligible -> unchanged, no log."""
        result = _source_and_call(
            """
QS_JOBS=5
_qs_cap_at_eligible 12
echo "QS_JOBS=$QS_JOBS"
"""
        )
        assert result.returncode == 0
        assert "QS_JOBS=5" in result.stdout
        assert result.stderr.strip() == ""

    def test_zero_not_capped(self) -> None:
        """QS_JOBS=0 (unlimited) -> unchanged regardless of eligible."""
        result = _source_and_call(
            """
QS_JOBS=0
_qs_cap_at_eligible 12
echo "QS_JOBS=$QS_JOBS"
"""
        )
        assert result.returncode == 0
        assert "QS_JOBS=0" in result.stdout
        assert result.stderr.strip() == ""

    def test_exact_eligible_unchanged(self) -> None:
        """QS_JOBS equal to eligible -> unchanged."""
        result = _source_and_call(
            """
QS_JOBS=12
_qs_cap_at_eligible 12
echo "QS_JOBS=$QS_JOBS"
"""
        )
        assert result.returncode == 0
        assert "QS_JOBS=12" in result.stdout
        assert result.stderr.strip() == ""


class TestMergeReplayOrder:
    """_qs_merge_worker_results and _qs_replay_worker_logs preserve order."""

    def test_merge_preserves_order(self) -> None:
        """Merged output preserves WORKER_ORDER."""
        tmpdir = tempfile.mkdtemp()
        try:
            work_dir = os.path.join(tmpdir, "wt")
            os.makedirs(work_dir)
            output_file = os.path.join(tmpdir, "merged")

            # Write per-worker result files out of order
            with open(os.path.join(work_dir, "results_z_last"), "w") as f:
                f.write("z|95.00\n")
            with open(os.path.join(work_dir, "results_a_first"), "w") as f:
                f.write("a|92.00\n")
            with open(os.path.join(work_dir, "results_m_mid"), "w") as f:
                f.write("m|88.00\n")

            result = _source_and_call(
                f"""
WORKER_ORDER=(a_first m_mid z_last)
_qs_merge_worker_results "{work_dir}" "{output_file}"
cat "{output_file}"
"""
            )
            assert result.returncode == 0
            lines = result.stdout.strip().splitlines()
            assert len(lines) == 3
            assert lines[0] == "a|92.00"
            assert lines[1] == "m|88.00"
            assert lines[2] == "z|95.00"
        finally:
            _rmrf(tmpdir)

    def test_replay_preserves_order(self) -> None:
        """Replayed output preserves WORKER_ORDER."""
        tmpdir = tempfile.mkdtemp()
        try:
            work_dir = os.path.join(tmpdir, "wt")
            os.makedirs(work_dir)

            with open(os.path.join(work_dir, "log_z_last"), "w") as f:
                f.write("=== z_last ===\n")
            with open(os.path.join(work_dir, "log_a_first"), "w") as f:
                f.write("=== a_first ===\n")
            with open(os.path.join(work_dir, "log_m_mid"), "w") as f:
                f.write("=== m_mid ===\n")

            result = _source_and_call(
                f"""
WORKER_ORDER=(a_first m_mid z_last)
_qs_replay_worker_logs "{work_dir}"
"""
            )
            assert result.returncode == 0
            lines = result.stdout.strip().splitlines()
            assert len(lines) == 3
            assert "a_first" in lines[0]
            assert "m_mid" in lines[1]
            assert "z_last" in lines[2]
        finally:
            _rmrf(tmpdir)


# ---------------------------------------------------------------------------
# Worker pool behaviour — failure propagation, cancellation
# ---------------------------------------------------------------------------


class TestWorkerPoolBehaviour:
    """Behavioural sanity checks via the production seam."""

    def test_worker_failure_propagates(self) -> None:
        """
        A worker that exits non-zero propagates to EXIT_CODE=1.

        The master process captures per-worker exit codes and sets
        ``EXIT_CODE=1`` when any worker fails.  Uses the production
        ``_qs_join_workers`` helper rather than an inline wait loop.
        """
        result = _source_and_call(
            """
EXIT_CODE=0
declare -a WORKER_PIDS=()
declare -a WORKER_NAMES=()
QS_JOBS=0
WORKER_TEMP_DIR="$(mktemp -d)"

# Launch two workers — one fails, one succeeds
(
  exit 0
) > "$WORKER_TEMP_DIR/log_ok" 2>&1 &
WORKER_PIDS+=($!)

(
  exit 2
) > "$WORKER_TEMP_DIR/log_fail" 2>&1 &
WORKER_PIDS+=($!)

# Join via production helper (replaces inline wait loop)
_qs_join_workers || EXIT_CODE=1

# Cleanup
rm -rf "$WORKER_TEMP_DIR"

echo "EXIT_CODE=$EXIT_CODE"
"""
        )
        assert result.returncode == 0
        assert "EXIT_CODE=1" in result.stdout

    def test_join_workers_all_pass(self) -> None:
        """
        When all workers succeed, ``_qs_join_workers`` preserves EXIT_CODE=0.

        Exercises the production helper with a clean worker set.
        """
        result = _source_and_call(
            """
EXIT_CODE=0
declare -a WORKER_PIDS=()
declare -a WORKER_NAMES=()
WORKER_TEMP_DIR="$(mktemp -d)"

# Launch three workers — all succeed
for i in ok1 ok2 ok3; do
  (exit 0) > "$WORKER_TEMP_DIR/log_$i" 2>&1 &
  WORKER_PIDS+=($!)
done

# Join via production helper
_qs_join_workers || EXIT_CODE=1

rm -rf "$WORKER_TEMP_DIR"
echo "EXIT_CODE=$EXIT_CODE"
"""
        )
        assert result.returncode == 0
        assert "EXIT_CODE=0" in result.stdout

    def test_join_workers_aggregates_failure(self) -> None:
        """
        ``_qs_join_workers`` returns 1 when any worker fails.

        Verifies that a mixed-success worker pool still triggers
        EXIT_CODE=1 through the production helper.
        """
        result = _source_and_call(
            """
EXIT_CODE=0
declare -a WORKER_PIDS=()
declare -a WORKER_NAMES=()
WORKER_TEMP_DIR="$(mktemp -d)"

# Launch three workers — middle one fails
(
  exit 0
) > "$WORKER_TEMP_DIR/log_ok1" 2>&1 &
WORKER_PIDS+=($!)

(
  exit 3
) > "$WORKER_TEMP_DIR/log_fail" 2>&1 &
WORKER_PIDS+=($!)

(
  exit 0
) > "$WORKER_TEMP_DIR/log_ok2" 2>&1 &
WORKER_PIDS+=($!)

# Join via production helper — should detect the failure
_qs_join_workers || EXIT_CODE=1

rm -rf "$WORKER_TEMP_DIR"
echo "EXIT_CODE=$EXIT_CODE"
"""
        )
        assert result.returncode == 0
        assert "EXIT_CODE=1" in result.stdout


# ---------------------------------------------------------------------------
# _kill_descendants — process-tree termination
# ---------------------------------------------------------------------------


class TestKillDescendants:
    """Process-tree traversal and signal propagation."""

    def test_kill_descendants_terminates_child(self) -> None:
        """
        ``_kill_descendants`` terminates a child process.

        Create a child that runs until signalled; send TERM via
        ``_kill_descendants`` and verify the child is reaped.
        """
        result = _source_and_call(
            f"""
TMP="{tempfile.mkdtemp()}"

# Launch a child that creates a marker file, then sleeps until killed
(
  touch "$TMP/child_alive"
  while true; do sleep 1; done
) &
CHILD_PID=$!

# Wait for the child to be alive, then kill it via _kill_descendants
sleep 0.2
_kill_descendants $CHILD_PID TERM

# Wait for reaping
wait $CHILD_PID 2>/dev/null || true

# The child's marker still exists (it didn't remove it)
if [ -f "$TMP/child_alive" ]; then
  echo "CHILD_WAS_ALIVE"
fi
rm -rf "$TMP"
"""
        )
        assert result.returncode == 0
        assert "CHILD_WAS_ALIVE" in result.stdout

    def test_kill_descendants_handles_nonexistent_pid(self) -> None:
        """``_kill_descendants`` with a nonexistent PID -> no-op, returns 0."""
        result = _source_and_call(
            """
_kill_descendants 999999999 TERM
echo "done"
"""
        )
        assert result.returncode == 0
        assert "done" in result.stdout

    def test_kill_descendants_branched_tree(self) -> None:
        """
        ``_kill_descendants`` kills an entire multi-level branched tree.

        Creates ROOT with two children, each with a grandchild, then
        verifies all six processes (ROOT + 2 children + 2 grandchildren)
        are terminated and processes outside the tree survive.
        """
        result = _source_and_call(
            f"""
TMP="{tempfile.mkdtemp()}"
PIDS="$TMP/pids"

# Build a tree:
#   ROOT
#   ├── CHILD1
#   │   └── GRANDCHILD1
#   └── CHILD2
#       └── GRANDCHILD2

(
  (
    sleep 60 &
    echo "$!" >> "$PIDS"
    wait 2>/dev/null || true
  ) &
  echo "$!" >> "$PIDS"

  (
    sleep 60 &
    echo "$!" >> "$PIDS"
    wait 2>/dev/null || true
  ) &
  echo "$!" >> "$PIDS"

  wait 2>/dev/null || true
) &
ROOT=$!
echo "$ROOT" >> "$PIDS"

# Allow tree to settle
sleep 0.3

# Spawn an unrelated process outside the tree
UNRELATED=$!
sleep 1 &
UNRELATED=$!

echo "$UNRELATED" >> "$PIDS.unrelated"

# Kill ROOT's entire tree
_kill_descendants "$ROOT" TERM

sleep 0.2

# Read PIDs and check each one
ALIVE=""
DEAD=""
while IFS= read -r pid; do
  [ -z "$pid" ] && continue
  if kill -0 "$pid" 2>/dev/null; then
    # Skip the test shell's own PID if captured
    [ "$pid" -eq $$ ] 2>/dev/null && continue
    ALIVE="$ALIVE $pid"
  else
    DEAD="$DEAD $pid"
  fi
done < "$PIDS"

# Count unique killed PIDs (ROOT + 2 children + 2 grandchildren)
KILLED_COUNT=$(echo "$DEAD" | tr ' ' '\\n' | sort -un | grep -c . || true)

echo "KILLED=$KILLED_COUNT"
echo "ALIVE_PIDS=$ALIVE"

# Verify unrelated process survived
if kill -0 "$UNRELATED" 2>/dev/null; then
  echo "UNRELATED_ALIVE"
fi

kill "$UNRELATED" 2>/dev/null || true
rm -rf "$TMP"
"""
        )
        assert result.returncode == 0
        assert "UNRELATED_ALIVE" in result.stdout
        # ROOT + at least 2 children = 3+ PIDs killed
        assert any(f"KILLED={n}" in result.stdout for n in (3, 4, 5)), (
            f"Expected KILLED=3,4,5 in stdout, got: {result.stdout}"
        )
        # Most importantly: verify ALIVE_PIDS is exactly empty — no tree PIDs survived.
        # Parse the ALIVE_PIDS= value and assert it is an empty string so that
        # any surviving descendent will cause a discriminating failure.
        alive_pids_line = None
        for line in result.stdout.strip().splitlines():
            if line.startswith("ALIVE_PIDS="):
                alive_pids_line = line
                break
        assert alive_pids_line is not None, f"ALIVE_PIDS= missing in stdout:\n{result.stdout}"
        alive_value = alive_pids_line[len("ALIVE_PIDS=") :].strip()
        assert alive_value == "", (
            f"Expected no surviving tree PIDs after _kill_descendants, "
            f"got: '{alive_value}' in stdout:\n{result.stdout}"
        )

    def test_kill_descendants_multi_child(self) -> None:
        """
        ``_kill_descendants`` kills every child when pgrep returns multiple.

        A parent with two children — both must be killed.
        """
        result = _bash(
            f"""
TMP="{tempfile.mkdtemp()}"
trap 'rm -rf "$TMP"' EXIT

# Create a root process that spawns two children
(
  sleep 30 &
  echo "$!" >> "$TMP/children"
  sleep 30 &
  echo "$!" >> "$TMP/children"
  wait 2>/dev/null || true
) &
ROOT=$!
echo "$ROOT" >> "$TMP/children"

# Source the helper and kill the tree
source "{_QS_JOBS_HELPER}"
sleep 0.3
_kill_descendants "$ROOT" TERM
sleep 0.2

# Verify none of the tree PIDs still exist
ALL_DEAD=true
while IFS= read -r pid; do
  [ -z "$pid" ] && continue
  if kill -0 "$pid" 2>/dev/null; then
    echo "PID_ALIVE:$pid"
    ALL_DEAD=false
  fi
done < "$TMP/children"

if [ "$ALL_DEAD" = true ]; then
  echo "ALL_TREE_DEAD"
fi
"""
        )
        assert result.returncode == 0
        assert "ALL_TREE_DEAD" in result.stdout


# ---------------------------------------------------------------------------
# Signal handler — _handle_worker_signal
# ---------------------------------------------------------------------------


class TestSignalHandler:
    """_handle_worker_signal traps, cleanup, and exact exit codes."""

    def test_handle_signal_exit_code_143(self) -> None:
        """_handle_worker_signal TERM -> exits 143."""
        result = _source_and_call(
            """
cleanup_temp_files() { :; }

WORKER_PIDS=()
WORKER_TEMP_DIR="$(mktemp -d)"

_handle_worker_signal TERM 143
echo "UNEXPECTED"
"""
        )
        assert result.returncode == 143
        assert "UNEXPECTED" not in result.stdout

    def test_handle_signal_exit_code_130(self) -> None:
        """_handle_worker_signal INT -> exits 130."""
        result = _source_and_call(
            """
cleanup_temp_files() { :; }

WORKER_PIDS=()
WORKER_TEMP_DIR="$(mktemp -d)"

_handle_worker_signal INT 130
echo "UNEXPECTED"
"""
        )
        assert result.returncode == 130
        assert "UNEXPECTED" not in result.stdout

    def test_handle_signal_exit_code_129(self) -> None:
        """_handle_worker_signal HUP -> exits 129."""
        result = _source_and_call(
            """
cleanup_temp_files() { :; }

WORKER_PIDS=()
WORKER_TEMP_DIR="$(mktemp -d)"

_handle_worker_signal HUP 129
echo "UNEXPECTED"
"""
        )
        assert result.returncode == 129
        assert "UNEXPECTED" not in result.stdout

    def test_trap_terminates_workers(self) -> None:
        """A real trap kills workers and cleans up temp dir."""
        tmpdir = tempfile.mkdtemp()
        try:
            state_file = os.path.join(tmpdir, "state")
            result = _source_and_call(
                f"""
cleanup_temp_files() {{
  if [ -n "${{WORKER_TEMP_DIR:-}}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
    rm -rf "$WORKER_TEMP_DIR"
  fi
}}

WORKER_PIDS=()
WORKER_TEMP_DIR="$(mktemp -d)"
echo "WTD=$WORKER_TEMP_DIR" > "{state_file}"

# Launch workers
(sleep 30) & WPID0=$!
WORKER_PIDS+=($WPID0)
echo "WP0=$WPID0" >> "{state_file}"
(sleep 30) & WPID1=$!
WORKER_PIDS+=($WPID1)
echo "WP1=$WPID1" >> "{state_file}"

# Verify workers are running
kill -0 $WPID0 2>/dev/null || echo "WP0_GONE_PRE"
kill -0 $WPID1 2>/dev/null || echo "WP1_GONE_PRE"

# Trap and trigger
trap '_handle_worker_signal TERM 143' TERM
kill -TERM $$
echo "UNEXPECTED"
"""
            )
            assert result.returncode == 143
            assert "UNEXPECTED" not in result.stdout

            # Read PIDs from state file
            wp0 = None
            wp1 = None
            wtd = None
            with open(state_file) as f:
                for line in f:
                    if line.startswith("WP0="):
                        wp0 = int(line.strip().split("=", 1)[1])
                    elif line.startswith("WP1="):
                        wp1 = int(line.strip().split("=", 1)[1])
                    elif line.startswith("WTD="):
                        wtd = line.strip().split("=", 1)[1]

            # Workers should be terminated
            if wp0 is not None:
                wp0_result = subprocess.run(["kill", "-0", str(wp0)], capture_output=True)
                assert wp0_result.returncode != 0, f"Worker {wp0} still alive"

            if wp1 is not None:
                wp1_result = subprocess.run(["kill", "-0", str(wp1)], capture_output=True)
                assert wp1_result.returncode != 0, f"Worker {wp1} still alive"

            # Temp dir should be removed
            if wtd is not None:
                assert not os.path.exists(wtd), f"Temp dir {wtd} still exists"
        finally:
            _rmrf(tmpdir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rmrf(path: str) -> None:
    """Remove *path* if it exists (file or directory)."""
    import shutil

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except FileNotFoundError:
        pass
