# Testing Stage Guide

This guide covers test generation AFTER implementation and code review are complete.

## Core Principle: Implementation-First Testing

**Always write implementation code first, then add tests after.**

- ✅ Implementation complete → Code reviewed → Write tests
- ❌ Never write tests before implementing functionality
- ❌ Never generate test code before implementation is complete

## When to Use This Guide

Use this guide in the **TESTING stage** after:
1. ✅ Implementation is complete (CODE stage done)
2. ✅ Code has been reviewed (REVIEW stage done)
3. Now ready to generate comprehensive tests

## Test Category Decision Tree

```
What are you testing?

🔧 QuickScale Core (generator, templates, file utils, config)
└─ Unit/Integration Test → quickscale_core/tests/
   ├─ Standard unit tests: no marker needed
   └─ Multi-step workflow tests: @pytest.mark.integration

⚙️ QuickScale CLI (commands: plan, apply, status, up, down...)
└─ Unit Test → quickscale_cli/tests/
   └─ Use cli_runner fixture; mock filesystem and Docker

🧩 Module Logic (auth, crm, blog, and other quickscale_modules)
└─ Unit Test → quickscale_modules/<name>/tests/
   └─ Django TestCase with --ds=tests.settings

🎬 Complete User Journey (requires running Docker)
└─ E2E Test → @pytest.mark.e2e (anywhere in quickscale_core/ or quickscale_cli/)
   └─ Run separately via: make test-e2e
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

## Unit Tests Recipe

**Purpose**: Test individual components in isolation with mocked dependencies.

**When to Use**:
- QuickScale CLI commands and generator logic
- Individual functions, classes, or modules
- Business logic without external dependencies

**Key Requirements**:
- Fast execution (< 1 second per test)
- Mock all external dependencies
- Test isolated behavior

**Example — CLI command test**:
```python
# quickscale_cli/tests/commands/test_plan_command.py
from click.testing import CliRunner
from quickscale_cli.main import cli

def test_plan_command_creates_config(tmp_path, cli_runner):
    """Test that plan command creates a project config file."""
    result = cli_runner.invoke(cli, ['plan', '--name', 'myproject'], catch_exceptions=False)
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

**Purpose**: Test multi-step workflows inside the core generator (not multi-package).

**When to Use**:
- End-to-end project generation followed by validation
- Workflows that span multiple internal components but don't need Docker

**Key Requirements**:
- Mark with `@pytest.mark.integration`
- Use `tmp_path` for filesystem isolation
- Use `ProjectGenerator` directly (no CLI invocation needed)
- **Included** in `make test` runs (not excluded)

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

**Purpose**: Test complete user workflows with real Docker containers.

**When to Use**:
- Testing CLI commands that start/stop Docker services (`quickscale up`, `quickscale down`)
- Testing with real databases and external services
- Production-like scenarios

**Key Requirements**:
- Mark with `@pytest.mark.e2e`
- **Excluded** from `make test` by default
- Run via `make test-e2e` (requires Docker running)
- Use `quickscale_cli.main.cli` via `CliRunner` or `subprocess`

**Example**:
```python
# quickscale_cli/tests/test_e2e_development_workflow.py
@pytest.mark.e2e
class TestDevelopmentCommandsE2E:
    """End-to-end tests for development commands with real Docker containers."""

    def test_up_and_down_workflow(self, tmp_path, cli_runner):
        """Test that quickscale up starts and quickscale down stops services."""
        # Generate project first
        generator = ProjectGenerator(theme="showcase_html")
        generator.generate("e2e_test", tmp_path / "e2e_test")

        # Start services
        result = cli_runner.invoke(cli, ['up'], catch_exceptions=False)
        assert result.exit_code == 0

        # Stop services
        result = cli_runner.invoke(cli, ['down'], catch_exceptions=False)
        assert result.exit_code == 0
```

## Test Contamination Prevention Checklist

### Before Writing Tests
- [ ] No global module mocking planned
- [ ] No global state modification planned
- [ ] No shared mutable data planned
- [ ] Cleanup strategy identified

### During Test Implementation
- [ ] Use setUp/tearDown for proper test isolation
- [ ] Store original state before modifying anything global
- [ ] Use context managers for automatic cleanup where possible
- [ ] Mock objects, not modules

### After Writing Tests
- [ ] Run tests in isolation - each test passes alone
- [ ] Run tests as suite - all tests pass together
- [ ] No contamination between tests
- [ ] All resources properly cleaned up

## Golden Rule

**Every test should pass whether run in isolation or as part of the full suite. If it doesn't, you have contamination that needs to be fixed.**

---

## References

For detailed testing standards, see:
- [Testing Standards](shared/testing_standards.md) - Complete reference: AAA pattern, mock usage, behavior-focused testing, fixtures, parameterization, contamination prevention
- [Code Principles](shared/code_principles.md) - SOLID, DRY, KISS principles
- [Architecture Guidelines](shared/architecture_guidelines.md) - System boundaries

For debugging test failures, see:
- [Debug Guide](debug.md) - Root cause analysis for failing tests
