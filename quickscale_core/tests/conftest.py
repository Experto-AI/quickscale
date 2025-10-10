"""Pytest configuration for quickscale_core tests."""

import pytest


@pytest.fixture
def sample_project_name():
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture
def sample_project_config():
    """Provide sample project configuration for testing."""
    return {
        "project_name": "testproject",
        "author": "Test Author",
        "email": "test@example.com",
        "description": "A test Django project",
    }
