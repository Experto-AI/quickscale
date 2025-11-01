"""Tests for railway_utils module."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from quickscale_cli.utils.railway_utils import (
    _compare_versions,
    check_poetry_lock_consistency,
    check_railway_cli_version,
    check_uncommitted_changes,
    fix_poetry_lock,
    generate_django_secret_key,
    get_app_service_name,
    get_deployment_url,
    get_railway_cli_version,
    get_railway_project_info,
    install_railway_cli,
    is_npm_installed,
    is_railway_authenticated,
    is_railway_cli_installed,
    is_railway_project_initialized,
    link_database_to_service,
    login_railway_cli_browserless,
    run_railway_command,
    set_railway_variable,
    set_railway_variables_batch,
    upgrade_railway_cli,
    verify_dockerfile,
    verify_railway_dependencies,
    verify_railway_json,
)


class TestIsRailwayCliInstalled:
    """Tests for is_railway_cli_installed function."""

    def test_railway_cli_installed_returns_true(self):
        """Test that Railway CLI installed returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            assert is_railway_cli_installed() is True
            mock_run.assert_called_once()

    def test_railway_cli_not_found_returns_false(self):
        """Test that Railway CLI not found returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert is_railway_cli_installed() is False

    def test_railway_cli_timeout_returns_false(self):
        """Test that Railway CLI timeout returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("railway", 5)
            assert is_railway_cli_installed() is False


class TestCompareVersions:
    """Tests for _compare_versions helper function."""

    def test_version1_greater_than_version2(self):
        """Test that comparison returns 1 when version1 > version2."""
        assert _compare_versions("3.5.0", "3.0.0") == 1
        assert _compare_versions("4.0.0", "3.9.9") == 1
        assert _compare_versions("3.0.1", "3.0.0") == 1

    def test_version1_less_than_version2(self):
        """Test that comparison returns -1 when version1 < version2."""
        assert _compare_versions("3.0.0", "3.5.0") == -1
        assert _compare_versions("2.9.9", "3.0.0") == -1
        assert _compare_versions("3.0.0", "3.0.1") == -1

    def test_versions_equal(self):
        """Test that comparison returns 0 when versions are equal."""
        assert _compare_versions("3.0.0", "3.0.0") == 0
        assert _compare_versions("4.1.5", "4.1.5") == 0

    def test_major_version_difference(self):
        """Test comparison with major version differences."""
        assert _compare_versions("5.0.0", "4.9.9") == 1
        assert _compare_versions("3.0.0", "4.0.0") == -1

    def test_minor_version_difference(self):
        """Test comparison with minor version differences."""
        assert _compare_versions("3.5.0", "3.4.9") == 1
        assert _compare_versions("3.3.0", "3.4.0") == -1

    def test_patch_version_difference(self):
        """Test comparison with patch version differences."""
        assert _compare_versions("3.0.2", "3.0.1") == 1
        assert _compare_versions("3.0.1", "3.0.2") == -1


class TestCheckRailwayCliVersion:
    """Tests for check_railway_cli_version function."""

    def test_version_meets_minimum(self):
        """Test that version check passes when CLI version meets minimum."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="railway version 3.5.0")
            assert check_railway_cli_version("3.0.0") is True

    def test_version_below_minimum(self):
        """Test that version check fails when CLI version below minimum."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="railway version 2.5.0")
            assert check_railway_cli_version("3.0.0") is False

    def test_version_exact_match(self):
        """Test that version check passes for exact version match."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="railway version 3.0.0")
            assert check_railway_cli_version("3.0.0") is True

    def test_version_check_fails_on_error(self):
        """Test that version check fails when Railway CLI not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert check_railway_cli_version("3.0.0") is False

    def test_version_output_malformed(self):
        """Test that version check fails with malformed output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="invalid output")
            assert check_railway_cli_version("3.0.0") is False


class TestIsRailwayAuthenticated:
    """Tests for is_railway_authenticated function."""

    def test_authenticated_returns_true(self):
        """Test that authenticated user returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            assert is_railway_authenticated() is True

    def test_not_authenticated_returns_false(self):
        """Test that non-authenticated user returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "railway")
            assert is_railway_authenticated() is False

    def test_railway_not_found_returns_false(self):
        """Test that Railway CLI not found returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert is_railway_authenticated() is False


