"""Tests for system dependency checking utilities."""

from unittest.mock import Mock, patch

import pytest

from quickscale_cli.utils.dependency_utils import (
    DependencyStatus,
    check_all_dependencies,
    check_docker_installed,
    check_git_installed,
    check_poetry_installed,
    check_postgresql_installed,
    check_python_version,
    verify_required_dependencies,
)


@pytest.fixture(autouse=True)
def enable_dependency_checks(monkeypatch):
    """Enable dependency checks for these tests by clearing the skip flag."""
    monkeypatch.delenv("QUICKSCALE_SKIP_DEPENDENCY_CHECKS", raising=False)


class TestCheckPythonVersion:
    """Tests for check_python_version function."""

    def test_python_version_meets_requirement(self):
        """Test Python version check when requirement is met."""
        # Current test environment should have Python 3.11+
        status = check_python_version()

        assert status.name == "Python"
        assert status.installed is True
        assert status.version is not None
        assert status.required is True
        assert "Runtime" in status.purpose

    def test_python_version_format(self):
        """Test Python version format is correct."""
        status = check_python_version()

        # Version should be in format "X.Y.Z"
        assert status.version is not None
        parts = status.version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestCheckPoetryInstalled:
    """Tests for check_poetry_installed function."""

    def test_poetry_installed(self):
        """Test when Poetry is installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Poetry (version 1.7.0)",
            )

            status = check_poetry_installed()

            assert status.name == "Poetry"
            assert status.installed is True
            assert status.version == "1.7.0"
            assert status.required is True
            assert "Dependency management" in status.purpose

    def test_poetry_not_installed(self):
        """Test when Poetry is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            status = check_poetry_installed()

            assert status.name == "Poetry"
            assert status.installed is False
            assert status.version is None
            assert status.required is True

    def test_poetry_check_timeout(self):
        """Test when Poetry check times out."""
        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("poetry", 5)

            status = check_poetry_installed()

            assert status.installed is False


class TestCheckGitInstalled:
    """Tests for check_git_installed function."""

    def test_git_installed(self):
        """Test when Git is installed."""
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/git"
            mock_run.return_value = Mock(
                returncode=0,
                stdout="git version 2.39.0",
            )

            status = check_git_installed()

            assert status.name == "Git"
            assert status.installed is True
            assert status.version == "2.39.0"
            assert status.required is False
            assert "Version control" in status.purpose

    def test_git_not_installed(self):
        """Test when Git is not installed."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            status = check_git_installed()

            assert status.name == "Git"
            assert status.installed is False
            assert status.version is None
            assert status.required is False


class TestCheckDockerInstalled:
    """Tests for check_docker_installed function."""

    def test_docker_installed(self):
        """Test when Docker is installed."""
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/docker"
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Docker version 24.0.5, build ced0996",
            )

            status = check_docker_installed()

            assert status.name == "Docker"
            assert status.installed is True
            assert status.version == "24.0.5"
            assert status.required is False
            assert "Containerized development" in status.purpose

    def test_docker_not_installed(self):
        """Test when Docker is not installed."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            status = check_docker_installed()

            assert status.name == "Docker"
            assert status.installed is False


class TestCheckPostgreSQLInstalled:
    """Tests for check_postgresql_installed function."""

    def test_postgresql_installed(self):
        """Test when PostgreSQL client is installed."""
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/psql"
            mock_run.return_value = Mock(
                returncode=0,
                stdout="psql (PostgreSQL) 16.0",
            )

            status = check_postgresql_installed()

            assert status.name == "PostgreSQL"
            assert status.installed is True
            assert status.version == "16.0"
            assert status.required is False
            assert "Database server" in status.purpose

    def test_postgresql_not_installed(self):
        """Test when PostgreSQL client is not installed."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            status = check_postgresql_installed()

            assert status.name == "PostgreSQL"
            assert status.installed is False


class TestCheckAllDependencies:
    """Tests for check_all_dependencies function."""

    def test_returns_all_dependency_statuses(self):
        """Test that all dependencies are checked."""
        statuses = check_all_dependencies()

        assert len(statuses) == 5
        names = [s.name for s in statuses]
        assert "Python" in names
        assert "Poetry" in names
        assert "Git" in names
        assert "Docker" in names
        assert "PostgreSQL" in names


class TestVerifyRequiredDependencies:
    """Tests for verify_required_dependencies function."""

    def test_all_required_present(self):
        """Test when all required dependencies are present."""
        with patch(
            "quickscale_cli.utils.dependency_utils.check_all_dependencies"
        ) as mock_check:
            mock_check.return_value = [
                DependencyStatus("Python", True, "3.11.0", True, "Runtime"),
                DependencyStatus("Poetry", True, "1.7.0", True, "Dependency mgmt"),
                DependencyStatus("Git", False, None, False, "Version control"),
            ]

            all_present, missing = verify_required_dependencies()

            assert all_present is True
            assert missing == []

    def test_required_missing(self):
        """Test when required dependencies are missing."""
        with patch(
            "quickscale_cli.utils.dependency_utils.check_all_dependencies"
        ) as mock_check:
            poetry_missing = DependencyStatus(
                "Poetry", False, None, True, "Dependency mgmt"
            )
            mock_check.return_value = [
                DependencyStatus("Python", True, "3.11.0", True, "Runtime"),
                poetry_missing,
                DependencyStatus("Git", False, None, False, "Version control"),
            ]

            all_present, missing = verify_required_dependencies()

            assert all_present is False
            assert len(missing) == 1
            assert missing[0] == poetry_missing
