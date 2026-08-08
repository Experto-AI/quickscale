#!/usr/bin/env bash
set -euo pipefail

# Unified version tool: check, update
# Usage:
#   scripts/version_tool.sh check
#   scripts/version_tool.sh update

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"
PYTHON="${PYTHON:-python3}"
MODULE_DISCOVERY_SHIM="$ROOT/quickscale_core/src/quickscale_core/contracts/module_discovery.py"

PYPROJECTS=("$ROOT/quickscale_core/pyproject.toml" "$ROOT/quickscale_cli/pyproject.toml" "$ROOT/quickscale/pyproject.toml")
PACKAGES=("$ROOT/quickscale_core/src/quickscale_core" "$ROOT/quickscale_cli/src/quickscale_cli")

MODULE_NAMES=()
MODULE_DIRS=()
MODULE_PYPROJECTS=()
MODULE_INITS=()

_load_module_inventory() {
  local output
  if [[ ! -f "$MODULE_DISCOVERY_SHIM" ]]; then
    echo "ERROR: module discovery shim not found at $MODULE_DISCOVERY_SHIM" >&2
    return 1
  fi
  if ! output=$("$PYTHON" "$MODULE_DISCOVERY_SHIM" --list-modules); then
    echo "ERROR: authoritative module inventory could not be loaded" >&2
    return 1
  fi
  if [[ -z "$output" ]]; then
    echo "ERROR: authoritative module inventory is empty" >&2
    return 1
  fi

  MODULE_NAMES=()
  while IFS= read -r module_name; do
    [[ -n "$module_name" ]] || continue
    MODULE_NAMES+=("$module_name")
  done <<< "$output"
  if [[ "${#MODULE_NAMES[@]}" -eq 0 ]]; then
    echo "ERROR: authoritative module inventory is empty" >&2
    return 1
  fi

  MODULE_DIRS=()
  MODULE_PYPROJECTS=()
  MODULE_INITS=()
  for module_name in "${MODULE_NAMES[@]}"; do
    MODULE_DIRS+=("$ROOT/quickscale_modules/$module_name")
    MODULE_PYPROJECTS+=("$ROOT/quickscale_modules/$module_name/pyproject.toml")
    MODULE_INITS+=(
      "$ROOT/quickscale_modules/$module_name/src/quickscale_modules_${module_name}/__init__.py"
    )
  done
}

read_version() {
  if [[ -f "$VERSION_FILE" ]]; then
    cat "$VERSION_FILE" | tr -d '\r' | sed -e 's/^\s*//' -e 's/\s*$//'
  else
    echo ""
  fi
}

get_pyproject_version() {
  local path="$1"
  if [[ -f "$path" ]]; then
    grep -m1 '^version' "$path" | sed -E 's/.*"([^"]+)".*/\1/' || true
  fi
}

# Get version from module.yml (preserves quotes)
get_module_yml_version() {
  local path="$1"
  if [[ -f "$path" ]]; then
    grep -E '^version:' "$path" | sed -E 's/.*"([^"]+)".*/\1/' || true
  fi
}

# Get __version__ from package __init__.py
get_init_version() {
  local path="$1"
  if [[ -f "$path" ]]; then
    grep -m1 '__version__' "$path" | sed -E 's/.*"([^"]+)".*/\1/' || true
  fi
}

update_pyproject() {
  local path="$1"; local version="$2"
  if [[ ! -f "$path" ]]; then
    echo "  (missing) $path"
    return 1
  fi
  local before; before=$(cat "$path")
  # Replace the first version = "..." occurrence (full match including old version)
  sed -E -i "0,/^version[[:space:]]*=[[:space:]]*\"[^\"]+\"/s//version = \"${version}\"/" "$path"
  local after; after=$(cat "$path")
  if [[ "$before" != "$after" ]]; then
    echo "  UPDATED: $path"
    return 0
  else
    echo "  NO-CHANGE: $path"
    return 2
  fi
}

update_module_yml() {
  local path="$1"; local version="$2"
  if [[ ! -f "$path" ]]; then
    echo "  (missing) $path"
    return 1
  fi
  local before; before=$(cat "$path")
  # Replace version: "X.Y.Z" preserving quotes
  sed -E -i "s|^(\s*version\s*:\s*)\"[^\"]*\"|\1\"${version}\"|" "$path"
  local after; after=$(cat "$path")
  if [[ "$before" != "$after" ]]; then
    echo "  UPDATED: $path"
    return 0
  else
    echo "  NO-CHANGE: $path"
    return 2
  fi
}

