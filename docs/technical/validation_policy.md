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
- `make test-cov` - Combined coverage path (core + CLI + optional backups module) with dual-threshold enforcement.
- `make test-e2e` - End-to-end validation with PostgreSQL and browser automation.
- `make ci-e2e` - CI-parity release-gate validation including E2E.
- `make version-check` - Verify `VERSION` parity across the versioned packages.
- `make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<sha|ABSENT>` - Maintainer helper for split-branch publishing with force-with-lease safety (SA117 Phase 4). The expected remote SHA (40 hex characters or `ABSENT` for first publish) is required.

**Assistant guidance:**
- Prefer `make` targets for shared repository workflows instead of calling lower-level helper scripts directly.
- Use `make lint` and `make format` for repo-wide lint and format guidance.
- Use `make test` or targeted `make test-unit` invocations for shared test runs.
- Use `make ci-e2e` for release-gate validation when the full hardening and release path needs E2E coverage.
- Use `make version-check` when verifying repository package-version parity.
- Do not invent or document nonexistent helper scripts such as `./scripts/test_all.sh`.

<a id="testing-standards"></a>
## Testing Standards

**Gate split** — the rule is authoritative in
[decisions.md §Unit/Integration Gate Split](./decisions.md#unitintegration-gate-split).

| Gate | Make target | Scope | Database | Role |
|------|-------------|-------|----------|------|
| Unit | `make test-unit` | `quickscale_core/tests`, `quickscale_cli/tests` (DB-free, marked `not integration and not e2e`) | None | N/A |
| Integration | `make test-integration` | `quickscale_modules/*/tests` (PostgreSQL-required, marked `not e2e`) | PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` |

`make test` runs both gates sequentially as a combined check.

**Coverage Targets:**
- 90% equal-weight package mean coverage plus 80% minimum per file for `quickscale_core`, `quickscale_cli`, modules, and themes.
- CI fails if the equal-weight package mean drops below 90% or any file falls below 80%.
- Coverage reports run on every CI build.
- Thresholds are enforced across both unit and integration gates — `make test-unit` (via `scripts/test_unit.sh`) covers core and CLI code, while `make test-integration` (via `scripts/test_integration.sh`) covers module suites. Non-quarantined integration suites enforce the normal dual overall and per-file thresholds. Quarantined suites are excluded from gate failure and from the overall mean; each quarantine entry is removed independently as its own owning ticket lands/completes — quarantine is per-entry, not held for a single simultaneous closeout across all entries.
- **Combined coverage path**: `make test-cov` aggregates coverage from core + CLI unit tests and (when PostgreSQL is available) the backups module's DR-engine exercise into a single combined measurement. The dual-threshold policy (90% equal-weight package mean, 80% per-file) is enforced via `scripts/check_coverage_policy.py`, which is invoked as Phase 4 of the `test-cov` recipe. Standalone `make test-cov` skips the backups module when PostgreSQL is unavailable.
- **Required-backups mode**: Set `REQUIRE_BACKUPS_COVERAGE=1` (e.g., `make test-cov REQUIRE_BACKUPS_COVERAGE=1`) to fail if PostgreSQL or the DR toolchain is not available, ensuring CI cannot silently skip backups-module coverage. This mode is used by `make ci` and `make ci-e2e` via `scripts/check_ci_locally.sh`.
- **Coverage policy helper**: `scripts/check_coverage_policy.py` is a standalone Python script that validates `coverage.json` output against the dual-threshold policy. It accepts `--mean-threshold` and `--per-file-threshold` overrides and exits with code 0 (pass), 1 (fail), or 2 (data error). Tests are in `scripts/test_ci_coverage_policy.py`.

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

<a id="runner-tuning-knobs"></a>
### Runner Tuning Knobs

Environment variables that control concurrency and progress reporting for the
repository validation runners. Defaults are tuned for CI parity; override only
when diagnosing a run or working under constrained resources. See
[CHANGELOG.md](../../CHANGELOG.md) for each knob's implementation history.

**Concurrency:**

| Variable | Default | Effect |
| --- | --- | --- |
| `QS_CI_PARALLEL` | `1` | `0` runs `make ci` static stages serially instead of concurrent fan-out. |
| `QS_E2E_PARALLEL` | `1` | `0` runs the Core and CLI E2E lanes serially instead of concurrently. |
| `QS_INTEGRATION_JOBS` | `0` | Caps concurrent module workers for `make test-integration`. `0` or unset = unlimited; `1` = serial; positive `N` = at most `N` workers. |
| `PYTEST_XDIST_WORKERS` | `auto` | Pins xdist worker count for unit tests. `0` = true serial run; positive integer caps workers. |
| `QS_E2E_XDIST_WORKERS` | `min(max(1,floor(nproc/2)), max(1,floor(MemAvailable_GiB/4)), 4)` | Pins pytest-xdist workers per E2E lane. `0` or `1` runs each lane serially; values `>=2` append `-n N --dist loadscope`. |

**E2E memory guard.** A preflight check falls back to serial lanes when resting
memory headroom is low, guarding against `systemd-oomd` reaping the run.

| Variable | Default | Effect |
| --- | --- | --- |
| `QS_E2E_NO_MEMORY_GUARD` | unset | `1` skips the preflight entirely. |
| `QS_E2E_MIN_AVAIL_MB` | `4096` | `MemAvailable` below this always forces serial. |
| `QS_E2E_COMFORT_AVAIL_MB` | `8192` | Low `SwapFree` forces serial only when `MemAvailable` is also under this. |
| `QS_E2E_MIN_SWAP_MB` | `3072` | `SwapFree` threshold, subject to the condition above. |

The swap threshold is deliberately conditional: on a RAM-rich machine, gigabytes
of swap held by idle browser or editor pages is normal and is not evidence of
memory pressure. The memory guard takes precedence over the worker setting: when
it fires, it forces serial lanes and sets the runner's internal
`E2E_XDIST_WORKERS=1`, so pytest runs serially in each lane even when an explicit
 `QS_E2E_XDIST_WORKERS` value was supplied. Only `QS_E2E_NO_MEMORY_GUARD=1`
bypasses this clamp; the threshold overrides do not bypass it.

**Progress and provenance:**

| Variable | Default | Effect |
| --- | --- | --- |
| `QS_E2E_HEARTBEAT_INTERVAL` | `60` | Seconds between progress lines during the concurrent-lane phase. Each tick prints total elapsed time plus per-lane silence (`running` vs `running, quiet 7m`); durations over an hour use `2h05m` form. |
| `QS_E2E_INTEGRATION_REF` | `v87` | Ref the provenance banner compares the checkout against. The banner prints the checkout path, the script's HEAD, and `OUT OF DATE — N commit(s) behind` when the checkout lags. |

<a id="reading-a-long-e2e-run"></a>
### Reading a Long E2E Run

Two distinct conditions, each with its own signal:

| Condition | Signal | Meaning | Remedy |
| --- | --- | --- | --- |
| Stuck lane | heartbeat `quiet Nm` | lane produced no log output for N minutes | inspect that lane's log; abort if genuinely hung |
| Out-of-date checkout | provenance banner `OUT OF DATE` | bash is executing older script text than the integration ref | re-launch the run from an up-to-date checkout |

Neither signal is a verdict on its own. A quiet stretch is normal during a Docker
image build or `pnpm install`. An out-of-date banner is expected when `make ci-e2e`
is launched from a pinned worktree while fixes land in a sibling tree — bash
executes the script text the run started with, so a mid-run commit is never picked
up. Check the banner before attributing a failure to the code under test.
