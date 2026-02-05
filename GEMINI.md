# QuickScale Development Agent

> **Auto-generated from `.agent/`** - Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Overview

This file configures Gemini CLI for QuickScale development with skills and workflows.

## Workflows

To run a workflow, say "Follow the [workflow-name] workflow".

### create-release

**Description**: Finalize a release with commit message, roadmap cleanup, and documentation

**Trigger**: "Follow the create-release workflow"

**Details**: See `.agent/workflows/create-release.md`

### implement-task

**Description**: Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages

**Trigger**: "Follow the implement-task workflow"

**Details**: See `.agent/workflows/implement-task.md`

### plan-sprint

**Description**: Plan the next sprint by analyzing roadmap and prioritizing tasks

**Trigger**: "Follow the plan-sprint workflow"

**Details**: See `.agent/workflows/plan-sprint.md`

### review-code

**Description**: Review staged code changes for quality, scope compliance, and completeness

**Trigger**: "Follow the review-code workflow"

**Details**: See `.agent/workflows/review-code.md`

## Skills

Skills provide reusable guidance. To use a skill, reference its SKILL.md file.

| Skill | Path | Description |
|-------|------|-------------|
| architecture-guidelines | `.agent/skills/architecture-guidelines/SKILL.md` | Tech stack compliance, layer boundaries, patterns |
| code-principles | `.agent/skills/code-principles/SKILL.md` | SOLID, DRY, KISS principles for code quality |
| development-workflow | `.agent/skills/development-workflow/SKILL.md` | Feature development and bug fix workflow stages |
| documentation-standards | `.agent/skills/documentation-standards/SKILL.md` | Docstring format, comments, and documentation quality |
| git-operations | `.agent/skills/git-operations/SKILL.md` | Git commands, staging, commits, and diff operations |
| roadmap-navigation | `.agent/skills/roadmap-navigation/SKILL.md` | Task detection, checklist parsing, and roadmap operations |
| task-focus | `.agent/skills/task-focus/SKILL.md` | Scope discipline and boundary enforcement |
| testing-standards | `.agent/skills/testing-standards/SKILL.md` | Test isolation, mocking, coverage standards |

## Agents

Agents are comprehensive guides for complex tasks.

| Agent | Path | Description |
|-------|------|-------------|
| code-reviewer | `.agent/agents/code-reviewer.md` | Comprehensive code quality review and validation |
| release-manager | `.agent/agents/release-manager.md` | Release finalization, commit messages, roadmap cleanup |
| roadmap-planner | `.agent/agents/roadmap-planner.md` | Sprint planning, release selection, roadmap validation |
| task-implementer | `.agent/agents/task-implementer.md` | Implements roadmap tasks with staged workflow |

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
- Coverage minimum 70%
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


---
*Generated from .agent/ on 2026-02-05T20:25:28+01:00*
