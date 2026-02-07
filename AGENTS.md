# QuickScale Development Agent

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Project Overview

QuickScale is a Django project generator that creates production-ready SaaS applications.
This file provides instructions for AI coding agents working on this codebase.
## Context Files

Read these before any development task:

1. `docs/technical/roadmap.md` - Current tasks and progress
2. `docs/technical/decisions.md` - IN/OUT of scope boundaries
3. `docs/contrib/code.md` - Implementation standards
4. `docs/contrib/review.md` - Quality checklist
5. `docs/contrib/testing.md` - Testing requirements

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
- When in doubt, ask - do not assume
## Agents

Available agent definitions for complex workflows:

| Agent | Description | Workflow |
|-------|-------------|----------|
| `code-reviewer` | Comprehensive code quality review and validation | review-code |
| `release-manager` | Release finalization, commit messages, roadmap cleanup | create-release |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation | plan-sprint |
| `task-implementer` | Implements roadmap tasks with staged workflow | implement-task |

## Subagents

| Subagent | Description | Parent Agents |
|----------|-------------|---------------|
| `architecture-checker` | Validates tech stack compliance and architectural boundaries | code-reviewer |
| `code-quality-reviewer` | Reviews SOLID, DRY, KISS compliance and code quality | code-reviewer |
| `doc-reviewer` | Validates documentation quality and completeness | code-reviewer |
| `report-generator` | Generates comprehensive review reports | code-reviewer |
| `scope-validator` | Validates changes against task scope, detects scope creep | task-implementer, code-reviewer |
| `test-reviewer` | Validates test quality, isolation, and coverage | code-reviewer |

## Skills

Reusable guidance modules in `.agent/skills/`:

| Skill | Description | Path |
|-------|-------------|------|
| `architecture-guidelines` | Tech stack compliance, layer boundaries, patterns | `.agent/skills/architecture-guidelines/SKILL.md` |
| `code-principles` | SOLID, DRY, KISS principles for code quality | `.agent/skills/code-principles/SKILL.md` |
| `development-workflow` | Feature development and bug fix workflow stages | `.agent/skills/development-workflow/SKILL.md` |
| `documentation-standards` | Docstring format, comments, and documentation quality | `.agent/skills/documentation-standards/SKILL.md` |
| `git-operations` | Git commands, staging, commits, and diff operations | `.agent/skills/git-operations/SKILL.md` |
| `roadmap-navigation` | Task detection, checklist parsing, and roadmap operations | `.agent/skills/roadmap-navigation/SKILL.md` |
| `task-focus` | Scope discipline and boundary enforcement | `.agent/skills/task-focus/SKILL.md` |
| `testing-standards` | Test isolation, mocking, coverage standards | `.agent/skills/testing-standards/SKILL.md` |

## Workflows

Step-by-step execution plans:

### create-release

Finalize a release with commit message, roadmap cleanup, and documentation

Details: `.agent/workflows/create-release.md`

- 1. Step 1: Verify Completion
- 2. Step 2: Extract Completed Tasks
- 3. Step 3: Generate Commit Message
- 4. Step 4: Create Release Notes
- 5. Step 5: Clean Roadmap
- 6. Step 6: Final Review
- 7. Step 7: Commit (Human Action)

### implement-task

Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages

Details: `.agent/workflows/implement-task.md`

- 1. Stage 1: PLAN
- 2. Stage 2: CODE
- 3. Stage 3: REVIEW
- 4. Stage 4: TEST
- 5. Stage 5: COMPLETE

### plan-sprint

Plan the next sprint by analyzing roadmap and prioritizing tasks

Details: `.agent/workflows/plan-sprint.md`

- 1. Step 1: Analyze Current State
- 2. Step 2: Identify Release Scope
- 3. Step 3: Prioritize Tasks
- 4. Step 4: Validate Task Scopes
- 5. Step 5: Create Sprint Plan
- 6. Step 6: Update Roadmap (Optional)

### review-code

Review staged code changes for quality, scope compliance, and completeness

Details: `.agent/workflows/review-code.md`

- 1. Step 1: Gather Context
- 2. Step 2: Scope Compliance Check
- 3. Step 3: Architecture Review
- 4. Step 4: Code Quality Review
- 5. Step 5: Testing Review
- 6. Step 6: Documentation Review
- 7. Step 7: Validation
- 8. Step 8: Generate Report

## Validation

```bash
./scripts/lint_agentic_flow.sh
./scripts/test_agentic_flow.sh
```

## Contract Notes

Codex supports rich markdown instructions. Input/output/success contracts are retained in source agent files and surfaced through workflow descriptions.

---
*Generated from .agent/ on 2026-02-07T12:58:06+01:00*
