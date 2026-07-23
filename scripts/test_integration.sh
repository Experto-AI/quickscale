#!/usr/bin/env bash
# Run integration tests (module suites requiring PostgreSQL) in the repository.
# Requires PostgreSQL 18 running on localhost:5432.
# See scripts/test_isolation_conformance.sh for the restricted role pattern.
#
# NOTE: This script runs module integration tests only.
# @pytest.mark.e2e tests are explicitly excluded (they belong under test_e2e.sh).
# Unit tests (core + CLI) are run via scripts/test_unit.sh.
# E2E tests are run via scripts/test_e2e.sh.
#
# Prerequisites:
#   - PostgreSQL 18 running on localhost:5432
#   - All test databases pre-created (see ci.yml create-test-databases step)
#   - A LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role (e.g. quickscale_test_role) with
#     ownership + schema grants on all module test databases
#   - Poetry installed, dependencies installed

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

SHOW_FULL_OUTPUT=false
# Repository policy is dual-threshold: protect floor quality per file while
# enforcing a 90% overall mean across the maintained test matrix.
COVERAGE_MEAN_THRESHOLD=90
FILE_COVERAGE_THRESHOLD=80

# ---------------------------------------------------------------------------
# SA76 — Ticketed quarantine for known integration-gate failures
# ---------------------------------------------------------------------------
# Each entry maps a module name to its owning ticket. When a module is
# quarantined, its test failures are excluded from the exit code and its
# coverage is excluded from the overall mean. Remove the entry when the
# owning ticket lands. Entries are removed independently as each owning
# ticket completes — not held for a single simultaneous closeout.
declare -A QUARANTINE_TICKETS

is_quarantined() {
  local mod_name="$1"
  [[ -n "${QUARANTINE_TICKETS[$mod_name]+exists}" ]]
}

get_quarantine_ticket() {
  local mod_name="$1"
  if [[ -n "${QUARANTINE_TICKETS[$mod_name]+exists}" ]]; then
    printf '%s\n' "${QUARANTINE_TICKETS[$mod_name]}"
  fi
}

PYTEST_EXTRA_ARGS=()
COVERAGE_RESULTS_FILE="$(mktemp)"

cleanup_temp_files() {
  rm -f "$COVERAGE_RESULTS_FILE"
  if [ -n "${WORKER_TEMP_DIR:-}" ] && [ -d "$WORKER_TEMP_DIR" ]; then
    rm -rf "$WORKER_TEMP_DIR"
  fi
}

trap cleanup_temp_files EXIT

# SA91 — INT/TERM/HUP signal cleanup: terminate worker subprocess trees,
# reap workers, then clean temp files.  The EXIT trap handles the common
# cleanup path; these signal traps add worker-tree termination before exit.
trap '_handle_worker_signal TERM 143' TERM
trap '_handle_worker_signal INT 130' INT
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

persist_module_coverage_xml() {
  local stage_name="$1"
  local coverage_xml="$2"
  local mod_name=""

  case "$stage_name" in
    module\ *)
      mod_name="${stage_name#module }"
      ;;
    *)
      return 0
      ;;
  esac

  local target_path="quickscale_modules/${mod_name}/coverage.xml"
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
  echo "  QS_INTEGRATION_JOBS   Concurrency limit for module test workers."
  echo "                        0 or unset = unlimited (all eligible modules run concurrently)."
  echo "                        1 = serial (one module at a time)."
  echo "                        Positive N = at most N workers at once."
  echo "                        Must be a non-negative decimal integer with no leading zeros."
  echo "                        Values exceeding the number of eligible test modules are capped."
  echo ""
  echo "Required environment (PostgreSQL 18):"
  echo "  - PostgreSQL running on localhost:5432"
  echo "  - Module test databases pre-created"
  echo "  - Restricted role (e.g. quickscale_test_role) with LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER"
  echo "  - QS_*_DB_USER env vars default to quickscale_test_role; can be overridden per module"
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

  # Subset runs cover only part of each file — suppress the per-file gate too.
  if [ "${QS_SKIP_COVERAGE_GATE:-}" = "1" ]; then
    return 0
  fi

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
  # Subset runs (e.g. `make test-bypassrls`, which runs only `-m bypass_rls`
  # tests) legitimately cover a fraction of each module, so the mean-coverage
  # gate does not apply. Opt out explicitly via QS_SKIP_COVERAGE_GATE=1.
  if [ "${QS_SKIP_COVERAGE_GATE:-}" = "1" ]; then
    echo "📊 Coverage gate skipped (QS_SKIP_COVERAGE_GATE=1 — subset run)."
    return 0
  fi
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
  local quarantine_ticket="${4:-}"
  shift 4
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
    shared_args+=(--cov-report=html)
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

  # Subset runs (QS_SKIP_COVERAGE_GATE=1, e.g. `make test-bypassrls -- -m bypass_rls`)
  # legitimately match zero tests in modules that have none of the selected marker.
  # pytest exits 5 ("no tests collected") there; treat that as success, not failure.
  if [ "${QS_SKIP_COVERAGE_GATE:-}" = "1" ] && [ "$stage_exit" -eq 5 ]; then
    stage_exit=0
  fi

  local coverage_pct
  coverage_pct="$(extract_coverage_percent "$coverage_xml" || true)"
  persist_module_coverage_xml "$stage_name" "$coverage_xml"
  if [ -n "$coverage_pct" ] && [ -z "$quarantine_ticket" ]; then
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
    if [ -n "$quarantine_ticket" ]; then
      echo "  → ${stage_name} coverage recorded: ${coverage_pct}% (quarantined — ${quarantine_ticket})"
    else
      echo "  → ${stage_name} coverage recorded: ${coverage_pct}%"
    fi
  fi

  rm -f "$coverage_xml" "$coverage_report" "$run_log"
  if [ $stage_exit -ne 0 ] || [ $coverage_policy_exit -ne 0 ]; then
    if [ -n "$quarantine_ticket" ]; then
      echo "  ⚠  ${stage_name}: known failures quarantined (${quarantine_ticket}) — excluded from gate"
      return 0
    fi
    return 1
  fi
  return 0
}

