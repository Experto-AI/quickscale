"""Pytest configuration for quickscale_cli tests."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


# Prefer workspace source trees over any stale user-site installs.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _src_path in (
    _REPO_ROOT / "quickscale/src",
    _REPO_ROOT / "quickscale_core/src",
    _REPO_ROOT / "quickscale_cli/src",
):
    _src_path_str = str(_src_path)
    if _src_path_str in sys.path:
        sys.path.remove(_src_path_str)
    sys.path.insert(0, _src_path_str)

# Make module adapter packages importable so that managed-wiring regeneration
# (refresh_managed_adapters) can import quickscale_modules_{name}.adapter.
for _module_entry in sorted((_REPO_ROOT / "quickscale_modules").iterdir()):
    _module_src = _module_entry / "src"
    if _module_src.is_dir():
        _src_str = str(_module_src.resolve())
        if _src_str not in sys.path:
            sys.path.insert(0, _src_str)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Mock system dependency checks to always pass in tests."""
    from quickscale_cli.utils.dependency_utils import DependencyStatus

    monkeypatch.setenv("QUICKSCALE_SKIP_DEPENDENCY_CHECKS", "1")

    mock_deps = [
        DependencyStatus("Python", True, "3.13.0", True, "Runtime"),
        DependencyStatus("Poetry", True, "1.8.0", True, "Dependency management"),
        DependencyStatus("Git", True, "2.40.0", True, "Version control"),
        DependencyStatus("Docker", True, "24.0.0", True, "Containerization"),
        DependencyStatus("PostgreSQL", True, "18.0", True, "Database"),
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
