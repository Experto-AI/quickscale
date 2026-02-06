"""Extended tests for deployment_commands.py - covering missing helper functions."""

from unittest.mock import Mock, patch

import pytest

from quickscale_cli.commands.deployment_commands import (
    _check_and_upgrade_railway_cli,
    _check_poetry_lock_step,
    _check_uncommitted_changes_step,
    _configure_env_vars_step,
    _create_app_service_step,
    _deploy_app_step,
    _display_summary,
    _ensure_railway_auth_step,
    _ensure_railway_cli_step,
    _generate_domain_step,
    _init_railway_project_step,
    _link_database_step,
    _setup_postgres_step,
    _verify_dependencies_step,
    _verify_deployment_step,
    _verify_railway_files_step,
)


# ============================================================================
# _check_uncommitted_changes_step
# ============================================================================


class TestCheckUncommittedChangesStep:
    """Tests for _check_uncommitted_changes_step"""

    @patch("quickscale_cli.commands.deployment_commands.check_uncommitted_changes")
    def test_no_changes(self, mock_check):
        """Test with no uncommitted changes"""
        mock_check.return_value = (False, "")
        _check_uncommitted_changes_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_uncommitted_changes")
    def test_has_changes_continue(self, mock_check, mock_confirm):
        """Test with uncommitted changes, user continues"""
        mock_check.return_value = (True, "M file.py")
        mock_confirm.return_value = True
        _check_uncommitted_changes_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_uncommitted_changes")
    def test_has_changes_cancel(self, mock_check, mock_confirm):
        """Test with uncommitted changes, user cancels"""
        mock_check.return_value = (True, "M file.py")
        mock_confirm.return_value = False
        with pytest.raises(SystemExit):
            _check_uncommitted_changes_step()


# ============================================================================
# _verify_railway_files_step
# ============================================================================


class TestVerifyRailwayFilesStep:
    """Tests for _verify_railway_files_step"""

    @patch("quickscale_cli.commands.deployment_commands.verify_dockerfile")
    @patch("quickscale_cli.commands.deployment_commands.verify_railway_json")
    def test_all_valid(self, mock_json, mock_docker):
        """Test all files valid"""
        mock_json.return_value = (True, "")
        mock_docker.return_value = (True, "")
        _verify_railway_files_step()

    @patch("quickscale_cli.commands.deployment_commands.verify_railway_json")
    def test_railway_json_invalid(self, mock_json):
        """Test invalid railway.json"""
        mock_json.return_value = (False, "Missing file")
        with pytest.raises(SystemExit):
            _verify_railway_files_step()

    @patch("quickscale_cli.commands.deployment_commands.verify_dockerfile")
    @patch("quickscale_cli.commands.deployment_commands.verify_railway_json")
    def test_dockerfile_missing(self, mock_json, mock_docker):
        """Test missing Dockerfile"""
        mock_json.return_value = (True, "")
        mock_docker.return_value = (False, "Missing Dockerfile")
        with pytest.raises(SystemExit):
            _verify_railway_files_step()


# ============================================================================
# _verify_dependencies_step
# ============================================================================


class TestVerifyDependenciesStep:
    """Tests for _verify_dependencies_step"""

    @patch("quickscale_cli.commands.deployment_commands.verify_railway_dependencies")
    def test_all_present(self, mock_verify):
        """Test all dependencies present"""
        mock_verify.return_value = (True, [])
        _verify_dependencies_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.verify_railway_dependencies")
    def test_missing_deps_continue(self, mock_verify, mock_confirm):
        """Test missing deps, user continues"""
        mock_verify.return_value = (False, ["gunicorn"])
        mock_confirm.return_value = True
        _verify_dependencies_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.verify_railway_dependencies")
    def test_missing_deps_cancel(self, mock_verify, mock_confirm):
        """Test missing deps, user cancels"""
        mock_verify.return_value = (False, ["gunicorn", "psycopg2-binary"])
        mock_confirm.return_value = False
        with pytest.raises(SystemExit):
            _verify_dependencies_step()


# ============================================================================
# _check_poetry_lock_step
# ============================================================================


