# REVIEW - Quality Control Guide

Use this guide for review-stage questions, evidence requirements, and outcome
language. Shared documents remain authoritative for normative engineering
policy.

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
