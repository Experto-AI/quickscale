# Validation Policy (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Validation Policy**
> **Related docs**: [Decisions](decisions.md) | [Implementation Contract](implementation_contract.md) | [Scaffolding](scaffolding.md)

This companion owns repository validation entrypoints, testing standards, coverage expectations, isolation rules, and E2E infrastructure guidance. [decisions.md](./decisions.md) remains the repository-wide tie-breaker for cross-cutting policy and prohibitions.

<a id="repository-command-reference"></a>
## Repository Command Reference

**Validation entrypoints:**
- Prefer repository `make` targets over lower-level helper scripts.
- Use the narrowest relevant validation first, then widen only as needed.

**Shared commands:**
- `make bootstrap` - Full repository bootstrap after Poetry is available.
- `make setup` - Install repository dependencies without rerunning bootstrap checks.
- `make lint` - Shared lint-check entrypoint.
- `make format` - Shared formatting entrypoint.
- `make test` - Shared unit and integration test entrypoint.
- `make test-unit` - Shared unit-only entrypoint with section and module scoping.
- `make test-integration` - Shared integration-test entrypoint for module suites against a NOBYPASSRLS PostgreSQL 18 role.
- `make test-e2e` - End-to-end validation with PostgreSQL and browser automation.
- `make ci-e2e` - CI-parity release-gate validation including E2E.
- `make version-check` - Verify `VERSION` parity across the versioned packages.
- `make publish-module MODULE=<name>` - Maintainer helper for split-branch publishing.

**Assistant guidance:**
- Prefer `make` targets for shared repository workflows instead of calling lower-level helper scripts directly.
- Use `make lint` and `make format` for repo-wide lint and format guidance.
- Use `make test` or targeted `make test-unit` invocations for shared test runs.
- Use `make ci-e2e` for release-gate validation when the full hardening and release path needs E2E coverage.
- Use `make version-check` when verifying repository package-version parity.
- Do not invent or document nonexistent helper scripts such as `./scripts/test_all.sh`.

<a id="testing-standards"></a>
## Testing Standards

**Coverage Targets:**
- 90% overall mean coverage plus 80% minimum per file for `quickscale_core`, `quickscale_cli`, modules, and themes.
- CI fails if overall mean drops below 90% or any file falls below 80%.
- Coverage reports run on every CI build.
- Thresholds are enforced across both unit and integration gates — `make test-unit` (via `scripts/test_unit.sh`) covers core and CLI code, while `make test-integration` (via `scripts/test_integration.sh`) covers module suites. Non-quarantined integration suites enforce the normal dual overall and per-file thresholds, while quarantined suites are excluded from gate failure and from the overall mean until their owning ticket closes.

**Test Requirements:**
- New features require tests.
- Bug fixes require regression tests.
- CLI changes require integration tests.
- Business logic requires unit tests.
- Critical paths require E2E tests.

**Test Stack:**
- `pytest` plus `pytest-django`.
- `factory_boy`.
- `pytest-cov`.
- GitHub Actions CI.

**Generated Projects Include:**
- a sample `pytest-django` test demonstrating patterns
- `factory_boy` configuration for model factories
- `pytest.ini` test configuration
- `.github/workflows/ci.yml` for automated testing

### Test Isolation Policy

**Policy:**
- Never create test artifacts in the codebase directory.
- Always use isolated filesystems for tests that create files.
- CLI tests use `CliRunner.isolated_filesystem()`.
- File-generation tests use `pytest.tmp_path` or `pytest.tmpdir`.
- Integration tests use temporary directories such as `tempfile.mkdtemp()`.

### E2E Testing Policy

**Purpose:** Validate complete user workflows with real database and browser automation before releases.

**Requirements:**
- PostgreSQL 18 container via `pytest-docker`.
- Playwright browser automation with Chromium.
- Full project lifecycle coverage: generate -> install -> migrate -> serve -> browse.
- Separate from fast CI using `@pytest.mark.e2e`.

**When Required:**
- Pre-release validation.
- Production-readiness verification.
- Frontend regression testing.
- Docker and database integration verification.
- After generator template changes.

**Tech Stack:**
- `pytest-docker` for PostgreSQL orchestration.
- `pytest-playwright` for browser automation.
- `docker-compose.test.yml` for PostgreSQL 18 test infrastructure.
- Playwright Chromium for headless or headed UI checks.

**Execution Time:** 5-10 minutes for the full suite. Acceptable for release gates; excluded from fast daily CI.

**CI Strategy:**
- Fast CI excludes E2E with `pytest -m "not e2e"`.
- Release CI includes E2E with `pytest -m e2e`.
- Separate workflows preserve fast feedback for daily development.

**Usage:** See [user_manual.md](./user_manual.md#21-end-to-end-e2e-tests) for operator-facing run instructions.

<a id="e2e-test-infrastructure"></a>
<a id="13-e2e-test-infrastructure"></a>
## E2E Test Infrastructure

**Purpose:** End-to-end testing validates the full QuickScale project lifecycle with real database and browser automation.

**Current structure:**

```
quickscale_core/tests/
├── test_e2e_full_workflow.py
├── docker-compose.test.yml
└── conftest.py
```

Key expectations:
- use isolated temporary directories for generated-project tests
- cover generate -> install -> migrate -> serve -> browse flows
- keep E2E separate from the fast default test path
- validate database, Docker, and browser integration together before release closeout when appropriate
