---
domain: root
merge_strategy: append
---

# Shared
- **Repository SSOT (wins on conflicts, always read)**:
    - `docs/technical/decisions.md` for scope rulings, approved stack, and tie-breakers.
    - `docs/technical/scaffolding.md` for repository, package, and generated-project structure.
- **Contrib authority model**:
    - `docs/contrib/shared/` owns workflow-agnostic QuickScale engineering rules.
    - `docs/contrib/*.md` stage guides apply those rules in a situation-specific way and do not prescribe a required workflow order.
    - If a stage guide conflicts with a `docs/contrib/shared/` rule source, the shared document wins.
- **Documentation precedence**:
    - Package README files are informational context only; repository SSOT documents win any conflict.
    - `README.md` and `START_HERE.md` provide orientation and current product surface but do not override `docs/technical/decisions.md`.
- **Important context (always read)**:
    - `README.md`
    - `START_HERE.md`
    - `docs/contrib/contributing.md`
- **Tooling**:
    - `Makefile` is the standard entrypoint for shared test and workflow commands.

# Adaptive
[include](#shared)


# Plan
[include](#shared)
- **Secondary applied guidance (always read)**:
    - `docs/contrib/plan.md` for planning checklists, prompts, and examples.

# Codebase Discovery
[include](#shared)


# External Research
[include](#shared)

# Implement
[include](#shared)
- **Secondary applied guidance (always read)**:
    - `docs/contrib/code.md` for implementation checklists, examples, and repo-specific reminders.

# Quality Gate
[include](#shared)
- **Secondary applied guidance (always read)**:
    - `docs/contrib/testing.md` for test placement, fixtures, and commands.
    - `docs/contrib/debug.md` for root-cause-first failure diagnosis and debug loops.

# Change Review
[include](#shared)
- **Secondary applied guidance (always read)**:
    - `docs/contrib/review.md` for review checklists and evidence prompts.
