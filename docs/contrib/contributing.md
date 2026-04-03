# Contributing to QuickScale

> **You are here**: [QuickScale](../../START_HERE.md) → [Contributing](../index.md) → **Contributing Guide** (Workflow Overview)
> **Related docs**: [Code Guide](code.md) | [Testing Guide](testing.md) | [Development Setup](../technical/development.md) | [Start Here](../../START_HERE.md)

Welcome! This guide will help you understand the development workflow and where to find the right documentation for each stage of contribution.

## Development Workflow

QuickScale follows a structured development workflow with focused, stage-specific guides. Follow these stages in order for any code change:

### 1. 📋 [PLAN](plan.md) - Planning & Task Review
**Use when:** Planning a roadmap from scratch OR reviewing/adjusting task specifications before implementation.

**Key activities:**
- Understand project context (read decisions.md, scaffolding.md, README.md)
- Break down features into clear, testable tasks
- Define task boundaries and deliverables
- Pre-task review (validate scope, check for conflicts)
- Plan for architecture compliance

**Referenced by prompts:**
- `roadmap-plan-review-and-update.prompt.md` (primary)
- `roadmap-task-implementation.prompt.md` (pre-implementation review)

---

### 2. 💻 [CODE](code.md) - Implementation
**Use when:** Writing implementation code following approved specifications.