class TestCheckPoetryLockStep:
    """Tests for _check_poetry_lock_step"""

    @patch("quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency")
    def test_consistent(self, mock_check):
        """Test consistent lock file"""
        mock_check.return_value = (True, "consistent")
        _check_poetry_lock_step()

    @patch("quickscale_cli.commands.deployment_commands.fix_poetry_lock")
    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency")
    def test_inconsistent_fix_success(self, mock_check, mock_confirm, mock_fix):
        """Test inconsistent lock, fix succeeds"""
        mock_check.return_value = (False, "outdated")
        mock_confirm.return_value = True
        mock_fix.return_value = (True, "Fixed")
        _check_poetry_lock_step()

    @patch("quickscale_cli.commands.deployment_commands.fix_poetry_lock")
    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency")
    def test_inconsistent_fix_fails(self, mock_check, mock_confirm, mock_fix):
        """Test inconsistent lock, fix fails, user continues"""
        mock_check.return_value = (False, "outdated")
        mock_confirm.side_effect = [True, True]  # fix? yes, continue? yes
        mock_fix.return_value = (False, "Failed to fix")
        _check_poetry_lock_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency")
    def test_inconsistent_user_declines_fix(self, mock_check, mock_confirm):
        """Test inconsistent lock, user declines fix, continues"""
        mock_check.return_value = (False, "outdated")
        mock_confirm.side_effect = [False, True]  # don't fix, but continue
        _check_poetry_lock_step()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency")
    def test_lock_not_found(self, mock_check, mock_confirm):
        """Test when lock file not found"""
        mock_check.return_value = (False, "lock not found")
        mock_confirm.return_value = True  # continue anyway
        _check_poetry_lock_step()


# ============================================================================
# _ensure_railway_cli_step
# ============================================================================


class TestEnsureRailwayCliStep:
    """Tests for _ensure_railway_cli_step"""

    @patch("quickscale_cli.commands.deployment_commands.is_railway_cli_installed")
    def test_cli_installed(self, mock_installed):
        """Test when CLI is installed"""
        mock_installed.return_value = True
        with patch(
            "quickscale_cli.commands.deployment_commands._check_and_upgrade_railway_cli"
        ):
            _ensure_railway_cli_step()

    @patch("quickscale_cli.commands.deployment_commands.install_railway_cli")
    @patch("quickscale_cli.commands.deployment_commands.is_npm_installed")
    @patch("quickscale_cli.commands.deployment_commands.is_railway_cli_installed")
    def test_install_success(self, mock_installed, mock_npm, mock_install):
        """Test successful CLI installation"""
        mock_installed.return_value = False
        mock_npm.return_value = True
        mock_install.return_value = True
        _ensure_railway_cli_step()

    @patch("quickscale_cli.commands.deployment_commands.install_railway_cli")
    @patch("quickscale_cli.commands.deployment_commands.is_npm_installed")
    @patch("quickscale_cli.commands.deployment_commands.is_railway_cli_installed")
    def test_install_fails(self, mock_installed, mock_npm, mock_install):
        """Test failed CLI installation"""
        mock_installed.return_value = False
        mock_npm.return_value = True
        mock_install.return_value = False
        with pytest.raises(SystemExit):
            _ensure_railway_cli_step()


# ============================================================================
# _check_and_upgrade_railway_cli
# ============================================================================


class TestCheckAndUpgradeRailwayCli:
    """Tests for _check_and_upgrade_railway_cli"""

    @patch("quickscale_cli.commands.deployment_commands.check_railway_cli_version")
    @patch("quickscale_cli.commands.deployment_commands.get_railway_cli_version")
    def test_version_up_to_date(self, mock_get, mock_check):
        """Test when version is up to date"""
        mock_get.return_value = "4.1.0"
        mock_check.return_value = True
        _check_and_upgrade_railway_cli()

    @patch("quickscale_cli.commands.deployment_commands.upgrade_railway_cli")
    @patch("quickscale_cli.commands.deployment_commands.check_railway_cli_version")
    @patch("quickscale_cli.commands.deployment_commands.get_railway_cli_version")
    def test_upgrade_success(self, mock_get, mock_check, mock_upgrade):
        """Test successful upgrade"""
        mock_get.side_effect = ["3.0.0", "4.1.0"]
        mock_check.return_value = False
        mock_upgrade.return_value = True
        _check_and_upgrade_railway_cli()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.upgrade_railway_cli")
    @patch("quickscale_cli.commands.deployment_commands.check_railway_cli_version")
    @patch("quickscale_cli.commands.deployment_commands.get_railway_cli_version")
    def test_upgrade_fails_continue(
        self, mock_get, mock_check, mock_upgrade, mock_confirm
    ):
        """Test upgrade failure, user continues"""
        mock_get.return_value = "3.0.0"
        mock_check.return_value = False
        mock_upgrade.return_value = False
        mock_confirm.return_value = True
        _check_and_upgrade_railway_cli()

    @patch("quickscale_cli.commands.deployment_commands.click.confirm")
    @patch("quickscale_cli.commands.deployment_commands.upgrade_railway_cli")
    @patch("quickscale_cli.commands.deployment_commands.check_railway_cli_version")
    @patch("quickscale_cli.commands.deployment_commands.get_railway_cli_version")
    def test_upgrade_fails_abort(
        self, mock_get, mock_check, mock_upgrade, mock_confirm
    ):
        """Test upgrade failure, user aborts"""
        mock_get.return_value = "3.0.0"
        mock_check.return_value = False
        mock_upgrade.return_value = False
        mock_confirm.return_value = False
        with pytest.raises(SystemExit):
            _check_and_upgrade_railway_cli()

    @patch("quickscale_cli.commands.deployment_commands.get_railway_cli_version")
    def test_no_version(self, mock_get):
        """Test when version cannot be determined"""
        mock_get.return_value = None
        _check_and_upgrade_railway_cli()


