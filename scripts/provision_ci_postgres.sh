#!/usr/bin/env bash
# provision_ci_postgres.sh — the single PostgreSQL environment contract.
#
# ``describe`` is deliberately a pure projection of the repository's module
# discovery shim and the profile table below.  ``hosted-setup`` and ``run``
# consume that projection; neither command is permitted to invent a second
# module or database list.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-$(command -v python3 || true)}"
DISCOVERY_SHIM="$ROOT/quickscale_core/src/quickscale_core/contracts/module_discovery.py"
POSTGRES_MAJOR=18
OWNER_LABEL="label=com.quickscale.owner=quickscale"
LIFECYCLE_LABEL="label=com.quickscale.lifecycle=integration"

MODULES=()
DATABASE_KEYS=()
DATABASE_NAMES=()
DATABASE_MODULES=()
MAPPING_MODULES=()
ROLE_NAME=""
ROLE_FLAGS=()
ALLOW_BYPASS="0"
PROFILE=""
MODE=""
SCOPE=""
PGHOST_VALUE=""
PGPORT_VALUE=""
DESCRIPTION_DIGEST=""
LEASE_DIR=""
LEASE_FILE=""
LEASE_TOKEN=""
CONTAINER_ID=""
CHILD_PID=""
CHILD_PGID=""
PENDING_CHILD_SIGNAL=""
PENDING_CHILD_STATUS=""

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  scripts/provision_ci_postgres.sh describe --profile PROFILE --format json
  scripts/provision_ci_postgres.sh hosted-setup --profile PROFILE
  scripts/provision_ci_postgres.sh run --profile PROFILE -- COMMAND [ARG ...]
  scripts/provision_ci_postgres.sh validate --profile PROFILE

Profiles: backups, restricted, isolation, bypassrls, client-only.
EOF
}

validate_word() {
  local label="$1" value="$2"
  [[ -n "$value" && "$value" != *$'\n'* && "$value" != *$'\r'* ]] || die "$label is empty or contains a newline"
}

validate_identifier() {
  local label="$1" value="$2"
  [[ "$value" =~ ^[a-z][a-z0-9_]*$ ]] || die "unsafe $label: $value"
  ((${#value} <= 63)) || die "$label exceeds PostgreSQL's 63-byte limit: $value"
}

validate_host_port() {
  PGHOST_VALUE="${PGHOST:-localhost}"
  PGPORT_VALUE="${PGPORT:-5432}"
  validate_word PGHOST "$PGHOST_VALUE"
  [[ "$PGHOST_VALUE" != *[[:space:]]* ]] || die "unsafe PGHOST"
  [[ "$PGPORT_VALUE" =~ ^[0-9]+$ && "$PGPORT_VALUE" -ge 1 && "$PGPORT_VALUE" -le 65535 ]] || die "invalid PGPORT: $PGPORT_VALUE"
}

load_inventory() {
  [[ -f "$DISCOVERY_SHIM" ]] || die "module discovery shim not found: $DISCOVERY_SHIM"
  local output
  output=$("$PYTHON" "$DISCOVERY_SHIM" --list-modules) || die "authoritative module discovery failed"
  [[ -n "$output" ]] || die "authoritative module inventory is empty"
  MODULES=()
  local item previous=""
  declare -A seen=()
  while IFS= read -r item; do
    [[ -n "$item" ]] || die "module inventory contains an empty entry"
    validate_identifier module "$item"
    [[ -z "${seen[$item]+present}" ]] || die "module inventory contains duplicate: $item"
    seen["$item"]=1
    [[ -z "$previous" || "$previous" < "$item" ]] || die "module inventory is not sorted"
    previous="$item"
    [[ "$item" != teams ]] || die "placeholder module is not provisionable: teams"
    MODULES+=("$item")
  done <<< "$output"
  ((${#MODULES[@]} == 12)) || die "module inventory count drift: expected 12, found ${#MODULES[@]}"
}

profile_scope() {
  local requested="${QS_PROVISION_SCOPE:-local_${BASHPID}}"
  [[ "$requested" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]] || die "unsafe provision scope"
  SCOPE="$requested"
}

build_profile() {
  PROFILE="$1"
  case "$PROFILE" in
    backups|restricted|isolation|bypassrls|client-only) ;;
    *) die "unknown profile: $PROFILE" ;;
  esac
  load_inventory
  DATABASE_KEYS=()
  DATABASE_NAMES=()
  DATABASE_MODULES=()
  MAPPING_MODULES=()
  ROLE_NAME=""
  ROLE_FLAGS=()
  ALLOW_BYPASS="0"
  local hosted_names="${QS_PROVISION_HOSTED:-0}"
  local prefix="test_quickscale"
  if [[ "$hosted_names" != 1 && "$hosted_names" != true ]]; then
    profile_scope
    prefix="test_qs_${PROFILE}_${SCOPE}"
  fi

  case "$PROFILE" in
    backups)
      DATABASE_KEYS=(backups); DATABASE_NAMES=(test_quickscale_backups); DATABASE_MODULES=(backups)
      MAPPING_MODULES=(backups); ROLE_NAME=postgres
      ROLE_FLAGS=(SUPERUSER LOGIN CREATEDB INHERIT BYPASSRLS CREATEROLE)
      ;;
    client-only) ;;
    *)
      DATABASE_KEYS=(smoke); DATABASE_NAMES=(test_quickscale_smoke); DATABASE_MODULES=(smoke)
      if [[ "$hosted_names" != 1 && "$hosted_names" != true ]]; then
        DATABASE_NAMES=("${prefix}_smoke")
      fi
      for item in "${MODULES[@]}"; do
        if [[ "$PROFILE" == isolation && "$item" == backups ]]; then
          continue
        fi
        DATABASE_KEYS+=("$item")
        DATABASE_MODULES+=("$item")
        if [[ "$hosted_names" == 1 || "$hosted_names" == true ]]; then
          DATABASE_NAMES+=("test_quickscale_$item")
        else
          DATABASE_NAMES+=("${prefix}_${item}")
        fi
      done
      case "$PROFILE" in
        restricted) MAPPING_MODULES=("${MODULES[@]}"); ROLE_NAME=quickscale_test_role; ROLE_FLAGS=(LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE) ;;
        isolation) MAPPING_MODULES=(orgs billing blog crm forms listings); ROLE_NAME=quickscale_test_role; ROLE_FLAGS=(LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE) ;;
        bypassrls) MAPPING_MODULES=("${MODULES[@]}"); ROLE_NAME=quickscale_bypassrls_test_role; ROLE_FLAGS=(LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE); ALLOW_BYPASS=1 ;;
      esac
      ;;
  esac
  for item in "${DATABASE_NAMES[@]}"; do validate_identifier database "$item"; done
  if [[ "$PROFILE" != client-only ]]; then
    validate_identifier role "$ROLE_NAME"
  fi
}

