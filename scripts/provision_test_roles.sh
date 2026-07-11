#!/usr/bin/env bash
# provision_test_roles.sh — SA59.3 Retained-role contract provisioning
#
# Creates/updates all test PostgreSQL roles cluster-wide:
#
#   1. quickscale_test_role  — direct-connection role for module test suites
#      Contract: LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE
#
#   2. quickscale_rls_test_role — inner restricted role for RLS boundary tests
#      Contract: NOBYPASSRLS NOINHERIT NOLOGIN
#
#   3. quickscale_rls_op_test_role — operator-access cross-tenant proof role
#      Contract: NOBYPASSRLS NOINHERIT NOLOGIN
#
# Usage:
#   ./scripts/provision_test_roles.sh          # uses psql (localhost:5432, postgres user)
#   ./scripts/provision_test_roles.sh -h <host> -U <user>  # custom connection
#
# Prerequisites:
#   - PostgreSQL 18 running with trust authentication (or configured pgpass)
#   - psql client available (or use --docker flag for docker exec)
#
# SA59.3: Every test-database role creation path (CI and local) must assert
# the full role contract explicitly.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Connection defaults
# ---------------------------------------------------------------------------
PGHOST="${PGHOST:-localhost}"
PGUSER="${PGUSER:-postgres}"
USE_DOCKER=false
DOCKER_CONTAINER="${QS_PG_CONTAINER:-}"

_PSQL() {
  if [ "$USE_DOCKER" = true ]; then
    local container="$DOCKER_CONTAINER"
    if [ -z "$container" ]; then
      # Try common container names
      for candidate in pg18-af10 quickscale-postgres-1 postgres; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$candidate"; then
          container="$candidate"
          break
        fi
      done
    fi
    if [ -z "$container" ]; then
      echo "ERROR: No PostgreSQL container found. Set QS_PG_CONTAINER or start one." >&2
      exit 1
    fi
    docker exec -i "$container" psql -U "$PGUSER" "$@"
  else
    psql -h "$PGHOST" -U "$PGUSER" "$@"
  fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host) PGHOST="$2"; shift 2 ;;
    -U|--user) PGUSER="$2"; shift 2 ;;
    --docker) USE_DOCKER=true; shift ;;
    --container) DOCKER_CONTAINER="$2"; USE_DOCKER=true; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -h, --host HOST       PostgreSQL host (default: localhost)"
      echo "  -U, --user USER       PostgreSQL user (default: postgres)"
      echo "  --docker              Use docker exec instead of psql"
      echo "  --container NAME      Docker container name (implies --docker)"
      echo "  --help                Show this help message"
      echo ""
      echo "Creates/updates quickscale_test_role and quickscale_rls_test_role"
      echo "with the SA59.3 retained-role contract."
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "=== Provisioning PostgreSQL test roles ==="

# ---------------------------------------------------------------------------
# 1. quickscale_test_role — direct-connection integration role
#    Contract: LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE
# ---------------------------------------------------------------------------
ROLE="quickscale_test_role"
echo ""
echo "--- ${ROLE} ---"

# Create or update the role with the full SA59.3 contract.
# Uses ALTER ROLE when the role already exists (idempotent).
_PSQL -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = '${ROLE}'" \
  | grep -q 1 \
  && EXISTING=true \
  || EXISTING=false

if [ "$EXISTING" = true ]; then
  _PSQL -c \
    "ALTER ROLE ${ROLE} WITH LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${ROLE} updated with LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE"
else
  _PSQL -c \
    "CREATE ROLE ${ROLE} WITH LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${ROLE} created with LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE"
fi

# Verify every required attribute
echo "  Verifying attributes..."
for attr in rolbypassrls rolsuper rolinherit rolcreaterole; do
  val=$(_PSQL -tc "SELECT ${attr} FROM pg_roles WHERE rolname = '${ROLE}'" | tr -d ' ')
  expected="f"
  if [ "$val" != "$expected" ]; then
    echo "  ERROR: ${ROLE} has ${attr}=${val} (expected ${expected})" >&2
    exit 1
  fi
done
echo "  ✓ All attributes verified"

# Verify login and createdb are set
for attr in rolcanlogin rolcreatedb; do
  val=$(_PSQL -tc "SELECT ${attr} FROM pg_roles WHERE rolname = '${ROLE}'" | tr -d ' ')
  expected="t"
  if [ "$val" != "$expected" ]; then
    echo "  ERROR: ${ROLE} has ${attr}=${val} (expected ${expected})" >&2
    exit 1
  fi
