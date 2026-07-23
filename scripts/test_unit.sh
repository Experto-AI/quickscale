#!/usr/bin/env bash
# Run unit tests (core + CLI) in the repository with Poetry.
# Module integration tests are run separately via scripts/test_integration.sh.
# Default output is dot-style. Use --full to show full per-file pytest + coverage output.
#
# NOTE: This script runs unit tests only (core + CLI; DB-free).
# E2E tests are excluded (too slow for regular runs).
# To run E2E tests, use: ./scripts/test_e2e.sh
# To run module integration tests, use: ./scripts/test_integration.sh

set -e

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"
# shellcheck source=./_python_requirement.sh
source "$REPO_ROOT/scripts/_python_requirement.sh"
# shellcheck source=./_qs_jobs.sh
source "$REPO_ROOT/scripts/_qs_jobs.sh"
REQUIRED_PYTHON_VERSION="$(quickscale_min_python_version "$REPO_ROOT")"
POETRY_AVAILABLE=false

# Lane mode: core and CLI unit suites are independent and DB-free, so they run
# as concurrent background workers by default (mirrors QS_E2E_PARALLEL in
# test_e2e.sh).  Set QS_UNIT_PARALLEL=0 to run the lanes serially.
if [ "${QS_UNIT_PARALLEL:-1}" = "0" ]; then
  UNIT_PARALLEL=false
else
  UNIT_PARALLEL=true
fi

# Per-worker scratch dir for lane logs, statuses, coverage data, and results.
WORKER_TEMP_DIR="$(mktemp -d)"
# Worker-pool bookkeeping consumed by the _qs_* helpers in _qs_jobs.sh.
WORKER_PIDS=()
WORKER_ORDER=()
WORKER_WAIT_PID=""

SHOW_FULL_OUTPUT=false
# Repository policy is dual-threshold: protect floor quality per file while
# enforcing a 90% overall mean across the maintained test matrix.
COVERAGE_MEAN_THRESHOLD=90
FILE_COVERAGE_THRESHOLD=80
PYTEST_EXTRA_ARGS=()
COVERAGE_RESULTS_FILE="$(mktemp)"

cleanup_temp_files() {
  rm -f "$COVERAGE_RESULTS_FILE"
  if [ -n "${WORKER_TEMP_DIR:-}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
    rm -rf "$WORKER_TEMP_DIR"
  fi
}

trap cleanup_temp_files EXIT
# Terminate lane worker subtrees and clean up on interrupt (shared handler).
trap '_handle_worker_signal INT 130' INT
trap '_handle_worker_signal TERM 143' TERM
trap '_handle_worker_signal HUP 129' HUP

if command -v poetry >/dev/null 2>&1; then
  POETRY_AVAILABLE=true
fi

get_repo_venv_python() {
  if [ -x "$VENV_BIN/python" ]; then
    printf '%s\n' "$VENV_BIN/python"
    return 0
  fi

  echo "❌ The repo-local .venv is incomplete: $VENV_BIN/python is missing or not executable." >&2
  echo "   This usually means the project was moved or copied without its virtualenv interpreter files." >&2

  local compatible_python
  compatible_python="$(quickscale_find_compatible_python "$REPO_ROOT" || true)"
  if [ -n "$compatible_python" ]; then
    echo "   Run ./scripts/bootstrap.sh to recreate .venv with $compatible_python." >&2
  else
    echo "   Install Python ${REQUIRED_PYTHON_VERSION}+ and then run ./scripts/bootstrap.sh to recreate .venv." >&2
  fi

  return 1
}

run_repo_tool() {
  local tool_name="$1"
  shift

  if [ "$POETRY_AVAILABLE" = true ]; then
    poetry run "$tool_name" "$@"
    return
  fi

  local venv_python
  venv_python="$(get_repo_venv_python)" || return 1
  "$venv_python" -m "$tool_name" "$@"
}

run_with_pythonpath() {
  local pythonpath="$1"
  shift
  local original_pythonpath="${PYTHONPATH-}"

  export PYTHONPATH="$pythonpath"
  "$@"
  local command_exit=$?

  if [ -n "$original_pythonpath" ]; then
    export PYTHONPATH="$original_pythonpath"
  else
    unset PYTHONPATH
  fi

  return $command_exit
}

cd "$REPO_ROOT"

persist_coverage_xml() {
  local stage_name="$1"
  local coverage_xml="$2"
  local target_path=""

  case "$stage_name" in
    quickscale_core)
      target_path="quickscale_core/coverage.xml"
      ;;
    quickscale_cli)
      target_path="quickscale_cli/coverage.xml"
      ;;
  esac

  if [ -n "$target_path" ] && [ -f "$coverage_xml" ]; then
    cp "$coverage_xml" "$target_path"
  fi
}

