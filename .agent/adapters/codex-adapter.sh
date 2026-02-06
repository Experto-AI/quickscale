#!/usr/bin/env bash
# Generate OpenAI Codex CLI configuration from .agent/ source files
#
# Creates:
#   - AGENTS.md         — hierarchical project instructions (Codex primary config)
#   - .codex/config.toml — Codex CLI settings (sandbox, model defaults)
#
# Leverages Codex CLI native features:
#   - AGENTS.md at repo root (primary instruction file, auto-read)
#   - Hierarchical AGENTS.md in subdirectories (nested instructions)
#   - .codex/config.toml for model, sandbox, and MCP configuration
#   - .agent/skills/*/SKILL.md already compatible with agentskills.io standard
#   - AGENTS.override.md for per-directory overrides
#
# Does NOT modify any .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
AGENTS_MD="$ROOT_DIR/AGENTS.md"
CODEX_DIR="$ROOT_DIR/.codex"
CODEX_CONFIG="$CODEX_DIR/config.toml"

# Create output directories
mkdir -p "$CODEX_DIR"

# ─── Helpers ───────────────────────────────────────────────────────────────────

# Extract a scalar YAML frontmatter value.
get_frontmatter() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    sed -n '/^---$/,/^---$/p' "$file" \
        | grep "^${key}:" \
        | head -1 \
        | sed "s/^${key}:[[:space:]]*//" \
        | tr -d '"' \
        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Extract a YAML list field from frontmatter.
get_frontmatter_list() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    sed -n '/^---$/,/^---$/p' "$file" \
        | sed -n "/^${key}:$/,/^[^ ]/p" \
        | grep '^  - ' \
        | sed 's/^  - //' \
        | tr -d '"'
}

# Extract body content after YAML frontmatter.
get_body() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file"
}

# ─── AGENTS.md ─────────────────────────────────────────────────────────────────

generate_agents_md() {
    cat > "$AGENTS_MD" << 'HEADER'
# QuickScale Development Agent

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Project Overview

QuickScale is a Django project generator that creates production-ready SaaS applications.
This file provides instructions for AI coding agents working on this codebase.

## Context Files

Read these before any development task:

1. `docs/technical/roadmap.md` — Current tasks and progress
2. `docs/technical/decisions.md` — IN/OUT of scope boundaries
3. `docs/contrib/code.md` — Implementation standards
4. `docs/contrib/review.md` — Quality checklist
5. `docs/contrib/testing.md` — Testing requirements

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
- When in doubt, ask — don't assume

HEADER

    # Add Agents section
    {
        echo "## Agents"
        echo ""
        echo "Available agent definitions for complex workflows:"
        echo ""
        echo "| Agent | Description | Workflow |"
        echo "|-------|-------------|----------|"
    } >> "$AGENTS_MD"

    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue
        local name description workflows
        name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        workflows=$(get_frontmatter_list "$agent_file" "workflows" | tr '\n' ',' | sed 's/,$//')
        echo "| \`${name}\` | ${description} | ${workflows} |" >> "$AGENTS_MD"
    done

    # Add Skills section
    {
        echo ""
        echo "## Skills"
        echo ""
        echo "Reusable guidance modules in \`.agent/skills/\`:"
        echo ""
        echo "| Skill | Description | Path |"
        echo "|-------|-------------|------|"
    } >> "$AGENTS_MD"

    for skill_dir in "$AGENT_DIR"/skills/*/; do
        [[ -f "${skill_dir}SKILL.md" ]] || continue
        local skill_name description
        skill_name=$(basename "$skill_dir")
        description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
        echo "| \`${skill_name}\` | ${description} | \`.agent/skills/${skill_name}/SKILL.md\` |" >> "$AGENTS_MD"
    done

    # Add Workflows section with details
    {
        echo ""
        echo "## Workflows"
        echo ""
        echo "Step-by-step execution plans:"
        echo ""
    } >> "$AGENTS_MD"

    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue
        local wf_name description
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")

        {
            echo "### ${wf_name}"
            echo ""
            echo "${description}"
            echo ""
            echo "Details: \`.agent/workflows/${wf_name}.md\`"
            echo ""

            # Extract steps
            local steps
            steps=$(get_body "$wf_file" \
                | grep -E '^## (Step|Stage) ' \
                | sed 's/^## /- /' || true)
            if [[ -z "$steps" ]]; then
                steps=$(get_body "$wf_file" \
                    | grep -E '^## ' \
                    | head -8 \
                    | sed 's/^## /- /' || true)
            fi
            if [[ -n "$steps" ]]; then
                echo "$steps"
                echo ""
            fi
        } >> "$AGENTS_MD"
    done

    # Add validation section
    cat >> "$AGENTS_MD" << 'VALIDATION'
## Validation

Always run before completing work:

```bash
./scripts/lint.sh      # Ruff format + check + mypy
./scripts/test_unit.sh # Unit and integration tests
```

VALIDATION

    {
        echo ""
        echo "---"
        echo "*Generated from .agent/ on $(date -Iseconds)*"
    } >> "$AGENTS_MD"
}

# ─── .codex/config.toml ───────────────────────────────────────────────────────

generate_codex_config() {
    # Only create if it doesn't exist (preserve user customization)
    if [[ -f "$CODEX_CONFIG" ]]; then
        return 0
    fi

    cat > "$CODEX_CONFIG" << 'CONFIG'
# Codex CLI project configuration
# Auto-generated from .agent/ — customize as needed
# See: https://developers.openai.com/codex/config-advanced

# Sandbox mode: workspace-write allows edits within the repo
sandbox_mode = "workspace-write"

# AGENTS.md is automatically read as the primary instruction file by Codex CLI.
# The fallback filenames below are used only if AGENTS.md is not found.
project_doc_fallback_filenames = ["CLAUDE.md", "GEMINI.md"]

# Notification on agent turn completion (optional)
# notify = "terminal-bell"
CONFIG
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo "  🤖 Codex CLI adapter: generating configuration..."

    generate_agents_md
    echo "     ✅ AGENTS.md"

    generate_codex_config
    if [[ -f "$CODEX_CONFIG" ]]; then
        echo "     ✅ .codex/config.toml"
    else
        echo "     ⏭️  .codex/config.toml (preserved existing)"
    fi
}

main "$@"
