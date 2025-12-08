"""Tests for module_commands.py - module management functionality."""

from unittest.mock import Mock, patch

import click
import pytest

from quickscale_cli.commands.module_commands import (
    _check_auth_module_migrations,
    _install_module_dependencies,
    _perform_module_embed,
    _print_installation_error,
    _update_single_module,
    _validate_git_environment,
    _validate_module_not_exists,
    _validate_remote_branch,
    _validate_update_environment,
    embed_module,
    push,
    update,
)


class TestValidateGitEnvironment:
    """Tests for _validate_git_environment function."""

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.is_working_directory_clean")
    def test_valid_environment(self, mock_clean, mock_repo):
        """Test validation passes when git repo is clean."""
        mock_repo.return_value = True
        mock_clean.return_value = True

        result = _validate_git_environment()

        assert result is True
        mock_repo.assert_called_once()
        mock_clean.assert_called_once()

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    def test_not_git_repo(self, mock_repo):
        """Test validation fails when not a git repository."""
        mock_repo.return_value = False

        result = _validate_git_environment()

        assert result is False

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.is_working_directory_clean")
    def test_dirty_working_directory(self, mock_clean, mock_repo):
        """Test validation fails when working directory has uncommitted changes."""
        mock_repo.return_value = True
        mock_clean.return_value = False

        result = _validate_git_environment()

        assert result is False


class TestValidateModuleNotExists:
    """Tests for _validate_module_not_exists function."""

    def test_module_does_not_exist(self, tmp_path):
        """Test validation passes when module doesn't exist."""
        result = _validate_module_not_exists(tmp_path, "auth")

        assert result is True

    def test_module_already_exists(self, tmp_path):
        """Test validation fails when module already exists."""
        # Create module directory
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        result = _validate_module_not_exists(tmp_path, "auth")

        assert result is False


class TestValidateRemoteBranch:
    """Tests for _validate_remote_branch function."""

    @patch("quickscale_cli.commands.module_commands.check_remote_branch_exists")
    def test_branch_exists(self, mock_check):
        """Test validation passes when branch exists on remote."""
        mock_check.return_value = True

        result = _validate_remote_branch(
            "https://example.com/repo.git", "splits/auth-module", "auth"
        )

        assert result is True
        mock_check.assert_called_once_with(
            "https://example.com/repo.git", "splits/auth-module"
        )

    @patch("quickscale_cli.commands.module_commands.check_remote_branch_exists")
    def test_branch_does_not_exist(self, mock_check):
        """Test validation fails when branch doesn't exist."""
        mock_check.return_value = False

        result = _validate_remote_branch(
            "https://example.com/repo.git", "splits/nonexistent-module", "nonexistent"
        )

        assert result is False


