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


## Skills

Available skills for code quality and workflow guidance:

| Skill | Description |
|-------|-------------|
| `architecture-guidelines` | Tech stack compliance, layer boundaries, patterns |
| `code-principles` | SOLID, DRY, KISS principles for code quality |
| `development-workflow` | Feature development and bug fix workflow stages |
| `documentation-standards` | Docstring format, comments, and documentation quality |
| `git-operations` | Git commands, staging, commits, and diff operations |
| `roadmap-navigation` | Task detection, checklist parsing, and roadmap operations |
| `task-focus` | Scope discipline and boundary enforcement |
| `testing-standards` | Test isolation, mocking, coverage standards |

## Agents

| Agent | Description |
|-------|-------------|
| `code-reviewer` | Comprehensive code quality review and validation |
| `release-manager` | Release finalization, commit messages, roadmap cleanup |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation |
| `task-implementer` | Implements roadmap tasks with staged workflow |

## Workflows

### create-release

Finalize a release with commit message, roadmap cleanup, and documentation

See: `.agent/workflows/create-release.md`

### implement-task

Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages

See: `.agent/workflows/implement-task.md`

### plan-sprint

Plan the next sprint by analyzing roadmap and prioritizing tasks

See: `.agent/workflows/plan-sprint.md`

### review-code

Review staged code changes for quality, scope compliance, and completeness

See: `.agent/workflows/review-code.md`

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


---
*Generated from .agent/ on 2026-02-05T20:25:28+01:00*
