#!/usr/bin/env bash

quickscale_requires_python_spec() {
    local root="$1"
    local pyproject="$root/pyproject.toml"
    local line

    if [[ ! -f "$pyproject" ]]; then
        echo "ERROR: pyproject.toml not found at $pyproject" >&2
        return 1
    fi

    line="$(
        awk '
            /^\[project\][[:space:]]*$/ { in_project=1; next }
            /^\[[^]]+\][[:space:]]*$/ { in_project=0 }
            in_project && /^[[:space:]]*requires-python[[:space:]]*=/ {
                print
                exit
            }
        ' "$pyproject"
    )"

    if [[ -z "$line" ]]; then
        echo "ERROR: [project].requires-python not found in $pyproject" >&2
        return 1
    fi

    printf '%s\n' "$line" | sed -E 's/^[^"]*"([^"]+)".*$/\1/'
}

quickscale_min_python_version() {
    local root="$1"
    local spec

    spec="$(quickscale_requires_python_spec "$root")" || return 1

    if [[ "$spec" =~ \>\=[[:space:]]*([0-9]+\.[0-9]+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi

    echo "ERROR: unsupported [project].requires-python format: $spec" >&2
    return 1
}

quickscale_system_search_path() {
    local root="$1"
    local entry
    local sanitized=""
    local IFS=':'

    for entry in $PATH; do
        if [[ -n "${VIRTUAL_ENV:-}" && "$entry" == "$VIRTUAL_ENV/bin" ]]; then
            continue
        fi

        if [[ "$entry" == "$root/.venv/bin" ]]; then
            continue
        fi

        if [[ -n "$sanitized" ]]; then
            sanitized="${sanitized}:"
        fi
        sanitized="${sanitized}${entry}"
    done

    printf '%s\n' "$sanitized"
}

quickscale_python_meets_minimum() {
    local python_bin="$1"
    local required_version="$2"
    local required_major="${required_version%%.*}"
    local required_minor="${required_version##*.}"

    "$python_bin" -c "import sys; raise SystemExit(0 if sys.version_info >= ($required_major, $required_minor) else 1)"
}

quickscale_python_candidates() {
    local root="$1"
    local search_path
    local entry
    local candidate
    local candidate_name
    local candidate_path
    local -a entries=()
    local nullglob_restore_cmd
    declare -A seen_paths=()

    search_path="$(quickscale_system_search_path "$root")"
    IFS=':' read -r -a entries <<< "$search_path"

    if shopt -q nullglob; then
        nullglob_restore_cmd='shopt -s nullglob'
    else
        nullglob_restore_cmd='shopt -u nullglob'
        shopt -s nullglob
    fi

    for entry in "${entries[@]}"; do
        if [[ -z "$entry" || ! -d "$entry" ]]; then
            continue
        fi

        for candidate in "$entry"/python3.[0-9]* "$entry"/python[0-9].[0-9]* "$entry"/python3 "$entry"/python; do
            if [[ ! -x "$candidate" || -d "$candidate" ]]; then
                continue
            fi

            candidate_name="$(basename "$candidate")"
            if [[ "$candidate_name" != "python3" && "$candidate_name" != "python" && ! "$candidate_name" =~ ^python[0-9]+\.[0-9]+$ ]]; then
                continue
            fi

            candidate_path="$(readlink -f "$candidate" 2>/dev/null || printf '%s' "$candidate")"
            if [[ -n "${seen_paths[$candidate_path]+x}" ]]; then
                continue
            fi

            seen_paths[$candidate_path]=1
            printf '%s\n' "$candidate_path"
        done
    done

    eval "$nullglob_restore_cmd"
}

quickscale_find_compatible_python() {
    local root="$1"
    local required_version
    local candidate_path

    required_version="$(quickscale_min_python_version "$root")" || return 1
    while IFS= read -r candidate_path; do
        if quickscale_python_meets_minimum "$candidate_path" "$required_version"; then
            printf '%s\n' "$candidate_path"
            return 0
        fi
    done < <(quickscale_python_candidates "$root")

    return 1
}

quickscale_python_major_minor() {
    local python_bin="$1"

    "$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
}
