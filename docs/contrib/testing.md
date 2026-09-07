# Testing Guide

Use this guide for QuickScale-specific test selection, locations, commands,
fixtures, and contamination-prevention reminders. Shared testing and debugging
standards remain authoritative for the normative rules.

## Test Category Decision Tree

```text
What are you testing?

QuickScale Core (generator, templates, file utils, config)
-> Unit/Integration Test -> quickscale_core/tests/
   - Standard unit tests: no marker needed
   - Multi-step workflow tests: @pytest.mark.integration

QuickScale CLI (commands: plan, apply, status, up, down...)
-> Unit Test -> quickscale_cli/tests/
   - Use cli_runner fixture; mock filesystem and Docker

Module Logic (auth, crm, blog, and other quickscale_modules)
-> Unit Test -> quickscale_modules/<name>/tests/
   - Django TestCase with --ds=tests.settings

Complete User Journey (requires running Docker)
-> E2E Test -> @pytest.mark.e2e (anywhere in quickscale_core/ or quickscale_cli/)
   - Run separately via: make test-e2e
```

## Running Tests

Pick the command from the validation tier the current work owns —
[Validation Tiers](../technical/validation_policy.md#validation-tiers) is
authoritative for tier selection and for what each tier owes. In short:
`change` runs lint, typecheck, and focused tests over the changed behavior;
`task` runs the owning section suite; `release` runs the full CI lanes. Each
tier's command subsumes the narrower ones, so run one command per tier rather
than a narrow target followed by a wider one repeating it — and do not reach for
a wider command to establish a baseline.

```bash
# change tier: focused run over the changed behavior
make test-unit K=<test-name-or-expression>
make test-unit SECTIONS=core K=<expr>        # narrow to one package too
# equivalent direct form:
poetry run pytest quickscale_core/tests/test_<area>.py --tb=short -m "not e2e" -o addopts= --no-cov

# task tier: the owning section suite
make test-unit -- --core
make test-integration MODULE=<name>

# release tier: full CI parity (make ci-e2e instead when an E2E trigger applies)
make ci

# Unit + integration tests for all packages (excludes e2e); task-tier breadth
make test

# Unit tests only (no integration tests)
make test-unit

# Run tests for a specific section
make test -- --core      # quickscale_core only
make test -- --cli       # quickscale_cli only
make test -- --modules   # quickscale_modules only

# Stop on first failure
make test-unit ARGS='-x'
poetry run pytest quickscale_core/tests --exitfirst --tb=short -m "not e2e"

# E2E tests only (requires Docker)
make test-e2e
```

## Re-running After a Failure

A failing run is the start of a fix cycle, and repeating the whole lane to
re-check one test is the slow way through it. Narrow the rerun instead:

```bash
# Re-run only what failed last time (recorded to .quickscale/last-failures.json)
make retry
make retry-show                     # print those commands without running them

# Narrow by hand
make test-unit K=test_render_theme
make test-integration MODULE=blog K=test_rls
make test-e2e K=test_wheel_lifecycle
make test-unit ARGS='-x --lf'       # raw pytest flags

# Re-run one stage of the local CI pipeline
make ci ONLY=integration
make ci FROM=coverage               # resume from a stage onward
make ci SKIP_INSTALL=1              # skip the dependency install
```

`K=`/`ARGS=` disable the coverage gate for the scoped run, because a narrowed
selection measures almost no code and would otherwise fail `--cov-fail-under=90`
on tests that passed. `ONLY=`/`FROM=`/`SKIP_INSTALL=` mark the run
`PARTIAL CI — NOT a full pass`. Both print a warning saying so: neither is a
substitute for the tier command that owns the change. See
[Scoping and Rerun Variables](../technical/validation_policy.md#scoping-and-rerun-variables).

## Database-Backed Test Setup

Unit and integration tests that require PostgreSQL in `quickscale_core/` use the
test compose file below.

Use the Docker Compose v2 plugin command syntax (`docker compose`). The
compose file name stays `docker-compose.test.yml`.

```bash
# Start PostgreSQL test database (quickscale_core)
docker compose -f quickscale_core/tests/docker-compose.test.yml up -d test-db

# Run unit and integration tests
make test

# Cleanup
docker compose -f quickscale_core/tests/docker-compose.test.yml down
```

## Repo Test Placement and Fixtures

### Unit Tests

- CLI command tests live in `quickscale_cli/tests/`; use `cli_runner` and mock
    filesystem or Docker interactions when the command path needs isolation.
- Core generator, file utility, and config tests live in
    `quickscale_core/tests/`.

Available fixtures (`quickscale_core/tests/conftest.py`):
- `generated_project_path` — generates a full project into `tmp_path` and returns the path
- `sample_project_name` — returns `"testproject"`
- `sample_project_config` — returns a config dict

Available fixtures (`quickscale_cli/tests/conftest.py`):
- `cli_runner` — Click `CliRunner` instance
- `sample_project_name` — returns `"testproject"`

### Integration Tests

- Use `quickscale_core/tests/` with `@pytest.mark.integration` for multi-step
    workflow coverage that stays below full E2E.

### E2E Tests

- Use `@pytest.mark.e2e` for full-journey coverage in `quickscale_core/` or
    `quickscale_cli/` tests.
- Run E2E separately via `make test-e2e`.

## Test Contamination Pitfalls

### Avoid global module mocking without cleanup

Global module replacement such as `sys.modules[...] = MagicMock()` leaks across
tests unless you pair it with reliable teardown logic.

### Prefer local patching or fixture-scoped setup

Prefer local patching or fixture-scoped setup so cleanup is automatic and
readable.

### Restore environment and temporary resources

Apply the same restoration discipline to temp files, caches, and any mutable
global registries.

## Testing Exit Criteria

Before considering a test update complete, confirm that:

- the test category and location match the repo-specific structure above
- the shared testing standards were followed for behavior focus, isolation, and maintainability
- the selected commands provide enough evidence for the changed behavior at the declared validation tier
- every check deferred to a wider tier is reported with that tier named
- failures that appear during authoring are handled through root-cause debugging rather than test padding or scope drift