show_help() {
  echo "Usage: $0 [OPTIONS] [-- <pytest-args>]"
  echo ""
  echo "Options:"
  echo "  --full            Show full pytest output (per-file lines + coverage details)"
  echo "  --verbose, -v     Alias for --full"
  echo "  --help, -h        Show this help message"
  echo ""
  echo "Environment:"
  echo "  QS_UNIT_PARALLEL=0  Run core and CLI lanes serially (default: concurrent)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full|--verbose|-v)
      SHOW_FULL_OUTPUT=true
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    --)
      shift
      PYTEST_EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

extract_coverage_percent() {
  local coverage_xml="$1"
  if [ ! -f "$coverage_xml" ]; then
    return 1
  fi

  local line_rate
  line_rate=$(
    awk -F'"' '/<coverage/{for (i = 1; i < NF; i++) {if ($i ~ /line-rate=/) {print $(i+1); exit}}}' \
      "$coverage_xml"
  )

  if [ -z "$line_rate" ]; then
    return 1
  fi

  awk -v rate="$line_rate" 'BEGIN { printf "%.2f", rate * 100 }'
}

extract_low_coverage_lines() {
  local coverage_report="$1"

  awk -v threshold="$FILE_COVERAGE_THRESHOLD" '
    /^Name[[:space:]]+Stmts[[:space:]]+Miss[[:space:]]+Cover/ {
      in_report = 1
      next
    }
    !in_report || /^-+/ || $1 == "TOTAL" {
      next
    }
    NF >= 4 {
      cover = $4
      gsub(/%/, "", cover)
      if ((cover + 0) < threshold) {
        print
      }
    }
  ' "$coverage_report"
}

