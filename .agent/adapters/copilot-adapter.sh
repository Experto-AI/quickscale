#!/usr/bin/env bash
# Generate GitHub Copilot VS Code configuration from normalized .agent IR.

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

GITHUB_DIR="$OUTPUT_ROOT/.github"
COPILOT_MD="$GITHUB_DIR/copilot-instructions.md"
PROMPTS_DIR="$GITHUB_DIR/prompts"
CHATMODES_DIR="$GITHUB_DIR/chatmodes"
INSTRUCTIONS_DIR="$GITHUB_DIR/instructions"

mkdir -p "$PROMPTS_DIR" "$CHATMODES_DIR" "$INSTRUCTIONS_DIR"

lint_cmd="$(resolve_lint_command)"
test_cmd="$(resolve_test_command)"

declare -a generated_files=()
track_generated() {
    generated_files+=("$(abs_to_rel "$1")")
}

owner_agent_for_workflow() {
    local wf_name="$1"
    jq -r --arg wf "$wf_name" '.agents[] | select((.workflows // []) | index($wf)) | .name' "$IR_PATH" | head -1
}

prompt_target_for_workflow() {
    local wf_name="$1"
    if [[ "$wf_name" == "create-release" ]]; then
        printf '%s\n' '${input:releaseVersion}'
    else
        printf '%s\n' '${input:taskId}'
    fi
}

generate_copilot_instructions() {
    cat "$(template_path "copilot_header.md")" > "$COPILOT_MD"

    {
        cat << 'BLOCK'

## Code Standards

### Python Style
- Python 3.11+
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no `.format()` or `%`)
- Ruff for formatting and linting (NOT Black or Flake8)

### Package Management
- Use Poetry (NOT pip or requirements.txt)
- Dependencies in pyproject.toml (NOT setup.py)

### Testing
- pytest with pytest-django
- NO global mocking (no sys.modules modifications)
- Test isolation mandatory
- Coverage minimum: 90% overall, 80% per file

## SOLID Principles

1. **Single Responsibility**: One class, one reason to change
2. **Open/Closed**: Open for extension, closed for modification
3. **Liskov**: Subtypes substitutable for base types
4. **Interface Segregation**: Small, focused interfaces
5. **Dependency Inversion**: Depend on abstractions

## Available Prompts

Use these in Copilot Chat with `#` or via the prompt picker:

| Prompt | Description |
|--------|-------------|
BLOCK
        jq -r '.workflows[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        cat << 'BLOCK'

## Available Chat Modes

Use in Copilot Chat by selecting the mode:

| Mode | Description |
|------|-------------|
BLOCK
        jq -r '(.agents + .subagents)[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        cat << 'BLOCK'

## Skills Reference

Detailed guidance available in `.agent/skills/`:

| Skill | Description |
|-------|-------------|
BLOCK
        jq -r '.skills[] | "| `\(.name)` | \(.description) |"' "$IR_PATH"

        render_validation_block "$lint_cmd" "$test_cmd"

        cat << 'BLOCK'
## Contract Notes

Copilot instructions support textual contracts. Structured contract fields are preserved in generated `.chatmode.md` files.

---
BLOCK
        printf '*Generated from .agent/ on %s*\n' "$(date -Iseconds)"
    } >> "$COPILOT_MD"

    track_generated "$COPILOT_MD"
}