done
echo "  ✓ LOGIN and CREATEDB verified"

# ---------------------------------------------------------------------------
# 2. quickscale_rls_test_role — inner restricted role for RLS boundary tests
#    Contract: NOBYPASSRLS NOINHERIT NOLOGIN
# ---------------------------------------------------------------------------
INNER_ROLE="quickscale_rls_test_role"
echo ""
echo "--- ${INNER_ROLE} ---"

_PSQL -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = '${INNER_ROLE}'" \
  | grep -q 1 \
  && INNER_EXISTS=true \
  || INNER_EXISTS=false

if [ "$INNER_EXISTS" = true ]; then
  _PSQL -c \
    "ALTER ROLE ${INNER_ROLE} WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${INNER_ROLE} updated with NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
else
  _PSQL -c \
    "CREATE ROLE ${INNER_ROLE} WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${INNER_ROLE} created with NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
fi

# Verify attributes for inner role
echo "  Verifying attributes..."
for attr in rolbypassrls rolsuper rolinherit rolcanlogin rolcreaterole; do
  val=$(_PSQL -tc "SELECT ${attr} FROM pg_roles WHERE rolname = '${INNER_ROLE}'" | tr -d ' ')
  expected="f"
  if [ "$val" != "$expected" ]; then
    echo "  ERROR: ${INNER_ROLE} has ${attr}=${val} (expected ${expected})" >&2
    exit 1
  fi
done
echo "  ✓ All attributes verified"

# ---------------------------------------------------------------------------
# 3. quickscale_rls_op_test_role — operator-access cross-tenant read-only proof
#    Contract: NOBYPASSRLS NOINHERIT NOLOGIN
# ---------------------------------------------------------------------------
OP_ROLE="quickscale_rls_op_test_role"
echo ""
echo "--- ${OP_ROLE} ---"

_PSQL -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = '${OP_ROLE}'" \
  | grep -q 1 \
  && OP_EXISTS=true \
  || OP_EXISTS=false

if [ "$OP_EXISTS" = true ]; then
  _PSQL -c \
    "ALTER ROLE ${OP_ROLE} WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${OP_ROLE} updated with NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
else
  _PSQL -c \
    "CREATE ROLE ${OP_ROLE} WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
  echo "  ✓ ${OP_ROLE} created with NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
fi

# Verify attributes for operator role
echo "  Verifying attributes..."
for attr in rolbypassrls rolsuper rolinherit rolcanlogin rolcreaterole; do
  val=$(_PSQL -tc "SELECT ${attr} FROM pg_roles WHERE rolname = '${OP_ROLE}'" | tr -d ' ')
  expected="f"
  if [ "$val" != "$expected" ]; then
    echo "  ERROR: ${OP_ROLE} has ${attr}=${val} (expected ${expected})" >&2
    exit 1
  fi
done
echo "  ✓ All attributes verified"

# ---------------------------------------------------------------------------
# 4. Grant USAGE ON SCHEMA public (idempotent)
# ---------------------------------------------------------------------------
echo ""
echo "--- Schema grants ---"
_PSQL -c "GRANT USAGE ON SCHEMA public TO ${ROLE}" 2>/dev/null || echo "  (schema usage already granted for ${ROLE})"
_PSQL -c "GRANT USAGE ON SCHEMA public TO ${INNER_ROLE}" 2>/dev/null || echo "  (schema usage already granted for ${INNER_ROLE})"
_PSQL -c "GRANT USAGE ON SCHEMA public TO ${OP_ROLE}" 2>/dev/null || echo "  (schema usage already granted for ${OP_ROLE})"
echo "  ✓ Schema grants applied"

# ---------------------------------------------------------------------------
# 5. Grant role membership — quickscale_test_role must be able to SET ROLE
#    to the RLS roles for RLS-boundary tests.  (CR-SA59-3-001)
# ---------------------------------------------------------------------------
echo ""
echo "--- Role membership grants ---"
_PSQL -c "GRANT ${INNER_ROLE} TO ${ROLE}"
_PSQL -c "GRANT ${OP_ROLE} TO ${ROLE}"
echo "  ✓ ${ROLE} granted membership in ${INNER_ROLE} and ${OP_ROLE}"

echo ""
echo "=== PostgreSQL test roles provisioned successfully ==="
echo ""
echo "  ${ROLE}:     LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE"
echo "  ${INNER_ROLE}: NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
echo "  ${OP_ROLE}:  NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE"
