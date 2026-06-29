#!/usr/bin/env bash
# test_isolation_conformance.sh — AF10 Isolation-Conformance CI Runner
#
# Runs the complete isolation-conformance test suite against a live PostgreSQL
# instance.  Intended for CI (isolation-conformance job) and for local
# verification after a local PostgreSQL service is started.
#
# Prerequisites:
#   - PostgreSQL 18 running on localhost:5432
#   - All test databases pre-created (see ci.yml create-test-databases step)
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
# PostgreSQL client helper — use local psql when available, fall back to
# docker exec for local validation (psql may not be on PATH).
# Override the container name via QS_PG_CONTAINER env var.
# ---------------------------------------------------------------------------
_PSQL() {
  if command -v psql >/dev/null 2>&1; then
    psql -h localhost -U postgres "$@"
  else
    local container="${QS_PG_CONTAINER:-pg18-af10}"
    docker exec -i "$container" psql -U postgres "$@"
  fi
}

# ---------------------------------------------------------------------------
# Create the restricted PostgreSQL role (idempotent, cluster-wide)
# ---------------------------------------------------------------------------
_RESTRICTED_ROLE="quickscale_rls_test_role"

echo "=== Setting up PostgreSQL restricted role ==="
_PSQL -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = '${_RESTRICTED_ROLE}'" \
  | grep -q 1 \
  || _PSQL -c \
    "CREATE ROLE ${_RESTRICTED_ROLE} NOBYPASSRLS NOINHERIT NOLOGIN"

# Verify the role was created correctly.
ROLE_BYPASS=$(_PSQL -tc \
  "SELECT rolbypassrls FROM pg_roles WHERE rolname = '${_RESTRICTED_ROLE}'" \
  | tr -d ' ')
if [ "$ROLE_BYPASS" != "f" ]; then
  echo "ERROR: ${_RESTRICTED_ROLE} has BYPASSRLS enabled - isolation test would be invalid!"
  exit 1
fi
echo "  ✓ ${_RESTRICTED_ROLE} created with NOBYPASSRLS"

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

  skip_count=$(python3 -c "
import sys, xml.etree.ElementTree as ET
tree = ET.parse('${xml_file}')
root = tree.getroot()
skipped = root.findall('.//testcase/skipped')
print(len(skipped))
")
  suite_name=$(basename "$xml_file" .xml)
  if [ "$skip_count" -gt 0 ]; then
    echo "  FAIL: ${skip_count} test(s) skipped in ${suite_name}"
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
