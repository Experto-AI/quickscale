#!/usr/bin/env bash

# Shared helpers for .agent adapter scripts.
# Scripts may set AGENT_DIR/ROOT_DIR/OUTPUT_ROOT before sourcing this file.

if [[ -z "${AGENT_DIR:-}" ]]; then
    COMMON_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    AGENT_DIR="$(cd "$COMMON_LIB_DIR/../.." && pwd)"
fi
if [[ -z "${ROOT_DIR:-}" ]]; then
    ROOT_DIR="$(dirname "$AGENT_DIR")"
fi

BUILD_DIR="$AGENT_DIR/.build"
MANIFEST_DIR="$BUILD_DIR/manifests"
IR_FILE_DEFAULT="$BUILD_DIR/ir.json"

trim() {
    local s="$1"
    # shellcheck disable=SC2001
    s="$(echo "$s" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    printf '%s' "$s"
}

strip_wrapping_quotes() {
    local s
    s="$(trim "$1")"
    s="${s#\"}"
    s="${s%\"}"
    s="${s#\'}"
    s="${s%\'}"
    printf '%s' "$s"
}

info() {
    printf '  %s\n' "$*"
}

warn() {
    printf '  WARN: %s\n' "$*" >&2
}

err() {
    printf '  ERROR: %s\n' "$*" >&2
}

ensure_build_dirs() {
    mkdir -p "$BUILD_DIR" "$MANIFEST_DIR"
}

abs_to_rel() {
    local path="$1"
    if [[ "$path" == "$ROOT_DIR"/* ]]; then
        printf '%s\n' "${path#"$ROOT_DIR"/}"
    else
        printf '%s\n' "$path"
    fi
}

manifest_path() {
    local platform="$1"
    printf '%s/%s.txt\n' "$MANIFEST_DIR" "$platform"
}

cleanup_with_manifest() {
    local platform="$1"
    shift || true

    local path
    for path in "$@"; do
        [[ -n "$path" ]] || continue
        if [[ "$path" == /* && "$path" != "$ROOT_DIR"/* ]]; then
            # External output roots are typically test sandboxes. Skip manifest mutation.
            return 0
        fi
    done

    ensure_build_dirs

    local manifest
    manifest="$(manifest_path "$platform")"

    declare -A keep
    local rel
    for rel in "$@"; do
        [[ -n "$rel" ]] || continue
        keep["$rel"]=1
    done

    if [[ -f "$manifest" ]]; then
        local stale
        while IFS= read -r stale; do
            [[ -n "$stale" ]] || continue
            if [[ -z "${keep[$stale]:-}" ]]; then
                local stale_path
                if [[ "$stale" == /* ]]; then
                    stale_path="$stale"
                else
                    stale_path="$ROOT_DIR/$stale"
                fi
                if [[ -f "$stale_path" ]]; then
                    rm -f "$stale_path"
                fi
            fi
        done < "$manifest"
    fi

    {
        for rel in "$@"; do
            [[ -n "$rel" ]] || continue
            printf '%s\n' "$rel"
        done
    } | sort -u > "$manifest"
}

cleanup_manifest_platform() {
    local platform="$1"
    local manifest
    manifest="$(manifest_path "$platform")"
    [[ -f "$manifest" ]] || return 0

    local stale stale_path
    while IFS= read -r stale; do
        [[ -n "$stale" ]] || continue
        if [[ "$stale" == /* ]]; then
            stale_path="$stale"
        else
            stale_path="$ROOT_DIR/$stale"
        fi
        if [[ -f "$stale_path" ]]; then
            rm -f "$stale_path"
        fi
    done < "$manifest"

    rm -f "$manifest"
}

get_frontmatter_block() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk '
        BEGIN { seen = 0; in_block = 0 }
        /^---[[:space:]]*$/ {
            seen++
            if (seen == 1) {
                in_block = 1
                next
            }
            if (seen == 2) {
                exit
            }
        }
        in_block { print }
    ' "$file"
}

get_frontmatter_scalar() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    get_frontmatter_block "$file" | awk -v key="$key" '
        $0 ~ "^" key ":[[:space:]]*" {
            sub("^" key ":[[:space:]]*", "", $0)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
            gsub(/^\"|\"$/, "", $0)
            gsub(/^\047|\047$/, "", $0)
            print
            exit
        }
    '
}

get_frontmatter_list() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    get_frontmatter_block "$file" | awk -v key="$key" '
        BEGIN { in_list = 0 }
        $0 ~ "^" key ":[[:space:]]*$" {
            in_list = 1
            next
        }
        in_list {
            if ($0 ~ "^[A-Za-z0-9_-]+:[[:space:]]*") {
                exit
            }
            if ($0 ~ "^[[:space:]]*-[[:space:]]+") {
                sub("^[[:space:]]*-[[:space:]]+", "", $0)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
                gsub(/^\"|\"$/, "", $0)
                gsub(/^\047|\047$/, "", $0)
                print
            }
        }
    '
}

get_frontmatter_section() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    get_frontmatter_block "$file" | awk -v key="$key" '
        BEGIN { capture = 0 }
        $0 ~ "^" key ":[[:space:]]*" {
            capture = 1
            print
            next
        }
        capture {
            if ($0 ~ "^[A-Za-z0-9_-]+:[[:space:]]*" && $0 !~ "^[[:space:]]") {
                exit
            }
            print
        }
    '
}

get_body() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk 'BEGIN{n=0} /^---[[:space:]]*$/{n++; next} n>=2{print}' "$file"
}

get_directives() {
    local file="$1" kind="$2"
    local extracted
    [[ -f "$file" ]] || return 0
    extracted="$(get_body "$file" | grep -oE '<!--[[:space:]]*invoke-[a-z-]+:[[:space:]]*[^[:space:]>]+' || true)"
    printf '%s\n' "$extracted" \
        | sed -E 's/<!--[[:space:]]*invoke-([a-z-]+):[[:space:]]*([^[:space:]>]+)$/\1\t\2/' \
        | awk -v kind="$kind" '$1 == kind { print $2 }' \
        | sort -u
}

yaml_get_value() {
    local file="$1" dotted_path="$2"
    [[ -f "$file" ]] || return 0

    awk -v target_path="$dotted_path" '
        function trim(s) {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
            return s
        }
        {
            line = $0
            sub(/[[:space:]]+#.*/, "", line)
            if (line ~ /^[[:space:]]*$/) {
                next
            }
            if (line !~ /:/) {
                next
            }

            match(line, /[^ ]/)
            indent = RSTART - 1
            if (indent < 0) {
                indent = 0
            }

            level = int(indent / 2)
            key = line
            sub(/:.*/, "", key)
            key = trim(key)

            value = line
            sub(/^[^:]*:[[:space:]]*/, "", value)
            value = trim(value)

            keys[level] = key
            for (i = level + 1; i < 64; i++) {
                delete keys[i]
            }

            full = keys[0]
            for (i = 1; i <= level; i++) {
                full = full "." keys[i]
            }

            if (value != "") {
                gsub(/^["\047]|["\047]$/, "", value)
                values[full] = value
            }
        }
        END {
            if (target_path in values) {
                print values[target_path]
            }
        }
    ' "$file"
}

