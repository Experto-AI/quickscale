#!/usr/bin/env bash
# Generate OpenAI Codex CLI configuration from normalized .agent IR.

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

AGENTS_MD="$OUTPUT_ROOT/AGENTS.md"
CODEX_DIR="$OUTPUT_ROOT/.codex"
CODEX_CONFIG="$CODEX_DIR/config.toml"

mkdir -p "$CODEX_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

generate_agents_md() {
    cat "$(template_path "codex_header.md")" > "$AGENTS_MD"

    {
        cat "$(template_path "codex_standards.md")"
        cat << 'BLOCK'
## Agents

Available agent definitions for complex workflows:

| Agent | Description | Workflow |
|-------|-------------|----------|
BLOCK
        jq -r '.agents[] | "| `\(.name)` | \(.description) | \(.workflows | join(", ")) |"' "$IR_PATH"

        cat << 'BLOCK'

## Subagents

| Subagent | Description | Parent Agents |
|----------|-------------|---------------|
BLOCK
        jq -r '.subagents[] | "| `\(.name)` | \(.description) | \(.parent_agents | join(", ")) |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills

Reusable guidance modules in `.agent/skills/`:

| Skill | Description | Path |
|-------|-------------|------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) | `.agent/skills/\(.name)/SKILL.md` |"' "$IR_PATH"

        cat << 'BLOCK'

## Workflows

Step-by-step execution plans:

BLOCK

        while IFS=$'\t' read -r wf_name wf_desc wf_path; do
            steps="$(collect_step_headings "$ROOT_DIR/$wf_path")"
            {
                printf '### %s\n\n' "$wf_name"
                printf '%s\n\n' "$wf_desc"
                printf 'Details: `%s`\n\n' "$wf_path"
                if [[ -n "$steps" ]]; then
                    printf '%s\n\n' "$(echo "$steps" | sed 's/^/- /')"
                fi
            }
        done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")

        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Codex supports rich markdown instructions. Input/output/success contracts are retained in source agent files and surfaced through workflow descriptions.

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$AGENTS_MD"

    track_generated "$AGENTS_MD"
}

generate_codex_config() {
    if [[ -f "$CODEX_CONFIG" ]]; then
        track_generated "$CODEX_CONFIG"
        return 0
    fi

    cat > "$CODEX_CONFIG" << 'BLOCK'
# Codex CLI project configuration
# Auto-generated from .agent/ - customize as needed

sandbox_mode = "workspace-write"
project_doc_fallback_filenames = ["CLAUDE.md", "GEMINI.md"]
BLOCK

    track_generated "$CODEX_CONFIG"
}

main() {
    info "Codex CLI adapter: generating configuration"
    assert_capability_value "codex_cli" "supports.project_doc" "AGENTS.md"

    generate_agents_md
    generate_codex_config

    cleanup_with_manifest "codex_cli" "${generated_files[@]}"

    info "Codex CLI adapter complete"
}

main "$@"
