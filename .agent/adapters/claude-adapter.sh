#!/usr/bin/env bash
# Generate Claude Code configuration from normalized .agent IR.

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

CLAUDE_MD="$OUTPUT_ROOT/CLAUDE.md"
CLAUDE_DIR="$OUTPUT_ROOT/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
AGENTS_DIR="$CLAUDE_DIR/agents"

mkdir -p "$COMMANDS_DIR" "$AGENTS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

emit_resource_refs() {
    local source_file="$1"

    local refs workflows skills delegates
    workflows=$( {
        get_frontmatter_list "$source_file" "workflows"
        get_directives "$source_file" "workflow"
    } | awk 'NF' | sort -u )
    skills=$( {
        get_frontmatter_list "$source_file" "skills"
        get_directives "$source_file" "skill"
    } | awk 'NF' | sort -u )
    delegates=$( {
        get_frontmatter_list "$source_file" "delegates_to"
        get_directives "$source_file" "agent"
    } | awk 'NF' | sort -u )

    if [[ -z "$workflows" && -z "$skills" && -z "$delegates" ]]; then
        return 0
    fi

    cat << 'BLOCK'
## Available Resources

BLOCK

    if [[ -n "$workflows" ]]; then
        cat << 'BLOCK'
### Workflows

BLOCK
        while IFS= read -r refs; do
            [[ -n "$refs" ]] || continue
            printf -- '- Follow `/%s` workflow\n' "$refs"
        done <<< "$workflows"
        echo ""
    fi

    if [[ -n "$skills" ]]; then
        cat << 'BLOCK'
### Skills

BLOCK
        while IFS= read -r refs; do
            [[ -n "$refs" ]] || continue
            printf -- '- Read `.agent/skills/%s/SKILL.md`\n' "$refs"
        done <<< "$skills"
        echo ""
    fi

    if [[ -n "$delegates" ]]; then
        cat << 'BLOCK'
### Delegation

BLOCK
        while IFS= read -r refs; do
            [[ -n "$refs" ]] || continue
            printf -- '- Delegate to `%s` when needed\n' "$refs"
        done <<< "$delegates"
        echo ""
    fi
}

generate_claude_md() {
    cat "$AGENT_DIR/templates/quickscale/claude_header.md" > "$CLAUDE_MD"

    {
        cat << 'BLOCK'

## Quick Commands

| Command | Description |
|---------|-------------|
BLOCK
        jq -r '.workflows[] | "| `/\(.name)` | \(.description) |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills

| Skill | Description | Source |
|-------|-------------|--------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) | `.agent/skills/\(.name)/SKILL.md` |"' "$IR_PATH"

        cat << 'BLOCK'

## Agents

| Agent | Description | Type |
|-------|-------------|------|
BLOCK
        jq -r '.agents[] | "| `\(.name)` | \(.description) | Agent |"' "$IR_PATH"
        jq -r '.subagents[] | "| `\(.name)` | \(.description) | Subagent |"' "$IR_PATH"

        cat << 'BLOCK'

## Key Principles

### Scope Discipline
- Implement ONLY items in task checklist
- No "nice-to-have" features or opportunistic refactoring

### Code Quality
- SOLID, DRY, KISS principles
- Type hints on all public APIs
- Google-style docstrings (single-line preferred)
- F-strings for formatting
- Ruff for linting (NOT Black or Flake8)

### Testing
- pytest with pytest-django
- No global mocking contamination (`sys.modules` modifications prohibited)
- Test isolation mandatory
- Coverage >= 90% overall, >= 80% per file

BLOCK
        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Platform support for structured contract fields: partial (`mode` native, other fields preserved as markdown sections)

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Framework | Django 4.2+ |
| Package Manager | Poetry (NOT pip/requirements.txt) |
| Package Config | pyproject.toml (NOT setup.py) |
| Linting | Ruff |
| Testing | pytest |
| Frontend | React 18+ with TypeScript |
| Build | Vite |
| Components | shadcn/ui |
| CSS | Tailwind CSS |

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$CLAUDE_MD"

    track_generated "$CLAUDE_MD"
}

generate_commands() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue
        local_file="$COMMANDS_DIR/${wf_name}.md"
        steps_summary="$(collect_step_headings "$ROOT_DIR/$wf_path")"

        {
            printf -- '---\n'
            printf -- 'description: %s\n' "$wf_desc"
            printf -- '---\n\n'
            printf -- 'Follow the %s workflow.\n\n' "$wf_name"
            if [[ -n "$steps_summary" ]]; then
                printf -- '## Steps\n\n%s\n\n' "$steps_summary"
            fi
            printf -- 'Arguments: $ARGUMENTS\n\n'
            printf -- 'Start by reading the full workflow: `%s`\n' "$wf_path"
        } > "$local_file"

        track_generated "$local_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_agent_files() {
    while IFS=$'\t' read -r name description path mode; do
        [[ -n "$name" ]] || continue
        local source_file="$ROOT_DIR/$path"
        local out_file="$AGENTS_DIR/${name}.md"

        {
            printf -- '---\n'
            printf -- 'name: %s\n' "$name"
            printf -- 'description: %s\n' "$description"
            if [[ -n "$mode" && "$mode" != "null" ]]; then
                printf -- 'mode: %s\n' "$mode"
            fi
            printf -- '---\n\n'

            emit_resource_refs "$source_file"
            render_contract_note_block 'partial'
            render_contract_block "$source_file"
            get_body "$source_file"
        } > "$out_file"

        track_generated "$out_file"
    done < <(jq -r '(.agents + .subagents)[] | [.name, .description, .path, (.mode // "")] | @tsv' "$IR_PATH")
}

main() {
    info "Claude Code adapter: generating configuration"

    generate_claude_md
    generate_commands
    generate_agent_files

    cleanup_with_manifest "claude_code" "${generated_files[@]}"

    info "Claude Code adapter complete"
}

main "$@"
