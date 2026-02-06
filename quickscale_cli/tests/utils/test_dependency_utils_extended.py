"""Extended tests for dependency_utils.py - covering missing subprocess/error paths."""

import os
import subprocess
from unittest.mock import MagicMock, patch


from quickscale_cli.utils.dependency_utils import (
    DependencyStatus,
    _should_skip_dependency_checks,
    _skipped_dependency,
    check_all_dependencies,
    check_docker_installed,
    check_git_installed,
    check_poetry_installed,
    check_postgresql_installed,
    verify_required_dependencies,
)


# ============================================================================
# _should_skip_dependency_checks
# ============================================================================


class TestShouldSkipDependencyChecks:
    """Tests for _should_skip_dependency_checks"""

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": ""}, clear=False)
    def test_empty_value(self):
        """Empty value returns False"""
        assert _should_skip_dependency_checks() is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "1"}, clear=False)
    def test_value_1(self):
        """Value '1' returns True"""
        assert _should_skip_dependency_checks() is True

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "true"}, clear=False)
    def test_value_true(self):
        """Value 'true' returns True"""
        assert _should_skip_dependency_checks() is True

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "YES"}, clear=False)
    def test_value_yes(self):
        """Value 'YES' returns True"""
        assert _should_skip_dependency_checks() is True

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "on"}, clear=False)
    def test_value_on(self):
        """Value 'on' returns True"""
        assert _should_skip_dependency_checks() is True

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "no"}, clear=False)
    def test_value_no(self):
        """Value 'no' returns False"""
        assert _should_skip_dependency_checks() is False

    @patch.dict(os.environ, {}, clear=False)
    def test_env_var_not_set(self):
        """Missing env var returns False"""
        os.environ.pop("QUICKSCALE_SKIP_DEPENDENCY_CHECKS", None)
        assert _should_skip_dependency_checks() is False


# ============================================================================
# _skipped_dependency
# ============================================================================


class TestSkippedDependency:
    """Tests for _skipped_dependency"""

    def test_basic_skip(self):
        """Basic skipped dependency without version env"""
        result = _skipped_dependency("Test", True, "Testing")
        assert result.name == "Test"
        assert result.installed is True
        assert result.version is None
        assert result.required is True

    @patch.dict(os.environ, {"MOCK_VERSION": "1.2.3"}, clear=False)
    def test_with_version_env(self):
        """Skipped dependency with version env set"""
        result = _skipped_dependency("Test", False, "Testing", "MOCK_VERSION")
        assert result.version == "1.2.3"

    def test_without_version_env(self):
        """Skipped dependency without version_env parameter"""
        result = _skipped_dependency("Test", True, "Purpose")
        assert result.version is None


# ============================================================================
# check_git_installed - subprocess error paths
# ============================================================================


class TestCheckGitInstalled:
    """Tests for check_git_installed subprocess error paths"""

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_git_subprocess_error(self, mock_run, mock_which):
        """Test when git --version raises SubprocessError"""
        mock_which.return_value = "/usr/bin/git"
        mock_run.side_effect = subprocess.SubprocessError("git error")
        result = check_git_installed()
        assert result.installed is False
        assert result.version is None

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_git_timeout(self, mock_run, mock_which):
        """Test when git --version times out"""
        mock_which.return_value = "/usr/bin/git"
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
        result = check_git_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    def test_git_not_found(self, mock_which):
        """Test when git binary not on PATH"""
        mock_which.return_value = None
        result = check_git_installed()
        assert result.installed is False
        assert result.version is None

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_git_file_not_found(self, mock_run, mock_which):
        """Test when git raises FileNotFoundError"""
        mock_which.return_value = "/usr/bin/git"
        mock_run.side_effect = FileNotFoundError("git not found")
        result = check_git_installed()
        assert result.installed is False


# ============================================================================
# check_docker_installed - compose v1/v2 paths
# ============================================================================


