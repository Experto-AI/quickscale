# DEBUG - Debugging and Bug-Fix Guide

Use this guide for QuickScale-specific debugging flow, failure-analysis inputs,
and command selection. Shared debugging, testing, scope, and architecture
rules remain authoritative.

## Suggested Debugging Loop

Apply the shared rules with this practical loop:

1. reproduce the failure with the smallest useful command or fixture set
2. decide whether the failure is in the code, the test, or the environment assumptions
3. isolate the root cause with targeted logs, assertions, and focused reruns
4. implement the smallest verified fix that addresses the real defect
5. add or update regression coverage when the repository's testing model expects it
6. rerun the most relevant checks first, then broaden validation as required by scope and risk

## Repo-Specific Debugging Commands

For focused failure analysis, these commands are usually the best starting
points:

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

## AI-Assisted Failure Analysis

When using an AI assistant or LLM to analyze failures:

- capture the smallest useful failing command output first
- include recent changes, expected behavior, and the test context
- prefer one failing test or `--exitfirst` output before pasting broader suite logs
- treat suggestions as hypotheses until they are verified against the code and reruns

## Scope Guardrails While Debugging

- fix the verified root cause, not the symptom
- do not weaken tests or add silent fallbacks just to make failures disappear
- keep the change inside the approved scope and note adjacent issues separately

## Debugging Exit Criteria

Before considering a bug fix complete, confirm that:

- the verified root cause is addressed directly
- no workaround was substituted for a real fix
- the change stayed inside the approved scope
- the relevant regression path is covered or the remaining gap is explicit
