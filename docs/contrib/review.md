# REVIEW - Quality Control Guide

This is a review application guide. It applies the shared rule sources during
self-review and peer review without becoming a second source of engineering
policy.

Shared documents in [shared/](shared/) remain authoritative when guidance
overlaps. This guide owns review checklists and review-stage evidence prompts.

## Use This Guide When

- reviewing a plan before implementation starts
- self-reviewing code, tests, or documentation before handoff
- reviewing bug fixes for scope, correctness, and regression safety

## Authoritative Sources for Review

Use these rule sources while reviewing:

- [Code Principles](shared/code_principles.md)
- [Code Style Standards](shared/code_style_standards.md)
- [Architecture Guidelines](shared/architecture_guidelines.md)
- [Testing Standards](shared/testing_standards.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Documentation Standards](shared/documentation_standards.md)
- [Debugging Standards](shared/debugging_standards.md)
- [Technical Decisions](../technical/decisions.md)

## Review Checklist

Review the change against these questions:

- does it stay inside the requested scope and preserve approved boundaries?
- does it fit the documented architecture and approved stack?
- does it apply the project code principles without unnecessary complexity or silent fallbacks?
- are naming, imports, type hints, logging, and public interfaces consistent with local standards?
- do tests cover the changed behavior at the right level without contamination or brittle implementation-detail coupling?
- does documentation match the code and explain non-obvious rationale or operator impact where needed?
- for bug fixes, is the verified root cause addressed and is regression protection in place?

## Evidence to Require

- validation commands or checks are explicit
- changed behavior is covered by tests or an explicit gap is recorded
- documentation impact is handled or intentionally not needed
- any remaining follow-up work is clearly separated from close blockers

## Review Outcome Guidance

When review finds issues:

- separate blockers from optional follow-up improvements
- call out missing evidence such as validation gaps or documentation gaps explicitly
- keep feedback tied to the authoritative shared rule source whenever possible

## Related Guidance

- [plan.md](plan.md) for planning application
- [code.md](code.md) for implementation application
- [testing.md](testing.md) for repo-specific test selection and commands
- [debug.md](debug.md) for debugging application