json_escape() {
  local value="$1"
  value=${value//\\/\\\\}; value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}; value=${value//$'\r'/\\r}
  printf '%s' "$value"
}

json_string_array() {
  local first=true item
  printf '['
  for item in "$@"; do
    $first || printf ','
    first=false
    printf '"%s"' "$(json_escape "$item")"
  done
  printf ']'
}

description_json() {
  local first=true i module env_prefix database_name key
  printf '{"schema_version":1,"profile":"%s","discovery":{"command":["%s","%s","--list-modules"],"source":"%s","modules":' \
    "$(json_escape "$PROFILE")" "$(json_escape "$PYTHON")" "$(json_escape "$DISCOVERY_SHIM")" "$(json_escape "$DISCOVERY_SHIM")"
  json_string_array "${MODULES[@]}"
  printf '},"databases":['
  for ((i=0; i<${#DATABASE_NAMES[@]}; i++)); do
    $first || printf ','; first=false
    printf '{"key":"%s","module":' "$(json_escape "${DATABASE_KEYS[$i]}")"
    printf '%s' "$( [[ "${DATABASE_MODULES[$i]}" == smoke ]] && printf 'null' || printf '"%s"' "$(json_escape "${DATABASE_MODULES[$i]}")" )"
    printf ',"name":"%s"}' "$(json_escape "${DATABASE_NAMES[$i]}")"
  done
  printf '],"role":{"name":"%s","flags":' "$(json_escape "$ROLE_NAME")"
  json_string_array "${ROLE_FLAGS[@]}"
  local bypass_json=false
  [[ "$ALLOW_BYPASS" == 1 ]] && bypass_json=true
  printf ',"allow_bypassrls":%s},"environment":{' "$bypass_json"
  first=true
  for module in "${MAPPING_MODULES[@]}"; do
    env_prefix="QS_${module^^}_DB"
    for key in NAME USER HOST PORT; do
      $first || printf ','; first=false
      case "$key" in
        NAME) database_name=""; for ((i=0; i<${#DATABASE_MODULES[@]}; i++)); do [[ "${DATABASE_MODULES[$i]}" == "$module" ]] && database_name="${DATABASE_NAMES[$i]}"; done; value="$database_name" ;;
        USER) value="$ROLE_NAME" ;;
        HOST) value="${PGHOST_VALUE:-localhost}" ;;
        PORT) value="${PGPORT_VALUE:-5432}" ;;
      esac
      printf '"%s":"%s"' "${env_prefix}_${key}" "$(json_escape "$value")"
    done
  done
  if [[ "$PROFILE" != client-only && "$PROFILE" != backups ]]; then
    $first || printf ','
    printf '"QUICKSCALE_ALLOW_BYPASSRLS":"%s"' "$ALLOW_BYPASS"
  fi
  printf '},"endpoint":{"host":"%s","port":"%s"}}\n' \
    "$(json_escape "${PGHOST_VALUE:-localhost}")" "$(json_escape "${PGPORT_VALUE:-5432}")"
}

psql_run() {
  local database="$1" sql="$2"; shift 2
  local -a args=(psql -X -v ON_ERROR_STOP=1 -h "$PGHOST_VALUE" -p "$PGPORT_VALUE" -U "${PGUSER:-postgres}" -d "$database")
  args+=(-v "db_name=$database")
  while (($#)); do args+=(-v "$1"); shift; done
  # psql only performs variable interpolation for script input (not a
  # command supplied with -c on current client releases). Feeding the
  # validated statement through stdin preserves quoted variables and gexec.
  "${args[@]}" <<< "$sql"
}

export_environment() {
  local module key env_prefix database_name value i
  for module in "${MAPPING_MODULES[@]}"; do
    env_prefix="QS_${module^^}_DB"
    for key in NAME USER HOST PORT; do
      case "$key" in
        NAME) database_name=""; for ((i=0; i<${#DATABASE_MODULES[@]}; i++)); do [[ "${DATABASE_MODULES[$i]}" == "$module" ]] && database_name="${DATABASE_NAMES[$i]}"; done; value="$database_name" ;;
        USER) value="$ROLE_NAME" ;;
        HOST) value="$PGHOST_VALUE" ;;
        PORT) value="$PGPORT_VALUE" ;;
      esac
      export "${env_prefix}_${key}=$value"
    done
  done
  if [[ "$PROFILE" != client-only && "$PROFILE" != backups ]]; then
    export QUICKSCALE_ALLOW_BYPASSRLS="$ALLOW_BYPASS"
  fi
}

validate_environment() {
  local module key env_prefix database_name expected actual i variable
  for module in "${MAPPING_MODULES[@]}"; do
    env_prefix="QS_${module^^}_DB"
    for key in NAME USER HOST PORT; do
      case "$key" in
        NAME) database_name=""; for ((i=0; i<${#DATABASE_MODULES[@]}; i++)); do [[ "${DATABASE_MODULES[$i]}" == "$module" ]] && database_name="${DATABASE_NAMES[$i]}"; done; expected="$database_name" ;;
        USER) expected="$ROLE_NAME" ;;
        HOST) expected="$PGHOST_VALUE" ;;
        PORT) expected="$PGPORT_VALUE" ;;
      esac
      variable="${env_prefix}_${key}"
      actual="${!variable-}"
      [[ "$actual" == "$expected" ]] || die "$variable does not match the validated PostgreSQL profile"
    done
  done
  if [[ "$PROFILE" != client-only && "$PROFILE" != backups ]]; then
    [[ "${QUICKSCALE_ALLOW_BYPASSRLS-}" == "$ALLOW_BYPASS" ]] || die "QUICKSCALE_ALLOW_BYPASSRLS does not match the validated PostgreSQL profile"
  fi
}

verify_clients() {
  local tool version
  for tool in psql pg_dump pg_restore; do
    command -v "$tool" >/dev/null 2>&1 || die "required PostgreSQL client is unavailable: $tool"
    version=$("$tool" --version 2>/dev/null) || die "cannot execute PostgreSQL client: $tool"
    [[ "$version" =~ (PostgreSQL\)[[:space:]]+|PostgreSQL[[:space:]]+)18([.]|$) ]] || die "$tool is not PostgreSQL 18: $version"
  done
}

install_hosted_clients() {
  # Subshell: verify_clients dies via `exit`, which would otherwise end the
  # whole script (silently, with stderr discarded) instead of installing.
  (verify_clients) 2>/dev/null || {
    command -v apt-get >/dev/null 2>&1 || die "apt-get is required to install PostgreSQL 18 clients"
    local -a elevate=()
    if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
      command -v sudo >/dev/null 2>&1 || die "sudo is required to install PostgreSQL 18 clients"
      elevate=(sudo)
    fi
    "${elevate[@]}" apt-get update
    "${elevate[@]}" apt-get install -y ca-certificates curl
    local distro_codename
    distro_codename=$(. /etc/os-release; printf '%s' "${VERSION_CODENAME:-}")
    validate_word VERSION_CODENAME "$distro_codename"
    "${elevate[@]}" install -d /usr/share/postgresql-common/pgdg
    "${elevate[@]}" curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
    printf 'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] http://apt.postgresql.org/pub/repos/apt %s-pgdg main\n' "$distro_codename" \
      | "${elevate[@]}" tee /etc/apt/sources.list.d/pgdg.list >/dev/null
    "${elevate[@]}" apt-get update
    "${elevate[@]}" apt-get install -y postgresql-client-18
    export PATH="/usr/lib/postgresql/18/bin:$PATH"
    if [[ -n "${GITHUB_PATH:-}" ]]; then
      [[ ! -L "$GITHUB_PATH" ]] || die "GITHUB_PATH must not be a symlink"
      printf '%s\n' /usr/lib/postgresql/18/bin >> "$GITHUB_PATH"
    fi
  }
  verify_clients
}

write_lease() {
  local base="$1" mode="$2" endpoint_host="$3" endpoint_port="$4"
  local previous_umask
  [[ -n "$base" && -d "$base" ]] || die "lease parent is unavailable"
  LEASE_DIR=$(mktemp -d "$base/quickscale-postgres.XXXXXX")
  chmod 700 "$LEASE_DIR"
  LEASE_FILE="$LEASE_DIR/lease"
  previous_umask=$(umask)
  umask 077
  LEASE_TOKEN=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  [[ ${#LEASE_TOKEN} -eq 64 ]] || die "high-entropy lease token unavailable"
  printf 'mode=%s\nprofile=%s\nendpoint_host=%s\nendpoint_port=%s\nscope=%s\ncontainer_id=%s\nhelper_pid=%s\ndescription_digest=%s\ntoken=%s\n' \
    "$mode" "$PROFILE" "$endpoint_host" "$endpoint_port" "$SCOPE" "$CONTAINER_ID" "$$" "$DESCRIPTION_DIGEST" "$LEASE_TOKEN" > "$LEASE_FILE"
  chmod 600 "$LEASE_FILE"
  umask "$previous_umask"
  export QUICKSCALE_POSTGRES_LEASE="$LEASE_FILE" QUICKSCALE_POSTGRES_LEASE_TOKEN="$LEASE_TOKEN"
}

read_lease_value() {
  local key="$1" file="$2" line value found=""
  while IFS='=' read -r line value; do
    [[ "$line" == "$key" ]] && found="$value"
  done < "$file"
  printf '%s' "$found"
}

is_live_ancestor() {
  local owner="$1" current="$$" parent
  while [[ "$current" =~ ^[0-9]+$ && "$current" -gt 1 ]]; do
    [[ "$current" == "$owner" ]] && return 0
    parent=""
    while read -r field value _rest; do
      [[ "$field" == PPid: ]] && parent="$value" && break
    done < "/proc/$current/status" 2>/dev/null || return 1
    [[ "$parent" =~ ^[0-9]+$ && "$parent" != "$current" ]] || return 1
    current="$parent"
  done
  return 1
}

validate_lease() {
  local file="${QUICKSCALE_POSTGRES_LEASE:-}" token="${QUICKSCALE_POSTGRES_LEASE_TOKEN:-}"
  [[ -n "$file" && -f "$file" && ! -L "$file" ]] || die "malformed or stale PostgreSQL lease"
  local dir; dir=$(dirname -- "$file")
  [[ "$(stat -c '%a' "$dir")" == 700 && "$(stat -c '%a' "$file")" == 600 ]] || die "PostgreSQL lease permissions are unsafe"
  local record_token; record_token=$(read_lease_value token "$file")
  [[ -n "$token" && "$token" == "$record_token" ]] || die "forged PostgreSQL lease token"
  [[ "$(read_lease_value profile "$file")" == "$PROFILE" ]] || die "profile-mismatched PostgreSQL lease"
  [[ "$(read_lease_value mode "$file")" == local ]] || die "lease mode is not local"
  [[ "$(read_lease_value endpoint_host "$file")" == "$PGHOST_VALUE" && "$(read_lease_value endpoint_port "$file")" == "$PGPORT_VALUE" ]] || die "lease endpoint does not match"
  local owner; owner=$(read_lease_value helper_pid "$file")
  [[ "$owner" =~ ^[0-9]+$ ]] || die "lease helper PID is invalid"
  kill -0 "$owner" 2>/dev/null || die "stale PostgreSQL lease"
  is_live_ancestor "$owner" || die "PostgreSQL lease helper is not a live ancestor"
  local container; container=$(read_lease_value container_id "$file")
  [[ -n "$container" ]] || die "lease has no owned container"
  docker inspect --type container --format '{{index .Config.Labels "com.quickscale.owner"}}|{{index .Config.Labels "com.quickscale.lifecycle"}}|{{index .Config.Labels "com.quickscale.scope"}}' "$container" 2>/dev/null | grep -Fx "quickscale|integration|$(read_lease_value scope "$file")" >/dev/null || die "lease container labels do not match"
  local record_digest current_digest
  record_digest=$(read_lease_value description_digest "$file")
  [[ "$record_digest" =~ ^[0-9a-f]{64}$ ]] || die "lease description digest is invalid"
  current_digest=$(printf '%s' "$(description_json)" | sha256sum | cut -d' ' -f1)
  [[ "$record_digest" == "$current_digest" ]] || die "lease description digest does not match the current profile"
}

validate_hosted_lease() {
  local file="${QUICKSCALE_POSTGRES_LEASE:-}" token="${QUICKSCALE_POSTGRES_LEASE_TOKEN:-}"
  [[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || die "hosted lease requires GitHub Actions"
  [[ -n "$file" && -f "$file" && ! -L "$file" && "$file" == "$RUNNER_TEMP"/* ]] || die "malformed hosted PostgreSQL lease"
  local dir; dir=$(dirname -- "$file")
  [[ "$(stat -c '%a' "$dir")" == 700 && "$(stat -c '%a' "$file")" == 600 ]] || die "hosted lease permissions are unsafe"
  [[ "$token" =~ ^[0-9a-f]{64}$ && "$token" == "$(read_lease_value token "$file")" ]] || die "forged hosted PostgreSQL lease token"
  [[ "$(read_lease_value mode "$file")" == hosted && "$(read_lease_value profile "$file")" == "$PROFILE" ]] || die "hosted lease profile or mode mismatch"
  [[ "$(read_lease_value endpoint_host "$file")" == "$PGHOST_VALUE" && "$(read_lease_value endpoint_port "$file")" == "$PGPORT_VALUE" ]] || die "hosted lease endpoint mismatch"
  local record_digest current_digest
  record_digest=$(read_lease_value description_digest "$file")
  current_digest=$(printf '%s' "$(description_json)" | sha256sum | cut -d' ' -f1)
  [[ "$record_digest" =~ ^[0-9a-f]{64}$ && "$record_digest" == "$current_digest" && "$(read_lease_value postconditions "$file")" == verified ]] || die "hosted lease postconditions or profile digest are unverified"
}

provision_role() {
  [[ "$PROFILE" != client-only && "$PROFILE" != backups ]] || return 0
  local flags="${ROLE_FLAGS[*]}"
  psql_run postgres "SELECT format('CREATE ROLE %I WITH ${flags}', :'role_name') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role_name') \\gexec" "role_name=$ROLE_NAME"
  psql_run postgres "SELECT format('ALTER ROLE %I WITH ${flags}', :'role_name') \\gexec" "role_name=$ROLE_NAME"
  local actual
    actual=$(psql -X -At -v ON_ERROR_STOP=1 -h "$PGHOST_VALUE" -p "$PGPORT_VALUE" -U "${PGUSER:-postgres}" -d postgres -v "role_name=$ROLE_NAME" <<< "SELECT rolcanlogin,rolcreatedb,rolinherit,rolbypassrls,rolsuper,rolcreaterole FROM pg_roles WHERE rolname=:'role_name'") || die "role postcondition query failed"
  if [[ "$PROFILE" == bypassrls ]]; then
    [[ "$actual" == "t|t|f|t|f|f" ]] || die "BYPASSRLS role postcondition failed: $actual"
  else
    [[ "$actual" == "t|t|f|f|f|f" ]] || die "restricted role postcondition failed: $actual"
  fi

  # The RLS boundary suites intentionally SET ROLE to non-login roles. Keep
  # these helper roles in the same authoritative lifecycle as the login role,
  # including their membership and exact non-privileged attributes.
  local inner_role inner_actual
  for inner_role in quickscale_rls_test_role quickscale_rls_op_test_role; do
    psql_run postgres "SELECT format('CREATE ROLE %I WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE', :'inner_role') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'inner_role') \\gexec" "inner_role=$inner_role"
    psql_run postgres "SELECT format('ALTER ROLE %I WITH NOBYPASSRLS NOINHERIT NOLOGIN NOSUPERUSER NOCREATEROLE', :'inner_role') \\gexec" "inner_role=$inner_role"
    inner_actual=$(printf '%s\n' "SELECT rolcanlogin,rolcreatedb,rolinherit,rolbypassrls,rolsuper,rolcreaterole FROM pg_roles WHERE rolname=:'inner_role'" | psql -X -At -v ON_ERROR_STOP=1 -h "$PGHOST_VALUE" -p "$PGPORT_VALUE" -U "${PGUSER:-postgres}" -d postgres -v "inner_role=$inner_role") || die "inner role postcondition query failed"
    [[ "$inner_actual" == "f|f|f|f|f|f" ]] || die "inner role postcondition failed: $inner_role: $inner_actual"
    psql_run postgres "SELECT format('GRANT %I TO %I', :'inner_role', :'role_name') \\gexec" "inner_role=$inner_role" "role_name=$ROLE_NAME"
  done
}

provision_databases() {
  local i database module
  [[ "$PROFILE" != client-only ]] || return 0
  provision_role
  for ((i=0; i<${#DATABASE_NAMES[@]}; i++)); do
    database="${DATABASE_NAMES[$i]}"; module="${DATABASE_MODULES[$i]}"
    psql_run postgres "SELECT format('CREATE DATABASE %I', :'db_name') WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \\gexec" "db_name=$database"
    psql_run postgres "SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'role_name') \\gexec" "db_name=$database" "role_name=$ROLE_NAME"
    psql_run "$database" "SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'role_name') \\gexec" "role_name=$ROLE_NAME"
    [[ -n "$module" ]] || true
  done
}

append_github_env() {
  local env_file="${GITHUB_ENV:-}" key value
  [[ -n "$env_file" ]] || die "GITHUB_ENV is required on hosted setup"
  [[ ! -L "$env_file" ]] || die "GITHUB_ENV must not be a symlink"
  : >> "$env_file"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    key="${line%%=*}"; value="${line#*=}"
    [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || die "unsafe GITHUB_ENV key"
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* && "$value" != *'<<'* ]] || die "unsafe GITHUB_ENV value"
    # The BYPASSRLS profile prepares a privileged role, but only the consumer
    # test step may authorize its use.  Never widen that exact-"1" escape hatch
    # to every later step in the hosted job through GITHUB_ENV.
    if [[ "$PROFILE" == bypassrls && "$key" == QUICKSCALE_ALLOW_BYPASSRLS ]]; then
      continue
    fi
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  done < <(description_json | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(f"{k}={v}" for k,v in d["environment"].items()))')
  printf 'QUICKSCALE_POSTGRES_LEASE=%s\nQUICKSCALE_POSTGRES_LEASE_TOKEN=%s\n' "$LEASE_FILE" "$LEASE_TOKEN" >> "$env_file"
}

cleanup() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [[ -n "$CHILD_PGID" && "$CHILD_PGID" != "0" ]]; then
    kill -TERM -- "-$CHILD_PGID" 2>/dev/null \
      || { [[ -z "$CHILD_PID" ]] || kill -TERM "$CHILD_PID" 2>/dev/null || true; }
  elif [[ -n "$CHILD_PID" ]]; then
    kill -TERM "$CHILD_PID" 2>/dev/null || true
  fi
  [[ -z "$CHILD_PID" ]] || wait "$CHILD_PID" 2>/dev/null || true
  if [[ -n "$CONTAINER_ID" ]]; then
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$SCOPE" ]]; then
    local ids id; local -a owned_ids=()
    if ids=$(docker ps -aq --filter "$OWNER_LABEL" --filter "$LIFECYCLE_LABEL" --filter "label=com.quickscale.scope=$SCOPE" 2>/dev/null); then
      if [[ -n "$ids" ]]; then
        while IFS= read -r id; do [[ -n "$id" ]] && owned_ids+=("$id"); done <<< "$ids"
        if ((${#owned_ids[@]} > 0)); then
          docker rm -f "${owned_ids[@]}" >/dev/null 2>&1 || true
        fi
      fi
    fi
  fi
  [[ -z "$LEASE_DIR" ]] || rm -rf -- "$LEASE_DIR"
  exit "$status"
}

resolve_image() {
  local image_id
  image_id=$(docker image inspect --format '{{.Id}}' postgres:18 2>/dev/null) || {
    docker pull postgres:18 >/dev/null || die "unable to pull postgres:18"
  }
  image_id=$(docker image inspect --format '{{.Id}}' postgres:18 2>/dev/null) || die "unable to inspect postgres:18"
  [[ "$image_id" =~ ^sha256:[0-9a-fA-F]{64}$ ]] || die "malformed immutable PostgreSQL image ID"
  printf '%s' "$image_id"
}

run_local() {
  [[ "$PROFILE" == restricted || "$PROFILE" == bypassrls || "$PROFILE" == isolation ]] || die "local run does not support profile $PROFILE"
  [[ "${GITHUB_ACTIONS:-}" != true ]] || die "local run is not permitted on GitHub Actions"
  validate_host_port
  verify_clients
  command -v docker >/dev/null 2>&1 || die "Docker is required for local PostgreSQL"
  local temp_base="${TMPDIR:-/tmp}" image_id published_port
  [[ -d "$temp_base" ]] || die "temporary directory is unavailable"
  profile_scope
  trap cleanup EXIT HUP INT TERM
  trap 'forward_signal HUP 129' HUP
  trap 'forward_signal INT 130' INT
  trap 'forward_signal TERM 143' TERM
  image_id=$(resolve_image)
  DESCRIPTION_DIGEST=$(printf '%s' "$(description_json)" | sha256sum | cut -d' ' -f1)
  # Keep the process-wide client default compatible with existing settings;
  # module mappings still carry the concrete loopback endpoint below.
  write_lease "$temp_base" local localhost 0
  local container_name="quickscale-pg-${SCOPE}-${BASHPID}"
  CONTAINER_ID=$(docker create --name "$container_name" --label com.quickscale.owner=quickscale --label com.quickscale.lifecycle=integration --label "com.quickscale.scope=$SCOPE" --label "com.quickscale.image-contract=$image_id" --tmpfs /var/lib/postgresql:rw --publish 127.0.0.1::5432 -e POSTGRES_HOST_AUTH_METHOD=trust "$image_id") || die "Docker container allocation failed"
  [[ -n "$CONTAINER_ID" ]] || die "Docker allocation returned no container ID"
  sed -i "s/^container_id=.*/container_id=$CONTAINER_ID/" "$LEASE_FILE"
  docker start "$CONTAINER_ID" >/dev/null || die "Docker container start failed"
  published_port=$(docker port "$CONTAINER_ID" 5432/tcp | sed -n 's/.*127\.0\.0\.1:\([0-9][0-9]*\).*/\1/p' | sed -n '1p')
  [[ "$published_port" =~ ^[0-9]+$ ]] || die "Docker did not report a dynamic loopback port"
  PGHOST_VALUE=localhost; PGPORT_VALUE="$published_port"
  export PGHOST=localhost PGPORT="$PGPORT_VALUE"
  DESCRIPTION_DIGEST=$(printf '%s' "$(description_json)" | sha256sum | cut -d' ' -f1)
  sed -i "s/^endpoint_host=.*/endpoint_host=localhost/; s/^endpoint_port=.*/endpoint_port=$PGPORT_VALUE/; s/^description_digest=.*/description_digest=$DESCRIPTION_DIGEST/" "$LEASE_FILE"
  local ready=false attempt ready_output
  for attempt in {1..60}; do
    if ready_output=$(psql -X -At -v ON_ERROR_STOP=1 -h "$PGHOST_VALUE" -p "$PGPORT_VALUE" -U postgres -d postgres -c 'SELECT current_setting('\''server_version_num'\'')' 2>/dev/null) \
      && [[ "$ready_output" == 18* ]]; then ready=true; break; fi
    sleep 1
  done
  [[ "$ready" == true ]] || die "PostgreSQL server did not report major 18"
  local actual_image
  actual_image=$(docker inspect --type container --format '{{.Image}}' "$CONTAINER_ID" 2>/dev/null) || die "unable to inspect PostgreSQL container image"
  [[ "$actual_image" == "$image_id" ]] || die "PostgreSQL container image changed after allocation"
  export_environment
  provision_databases
  (( $# > 0 )) || die "run requires a child command after --"
  command -v setsid >/dev/null 2>&1 || die "setsid is required for isolated child process groups"
  export QUICKSCALE_POSTGRES_LEASE_VALIDATED="$LEASE_TOKEN"
  export QUICKSCALE_POSTGRES_PROFILE="$PROFILE"
  export QS_PROVISION_SCOPE="$SCOPE"
  # A Make recipe can inherit SIGINT as ignored.  ``setsid`` deliberately
  # preserves that disposition, which would make an otherwise independent
  # child immune to the signal group used by this lifecycle.  Reset the three
  # lifecycle signals at the exec boundary while retaining the verified new
  # session/process-group semantics.
  local child_sid="" observed_child_pgid="" parent_pgid result=0 probe_failed=false active_pid
  local child_was_active=false
  local child_identity="" child_termination="" extra_identity=""
  local child_status_file="$LEASE_DIR/child-status"
  local -a active_child_pids=()
  parent_pgid=$(ps -o pgid= -p $$) || die "cannot inspect the lifecycle process group"
  parent_pgid=${parent_pgid//[[:space:]]/}
  [[ "$parent_pgid" =~ ^[0-9]+$ ]] || die "lifecycle process group is invalid"
  # Defer lifecycle signals across the launch-to-ownership window.  The shell
  # records the first signal, binds both the child PID and its setsid-defined
  # process-group identity in one assignment command, then forwards the signal
  # before any verification can declare the child ready.
  trap 'defer_signal HUP 129' HUP
  trap 'defer_signal INT 130' INT
  trap 'defer_signal TERM 143' TERM
  setsid -- env --default-signal=HUP --default-signal=INT --default-signal=TERM \
    "$PYTHON" -c '
import os
import signal
import sys

status_file = sys.argv[1]
command = sys.argv[2:]
signals = {signal.SIGHUP, signal.SIGINT, signal.SIGPIPE, signal.SIGTERM}
old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signals)
child_pid = os.fork()
if child_pid == 0:
    for signum in signals:
        signal.signal(signum, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        os.write(2, f"{command[0]}: {error.strerror}\n".encode())
        os._exit(127)

received_signal = 0

def forward_received_signal(signum, _frame):
    global received_signal
    if received_signal == 0:
        received_signal = signum
    try:
        os.kill(child_pid, signum)
    except ProcessLookupError:
        pass

for signum in signals:
    signal.signal(signum, forward_received_signal)
signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)

while True:
    try:
        _, wait_status = os.waitpid(child_pid, 0)
        break
    except InterruptedError:
        continue

if received_signal:
    termination_kind = "signal"
    termination_status = received_signal
elif os.WIFSIGNALED(wait_status):
    termination_kind = "signal"
    termination_status = os.WTERMSIG(wait_status)
elif os.WIFEXITED(wait_status):
    termination_kind = "exit"
    termination_status = os.WEXITSTATUS(wait_status)
else:
    termination_kind = "unknown"
    termination_status = 1

descriptor = os.open(
    status_file,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
    0o600,
)
with os.fdopen(descriptor, "w", encoding="ascii") as stream:
    stream.write(f"{termination_kind}:{termination_status}\n")

if termination_kind == "signal":
    try:
        signal.signal(termination_status, signal.SIG_DFL)
    except (OSError, ValueError):
        pass
    os.kill(os.getpid(), termination_status)
    os._exit(128 + termination_status)
os._exit(termination_status)
' "$child_status_file" "$@" & CHILD_PID=$! CHILD_PGID=$!
  trap 'forward_signal HUP 129' HUP
  trap 'forward_signal INT 130' INT
  trap 'forward_signal TERM 143' TERM
  if [[ -n "$PENDING_CHILD_SIGNAL" ]]; then
    forward_signal "$PENDING_CHILD_SIGNAL" "$PENDING_CHILD_STATUS"
  fi
  # Snapshot liveness immediately before verification, then take a complete
  # second snapshot if the probe fails.  A child that remains active is an
  # ownership-verification error; a child that exits normally keeps its status.
  # If a previously-active child instead dies by signal in that window, fail
  # with the ownership diagnostic rather than leaking its 128+signal status.
  mapfile -t active_child_pids < <(jobs -pr)
  for active_pid in "${active_child_pids[@]}"; do
    [[ "$active_pid" != "$CHILD_PID" ]] || child_was_active=true
  done
  if child_identity=$(ps -o pgid=,sid= -p "$CHILD_PID"); then
    read -r observed_child_pgid child_sid extra_identity <<< "$child_identity"
  else
    probe_failed=true
  fi
  if [[ "$probe_failed" == true ]]; then
    active_child_pids=()
    mapfile -t active_child_pids < <(jobs -pr)
    for active_pid in "${active_child_pids[@]}"; do
      [[ "$active_pid" != "$CHILD_PID" ]] || die "cannot verify the process group of a live child"
    done
    wait "$CHILD_PID" || result=$?
    CHILD_PID=""
    CHILD_PGID=""
    if [[ "$child_was_active" == true ]]; then
      if [[ -f "$child_status_file" && ! -L "$child_status_file" ]]; then
        IFS= read -r child_termination < "$child_status_file" || true
      fi
      [[ "$child_termination" == "exit:$result" ]] \
        || die "cannot verify the process group of a live child"
    fi
    exit "$result"
  fi
  [[ -z "$extra_identity" && "$observed_child_pgid" =~ ^[0-9]+$ && "$observed_child_pgid" == "$CHILD_PID" ]] || die "child process group is not distinct"
  [[ "$child_sid" == "$CHILD_PID" && "$observed_child_pgid" != "$parent_pgid" ]] || die "child session is not distinct"
  wait "$CHILD_PID" || result=$?
  CHILD_PID=""
  CHILD_PGID=""
  exit "$result"
}

defer_signal() {
  if [[ -z "$PENDING_CHILD_SIGNAL" ]]; then
    PENDING_CHILD_SIGNAL="$1"
    PENDING_CHILD_STATUS="$2"
  fi
}

forward_signal() {
  local signal="$1" status="$2"
  if [[ -n "$CHILD_PGID" && "$CHILD_PGID" != "0" ]]; then
    kill -"$signal" -- "-$CHILD_PGID" 2>/dev/null \
      || { [[ -z "$CHILD_PID" ]] || kill -"$signal" "$CHILD_PID" 2>/dev/null || true; }
    wait "$CHILD_PID" 2>/dev/null || true
  elif [[ -n "$CHILD_PID" ]]; then
    kill -"$signal" "$CHILD_PID" 2>/dev/null || true
    wait "$CHILD_PID" 2>/dev/null || true
  fi
  exit "$status"
}

main() {
  if (($# == 1)) && [[ "$1" == --help || "$1" == -h ]]; then
    usage
    return 0
  fi
  (($# >= 1)) || { usage >&2; return 2; }
  local operation="$1"; shift
  local profile="" format="" command_args=()
  while (($#)); do
    case "$1" in
      --profile) (($# >= 2)) || die '--profile requires a value'; profile="$2"; shift 2 ;;
      --format) (($# >= 2)) || die '--format requires a value'; format="$2"; shift 2 ;;
      --) shift; command_args=("$@"); break ;;
      *) die "unknown option: $1" ;;
    esac
  done
  [[ -n "$profile" ]] || die '--profile is required'
  [[ "$operation" == describe || "$operation" == hosted-setup || "$operation" == run || "$operation" == validate ]] || die "unknown operation: $operation"
  validate_host_port
  [[ "$operation" != describe || "$format" == json ]] || die 'describe requires --format json'
  [[ "$operation" == describe || -z "$format" ]] || die 'only describe accepts --format'
  if [[ "$operation" == hosted-setup ]]; then
    [[ "${GITHUB_ACTIONS:-}" == true ]] || die 'hosted-setup is GitHub-only'
    QS_PROVISION_HOSTED=1; export QS_PROVISION_HOSTED
  fi
  build_profile "$profile"
  case "$operation" in
    describe) description_json ;;
    hosted-setup)
      if [[ -n "${QUICKSCALE_POSTGRES_LEASE:-}" ]]; then
        validate_hosted_lease
        exit 0
      fi
      install_hosted_clients
      if [[ "$PROFILE" != client-only ]]; then provision_databases; fi
      SCOPE="hosted_${GITHUB_RUN_ID:-run}"
      DESCRIPTION_DIGEST=$(printf '%s' "$(description_json)" | sha256sum | cut -d' ' -f1)
      write_lease "${RUNNER_TEMP:-${TMPDIR:-/tmp}}" hosted "$PGHOST_VALUE" "$PGPORT_VALUE"
      printf 'postconditions=verified\n' >> "$LEASE_FILE"
      append_github_env
      ;;
    run)
      if [[ -n "${QUICKSCALE_POSTGRES_LEASE:-}" ]]; then
        validate_lease
        export_environment
        export QUICKSCALE_POSTGRES_LEASE_VALIDATED="$QUICKSCALE_POSTGRES_LEASE_TOKEN"
        export QUICKSCALE_POSTGRES_PROFILE="$PROFILE"
        ((${#command_args[@]} > 0)) || die 'run requires a child command after --'
        exec "${command_args[@]}"
      fi
      run_local "${command_args[@]}"
      ;;
    validate)
      [[ -z "$format" && ${#command_args[@]} -eq 0 ]] || die 'validate accepts only --profile'
      if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
        validate_hosted_lease
      else
        validate_lease
        validate_environment
      fi
      ;;
  esac
}

main "$@"
