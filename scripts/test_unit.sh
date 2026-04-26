#!/usr/bin/env bash
# Run unit and integration tests in the repository with Poetry.
# Default output is dot-style. Use --full to show full per-file pytest + coverage output.
#
# NOTE: This script runs unit and integration tests only.
# E2E tests are excluded (too slow for regular runs).
# To run E2E tests, use: ./scripts/test_e2e.sh

set -e

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"
# shellcheck source=./_python_requirement.sh
source "$REPO_ROOT/scripts/_python_requirement.sh"
REQUIRED_PYTHON_VERSION="$(quickscale_min_python_version "$REPO_ROOT")"
POETRY_AVAILABLE=false

SHOW_FULL_OUTPUT=false
# Repository policy is dual-threshold: protect floor quality per file while
# enforcing a 90% overall mean across the maintained test matrix.
COVERAGE_MEAN_THRESHOLD=90
FILE_COVERAGE_THRESHOLD=80
PYTEST_EXTRA_ARGS=()
COVERAGE_RESULTS_FILE="$(mktemp)"

cleanup_temp_files() {
  rm -f "$COVERAGE_RESULTS_FILE"
}

trap cleanup_temp_files EXIT

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

echo "🧪 Running unit and integration tests..."
if [ "$SHOW_FULL_OUTPUT" = true ]; then
  echo "Output mode: full"
else
  echo "Output mode: dots"
fi
echo "Coverage policy: ${COVERAGE_MEAN_THRESHOLD}% overall mean, ${FILE_COVERAGE_THRESHOLD}% per file"
if [ "$POETRY_AVAILABLE" = false ] && [ -x "$VENV_BIN/python" ]; then
  echo "Execution environment: repo-local .venv (Poetry not found on PATH)"
fi
echo ""

if [ "$POETRY_AVAILABLE" = false ]; then
  get_repo_venv_python >/dev/null || exit 1
fi

# Track exit codes
EXIT_CODE=0

echo "📦 Testing quickscale_core..."
# Run from root directory to use root Poetry environment (monorepo setup)
# Skip E2E tests (run separately with ./scripts/test_e2e.sh)
# Use package name (not src/) to avoid double-counting with pyproject.toml addopts
if ! run_pytest_stage \
  "quickscale_core" \
  "quickscale_core" \
  true \
  run_repo_tool pytest quickscale_core/tests/ -m "not e2e"; then
  EXIT_CODE=1
fi

echo ""
echo "📦 Testing quickscale_cli..."
# Run from root directory to use root Poetry environment (monorepo setup)
# Skip E2E tests (run separately with ./scripts/test_e2e.sh)
# Use package name (not src/) to avoid double-counting with pyproject.toml addopts
if ! run_pytest_stage \
  "quickscale_cli" \
  "quickscale_cli" \
  true \
  run_repo_tool pytest quickscale_cli/tests/ -m "not e2e"; then
  EXIT_CODE=1
fi

echo ""
echo "📦 Testing quickscale_modules..."
# Test modules using ROOT poetry environment (centralized dependencies)
# Modules are installed in editable mode via root pyproject.toml
# PYTHONPATH keeps the current module root first and adds sibling module src dirs
# so cross-module imports like notifications -> forms resolve during bootstrap.
if [ -d "quickscale_modules" ]; then
  for mod in quickscale_modules/*; do
    if [ -d "$mod" ]; then
      mod_name=$(basename "$mod")
      if [ -d "$mod/tests" ]; then
        echo "  → Testing module: $mod_name"
        # Package name format: quickscale_modules_<name> (underscores, not hyphens)
        pkg_name="quickscale_modules_${mod_name}"
        # Use ROOT poetry environment with PYTHONPATH pointing to module
        # Coverage uses package name (importable), not filesystem path
        if ! run_pytest_stage \
          "module ${mod_name}" \
          "$pkg_name" \
          false \
          run_with_pythonpath "$(build_module_pythonpath "$mod")${PYTHONPATH:+:$PYTHONPATH}" run_repo_tool pytest "$mod/tests/" \
            -p pytest_django --ds=tests.settings; then
          EXIT_CODE=1
        fi
      else
        echo "  → Skipping $mod_name (no tests/ directory)"
      fi
    fi
  done
else
  echo "  → No quickscale_modules directory found"
fi

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
