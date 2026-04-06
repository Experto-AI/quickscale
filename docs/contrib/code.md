# CODE - Implementation Guide

This is an implementation application guide. It applies the shared rule sources to day-to-day code changes without acting as a separate rules authority.

Shared documents in [shared/](shared/) remain authoritative when guidance overlaps.

## Use This Guide When

- writing new implementation code
- modifying existing behavior inside an approved task boundary
- checking whether a proposed change still fits the local architecture and coding style

## Authoritative Sources for Implementation

Use these rule sources while implementing:

- [Code Principles](shared/code_principles.md)
- [Code Style Standards](shared/code_style_standards.md)
- [Architecture Guidelines](shared/architecture_guidelines.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Documentation Standards](shared/documentation_standards.md)
- [Testing Standards](shared/testing_standards.md)

## Implementation Checklist

During implementation, confirm that you are:

- keeping changes inside the explicit task boundary
- applying the simplest design that satisfies the request
- reusing existing patterns before introducing new abstractions
- placing code in the correct architectural layer and preserving interfaces unless change is required
- handling invalid inputs, edge cases, and failures explicitly
- following the shared style rules for naming, typing, imports, formatting, logging, and local consistency
- documenting rationale where needed without duplicating what the code already says
- updating tests and documentation when the change requires them

## Project-Specific Reminders

- If a convention is not documented in the shared docs, match the surrounding package or module rather than inventing a new local style
- Keep unrelated cleanup, refactors, and style-only changes out of scoped implementation work
- Use [Quality Analysis Tools](../technical/quality_tools.md) when you need deeper static analysis beyond the immediate task

## Implementation Exit Criteria

Implementation is in good shape when:

- the change follows the relevant shared rules
- the scope is still tight and reviewable
- validation requirements are identified or already updated
- documentation impact is handled or explicitly noted

## Related Guidance

- [review.md](review.md) for quality checks
- [testing.md](testing.md) for repo-specific test selection and commands
- [debug.md](debug.md) for debugging application when validation fails
