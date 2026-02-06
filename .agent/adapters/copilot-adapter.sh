#!/usr/bin/env bash
# Generate GitHub Copilot configuration from .agent/ source files
#
# Creates:
#   - .github/copilot-instructions.md          — always-on project instructions
#   - .github/prompts/*.prompt.md              — reusable prompt files (from workflows)
#   - .github/agents/*.agent.md                — custom coding agents (from agents)
#   - .github/instructions/*.instructions.md   — path-specific instructions (from contexts)
#
# Leverages GitHub Copilot native features (VS Code 1.108+):
#   - copilot-instructions.md for always-on project guidance
#   - .prompt.md files with YAML frontmatter (description, tools, mode)
#   - .agent.md files with YAML frontmatter (description, tools, agents)
#   - .instructions.md files with applyTo globs for path-specific rules
#   - AGENTS.md support (added Aug 28, 2025)
#   - Experimental Agent Skills (in active development)
#
# Does NOT modify any .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
GITHUB_DIR="$ROOT_DIR/.github"
COPILOT_MD="$GITHUB_DIR/copilot-instructions.md"
PROMPTS_DIR="$GITHUB_DIR/prompts"
AGENTS_DIR="$GITHUB_DIR/agents"
INSTRUCTIONS_DIR="$GITHUB_DIR/instructions"

# Create output directories
mkdir -p "$PROMPTS_DIR" "$AGENTS_DIR" "$INSTRUCTIONS_DIR"

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

# ─── copilot-instructions.md ──────────────────────────────────────────────────

generate_copilot_instructions() {
    cat > "$COPILOT_MD" << 'HEADER'
# QuickScale Development Instructions

> **Auto-generated from `.agent/`** - Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Project Overview

QuickScale is a Django project generator that creates production-ready SaaS applications.

## Code Standards

### Python Style
- Python 3.11+
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no .format() or %)
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

## Code Patterns

### DO
```python
# Type hints
def process_data(data: dict) -> Result:
    """Process input data and return result"""
    ...

# Explicit error handling
try:
    result = operation()
except SpecificError as e:
    raise ProcessingError(f"Operation failed: {e}")

# Dependency injection
class Service:
    def __init__(self, repository: Repository):
        self._repository = repository
```

### DON'T
```python
# No bare except
try:
    ...
except:  # ❌ Never
    pass

# No global mocking in tests
sys.modules['module'] = mock  # ❌ Never

# No requirements.txt
# requirements.txt  # ❌ Use pyproject.toml
```

## Architecture

### Layers
1. **Presentation**: Views, templates, API endpoints
2. **Application**: Services, commands, queries
3. **Domain**: Models, business logic
4. **Infrastructure**: Database, external services

### Rules
- Views must not access database directly (use services)
- Models must not call external services
- Infrastructure must not depend on presentation

## Frontend Stack

- React 18+ with TypeScript
- Vite for build
- shadcn/ui for components
- Tailwind CSS for styling
- TanStack Query for server state

