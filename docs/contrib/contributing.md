# Contributing to QuickScale

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
- **[Release Template](../technical/release_template.md)** - Standard format for release documentation

---

## Release Documentation Policy

When a roadmap release or major roadmap item is implemented, maintainers MUST create a release document under `docs/releases/` and remove the corresponding detailed release section from the roadmap. This keeps the roadmap focused on upcoming work and preserves completed release artifacts as standalone documents.

### Required Release Documentation Conventions

- **Implementation filename**: `docs/releases/release-<version>-implementation.md` (e.g. `release-v0.52.0-implementation.md`)
- **Review filename**: `docs/releases/release-<version>-review.md` (e.g. `release-v0.52.0-review.md`)
- **Minimum content (implementation)**: release title, release date, summary of verifiable improvements, completed tasks checklist, validation commands, and a short "Next steps" list
- **Minimum content (review)**: comprehensive quality assessment, scope compliance check, code quality validation, testing review, approval status
- Link back to the roadmap and to `decisions.md` where appropriate

### Release Documentation Process

Follow these steps after completing a release:

1. Create `docs/releases/release-<version>-implementation.md` with implementation details, test results, and validation
2. (Optional) Create `docs/releases/release-<version>-review.md` with quality assessment and approval status
3. Commit the release documentation
4. Remove the completed release section from `docs/technical/roadmap.md` (or replace it with a one-line pointer to the release docs)
5. Update indexes/README links if necessary

This policy ensures completed work is archived in a discoverable place and the roadmap remains current and actionable.

---

## GitHub Prompts

QuickScale uses structured prompts for automated development workflows:

### [roadmap-task-implementation.prompt.md](../../.github/prompts/roadmap-task-implementation.prompt.md)
**Complete task implementation workflow** - Covers PLAN → CODE → REVIEW → TESTING stages for implementing roadmap tasks.

### [roadmap-plan-review-and-update.prompt.md](../../.github/prompts/roadmap-plan-review-and-update.prompt.md)
**Roadmap planning and validation** - Choose next release, validate implementation plan, reconcile with decisions.md.

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
