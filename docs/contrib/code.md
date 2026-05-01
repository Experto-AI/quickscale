# CODE - Implementation Guide

Use the shared authority map for normative rules. This guide keeps the
implementation-stage checklist, scope guardrails, and repo-specific reminders
that help you apply those rules locally.

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

## Scope Guardrails in Practice

- Do not change function signatures, public URLs, schema shape, or wiring unless the task explicitly requires it.
- Keep unrelated cleanup, formatting, and refactors out of scoped implementation work.
- When a genuinely needed adjacent change appears, note it explicitly instead of silently widening the edit.

## Project-Specific Reminders

- If a convention is not documented in the shared docs, match the surrounding package or module rather than inventing a new local style.
- Keep unrelated cleanup, refactors, and style-only changes out of scoped implementation work.
- Use [Quality Analysis Tools](../technical/quality_tools.md) when you need deeper static analysis beyond the immediate task.

## Implementation Exit Criteria

Implementation is in good shape when:

- the change follows the relevant shared rules
- the scope is still tight and reviewable
- validation requirements are identified or already updated
- documentation impact is handled or explicitly noted
