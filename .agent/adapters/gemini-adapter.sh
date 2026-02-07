#!/usr/bin/env bash
# Generate Gemini CLI configuration from normalized .agent IR.

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

GEMINI_MD="$OUTPUT_ROOT/GEMINI.md"
GEMINI_DIR="$OUTPUT_ROOT/.gemini"
COMMANDS_DIR="$GEMINI_DIR/commands"
SETTINGS_JSON="$GEMINI_DIR/settings.json"
GEMINI_IGNORE="$OUTPUT_ROOT/.geminiignore"

mkdir -p "$COMMANDS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g; s/--*/-/g'
}

toml_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    echo "$s"
}

generate_gemini_md() {
    cat "$AGENT_DIR/templates/quickscale/gemini_header.md" > "$GEMINI_MD"

    jq -r '.contexts[] | "- @\(.path)"' "$IR_PATH" >> "$GEMINI_MD"

    {
        cat << 'BLOCK'

## Workflows

Run a workflow with `/workflow-name` or say *"Follow the workflow-name workflow"*.

| Command | Description | Source |
|---------|-------------|--------|
BLOCK
        jq -r '.workflows[] | "| `/\(.name)` | \(.description) | `@\(.path)` |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills

Skills provide reusable coding guidance. Load on demand via `@path` references.

| Skill | Description | Import |
|-------|-------------|--------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) | `@.agent/skills/\(.name)/SKILL.md` |"' "$IR_PATH"

        cat << 'BLOCK'

## Agents

Agents are comprehensive role definitions for complex multi-step tasks.

| Agent | Description | Workflows | Import |
|-------|-------------|-----------|--------|
BLOCK
        jq -r '.agents[] | "| `\(.name)` | \(.description) | \((.workflows | map("/" + .) | join(", "))) | `@\(.path)` |"' "$IR_PATH"

        cat << 'BLOCK'

## Subagents

Subagents handle focused sub-tasks delegated by agents.

| Subagent | Description | Import |
|----------|-------------|--------|
BLOCK
        jq -r '.subagents[] | "| `\(.name)` | \(.description) | `@\(.path)` |"' "$IR_PATH"

        cat << 'BLOCK'

## Key Principles

### Scope Discipline (CRITICAL)
- Implement ONLY items explicitly listed in task checklist
- NO "nice-to-have" features, NO opportunistic refactoring
- When in doubt, ask - do not assume

### Code Quality
- **SOLID** · **DRY** · **KISS** · **Explicit Failure**
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no `.format()` or `%`)

### Testing
- pytest with pytest-django - NO global mocking (`sys.modules` modifications prohibited)
- Test isolation mandatory · Coverage >= 90% overall, >= 80% per file

BLOCK
        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Platform support for structured contract fields: unsupported natively; contract metadata is preserved in source agent files.

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Framework | Django 4.2+ |
| Package Manager | Poetry (NOT pip/requirements.txt) |
| Package Config | pyproject.toml (NOT setup.py) |
| Linting | Ruff (NOT Black or Flake8) |
| Testing | pytest |
| Frontend | React 18+ with TypeScript |
| Build | Vite |
| Components | shadcn/ui |
| CSS | Tailwind CSS |

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$GEMINI_MD"

    track_generated "$GEMINI_MD"
}

generate_settings_json() {
    cat > "$SETTINGS_JSON" << 'JSON'
{
  "context": {
    "fileName": "GEMINI.md"
  },
  "skills": {
    "enabled": true
  },
  "experimental": {
    "enableAgents": true
  }
}
JSON

    track_generated "$SETTINGS_JSON"
}

owning_agent_for_workflow() {
    local workflow_name="$1"
    jq -r --arg wf "$workflow_name" '.agents[] | select((.workflows // []) | index($wf)) | .name' "$IR_PATH" | head -1
}

generate_commands() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue

        local wf_slug toml_file owning_agent steps_summary skills lines escaped_desc
        wf_slug="$(slugify "$wf_name")"
        toml_file="$COMMANDS_DIR/${wf_slug}.toml"
        owning_agent="$(owning_agent_for_workflow "$wf_name")"
        steps_summary="$(collect_step_headings "$ROOT_DIR/$wf_path")"

        lines="Follow the ${wf_name} workflow."$'\n\n'
        if [[ -n "$owning_agent" ]]; then
            lines+="Adopt the role defined in: @{.agent/agents/${owning_agent}.md}"$'\n\n'
            skills=$(jq -r --arg name "$owning_agent" '.agents[] | select(.name == $name) | ((.skills + .directives.skills) | unique[])' "$IR_PATH")
            if [[ -n "$skills" ]]; then
                lines+="Apply these skills:"$'\n'
                while IFS= read -r skill; do
                    [[ -n "$skill" ]] || continue
                    lines+="- @{.agent/skills/${skill}/SKILL.md}"$'\n'
                done <<< "$skills"
                lines+=$'\n'
            fi
        fi

        if [[ -n "$steps_summary" ]]; then
            lines+="## Steps"$'\n\n'
            lines+="$steps_summary"$'\n\n'
        fi

        lines+="Read the full workflow: @{${wf_path}}"$'\n\n'
        lines+="Arguments: {{args}}"

        escaped_desc="$(toml_escape "$wf_desc")"

        {
            printf 'description = "%s"\n' "$escaped_desc"
            printf 'steps = """\n'
            printf '%s\n' "$lines"
            printf '"""\n'
        } > "$toml_file"

        track_generated "$toml_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_geminiignore() {
    if [[ -f "$GEMINI_IGNORE" ]]; then
        track_generated "$GEMINI_IGNORE"
        return 0
    fi

    cat > "$GEMINI_IGNORE" << 'IGNORE'
# Auto-generated by .agent/adapters/gemini-adapter.sh
# Customize as needed; this file will be preserved if it already exists.

htmlcov/
*.egg-info/
dist/
build/
__pycache__/
.vscode/
.idea/
node_modules/
CLAUDE.md
.github/copilot-instructions.md
IGNORE

    track_generated "$GEMINI_IGNORE"
}

main() {
    info "Gemini CLI adapter: generating configuration"

    generate_gemini_md
    generate_settings_json
    generate_commands
    generate_geminiignore

    cleanup_with_manifest "gemini_cli" "${generated_files[@]}"

    info "Gemini CLI adapter complete"
}

main "$@"