generate_prompts() {
    while IFS=$'\t' read -r wf_name wf_desc wf_path; do
        [[ -n "$wf_name" ]] || continue
        local prompt_file owner_agent steps target
        prompt_file="$PROMPTS_DIR/${wf_name}.prompt.md"
        owner_agent="$(owner_agent_for_workflow "$wf_name")"
        steps="$(collect_step_headings "$ROOT_DIR/$wf_path")"
        target="$(prompt_target_for_workflow "$wf_name")"

        {
            printf -- '---\n'
            printf -- 'description: "%s"\n' "$wf_desc"
            if [[ -n "$owner_agent" ]]; then
                printf -- 'mode: %s\n' "$owner_agent"
            else
                printf -- 'mode: agent\n'
            fi
            printf -- 'tools:\n'
            printf -- '  - changes\n'
            printf -- '  - codebase\n'
            printf -- '  - editFiles\n'
            printf -- '  - terminalLastCommand\n'
            printf -- '  - runInTerminal\n'
            printf -- '  - findFiles\n'
            printf -- '  - search\n'
            printf -- '  - usages\n'
            printf -- '  - problems\n'
            printf -- '---\n\n'

            printf -- 'Follow the %s workflow for project development.\n\n' "$wf_name"
            if [[ -n "$steps" ]]; then
                printf -- '## Steps\n\n%s\n\n' "$(echo "$steps" | sed 's/^/- /')"
            fi
            printf -- 'Target: %s\n\n' "$target"
            printf -- 'Read the full workflow at `%s` and follow it step by step.\n\n' "$wf_path"

            render_validation_block "$lint_cmd" "$test_cmd"
        } > "$prompt_file"

        track_generated "$prompt_file"
    done < <(jq -r '.workflows[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_chatmodes() {
    while IFS=$'\t' read -r name description path; do
        [[ -n "$name" ]] || continue
        local source_file="$ROOT_DIR/$path"
        local out_file="$CHATMODES_DIR/${name}.chatmode.md"

        delegates=$( {
            get_frontmatter_list "$source_file" "delegates_to"
            get_directives "$source_file" "agent"
        } | awk 'NF' | sort -u )
        skills=$( {
            get_frontmatter_list "$source_file" "skills"
            get_directives "$source_file" "skill"
        } | awk 'NF' | sort -u )
        workflows=$( {
            get_frontmatter_list "$source_file" "workflows"
            get_directives "$source_file" "workflow"
        } | awk 'NF' | sort -u )

        {
            printf -- '---\n'
            printf -- 'description: "%s"\n' "$description"
            printf -- 'whenToUse: "%s"\n' "$description"
            printf -- 'groups:\n'
            printf -- '  - generated\n'
            printf -- 'tools:\n'
            printf -- '  - changes\n'
            printf -- '  - codebase\n'
            printf -- '  - editFiles\n'
            printf -- '  - fetch\n'
            printf -- '  - findFiles\n'
            printf -- '  - githubRepo\n'
            printf -- '  - problems\n'
            printf -- '  - runInTerminal\n'
            printf -- '  - search\n'
            printf -- '  - terminalLastCommand\n'
            printf -- '  - usages\n'
            printf -- '---\n\n'

            if [[ -n "$skills" ]]; then
                printf -- '## Skills\n\n'
                while IFS= read -r skill; do
                    [[ -n "$skill" ]] || continue
                    printf -- '- Read `.agent/skills/%s/SKILL.md`\n' "$skill"
                done <<< "$skills"
                printf '\n'
            fi

            if [[ -n "$workflows" ]]; then
                printf -- '## Workflows\n\n'
                while IFS= read -r wf; do
                    [[ -n "$wf" ]] || continue
                    printf -- '- Follow `.agent/workflows/%s.md`\n' "$wf"
                done <<< "$workflows"
                printf '\n'
            fi

            if [[ -n "$delegates" ]]; then
                printf -- '## Delegation\n\n'
                while IFS= read -r delegate; do
                    [[ -n "$delegate" ]] || continue
                    printf -- '- Delegate to chat mode `%s` when needed\n' "$delegate"
                done <<< "$delegates"
                printf '\n'
            fi

            render_contract_note_block 'textual'
            render_contract_block "$source_file"
            get_body "$source_file"
        } > "$out_file"

        track_generated "$out_file"
    done < <(jq -r '(.agents + .subagents)[] | [.name, .description, .path] | @tsv' "$IR_PATH")
}

generate_instructions() {
    cat > "$INSTRUCTIONS_DIR/python.instructions.md" << 'BLOCK'
---
applyTo: "**/*.py"
---
- Use Python 3.11+ features
- Type hints on all public functions and methods
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for string formatting (no .format() or %)
- Ruff for formatting and linting
- Poetry for package management (pyproject.toml, not setup.py)
- pytest for testing (not unittest alone)
- No bare except clauses
- No global mocking (no sys.modules modifications)
- Follow SOLID, DRY, KISS principles
BLOCK

    cat > "$INSTRUCTIONS_DIR/testing.instructions.md" << 'BLOCK'
---
applyTo: "**/test_*.py,**/tests/**/*.py"
---
- Use pytest fixtures and parametrize
- Each test must be independent (no shared mutable state)
- No global mocking contamination (no sys.modules modifications)
- Use unittest.mock.patch as context manager or decorator
- Test isolation mandatory
- Coverage minimum: 90% overall, 80% per file
- Name tests: test_{what}_{condition}_{expected}
- Implementation-first: tests written after code review
BLOCK

    cat > "$INSTRUCTIONS_DIR/frontend.instructions.md" << 'BLOCK'
---
applyTo: "**/*.{ts,tsx,js,jsx}"
---
- React 18+ with TypeScript
- Vite for build tooling
- shadcn/ui for components (not MUI, Chakra)
- Tailwind CSS for styling
- TanStack Query for server state
BLOCK

    cat > "$INSTRUCTIONS_DIR/docs.instructions.md" << 'BLOCK'
---
applyTo: "**/*.md"
---
- Use kebab-case for markdown filenames
- Keep documentation concise and actionable
- Comments explain why, not what
BLOCK

    track_generated "$INSTRUCTIONS_DIR/python.instructions.md"
    track_generated "$INSTRUCTIONS_DIR/testing.instructions.md"
    track_generated "$INSTRUCTIONS_DIR/frontend.instructions.md"
    track_generated "$INSTRUCTIONS_DIR/docs.instructions.md"
}

main() {
    info "Copilot VS Code adapter: generating configuration"
    assert_capability_value "github_copilot" "supports.prompts" "prompt_md"
    assert_capability_value "github_copilot" "supports.agents" "chat_mode_md"

    generate_copilot_instructions
    generate_prompts
    generate_chatmodes
    generate_instructions

    cleanup_with_manifest "github_copilot" "${generated_files[@]}"

    info "Copilot VS Code adapter complete"
}

main "$@"
