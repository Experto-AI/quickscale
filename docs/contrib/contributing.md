# Contributing to QuickScale

> **You are here**: [QuickScale](../../START_HERE.md) → [Contributing](../index.md) → **Contributing Guide** (Guide Map)
> **Related docs**: [Code Guide](code.md) | [Testing Guide](testing.md) | [Development Setup](../technical/development.md) | [Start Here](../../START_HERE.md)

Welcome! This guide maps the contribution documentation and authority boundaries for contributors and AI assistants.

## Contribution Guides

The files in `docs/contrib/` define project-specific implementation rules and reference material. They do not prescribe a required execution flow. Different human and agent workflows may sequence planning, implementation, review, testing, and debugging differently.

When guidance overlaps, the shared documents in `docs/contrib/shared/` are authoritative. The stage guides below show how to apply those shared rules to a specific kind of work.

### 📋 [PLAN](plan.md) - Planning & Task Review
**Use when:** Clarifying scope, breaking down work, or reviewing task specifications before or during implementation.

**Key activities:**
- Understand project context (read decisions.md, scaffolding.md, README.md)
- Break down features into clear, testable tasks
- Define task boundaries and deliverables
- Pre-task review (validate scope, check for conflicts)
- Plan for architecture compliance

---

### 💻 [CODE](code.md) - Implementation
**Use when:** Writing implementation code following approved specifications.

**Key activities:**
- Apply SOLID principles during implementation
- Follow DRY, KISS, Explicit Failure patterns
- Maintain code structure and organization
- Use type hints and proper documentation
- **Strict scope enforcement** (implement ONLY what's in the task checklist)

---

### ✅ [REVIEW](review.md) - Quality Control
**Use when:** Reviewing planned or implemented changes for correctness, architecture, scope, and documentation quality.

**Key activities:**
- Verify technical stack compliance
- Verify architectural pattern adherence
- Verify SOLID/DRY/KISS adherence
- Verify scope compliance (no feature creep)
- Verify documentation completeness
- Pre-commit quality checklist

---

### 🧪 [TESTING](testing.md) - Test Generation
**Use when:** Selecting, writing, or organizing tests for implemented behavior, and when choosing the correct test category for the repo.

**Key activities:**
- Implementation-first testing approach
- Choose correct test category (unit/integration/e2e)
- Structure tests by functionality
- Behavior-focused testing (test contracts, not internals)
- Proper mock usage (NO global mocking)
- Arrange-Act-Assert pattern

---

### 🐛 [DEBUG](debug.md) - Debugging & Root Cause Analysis
**Use when:** Diagnosing failing tests, regressions, or bugs and fixing root causes.

**Key activities:**
- Root cause analysis (never mask symptoms)
- DMAIC process (Define, Measure, Analyze, Improve, Control)
- Debug failing tests (determine if test or code is wrong)
- Minimal fixes addressing root cause
- Add regression tests after fixes

---

## Shared Principles

These shared documents are the authoritative rule sources for project-specific engineering practices. When a stage guide overlaps with one of these documents, follow the shared document.

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

## Quick Start Guide

### For New Contributors
1. Read [README.md](../../README.md) to understand the project
2. Review [Technical Decisions](../technical/decisions.md) to understand scope
3. Check [Technical Roadmap](../technical/roadmap.md) for available tasks
4. Open the shared rules and stage guides relevant to the task

### For Code Changes
Use the guides that match the work in front of you:

- Use the shared documents as the project rule source of truth
- Use PLAN, CODE, REVIEW, TESTING, and DEBUG as task-specific reference guides
- Let your execution workflow decide the order in which those guides are applied

---

## Questions or Issues?

- **Technical questions**: Check [Technical Decisions](../technical/decisions.md)
- **Architecture questions**: See [Architecture Guidelines](shared/architecture_guidelines.md)
- **Testing questions**: Review [Testing Standards](shared/testing_standards.md)
- **Bugs or issues**: Follow [DEBUG](debug.md) guide
