# QuickScale Development Agent

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Project Conventions

@.agent/contexts/project-conventions.md

## Authoritative Files

@.agent/contexts/authoritative-files.md

## Quick Commands

| Command | Description |
|---------|-------------|
| `/create-release` | Finalize a release with commit message, roadmap cleanup, and documentation |
| `/implement-task` | Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages |
| `/plan-sprint` | Plan the next sprint by analyzing roadmap and prioritizing tasks |
| `/review-code` | Review staged code changes for quality, scope compliance, and completeness |

## Skills

| Skill | Description | Source |
|-------|-------------|--------|
| `architecture-guidelines` | Tech stack compliance, layer boundaries, patterns | `.agent/skills/architecture-guidelines/SKILL.md` |
| `code-principles` | SOLID, DRY, KISS principles for code quality | `.agent/skills/code-principles/SKILL.md` |
| `development-workflow` | Feature development and bug fix workflow stages | `.agent/skills/development-workflow/SKILL.md` |
| `documentation-standards` | Docstring format, comments, and documentation quality | `.agent/skills/documentation-standards/SKILL.md` |
| `git-operations` | Git commands, staging, commits, and diff operations | `.agent/skills/git-operations/SKILL.md` |
| `roadmap-navigation` | Task detection, checklist parsing, and roadmap operations | `.agent/skills/roadmap-navigation/SKILL.md` |
| `task-focus` | Scope discipline and boundary enforcement | `.agent/skills/task-focus/SKILL.md` |
| `testing-standards` | Test isolation, mocking, coverage standards | `.agent/skills/testing-standards/SKILL.md` |

## Agents

| Agent | Description | Type |
|-------|-------------|------|
| `code-reviewer` | Comprehensive code quality review and validation | Agent |
| `release-manager` | Release finalization, commit messages, roadmap cleanup | Agent |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation | Agent |
| `task-implementer` | Implements roadmap tasks with staged workflow | Agent |
| `architecture-checker` | Validates tech stack compliance and architectural boundaries | Subagent |
| `code-quality-reviewer` | Reviews SOLID, DRY, KISS compliance and code quality | Subagent |
| `doc-reviewer` | Validates documentation quality and completeness | Subagent |
| `report-generator` | Generates comprehensive review reports | Subagent |
| `scope-validator` | Validates changes against task scope, detects scope creep | Subagent |
| `test-reviewer` | Validates test quality, isolation, and coverage | Subagent |

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
- No global mocking contamination (`sys.modules` modifications prohibited)
- Test isolation mandatory
- Coverage ≥ 90% overall, ≥ 80% per file

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
| Linting | Ruff |
| Testing | pytest |
| Frontend | React 18+ with TypeScript |
| Build | Vite |
| Components | shadcn/ui |
| CSS | Tailwind CSS |

---
*Generated from .agent/ on 2026-02-06T20:21:56+01:00*