class TestIsRailwayProjectInitialized:
    """Tests for is_railway_project_initialized function."""

    def test_project_initialized_returns_true(self, tmp_path, monkeypatch):
        """Test that initialized project returns True."""
        monkeypatch.chdir(tmp_path)
        railway_config = tmp_path / ".railway"
        railway_config.mkdir()

        assert is_railway_project_initialized() is True

    def test_project_not_initialized_returns_false(self, tmp_path, monkeypatch):
        """Test that non-initialized project returns False."""
        monkeypatch.chdir(tmp_path)

        assert is_railway_project_initialized() is False


class TestGetRailwayProjectInfo:
    """Tests for get_railway_project_info function."""

    def test_returns_none_when_not_initialized(self, tmp_path, monkeypatch):
        """Test that function returns None when project not initialized."""
        monkeypatch.chdir(tmp_path)

        result = get_railway_project_info()
        assert result is None

    def test_returns_project_info_when_initialized(self, tmp_path, monkeypatch):
        """Test that function returns project info when initialized."""
        monkeypatch.chdir(tmp_path)
        railway_config = tmp_path / ".railway"
        railway_config.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Project: test-project")
            result = get_railway_project_info()

            assert result is not None
            assert "status" in result
            assert "Project: test-project" in result["status"]

    def test_returns_none_on_command_failure(self, tmp_path, monkeypatch):
        """Test that function returns None when Railway command fails."""
        monkeypatch.chdir(tmp_path)
        railway_config = tmp_path / ".railway"
        railway_config.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "railway")
            result = get_railway_project_info()

            assert result is None


