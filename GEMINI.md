# QuickScale Development Agent

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Context

Read these files to understand the project:

- @.agent/contexts/authoritative-files.md
- @.agent/contexts/project-conventions.md

## Workflows

Run a workflow with `/workflow-name` or say *"Follow the workflow-name workflow"*.

| Command | Description | Source |
|---------|-------------|--------|
| `/create-release` | Finalize a release with commit message, roadmap cleanup, and documentation | `@.agent/workflows/create-release.md` |
| `/implement-task` | Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages | `@.agent/workflows/implement-task.md` |
| `/plan-sprint` | Plan the next sprint by analyzing roadmap and prioritizing tasks | `@.agent/workflows/plan-sprint.md` |
| `/review-code` | Review staged code changes for quality, scope compliance, and completeness | `@.agent/workflows/review-code.md` |

## Skills

Skills provide reusable coding guidance. Load on demand via `@path` references.

| Skill | Description | Import |
|-------|-------------|--------|
| `architecture-guidelines` | Tech stack compliance, layer boundaries, patterns | `@.agent/skills/architecture-guidelines/SKILL.md` |
| `code-principles` | SOLID, DRY, KISS principles for code quality | `@.agent/skills/code-principles/SKILL.md` |
| `development-workflow` | Feature development and bug fix workflow stages | `@.agent/skills/development-workflow/SKILL.md` |
| `documentation-standards` | Docstring format, comments, and documentation quality | `@.agent/skills/documentation-standards/SKILL.md` |
| `git-operations` | Git commands, staging, commits, and diff operations | `@.agent/skills/git-operations/SKILL.md` |
| `roadmap-navigation` | Task detection, checklist parsing, and roadmap operations | `@.agent/skills/roadmap-navigation/SKILL.md` |
| `task-focus` | Scope discipline and boundary enforcement | `@.agent/skills/task-focus/SKILL.md` |
| `testing-standards` | Test isolation, mocking, coverage standards | `@.agent/skills/testing-standards/SKILL.md` |

## Agents

Agents are comprehensive role definitions for complex multi-step tasks.

| Agent | Description | Workflows | Import |
|-------|-------------|-----------|--------|
| `code-reviewer` | Comprehensive code quality review and validation | /review-code | `@.agent/agents/code-reviewer.md` |
| `release-manager` | Release finalization, commit messages, roadmap cleanup | /create-release | `@.agent/agents/release-manager.md` |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation | /plan-sprint | `@.agent/agents/roadmap-planner.md` |
| `task-implementer` | Implements roadmap tasks with staged workflow | /implement-task | `@.agent/agents/task-implementer.md` |

## Subagents

Subagents handle focused sub-tasks delegated by agents.

| Subagent | Description | Import |
|----------|-------------|--------|
| `architecture-checker` | Validates tech stack compliance and architectural boundaries | `@.agent/subagents/architecture-checker.md` |
| `code-quality-reviewer` | Reviews SOLID, DRY, KISS compliance and code quality | `@.agent/subagents/code-quality-reviewer.md` |
| `doc-reviewer` | Validates documentation quality and completeness | `@.agent/subagents/doc-reviewer.md` |
| `report-generator` | Generates comprehensive review reports | `@.agent/subagents/report-generator.md` |
| `scope-validator` | Validates changes against task scope, detects scope creep | `@.agent/subagents/scope-validator.md` |
| `test-reviewer` | Validates test quality, isolation, and coverage | `@.agent/subagents/test-reviewer.md` |

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

---
*Generated from .agent/ on 2026-02-06T20:21:56+01:00*
