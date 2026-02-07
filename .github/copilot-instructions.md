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
- F-strings for formatting (no `.format()` or `%`)
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
## Available Prompts

Use these in Copilot Chat with `#` or via the prompt picker:

| Prompt | Description |
|--------|-------------|
| `create-release` | Finalize a release with commit message, roadmap cleanup, and documentation |
| `implement-task` | Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages |
| `plan-sprint` | Plan the next sprint by analyzing roadmap and prioritizing tasks |
| `review-code` | Review staged code changes for quality, scope compliance, and completeness |

## Available Agents

Use in Copilot Chat by selecting the agent:

| Agent | Description |
|------|-------------|
| `code-reviewer` | Comprehensive code quality review and validation |
| `release-manager` | Release finalization, commit messages, roadmap cleanup |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation |
| `task-implementer` | Implements roadmap tasks with staged workflow |
| `architecture-checker` | Validates tech stack compliance and architectural boundaries |
| `code-quality-reviewer` | Reviews SOLID, DRY, KISS compliance and code quality |
| `doc-reviewer` | Validates documentation quality and completeness |
| `report-generator` | Generates comprehensive review reports |
| `scope-validator` | Validates changes against task scope, detects scope creep |
| `test-reviewer` | Validates test quality, isolation, and coverage |

## Skills Reference

Detailed guidance available in `.agent/skills/`:

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
## Validation

```bash
./scripts/lint_agentic_flow.sh
./scripts/test_agentic_flow.sh
```

## Contract Notes

Copilot instructions support textual contracts. Structured contract fields are preserved in generated `.agent.md` files.

---
*Generated from .agent/ on 2026-02-07T12:58:06+01:00*