class TestRunRailwayCommand:
    """Tests for run_railway_command function."""

    def test_successful_command_execution(self):
        """Test successful Railway command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="success")
            result = run_railway_command(["status"])

            assert result.returncode == 0
            assert result.stdout == "success"

    def test_interactive_command_execution(self):
        """Test interactive Railway command execution without output capture."""
        with patch("quickscale_cli.utils.railway_utils.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = run_railway_command(["init"], interactive=True)

            assert result.returncode == 0
            # Verify subprocess.run was called without capture_output
            call_kwargs = mock_run.call_args[1]
            assert (
                "capture_output" not in call_kwargs
                or call_kwargs["capture_output"] is False
            )

    def test_command_timeout_raises_error(self):
        """Test that timeout raises TimeoutError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("railway", 60)

            with pytest.raises(TimeoutError, match="Railway command timed out"):
                run_railway_command(["status"])

    def test_railway_not_found_raises_error(self):
        """Test that FileNotFoundError is raised when Railway CLI missing."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(FileNotFoundError, match="Railway CLI not found"):
                run_railway_command(["status"])

    def test_command_with_custom_timeout(self):
        """Test Railway command with custom timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="success")
            result = run_railway_command(["status"], timeout=120)

            assert result.returncode == 0
            # Verify timeout was passed correctly
            assert mock_run.call_args[1]["timeout"] == 120

    def test_failed_command_returns_error_code(self):
        """Test that failed command returns non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Error message"
            )
            result = run_railway_command(["invalid-command"])

            assert result.returncode == 1
            assert result.stderr == "Error message"


class TestSetRailwayVariable:
    """Tests for set_railway_variable function."""

    def test_successful_variable_set(self):
        """Test successful environment variable setting."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = set_railway_variable("KEY", "value")

            assert result is True

    def test_successful_variable_set_with_service(self):
        """Test successful environment variable setting with service parameter."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = set_railway_variable("KEY", "value", service="my-service")

            assert result is True
            # Verify the service parameter was included in the command
            call_args = mock_run.call_args[0][0]
            assert "--service" in call_args
            assert "my-service" in call_args

    def test_failed_variable_set(self):
        """Test failed environment variable setting."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            result = set_railway_variable("KEY", "value")

            assert result is False

    def test_exception_during_variable_set(self):
        """Test that exceptions are handled gracefully."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unknown error")
            result = set_railway_variable("KEY", "value")

            assert result is False


class TestSetRailwayVariablesBatch:
    """Tests for set_railway_variables_batch function."""

    def test_successful_batch_set(self):
        """Test successful batch environment variable setting."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            variables = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
            success, failed = set_railway_variables_batch(variables)

            assert success is True
            assert failed == []
            # Verify all variables were included in single command
            call_args = mock_run.call_args[0][0]
            assert "KEY1=value1" in call_args
            assert "KEY2=value2" in call_args
            assert "KEY3=value3" in call_args

    def test_successful_batch_set_with_service(self):
        """Test successful batch environment variable setting with service parameter."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            variables = {"KEY1": "value1", "KEY2": "value2"}
            success, failed = set_railway_variables_batch(
                variables, service="my-service"
            )

            assert success is True
            assert failed == []
            # Verify the service parameter was included
            call_args = mock_run.call_args[0][0]
            assert "--service" in call_args
            assert "my-service" in call_args

    def test_empty_variables_dict(self):
        """Test batch set with empty variables dictionary."""
        success, failed = set_railway_variables_batch({})

        assert success is True
        assert failed == []

    def test_failed_batch_set_falls_back_to_individual(self):
        """Test that failed batch set falls back to individual variable setting."""
        with patch("subprocess.run") as mock_run:
            # First call (batch) fails, subsequent calls (individual) succeed
            mock_run.side_effect = [
                Exception("Batch failed"),  # Batch attempt fails
                Mock(returncode=0),  # KEY1 individual set succeeds
                Mock(returncode=0),  # KEY2 individual set succeeds
            ]
            variables = {"KEY1": "value1", "KEY2": "value2"}
            success, failed = set_railway_variables_batch(variables)

            assert success is True
            assert failed == []
            # Verify fallback occurred (3 calls: 1 batch + 2 individual)
            assert mock_run.call_count == 3

    def test_fallback_with_partial_failure(self):
        """Test fallback when some individual variables fail to set."""
        with patch("subprocess.run") as mock_run:
            # First call (batch) fails, then individual calls have mixed results
            mock_run.side_effect = [
                Exception("Batch failed"),  # Batch attempt fails
                Mock(returncode=0),  # KEY1 succeeds
                Mock(returncode=1),  # KEY2 fails
                Mock(returncode=0),  # KEY3 succeeds
            ]
            variables = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
            success, failed = set_railway_variables_batch(variables)

            assert success is False
            assert "KEY2" in failed
            assert len(failed) == 1

    def test_batch_set_single_variable(self):
        """Test batch set with single variable."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            variables = {"SECRET_KEY": "my-secret"}
            success, failed = set_railway_variables_batch(variables)

            assert success is True
            assert failed == []
            call_args = mock_run.call_args[0][0]
            assert "SECRET_KEY=my-secret" in call_args

    def test_batch_set_with_special_characters(self):
        """Test batch set with special characters in values."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            variables = {
                "SECRET_KEY": "django-insecure-!@#$%^&*()",
                "ALLOWED_HOSTS": "app1.com,app2.com,app3.com",
            }
            success, failed = set_railway_variables_batch(variables)

            assert success is True
            assert failed == []

    def test_batch_returns_false_on_failure(self):
        """Test that batch returns False when Railway command fails with non-zero return code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            variables = {"KEY1": "value1"}

            success, failed = set_railway_variables_batch(variables)

            # When batch command fails with non-zero return code, it returns False
            # with empty failed list. The fallback only occurs on exceptions
            assert success is False
            assert failed == []