yaml_in_section_value() {
    local section="$1" key="$2"
    local file="$AGENT_DIR/config.yaml"
    yaml_get_value "$file" "${section}.${key}"
}

yaml_to_bool() {
    local value
    value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
    if [[ "$value" == "true" || "$value" == "yes" || "$value" == "1" ]]; then
        printf 'true\n'
    else
        printf 'false\n'
    fi
}

platform_enabled() {
    local platform_key="$1"
    local file="$AGENT_DIR/config.yaml"
    [[ -f "$file" ]] || { printf 'true\n'; return 0; }

    local value
    value="$(yaml_get_value "$file" "adapters.platforms.${platform_key}.enabled")"
    if [[ -z "$value" ]]; then
        value="$(yaml_get_value "$file" "adapters.platforms.${platform_key}")"
    fi

    if [[ -z "$value" ]]; then
        printf 'true\n'
    else
        yaml_to_bool "$value"
    fi
}

platform_support_mode() {
    local platform_key="$1"
    local file="$AGENT_DIR/config.yaml"
    [[ -f "$file" ]] || { printf 'native\n'; return 0; }

    local value
    value="$(yaml_get_value "$file" "adapters.platforms.${platform_key}.support_mode")"
    if [[ -z "$value" ]]; then
        printf 'native\n'
    else
        printf '%s\n' "$value"
    fi
}

platform_experimental() {
    local platform_key="$1"
    local file="$AGENT_DIR/config.yaml"
    [[ -f "$file" ]] || { printf 'false\n'; return 0; }

    local value
    value="$(yaml_get_value "$file" "adapters.platforms.${platform_key}.experimental")"
    if [[ -z "$value" ]]; then
        printf 'false\n'
    else
        yaml_to_bool "$value"
    fi
}

config_project_name() {
    local value
    value="$(yaml_in_section_value "project" "name")"
    if [[ -n "$value" ]]; then
        printf '%s\n' "$value"
    else
        printf 'Project\n'
    fi
}

config_project_profile() {
    local value
    value="$(yaml_in_section_value "project" "profile")"
    if [[ -n "$value" ]]; then
        printf '%s\n' "$value"
    else
        printf 'quickscale\n'
    fi
}