HEADER

    # Add available prompts/agents section
    {
        echo "## Available Prompts"
        echo ""
        echo "Use these in Copilot Chat with \`#\` or via the prompt picker:"
        echo ""
        echo "| Prompt | Description |"
        echo "|--------|-------------|"
    } >> "$COPILOT_MD"

    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue
        local wf_name description
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        echo "| \`${wf_name}\` | ${description} |" >> "$COPILOT_MD"
    done

    {
        echo ""
        echo "## Available Agents"
        echo ""
        echo "Use in Copilot Chat with \`@agent-name\`:"
        echo ""
        echo "| Agent | Description |"
        echo "|-------|-------------|"
    } >> "$COPILOT_MD"

    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue
        local name description
        name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        echo "| \`${name}\` | ${description} |" >> "$COPILOT_MD"
    done

    {
        echo ""
        echo "## Skills Reference"
        echo ""
        echo "Detailed guidance available in \`.agent/skills/\`:"
        echo ""
        echo "| Skill | Description |"
        echo "|-------|-------------|"
    } >> "$COPILOT_MD"

    for skill_dir in "$AGENT_DIR"/skills/*/; do
        [[ -f "${skill_dir}SKILL.md" ]] || continue
        local skill_name description
        skill_name=$(basename "$skill_dir")
        description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
        echo "| \`${skill_name}\` | ${description} |" >> "$COPILOT_MD"
    done

    cat >> "$COPILOT_MD" << 'VALIDATION'

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
    } >> "$COPILOT_MD"
}

# ─── Prompt Files (from .agent/workflows/) ─────────────────────────────────────

generate_prompts() {
    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue

        local wf_name description prompt_file agent_name
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        prompt_file="$PROMPTS_DIR/${wf_name}.prompt.md"

        # Find which agent uses this workflow
        agent_name=""
        for agent_file in "$AGENT_DIR"/agents/*.md; do
            [[ -f "$agent_file" ]] || continue
            if get_frontmatter_list "$agent_file" "workflows" | grep -qx "$wf_name" 2>/dev/null; then
                agent_name=$(basename "$agent_file" .md)
                break
            fi
        done

        # Extract step summaries from workflow
        local steps_summary
        steps_summary=$(get_body "$wf_file" \
            | grep -E '^## (Step|Stage) ' \
            | sed 's/^## /- /' || true)
        if [[ -z "$steps_summary" ]]; then
            steps_summary=$(get_body "$wf_file" \
                | grep -E '^## ' \
                | head -8 \
                | sed 's/^## /- /' || true)
        fi

        {
            echo "---"
            echo "description: \"${description}\""
            echo "mode: agent"
            echo "tools:"
            echo "  - changes"
            echo "  - codebase"
            echo "  - editFiles"
            echo "  - terminalLastCommand"
            echo "  - runInTerminal"
            echo "  - findFiles"
            echo "  - search"
            echo "  - usages"
            if [[ -n "$agent_name" ]]; then
                echo "  - problems"
            fi
            echo "---"
            echo ""
            echo "Follow the ${wf_name} workflow for QuickScale development."
            echo ""
            if [[ -n "$steps_summary" ]]; then
                echo "## Steps"
                echo ""
                echo "$steps_summary"
                echo ""
            fi
            echo "Target: \${input:taskId}"
            echo ""
            echo "Read the full workflow at \`.agent/workflows/${wf_name}.md\` and follow it step by step."
            echo ""
            echo "Always validate with:"
            echo "\`\`\`bash"
            echo "./scripts/lint.sh"
            echo "./scripts/test_unit.sh"
            echo "\`\`\`"
        } > "$prompt_file"
    done
}

# ─── Agent Files (from .agent/agents/) ─────────────────────────────────────────

generate_agents() {
    for agent_file in "$AGENT_DIR"/agents/*.md; do
        [[ -f "$agent_file" ]] || continue

        local agent_name description output_file body
        agent_name=$(basename "$agent_file" .md)
        description=$(get_frontmatter "$agent_file" "description")
        body=$(get_body "$agent_file")
        output_file="$AGENTS_DIR/${agent_name}.agent.md"

        # Build sub-agents list if delegates_to is non-empty
        local agents_yaml=""
        local has_delegates=false
        while IFS= read -r delegate; do
            [[ -z "$delegate" ]] && continue
            if [[ "$has_delegates" == "false" ]]; then
                agents_yaml="agents:"
                has_delegates=true
            fi
            agents_yaml+=$'\n'"  - .github/agents/${delegate}.agent.md"
        done < <(get_frontmatter_list "$agent_file" "delegates_to")

        # Write agent file
        {
            echo "---"
            echo "description: \"${description}\""
            echo "tools:"
            echo "  - changes"
            echo "  - codebase"
            echo "  - editFiles"
            echo "  - fetch"
            echo "  - findFiles"
            echo "  - githubRepo"
            echo "  - problems"
            echo "  - runInTerminal"
            echo "  - search"
            echo "  - terminalLastCommand"
            echo "  - usages"
            if [[ -n "$agents_yaml" ]]; then
                echo "${agents_yaml}"
            fi
            echo "---"
            echo ""

            # Include skills references
            local skills_section=""
            while IFS= read -r skill; do
                [[ -z "$skill" ]] && continue
                skills_section+="- Read \`.agent/skills/${skill}/SKILL.md\` for ${skill} guidance"$'\n'
            done < <(get_frontmatter_list "$agent_file" "skills")

            if [[ -n "$skills_section" ]]; then
                echo "## Skills"
                echo ""
                echo "$skills_section"
            fi

            # Include workflow references
            local wf_section=""
            while IFS= read -r wf; do
                [[ -z "$wf" ]] && continue
                wf_section+="- Follow \`.agent/workflows/${wf}.md\`"$'\n'
            done < <(get_frontmatter_list "$agent_file" "workflows")

            if [[ -n "$wf_section" ]]; then
                echo "## Workflows"
                echo ""
                echo "$wf_section"
            fi

            echo ""
            echo "$body"
        } > "$output_file"
    done

    # Also generate agent files for subagents
    for sa_file in "$AGENT_DIR"/subagents/*.md; do
        [[ -f "$sa_file" ]] || continue

        local sa_name description output_file body
        sa_name=$(basename "$sa_file" .md)
        description=$(get_frontmatter "$sa_file" "description")
        body=$(get_body "$sa_file")
        output_file="$AGENTS_DIR/${sa_name}.agent.md"

        {
            echo "---"
            echo "description: \"${description}\""
            echo "tools:"
            echo "  - changes"
            echo "  - codebase"
            echo "  - findFiles"
            echo "  - problems"
            echo "  - search"
            echo "  - usages"
            echo "---"
            echo ""

            local skills_section=""
            while IFS= read -r skill; do
                [[ -z "$skill" ]] && continue
                skills_section+="- Read \`.agent/skills/${skill}/SKILL.md\` for ${skill} guidance"$'\n'
            done < <(get_frontmatter_list "$sa_file" "skills")

            if [[ -n "$skills_section" ]]; then
                echo "## Skills"
                echo ""
                echo "$skills_section"
            fi

            echo ""
            echo "$body"
        } > "$output_file"
    done
}

# ─── Path-Specific Instructions (from .agent/contexts/) ────────────────────────

generate_instructions() {
    # Python source files instruction
    cat > "$INSTRUCTIONS_DIR/python.instructions.md" << 'EOF'
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
EOF

    # Test files instruction
    cat > "$INSTRUCTIONS_DIR/testing.instructions.md" << 'EOF'
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
EOF

    # Frontend instruction
    cat > "$INSTRUCTIONS_DIR/frontend.instructions.md" << 'EOF'
---
applyTo: "**/*.{ts,tsx,js,jsx}"
---
- React 18+ with TypeScript
- Vite for build tooling
- shadcn/ui for components (not MUI, Chakra)
- Tailwind CSS for styling
- TanStack Query for server state
EOF

    # Documentation instruction
    cat > "$INSTRUCTIONS_DIR/docs.instructions.md" << 'EOF'
---
applyTo: "**/*.md"
---
- Use kebab-case for markdown filenames
- Google-style docstrings referenced in docs
- Comments explain "why" not "what"
- Keep documentation concise and actionable
EOF
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo "  🐙 Copilot adapter: generating configuration..."

    generate_copilot_instructions
    echo "     ✅ .github/copilot-instructions.md"

    generate_prompts
    local prompt_count
    prompt_count=$(find "$PROMPTS_DIR" -name '*.prompt.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .github/prompts/ (${prompt_count} prompts)"

    generate_agents
    local agent_count
    agent_count=$(find "$AGENTS_DIR" -name '*.agent.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .github/agents/ (${agent_count} agents)"

    generate_instructions
    local instr_count
    instr_count=$(find "$INSTRUCTIONS_DIR" -name '*.instructions.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .github/instructions/ (${instr_count} instruction sets)"
}

main "$@"