class TestGenerateDjangoSecretKey:
    """Tests for generate_django_secret_key function."""

    def test_generates_valid_secret_key(self):
        """Test that function generates valid Django secret key."""
        secret_key = generate_django_secret_key()

        assert isinstance(secret_key, str)
        assert len(secret_key) >= 50

    def test_generates_key_with_django(self):
        """Test key generation when Django is available."""
        # This test verifies the function works when Django is available
        # Since Django may or may not be installed in the test environment,
        # we just verify the function returns a valid key
        secret_key = generate_django_secret_key()

        assert isinstance(secret_key, str)
        assert len(secret_key) >= 50
        # Verify it only contains valid characters for a Django secret key
        import string

        valid_chars = string.ascii_letters + string.digits + string.punctuation
        assert all(c in valid_chars for c in secret_key)

    def test_fallback_without_django(self):
        """Test fallback implementation when Django not available."""
        # Mock the Django import to fail, triggering fallback
        import sys

        # Temporarily remove django from sys.modules if present
        django_module = sys.modules.pop("django.core.management.utils", None)

        try:
            # Reload the module to trigger ImportError path
            import importlib

            from quickscale_cli.utils import railway_utils

            importlib.reload(railway_utils)

            secret_key = railway_utils.generate_django_secret_key()

            assert isinstance(secret_key, str)
            assert len(secret_key) == 50
        finally:
            # Restore django module if it was present
            if django_module is not None:
                sys.modules["django.core.management.utils"] = django_module


class TestGetDeploymentUrl:
    """Tests for get_deployment_url function."""

    def test_extracts_url_from_status(self):
        """Test URL extraction from Railway status output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Deployment: https://myapp.railway.app",
            )
            url = get_deployment_url()

            assert url == "https://myapp.railway.app"

    def test_extracts_url_with_service_parameter(self):
        """Test URL extraction with service parameter (kept for compatibility)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Deployment: https://myapp.railway.app",
            )
            # Service parameter is kept for backwards compatibility but not used
            url = get_deployment_url(service="app")

            assert url == "https://myapp.railway.app"
            # Note: Railway CLI v4's status command does not accept --service flag
            call_args = mock_run.call_args[0][0]
            assert "status" in call_args
            assert "--service" not in call_args

    def test_returns_none_when_no_url(self):
        """Test that function returns None when no URL in output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="No deployment found")
            url = get_deployment_url()

            assert url is None

    def test_returns_none_on_command_failure(self):
        """Test that function returns None when command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")
            url = get_deployment_url()

            assert url is None

    def test_returns_none_on_exception(self):
        """Test that function returns None when exception occurs."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Error")
            url = get_deployment_url()

            assert url is None


class TestGenerateRailwayDomain:
    """Tests for generate_railway_domain function."""

    def test_extracts_domain_with_regex_match(self):
        """Test domain extraction using regex pattern match."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Generated domain: https://myapp-production-abc123.up.railway.app",
            )

            from quickscale_cli.utils.railway_utils import generate_railway_domain

            domain = generate_railway_domain("my-service")

            assert domain == "https://myapp-production-abc123.up.railway.app"

    def test_extracts_domain_when_output_is_url(self):
        """Test domain extraction when output is just the URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="https://myapp.up.railway.app",
            )

            from quickscale_cli.utils.railway_utils import generate_railway_domain

            domain = generate_railway_domain("my-service")

            assert domain == "https://myapp.up.railway.app"

    def test_returns_none_when_no_domain_found(self):
        """Test returns None when no domain in output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="No domain generated",
            )

            from quickscale_cli.utils.railway_utils import generate_railway_domain

            domain = generate_railway_domain("my-service")

            assert domain is None

    def test_returns_none_on_command_failure(self):
        """Test returns None when Railway command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
            )

            from quickscale_cli.utils.railway_utils import generate_railway_domain

            domain = generate_railway_domain("my-service")

            assert domain is None

    def test_returns_none_on_exception(self):
        """Test returns None when exception occurs."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Error")

            from quickscale_cli.utils.railway_utils import generate_railway_domain

            domain = generate_railway_domain("my-service")

            assert domain is None


class TestGetAppServiceName:
    """Tests for get_app_service_name function."""

    def test_returns_project_name_when_provided(self):
        """Test that function returns project name when provided."""
        result = get_app_service_name("myproject")

        assert result == "myproject"

    def test_returns_current_directory_name_as_fallback(self, tmp_path, monkeypatch):
        """Test that function returns current directory name when no project name."""
        # Create directory first, then change to it
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        result = get_app_service_name()

        assert result == "test_project"


