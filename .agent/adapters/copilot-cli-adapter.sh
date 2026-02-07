#!/usr/bin/env bash
# Generate GitHub Copilot CLI-specific artifacts.

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

COPILOT_CLI_DIR="$OUTPUT_ROOT/.github/copilot-cli"
INSTRUCTIONS_MD="$COPILOT_CLI_DIR/INSTRUCTIONS.md"
PROMPTS_DIR="$COPILOT_CLI_DIR/prompts"
AGENTS_DIR="$COPILOT_CLI_DIR/agents"

mkdir -p "$PROMPTS_DIR" "$AGENTS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

generate_instructions() {
    cat "$(template_path "copilot_cli_header.md")" > "$INSTRUCTIONS_MD"

    {
        cat << 'BLOCK'

## Workflows

| Workflow | Description |
|----------|-------------|
BLOCK
        jq -r '.workflows[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        cat << 'BLOCK'

## Agents

| Agent | Description | Workflows |
|-------|-------------|-----------|
BLOCK
        jq -r '.agents[] | "| `\(.name)` | \(.description) | \(.workflows | join(", ")) |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills

| Skill | Description |
|-------|-------------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Copilot CLI consumes markdown instructions and prompt files. Full agent contracts are embedded in generated agent markdown.

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$INSTRUCTIONS_MD"

    track_generated "$INSTRUCTIONS_MD"
}

generate_prompts() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue
        local out_file="$PROMPTS_DIR/${wf_name}.md"
        local steps target
        steps="$(collect_step_headings "$ROOT_DIR/$wf_path")"
        if [[ "$wf_name" == "create-release" ]]; then
            target='release_version'
        else
            target='task_id'
        fi

        {
            printf '# %s\n\n' "$wf_desc"
            printf 'Workflow: `%s`\n\n' "$wf_name"
            if [[ -n "$steps" ]]; then
                printf '## Steps\n\n%s\n\n' "$steps"
            fi
            printf 'Arguments: `%s`\n\n' "$target"
            printf 'Source: `%s`\n\n' "$wf_path"
            printf 'Validation:\n'
            printf '```bash\n%s\n%s\n```\n' "$lint_cmd" "$test_cmd"
        } > "$out_file"

        track_generated "$out_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_agents() {
    while IFS=$'\t' read -r name description path; do
        [[ -n "$name" ]] || continue
        local source_file="$ROOT_DIR/$path"
        local out_file="$AGENTS_DIR/${name}.md"

        {
            printf '# %s\n\n' "$name"
            printf '%s\n\n' "$description"
            render_contract_block "$source_file"
            get_body "$source_file"
        } > "$out_file"

        track_generated "$out_file"
    done < <(jq -r '.agents[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

main() {
    info "Copilot CLI adapter: generating configuration"
    assert_capability_value "copilot_cli" "tier" "experimental"

    generate_instructions
    generate_prompts
    generate_agents

    cleanup_with_manifest "copilot_cli" "${generated_files[@]}"

    info "Copilot CLI adapter complete"
}

main "$@"