echo "🧪 Running integration tests (module suites requiring PostgreSQL)..."
echo "  Required role attributes: LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER"
echo "  (see scripts/test_isolation_conformance.sh for role-creation pattern)"
echo ""
if [ "$POETRY_AVAILABLE" = false ] && [ -x "$VENV_BIN/python" ]; then
  echo "Execution environment: repo-local .venv (Poetry not found on PATH)"
fi
echo ""

# ---------------------------------------------------------------------------
# SA80.2 — Wire every PostgreSQL-using module's test settings to the
# restricted role, matching CI workflow retained-role contract.
# Each var defaults to quickscale_test_role; callers can pre-export to
# override individual modules.  Keeps the SA58 boot guard active against
# the NOBYPASSRLS/NOSUPERUSER role.
# Matches .github/workflows/ci.yml (lines 399-410) and publish.yml (160-171).
# ---------------------------------------------------------------------------
export QS_ANALYTICS_DB_USER="${QS_ANALYTICS_DB_USER:-quickscale_test_role}"
export QS_AUTH_DB_USER="${QS_AUTH_DB_USER:-quickscale_test_role}"
export QS_BACKUPS_DB_USER="${QS_BACKUPS_DB_USER:-quickscale_test_role}"
export QS_BILLING_DB_USER="${QS_BILLING_DB_USER:-quickscale_test_role}"
export QS_BLOG_DB_USER="${QS_BLOG_DB_USER:-quickscale_test_role}"
export QS_CRM_DB_USER="${QS_CRM_DB_USER:-quickscale_test_role}"
export QS_FORMS_DB_USER="${QS_FORMS_DB_USER:-quickscale_test_role}"
export QS_LISTINGS_DB_USER="${QS_LISTINGS_DB_USER:-quickscale_test_role}"
export QS_NOTIFICATIONS_DB_USER="${QS_NOTIFICATIONS_DB_USER:-quickscale_test_role}"
export QS_ORGS_DB_USER="${QS_ORGS_DB_USER:-quickscale_test_role}"
export QS_SOCIAL_DB_USER="${QS_SOCIAL_DB_USER:-quickscale_test_role}"
export QS_STORAGE_DB_USER="${QS_STORAGE_DB_USER:-quickscale_test_role}"

if [ "$POETRY_AVAILABLE" = false ]; then
  get_repo_venv_python >/dev/null || exit 1
fi

# Track exit codes
EXIT_CODE=0

