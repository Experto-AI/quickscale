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
# Re-run only the tests that failed in the last run
make retry
make retry-show          # show what retry would run, without running it

# Stop immediately at first failure
make test-unit ARGS='-x'
poetry run pytest quickscale_core/tests --exitfirst --tb=short -m "not e2e"

# Narrow to one test by name (coverage gate off for the scoped run)
make test-unit K=test_<name>
make test-integration MODULE=<name> K=test_<name>

# Run one package section
make test -- --core
make test -- --cli
make test -- --modules

# Run a specific file directly
poetry run pytest quickscale_core/tests/test_integration.py --tb=short

# Re-run a single stage of the local CI pipeline while iterating
make ci ONLY=integration
```

`make retry` reads `.quickscale/last-failures.json`, which a failing test target
or CI stage writes. Scoped and partial runs both print a warning that they are
not a substitute for the full tier command — see
[Scoping and Rerun Variables](../technical/validation_policy.md#scoping-and-rerun-variables).

See [testing.md](testing.md) for the full repo-specific testing map.

## AI-Assisted Failure Analysis

When using an AI assistant or LLM to analyze failures:

- capture the smallest useful failing command output first
- include recent changes, expected behavior, and the test context
- prefer one failing test or `-x`/`--exitfirst` output before pasting broader suite logs
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