class TestIsNpmInstalled:
    """Tests for is_npm_installed function."""

    def test_npm_installed_returns_true(self):
        """Test that npm installed returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            assert is_npm_installed() is True
            mock_run.assert_called_once()

    def test_npm_not_found_returns_false(self):
        """Test that npm not found returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert is_npm_installed() is False

    def test_npm_timeout_returns_false(self):
        """Test that npm timeout returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("npm", 5)
            assert is_npm_installed() is False


class TestGetRailwayCliVersion:
    """Tests for get_railway_cli_version function."""

    def test_returns_version_string(self):
        """Test that function returns version string."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="railway version 4.1.5")
            result = get_railway_cli_version()
            assert result == "4.1.5"

    def test_returns_none_when_not_installed(self):
        """Test that function returns None when Railway CLI not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = get_railway_cli_version()
            assert result is None

    def test_returns_none_with_malformed_output(self):
        """Test that function returns None with malformed output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="invalid")
            result = get_railway_cli_version()
            assert result is None


class TestInstallRailwayCli:
    """Tests for install_railway_cli function."""

    def test_successful_installation(self):
        """Test successful Railway CLI installation."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = install_railway_cli()
            assert result is True
            mock_run.assert_called_once()

    def test_failed_installation(self):
        """Test failed Railway CLI installation."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            result = install_railway_cli()
            assert result is False

    def test_installation_timeout(self):
        """Test Railway CLI installation timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("npm", 180)
            result = install_railway_cli()
            assert result is False


class TestUpgradeRailwayCli:
    """Tests for upgrade_railway_cli function."""

    def test_successful_upgrade(self):
        """Test successful Railway CLI upgrade."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = upgrade_railway_cli()
            assert result is True
            mock_run.assert_called_once()

    def test_failed_upgrade(self):
        """Test failed Railway CLI upgrade."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            result = upgrade_railway_cli()
            assert result is False

    def test_upgrade_timeout(self):
        """Test Railway CLI upgrade timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("npm", 180)
            result = upgrade_railway_cli()
            assert result is False


class TestLoginRailwayCliBrowserless:
    """Tests for login_railway_cli_browserless function."""

    def test_successful_login(self):
        """Test successful Railway CLI login."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = login_railway_cli_browserless()
            assert result is True

    def test_failed_login(self):
        """Test failed Railway CLI login."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            result = login_railway_cli_browserless()
            assert result is False

    def test_login_timeout(self):
        """Test Railway CLI login timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("railway", 300)
            result = login_railway_cli_browserless()
            assert result is False


class TestCheckUncommittedChanges:
    """Tests for check_uncommitted_changes function."""

    def test_has_uncommitted_changes(self):
        """Test detection of uncommitted changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout=" M file1.py\n?? file2.py"
            )
            has_changes, output = check_uncommitted_changes()
            assert has_changes is True
            assert "file1.py" in output

    def test_no_uncommitted_changes(self):
        """Test no uncommitted changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            has_changes, output = check_uncommitted_changes()
            assert has_changes is False
            assert output == ""

    def test_git_not_available(self):
        """Test when git is not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            has_changes, output = check_uncommitted_changes()
            assert has_changes is False
            assert output == ""


class TestVerifyRailwayJson:
    """Tests for verify_railway_json function."""

    def test_valid_railway_json(self, tmp_path, monkeypatch):
        """Test valid railway.json file."""
        monkeypatch.chdir(tmp_path)
        railway_json = tmp_path / "railway.json"
        railway_json.write_text(
            '{"$schema": "https://railway.app/railway.schema.json"}'
        )

        is_valid, error_msg = verify_railway_json()
        assert is_valid is True
        assert error_msg == ""

    def test_missing_railway_json(self, tmp_path, monkeypatch):
        """Test missing railway.json file."""
        monkeypatch.chdir(tmp_path)

        is_valid, error_msg = verify_railway_json()
        assert is_valid is False
        assert "not found" in error_msg

    def test_invalid_railway_json(self, tmp_path, monkeypatch):
        """Test invalid railway.json file."""
        monkeypatch.chdir(tmp_path)
        railway_json = tmp_path / "railway.json"
        railway_json.write_text("invalid json {")

        is_valid, error_msg = verify_railway_json()
        assert is_valid is False
        assert "not valid JSON" in error_msg

    def test_railway_json_read_error(self, tmp_path, monkeypatch):
        """Test error reading railway.json file."""
        monkeypatch.chdir(tmp_path)
        railway_json = tmp_path / "railway.json"
        railway_json.write_text('{"valid": "json"}')

        # Mock open to raise a generic exception (e.g., permission denied)
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            is_valid, error_msg = verify_railway_json()
            assert is_valid is False
            assert "Error reading railway.json" in error_msg
            assert "Permission denied" in error_msg


