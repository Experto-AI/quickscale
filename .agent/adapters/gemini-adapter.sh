#!/usr/bin/env bash
# Generate Gemini CLI configuration from .agent/ source files
#
# Creates:
#   - GEMINI.md              — project instructions with @path imports
#   - .gemini/settings.json  — Gemini CLI project settings
#   - .gemini/commands/*.toml — slash commands (from .agent/workflows/)
#   - .geminiignore           — file filtering (only if absent)
#
# Leverages Gemini CLI native features (as of v0.27.0, Feb 3, 2026):
#   - @path imports in GEMINI.md for lazy file loading
#   - @{path} file injection in command steps
#   - {{args}} argument interpolation in commands
#   - skills.enabled for skill support
#   - Agent Skills (promoted to stable in v0.27.0)
#   - Event-driven architecture for improved performance
#
# Does NOT modify any .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
GEMINI_MD="$ROOT_DIR/GEMINI.md"
GEMINI_DIR="$ROOT_DIR/.gemini"
COMMANDS_DIR="$GEMINI_DIR/commands"
SETTINGS_JSON="$GEMINI_DIR/settings.json"
GEMINI_IGNORE="$ROOT_DIR/.geminiignore"

# Create output directories
mkdir -p "$COMMANDS_DIR"

# ─── Helpers ───────────────────────────────────────────────────────────────────

# Extract a scalar YAML frontmatter value.
# Usage: get_frontmatter <file> <key>
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

# Extract a YAML list field from frontmatter (one item per line).
# Usage: get_frontmatter_list <file> <key>
get_frontmatter_list() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    sed -n '/^---$/,/^---$/p' "$file" \
        | sed -n "/^${key}:$/,/^[^ -]/p" \
        | grep '^  *- ' \
        | sed 's/^  *- //' \
        | tr -d '"'
}

# Extract body content after YAML frontmatter (everything after closing ---).
# Usage: get_body <file>
get_body() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file"
}

# Sanitize a filename stem into a command-friendly slug.
slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g; s/--*/-/g'
}

# Escape a string for safe embedding in a TOML double-quoted value.
toml_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    echo "$s"
}

# ─── GEMINI.md (with @path imports) ───────────────────────────────────────────

