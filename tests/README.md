# QuickScale Test Suite

This directory contains test code for the QuickScale project. The test suite is designed to be robust, deterministic, and maintainable.

## Test Structure

Tests are organized into the following directories:

### Core Test Categories
- `tests/unit/`: Unit tests for individual components
  - `tests/unit/commands/`: Command-line interface tests
  - `tests/unit/utils/`: Utility function tests
  - `tests/unit/django_components/`: Django component unit tests
    - `models/`: Django model tests
    - `admin/`: Django admin tests
    - `utils/`: Django utility tests
    - `template_tags/`: Template tag tests

- `tests/integration/`: Integration tests that test multiple components together
  - `tests/integration/django_apps/`: Django application integration tests
    - `stripe_integration/`: Stripe integration tests
    - `credit_system/`: Credit system integration tests
    - `user_management/`: User management integration tests
    - `admin_dashboard/`: Admin dashboard integration tests

- `tests/e2e/`: End-to-end tests that test the complete system
  - `tests/e2e/django_workflows/`: Django workflow E2E tests
    - `user_workflows/`: User authentication and profile workflows
    - `payment_workflows/`: Payment and subscription workflows
    - `admin_workflows/`: Admin management workflows

### Supporting Files
- `tests/__pycache__/`: Python cache files (automatically generated)
- `tests/conftest.py`: Common fixtures for all tests
- `tests/utils.py`: Utility functions for tests

## Running Tests

The simplest way to run tests is using the `run_tests.sh` script:

```bash
# Run unit tests only
./run_tests.sh --unit

# Run integration tests only
./run_tests.sh --integration

# Run end-to-end tests only
./run_tests.sh --e2e

# Run Django component tests only (unit + integration + e2e Django tests)
./run_tests.sh --django

# Run multiple test types
./run_tests.sh --unit --integration
./run_tests.sh --unit --integration --e2e

# Run all tests (default behavior when no flags specified)
./run_tests.sh

# Run with coverage report
./run_tests.sh --coverage

# Show only failed tests (for debugging)
./run_tests.sh --failures-only
./run_tests.sh -f

# Stop on first failure (for quick debugging)
./run_tests.sh --exitfirst --unit

# Combine options
./run_tests.sh --unit --integration --coverage
```

Alternatively, you can run pytest directly:

```bash
# Run by directory
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/e2e/

# Run by markers
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m e2e
python -m pytest -m django_component

# Run all tests
python -m pytest
```

## Test Types

### Unit Tests (`tests/unit/`)
Fast tests with no external dependencies. Test individual functions, classes, and modules in isolation.

- **Command tests**: Test CLI command functionality
- **Utility tests**: Test helper functions and utilities  
- **Django component tests**: Test individual Django models, admin configs, utilities, and template tags

### Integration Tests (`tests/integration/`)
Medium-speed tests with some external dependencies. Test how multiple components work together.

- **Django app integration**: Test interactions between Django apps, models, views, and services
- **Stripe integration**: Test Stripe webhook handling and payment processing
- **Credit system integration**: Test credit consumption and management workflows
- **User management integration**: Test authentication, authorization, and user workflows

### End-to-End Tests (`tests/e2e/`)
Slow, comprehensive tests that test the complete system with Docker. These test the full workflow from project creation to deployment.

- **Project lifecycle**: Test complete QuickScale project creation and management
- **Django workflows**: Test complete user journeys in generated Django applications
- **Payment workflows**: Test end-to-end payment and subscription processes
- **Admin workflows**: Test complete admin management processes

### Django Component Tests
Tests marked with `@pytest.mark.django_component` validate Django application functionality:

- **Models**: Test Django ORM operations, relationships, and model methods
- **Views**: Test HTTP request/response handling and form processing
- **Admin**: Test Django admin interface customizations
- **Utils**: Test Django utility functions and helpers
- **Template Tags**: Test custom template tag functionality

**Key difference**: 
- **Generator tests** (unit/integration/e2e without django_component marker) test the **QuickScale generator itself**
- **Django component tests** test the **generated Django application functionality**

## Test Fixtures

The test suite uses pytest fixtures for setting up test environments. Key fixtures include:

- `cli_runner`: For testing CLI commands in an isolated directory
- `mock_config_file`: For creating test configuration files
- `wait_for_service`: For waiting for services to be ready in integration tests
- `real_project_fixture`: For creating a real QuickScale project for integration tests
- `mock_docker`: For mocking Docker-related functionality in unit tests
- `retry`: For retrying flaky tests

## Writing New Tests

When adding new tests, follow these guidelines:

1. **Test Isolation**: Each test should be independent and not rely on state from other tests
2. **Dynamic Waiting**: Use the `wait_for_service` fixture instead of `time.sleep()`
3. **Resource Cleanup**: Ensure all resources are cleaned up in fixture teardowns
4. **Error Handling**: Add proper error handling for external dependencies
5. **Test Documentation**: Add docstrings to explain what each test is checking

### Example:

```python
def test_example_feature(cli_runner, wait_for_service):
    """Test that the example feature works correctly."""
    # Setup
    result = run_quickscale_command('setup', ['example'])
    assert result.returncode == 0
    
    # Wait for service to be ready
    service_name = "example_service"
    assert wait_for_docker_service(service_name, timeout=30), "Service not running"
    
    # Test functionality
    result = run_quickscale_command('example', ['command'])
    assert "Expected output" in result.stdout
    assert result.returncode == 0
```

## Test Stability Features

The test system includes several features for improving stability:

1. **Deterministic Test Order**: Critical tests are ordered using `pytest.mark.order`
2. **Dynamic Waiting**: Tests use polling instead of fixed sleep times
3. **Proper Resource Isolation**: Each test runs in an isolated environment
4. **Robust Cleanup**: Tests clean up resources even if they fail
5. **Retry Mechanism**: Flaky tests can be retried automatically
6. **Timeout Handling**: Tests have proper timeouts to avoid hanging
7. **Parallel Test Support**: Tests can run in parallel where appropriate