# ============================================================================
# _ensure_railway_auth_step
# ============================================================================


class TestEnsureRailwayAuthStep:
    """Tests for _ensure_railway_auth_step"""

    @patch("quickscale_cli.commands.deployment_commands.is_railway_authenticated")
    def test_already_authenticated(self, mock_auth):
        """Test when already authenticated"""
        mock_auth.return_value = True
        _ensure_railway_auth_step()

    @patch("quickscale_cli.commands.deployment_commands.login_railway_cli_browserless")
    @patch("quickscale_cli.commands.deployment_commands.is_railway_authenticated")
    def test_login_success(self, mock_auth, mock_login):
        """Test successful login"""
        mock_auth.return_value = False
        mock_login.return_value = True
        _ensure_railway_auth_step()


# ============================================================================
# _init_railway_project_step
# ============================================================================


class TestInitRailwayProjectStep:
    """Tests for _init_railway_project_step"""

    @patch("quickscale_cli.commands.deployment_commands.is_railway_project_initialized")
    def test_already_initialized(self, mock_init):
        """Test when project already initialized"""
        mock_init.return_value = True
        _init_railway_project_step()

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    @patch("quickscale_cli.commands.deployment_commands.is_railway_project_initialized")
    def test_init_fails(self, mock_init, mock_run):
        """Test initialization failure"""
        mock_init.return_value = False
        mock_run.return_value = Mock(returncode=1)
        with pytest.raises(SystemExit):
            _init_railway_project_step()

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    @patch("quickscale_cli.commands.deployment_commands.is_railway_project_initialized")
    def test_init_exception(self, mock_init, mock_run):
        """Test initialization exception"""
        mock_init.return_value = False
        mock_run.side_effect = TimeoutError("timeout")
        with pytest.raises(SystemExit):
            _init_railway_project_step()


# ============================================================================
# _setup_postgres_step
# ============================================================================


class TestSetupPostgresStep:
    """Tests for _setup_postgres_step"""

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_postgres_exists(self, mock_run):
        """Test when PostgreSQL already exists"""
        mock_run.return_value = Mock(returncode=0, stdout="postgres available")
        _setup_postgres_step()

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_add_postgres_success(self, mock_run):
        """Test adding PostgreSQL successfully"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="no database"),
            Mock(returncode=0, stdout="added"),
        ]
        _setup_postgres_step()

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_add_postgres_fails(self, mock_run):
        """Test adding PostgreSQL failure"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="no database"),
            Mock(returncode=1, stdout=""),
        ]
        _setup_postgres_step()

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_check_exception(self, mock_run):
        """Test exception during check"""
        mock_run.side_effect = Exception("network error")
        _setup_postgres_step()


# ============================================================================
# _create_app_service_step
# ============================================================================


class TestCreateAppServiceStep:
    """Tests for _create_app_service_step"""

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_service_exists(self, mock_run):
        """Test when service already exists"""
        mock_run.return_value = Mock(returncode=0, stdout="myapp service running")
        _create_app_service_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_create_success(self, mock_run):
        """Test successful service creation"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="no matching service"),
            Mock(returncode=0, stdout="created"),
        ]
        _create_app_service_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_create_fails(self, mock_run):
        """Test service creation failure"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="no matching"),
            Mock(returncode=1, stdout=""),
        ]
        _create_app_service_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_exception(self, mock_run):
        """Test exception during service creation"""
        mock_run.side_effect = Exception("error")
        _create_app_service_step("myapp")


# ============================================================================
# _deploy_app_step
# ============================================================================