generate_gemini_md() {
    local workflows_table="" skills_table="" agents_table="" subagents_table=""
    local context_imports=""

    # Build context @imports
    for ctx_file in "$AGENT_DIR"/contexts/*.md; do
        [[ -f "$ctx_file" ]] || continue
        local ctx_name
        ctx_name=$(basename "$ctx_file" .md)
        context_imports+="- @.agent/contexts/${ctx_name}.md"$'\n'
    done

    # Build workflows table
    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue
        local wf_name description
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        workflows_table+="| \`/${wf_name}\` | ${description} | \`@.agent/workflows/${wf_name}.md\` |"$'\n'
    done

    # Build skills table
    for skill_dir in "$AGENT_DIR"/skills/*/; do
        [[ -f "${skill_dir}SKILL.md" ]] || continue
        local skill_name description
        skill_name=$(basename "$skill_dir")
        description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
        skills_table+="| \`${skill_name}\` | ${description} | \`@.agent/skills/${skill_name}/SKILL.md\` |"$'\n'
    done

    # Build agents table
    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue
        local name description agent_workflows
        name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        agent_workflows=$(get_frontmatter_list "$agent_file" "workflows" \
            | sed 's/^/\//' | paste -sd ', ' - || true)
        agents_table+="| \`${name}\` | ${description} | ${agent_workflows} | \`@.agent/agents/${name}.md\` |"$'\n'
    done

    # Build subagents table
    for sa_file in "$AGENT_DIR"/subagents/*.md; do
        [[ -f "$sa_file" ]] || continue
        local name description
        name=$(basename "$sa_file" .md)
        description=$(get_frontmatter "$sa_file" "description")
        subagents_table+="| \`${name}\` | ${description} | \`@.agent/subagents/${name}.md\` |"$'\n'
    done

    cat > "$GEMINI_MD" << HEADER
# QuickScale Development Agent

> **Auto-generated from \`.agent/\`** — Do not edit directly.
> Regenerate with: \`.agent/adapters/generate-all.sh\`

## Context

Read these files to understand the project:

${context_imports}
## Workflows

Run a workflow with \`/workflow-name\` or say *"Follow the workflow-name workflow"*.

| Command | Description | Source |
|---------|-------------|--------|
${workflows_table}
## Skills

Skills provide reusable coding guidance. Load on demand via \`@path\` references.

| Skill | Description | Import |
|-------|-------------|--------|
${skills_table}
## Agents

Agents are comprehensive role definitions for complex multi-step tasks.

| Agent | Description | Workflows | Import |
|-------|-------------|-----------|--------|
${agents_table}
HEADER

    # Subagents section (only if any exist)
    if [[ -n "$subagents_table" ]]; then
        cat >> "$GEMINI_MD" << SUBAGENTS
## Subagents

Subagents handle focused sub-tasks delegated by agents.

| Subagent | Description | Import |
|----------|-------------|--------|
${subagents_table}
SUBAGENTS
    fi

    cat >> "$GEMINI_MD" << 'PRINCIPLES'
## Key Principles

### Scope Discipline (CRITICAL)
- Implement ONLY items explicitly listed in task checklist
- NO "nice-to-have" features, NO opportunistic refactoring
- When in doubt, ask — don't assume

### Code Quality
- **SOLID** · **DRY** · **KISS** · **Explicit Failure**
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no `.format()` or `%`)

### Testing
- pytest with pytest-django — NO global mocking (`sys.modules` modifications prohibited)
- Test isolation mandatory · Coverage ≥ 90% overall, ≥ 80% per file

### Validation

```bash
./scripts/lint.sh       # Ruff format + check + mypy
./scripts/test_unit.sh  # Unit and integration tests
```

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

PRINCIPLES

    echo "---" >> "$GEMINI_MD"
    echo "*Generated from .agent/ on $(date -Iseconds)*" >> "$GEMINI_MD"
}

# ─── .gemini/settings.json ────────────────────────────────────────────────────
# NOTE: Agent Skills promoted to stable in Gemini CLI v0.27.0 (Feb 3, 2026).
# The event-driven architecture improves performance and reliability.

generate_settings_json() {
    cat > "$SETTINGS_JSON" << 'SETTINGS'
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
SETTINGS
}

# ─── .gemini/commands/*.toml (from .agent/workflows/) ─────────────────────────

generate_commands() {
    # Remove previously generated commands to avoid stale leftovers
    rm -f "$COMMANDS_DIR"/*.toml

    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue

        local wf_name wf_desc wf_slug toml_file
        wf_name=$(basename "$wf_file" .md)
        wf_desc=$(get_frontmatter "$wf_file" "description")
        wf_slug=$(slugify "$wf_name")
        toml_file="$COMMANDS_DIR/${wf_slug}.toml"

        # Find the agent that owns this workflow (if any)
        local owning_agent=""
        for agent_file in "$AGENT_DIR"/agents/*.md; do
            [[ -f "$agent_file" ]] || continue
            if get_frontmatter_list "$agent_file" "workflows" | grep -qx "$wf_name"; then
                owning_agent=$(basename "$agent_file" .md)
                break
            fi
        done

        # Extract step/stage headings from the workflow body for a summary
        local steps_summary=""
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

        # Build multi-line steps content
        local steps=""
        steps="Follow the ${wf_name} workflow."$'\n'$'\n'

        if [[ -n "$owning_agent" ]]; then
            steps+="Adopt the role defined in: @{.agent/agents/${owning_agent}.md}"$'\n'$'\n'

            # Inject skill references for the owning agent
            local skills
            skills=$(get_frontmatter_list "$AGENT_DIR/agents/${owning_agent}.md" "skills")
            if [[ -n "$skills" ]]; then
                steps+="Apply these skills:"$'\n'
                while IFS= read -r skill; do
                    [[ -z "$skill" ]] && continue
                    if [[ -f "$AGENT_DIR/skills/${skill}/SKILL.md" ]]; then
                        steps+="- @{.agent/skills/${skill}/SKILL.md}"$'\n'
                    fi
                done <<< "$skills"
                steps+=$'\n'
            fi
        fi

        if [[ -n "$steps_summary" ]]; then
            steps+="## Steps"$'\n'$'\n'
            steps+="${steps_summary}"$'\n'$'\n'
        fi

        steps+="Read the full workflow: @{.agent/workflows/${wf_name}.md}"$'\n'$'\n'
        steps+="Arguments: {{args}}"

        # Escape description for TOML
        local escaped_desc
        escaped_desc=$(toml_escape "$wf_desc")

        # Write the TOML command file
        {
            echo "description = \"${escaped_desc}\""
            echo "steps = \"\"\""
            echo "$steps"
            echo "\"\"\""
        } > "$toml_file"
    done
}

# ─── .geminiignore (only if absent) ───────────────────────────────────────────

generate_geminiignore() {
    # Do not overwrite a user-customized ignore file
    [[ -f "$GEMINI_IGNORE" ]] && return 0

    cat > "$GEMINI_IGNORE" << 'IGNORE'
# Auto-generated by .agent/adapters/gemini-adapter.sh
# Customize as needed — this file won't be overwritten if it exists.

# Build artifacts
htmlcov/
*.egg-info/
dist/
build/
__pycache__/

# IDE / editor
.vscode/
.idea/

# Dependencies (large, not useful for context)
node_modules/

# Generated platform configs (avoid circular context)
CLAUDE.md
.github/copilot-instructions.md
IGNORE
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo "  💜 Gemini CLI adapter: generating configuration..."

    generate_gemini_md
    echo "     ✅ GEMINI.md"

    generate_settings_json
    echo "     ✅ .gemini/settings.json"

    generate_commands
    local cmd_count
    cmd_count=$(find "$COMMANDS_DIR" -name '*.toml' -type f 2>/dev/null | wc -l)
    echo "     ✅ .gemini/commands/ (${cmd_count} commands)"

    generate_geminiignore
    echo "     ✅ .geminiignore (preserved if existing)"
}

main "$@"
