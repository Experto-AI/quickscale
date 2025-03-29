"""Pytest configuration and fixtures for testing."""
import os
import sys
import pytest
from pathlib import Path

@pytest.fixture
def cli_runner(monkeypatch, tmp_path):
    """Fixture for testing CLI commands."""
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    # Create a test project structure
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    
    yield
    
    # Restore original directory
    os.chdir(original_dir)

@pytest.fixture
def mock_config_file(tmp_path):
    """Create a mock configuration file for testing."""
    config_file = tmp_path / "quickscale.yaml"
    config_file.write_text(
        "project:\n"
        "  name: test_project\n"
        "  path: ./test_project\n"
    )
    return config_file