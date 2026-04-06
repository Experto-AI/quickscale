# Contributing to QuickScale

> **You are here**: [QuickScale](../../START_HERE.md) → [Contributing](../index.md) → **Contributing Guide** (Guide Map)
> **Related docs**: [Code Guide](code.md) | [Testing Guide](testing.md) | [Development Setup](../technical/development.md) | [Start Here](../../START_HERE.md)

Welcome! This guide maps the contribution documentation and authority boundaries for contributors and AI assistants.

## Authority Model

The files in `docs/contrib/` define project-specific contribution guidance without prescribing a required execution flow. Different human and agent workflows may sequence planning, implementation, review, testing, and debugging differently.

`docs/contrib/shared/` is the authoritative source for project-specific implementation rules.

- Shared documents define normative rules
- Stage guides in this folder apply those rules in a specific situation
- Stage guides do not define a competing source of truth for engineering rules
- If a stage guide conflicts with a shared document, the shared document wins

## Shared Rule Sources

Start with the authoritative rule source for the topic you are touching:

| Topic | Authoritative source |
|---|---|
| Core design principles | [Code Principles](shared/code_principles.md) |
| Code style and local conventions | [Code Style Standards](shared/code_style_standards.md) |
| Architecture and stack boundaries | [Architecture Guidelines](shared/architecture_guidelines.md) |
| Testing standards | [Testing Standards](shared/testing_standards.md) |
| Scope discipline | [Task Focus Guidelines](shared/task_focus_guidelines.md) |
| Documentation conventions | [Documentation Standards](shared/documentation_standards.md) |
| Debugging and bug-fix discipline | [Debugging Standards](shared/debugging_standards.md) |
| Shared authority overview | [Shared Rule Sources](shared/README.md) |

## Application Guides

Use the stage guide that matches the work in front of you. These guides are workflow-agnostic application references, not required workflow steps.

### 📋 [PLAN](plan.md)
Use when clarifying scope, identifying affected areas, or preparing an implementation approach.

### 💻 [CODE](code.md)
Use when implementing or modifying code within an approved task boundary.

### ✅ [REVIEW](review.md)
Use when self-reviewing or reviewing plans, code changes, tests, and documentation.

### 🧪 [TESTING](testing.md)
Use when selecting test locations, writing tests, or running repo-specific test commands.

### 🐛 [DEBUG](debug.md)
Use when diagnosing failures, isolating regressions, and fixing verified root causes.

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

1. Read [README.md](../../README.md) and [Technical Decisions](../technical/decisions.md) to understand the project and scope
2. Open the relevant shared rule sources for the change you are making
3. Use the stage guide that matches your current task as an application checklist
4. Let your execution workflow decide ordering; these docs do not prescribe a required sequence

---

## Questions or Issues?

- **Technical questions**: Check [Technical Decisions](../technical/decisions.md)
- **Architecture questions**: See [Architecture Guidelines](shared/architecture_guidelines.md)
- **Testing questions**: Review [Testing Standards](shared/testing_standards.md)
- **Bugs or issues**: Follow [DEBUG](debug.md) guide
