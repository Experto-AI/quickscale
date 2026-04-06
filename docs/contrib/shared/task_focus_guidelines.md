# Task Focus Guidelines

This file contains the authoritative scope-discipline rules for QuickScale.

## Task Boundary Management

- Understand the exact boundaries of the requested change before editing
- Work within those boundaries without drifting into adjacent cleanup or redesign
- Preserve existing interfaces unless the request explicitly includes an interface change

## Change Discipline

- Make one logical change at a time
- Keep changes small enough to reason about and review safely
- Do not bundle unrelated refactors, style-only rewrites, or speculative improvements into a scoped task

## Scope Control Rules

- Define what is in scope and what is out of scope before broadening the edit set
- Limit changes to the files, symbols, and behaviors required for the requested outcome
- Surface follow-on work explicitly instead of silently expanding the task

## Validation and Handoff Discipline

- Verify that completed changes map directly to the requested outcome
- Call out validation gaps, documentation gaps, and unresolved dependencies explicitly
- Treat unrequested "nice to have" improvements as out of scope unless they are separately approved

## Compatibility and Local Consistency

- Maintain the existing architecture and public contracts unless change is explicitly authorized
- Match established local style rather than reformatting unrelated code
- Avoid introducing new patterns or abstractions unless the task and the surrounding architecture justify them