class TestCheckAuthModuleMigrations:
    """Tests for _check_auth_module_migrations function."""

    @patch("quickscale_cli.commands.module_commands.has_migrations_been_run")
    def test_no_migrations_run(self, mock_migrations):
        """Test check passes when no migrations have been run."""
        mock_migrations.return_value = False

        result = _check_auth_module_migrations(non_interactive=True)

        assert result is True

    @patch("quickscale_cli.commands.module_commands.has_migrations_been_run")
    def test_migrations_exist_non_interactive(self, mock_migrations):
        """Test check fails in non-interactive mode when migrations exist."""
        mock_migrations.return_value = True

        result = _check_auth_module_migrations(non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands.has_migrations_been_run")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_migrations_exist_user_confirms(self, mock_confirm, mock_migrations):
        """Test check passes when user confirms to continue despite migrations."""
        mock_migrations.return_value = True
        mock_confirm.return_value = True

        result = _check_auth_module_migrations(non_interactive=False)

        assert result is True

    @patch("quickscale_cli.commands.module_commands.has_migrations_been_run")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_migrations_exist_user_cancels(self, mock_confirm, mock_migrations):
        """Test check fails when user cancels."""
        mock_migrations.return_value = True
        mock_confirm.return_value = False

        result = _check_auth_module_migrations(non_interactive=False)

        assert result is False


class TestPerformModuleEmbed:
    """Tests for _perform_module_embed function."""

    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS", {})
    def test_successful_embed_without_configurator(
        self, mock_subtree, mock_add_module, mock_install, tmp_path
    ):
        """Test successful module embedding without configurator."""
        mock_install.return_value = True
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        result = _perform_module_embed(
            tmp_path,
            "auth",
            "https://example.com/repo.git",
            "splits/auth-module",
            {},
        )

        assert result is True
        mock_subtree.assert_called_once()
        mock_add_module.assert_called_once()
        mock_install.assert_called_once_with(tmp_path, "auth")

    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    def test_embed_with_configurator(
        self, mock_subtree, mock_add_module, mock_install, tmp_path
    ):
        """Test embedding with module configurator."""
        mock_install.return_value = True
        module_dir = tmp_path / "modules" / "blog"
        module_dir.mkdir(parents=True)

        # Mock configurator
        configurator = Mock(return_value={})
        applier = Mock()

        with patch(
            "quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS",
            {"blog": (configurator, applier)},
        ):
            result = _perform_module_embed(
                tmp_path,
                "blog",
                "https://example.com/repo.git",
                "splits/blog-module",
                {"some": "config"},
            )

        assert result is True
        applier.assert_called_once_with(tmp_path, {"some": "config"})

    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS", {})
    def test_embed_dependency_installation_fails(
        self, mock_subtree, mock_add_module, mock_install, tmp_path
    ):
        """Test embedding fails when dependency installation fails."""
        mock_install.return_value = False

        result = _perform_module_embed(
            tmp_path,
            "listings",
            "https://example.com/repo.git",
            "splits/listings-module",
            {},
        )

        assert result is False


class TestInstallModuleDependencies:
    """Tests for _install_module_dependencies function."""

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_successful_installation(self, mock_run, tmp_path):
        """Test successful dependency installation."""
        # Create module directory
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        # Mock successful subprocess calls
        mock_run.return_value = Mock(returncode=0)

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is True
        assert mock_run.call_count == 2  # poetry add + poetry install

    def test_module_directory_not_found(self, tmp_path):
        """Test installation fails when module directory doesn't exist."""
        result = _install_module_dependencies(tmp_path, "nonexistent")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_poetry_add_fails(self, mock_run, tmp_path):
        """Test installation fails when poetry add fails."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        # Mock failed poetry add
        mock_run.return_value = Mock(returncode=1, stderr="Error", stdout="")

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_poetry_install_fails(self, mock_run, tmp_path):
        """Test installation fails when poetry install fails."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        # First call (poetry add) succeeds, second (poetry install) fails
        mock_run.side_effect = [
            Mock(returncode=0),  # poetry add success
            Mock(
                returncode=1, stderr="Install error", stdout=""
            ),  # poetry install fails
        ]

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_nested_module_path_detection(self, mock_run, tmp_path):
        """Test detection and use of nested module path."""
        # Create nested module structure
        module_dir = tmp_path / "modules" / "auth"
        nested_dir = module_dir / "quickscale_modules" / "auth"
        nested_dir.mkdir(parents=True)
        (nested_dir / "pyproject.toml").touch()

        mock_run.return_value = Mock(returncode=0)

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is True
        # Verify nested path was used
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "quickscale_modules/auth" in " ".join(first_call_args)

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_subprocess_exception(self, mock_run, tmp_path):
        """Test handling of subprocess exceptions (CalledProcessError)."""
        import subprocess

        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        # Use CalledProcessError which is the actual exception subprocess.run can raise
        mock_run.side_effect = subprocess.CalledProcessError(1, ["poetry", "add"])

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is False


class TestPrintInstallationError:
    """Tests for _print_installation_error function."""

    def test_error_message_printed(self, tmp_path):
        """Test that error details are printed correctly."""
        result = Mock(stderr="Error output", stdout="Standard output")

        # Should not raise - just print to console
        _print_installation_error(tmp_path, "auth", result)


class TestEmbedModule:
    """Tests for embed_module function."""

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS", {})
    def test_successful_embed(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_auth_check,
        mock_perform,
        tmp_path,
    ):
        """Test successful module embedding."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_auth_check.return_value = True
        mock_perform.return_value = True

        result = embed_module("auth", tmp_path, non_interactive=True)

        assert result is True
        mock_perform.assert_called_once()

    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_git_validation_fails(self, mock_git_env, tmp_path):
        """Test embedding fails when git validation fails."""
        mock_git_env.return_value = False

        result = embed_module("auth", tmp_path)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_module_already_exists(self, mock_git_env, mock_not_exists, tmp_path):
        """Test embedding fails when module already exists."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = False

        result = embed_module("auth", tmp_path)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_remote_branch_not_found(
        self, mock_git_env, mock_not_exists, mock_remote, tmp_path
    ):
        """Test embedding fails when remote branch doesn't exist."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = False

        result = embed_module("auth", tmp_path)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_auth_migration_check_fails(
        self, mock_git_env, mock_not_exists, mock_remote, mock_auth_check, tmp_path
    ):
        """Test embedding fails when auth migration check fails."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_auth_check.return_value = False

        result = embed_module("auth", tmp_path, non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS", {})
    def test_git_error_handling(
        self, mock_git_env, mock_not_exists, mock_remote, mock_perform, tmp_path
    ):
        """Test handling of GitError during embedding."""
        from quickscale_core.utils.git_utils import GitError

        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.side_effect = GitError("Git operation failed")

        result = embed_module("blog", tmp_path, non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS", {})
    def test_unexpected_error_handling(
        self, mock_git_env, mock_not_exists, mock_remote, mock_perform, tmp_path
    ):
        """Test handling of unexpected exceptions."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.side_effect = Exception("Unexpected error")

        result = embed_module("listings", tmp_path, non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_embed_with_configurator_called(
        self, mock_git_env, mock_not_exists, mock_remote, mock_perform, tmp_path
    ):
        """Test that module configurator is called when available."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.return_value = True

        configurator = Mock(return_value={"test": "config"})
        applier = Mock()

        with patch(
            "quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS",
            {"blog": (configurator, applier)},
        ):
            result = embed_module("blog", tmp_path, non_interactive=True)

        assert result is True
        configurator.assert_called_once_with(non_interactive=True)


class TestValidateUpdateEnvironment:
    """Tests for _validate_update_environment function."""

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.is_working_directory_clean")
    def test_valid_update_environment(self, mock_clean, mock_repo):
        """Test validation passes in valid environment."""
        mock_repo.return_value = True
        mock_clean.return_value = True

        # Should not raise
        _validate_update_environment()

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    def test_not_git_repo_raises(self, mock_repo):
        """Test validation raises when not a git repository."""
        mock_repo.return_value = False

        with pytest.raises(click.Abort):
            _validate_update_environment()

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.is_working_directory_clean")
    def test_dirty_working_directory_raises(self, mock_clean, mock_repo):
        """Test validation raises when working directory is dirty."""
        mock_repo.return_value = True
        mock_clean.return_value = False

        with pytest.raises(click.Abort):
            _validate_update_environment()


class TestUpdateSingleModule:
    """Tests for _update_single_module function."""

    @patch("quickscale_cli.commands.module_commands.update_module_version")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_successful_update(self, mock_pull, mock_update_version):
        """Test successful module update."""
        mock_pull.return_value = "Changes applied successfully"
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=False
        )

        mock_pull.assert_called_once_with(
            prefix="modules/auth",
            remote="https://example.com/repo.git",
            branch="splits/auth-module",
            squash=True,
        )
        mock_update_version.assert_called_once()

    @patch("quickscale_cli.commands.module_commands.update_module_version")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_update_with_no_preview(self, mock_pull, mock_update_version):
        """Test update with preview disabled."""
        mock_pull.return_value = "Changes"
        module_info = Mock(prefix="modules/blog", branch="splits/blog-module")

        _update_single_module(
            "blog", module_info, "https://example.com/repo.git", no_preview=True
        )

        mock_pull.assert_called_once()

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_update_git_error(self, mock_pull):
        """Test handling of GitError during update."""
        from quickscale_core.utils.git_utils import GitError

        mock_pull.side_effect = GitError("Pull failed")
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        # Should not raise - error is handled internally
        _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=False
        )


class TestUpdateCommand:
    """Tests for update click command."""

    @patch("quickscale_cli.commands.module_commands._update_single_module")
    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_successful_update(
        self, mock_confirm, mock_validate, mock_load, mock_update
    ):
        """Test successful update of installed modules."""
        mock_confirm.return_value = True
        module_info = Mock(
            installed_version="v0.70.0",
            prefix="modules/auth",
            branch="splits/auth-module",
        )
        config = Mock(
            modules={"auth": module_info}, default_remote="https://example.com/repo.git"
        )
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update, ["--no-preview"])

        assert result.exit_code == 0

    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    def test_no_modules_installed(self, mock_validate, mock_load):
        """Test update when no modules are installed."""
        config = Mock(modules={})
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update)

        assert result.exit_code == 0
        assert "No modules installed" in result.output

    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_user_cancels_update(self, mock_confirm, mock_validate, mock_load):
        """Test update cancelled by user."""
        mock_confirm.return_value = False
        module_info = Mock(installed_version="v0.70.0")
        config = Mock(
            modules={"auth": module_info}, default_remote="https://example.com/repo.git"
        )
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update)

        assert result.exit_code == 0
        assert "cancelled" in result.output


