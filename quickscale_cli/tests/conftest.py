"""Pytest configuration for quickscale_cli tests."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock system dependency checks to always pass in tests."""
    from quickscale_cli.utils.dependency_utils import DependencyStatus

    mock_deps = [
        DependencyStatus("Python", True, "3.12.0", True, "Runtime"),
        DependencyStatus("Poetry", True, "1.8.0", True, "Dependency management"),
        DependencyStatus("Git", True, "2.40.0", True, "Version control"),
        DependencyStatus("Docker", True, "24.0.0", True, "Containerization"),
        DependencyStatus("PostgreSQL", True, "15.0", True, "Database"),
    ]

    with patch(
        "quickscale_cli.utils.dependency_utils.check_all_dependencies",
        return_value=mock_deps,
    ):
        yield


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as full end-to-end test (requires Docker)"
    )
