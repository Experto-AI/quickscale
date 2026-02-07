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
    cat "$AGENT_DIR/templates/quickscale/codex_header.md" > "$AGENTS_MD"

    {
        cat << 'BLOCK'

## Context Files

Read these before any development task:

1. `docs/technical/roadmap.md` - Current tasks and progress
2. `docs/technical/decisions.md` - IN/OUT of scope boundaries
3. `docs/contrib/code.md` - Implementation standards
4. `docs/contrib/review.md` - Quality checklist
5. `docs/contrib/testing.md` - Testing requirements

## Code Standards

### Python
- Python 3.11+
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no .format() or %)
- Ruff for formatting and linting (NOT Black or Flake8)
- Poetry for package management (NOT pip or requirements.txt)
- Dependencies in pyproject.toml (NOT setup.py)

### SOLID Principles
1. **Single Responsibility**: One class, one reason to change
2. **Open/Closed**: Open for extension, closed for modification
3. **Liskov**: Subtypes substitutable for base types
4. **Interface Segregation**: Small, focused interfaces
5. **Dependency Inversion**: Depend on abstractions

### Testing
- pytest with pytest-django
- NO global mocking (no sys.modules modifications)
- Test isolation mandatory
- Coverage minimum: 90% overall, 80% per file

### Architecture Layers
1. **Presentation**: Views, templates, API endpoints
2. **Application**: Services, commands, queries
3. **Domain**: Models, business logic
4. **Infrastructure**: Database, external services

### Frontend
- React 18+ with TypeScript
- Vite for build
- shadcn/ui for components
- Tailwind CSS for styling

## Scope Discipline

- Implement ONLY items in task checklist
- No "nice-to-have" features or opportunistic refactoring
- When in doubt, ask - do not assume

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

    generate_agents_md
    generate_codex_config

    cleanup_with_manifest "codex_cli" "${generated_files[@]}"

    info "Codex CLI adapter complete"
}

main "$@"