class TestVerifyDockerfile:
    """Tests for verify_dockerfile function."""

    def test_dockerfile_exists(self, tmp_path, monkeypatch):
        """Test Dockerfile exists."""
        monkeypatch.chdir(tmp_path)
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12")

        exists, error_msg = verify_dockerfile()
        assert exists is True
        assert error_msg == ""

    def test_dockerfile_missing(self, tmp_path, monkeypatch):
        """Test Dockerfile missing."""
        monkeypatch.chdir(tmp_path)

        exists, error_msg = verify_dockerfile()
        assert exists is False
        assert "not found" in error_msg


class TestVerifyRailwayDependencies:
    """Tests for verify_railway_dependencies function."""

    def test_all_dependencies_present(self, tmp_path, monkeypatch):
        """Test all required dependencies are present."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python = "^3.12"
gunicorn = "^21.0"
psycopg2-binary = "^2.9"
dj-database-url = "^2.1"
whitenoise = "^6.6"
        """
        )

        all_present, missing = verify_railway_dependencies()
        assert all_present is True
        assert missing == []

    def test_missing_dependencies(self, tmp_path, monkeypatch):
        """Test missing required dependencies."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.poetry.dependencies]
python = "^3.12"
gunicorn = "^21.0"
        """
        )

        all_present, missing = verify_railway_dependencies()
        assert all_present is False
        assert "psycopg2-binary" in missing
        assert "dj-database-url" in missing
        assert "whitenoise" in missing

    def test_pyproject_missing(self, tmp_path, monkeypatch):
        """Test pyproject.toml missing."""
        monkeypatch.chdir(tmp_path)

        all_present, missing = verify_railway_dependencies()
        assert all_present is False
        assert len(missing) == 1
        assert "not found" in missing[0]

    def test_pyproject_read_error(self, tmp_path, monkeypatch):
        """Test error reading pyproject.toml file."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')

        # Mock open to raise a generic exception (e.g., permission denied)
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            all_present, missing = verify_railway_dependencies()
            assert all_present is False
            assert len(missing) == 1
            assert "Error reading pyproject.toml" in missing[0]
            assert "Permission denied" in missing[0]


class TestCheckPoetryLockConsistency:
    """Tests for check_poetry_lock_consistency function."""

    def test_consistent_lock_file(self, tmp_path, monkeypatch):
        """Test poetry.lock is consistent with pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')
        poetry_lock = tmp_path / "poetry.lock"
        poetry_lock.write_text("")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            is_consistent, message = check_poetry_lock_consistency()

            assert is_consistent is True
            assert "consistent" in message.lower()

    def test_inconsistent_lock_file(self, tmp_path, monkeypatch):
        """Test poetry.lock is inconsistent with pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')
        poetry_lock = tmp_path / "poetry.lock"
        poetry_lock.write_text("")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            is_consistent, message = check_poetry_lock_consistency()

            assert is_consistent is False
            assert "inconsistent" in message.lower()

    def test_missing_pyproject(self, tmp_path, monkeypatch):
        """Test pyproject.toml not found."""
        monkeypatch.chdir(tmp_path)

        is_consistent, message = check_poetry_lock_consistency()
        assert is_consistent is False
        assert "not found" in message.lower()

    def test_missing_poetry_lock(self, tmp_path, monkeypatch):
        """Test poetry.lock not found."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')

        is_consistent, message = check_poetry_lock_consistency()
        assert is_consistent is False
        assert "not found" in message.lower()
        assert "poetry lock" in message.lower()

    def test_poetry_not_available(self, tmp_path, monkeypatch):
        """Test when poetry command is not available."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')
        poetry_lock = tmp_path / "poetry.lock"
        poetry_lock.write_text("")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            is_consistent, message = check_poetry_lock_consistency()

            # Should return True with a message indicating poetry not found
            assert is_consistent is True
            assert "unable to verify" in message.lower()

    def test_poetry_timeout(self, tmp_path, monkeypatch):
        """Test when poetry check times out."""
        monkeypatch.chdir(tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.12"')
        poetry_lock = tmp_path / "poetry.lock"
        poetry_lock.write_text("")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("poetry", 10)
            is_consistent, message = check_poetry_lock_consistency()

            # Should return True with a message indicating unable to verify
            assert is_consistent is True
            assert "unable to verify" in message.lower()


class TestFixPoetryLock:
    """Tests for fix_poetry_lock function."""

    def test_successful_fix(self):
        """Test successful poetry lock fix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            success, message = fix_poetry_lock()

            assert success is True
            assert "updated successfully" in message.lower()
            mock_run.assert_called_once()

    def test_failed_fix(self):
        """Test failed poetry lock fix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="Error message")
            success, message = fix_poetry_lock()

            assert success is False
            assert "failed" in message.lower()

    def test_poetry_not_found(self):
        """Test when poetry is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            success, message = fix_poetry_lock()

            assert success is False
            assert "failed to run" in message.lower()

    def test_poetry_lock_timeout(self):
        """Test when poetry lock times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("poetry", 60)
            success, message = fix_poetry_lock()

            assert success is False
            assert "timed out" in message.lower()

    def test_subprocess_error(self):
        """Test when subprocess error occurs."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Error")
            success, message = fix_poetry_lock()

            assert success is False
            assert "failed to run" in message.lower()


