# Testing Standards

This file contains the authoritative testing standards for QuickScale.

Repo-specific test categories, locations, commands, and AI-assisted
failure-analysis guidance belong in [testing.md](../testing.md) and
[debug.md](../debug.md).

## Behavior and Contract Focus

- Test observable behavior and public contracts rather than internal implementation details
- Keep assertions tied to outputs, side effects, or published interfaces
- Update tests when intended behavior changes; do not preserve stale expectations by default

## Isolation and Dependency Control

- Isolate unit tests from external dependencies with appropriate mocks, fakes, or fixtures
- Do not use live network services, shared mutable state, or environment-sensitive global state in unit tests unless the test category explicitly requires it
- Restore any mutated global state, environment, filesystem artifacts, caches, or registries before the test ends
- Every test should pass both in isolation and as part of the full suite

## Test Structure and Readability

- Group related tests consistently by feature or unit under test
- Prefer clear arrange-act-assert structure
- Keep each test focused on one behavior or narrow scenario
- Use names that describe the behavior or contract being verified

## Test Data Management

- Use fixtures, factories, and shared helpers for common setup when they improve clarity and consistency
- Avoid ad-hoc duplicated test data when a reusable factory or fixture captures the same intent more clearly
- Keep test data explicit enough that the behavior under test remains obvious

## Parameterization and Duplication Control

- Use parameterization when the same behavior must be checked across multiple inputs
- Avoid copy-pasted tests that differ only by data
- Split tests when scenarios have materially different intent or setup

## Coverage and Edge Conditions

- Cover happy paths, error paths, and meaningful edge conditions for changed behavior
- Verify boundary conditions and invalid input handling where relevant
- Add or update regression coverage for confirmed defects when the repository's testing model expects it

## Test Maintenance Discipline

- When a test fails, determine whether the test is outdated or the code regressed
- Do not weaken, pad, or overfit tests just to make a change pass
- Keep test updates aligned with the production change; avoid broad unrelated rewrites in the same test update
- Prefer local patching and scoped cleanup over global modifications that can leak across tests