class TestCheckDockerInstalled:
    """Tests for check_docker_installed compose fallback paths"""

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_docker_with_compose_v2(self, mock_run, mock_which):
        """Test Docker with compose v2 plugin"""
        mock_which.return_value = "/usr/bin/docker"

        def side_effect(cmd, **kwargs):
            if cmd == ["docker", "--version"]:
                return MagicMock(
                    stdout="Docker version 24.0.6, build ed223bc", returncode=0
                )
            if cmd == ["docker", "compose", "version"]:
                return MagicMock(stdout="Docker Compose version v2.21.0", returncode=0)
            raise subprocess.SubprocessError("unexpected")

        mock_run.side_effect = side_effect
        result = check_docker_installed()
        assert result.installed is True
        assert result.version is not None

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_docker_with_compose_v1_fallback(self, mock_run, mock_which):
        """Test Docker falls back to docker-compose v1"""
        mock_which.return_value = "/usr/bin/docker"

        call_count = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if cmd == ["docker", "--version"]:
                return MagicMock(
                    stdout="Docker version 24.0.6, build ed223bc", returncode=0
                )
            if cmd == ["docker", "compose", "version"]:
                raise subprocess.SubprocessError("not found")
            if cmd == ["docker-compose", "--version"]:
                return MagicMock(stdout="docker-compose version 1.29.2", returncode=0)
            raise subprocess.SubprocessError("unexpected")

        mock_run.side_effect = side_effect
        result = check_docker_installed()
        assert result.installed is True

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_docker_no_compose(self, mock_run, mock_which):
        """Test Docker installed but no compose at all"""
        mock_which.return_value = "/usr/bin/docker"

        def side_effect(cmd, **kwargs):
            if cmd == ["docker", "--version"]:
                return MagicMock(
                    stdout="Docker version 24.0.6, build ed223bc", returncode=0
                )
            raise subprocess.SubprocessError("not found")

        mock_run.side_effect = side_effect
        result = check_docker_installed()
        assert result.installed is False
        assert "Compose not found" in result.purpose

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_docker_version_error(self, mock_run, mock_which):
        """Test when docker --version itself fails"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = subprocess.SubprocessError("docker error")
        result = check_docker_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    def test_docker_not_found(self, mock_which):
        """Test when docker binary not on PATH"""
        mock_which.return_value = None
        result = check_docker_installed()
        assert result.installed is False


# ============================================================================
# check_postgresql_installed - error paths
# ============================================================================


class TestCheckPostgresqlInstalled:
    """Tests for check_postgresql_installed error paths"""

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_psql_subprocess_error(self, mock_run, mock_which):
        """Test when psql --version raises SubprocessError"""
        mock_which.return_value = "/usr/bin/psql"
        mock_run.side_effect = subprocess.SubprocessError("psql error")
        result = check_postgresql_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_psql_timeout(self, mock_run, mock_which):
        """Test when psql --version times out"""
        mock_which.return_value = "/usr/bin/psql"
        mock_run.side_effect = subprocess.TimeoutExpired("psql", 5)
        result = check_postgresql_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    def test_psql_not_found(self, mock_which):
        """Test when psql not on PATH"""
        mock_which.return_value = None
        result = check_postgresql_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.shutil.which")
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_psql_success(self, mock_run, mock_which):
        """Test successful psql check"""
        mock_which.return_value = "/usr/bin/psql"
        mock_run.return_value = MagicMock(stdout="psql (PostgreSQL) 16.1", returncode=0)
        result = check_postgresql_installed()
        assert result.installed is True
        assert result.version == "16.1"


# ============================================================================
# check_all_dependencies / verify_required_dependencies
# ============================================================================


class TestCheckAllDependencies:
    """Tests for check_all_dependencies and verify_required_dependencies"""

    @patch("quickscale_cli.utils.dependency_utils.check_postgresql_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_docker_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_git_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_poetry_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_python_version")
    def test_all_installed(self, mock_py, mock_poetry, mock_git, mock_docker, mock_pg):
        """Test when all dependencies installed"""
        for mock_fn, name in [
            (mock_py, "Python"),
            (mock_poetry, "Poetry"),
            (mock_git, "Git"),
            (mock_docker, "Docker"),
            (mock_pg, "PostgreSQL"),
        ]:
            mock_fn.return_value = DependencyStatus(
                name=name, installed=True, version="1.0", required=True, purpose="test"
            )

        results = check_all_dependencies()
        assert len(results) == 5
        assert all(d.installed for d in results)

    @patch("quickscale_cli.utils.dependency_utils.check_all_dependencies")
    def test_verify_missing_required(self, mock_all):
        """Test verify_required_dependencies with missing required dep"""
        mock_all.return_value = [
            DependencyStatus("Python", True, "3.12", True, "test"),
            DependencyStatus("Poetry", False, None, True, "test"),
            DependencyStatus("Git", True, "2.0", False, "test"),
            DependencyStatus("Docker", True, "24.0", False, "test"),
            DependencyStatus("PostgreSQL", True, "16", False, "test"),
        ]

        ok, missing = verify_required_dependencies()
        assert ok is False, f"Expected False but got {ok}, missing={missing}"
        assert len(missing) == 1, (
            f"Expected 1 missing but got {len(missing)}: {missing}"
        )
        assert missing[0].name == "Poetry"

    @patch("quickscale_cli.utils.dependency_utils.check_postgresql_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_docker_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_git_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_poetry_installed")
    @patch("quickscale_cli.utils.dependency_utils.check_python_version")
    def test_verify_all_present(
        self, mock_py, mock_poetry, mock_git, mock_docker, mock_pg
    ):
        """Test verify_required_dependencies when all present"""
        for mock_fn, name in [
            (mock_py, "Python"),
            (mock_poetry, "Poetry"),
            (mock_git, "Git"),
            (mock_docker, "Docker"),
            (mock_pg, "PostgreSQL"),
        ]:
            mock_fn.return_value = DependencyStatus(name, True, "1.0", True, "test")

        ok, missing = verify_required_dependencies()
        assert ok is True
        assert len(missing) == 0


# ============================================================================
# check_poetry_installed - subprocess error paths
# ============================================================================


class TestCheckPoetryInstalled:
    """Tests for check_poetry_installed"""

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_poetry_success(self, mock_run):
        """Test successful poetry check"""
        mock_run.return_value = MagicMock(stdout="Poetry (version 1.8.3)", returncode=0)
        result = check_poetry_installed()
        assert result.installed is True
        assert "1.8.3" in result.version

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_poetry_not_found(self, mock_run):
        """Test when poetry command not found"""
        mock_run.side_effect = FileNotFoundError("poetry not found")
        result = check_poetry_installed()
        assert result.installed is False

    @patch.dict(os.environ, {"QUICKSCALE_SKIP_DEPENDENCY_CHECKS": "0"}, clear=False)
    @patch("quickscale_cli.utils.dependency_utils.subprocess.run")
    def test_poetry_timeout(self, mock_run):
        """Test when poetry --version times out"""
        mock_run.side_effect = subprocess.TimeoutExpired("poetry", 5)
        result = check_poetry_installed()
        assert result.installed is False