class TestDeployAppStep:
    """Tests for _deploy_app_step"""

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_success(self, mock_run):
        """Test successful deployment"""
        mock_run.return_value = Mock(returncode=0, stderr="")
        _deploy_app_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_failure(self, mock_run):
        """Test deployment failure"""
        mock_run.return_value = Mock(returncode=1, stderr="build failed")
        with pytest.raises(SystemExit):
            _deploy_app_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.run_railway_command")
    def test_timeout(self, mock_run):
        """Test deployment timeout"""
        mock_run.side_effect = TimeoutError("timeout")
        _deploy_app_step("myapp")


# ============================================================================
# _verify_deployment_step
# ============================================================================


class TestVerifyDeploymentStep:
    """Tests for _verify_deployment_step"""

    @patch("quickscale_cli.commands.deployment_commands.get_railway_variables")
    def test_all_vars_set(self, mock_vars):
        """Test all variables set"""
        mock_vars.return_value = {
            "DATABASE_URL": "postgres://...",
            "SECRET_KEY": "secret",
            "DEBUG": "False",
            "DJANGO_SETTINGS_MODULE": "myapp.settings.production",
            "ALLOWED_HOSTS": "myapp.up.railway.app",
        }
        _verify_deployment_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.get_railway_variables")
    def test_missing_vars(self, mock_vars):
        """Test with missing variables"""
        mock_vars.return_value = {"DEBUG": "False"}
        _verify_deployment_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.get_railway_variables")
    def test_no_vars(self, mock_vars):
        """Test when vars can't be retrieved"""
        mock_vars.return_value = None
        _verify_deployment_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.get_railway_variables")
    def test_long_value_truncated(self, mock_vars):
        """Test long variable values are truncated"""
        mock_vars.return_value = {
            "ALLOWED_HOSTS": "a" * 100,
        }
        _verify_deployment_step("myapp")


# ============================================================================
# _display_summary / _link_database_step / _generate_domain_step / _configure_env_vars_step
# ============================================================================


class TestRemainingHelpers:
    """Tests for remaining deployment helper functions"""

    def test_display_summary_with_domain(self):
        """Display summary with domain"""
        _display_summary("myapp", "https://myapp.up.railway.app")

    def test_display_summary_without_domain(self):
        """Display summary without domain"""
        _display_summary("myapp", None)

    @patch("quickscale_cli.commands.deployment_commands.link_database_to_service")
    def test_link_database_success(self, mock_link):
        """Test successful database link"""
        mock_link.return_value = (True, "Linked")
        _link_database_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.link_database_to_service")
    def test_link_database_failure(self, mock_link):
        """Test failed database link"""
        mock_link.return_value = (False, "Failed")
        _link_database_step("myapp")

    @patch("quickscale_cli.commands.deployment_commands.generate_railway_domain")
    def test_generate_domain_success(self, mock_gen):
        """Test successful domain generation"""
        mock_gen.return_value = "https://myapp.up.railway.app"
        result = _generate_domain_step("myapp")
        assert result is not None

    @patch("quickscale_cli.commands.deployment_commands.generate_railway_domain")
    def test_generate_domain_failure(self, mock_gen):
        """Test domain generation failure"""
        mock_gen.return_value = None
        result = _generate_domain_step("myapp")
        assert result is None

    @patch("quickscale_cli.commands.deployment_commands.set_railway_variables_batch")
    @patch("quickscale_cli.commands.deployment_commands.generate_django_secret_key")
    def test_configure_env_vars_success(self, mock_secret, mock_batch):
        """Test successful env var configuration"""
        mock_secret.return_value = "secret-key"
        mock_batch.return_value = (True, [])
        _configure_env_vars_step("myapp", "myapp.up.railway.app")

    @patch("quickscale_cli.commands.deployment_commands.set_railway_variables_batch")
    @patch("quickscale_cli.commands.deployment_commands.generate_django_secret_key")
    def test_configure_env_vars_failure(self, mock_secret, mock_batch):
        """Test env var configuration with failures"""
        mock_secret.return_value = "secret-key"
        mock_batch.return_value = (False, ["SECRET_KEY"])
        _configure_env_vars_step("myapp", None)

    @patch("quickscale_cli.commands.deployment_commands.set_railway_variables_batch")
    @patch("quickscale_cli.commands.deployment_commands.generate_django_secret_key")
    def test_configure_env_vars_no_domain(self, mock_secret, mock_batch):
        """Test env var config without domain"""
        mock_secret.return_value = "secret-key"
        mock_batch.return_value = (True, [])
        _configure_env_vars_step("myapp", None)
