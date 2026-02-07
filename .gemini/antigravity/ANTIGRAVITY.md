# QuickScale Gemini Antigravity Profile

> **Auto-generated from `.agent/`** — Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

This profile provides workflow and agent mappings tailored for Gemini Antigravity.

## Workflows

| Workflow | Description | Source |
|----------|-------------|--------|
| `create-release` | Finalize a release with commit message, roadmap cleanup, and documentation | `.agent/workflows/create-release.md` |
| `implement-task` | Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages | `.agent/workflows/implement-task.md` |
| `plan-sprint` | Plan the next sprint by analyzing roadmap and prioritizing tasks | `.agent/workflows/plan-sprint.md` |
| `review-code` | Review staged code changes for quality, scope compliance, and completeness | `.agent/workflows/review-code.md` |

## Agents

| Agent | Description | Skills |
|-------|-------------|--------|
| `code-reviewer` | Comprehensive code quality review and validation | architecture-guidelines, code-principles, documentation-standards, git-operations, task-focus, testing-standards |
| `release-manager` | Release finalization, commit messages, roadmap cleanup | git-operations, roadmap-navigation |
| `roadmap-planner` | Sprint planning, release selection, roadmap validation | roadmap-navigation, task-focus |
| `task-implementer` | Implements roadmap tasks with staged workflow | architecture-guidelines, code-principles, development-workflow, documentation-standards, git-operations, roadmap-navigation, task-focus, testing-standards |

## Subagents

| Subagent | Description | Parents |
|----------|-------------|---------|
| `architecture-checker` | Validates tech stack compliance and architectural boundaries | code-reviewer |
| `code-quality-reviewer` | Reviews SOLID, DRY, KISS compliance and code quality | code-reviewer |
| `doc-reviewer` | Validates documentation quality and completeness | code-reviewer |
| `report-generator` | Generates comprehensive review reports | code-reviewer |
| `scope-validator` | Validates changes against task scope, detects scope creep | task-implementer, code-reviewer |
| `test-reviewer` | Validates test quality, isolation, and coverage | code-reviewer |

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

Gemini Antigravity mapping is rendered as markdown metadata and command stubs.

---
*Generated from .agent/ on 2026-02-07T09:49:28+01:00*