template_path() {
    local filename="$1"
    local profile
    profile="$(config_project_profile)"

    local candidate
    candidate="$AGENT_DIR/templates/${profile}/${filename}"
    if [[ -f "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    candidate="$AGENT_DIR/templates/quickscale/${filename}"
    if [[ -f "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    candidate="$AGENT_DIR/templates/default/${filename}"
    if [[ -f "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    printf '%s\n' "$AGENT_DIR/templates/quickscale/${filename}"
}

capability_file_for_platform() {
    local platform_key="$1"
    case "$platform_key" in
        claude_code) printf '%s\n' "$AGENT_DIR/adapters/capabilities/claude_code.yaml" ;;
        gemini_cli) printf '%s\n' "$AGENT_DIR/adapters/capabilities/gemini_cli.yaml" ;;
        github_copilot) printf '%s\n' "$AGENT_DIR/adapters/capabilities/copilot_vscode.yaml" ;;
        codex_cli) printf '%s\n' "$AGENT_DIR/adapters/capabilities/codex_cli.yaml" ;;
        *) return 1 ;;
    esac
}

capability_value() {
    local platform_key="$1" dotted_path="$2"
    local file
    file="$(capability_file_for_platform "$platform_key")" || return 0
    yaml_get_value "$file" "$dotted_path"
}

assert_capability_value() {
    local platform_key="$1" dotted_path="$2" expected="$3"
    local value
    value="$(capability_value "$platform_key" "$dotted_path")"
    if [[ -z "$value" ]]; then
        err "Missing capability '${dotted_path}' for platform '${platform_key}'"
        return 1
    fi
    if [[ "$value" != "$expected" ]]; then
        err "Capability mismatch for '${platform_key}': ${dotted_path}=${value}, expected ${expected}"
        return 1
    fi
    return 0
}

config_output_directory() {
    local value
    value=$(yaml_in_section_value "adapters" "output_directory")
    if [[ -z "$value" ]]; then
        printf '.\n'
    else
        printf '%s\n' "$value"
    fi
}

resolve_output_root() {
    local out_dir
    out_dir="$(config_output_directory)"
    if [[ "$out_dir" == /* ]]; then
        printf '%s\n' "$out_dir"
    else
        printf '%s\n' "$ROOT_DIR/$out_dir"
    fi
}

config_project_command() {
    local key="$1" default_value="$2"
    local value
    value=$(yaml_in_section_value "project" "$key")
    if [[ -n "$value" ]]; then
        printf '%s\n' "$value"
    else
        printf '%s\n' "$default_value"
    fi
}

has_repo_command() {
    local command_path="$1"
    [[ -f "$ROOT_DIR/$command_path" && -x "$ROOT_DIR/$command_path" ]]
}

resolve_lint_command() {
    local configured fallback
    configured="$(config_project_command "lint_command" "./scripts/lint.sh")"
    fallback="./scripts/lint.sh"

    if has_repo_command "$configured"; then
        printf '%s\n' "$configured"
        return 0
    fi
    if has_repo_command "$fallback"; then
        warn "Configured lint_command '$configured' not found, using '$fallback'"
        printf '%s\n' "$fallback"
        return 0
    fi

    warn "No lint command found; leaving configured value '$configured'"
    printf '%s\n' "$configured"
}

resolve_test_command() {
    local configured
    configured="$(config_project_command "test_command" "./scripts/test_unit.sh")"

    local candidate
    for candidate in "$configured" "./scripts/test_unit.sh" "./scripts/test-all.sh"; do
        if has_repo_command "$candidate"; then
            if [[ "$candidate" != "$configured" ]]; then
                warn "Configured test_command '$configured' not found, using '$candidate'"
            fi
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    warn "No test command found; leaving configured value '$configured'"
    printf '%s\n' "$configured"
}

strict_mode_enabled() {
    local file="$AGENT_DIR/config.yaml"
    [[ -f "$file" ]] || { printf 'false\n'; return 0; }
    local value
    value=$(awk '
        BEGIN { in_workflows = 0 }
        /^workflows:[[:space:]]*$/ { in_workflows = 1; next }
        in_workflows {
            if ($0 ~ "^[^[:space:]]") { exit }
            if ($0 ~ "^[[:space:]]*stage_validation:[[:space:]]*") {
                line = $0
                sub("^[[:space:]]*stage_validation:[[:space:]]*", "", line)
                sub(/[[:space:]]+#.*/, "", line)
                gsub(/[[:space:]]+$/, "", line)
                gsub(/^\"|\"$/, "", line)
                print tolower(line)
                exit
            }
        }
    ' "$file")

    if [[ "$value" == "strict" ]]; then
        printf 'true\n'
    else
        printf 'false\n'
    fi
}

json_array_from_lines() {
    jq -R -s 'split("\n") | map(select(length>0))'
}
