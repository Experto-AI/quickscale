# QuickScale Test Suite

This directory contains test code for the QuickScale project. The test suite is designed to be robust, deterministic, and maintainable.

## Test Structure

Tests are organized into the following directories:

- `tests/unit/`: Unit tests for individual components
- `tests/integration/`: Integration tests that test multiple components together
- `tests/__pycache__/`: Python cache files (automatically generated)
- `tests/conftest.py`: Common fixtures for all tests
- `tests/utils.py`: Utility functions for tests

## Running Tests

The simplest way to run tests is using the `run_tests.sh` script:

```bash
# Run unit tests only (default)
./run_tests.sh

# Run all tests (unit and integration)
./run_tests.sh --all

# Run with coverage report
./run_tests.sh --coverage

# Run tests in parallel
./run_tests.sh --parallel

# Run integration tests only
./run_tests.sh --integration
```

Alternatively, you can run pytest directly:

```bash
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest  # Run all tests
```

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

## Dependencies

The test suite requires these packages:

```
pytest
pytest-timeout
pytest-cov
pytest-xdist
pytest-mock
pytest-order
```

Install with:

```bash
pip install -r requirements-dev.txt
``` 