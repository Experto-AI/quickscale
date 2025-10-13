"""Pytest configuration for quickscale_core tests."""

import pytest


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture
def sample_project_config() -> dict[str, str]:
    """Provide sample project configuration dictionary for testing."""
    return {
        "project_name": "testproject",
        "author": "Test Author",
        "email": "test@example.com",
        "description": "A test Django project",
    }


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (end-to-end workflow)"
    )
