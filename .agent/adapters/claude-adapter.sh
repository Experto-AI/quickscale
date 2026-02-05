#!/usr/bin/env bash
# Generate Claude Code configuration from .agent/ source files
# Creates: CLAUDE.md, .claude/ directory with commands

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
CLAUDE_MD="$ROOT_DIR/CLAUDE.md"
CLAUDE_DIR="$ROOT_DIR/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"

# Create directories
mkdir -p "$COMMANDS_DIR"

# Helper: Extract YAML frontmatter value
get_frontmatter() {
    local file="$1"
    local key="$2"
    grep "^$key:" "$file" 2>/dev/null | head -1 | sed "s/^$key: *//" | tr -d '"'
}

# Helper: Read file content after frontmatter
get_content() {
    local file="$1"
    sed -n '/^---$/,/^---$/!p' "$file" | tail -n +1
}

# Generate CLAUDE.md
generate_claude_md() {
    cat > "$CLAUDE_MD" << 'HEADER'
# QuickScale Development Agent

> **Auto-generated from `.agent/`** - Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Overview

This file configures Claude Code for QuickScale development with modular agents, skills, and workflows.

## Quick Commands

| Command | Description |
|---------|-------------|
| `/implement-task` | Implement next roadmap task |
| `/review-code` | Review staged changes |
| `/plan-sprint` | Plan next sprint |
| `/create-release` | Finalize release |

HEADER

    # Add Skills section
    echo "" >> "$CLAUDE_MD"
    echo "## Skills" >> "$CLAUDE_MD"
    echo "" >> "$CLAUDE_MD"
    echo "Available skills for code quality and workflow guidance:" >> "$CLAUDE_MD"
    echo "" >> "$CLAUDE_MD"
    echo "| Skill | Description |" >> "$CLAUDE_MD"
    echo "|-------|-------------|" >> "$CLAUDE_MD"

    for skill_dir in "$AGENT_DIR"/skills/*/; do
        if [[ -f "${skill_dir}SKILL.md" ]]; then
            skill_name=$(basename "$skill_dir")
            description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
            echo "| \`$skill_name\` | $description |" >> "$CLAUDE_MD"
        fi
    done

    # Add Agents section
    echo "" >> "$CLAUDE_MD"
    echo "## Agents" >> "$CLAUDE_MD"
    echo "" >> "$CLAUDE_MD"
    echo "| Agent | Description |" >> "$CLAUDE_MD"
    echo "|-------|-------------|" >> "$CLAUDE_MD"

    for agent_file in "$AGENT_DIR"/agents/*.md; do
        if [[ -f "$agent_file" ]]; then
            agent_name=$(basename "$agent_file" .md)
            description=$(get_frontmatter "$agent_file" "description")
            echo "| \`$agent_name\` | $description |" >> "$CLAUDE_MD"
        fi
    done

    # Add Workflows section
    echo "" >> "$CLAUDE_MD"
    echo "## Workflows" >> "$CLAUDE_MD"
    echo "" >> "$CLAUDE_MD"

    for workflow_file in "$AGENT_DIR"/workflows/*.md; do
        if [[ -f "$workflow_file" ]]; then
            workflow_name=$(basename "$workflow_file" .md)
            description=$(get_frontmatter "$workflow_file" "description")
            echo "### $workflow_name" >> "$CLAUDE_MD"
            echo "" >> "$CLAUDE_MD"
            echo "$description" >> "$CLAUDE_MD"
            echo "" >> "$CLAUDE_MD"
            echo "See: \`.agent/workflows/$workflow_name.md\`" >> "$CLAUDE_MD"
            echo "" >> "$CLAUDE_MD"
        fi
    done

    # Add Context section
    cat >> "$CLAUDE_MD" << 'CONTEXT'
## Context Files

Always read before development:

1. `docs/technical/roadmap.md` - Current tasks and progress
2. `docs/technical/decisions.md` - IN/OUT of scope
3. `docs/contrib/code.md` - Implementation standards
4. `docs/contrib/review.md` - Quality checklist

## Key Principles

### Scope Discipline
- Implement ONLY items in task checklist
- No "nice-to-have" features
- No opportunistic refactoring

### Code Quality
- SOLID, DRY, KISS principles
- Type hints on public APIs
- Google-style docstrings

### Testing
- No global mocking contamination
- Test isolation mandatory
- Coverage ≥ 70%

### Validation
```bash
./scripts/lint.sh
./scripts/test-all.sh
```

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Framework | Django 4.2+ |
| Package Manager | Poetry |
| Linting | Ruff |
| Testing | pytest |
| Frontend | React + Vite + shadcn/ui |

CONTEXT

    echo "" >> "$CLAUDE_MD"
    echo "---" >> "$CLAUDE_MD"
    echo "*Generated from .agent/ on $(date -Iseconds)*" >> "$CLAUDE_MD"
}

# Generate slash commands
generate_commands() {
    # /implement-task command
    cat > "$COMMANDS_DIR/implement-task.md" << 'EOF'
Follow the implement-task workflow from `.agent/workflows/implement-task.md`:

1. **PLAN**: Read context, identify task, confirm scope
2. **CODE**: Implement following code principles
3. **REVIEW**: Self-review against standards
4. **TEST**: Write tests, verify passing
5. **COMPLETE**: Update roadmap, stage changes

Task ID: $ARGUMENTS (or auto-detect from roadmap)

Start by reading `.agent/workflows/implement-task.md` for detailed steps.
EOF

    # /review-code command
    cat > "$COMMANDS_DIR/review-code.md" << 'EOF'
Follow the review-code workflow from `.agent/workflows/review-code.md`:

1. Gather context - read ALL staged files in full
2. Scope compliance - verify no out-of-scope changes
3. Architecture review - verify tech stack compliance
4. Code quality review - SOLID, DRY, KISS
5. Testing review - isolation, coverage
6. Documentation review - docstrings, comments
7. Validation - lint and tests
8. Generate report

Start by reading `.agent/workflows/review-code.md` for detailed steps.
EOF

    # /plan-sprint command
    cat > "$COMMANDS_DIR/plan-sprint.md" << 'EOF'
Follow the plan-sprint workflow from `.agent/workflows/plan-sprint.md`:

1. Analyze current state
2. Identify release scope
3. Prioritize tasks
4. Validate task scopes
5. Create sprint plan

Start by reading `.agent/workflows/plan-sprint.md` for detailed steps.
EOF

    # /create-release command
    cat > "$COMMANDS_DIR/create-release.md" << 'EOF'
Follow the create-release workflow from `.agent/workflows/create-release.md`:

1. Verify completion (tests pass)
2. Extract completed tasks
3. Generate commit message
4. Create release notes
5. Clean roadmap
6. Final review

Version: $ARGUMENTS

Start by reading `.agent/workflows/create-release.md` for detailed steps.
EOF
}

# Main execution
main() {
    generate_claude_md
    generate_commands
}

main "$@"
