#!/usr/bin/env bash
# Generate Claude Code configuration from .agent/ source files
#
# Creates:
#   - CLAUDE.md            — project instructions with @import syntax
#   - .claude/commands/    — slash commands (from .agent/workflows/)
#   - .claude/agents/      — agents & subagents (from .agent/agents/ + .agent/subagents/)
#
# NOTE: As of Jan 24, 2026, Claude Code merged slash commands into skills.
# The .claude/commands/ files generated here are automatically treated as skills.
#
# Preserves: .claude/settings.local.json, .mcp.json
# Does NOT modify any .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
CLAUDE_MD="$ROOT_DIR/CLAUDE.md"
CLAUDE_DIR="$ROOT_DIR/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
AGENTS_DIR="$CLAUDE_DIR/agents"

# Create output directories
mkdir -p "$COMMANDS_DIR" "$AGENTS_DIR"

# ─── Helpers ───────────────────────────────────────────────────────────────────

# Extract a scalar YAML frontmatter value.
# Usage: get_frontmatter <file> <key>
get_frontmatter() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    grep "^${key}:" "$file" 2>/dev/null \
        | head -1 \
        | sed "s/^${key}:[[:space:]]*//" \
        | tr -d '"' \
        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Extract a YAML list field from frontmatter (one item per line).
# Usage: get_frontmatter_list <file> <key>
get_frontmatter_list() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    sed -n '/^---$/,/^---$/p' "$file" \
        | sed -n "/^${key}:$/,/^[^ ]/p" \
        | grep '^  - ' \
        | sed 's/^  - //' \
        | tr -d '"'
}

# Extract body content after YAML frontmatter (everything after closing ---).
# Usage: get_body <file>
get_body() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file"
}

# ─── CLAUDE.md ─────────────────────────────────────────────────────────────────

generate_claude_md() {
    local workflows_table="" skills_table="" agents_table=""

    # Build quick-commands table from workflows
    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue
        local wf_name description
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        workflows_table+="| \`/${wf_name}\` | ${description} |"$'\n'
    done

    # Build skills table
    for skill_dir in "$AGENT_DIR"/skills/*/; do
        [[ -f "${skill_dir}SKILL.md" ]] || continue
        local skill_name description
        skill_name=$(basename "$skill_dir")
        description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
        skills_table+="| \`${skill_name}\` | ${description} | \`.agent/skills/${skill_name}/SKILL.md\` |"$'\n'
    done

    # Build agents table (agents + subagents)
    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue
        local name description
        name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        agents_table+="| \`${name}\` | ${description} | Agent |"$'\n'
    done
    for sa_file in "$AGENT_DIR"/subagents/*.md; do
        [[ -f "$sa_file" ]] || continue
        local name description
        name=$(basename "$sa_file" .md)
        description=$(get_frontmatter "$sa_file" "description")
        agents_table+="| \`${name}\` | ${description} | Subagent |"$'\n'
    done

    cat > "$CLAUDE_MD" << HEADER
# QuickScale Development Agent

> **Auto-generated from \`.agent/\`** — Do not edit directly.
> Regenerate with: \`.agent/adapters/generate-all.sh\`

## Project Conventions

@.agent/contexts/project-conventions.md

## Authoritative Files

@.agent/contexts/authoritative-files.md

## Quick Commands

| Command | Description |
|---------|-------------|
${workflows_table}
## Skills

| Skill | Description | Source |
|-------|-------------|--------|
${skills_table}
## Agents

| Agent | Description | Type |
|-------|-------------|------|
${agents_table}
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
- No global mocking contamination (\`sys.modules\` modifications prohibited)
- Test isolation mandatory
- Coverage ≥ 90% overall, ≥ 80% per file

### Validation

\`\`\`bash
./scripts/lint.sh       # Ruff format + check + mypy
./scripts/test_unit.sh  # Unit and integration tests
\`\`\`

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
*Generated from .agent/ on $(date -Iseconds)*
HEADER
}

# ─── Slash Commands (from .agent/workflows/) ──────────────────────────────────

generate_commands() {
    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue

        local wf_name description command_file steps_summary
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        command_file="$COMMANDS_DIR/${wf_name}.md"

        # Extract step/stage headings from the workflow body
        steps_summary=$(get_body "$wf_file" \
            | grep -E '^## (Step|Stage) ' \
            | sed 's/^## //' \
            | nl -ba -s '. ' \
            | sed 's/^[[:space:]]*//' || true)

        # Fallback: any H2 headings
        if [[ -z "$steps_summary" ]]; then
            steps_summary=$(get_body "$wf_file" \
                | grep -E '^## ' \
                | head -8 \
                | nl -ba -s '. ' \
                | sed 's/^[[:space:]]*//' || true)
        fi

        {
            echo "---"
            echo "description: ${description}"
            echo "---"
            echo ""
            echo "Follow the ${wf_name} workflow."
            echo ""
            if [[ -n "$steps_summary" ]]; then
                echo "## Steps"
                echo ""
                echo "$steps_summary"
                echo ""
            fi
            echo "Target: \$ARGUMENTS"
            echo ""
            echo "Start by reading the full workflow: \`.agent/workflows/${wf_name}.md\`"
        } > "$command_file"
    done
}

