# Authoritative Files Index

> This document lists the authoritative files that agents should read before any task.

## Reading Order

Read these files in order before starting development work:

### Tier 1: Foundation (Always Read First)

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `docs/technical/decisions.md` | **Authoritative** - Technical rules, what's IN/OUT of scope |
| 2 | `docs/technical/roadmap.md` | Task checklist, current sprint, progress tracking |
| 3 | `docs/technical/scaffolding.md` | Directory structures, file layouts |
| 4 | `README.md` | Project overview, quick start |

### Tier 2: Task-Specific (Read as Needed)

| File | When to Read |
|------|--------------|
| `docs/contrib/plan.md` | Before starting a task (PLAN stage) |
| `docs/contrib/code.md` | During implementation (CODE stage) |
| `docs/contrib/review.md` | After code complete (REVIEW stage) |
| `docs/contrib/testing.md` | When writing tests (TEST stage) |
| `docs/contrib/debug.md` | When troubleshooting issues |

### Tier 3: Reference (Deep Dives)

| File | Purpose |
|------|---------|
| `docs/contrib/shared/code_principles.md` | SOLID, DRY, KISS detailed examples |
| `docs/contrib/shared/testing_standards.md` | Test patterns, isolation requirements |
| `docs/contrib/shared/architecture_guidelines.md` | Tech stack, layer boundaries |
| `docs/contrib/shared/documentation_standards.md` | Docstring format, comments |
| `docs/contrib/shared/task_focus_guidelines.md` | Scope discipline rules |

## Conflict Resolution

When documents conflict, authority order is:

1. **`decisions.md`** — Always wins
2. **`roadmap.md`** — Task-specific requirements
3. **`contrib/*.md`** — Stage guidelines
4. **Other docs** — Supplementary information

## File Purpose Summary

| File | Single-Line Purpose |
|------|---------------------|
| `decisions.md` | What we MUST and MUST NOT do |
| `roadmap.md` | What we ARE doing now |
| `scaffolding.md` | Where code goes |
| `code.md` | How to write code |
| `review.md` | How to validate code |
| `testing.md` | How to test code |
