#!/usr/bin/env bash
# Generate OpenCode compatibility configuration from normalized .agent IR.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/render_common.sh"

IR_PATH="${IR_FILE:-$IR_FILE_DEFAULT}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$(resolve_output_root)}"

OPENCODE_JSON="$OUTPUT_ROOT/.opencode.json"
OPENCODE_DIR="$OUTPUT_ROOT/.opencode"
COMMANDS_DIR="$OPENCODE_DIR/commands"

mkdir -p "$COMMANDS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

generate_opencode_json() {
    local system_prompt
    system_prompt="You are a QuickScale development agent."
    system_prompt+="\n\nCode Standards: Python 3.11+, type hints on public APIs, Google-style docstrings, Ruff for linting, Poetry for package management."
    system_prompt+="\n\nTesting: pytest, no global mocking contamination, coverage >= 90% overall and >= 80% per file."
    system_prompt+="\n\nValidation commands: ${lint_cmd} and ${test_cmd}."

    cat > "$OPENCODE_JSON" << JSON
{
  "\$schema": "https://opencode.ai/schema.json",
  "agents": {
    "coder": {
      "model": "sonnet",
      "systemPrompt": "$(json_escape "$system_prompt")"
    }
  },
  "lsp": {
    "python": {
      "command": "pyright-langserver",
      "args": ["--stdio"]
    }
  }
}
JSON

    track_generated "$OPENCODE_JSON"
}

generate_commands() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue
        local command_file="$COMMANDS_DIR/${wf_name}.md"
        local steps
        steps="$(collect_step_headings "$ROOT_DIR/$wf_path")"

        {
            printf '# %s\n\n' "$wf_desc"
            printf 'Follow the `%s` workflow for QuickScale development.\n\n' "$wf_name"
            if [[ -n "$steps" ]]; then
                printf '## Steps\n\n%s\n\n' "$steps"
            fi
            printf 'Target: $TASK_ID\n\n'
            printf 'Read workflow source: `%s`\n\n' "$wf_path"
            printf '## Validation\n\n'
            printf '```bash\n%s\n%s\n```\n' "$lint_cmd" "$test_cmd"
        } > "$command_file"

        track_generated "$command_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

main() {
    info "OpenCode adapter: generating compatibility configuration"

    generate_opencode_json
    generate_commands

    cleanup_with_manifest "opencode" "${generated_files[@]}"

    info "OpenCode adapter complete"
}

main "$@"
