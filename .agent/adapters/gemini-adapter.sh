#!/usr/bin/env bash
# Generate Gemini CLI configuration from .agent/ source files
# Creates: GEMINI.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output path
GEMINI_MD="$ROOT_DIR/GEMINI.md"

# Helper: Extract YAML frontmatter value
get_frontmatter() {
    local file="$1"
    local key="$2"
    grep "^$key:" "$file" 2>/dev/null | head -1 | sed "s/^$key: *//" | tr -d '"'
}

# Helper: Check if file has invoke directives
has_invokes() {
    local file="$1"
    grep -q "invoke-skill:\|invoke-agent:" "$file" 2>/dev/null
}

# Generate GEMINI.md
generate_gemini_md() {
    cat > "$GEMINI_MD" << 'HEADER'
# QuickScale Development Agent

> **Auto-generated from `.agent/`** - Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Overview

This file configures Gemini CLI for QuickScale development with skills and workflows.

## Workflows

To run a workflow, say "Follow the [workflow-name] workflow".

HEADER

    # Add Workflows
    for workflow_file in "$AGENT_DIR"/workflows/*.md; do
        if [[ -f "$workflow_file" ]]; then
            workflow_name=$(basename "$workflow_file" .md)
            description=$(get_frontmatter "$workflow_file" "description")
            echo "### $workflow_name" >> "$GEMINI_MD"
            echo "" >> "$GEMINI_MD"
            echo "**Description**: $description" >> "$GEMINI_MD"
            echo "" >> "$GEMINI_MD"
            echo "**Trigger**: \"Follow the $workflow_name workflow\"" >> "$GEMINI_MD"
            echo "" >> "$GEMINI_MD"
            echo "**Details**: See \`.agent/workflows/$workflow_name.md\`" >> "$GEMINI_MD"
            echo "" >> "$GEMINI_MD"
        fi
    done

    # Add Skills section
    echo "## Skills" >> "$GEMINI_MD"
    echo "" >> "$GEMINI_MD"
    echo "Skills provide reusable guidance. To use a skill, reference its SKILL.md file." >> "$GEMINI_MD"
    echo "" >> "$GEMINI_MD"
    echo "| Skill | Path | Description |" >> "$GEMINI_MD"
    echo "|-------|------|-------------|" >> "$GEMINI_MD"

    for skill_dir in "$AGENT_DIR"/skills/*/; do
        if [[ -f "${skill_dir}SKILL.md" ]]; then
            skill_name=$(basename "$skill_dir")
            description=$(get_frontmatter "${skill_dir}SKILL.md" "description")
            echo "| $skill_name | \`.agent/skills/$skill_name/SKILL.md\` | $description |" >> "$GEMINI_MD"
        fi
    done

    # Add Agents section
    echo "" >> "$GEMINI_MD"
    echo "## Agents" >> "$GEMINI_MD"
    echo "" >> "$GEMINI_MD"
    echo "Agents are comprehensive guides for complex tasks." >> "$GEMINI_MD"
    echo "" >> "$GEMINI_MD"
    echo "| Agent | Path | Description |" >> "$GEMINI_MD"
    echo "|-------|------|-------------|" >> "$GEMINI_MD"

    for agent_file in "$AGENT_DIR"/agents/*.md; do
        if [[ -f "$agent_file" ]]; then
            agent_name=$(basename "$agent_file" .md)
            description=$(get_frontmatter "$agent_file" "description")
            echo "| $agent_name | \`.agent/agents/$agent_name.md\` | $description |" >> "$GEMINI_MD"
        fi
    done

    # Add Core Principles
    cat >> "$GEMINI_MD" << 'PRINCIPLES'

## Core Principles

### Scope Discipline (CRITICAL)
- Implement ONLY items explicitly listed in task checklist
- NO "nice-to-have" features
- NO opportunistic refactoring
- When in doubt, ask - don't assume

### Code Quality Standards
- **SOLID**: Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion
- **DRY**: Don't Repeat Yourself - no code duplication
- **KISS**: Keep It Simple - no over-engineering
- **Explicit Failure**: No bare except, no silent failures

### Testing Standards
- **No global mocking contamination** (no sys.modules modifications)
- Test isolation mandatory (each test independent)
- Coverage minimum: 90% overall, 80% per file
- Implementation-first (write tests after code review)

### Documentation Standards
- Google-style docstrings (single-line preferred)
- No ending punctuation on single-line docstrings
- Comments explain "why" not "what"

## Tech Stack

| Category | Approved | Prohibited |
|----------|----------|------------|
| Language | Python 3.11+ | Python 2.x |
| Framework | Django 4.2+ | Flask, FastAPI |
| Package Manager | Poetry | pip, requirements.txt |
| Linting | Ruff | Black, Flake8 |
| Testing | pytest | unittest alone |
| Frontend | React + Vite | Create React App |
| UI Library | shadcn/ui | MUI, Chakra |

## Validation Commands

Always run before completion:

```bash
# Lint check
./scripts/lint.sh

# Full test suite
./scripts/test-all.sh
```

## Context Files

Read before any development task:

1. `docs/technical/roadmap.md` - Task checklist and progress
2. `docs/technical/decisions.md` - IN/OUT of scope boundaries
3. `docs/contrib/code.md` - Implementation standards
4. `docs/contrib/review.md` - Quality checklist
5. `docs/contrib/testing.md` - Testing requirements

PRINCIPLES

    echo "" >> "$GEMINI_MD"
    echo "---" >> "$GEMINI_MD"
    echo "*Generated from .agent/ on $(date -Iseconds)*" >> "$GEMINI_MD"
}

# Main execution
main() {
    generate_gemini_md
}

main "$@"
