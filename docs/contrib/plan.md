# PLAN - Planning and Analysis Guide

This is a planning application guide. It helps you apply the project rule sources during planning without prescribing a required execution order.

Shared documents in [shared/](shared/) remain authoritative when guidance overlaps.

## Use This Guide When

- clarifying user intent and scope
- identifying likely files, modules, or architectural layers involved
- deciding how to keep implementation focused and testable
- preparing reviewable implementation steps or checkpoints

## Authoritative Sources for Planning

Use these rule sources while planning:

- [Code Principles](shared/code_principles.md)
- [Architecture Guidelines](shared/architecture_guidelines.md)
- [Testing Standards](shared/testing_standards.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Documentation Standards](shared/documentation_standards.md)
- [Technical Decisions](../technical/decisions.md)
- [Scaffolding Guide](../technical/scaffolding.md)
- [README.md](../../README.md)
- [User Manual](../technical/user_manual.md)

## Planning Checklist

Before implementation starts, make sure the plan captures:

- the requested outcome and the explicit non-goals
- the most likely files, packages, or architectural layers involved
- architecture and stack constraints that limit the solution space
- where existing patterns can be reused instead of introducing new abstractions
- explicit failure and validation expectations for the changed behavior
- the tests, checks, or commands that will show the change is correct
- documentation that may need updates
- any open questions that still block safe implementation

## Planning Exit Criteria

Planning is ready when:

- scope boundaries are clear enough to avoid drift
- the proposed change fits the documented architecture
- validation is defined clearly enough to confirm the outcome
- the remaining unknowns are small enough to resolve during execution, or are explicitly surfaced first

## Related Guidance

- [code.md](code.md) for implementation application
- [review.md](review.md) for quality checks
- [testing.md](testing.md) for repo-specific test selection and commands
- [debug.md](debug.md) for debugging application
