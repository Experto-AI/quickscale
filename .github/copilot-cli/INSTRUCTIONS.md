# QuickScale Copilot CLI Instructions

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

Use these instructions and workflow prompts with GitHub Copilot CLI.

## Workflows

| Workflow | Description |
|----------|-------------|
| `create-release` | Finalize a release with commit message, roadmap cleanup, and documentation |
| `implement-task` | Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages |
| `plan-sprint` | Plan the next sprint by analyzing roadmap and prioritizing tasks |
| `review-code` | Review staged code changes for quality, scope compliance, and completeness |

## Agents

| Agent | Description | Workflows |
|-------|-------------|-----------|
| `code-reviewer` | Comprehensive code quality review and validation | review-code |
| `release-manager` | Release finalization, commit messages, roadmap cleanup | create-release |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation | plan-sprint |
| `task-implementer` | Implements roadmap tasks with staged workflow | implement-task |

## Skills

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
./scripts/lint.sh
./scripts/test_unit.sh
```

## Contract Notes

Copilot CLI consumes markdown instructions and prompt files. Full agent contracts are embedded in generated agent markdown.

---
*Generated from .agent/ on 2026-02-07T09:49:29+01:00*
