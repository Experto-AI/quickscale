# DEBUG - Debugging and Bug-Fix Guide

This is a debugging application guide. It applies the shared debugging, testing, scope, and architecture rules while you diagnose failures and fix verified root causes.

Shared documents in [shared/](shared/) remain authoritative when guidance overlaps.

## Use This Guide When

- diagnosing failing tests, regressions, or production bugs
- deciding whether a failure belongs in code, tests, or environment setup
- checking that a proposed bug fix is narrow, validated, and not masking the real issue

## Authoritative Sources for Debugging

Use these rule sources while debugging:

- [Debugging Standards](shared/debugging_standards.md)
- [Code Principles](shared/code_principles.md)
- [Testing Standards](shared/testing_standards.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Architecture Guidelines](shared/architecture_guidelines.md)

## Suggested Debugging Loop

Apply the shared rules with this practical loop:

1. reproduce the failure with the smallest useful command or fixture set
2. decide whether the failure is in the code, the test, or the environment assumptions
3. isolate the root cause with targeted logs, assertions, and focused reruns
4. implement the smallest verified fix that addresses the real defect
5. add or update regression coverage when the repository's testing model expects it
6. rerun the most relevant checks first, then broaden validation as required by scope and risk

## Repo-Specific Debugging Commands

For focused failure analysis, these commands are usually the best starting points:

```bash
# Stop immediately at first failure
poetry run pytest quickscale_core/tests --exitfirst --tb=short -m "not e2e"

# Run one package section
make test -- --core
make test -- --cli
make test -- --modules

# Run a specific file directly
poetry run pytest quickscale_core/tests/test_integration.py --tb=short
```

See [testing.md](testing.md) for the full repo-specific testing map.

## Debugging Exit Criteria

Before considering a bug fix complete, confirm that:

- the verified root cause is addressed directly
- no workaround was substituted for a real fix
- the change stayed inside the approved scope
- the relevant regression path is covered or the remaining gap is explicit

## Related Guidance

- [testing.md](testing.md) for repo-specific test commands and locations
- [review.md](review.md) for post-fix quality review
- [code.md](code.md) for implementation application
