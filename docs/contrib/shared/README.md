# Shared Rule Sources

This directory owns workflow-agnostic contributor rules. When guidance here
overlaps with a stage guide in `docs/contrib/*.md`, the shared document wins.

## Shared vs. Stage Ownership

- Shared documents own normative principles, constraints, architecture
	boundaries, quality expectations, and references to repository SSOT docs.
- Stage guides own planning, implementation, review, testing, and debugging
	application guidance, plus repo commands, checklists, and evidence prompts.

## Authority Map

| Topic | Authoritative source | Typically applied from |
|---|---|---|
| Core design principles | [Code Principles](code_principles.md) | plan, code, review, debug |
| Code style and local conventions | [Code Style Standards](code_style_standards.md) | code, review |
| Architecture and stack boundaries | [Architecture Guidelines](architecture_guidelines.md) | plan, code, review, debug |
| Testing standards | [Testing Standards](testing_standards.md) | plan, testing, review, debug |
| Scope discipline | [Task Focus Guidelines](task_focus_guidelines.md) | plan, code, review, debug |
| Documentation conventions | [Documentation Standards](documentation_standards.md) | plan, code, review |
| Debugging and bug-fix discipline | [Debugging Standards](debugging_standards.md) | debug, review, testing |
