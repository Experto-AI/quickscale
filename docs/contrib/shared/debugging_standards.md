# Debugging Standards

This file contains the authoritative debugging and bug-fix standards for
QuickScale.

## Root Cause First

- Identify and fix the underlying cause of a bug rather than masking symptoms
- Do not introduce superficial workarounds or silent fallbacks that leave the real defect in place
- Treat unexplained retries, blanket exception swallowing, and arbitrary default returns as suspect until the underlying issue is understood

## Test Failure Triage

When tests fail after code changes:

- determine whether the test is outdated or the code regressed
- update the test only when the intended behavior has genuinely changed
- fix the code when the test still reflects the correct current behavior
- document the reasoning behind test changes made to reflect intentional behavior changes

## Focused Reproduction and Isolation

- Reproduce the problem with the smallest useful command, input, or fixture set
- Prefer targeted reruns that expose the failing behavior clearly before widening to broader validation
- Use structured logging, assertions, and targeted instrumentation that clarify the failure instead of adding noise

## Minimal, Scoped Fixes

- Keep bug fixes focused on the reported problem and its verified root cause
- Avoid bundling unrelated refactors, enhancements, or cleanup into a debugging change
- Preserve existing interfaces unless the fix explicitly requires an approved interface change

## Regression Protection

- Add or update regression coverage for confirmed bugs when the repository's testing model expects it
- Verify the fix with the most directly relevant tests first, then broaden validation as required by risk and scope
- If broader validation is deferred, call that out explicitly during review

## Debugging Review Application

When reviewing a bug fix, verify:

- the fix addresses the actual root cause
- no symptom-masking workaround was substituted for a real fix
- the change stayed within scope
- the relevant regression path is now covered or the gap is explicitly noted