# Print quarantine banner if any modules are quarantined
if [ ${#QUARANTINE_TICKETS[@]} -gt 0 ]; then
  echo "🔒 SA76 quarantine active — known failures excluded from gate."
  for mod_name in "${!QUARANTINE_TICKETS[@]}"; do
    echo "     ${mod_name}: ${QUARANTINE_TICKETS[$mod_name]}"
  done
  echo ""
fi

echo "📦 Testing quickscale_modules..."
# Test modules using ROOT poetry environment (centralized dependencies)
# Modules are installed in editable mode via root pyproject.toml
# PYTHONPATH keeps the current module root first and adds sibling module src dirs
# so cross-module imports like notifications -> forms resolve during bootstrap.
#
# NOTE: No blanket QUICKSCALE_ALLOW_BYPASSRLS=1 here — the SA58 boot guard
# stays active against the NOBYPASSRLS role.  Set the SA14.4 hatch explicitly
# per-suite when BYPASSRLS-dependent tests need to run.
if [ -d "quickscale_modules" ]; then
  # Parse QS_INTEGRATION_JOBS concurrency setting (SA91).
  #   0 or unset = unlimited (all eligible modules run concurrently)
  #   positive N = bound to N concurrent workers
  #   1 = effectively serial, still through the same worker subshell path
  # Validation rejects non-decimal, leading-zero, and overflowing values.
  # Capping to eligible worker count happens after WORKER_ORDER is built.
  QS_JOBS="$(qs_validate_jobs "${QS_INTEGRATION_JOBS:-}" 2>/dev/null)" || {
    # Re-run without suppressing stderr for the user-facing error message
    qs_validate_jobs "${QS_INTEGRATION_JOBS:-}" >/dev/null
    exit 1
  }

  # Create temp directory for per-worker state (SA91 — parallel execution)
  WORKER_TEMP_DIR="$(mktemp -d)"
  declare -a WORKER_PIDS=()
  declare -a WORKER_NAMES=()
  declare -a WORKER_ORDER=()

  # First pass: build WORKER_ORDER so we know the eligible worker count
  # before launching any workers.  Positive QS_JOBS values that exceed the
  # eligible count are capped so a request for 100 workers on 12 modules
  # does not leave leftover slots idle.
  _qs_build_worker_order "$REPO_ROOT/quickscale_modules"

  # Cap QS_JOBS at the eligible worker count for positive values.
  _qs_cap_at_eligible "${#WORKER_ORDER[@]}"

  for mod in quickscale_modules/*; do
    if [ -d "$mod" ]; then
      mod_name=$(basename "$mod")
      if [ -d "$mod/tests" ]; then
        # WORKER_ORDER already populated in first pass; second pass launches
        # workers with the (possibly capped) QS_JOBS bound.

        quarantine_flag=""
        if is_quarantined "$mod_name"; then
          quarantine_flag="$(get_quarantine_ticket "$mod_name")"
        fi

        # Package name format: quickscale_modules_<name> (underscores, not hyphens)
        pkg_name="quickscale_modules_${mod_name}"
        worker_results="$WORKER_TEMP_DIR/results_${mod_name}"
        worker_log="$WORKER_TEMP_DIR/log_${mod_name}"

        # Launch worker in a background subshell — same path for all
        # concurrency levels (QS_INTEGRATION_JOBS=1 runs one at a time
        # through the wait/remove loop below; 0 runs all concurrently).
        (
          if [ -n "$quarantine_flag" ]; then
            echo "  → Testing module: $mod_name [quarantined: ${quarantine_flag}]"
          else
            echo "  → Testing module: $mod_name"
          fi

          # Each worker uses its own COVERAGE_RESULTS_FILE and COVERAGE_FILE
          # so concurrent coverage-append writes and .coverage data file
          # access do not collide across workers.
          COVERAGE_RESULTS_FILE="$worker_results"
          # COVERAGE_FILE must be exported so that coverage.py (run as a
          # subprocess via pytest-cov and the `coverage report` command)
          # reads it from os.environ rather than defaulting to the shared
          # `.coverage` path, which would race across parallel workers.
          export COVERAGE_FILE="$WORKER_TEMP_DIR/.coverage.${mod_name}"
          run_pytest_stage \
            "module ${mod_name}" \
            "$pkg_name" \
            false \
            "$quarantine_flag" \
            run_with_pythonpath "$(build_module_pythonpath "$mod")${PYTHONPATH:+:$PYTHONPATH}" run_repo_tool pytest "$mod/tests/" \
              -m "not e2e" -p pytest_django --ds=tests.settings
        ) > "$worker_log" 2>&1 &

        WORKER_NAMES+=("$mod_name")
        WORKER_PIDS+=($!)

        # Enforce concurrency bound: when at the limit, wait for the
        # oldest running worker to free a slot before launching more.
        _qs_enforce_worker_bound "$QS_JOBS" || EXIT_CODE=1
      else
        echo "  → Skipping $mod_name (no tests/ directory)"
      fi
    fi
  done

  # Wait for remaining workers and capture exit codes
  _qs_join_workers || EXIT_CODE=1

  # Replay captured worker output in original module order so the
  # deterministic summary structure is preserved.
  _qs_replay_worker_logs "$WORKER_TEMP_DIR"

  # Merge per-module coverage results before the overall-mean check.
  _qs_merge_worker_results "$WORKER_TEMP_DIR" "$COVERAGE_RESULTS_FILE"
else
  echo "  → No quickscale_modules directory found"
fi

echo ""
if [ ${#QUARANTINE_TICKETS[@]} -gt 0 ]; then
  echo "  (coverage from quarantined modules excluded from mean)"
fi
if ! check_overall_mean_coverage; then
  EXIT_CODE=1
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ Integration tests passed!"
else
  echo "❌ Some integration tests failed!"
  exit $EXIT_CODE
fi
