# PLAN - Planning and Analysis Guide

Use the shared authority map first, then pull in technical docs such as
`decisions.md`, `scaffolding.md`, `README.md`, or `user_manual.md` only when
the task touches those surfaces. This guide keeps the planning-stage checklist
and questions.

## Planning Checklist

Before implementation starts, make sure the plan captures:

- the requested outcome and the explicit non-goals
- the most likely files, packages, or architectural layers involved
- architecture and stack constraints that limit the solution space
- where existing patterns or seams can be reused instead of introducing new abstractions
- explicit failure and validation expectations for the changed behavior
- the tests, checks, or commands that will show the change is correct
- documentation that may need updates
- any open questions that still block safe implementation

## Applied Planning Questions

Use these prompts while translating the shared rules into a concrete plan:

- Responsibility boundaries: which responsibilities belong together, and which should remain in separate layers or modules?
- Existing seams: which current service, adapter, helper, or managed wiring seam can be reused before introducing a new abstraction?
- Explicit failure: what invalid input, missing configuration, or unsupported state must fail clearly instead of silently?
- Testability: what evidence will prove the requested behavior and its meaningful edge cases?
- Scope control: what follow-on work must be noted rather than folded into the current task?
- Documentation impact: what contributor, operator, or user-facing docs must
	change if behavior or commands change?

## Planning Exit Criteria

Planning is ready when:

- scope boundaries are clear enough to avoid drift
- the proposed change fits the documented architecture
- validation is defined clearly enough to confirm the outcome
- the remaining unknowns are small enough to resolve during execution, or are
	explicitly surfaced first
