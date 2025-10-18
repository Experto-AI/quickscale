"""Pytest configuration for quickscale_cli tests."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: mark test as full end-to-end test (requires Docker)")