build_module_pythonpath() {
  local module_path="$1"
  local sibling_path=""
  local -a path_entries=("$module_path")

  # Add the repo root so cross-module shared test helpers
  # (e.g. tests_shared.isolation) are importable from every module's tests.
  path_entries+=(".")

  if [ -d "$module_path/src" ]; then
    path_entries+=("$module_path/src")
  fi

  for sibling_path in quickscale_modules/*; do
    if [ "$sibling_path" = "$module_path" ] || [ ! -d "$sibling_path/src" ]; then
      continue
    fi
    path_entries+=("$sibling_path/src")
  done

  local IFS=:
  printf '%s' "${path_entries[*]}"
}

check_overall_mean_coverage() {
  if [ ! -s "$COVERAGE_RESULTS_FILE" ]; then
    return 0
  fi

  local overall_mean
  overall_mean="$({
    awk -F'|' '{ sum += $2; count += 1 } END { if (count > 0) printf "%.2f", sum / count }' "$COVERAGE_RESULTS_FILE"
  })"

  echo "📊 Coverage policy summary:"
  awk -F'|' '{ printf "  → %s: %s%%\n", $1, $2 }' "$COVERAGE_RESULTS_FILE"
  echo "  → overall mean: ${overall_mean}% (minimum ${COVERAGE_MEAN_THRESHOLD}%)"

  if awk -v mean="$overall_mean" -v threshold="$COVERAGE_MEAN_THRESHOLD" 'BEGIN { exit (mean + 0 >= threshold ? 0 : 1) }'; then
    return 0
  fi

  echo "  → Overall mean coverage is below ${COVERAGE_MEAN_THRESHOLD}%."
  return 1
}

run_pytest_stage() {
  local stage_name="$1"
  local coverage_target="$2"
  local include_html_report="$3"
  shift 3
  local -a stage_cmd=("$@")

  local coverage_xml
  coverage_xml="$(mktemp)"
  local coverage_report
  coverage_report="$(mktemp)"
  local run_log
  run_log="$(mktemp)"
  local stage_exit=0
  local coverage_policy_exit=0
  local coverage_report_exit=0

  local -a shared_args=(
    --tb=long
    -ra
    -o "addopts="
    "--cov=${coverage_target}"
    "--cov-report=xml:${coverage_xml}"
    --cov-fail-under=0
  )

  if [ "$include_html_report" = true ]; then
    # Stage-specific HTML dir: concurrent lanes would otherwise both write the
    # default htmlcov/ and clobber each other.
    shared_args+=("--cov-report=html:htmlcov_${stage_name}")
  fi

  local -a quiet_args=(
    -q
  )

  local -a full_args=(
    --cov-report=term-missing
  )

  if [ "$SHOW_FULL_OUTPUT" = true ]; then
    set +e
    "${stage_cmd[@]}" "${shared_args[@]}" "${full_args[@]}" "${PYTEST_EXTRA_ARGS[@]}"
    stage_exit=$?
    set -e
  else
    set +e
    "${stage_cmd[@]}" "${shared_args[@]}" "${quiet_args[@]}" "${PYTEST_EXTRA_ARGS[@]}" 2>&1 | tee "$run_log"
    stage_exit=${PIPESTATUS[0]}
    set -e
  fi

  local coverage_pct
  coverage_pct="$(extract_coverage_percent "$coverage_xml" || true)"
  persist_coverage_xml "$stage_name" "$coverage_xml"
  if [ -n "$coverage_pct" ]; then
    printf '%s|%s\n' "$stage_name" "$coverage_pct" >> "$COVERAGE_RESULTS_FILE"
  fi

  set +e
  run_repo_tool coverage report -m --fail-under=0 > "$coverage_report"
  coverage_report_exit=$?
  set -e

  if [ $coverage_report_exit -eq 0 ]; then
    local low_coverage_lines
    low_coverage_lines="$(extract_low_coverage_lines "$coverage_report")"
    if [ -n "$low_coverage_lines" ]; then
      coverage_policy_exit=1
      echo "  → Files below ${FILE_COVERAGE_THRESHOLD}% coverage:"
      printf '%s\n' "$low_coverage_lines"
    fi
  fi

  if [ -n "$coverage_pct" ]; then
    echo "  → ${stage_name} coverage recorded: ${coverage_pct}%"
  fi

  rm -f "$coverage_xml" "$coverage_report" "$run_log"
  if [ $stage_exit -ne 0 ] || [ $coverage_policy_exit -ne 0 ]; then
    return 1
  fi
  return 0
}

# Map a lane id to its (stage_name, tests-path) pair.
lane_stage_name() {
  case "$1" in
    core) printf 'quickscale_core' ;;
    cli)  printf 'quickscale_cli' ;;
  esac
}
lane_tests_path() {
  case "$1" in
    core) printf 'quickscale_core/tests/' ;;
    cli)  printf 'quickscale_cli/tests/' ;;
  esac
}

# launch_unit_lane <core|cli> [log_file]
#
# Runs one package's unit stage in a background subshell.  Each lane isolates
# its coverage artifacts so concurrent lanes never race:
#   - COVERAGE_FILE: per-lane .coverage data file (read by `coverage report`)
#   - COVERAGE_RESULTS_FILE: per-lane results, merged after the join barrier
# When log_file is given the lane's output is captured for post-join replay
# (parallel mode); without it the output streams live (serial mode).
launch_unit_lane() {
  local lane="$1"
  local log_file="${2:-}"
  local status_file="$WORKER_TEMP_DIR/status_$lane"
  local stage_name tests_path
  stage_name="$(lane_stage_name "$lane")"
  tests_path="$(lane_tests_path "$lane")"

  _run_unit_lane_body() {
    set +e
    export COVERAGE_FILE="$WORKER_TEMP_DIR/coverage_$lane"
    COVERAGE_RESULTS_FILE="$WORKER_TEMP_DIR/results_$lane"
    : > "$COVERAGE_RESULTS_FILE"
    echo "📦 Testing ${stage_name}..."
    # Run from root directory to use root Poetry environment (monorepo setup).
    # Skip E2E tests (run separately with ./scripts/test_e2e.sh).
    # Use package name (not src/) to avoid double-counting with pyproject addopts.
    run_pytest_stage \
      "$stage_name" \
      "$stage_name" \
      true \
      run_repo_tool pytest "$tests_path" -m "not integration and not e2e"
    local lane_status=$?
    printf '%s\n' "$lane_status" > "$status_file"
    exit "$lane_status"
  }

  if [ -n "$log_file" ]; then
    ( _run_unit_lane_body ) > "$log_file" 2>&1 &
  else
    ( _run_unit_lane_body ) &
  fi
  WORKER_PIDS+=("$!")
}

read_lane_status() {
  local lane="$1"
  local status_file="$WORKER_TEMP_DIR/status_$lane"
  local status
  if [ -f "$status_file" ]; then
    read -r status < "$status_file"
    printf '%s' "$status"
  else
    printf '1'
  fi
}

# Serial: one lane at a time, streaming output (preserves pre-parallel behavior).
run_unit_lanes_serial() {
  local lane lane_status
  local failed=false
  for lane in core cli; do
    WORKER_PIDS=()
    launch_unit_lane "$lane"
    _qs_join_workers || failed=true
    lane_status="$(read_lane_status "$lane")"
    [ "$lane_status" -ne 0 ] && failed=true
    # Fold the lane's coverage result into the aggregate for the mean gate.
    cat "$WORKER_TEMP_DIR/results_$lane" >> "$COVERAGE_RESULTS_FILE" 2>/dev/null || true
    echo ""
  done
  WORKER_PIDS=()
  [ "$failed" = false ]
}

# Parallel: launch both lanes, join, then replay logs and merge results in a
# deterministic order so output and the coverage summary stay stable.
run_unit_lanes_parallel() {
  local lane lane_status
  local failed=false
  WORKER_PIDS=()
  WORKER_ORDER=(core cli)
  launch_unit_lane core "$WORKER_TEMP_DIR/log_core"
  launch_unit_lane cli "$WORKER_TEMP_DIR/log_cli"

  _qs_join_workers || failed=true

  _qs_replay_worker_logs "$WORKER_TEMP_DIR"
  _qs_merge_worker_results "$WORKER_TEMP_DIR" "$COVERAGE_RESULTS_FILE"
  for lane in core cli; do
    lane_status="$(read_lane_status "$lane")"
    [ "$lane_status" -ne 0 ] && failed=true
  done
  WORKER_PIDS=()
  [ "$failed" = false ]
}

echo "🧪 Running unit tests (core + CLI)..."
if [ "$SHOW_FULL_OUTPUT" = true ]; then
  echo "Output mode: full"
else
  echo "Output mode: dots"
fi
echo "Coverage policy: ${COVERAGE_MEAN_THRESHOLD}% overall mean, ${FILE_COVERAGE_THRESHOLD}% per file"
if [ "$UNIT_PARALLEL" = true ]; then
  echo "Lane mode: parallel (core + CLI)"
else
  echo "Lane mode: serial (QS_UNIT_PARALLEL=0)"
fi
if [ "$POETRY_AVAILABLE" = false ] && [ -x "$VENV_BIN/python" ]; then
  echo "Execution environment: repo-local .venv (Poetry not found on PATH)"
fi
echo ""

if [ "$POETRY_AVAILABLE" = false ]; then
  get_repo_venv_python >/dev/null || exit 1
fi

# Track exit codes
EXIT_CODE=0

if [ "$UNIT_PARALLEL" = true ]; then
  run_unit_lanes_parallel || EXIT_CODE=1
else
  run_unit_lanes_serial || EXIT_CODE=1
fi

echo ""
echo "📦 Module integration tests are available via:"
echo "    make test-integration"
echo "  or directly:"
echo "    ./scripts/test_integration.sh"
echo ""
echo "  Requires PostgreSQL 18 with a LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role."
echo "  Override QUICKSCALE_ALLOW_BYPASSRLS=1 explicitly per-suite for the"
echo "  SA14.4 BYPASSRLS hatch."

echo ""
if ! check_overall_mean_coverage; then
  EXIT_CODE=1
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ Tests passed!"
else
  echo "❌ Some tests failed!"
  exit $EXIT_CODE
fi