update_module_init() {
  local path="$1"; local version="$2"
  if [[ ! -f "$path" ]]; then
    echo "  (missing) $path"
    return 1
  fi
  local before; before=$(cat "$path")
  sed -E -i "s|__version__ = \"[^\"]*\"|__version__ = \"${version}\"|" "$path"
  local after; after=$(cat "$path")
  if [[ "$before" != "$after" ]]; then
    echo "  UPDATED: $path"
    return 0
  else
    echo "  NO-CHANGE: $path"
    return 2
  fi
}

update_internal_dependencies() {
  local version="$1"
  local path="$2"
  if [[ ! -f "$path" ]]; then
    return 1
  fi
  local before; before=$(cat "$path")
  # Update quickscale-core dependency constraint
  sed -E -i "s|^(quickscale-core[[:space:]]*=[[:space:]]*)\"\^[0-9]+\.[0-9]+\.[0-9]+\"|\1\"^${version}\"|" "$path"
  # Update quickscale-cli dependency constraint
  sed -E -i "s|^(quickscale-cli[[:space:]]*=[[:space:]]*)\"\^[0-9]+\.[0-9]+\.[0-9]+\"|\1\"^${version}\"|" "$path"
  local after; after=$(cat "$path")
  if [[ "$before" != "$after" ]]; then
    echo "  UPDATED DEPS: $path"
    return 0
  fi
  return 2
}

find_yaml_docs() {
  local out=()
  if [[ -d "$ROOT/docs" ]]; then
    while IFS= read -r -d $'\0' f; do
      # check for version: field in the file
      if grep -Eq '^\s*version\s*:' "$f"; then
        out+=("$f")
      fi
    done < <(find "$ROOT/docs" -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)
  fi
  printf '%s\n' "${out[@]:-}"
}

update_yaml_versions() {
  local version="$1"
  shift
  local updated=()
  for p in "$@"; do
    local before; before=$(cat "$p")
    sed -E -i "s|^(\s*version\s*:\s*).*|\1${version}|" "$p"
    local after; after=$(cat "$p")
    if [[ "$before" != "$after" ]]; then
      updated+=("$p")
      echo "  Updated YAML: $p"
    fi
  done
  return 0
}

embed_version_into_packages() {
  local version="$1"
  for pkg in "${PACKAGES[@]}"; do
    if [[ -d "$pkg" ]]; then
      local target="$pkg/_version.py"
      printf '%s\n' "# Auto-generated by scripts/version_tool.sh" "__version__ = \"${version}\"" > "$target"
      echo "Wrote $target"
    else
      echo "Package dir not found, skipping: $pkg"
    fi
  done
}

# -------------------------------------------------------------------------
# Module-level helpers — authoritative manifest inventory
# -------------------------------------------------------------------------

_count_modules() {
  echo "${#MODULE_NAMES[@]}"
}

_find_present_modules() {
  local out=()
  for d in "${MODULE_DIRS[@]}"; do
    if [[ -f "$d/module.yml" ]]; then
      out+=("$d")
    fi
  done
  printf '%s\n' "${out[@]:-}"
}

# Core snapshot directory for a module
_snapshot_dir() {
  echo "$ROOT/quickscale_core/src/quickscale_core/data/manifests/$1"
}

# Sync a module's source module.yml to its core snapshot
_sync_module_snapshot() {
  local mod_name="$1"
  local src="$ROOT/quickscale_modules/$mod_name/module.yml"
  local dst_dir="$ROOT/quickscale_core/src/quickscale_core/data/manifests/$mod_name"
  local dst="$dst_dir/module.yml"
  if [[ ! -f "$src" ]]; then
    echo "  (missing source) $src"
    return 1
  fi
  mkdir -p "$dst_dir"
  cp "$src" "$dst"
  echo "  SYNCED: $dst"
}

