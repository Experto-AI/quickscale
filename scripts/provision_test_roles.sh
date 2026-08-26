#!/usr/bin/env bash
# provision_test_roles.sh — retained PostgreSQL test-role contract.
#
# With no options this preserves the historical restricted-role behavior and
# provisions the three RLS helper roles.  ``--profile bypassrls`` additionally
# provisions the dedicated BYPASSRLS login used by the nightly lane.

set -euo pipefail

PGHOST_VALUE="${PGHOST:-localhost}"
PGUSER_VALUE="${PGUSER:-postgres}"
PGPORT_VALUE="${PGPORT:-5432}"
USE_DOCKER=false
DOCKER_CONTAINER="${QS_PG_CONTAINER:-}"
PROFILE=restricted

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
safe_identifier() {
  [[ "$2" =~ ^[a-z][a-z0-9_]*$ && ${#2} -le 63 ]] || die "unsafe $1: $2"
}
safe_container_name() {
  [[ "$1" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || die "unsafe container: $1"
}

while (($#)); do
  case "$1" in
    -h|--host) (($# >= 2)) || die '--host requires a value'; PGHOST_VALUE="$2"; shift 2 ;;
    -U|--user) (($# >= 2)) || die '--user requires a value'; PGUSER_VALUE="$2"; shift 2 ;;
    -p|--port) (($# >= 2)) || die '--port requires a value'; PGPORT_VALUE="$2"; shift 2 ;;
    --docker) USE_DOCKER=true; shift ;;
    --container) (($# >= 2)) || die '--container requires a value'; DOCKER_CONTAINER="$2"; USE_DOCKER=true; shift 2 ;;
    --profile) (($# >= 2)) || die '--profile requires a value'; PROFILE="$2"; shift 2 ;;
    --help)
      cat <<'EOF'
Usage: provision_test_roles.sh [-h HOST] [-U USER] [-p PORT] [--docker]
       [--container NAME] [--profile restricted|bypassrls]

The default restricted profile provisions quickscale_test_role plus the two
non-login RLS helper roles.  The bypassrls profile also provisions
quickscale_bypassrls_test_role.
EOF
      exit 0
      ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "$PGPORT_VALUE" =~ ^[0-9]+$ && "$PGPORT_VALUE" -ge 1 && "$PGPORT_VALUE" -le 65535 ]] || die "invalid port: $PGPORT_VALUE"
[[ "$PGHOST_VALUE" != *$'\n'* && "$PGHOST_VALUE" != *$'\r'* && "$PGHOST_VALUE" != *[[:space:]]* ]] || die 'unsafe host'
[[ "$PROFILE" == restricted || "$PROFILE" == bypassrls ]] || die "unknown profile: $PROFILE"
safe_identifier user "$PGUSER_VALUE"

psql_cmd() {
  local -a command
  if [[ "$USE_DOCKER" == true ]]; then
    if [[ -z "$DOCKER_CONTAINER" ]]; then
      for candidate in pg18-af10 quickscale-postgres-1 postgres; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -Fxq "$candidate"; then
          DOCKER_CONTAINER="$candidate"
          break
        fi
      done
    fi
    [[ -n "$DOCKER_CONTAINER" ]] || die 'no PostgreSQL container found; set --container'
    safe_container_name "$DOCKER_CONTAINER"
    command=(docker exec -i "$DOCKER_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$PGUSER_VALUE")
  else
    command=(psql -X -v ON_ERROR_STOP=1 -h "$PGHOST_VALUE" -p "$PGPORT_VALUE" -U "$PGUSER_VALUE")
  fi
  "${command[@]}" "$@"
}

ensure_role() {
  local role="$1" flags="$2" expected="$3" actual
  safe_identifier role "$role"
  psql_cmd -d postgres -v "role_name=$role" -c "SELECT format('CREATE ROLE %I WITH ${flags}', :'role_name') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'role_name') \\gexec"
  psql_cmd -d postgres -v "role_name=$role" -c "SELECT format('ALTER ROLE %I WITH ${flags}', :'role_name') \\gexec"
  actual=$(psql_cmd -At -d postgres -v "role_name=$role" -c "SELECT rolcanlogin,rolcreatedb,rolinherit,rolbypassrls,rolsuper,rolcreaterole FROM pg_roles WHERE rolname=:'role_name'") || die "failed to verify $role"
  [[ "$actual" == "$expected" ]] || die "role postcondition failed for $role: $actual (expected $expected)"
}

ensure_role quickscale_test_role \
  'LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE' 't|t|f|f|f|f'
ensure_role quickscale_rls_test_role \
  'NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE' 'f|f|f|f|f|f'
ensure_role quickscale_rls_op_test_role \
  'NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE' 'f|f|f|f|f|f'

if [[ "$PROFILE" == bypassrls ]]; then
  ensure_role quickscale_bypassrls_test_role \
    'LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE' 't|t|f|t|f|f'
fi

for role in quickscale_test_role quickscale_rls_test_role quickscale_rls_op_test_role; do
  psql_cmd -d postgres -v "role_name=$role" -c "SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'role_name') \\gexec"
done
psql_cmd -d postgres -v role_name=quickscale_test_role -v inner_role=quickscale_rls_test_role -c \
  "SELECT format('GRANT %I TO %I', :'inner_role', :'role_name') \\gexec"
psql_cmd -d postgres -v role_name=quickscale_test_role -v inner_role=quickscale_rls_op_test_role -c \
  "SELECT format('GRANT %I TO %I', :'inner_role', :'role_name') \\gexec"

printf 'PostgreSQL test roles provisioned successfully (%s profile).\n' "$PROFILE"