class TestLinkDatabaseToService:
    """Tests for link_database_to_service function."""

    def test_successful_link_with_postgres_name(self):
        """Test successful DATABASE_URL link using Postgres service name."""
        with patch(
            "quickscale_cli.utils.railway_utils.run_railway_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            success, message = link_database_to_service("myapp")

            assert success is True
            assert "linked successfully" in message.lower()
            # Verify the correct reference format was used
            mock_run.assert_called_once_with(
                [
                    "variables",
                    "--set",
                    "DATABASE_URL=${{Postgres.DATABASE_URL}}",
                    "--service",
                    "myapp",
                ],
                timeout=30,
            )

    def test_fallback_to_postgresql_name(self):
        """Test fallback to PostgreSQL service name when Postgres fails."""
        with patch(
            "quickscale_cli.utils.railway_utils.run_railway_command"
        ) as mock_run:
            # First call (Postgres) fails, second call (PostgreSQL) succeeds
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="Service not found"),
                Mock(returncode=0, stdout="", stderr=""),
            ]
            success, message = link_database_to_service("myapp")

            assert success is True
            assert "linked successfully" in message.lower()
            # Verify both attempts were made
            assert mock_run.call_count == 2
            # Check second call used PostgreSQL
            second_call = mock_run.call_args_list[1]
            assert "PostgreSQL.DATABASE_URL" in second_call[0][0][2]

    def test_link_fails_both_attempts(self):
        """Test when both Postgres and PostgreSQL link attempts fail."""
        with patch(
            "quickscale_cli.utils.railway_utils.run_railway_command"
        ) as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="Service not found"),
                Mock(returncode=1, stdout="", stderr="Service not found"),
            ]
            success, message = link_database_to_service("myapp")

            assert success is False
            assert "failed to link" in message.lower()
            assert mock_run.call_count == 2

    def test_link_with_exception(self):
        """Test when an exception occurs during linking."""
        with patch(
            "quickscale_cli.utils.railway_utils.run_railway_command"
        ) as mock_run:
            mock_run.side_effect = Exception("Network error")
            success, message = link_database_to_service("myapp")

            assert success is False
            assert "error linking" in message.lower()
            assert "network error" in message.lower()

    def test_link_with_different_service_name(self):
        """Test linking with a different service name."""
        with patch(
            "quickscale_cli.utils.railway_utils.run_railway_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            success, message = link_database_to_service("custom-app-123")

            assert success is True
            # Verify service name was passed correctly
            call_args = mock_run.call_args[0][0]
            assert "--service" in call_args
            assert "custom-app-123" in call_args