cmd_check_modules() {
  _load_module_inventory || return 1
  local version; version=$(read_version)
  local count; count=$(_count_modules)
  echo "Found $count module(s) from authoritative inventory"

  local mismatch=0
  for m in "${MODULE_NAMES[@]}"; do
    local yml="$ROOT/quickscale_modules/$m/module.yml"
    local pyproject="$ROOT/quickscale_modules/$m/pyproject.toml"
    local init="$ROOT/quickscale_modules/$m/src/quickscale_modules_${m}/__init__.py"

    local yml_ver; yml_ver=$(get_module_yml_version "$yml")
    local py_ver; py_ver=$(get_pyproject_version "$pyproject")
    local init_ver; init_ver=$(get_init_version "$init")

    local ok=0
    if [[ "$yml_ver" != "$version" ]]; then
      echo "  [$m] module.yml version = ${yml_ver:-missing} != ${version}"
      ok=1
    fi
    if [[ "$py_ver" != "$version" ]]; then
      echo "  [$m] pyproject.toml version = ${py_ver:-missing} != ${version}"
      ok=1
    fi
    if [[ "$init_ver" != "$version" ]]; then
      echo "  [$m] __init__.py __version__ = ${init_ver:-missing} != ${version}"
      ok=1
    fi

    if [[ "$ok" -eq 0 ]]; then
      echo "  [$m] OK — all versions match $version"
    else
      mismatch=1
    fi
  done

  if [[ "$mismatch" -ne 0 ]]; then
    return 2
  fi
  return 0
}

cmd_update_modules() {
  _load_module_inventory || return 1
  local version; version=$(read_version)
  local count; count=$(_count_modules)

  echo "Updating $count modules to version ${version}..."

  for m in "${MODULE_NAMES[@]}"; do
    local yml="$ROOT/quickscale_modules/$m/module.yml"
    local pyproject="$ROOT/quickscale_modules/$m/pyproject.toml"
    local init="$ROOT/quickscale_modules/$m/src/quickscale_modules_${m}/__init__.py"

    echo "  [$m]"
    update_module_yml "$yml" "$version" || true
    update_pyproject "$pyproject" "$version" || true
    update_module_init "$init" "$version" || true
    _sync_module_snapshot "$m" || true
  done

  return 0
}

cmd_check() {
  local version; version=$(read_version)
  echo "Repository VERSION: ${version}"
  local ok=0
  for p in "${PYPROJECTS[@]}"; do
    if [[ -f "$p" ]]; then
      local pv; pv=$(get_pyproject_version "$p")
      echo "$p: pyproject version = ${pv}"
      if [[ "${pv}" != "${version}" ]]; then
        echo "  MISMATCH: ${p} != VERSION"
        ok=2
      fi
    else
      echo "$p: (missing)"
    fi
  done

  # Module-level check
  echo ""
  cmd_check_modules || {
    local rc=$?
    if [[ "$ok" -eq 0 ]]; then ok=$rc; fi
  }

  return $ok
}

cmd_update() {
  local version; version=$(read_version)
  echo "Updating all files to version ${version}..."

  # Update pyproject.toml files (core, cli, quickscale)
  for p in "${PYPROJECTS[@]}"; do
    update_pyproject "$p" "$version" || true
    update_internal_dependencies "$version" "$p" || true
  done

  # Update YAML files under docs/ that contain a version: field (Markdown excluded)
  mapfile -t yamls < <(find_yaml_docs)
  if [[ ${#yamls[@]} -gt 0 ]]; then
    update_yaml_versions "$version" "${yamls[@]}"
  fi

  # Embed into _version.py files
  embed_version_into_packages "$version"

  # Update authoritative module packages and sync snapshots.
  echo ""
  cmd_update_modules

  echo ""
  echo "✅ All files updated to version ${version}"
  return 0
}

usage() {
  cat <<EOF
Usage: $0 <command>

Commands:
  check    Verify VERSION matches all pyproject.toml + module versions
  update   Update all files including authoritative module packages and snapshots

Examples:
  # After editing VERSION file, update everything:
  $0 update

  # Verify everything is in sync:
  $0 check

Workflow:
  1. Edit VERSION file with new version
  2. Run: $0 update
  3. Build/publish your packages

Module check exit codes:
  0 — authoritative modules present, all versions match VERSION
  1 — authoritative inventory could not be loaded
  2 — module version mismatch
EOF
}

main() {
  if [[ $# -lt 1 ]]; then usage; exit 2; fi
  cmd="$1"; shift
  case "$cmd" in
    check)
      cmd_check || exit $? ;;
    update)
      cmd_update || exit $? ;;
    -h|--help|help)
      usage ;;
    *)
      echo "Unknown command: $cmd"; usage; exit 2 ;;
  esac
}

main "$@"