class TestPushCommand:
    """Tests for push click command."""

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_push")
    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_successful_push(self, mock_confirm, mock_repo, mock_load, mock_push):
        """Test successful push of module changes."""
        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")
        config = Mock(modules={"auth": module_info})
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code == 0
        mock_push.assert_called_once()

    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    def test_push_not_git_repo(self, mock_repo):
        """Test push fails when not a git repository."""
        mock_repo.return_value = False

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code != 0

    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    def test_push_module_not_installed(self, mock_repo, mock_load):
        """Test push fails when module is not installed."""
        mock_repo.return_value = True
        config = Mock(modules={})
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code != 0

    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_user_cancels_push(self, mock_confirm, mock_repo, mock_load):
        """Test push cancelled by user."""
        mock_repo.return_value = True
        mock_confirm.return_value = False
        module_info = Mock(prefix="modules/auth")
        config = Mock(modules={"auth": module_info})
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_push")
    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_push_with_custom_branch(
        self, mock_confirm, mock_repo, mock_load, mock_push
    ):
        """Test push with custom branch name."""
        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_info = Mock(prefix="modules/auth")
        config = Mock(modules={"auth": module_info})
        mock_load.return_value = config

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            push, ["--module", "auth", "--branch", "feature/custom-branch"]
        )

        assert result.exit_code == 0
        # Verify custom branch was used
        call_args = mock_push.call_args
        assert call_args[1]["branch"] == "feature/custom-branch"

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_push")
    @patch("quickscale_cli.commands.module_commands.load_config")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_push_git_error(self, mock_confirm, mock_repo, mock_load, mock_push):
        """Test handling of GitError during push."""
        from quickscale_core.utils.git_utils import GitError

        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_info = Mock(prefix="modules/auth")
        config = Mock(modules={"auth": module_info})
        mock_load.return_value = config
        mock_push.side_effect = GitError("Push failed")

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code != 0
