# Testing Guide

This is a testing application guide. It combines the shared testing standards
with QuickScale-specific test locations, fixtures, commands, examples, and
contamination-prevention reminders.

Shared documents in [shared/](shared/) remain authoritative when guidance
overlaps.

## Use This Guide When

Use this guide when you need to:

1. choose the correct test category and location
2. write or update tests for implemented behavior
3. run the relevant repo-specific test commands for the affected area
4. diagnose test-setup or contamination issues

## Authoritative Sources for Testing

Apply these rule sources while working on tests:

- [Testing Standards](shared/testing_standards.md)
- [Code Principles](shared/code_principles.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Debugging Standards](shared/debugging_standards.md) when failures need diagnosis

## Applied Testing Checklist

- choose the correct test category and location before writing new tests
- assert on behavior and contracts, not internal implementation details
- isolate external dependencies and restore any global state you modify
- use clear arrange-act-assert structure and descriptive test names
- add edge-case or regression coverage when changed behavior requires it
- confirm the relevant tests pass alone and in the relevant suite

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

```bash
# Start PostgreSQL test database (quickscale_core)
docker-compose -f quickscale_core/tests/docker-compose.test.yml up -d test-db

# Run unit and integration tests
make test

# Cleanup
docker-compose -f quickscale_core/tests/docker-compose.test.yml down
```

## Unit Tests Recipe

Use the shared testing standards for structure, behavior focus, isolation, and
mock discipline. This section captures the repo-specific placement and fixtures
that matter while applying those rules.

**Example — CLI command test**:

```python
# quickscale_cli/tests/commands/test_plan_command.py
from click.testing import CliRunner
from quickscale_cli.main import cli


def test_plan_command_creates_config(tmp_path, cli_runner):
    """Test that plan command creates a project config file."""
    result = cli_runner.invoke(
        cli,
        ["plan", "--name", "myproject"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
```

**Example — Core generator unit test**:

```python
# quickscale_core/tests/test_generator/test_generator.py
def test_generator_creates_manage_py(generated_project_path):
    """Test that the generator produces a valid manage.py."""
    assert (generated_project_path / "manage.py").exists()
```

Available fixtures (`quickscale_core/tests/conftest.py`):
- `generated_project_path` — generates a full project into `tmp_path` and returns the path
- `sample_project_name` — returns `"testproject"`
- `sample_project_config` — returns a config dict

Available fixtures (`quickscale_cli/tests/conftest.py`):
- `cli_runner` — Click `CliRunner` instance
- `sample_project_name` — returns `"testproject"`

## Integration Tests Recipe

Use the shared testing standards for the normative rules. This section defines
the repo-specific integration-test location and marker usage.

**Example**:

```python
# quickscale_core/tests/test_integration.py
@pytest.mark.integration
class TestProjectGenerationIntegration:
    """End-to-end integration tests."""

    def test_generate_and_validate_project(self, tmp_path):
        """Generate project and verify it is a valid Django project."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "integration_test"

        generator.generate("integration_test", output_path)

        assert (output_path / "manage.py").exists()
        assert (output_path / "integration_test").is_dir()
        assert (output_path / "pyproject.toml").exists()
```

## E2E Tests Recipe

Use the shared testing standards for the normative rules. This section defines
the repo-specific e2e marker and command path.

**Example**:

```python
# quickscale_cli/tests/test_e2e_development_workflow.py
@pytest.mark.e2e
class TestDevelopmentCommandsE2E:
    """End-to-end tests for development commands with real Docker containers."""

    def test_up_and_down_workflow(self, tmp_path, cli_runner):
        """Test that quickscale up starts and quickscale down stops services."""
        generator = ProjectGenerator(theme="showcase_html")
        generator.generate("e2e_test", tmp_path / "e2e_test")

        result = cli_runner.invoke(cli, ["up"], catch_exceptions=False)
        assert result.exit_code == 0

        result = cli_runner.invoke(cli, ["down"], catch_exceptions=False)
        assert result.exit_code == 0
```

## Test Contamination Pitfalls

### Avoid global module mocking without cleanup

```python
import sys
from unittest.mock import MagicMock

sys.modules["some_module"] = MagicMock()
```

Global module replacement like the example above leaks across tests unless you
pair it with reliable teardown logic.

### Prefer local patching or fixture-scoped setup

```python
from unittest.mock import patch


@patch("module.function")
def test_something(mock_function):
    mock_function.return_value = "test_value"
```

Prefer local patching or fixture-scoped setup so cleanup is automatic and
readable.

### Restore environment and temporary resources

```python
class TestEnvironmentVariables(TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
```

Apply the same restoration discipline to temp files, caches, and any mutable
global registries.

## Testing Exit Criteria

Before considering a test update complete, confirm that:

- the test category and location match the repo-specific structure above
- the shared testing standards were followed for behavior focus, isolation, and maintainability
- the selected commands provide enough evidence for the changed behavior
- failures that appear during authoring are handled through root-cause debugging rather than test padding or scope drift

---

## References

For authoritative testing rules, see:

- [Testing Standards](shared/testing_standards.md)
- [Code Principles](shared/code_principles.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)

For failure diagnosis, see:

- [Debugging Standards](shared/debugging_standards.md)
- [debug.md](debug.md)
