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
- `make test-integration` - Shared integration-test entrypoint for module suites through the owned PostgreSQL 18 lifecycle and its NOBYPASSRLS role.
- `make test-cov` - Combined coverage path (core + CLI + optional backups module) with dual-threshold enforcement.
- `make test-e2e` - End-to-end validation with PostgreSQL and browser automation.
- `make retry` - Re-run only the tests recorded as failing by the last run; `make retry-show` prints those commands without running them.
- `make ci-e2e` - CI-parity release-gate validation including E2E.
- `make version-check` - Verify `VERSION` parity across the versioned packages.
- `make check-commit-testimony` - Require each behavioural control commit to carry an SA ticket, integer vNN roadmap reference, or same-commit changelog testimony.
- `make check-gate-suites` - Run every `scripts/test_*.py` suite with pytest's cache provider and product coverage disabled.
- `make check-dependency-vulnerabilities` - Run the blocking Trivy v0.74.0 scan of both committed Poetry lockfiles.
- `make check-security-static-analysis` - Run the blocking focused Bandit 1.9.4 source scan.
- `make security-negative-probes` - Prove scanner, checksum, archive-safety, and stale-database failures remain fail-closed.
- `make isolation-conformance` - Run the PostgreSQL isolation-conformance suites through the repository-owned runner.
- `make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40-hex-remote-sha>` - Maintainer helper for split-branch publishing with force-with-lease safety (SA117 Phase 4). Each mutable split-branch update requires a freshly observed exact 40-hex remote SHA. The accepted SA145 exact-SHA contract forbids `ABSENT`; it is not a valid input.

**Assistant guidance:**
- Prefer `make` targets for shared repository workflows instead of calling lower-level helper scripts directly.
- Use `make lint` and `make format` for repo-wide lint and format guidance.
- Select the test command from the validation tier below rather than defaulting to the widest one. `make test` is a `task`/`release`-tier command and is never the per-change check.
- Scope a run with the target's own variables rather than hand-rolling a pytest invocation: `K=<expr>` narrows by keyword, `ARGS=<flags>` forwards raw pytest flags, and both compose with `SECTIONS=`/`MODULE=`. See [Scoping and Rerun Variables](#scoping-and-rerun-variables).
- `make ci ONLY=`/`FROM=`/`SKIP_INSTALL=` re-runs part of the local CI pipeline while iterating on a failure. **A partial run never satisfies the `release` tier** — it announces itself as `PARTIAL CI — NOT a full pass` and the tier still owes a complete `make ci`.
- Use `make ci-e2e` for release-gate validation when the full hardening and release path needs E2E coverage.
- Use `make version-check` when verifying repository package-version parity.
- Use `make check-commit-testimony` to validate hosted-workflow, gate-registry, and provisioning-station commit testimony over the selected Git range.
- Use `make check-gate-suites` when validating the registry's complete `scripts/` conformance population; it is cache-free and does not contribute product coverage.
- Use `make isolation-conformance` when Docker, PostgreSQL 18 client tools, and Poetry dependencies are available. The target delegates to the owned isolation profile, which provisions scoped databases on a dynamic loopback endpoint; hosted service/lease behavior remains distinct.
- Do not invent or document nonexistent helper scripts such as `./scripts/test_all.sh`.

<a id="validation-tiers"></a>
## Validation Tiers

Validation depth is chosen by tier, not by habit. A tier bounds the obligation:
run the tier the current work owns and stop there.