# ─── Agents (from .agent/agents/) ─────────────────────────────────────────────

generate_agents() {
    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue

        local agent_name description body output_file
        agent_name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        body=$(get_body "$agent_file")
        output_file="$AGENTS_DIR/${agent_name}.md"

        # Map skills → command references
        local skills_refs=""
        while IFS= read -r skill; do
            [[ -z "$skill" ]] && continue
            skills_refs+="- Use \`/${skill}\` command for ${skill} guidance"$'\n'
        done < <(get_frontmatter_list "$agent_file" "skills")

        # Map delegates_to → agent references
        local delegates_refs=""
        while IFS= read -r delegate; do
            [[ -z "$delegate" ]] && continue
            delegates_refs+="- Delegate to \`${delegate}\` agent when needed"$'\n'
        done < <(get_frontmatter_list "$agent_file" "delegates_to")

        # Map workflows → command references
        local workflow_refs=""
        while IFS= read -r wf; do
            [[ -z "$wf" ]] && continue
            workflow_refs+="- Follow \`/${wf}\` workflow"$'\n'
        done < <(get_frontmatter_list "$agent_file" "workflows")

        # Write with only Claude-supported frontmatter fields
        {
            echo "---"
            echo "name: ${agent_name}"
            echo "description: ${description}"
            echo "---"
            echo ""
            if [[ -n "$skills_refs" || -n "$delegates_refs" || -n "$workflow_refs" ]]; then
                echo "## Available Resources"
                echo ""
                if [[ -n "$workflow_refs" ]]; then
                    echo "### Workflows"
                    echo ""
                    echo "$workflow_refs"
                fi
                if [[ -n "$skills_refs" ]]; then
                    echo "### Skills (as commands)"
                    echo ""
                    echo "$skills_refs"
                fi
                if [[ -n "$delegates_refs" ]]; then
                    echo "### Delegated Agents"
                    echo ""
                    echo "$delegates_refs"
                fi
                echo ""
            fi
            echo "$body"
        } > "$output_file"
    done
}

# ─── Subagents (from .agent/subagents/) ───────────────────────────────────────

generate_subagents() {
    for sa_file in "$AGENT_DIR"/subagents/*.md; do
        [[ -f "$sa_file" ]] || continue

        local sa_name description body output_file
        sa_name=$(basename "$sa_file" .md)
        description=$(get_frontmatter "$sa_file" "description")
        body=$(get_body "$sa_file")
        output_file="$AGENTS_DIR/${sa_name}.md"

        # Map skills → command references
        local skills_refs=""
        while IFS= read -r skill; do
            [[ -z "$skill" ]] && continue
            skills_refs+="- Use \`/${skill}\` command for ${skill} guidance"$'\n'
        done < <(get_frontmatter_list "$sa_file" "skills")

        # Write with only Claude-supported frontmatter fields
        {
            echo "---"
            echo "name: ${sa_name}"
            echo "description: ${description}"
            echo "---"
            echo ""
            if [[ -n "$skills_refs" ]]; then
                echo "## Available Skills (as commands)"
                echo ""
                echo "$skills_refs"
                echo ""
            fi
            echo "$body"
        } > "$output_file"
    done
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo "  📘 Claude Code adapter: generating configuration..."

    generate_claude_md
    echo "     ✅ CLAUDE.md"

    generate_commands
    local cmd_count
    cmd_count=$(find "$COMMANDS_DIR" -name '*.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .claude/commands/ (${cmd_count} commands)"

    generate_agents
    generate_subagents
    local agent_count
    agent_count=$(find "$AGENTS_DIR" -name '*.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .claude/agents/ (${agent_count} agents)"
}

main "$@"
