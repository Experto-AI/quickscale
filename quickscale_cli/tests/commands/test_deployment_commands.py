"""Tests for deployment commands."""

from contextlib import contextmanager
from unittest.mock import Mock, patch

from click.testing import CliRunner

from quickscale_cli.commands.deployment_commands import railway


@contextmanager
def mock_preflight_checks(has_changes=False, all_valid=True):
    """Context manager to mock all pre-flight check functions."""
    with patch("quickscale_cli.commands.deployment_commands.check_uncommitted_changes") as mock_git:
        with patch(
            "quickscale_cli.commands.deployment_commands.verify_railway_json"
        ) as mock_railway_json:
            with patch(
                "quickscale_cli.commands.deployment_commands.verify_dockerfile"
            ) as mock_dockerfile:
                with patch(
                    "quickscale_cli.commands.deployment_commands.verify_railway_dependencies"
                ) as mock_deps:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency"
                    ) as mock_poetry_lock:
                        # Configure defaults
                        mock_git.return_value = (has_changes, "")
                        mock_railway_json.return_value = (all_valid, "" if all_valid else "Error")
                        mock_dockerfile.return_value = (all_valid, "" if all_valid else "Error")
                        mock_deps.return_value = (all_valid, [] if all_valid else ["missing"])
                        mock_poetry_lock.return_value = (True, "consistent")

                        yield {
                            "git": mock_git,
                            "railway_json": mock_railway_json,
                            "dockerfile": mock_dockerfile,
                            "deps": mock_deps,
                            "poetry_lock": mock_poetry_lock,
                        }


