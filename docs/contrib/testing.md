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

```bash
# Unit + integration tests for all packages (excludes e2e)
make test

# Unit tests only (no integration tests)
make test-unit

# Run tests for a specific section
make test -- --core      # quickscale_core only
make test -- --cli       # quickscale_cli only
make test -- --modules   # quickscale_modules only

# Stop on first failure (direct pytest)
poetry run pytest quickscale_core/tests --exitfirst --tb=short -m "not e2e"

# E2E tests only (requires Docker)
make test-e2e
```

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
- the selected commands provide enough evidence for the changed behavior
- failures that appear during authoring are handled through root-cause debugging rather than test padding or scope drift