| Tier | Applies to | Command |
|------|-----------|---------|
| `change` | one implementation phase, one correction, one edit session | `make lint`, `make typecheck`, then a focused `make test-unit K=<expr>` (or `SECTIONS=<section> K=<expr>`) over the changed behavior; equivalently `poetry run pytest <path-or-node> --tb=short -m "not e2e" -o addopts= --no-cov` |
| `task` | a completed plan, a convergence pass, or a delta crossing a package or module boundary | the owning section suite — `make test-unit -- --core` or `-- --cli`, or `make test-integration MODULE=<name>` — or `make check QUIET=1` when repository gates sit in the delta's surface |
| `release` | plan closeout, version bump, generator-template change, pre-merge | `make ci`, or `make ci-e2e` when an [E2E trigger](#e2e-testing-policy) applies, followed by the closeout lanes in [Clean-Initial Migration Acceptance](#clean-initial-migration-acceptance-sa151) |

**Each tier's command already subsumes the narrower ones.** `make check` covers
lint, typecheck, the unit gate, and the repository gates; `make ci` covers those
plus mypy, coverage, and the integration gate. Running a narrower target first and
then a wider one that repeats it is the duplication this policy exists to remove —
pick the tier, run its command once.

**Tier selection rules:**
- Default to `change`. Escalate to `task` when the delta crosses a package or
  module boundary, touches a file an earlier phase of the same plan already
  changed, or changes shared or generated surface.
- Escalate to `release` at plan closeout and whenever an E2E trigger under
  [E2E Testing Policy](#e2e-testing-policy) fires — notably after generator
  template changes.
- A green `change` tier is a complete obligation at that tier. Report every check
  deferred to a wider tier by naming that tier; a deferral with no named tier is
  an omission, not a tier choice.
- `make test-cov` and the [coverage targets](#testing-standards) below are
  `task`/`release`-tier obligations. A `change`-tier run passes
  `-o addopts= --no-cov` so the package-level coverage addopts do not fail a
  scoped run — that is a scoping flag, never a way to avoid the threshold at the
  tier that owns it. `K=`/`ARGS=` apply those two flags for you and print
  `coverage gate disabled` so a scoped green is never read as a coverage pass;
  `make test-cov` deliberately accepts neither variable.
- **A wider tier is never run to establish a baseline.** It runs when the delta
  reaches its surface. A pre-existing failure is discovered at the tier that
  reaches it, and no baseline run precedes implementation.

## Candidate review and integration

Develop in the assigned track worktree, never directly on the integration branch.
Independent tracks may implement concurrently; serialize integration and reconcile
shared closeout documents at merge time. A shared audit or changelog file alone
does not prohibit independent implementation. One reviewed delivery runs at a time
per worktree; grouped tickets retain their individual acceptance criteria.

1. Measure worktree divergence and working-tree status against the current
   integration branch. Sync and resolve conflicts in the worktree before final
   review. Confirm the relevant starting condition with focused inspection; do
   not run a wider validation tier solely to establish a baseline.
2. Declare the candidate's file scope, verification commands, expected exits and
   artifacts, and rollback. Materialize the complete base-to-tip patch for the
   reviewer, including required fixture context. Record base and tip identities
   and a clean `git status --porcelain` at the exact reviewed tip. Missing patch
   input or a reviewer non-return yields no grade.
3. Obtain independent review and the validation required at the
   [owning tier](#validation-tiers). Changed reviewed product bytes or validation
   inputs require renewed review and validation against the new binding. Reuse
   accepted evidence only while its candidate and input binding remains valid.
   Review and validation may proceed in the same maintainer session; a fresh
   root session is not a gate.
4. Keep documents that record a verdict outside its frozen product evidence.
   After the verdict, reconcile audit notes and status in a separate documentation
   commit within the same delivery. Review and validate that documentation delta;
   recording evidence does not invalidate the unchanged product candidate.
5. Merge the exact reviewed and validated product tip, followed by its reviewed
   documentation closeout. If integration changes that binding, obtain the
   renewed evidence before completion. An explicitly authorized partial
   checkpoint remains open and clears no branch-state or release gate. Git-ref
   deliveries require a maintainer session with the necessary ref authority and
   credentials.

Do not deselect an integration-branch failure with `PYTEST_ADDOPTS`, `--deselect`,
or Makefile/CI changes to conceal a red gate. Assign one owning ticket, repair
within its authorized scope, and rerun. Other
tracks may continue implementation and unexcluded validation provisionally, but
no other ticket completes merge-back until the owning repair is green. Preserve
quality monotonicity: no additional warning or critical regressions, no raised
complexity ceilings, and no restored file-line ceilings. Findings outside the
delivery's scope receive their own ticket.

Long commands must produce durable logs and an actual completion exit code. Run
`make test` and `make quality` detached with `setsid`, write their exit status to a
file, and poll it. Never detach with `nohup`: its inherited ignored SIGHUP can
manufacture false failures in signal tests. Size budgets for the actual command
and parallelism. An interrupted run or missing exit status proves neither a pass
nor a product failure. Inspect logs and owned resources and complete required
cleanup. An unchanged candidate may be retried with its reason, logs, and attempt
recorded. Retain prior attempts as immutable evidence and give new attempts
distinct identifiers; a red result needs diagnosis and cannot be relabeled green.
Measured candidate bindings and run results belong in delivery and release evidence.
The roadmap states the required candidate and pending acceptance, without copying
transient tips or working-tree status.

The authorized roadmap simplification supersedes earlier one-run-only, no-retry,
and fresh-authority restrictions for verification within an already authorized
delivery. `EV-8` identifies SA165's first replacement verdict; it is not an attempt
limit. Changed reviewed product bytes or validation inputs still require renewed
review and validation. This change grants no additional product scope or
deployment/publication authority.

### PostgreSQL routing and scheduling

Track 3 (W3) owns scheduling priority and the exclusive Docker-backed acceptance
slot. Coordinate these acceptance windows across tracks. Helper-routed local
`restricted`, `isolation`, and `bypassrls` profiles provision private ephemeral
PostgreSQL 18 containers, dynamic loopback ports, scoped databases, and validated
roles; they do not claim the standing `localhost:5432` service. In particular,
`make test` routes its integration leg through these profiles. Preserve the
distinction between private profile resources and deliberately shared endpoints.

When a strict acceptance window requires stopping the standing `pg18-af10`
container, Track 3 must restart it afterwards and restore the twelve
`test_quickscale_*` databases and `quickscale_test_role` ownership. Do not remove
the container or prune its volume. Private profiles clean up only their own
validated resources; preserve the runners' exact-scope cleanup contracts.

<a id="testing-standards"></a>
## Testing Standards

**Gate split** — the rule is authoritative in
[decisions.md §Unit/Integration Gate Split](./decisions.md#unitintegration-gate-split).

| Gate | Make target | Scope | Database | Role |
|------|-------------|-------|----------|------|
| Unit | `make test-unit` | `quickscale_core/tests`, `quickscale_cli/tests` (DB-free, marked `not integration and not e2e`) | None | N/A |
| Integration | `make test-integration` | `quickscale_modules/*/tests` (PostgreSQL-required, marked `not e2e`) | Owned, dynamically scoped PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` |

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

### Registered script-gate and isolation execution

The registry-derived local and hosted conformance flow includes ten registered hosted
gates, including the CSRF-exempt contract, behavioural-commit testimony, blocking Trivy
dependency-vulnerability, and Bandit static-security gates. `make check-gate-suites` is the owning execution context for all current
`scripts/test_*.py` suites and invokes exactly:

```text
$(PYTHON) -m pytest scripts/ -p no:cacheprovider --no-cov -q
```

The scripts directory remains outside `.coveragerc`; the product coverage source list
and `fail_under = 90` are unchanged. The hosted CI job set also contains six
separately justified unowned jobs, for sixteen jobs total. `isolation-conformance` is
one of those hosted-unowned jobs: Make exposes the same runner for local verification,
but local execution uses the owned PostgreSQL 18 lifecycle described by
`scripts/provision_ci_postgres.sh`: Docker allocates a dynamic loopback endpoint and
scoped databases, and the profile validates the restricted role before the runner starts.
Hosted execution consumes its separately provisioned service and lease; no pre-created
local host server or database set is implied by this target or policy.

Trivy is acquired on demand from the v0.74.0 release for Linux x86_64/arm64 or
macOS x86_64/arm64 and verified against the official release-manifest SHA-256
before extraction. Windows uses WSL and therefore the Linux asset. Unsupported
native hosts fail explicitly; there is no skip path. Network/database refresh is
an explicit online prerequisite for the vulnerability target, while Bandit and
the committed gate/parity checks remain local.

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
- Stable content-addressed backend image identity across unchanged runs, with measured cold-versus-warm reuse coverage.
- Run-scoped container, port, volume, and network identity with exact QuickScale owner/lifecycle/scope labels; normal cleanup must remove matching disposable resources and untagged variable images without broad pruning, while `--no-cleanup` preserves diagnostic state.
- A source-free installed-wheel lifecycle from an external working directory that applies current artifacts for all twelve shipped modules and proves collectstatic, migrations, HTTP service, and exact-label cleanup.
- Separate from fast CI using `@pytest.mark.e2e`.

**When Required:** each trigger below escalates the work to the `release` tier
(see [Validation Tiers](#validation-tiers)).
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

### Clean-Initial Migration Acceptance (SA151)

The clean-break migration policy is guarded by two source-derived checks. Run
the topology guard without the package-default full-core coverage addopts:

```bash
poetry run pytest quickscale_core/tests/test_module_migration_topology.py -q --tb=short -o addopts= --no-cov
```

Run the generated-project proof as an E2E node against the pytest-docker
PostgreSQL 18 service:

```bash
poetry run pytest quickscale_core/tests/test_generated_project_runtime.py::TestGeneratedProjectRuntimeSmoke::test_all_module_initial_migrations_apply_from_embedded_sources -q --tb=short -o addopts= --no-cov
```

The second command is non-skippable: acceptance requires one pass and zero
skips. It generates a standalone all-module project, installs its dependencies
without a maintainer wheelhouse or source path, applies migrations once to an
empty database owned by a `NOSUPERUSER NOBYPASSRLS NOINHERIT` login role,
checks `makemigrations --check --dry-run`, verifies runtime migration origins
and recorder parity, and proves database/role cleanup. Release closeout also
runs `make test-integration`, `make test-bypassrls`, `make typecheck`, and the
serial `make test-e2e` lanes. These lanes are the canonical `release` tier for a
plan closeout; see [Validation Tiers](#validation-tiers).

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
- keep stable backend image identity independent from per-run resource identity, and bind cleanup to inspected labels rather than names or global prune commands

<a id="runner-tuning-knobs"></a>
<a id="scoping-and-rerun-variables"></a>
### Scoping and Rerun Variables

Make variables (not environment variables) that narrow a run or replay the last
failure. They exist so a fix can be re-verified in seconds instead of by
repeating the full lane; none of them changes what an unscoped run means.

| Variable | Targets | Effect |
| --- | --- | --- |
| `K=<expr>` | `test-unit`, `test`, `test-integration`, `test-e2e` | Passes `-k <expr>` to pytest. Composes with `SECTIONS=` and `MODULE=`. |
| `ARGS=<flags>` | same | Raw pytest flags, word-split by the recipe (`ARGS='-x --lf -vv'`). |
| `ONLY=<stage>` | `ci`, `ci-e2e` | Run only the named stages: `install`, `static`, `coverage`, `integration`, `e2e` (comma-separated). |
| `FROM=<stage>` | `ci`, `ci-e2e` | Run that stage and every stage after it. |
| `SKIP_INSTALL=1` | `ci`, `ci-e2e` | Skip the dependency-install stage. |

**Both families announce themselves, because both weaken a signal.** `K=`/`ARGS=`
disable the coverage gate (a narrowed selection measures almost no code, so the
90% threshold would fail on tests that passed) and print
`coverage gate disabled`. `ONLY=`/`FROM=`/`SKIP_INSTALL=` mark the run
`PARTIAL CI — NOT a full pass` and list what was skipped. **Neither satisfies the
tier its unscoped form belongs to** — a skipped stage may be exactly the one that
covers the change.

Scoped runs also default to serial pytest, since a 16-worker fan-out costs more
to start than a narrowed selection costs to run and `-x` cannot stop cleanly
under xdist; an explicit `PYTEST_XDIST_WORKERS=` still wins.

**Replaying a failure.** A failing test target or CI stage records the failing
node ids to `.quickscale/last-failures.json`; `make retry` re-runs exactly those
and `make retry-show` prints the commands without running them. Stages that run
pytest with `-p no:cacheprovider` (`check-gate-suites`,
`test-postgres-provisioning`) write no cache, so those record a stage-level
command instead of individual tests.

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
