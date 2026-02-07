#!/usr/bin/env bash
# Generate Gemini Antigravity-compatible configuration.

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

ANTI_DIR="$OUTPUT_ROOT/.gemini/antigravity"
PROFILE_MD="$ANTI_DIR/ANTIGRAVITY.md"
COMMANDS_DIR="$ANTI_DIR/commands"
SETTINGS_JSON="$ANTI_DIR/settings.json"

mkdir -p "$COMMANDS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

generate_profile() {
    cat "$(template_path "gemini_antigravity_header.md")" > "$PROFILE_MD"

    {
        cat << 'BLOCK'

## Workflows

| Workflow | Description | Source |
|----------|-------------|--------|
BLOCK
        jq -r '.workflows[] | "| `\(.name)` | \(.description) | `\(.path)` |"' "$IR_PATH"

        cat << 'BLOCK'

## Agents

| Agent | Description | Skills |
|-------|-------------|--------|
BLOCK
        jq -r '.agents[] | "| `\(.name)` | \(.description) | \((.skills + .directives.skills) | unique | join(", ")) |"' "$IR_PATH"

        cat << 'BLOCK'

## Subagents

| Subagent | Description | Parents |
|----------|-------------|---------|
BLOCK
        jq -r '.subagents[] | "| `\(.name)` | \(.description) | \(.parent_agents | join(", ")) |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills

| Skill | Description |
|-------|-------------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Gemini Antigravity mapping is rendered as markdown metadata and command stubs.

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$PROFILE_MD"

    track_generated "$PROFILE_MD"
}

generate_commands() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue
        local out_file="$COMMANDS_DIR/${wf_name}.md"
        local steps
        steps="$(collect_step_headings "$ROOT_DIR/$wf_path")"

        {
            printf '# %s\n\n' "$wf_desc"
            printf 'Follow workflow `%s`.\n\n' "$wf_name"
            if [[ -n "$steps" ]]; then
                printf '## Steps\n\n%s\n\n' "$steps"
            fi
            printf 'Read source workflow: `%s`\n\n' "$wf_path"
            printf 'Arguments: $ARGS\n'
        } > "$out_file"

        track_generated "$out_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_settings() {
    cat > "$SETTINGS_JSON" << 'JSON'
{
  "profile": "quickscale-antigravity",
  "contextFile": "ANTIGRAVITY.md",
  "commandsDir": "commands",
  "agentsEnabled": true
}
JSON

    track_generated "$SETTINGS_JSON"
}

main() {
    info "Gemini Antigravity adapter: generating configuration"
    assert_capability_value "gemini_antigravity" "tier" "experimental"

    generate_profile
    generate_commands
    generate_settings

    cleanup_with_manifest "gemini_antigravity" "${generated_files[@]}"

    info "Gemini Antigravity adapter complete"
}

main "$@"
