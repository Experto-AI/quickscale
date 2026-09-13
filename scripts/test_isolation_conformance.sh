#!/usr/bin/env bash
# test_isolation_conformance.sh — AF10 Isolation-Conformance CI Runner
#
# Runs the complete isolation-conformance test suite against the PostgreSQL
# lifecycle lease supplied by provision_ci_postgres.sh.
#
# Prerequisites:
#   - provision_ci_postgres.sh has supplied a validated isolation lease
#   - Poetry installed, dependencies installed
#
# What it runs:
#   1. Conformance gate — orgs test_tenant_table_conformance.py (PostgreSQL-only tests)
#   2. RLS boundary tests — each module's test_rls_boundary.py
#   3. CRM authenticated-request isolation test — test_isolation.py
#
# Fails if any isolation test is skipped (ensures the gate cannot pass by skipping).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# PostgreSQL client helper. The validated lease supplies the dynamic endpoint;
# there is deliberately no host-service or alternate-container fallback.
# ---------------------------------------------------------------------------
_PSQL() {
  psql -X -v ON_ERROR_STOP=1 \
    -h "${PGHOST:-localhost}" \
    -p "${PGPORT:?validated PostgreSQL lease did not set PGPORT}" \
    -U "${QS_ORGS_DB_USER:-quickscale_test_role}" "$@"
}

# Hosted workflows run the isolation helper profile against their PostgreSQL
# service container. Local calls revalidate inherited markers against the live
# isolation lease rather than trusting marker equality.
if [[ "${GITHUB_ACTIONS:-}" != true ]]; then
  if [[ -z "${QUICKSCALE_POSTGRES_LEASE_TOKEN:-}" || "${QUICKSCALE_POSTGRES_LEASE_VALIDATED:-}" != "$QUICKSCALE_POSTGRES_LEASE_TOKEN" ]]; then
    exec "$REPO_ROOT/scripts/provision_ci_postgres.sh" run \
      --profile isolation -- "$REPO_ROOT/scripts/test_isolation_conformance.sh" "$@"
  fi
  "$REPO_ROOT/scripts/provision_ci_postgres.sh" validate --profile isolation
fi

echo "=== Using validated PostgreSQL isolation lease ==="

# ---------------------------------------------------------------------------
# Track results
# ---------------------------------------------------------------------------
PASS=0
FAIL=0
ISOLATION_XML_DIR="$(mktemp -d)"
PYTEST_BASE=(-o "addopts=" --tb=long -ra)

cleanup() {
  rm -rf "$ISOLATION_XML_DIR"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Helper: build PYTHONPATH for a module (matches test_unit.sh pattern)
# ---------------------------------------------------------------------------
build_module_pythonpath() {
  local module_path="$1"
  local path_entries=("$module_path" ".")

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

# ---------------------------------------------------------------------------
# Helper: run one isolation test suite
# ---------------------------------------------------------------------------
run_suite() {
  local suite_name="$1"
  local settings_module="$2"
  local module_dir="$3"
  shift 3
  local test_paths=("$@")
  local xml_file="${ISOLATION_XML_DIR}/${suite_name//\//_}.xml"

  echo ""
  echo "=== [${suite_name}] ==="
  echo "  Settings: ${settings_module}"
  echo "  Module:   ${module_dir}"
  echo "  Tests:    ${test_paths[*]}"

  local pythonpath
  pythonpath="$(build_module_pythonpath "$module_dir")"

  if PYTHONPATH="${pythonpath}${PYTHONPATH:+:$PYTHONPATH}" \
     poetry run pytest "${test_paths[@]}" \
       -p pytest_django --ds="$settings_module" \
       "${PYTEST_BASE[@]}" \
       --junitxml="$xml_file" \
       -v; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# 1. Conformance gate (orgs) — PostgreSQL-only tests
# ---------------------------------------------------------------------------
run_suite \
  "orgs-conformance" \
  "tests.settings" \
  "quickscale_modules/orgs" \
  "quickscale_modules/orgs/tests/test_tenant_table_conformance.py"

# ---------------------------------------------------------------------------
# 2. Module RLS boundary tests — each module's test_rls_boundary.py
# ---------------------------------------------------------------------------
RLS_MODULES=(billing blog crm forms listings)
for mod in "${RLS_MODULES[@]}"; do
  test_file="quickscale_modules/${mod}/tests/test_rls_boundary.py"
  if [ -f "$test_file" ]; then
    run_suite \
      "rls-${mod}" \
      "tests.settings" \
      "quickscale_modules/${mod}" \
      "$test_file"
  fi
done

# ---------------------------------------------------------------------------
# 3. CRM authenticated-request isolation test
# ---------------------------------------------------------------------------
run_suite \
  "crm-isolation" \
  "tests.settings" \
  "quickscale_modules/crm" \
  "quickscale_modules/crm/tests/test_isolation.py"

# ---------------------------------------------------------------------------
# 4. Check for skipped tests across all JUnit XML files
# ---------------------------------------------------------------------------
echo ""
echo "=== Checking for skipped tests ==="
SKIPPED_FOUND=0
for xml_file in "${ISOLATION_XML_DIR}"/*.xml; do
  [ -f "$xml_file" ] || continue

  skip_report=$(python3 -c "
import xml.etree.ElementTree as ET

tree = ET.parse('${xml_file}')
skipped_tests = []
for case in tree.getroot().findall('.//testcase'):
    for skipped in case.findall('skipped'):
        message = skipped.get('message', '')
        skipped_tests.append(f\"{case.get('name')}: {message}\")
print(len(skipped_tests))
for line in skipped_tests:
    print(line)
")
  skip_count=$(printf '%s\n' "$skip_report" | head -1)
  suite_name=$(basename "$xml_file" .xml)
  if [ "$skip_count" -gt 0 ]; then
    echo "  FAIL: ${skip_count} test(s) skipped in ${suite_name}"
    printf '%s\n' "$skip_report" | tail -n +2 | sed 's/^/    /'
    SKIPPED_FOUND=1
  fi
done

if [ "$SKIPPED_FOUND" -eq 1 ]; then
  echo ""
  echo "❌ Some isolation tests were skipped — isolation-conformance gate FAILED"
  echo "   All isolation tests must run under PostgreSQL. Check environment."
  exit 1
fi
echo "  ✓ No isolation tests skipped"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Isolation-Conformance Summary ==="
echo "  Passed suites: ${PASS}"
echo "  Failed suites: ${FAIL}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "✅ All isolation-conformance suites passed!"
else
  echo "❌ ${FAIL} isolation-conformance suite(s) failed!"
  exit 1
fi