**Key activities:**
- Apply SOLID principles during implementation
- Follow DRY, KISS, Explicit Failure patterns
- Maintain code structure and organization
- Use type hints and proper documentation
- **Strict scope enforcement** (implement ONLY what's in the task checklist)

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (primary)

---

### 3. ✅ [REVIEW](review.md) - Quality Control
**Use when:** Reviewing generated code AFTER implementation, BEFORE writing tests.

**Key activities:**
- Verify technical stack compliance
- Verify architectural pattern adherence
- Verify SOLID/DRY/KISS adherence
- Verify scope compliance (no feature creep)
- Verify documentation completeness
- Pre-commit quality checklist

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (self-review after coding)
- `release-commit-message-and-roadmap-cleaning.prompt.md` (final review)

---

### 4. 🧪 [TESTING](testing.md) - Test Generation
**Use when:** Generating tests AFTER implementation is complete AND code-reviewed.

**Key activities:**
- Implementation-first testing approach
- Choose correct test category (unit/integration/e2e)
- Structure tests by functionality
- Behavior-focused testing (test contracts, not internals)
- Proper mock usage (NO global mocking)
- Arrange-Act-Assert pattern

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (after code and review stages)

---

### 5. 🐛 [DEBUG](debug.md) - Debugging & Root Cause Analysis
**Use when:** Debugging issues, fixing failing tests, or addressing bugs.

**Key activities:**
- Root cause analysis (never mask symptoms)
- DMAIC process (Define, Measure, Analyze, Improve, Control)
- Debug failing tests (determine if test or code is wrong)
- Minimal fixes addressing root cause
- Add regression tests after fixes

**Referenced by prompts:**
- Can be invoked manually when debugging is needed
- Referenced during test failure analysis

---

## Shared Principles

These foundational documents are referenced by all stage files:

### [Code Principles](shared/code_principles.md)
**SOLID, DRY, KISS, Explicit Failure** - Core coding principles with examples for each stage.

### [Architecture Guidelines](shared/architecture_guidelines.md)
**Tech stack, layer boundaries, package structure** - System architecture and technical decisions.

### [Testing Standards](shared/testing_standards.md)
**Complete testing reference** - Comprehensive testing standards and patterns.

### [Task Focus Guidelines](shared/task_focus_guidelines.md)
**Scope discipline** - Preventing scope creep and maintaining task boundaries.

### [Documentation Standards](shared/documentation_standards.md)
**Docstring format, comments, README structure** - Documentation conventions.

---

## Project Context Documentation

Before contributing, familiarize yourself with these key project documents:

- **[README.md](../../README.md)** - Project overview and getting started
- **[Technical Roadmap](../technical/roadmap.md)** - Current development roadmap and task tracking
- **[Technical Decisions](../technical/decisions.md)** - What's IN vs OUT of scope
- **[Scaffolding Guide](../technical/scaffolding.md)** - Directory layout and project structure
- **[Release Summary Template](../technical/release_summary_template.md)** - Standard format for public release summaries

---

## Release Documentation Policy

When a QuickScale version is published, keep the release record single-source and public:

- `CHANGELOG.md` is the canonical all-version history index.
- `docs/releases/release-<version>.md` is the official release note linked from the GitHub tag and the release PR.
- `docs/technical/release_summary_template.md` is the required template for those release notes.
- `docs/technical/roadmap.md` tracks active or unreleased release-closeout work until the tagged release is cut.

This keeps release history easy to scan and avoids parallel release documents drifting out of sync.

### Required Release Documentation Conventions

- **Changelog entry**: Add or update the version entry in `CHANGELOG.md` for every completed release record.
- **Release-note filename**: `docs/releases/release-<version>.md` (for example, `release-v0.75.0.md`) for every tagged public release.
- **Release-note template**: Use `docs/technical/release_summary_template.md`.
- **Publication rule**: Only create a file in `docs/releases/` when it is the release note that will be linked from the GitHub tag and release PR.
- **Minimum content**: release focus, shipped outcomes, breaking changes or migration notes when relevant, validation summary, and deferred follow-up.
- Link back to the roadmap and to `decisions.md` where appropriate.
- Keep maintainer-only review detail in the release PR or active roadmap section rather than in a second release document.
- For internal-only or not-yet-tagged work, keep status in `docs/technical/roadmap.md` until the public release is cut.

### Release Documentation Process

Follow these steps after completing a release:

1. Update `CHANGELOG.md` with the release version, date, and concise shipped outcome.
2. When cutting the tagged release, add `docs/releases/release-<version>.md` using the release summary template.
3. Link the GitHub tag and the release PR to that `docs/releases/` file.
4. Replace the completed roadmap section with a concise pointer once the changelog entry and official release note are in place.
5. Update indexes and other documentation links if necessary.

For unreleased or internal-only versions, keep closeout notes in the roadmap until the tagged public release exists.

This policy keeps `CHANGELOG.md` as the history index, makes each published `docs/releases/` file the single public artifact, and avoids dead archive guidance.

---

## GitHub Prompts

QuickScale uses structured prompts for automated development workflows:

### [roadmap-plan-review-and-update.prompt.md](../../.github/prompts/roadmap-plan-review-and-update.prompt.md)
**Roadmap planning and validation** - Choose next release, validate implementation plan, reconcile with decisions.md.

### [roadmap-task-implementation.prompt.md](../../.github/prompts/roadmap-task-implementation.prompt.md)
**Complete task implementation workflow** - Covers PLAN → CODE → REVIEW → TESTING stages for implementing roadmap tasks.

### [roadmap-task-review.prompt.md](../../.github/prompts/roadmap-task-review.prompt.md)
**Post-implementation quality review** - Comprehensive code review of completed implementation. Takes release version as parameter (e.g., `0.68.0`) and can support final release review before the public release note and roadmap cleanup.

### [release-commit-message-and-roadmap-cleaning.prompt.md](../../.github/prompts/release-commit-message-and-roadmap-cleaning.prompt.md)
**Release finalization** - Generate release commit message, clean up roadmap after release completion.

---

## Quick Start Guide

### For New Contributors
1. Read [README.md](../../README.md) to understand the project
2. Review [Technical Decisions](../technical/decisions.md) to understand scope
3. Check [Technical Roadmap](../technical/roadmap.md) for available tasks
4. Follow the workflow stages above when implementing

### For Code Changes
```
PLAN → CODE → REVIEW → TESTING → (DEBUG if needed)
```

Each stage has a focused guide that tells you exactly what to do and what rules to follow.

---

## Why This Structure?

**AI assistants don't follow big files with many rules.** This structure provides:

✅ **Focused, digestible guides** - Each stage file is ~200-400 lines maximum
✅ **Clear workflow enforcement** - Stages must be followed in order
✅ **Single source of truth** - Shared principles referenced, not duplicated
✅ **Flexible prompts** - Each prompt references only the stages it needs
✅ **Scalable** - Easy to add new stages or prompts without bloating existing files

---

## Questions or Issues?

- **Technical questions**: Check [Technical Decisions](../technical/decisions.md)
- **Architecture questions**: See [Architecture Guidelines](shared/architecture_guidelines.md)
- **Testing questions**: Review [Testing Standards](shared/testing_standards.md)
- **Bugs or issues**: Follow [DEBUG](debug.md) guide

Happy contributing! 🚀