class TestRailwayCommand:
    """Tests for railway deployment command."""

    def test_railway_cli_not_installed(self):
        """Test railway command when Railway CLI not installed."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_npm_installed"
                ) as mock_npm:
                    mock_installed.return_value = False
                    mock_npm.return_value = False

                    result = runner.invoke(railway)

                    assert result.exit_code == 1
                    assert "npm is not installed" in result.output

    def test_railway_not_authenticated(self):
        """Test railway command when not authenticated."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.login_railway_cli_browserless"
                    ) as mock_login:
                        mock_installed.return_value = True
                        mock_auth.return_value = False
                        mock_login.return_value = False

                        result = runner.invoke(railway)

                        assert result.exit_code == 1
                        assert "Authentication failed" in result.output

    def test_railway_successful_deployment_with_existing_project(self):
        """Test successful deployment when Railway project already initialized."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_run.return_value = Mock(
                                            returncode=0,
                                            stdout="postgres available",
                                            stderr="",
                                        )
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        result = runner.invoke(railway)

                                        assert result.exit_code == 0
                                        assert (
                                            "Deployment process completed successfully!"
                                            in result.output
                                        )
                                        assert (
                                            "Railway project already initialized" in result.output
                                        )

    def test_railway_initializes_new_project(self):
        """Test railway command initializes new project."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = False
                                        mock_run.return_value = Mock(
                                            returncode=0,
                                            stdout="postgres available",
                                            stderr="",
                                        )
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        result = runner.invoke(railway, input="\n")

                                        assert result.exit_code == 0
                                        assert "Railway project initialized" in result.output

    def test_railway_with_project_name_option(self):
        """Test railway command with --project-name option."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_run.return_value = Mock(
                                            returncode=0,
                                            stdout="postgres available",
                                            stderr="",
                                        )
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        result = runner.invoke(
                                            railway,
                                            ["--project-name", "myapp"],
                                        )

                                        assert result.exit_code == 0
                                        # Verify DJANGO_SETTINGS_MODULE was included in batch
                                        batch_vars = mock_batch_set.call_args[0][0]
                                        assert "DJANGO_SETTINGS_MODULE" in batch_vars
                                        assert (
                                            "myapp.settings.production"
                                            in batch_vars["DJANGO_SETTINGS_MODULE"]
                                        )

    def test_railway_deployment_failure(self):
        """Test railway command when deployment fails."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        # Call sequence: postgres service check, app service
                                        # check, deployment (fails)
                                        mock_run.side_effect = [
                                            Mock(
                                                returncode=0, stdout="postgres", stderr=""
                                            ),  # postgres service check
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service check (not found)
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service creation
                                            Mock(
                                                returncode=1, stdout="", stderr="Build failed"
                                            ),  # deployment fails
                                        ]

                                        result = runner.invoke(railway)

                                        assert result.exit_code == 1
                                        assert "Deployment failed" in result.output

    def test_railway_project_init_failure(self):
        """Test railway command when project init fails."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            mock_installed.return_value = True
                            mock_auth.return_value = True
                            mock_project_init.return_value = False
                            mock_run.return_value = Mock(
                                returncode=1, stdout="", stderr="Init failed"
                            )

                            result = runner.invoke(railway, input="\n")

                            assert result.exit_code == 1
                            assert "Failed to initialize Railway project" in result.output

    def test_railway_sets_environment_variables_in_batch(self):
        """Test railway command sets all required environment variables in batch."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_run.return_value = Mock(
                                            returncode=0,
                                            stdout="postgres available",
                                            stderr="",
                                        )
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        result = runner.invoke(railway)

                                        assert result.exit_code == 0
                                        # Verify batch set was called once
                                        assert mock_batch_set.call_count == 1

                                        # Verify all environment variables were included in batch
                                        batch_vars = mock_batch_set.call_args[0][0]
                                        assert "SECRET_KEY" in batch_vars
                                        assert "ALLOWED_HOSTS" in batch_vars
                                        assert "DEBUG" in batch_vars
                                        assert batch_vars["DEBUG"] == "False"

                                        # Verify ALLOWED_HOSTS was set with the domain (without https://)
                                        assert (
                                            "myapp-production-abc123.up.railway.app"
                                            in batch_vars["ALLOWED_HOSTS"]
                                        )

                                        # Verify this triggers only ONE deployment
                                        assert "triggers ONE deployment" in result.output

    def test_railway_handles_timeout(self):
        """Test railway command handles deployment timeout gracefully."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        # Call sequence: postgres check, app service check,
                                        # app service creation, deployment times out
                                        mock_run.side_effect = [
                                            Mock(
                                                returncode=0, stdout="postgres", stderr=""
                                            ),  # postgres service check
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service check (not found)
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service creation
                                            TimeoutError(
                                                "Railway command timed out"
                                            ),  # deployment times out
                                        ]

                                        result = runner.invoke(railway)

                                        assert "Deployment command timed out" in result.output

    def test_railway_uncommitted_changes_user_cancels(self):
        """Test railway command when user cancels deployment due to uncommitted changes."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.deployment_commands.check_uncommitted_changes"
        ) as mock_git:
            mock_git.return_value = (True, "M some_file.py")

            result = runner.invoke(railway, input="n\n")

            assert result.exit_code == 0
            assert "You have uncommitted changes" in result.output
            assert "Deployment cancelled" in result.output

    def test_railway_invalid_railway_json(self):
        """Test railway command with invalid railway.json."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.deployment_commands.check_uncommitted_changes"
        ) as mock_git:
            with patch(
                "quickscale_cli.commands.deployment_commands.verify_railway_json"
            ) as mock_railway_json:
                mock_git.return_value = (False, "")
                mock_railway_json.return_value = (False, "railway.json not found in project root")

                result = runner.invoke(railway)

                assert result.exit_code == 1
                assert "railway.json not found in project root" in result.output

    def test_railway_missing_dockerfile(self):
        """Test railway command with missing Dockerfile."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.deployment_commands.check_uncommitted_changes"
        ) as mock_git:
            with patch(
                "quickscale_cli.commands.deployment_commands.verify_railway_json"
            ) as mock_railway_json:
                with patch(
                    "quickscale_cli.commands.deployment_commands.verify_dockerfile"
                ) as mock_dockerfile:
                    mock_git.return_value = (False, "")
                    mock_railway_json.return_value = (True, "")
                    mock_dockerfile.return_value = (False, "Dockerfile not found in project root")

                    result = runner.invoke(railway)

                    assert result.exit_code == 1
                    assert "Dockerfile not found in project root" in result.output

    def test_railway_missing_dependencies_user_cancels(self):
        """Test railway command when user cancels due to missing dependencies."""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.deployment_commands.check_uncommitted_changes"
        ) as mock_git:
            with patch(
                "quickscale_cli.commands.deployment_commands.verify_railway_json"
            ) as mock_railway_json:
                with patch(
                    "quickscale_cli.commands.deployment_commands.verify_dockerfile"
                ) as mock_dockerfile:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.verify_railway_dependencies"
                    ) as mock_deps:
                        mock_git.return_value = (False, "")
                        mock_railway_json.return_value = (True, "")
                        mock_dockerfile.return_value = (True, "")
                        mock_deps.return_value = (False, ["gunicorn", "psycopg2-binary"])

                        result = runner.invoke(railway, input="n\n")

                        assert result.exit_code == 0
                        assert "Missing required Railway dependencies" in result.output
                        assert "gunicorn" in result.output
                        assert "Deployment cancelled" in result.output

    def test_railway_poetry_lock_inconsistent_user_fixes(self):
        """Test railway command when poetry.lock is inconsistent and user fixes it."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency"
            ) as mock_poetry_check:
                with patch(
                    "quickscale_cli.commands.deployment_commands.fix_poetry_lock"
                ) as mock_fix:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
                    ) as mock_installed:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                        ) as mock_auth:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                            ) as mock_project_init:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.run_railway_command"
                                ) as mock_run:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                    ) as mock_batch_set:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                        ) as mock_secret:
                                            with patch(
                                                "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                            ) as mock_domain:
                                                mock_poetry_check.return_value = (
                                                    False,
                                                    "poetry.lock is inconsistent",
                                                )
                                                mock_fix.return_value = (
                                                    True,
                                                    "poetry.lock updated successfully",
                                                )
                                                mock_installed.return_value = True
                                                mock_auth.return_value = True
                                                mock_project_init.return_value = True
                                                mock_run.return_value = Mock(
                                                    returncode=0,
                                                    stdout="postgres available",
                                                    stderr="",
                                                )
                                                mock_batch_set.return_value = (True, [])
                                                mock_secret.return_value = "test-secret-key"
                                                mock_domain.return_value = (
                                                    "https://myapp-production-abc123.up.railway.app"
                                                )

                                                result = runner.invoke(railway, input="y\n")

                                                assert result.exit_code == 0
                                                assert (
                                                    "poetry.lock updated successfully"
                                                    in result.output
                                                )
                                                mock_fix.assert_called_once()

    def test_railway_poetry_lock_inconsistent_user_cancels(self):
        """Test railway command when poetry.lock is inconsistent and user cancels without fixing."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.check_poetry_lock_consistency"
            ) as mock_poetry_check:
                mock_poetry_check.return_value = (False, "poetry.lock is inconsistent")

                result = runner.invoke(railway, input="n\nn\n")

                assert result.exit_code == 0
                assert "poetry.lock is inconsistent" in result.output
                assert "Deployment cancelled" in result.output

    def test_railway_cli_auto_install_success(self):
        """Test railway command auto-installs CLI successfully."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_npm_installed"
                ) as mock_npm:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.install_railway_cli"
                    ) as mock_install:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                        ) as mock_auth:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                            ) as mock_project_init:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.run_railway_command"
                                ) as mock_run:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                    ) as mock_batch_set:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                        ) as mock_secret:
                                            with patch(
                                                "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                            ) as mock_domain:
                                                mock_installed.return_value = False
                                                mock_npm.return_value = True
                                                mock_install.return_value = True
                                                mock_auth.return_value = True
                                                mock_project_init.return_value = True
                                                mock_run.return_value = Mock(
                                                    returncode=0,
                                                    stdout="postgres available",
                                                    stderr="",
                                                )
                                                mock_batch_set.return_value = (True, [])
                                                mock_secret.return_value = "test-secret-key"
                                                mock_domain.return_value = (
                                                    "https://myapp-production-abc123.up.railway.app"
                                                )

                                                result = runner.invoke(railway)

                                                assert result.exit_code == 0
                                                assert (
                                                    "Railway CLI installed successfully"
                                                    in result.output
                                                )
                                                mock_install.assert_called_once()

    def test_railway_cli_upgrade_success(self):
        """Test railway command upgrades CLI successfully when version is outdated."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.get_railway_cli_version"
                ) as mock_version:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.check_railway_cli_version"
                    ) as mock_check_version:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.upgrade_railway_cli"
                        ) as mock_upgrade:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                            ) as mock_auth:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                                ) as mock_project_init:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.run_railway_command"
                                    ) as mock_run:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                        ) as mock_batch_set:
                                            with patch(
                                                "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                            ) as mock_secret:
                                                with patch(
                                                    "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                                ) as mock_domain:
                                                    mock_installed.return_value = True
                                                    mock_version.side_effect = [
                                                        "3.0.0",
                                                        "4.1.0",
                                                    ]  # Before and after upgrade
                                                    mock_check_version.return_value = (
                                                        False  # Version < 4.0.0
                                                    )
                                                    mock_upgrade.return_value = True
                                                    mock_auth.return_value = True
                                                    mock_project_init.return_value = True
                                                    mock_run.return_value = Mock(
                                                        returncode=0,
                                                        stdout="postgres available",
                                                        stderr="",
                                                    )
                                                    mock_batch_set.return_value = (True, [])
                                                    mock_secret.return_value = "test-secret-key"
                                                    mock_domain.return_value = "https://myapp-production-abc123.up.railway.app"

                                                    result = runner.invoke(railway)

                                                    assert result.exit_code == 0
                                                    assert (
                                                        "Railway CLI upgraded to 4.1.0"
                                                        in result.output
                                                    )
                                                    mock_upgrade.assert_called_once()

    def test_railway_postgres_service_created(self):
        """Test railway command creates PostgreSQL service when not present."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_batch_set.return_value = (True, [])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        # Call sequence: postgres check (not found), add postgres,
                                        # app service check, app service creation, deployment
                                        mock_run.side_effect = [
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # postgres check (not found)
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # add postgres
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service check (not found)
                                            Mock(
                                                returncode=0, stdout="", stderr=""
                                            ),  # app service creation
                                            Mock(returncode=0, stdout="", stderr=""),  # deployment
                                        ]

                                        result = runner.invoke(railway)

                                        assert result.exit_code == 0
                                        assert "PostgreSQL service added" in result.output

    def test_railway_batch_variables_fallback_to_individual(self):
        """Test railway command falls back to individual variable setting when batch fails."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                            ) as mock_batch_set:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                ) as mock_secret:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                    ) as mock_domain:
                                        mock_installed.return_value = True
                                        mock_auth.return_value = True
                                        mock_project_init.return_value = True
                                        mock_run.return_value = Mock(
                                            returncode=0,
                                            stdout="postgres available",
                                            stderr="",
                                        )
                                        # Batch setting fails with some variables
                                        mock_batch_set.return_value = (False, ["DEBUG"])
                                        mock_secret.return_value = "test-secret-key"
                                        mock_domain.return_value = (
                                            "https://myapp-production-abc123.up.railway.app"
                                        )

                                        result = runner.invoke(railway)

                                        assert result.exit_code == 0
                                        assert (
                                            "Some environment variables could not be set"
                                            in result.output
                                        )
                                        assert "DEBUG" in result.output

    def test_railway_login_success(self):
        """Test railway command successfully authenticates when not logged in."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.login_railway_cli_browserless"
                    ) as mock_login:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                        ) as mock_project_init:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.run_railway_command"
                            ) as mock_run:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                ) as mock_batch_set:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                    ) as mock_secret:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                        ) as mock_domain:
                                            mock_installed.return_value = True
                                            mock_auth.return_value = False
                                            mock_login.return_value = True
                                            mock_project_init.return_value = True
                                            mock_run.return_value = Mock(
                                                returncode=0,
                                                stdout="postgres available",
                                                stderr="",
                                            )
                                            mock_batch_set.return_value = (True, [])
                                            mock_secret.return_value = "test-secret-key"
                                            mock_domain.return_value = (
                                                "https://myapp-production-abc123.up.railway.app"
                                            )

                                            result = runner.invoke(railway)

                                            assert result.exit_code == 0
                                            assert (
                                                "Successfully authenticated with Railway"
                                                in result.output
                                            )
                                            mock_login.assert_called_once()

    def test_railway_links_database_url(self):
        """Test railway command links DATABASE_URL to app service."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.link_database_to_service"
                            ) as mock_link:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                ) as mock_batch_set:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                    ) as mock_secret:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                        ) as mock_domain:
                                            mock_installed.return_value = True
                                            mock_auth.return_value = True
                                            mock_project_init.return_value = True
                                            mock_run.return_value = Mock(
                                                returncode=0,
                                                stdout="postgres available",
                                                stderr="",
                                            )
                                            mock_link.return_value = (
                                                True,
                                                "DATABASE_URL reference linked successfully",
                                            )
                                            mock_batch_set.return_value = (True, [])
                                            mock_secret.return_value = "test-secret-key"
                                            mock_domain.return_value = (
                                                "https://myapp-production-abc123.up.railway.app"
                                            )

                                            result = runner.invoke(
                                                railway, ["--project-name", "myapp"]
                                            )

                                            assert result.exit_code == 0
                                            assert (
                                                "DATABASE_URL reference linked successfully"
                                                in result.output
                                            )
                                            # Verify link_database_to_service was called with
                                            # correct service name
                                            mock_link.assert_called_once_with("myapp")

    def test_railway_database_link_failure_shows_warning(self):
        """Test railway command shows warning when DATABASE_URL linking fails."""
        runner = CliRunner()

        with mock_preflight_checks():
            with patch(
                "quickscale_cli.commands.deployment_commands.is_railway_cli_installed"
            ) as mock_installed:
                with patch(
                    "quickscale_cli.commands.deployment_commands.is_railway_authenticated"
                ) as mock_auth:
                    with patch(
                        "quickscale_cli.commands.deployment_commands.is_railway_project_initialized"
                    ) as mock_project_init:
                        with patch(
                            "quickscale_cli.commands.deployment_commands.run_railway_command"
                        ) as mock_run:
                            with patch(
                                "quickscale_cli.commands.deployment_commands.link_database_to_service"
                            ) as mock_link:
                                with patch(
                                    "quickscale_cli.commands.deployment_commands.set_railway_variables_batch"
                                ) as mock_batch_set:
                                    with patch(
                                        "quickscale_cli.commands.deployment_commands.generate_django_secret_key"
                                    ) as mock_secret:
                                        with patch(
                                            "quickscale_cli.commands.deployment_commands.generate_railway_domain"
                                        ) as mock_domain:
                                            mock_installed.return_value = True
                                            mock_auth.return_value = True
                                            mock_project_init.return_value = True
                                            mock_run.return_value = Mock(
                                                returncode=0,
                                                stdout="postgres available",
                                                stderr="",
                                            )
                                            mock_link.return_value = (
                                                False,
                                                "Failed to link DATABASE_URL",
                                            )
                                            mock_batch_set.return_value = (True, [])
                                            mock_secret.return_value = "test-secret-key"
                                            mock_domain.return_value = (
                                                "https://myapp-production-abc123.up.railway.app"
                                            )

                                            result = runner.invoke(railway)

                                            assert result.exit_code == 0
                                            assert "Failed to link DATABASE_URL" in result.output
                                            assert "link DATABASE_URL manually" in result.output
