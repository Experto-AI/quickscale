"""Tests for module_commands.py - module management functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest

from quickscale_cli.commands.module_config import (
    APPLY_MODULE_EXECUTION_MODE,
    ModuleConfigurator,
)
from quickscale_core.manifest.loader import ManifestError

from quickscale_cli.commands.module_commands import (
    _check_auth_module_migrations,
    _commit_module_update,
    _install_module_dependencies,
    _perform_module_embed,
    _print_installation_error,
    _resolve_embedded_module_install_path,
    _sync_state_module_version,
    _update_single_module,
    _validate_git_environment,
    _validate_module_not_exists,
    _validate_remote_branch,
    _validate_update_environment,
    embed_module,
    ModuleEmbedProvenance,
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

    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    def test_no_migrations_run(self, mock_assess):
        """Test check passes when no migrations have been run."""
        mock_assess.return_value = Mock(
            compatible=True,
            incompatible=False,
            unverifiable=False,
            reason="compatible",
        )

        result = _check_auth_module_migrations(Path("/tmp"), non_interactive=True)

        assert result is True

    @patch("quickscale_cli.commands.module_commands.format_auth_migration_remediation")
    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    def test_migrations_exist_non_interactive(self, mock_assess, mock_remediation):
        """Test check fails in non-interactive mode when migrations exist."""
        mock_assess.return_value = Mock(
            compatible=False,
            incompatible=True,
            unverifiable=False,
            reason="incompatible",
        )
        mock_remediation.return_value = "fix steps"

        result = _check_auth_module_migrations(Path("/tmp"), non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands.format_auth_migration_remediation")
    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    def test_unverifiable_non_interactive_strict(
        self,
        mock_assess,
        mock_remediation,
    ):
        """Test unverifiable state fails in strict non-interactive mode."""
        mock_assess.return_value = Mock(
            compatible=False,
            incompatible=False,
            unverifiable=True,
            status="unverifiable",
            reason="connection refused",
        )
        mock_remediation.return_value = "fix steps"

        result = _check_auth_module_migrations(Path("/tmp"), non_interactive=True)

        assert result is False

    @patch("quickscale_cli.commands.module_commands.format_auth_migration_remediation")
    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    def test_unverifiable_non_interactive_allowed(
        self,
        mock_assess,
        mock_remediation,
    ):
        """Test unverifiable state can continue when explicitly allowed."""
        mock_assess.return_value = Mock(
            compatible=False,
            incompatible=False,
            unverifiable=True,
            status="unverifiable",
            reason="connection refused",
        )
        mock_remediation.return_value = "fix steps"

        result = _check_auth_module_migrations(
            Path("/tmp"),
            non_interactive=True,
            allow_unverifiable_auth_state=True,
        )

        assert result is True

    @patch("quickscale_cli.commands.module_commands.format_auth_migration_remediation")
    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_migrations_exist_user_confirms(
        self,
        mock_confirm,
        mock_assess,
        mock_remediation,
    ):
        """Test check passes when user confirms to continue despite migrations."""
        mock_assess.return_value = Mock(
            compatible=False,
            incompatible=True,
            unverifiable=False,
            reason="incompatible",
        )
        mock_remediation.return_value = "fix steps"
        mock_confirm.return_value = True

        result = _check_auth_module_migrations(Path("/tmp"), non_interactive=False)

        assert result is True

    @patch("quickscale_cli.commands.module_commands.format_auth_migration_remediation")
    @patch("quickscale_cli.commands.module_commands.assess_auth_migration_state")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_migrations_exist_user_cancels(
        self,
        mock_confirm,
        mock_assess,
        mock_remediation,
    ):
        """Test check fails when user cancels."""
        mock_assess.return_value = Mock(
            compatible=False,
            incompatible=True,
            unverifiable=False,
            reason="incompatible",
        )
        mock_remediation.return_value = "fix steps"
        mock_confirm.return_value = False

        result = _check_auth_module_migrations(Path("/tmp"), non_interactive=False)

        assert result is False


class TestPerformModuleEmbed:
    """Tests for _perform_module_embed function."""

    @patch("quickscale_cli.commands.module_commands._sync_module_dependencies")
    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_successful_embed_without_configurator(
        self,
        mock_subtree,
        mock_add_module,
        mock_install,
        mock_sync_dependencies,
        tmp_path,
    ):
        """Test successful module embedding without configurator."""
        mock_sync_dependencies.return_value = True
        mock_install.return_value = True
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        result = _perform_module_embed(
            tmp_path,
            "auth",
            "https://example.com/repo.git",
            "splits/auth-module",
            {},
        )

        assert result == (True, None)
        mock_subtree.assert_called_once()
        mock_add_module.assert_called_once_with(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="0.82.0",
            project_path=tmp_path,
        )
        mock_sync_dependencies.assert_called_once_with(tmp_path, "auth", {})
        mock_install.assert_called_once_with(tmp_path, "auth")

    @patch("quickscale_cli.commands.module_commands._sync_module_dependencies")
    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    def test_embed_with_configurator(
        self,
        mock_subtree,
        mock_add_module,
        mock_install,
        mock_sync_dependencies,
        tmp_path,
    ):
        """Test embedding with module configurator."""
        mock_sync_dependencies.return_value = True
        mock_install.return_value = True
        module_dir = tmp_path / "modules" / "blog"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: blog\nversion: "0.82.0"\n')

        # Mock configurator
        configurator = Mock(return_value={})
        applier = Mock()

        with patch(
            "quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY",
            {
                "blog": ModuleConfigurator(
                    name="blog", configure=configurator, apply=applier
                )
            },
        ):
            result = _perform_module_embed(
                tmp_path,
                "blog",
                "https://example.com/repo.git",
                "splits/blog-module",
                {"some": "config"},
            )

        assert result == (True, None)
        applier.assert_called_once_with(tmp_path, {"some": "config"})
        mock_sync_dependencies.assert_called_once_with(
            tmp_path,
            "blog",
            {"some": "config"},
        )

    @patch("quickscale_cli.commands.module_commands._sync_module_dependencies")
    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_embed_dependency_installation_fails(
        self,
        mock_subtree,
        mock_add_module,
        mock_install,
        mock_sync_dependencies,
        tmp_path,
    ):
        """Test embedding fails when dependency installation fails."""
        mock_sync_dependencies.return_value = True
        mock_install.return_value = False
        module_dir = tmp_path / "modules" / "listings"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()
        (module_dir / "module.yml").write_text('name: listings\nversion: "0.82.0"\n')

        result = _perform_module_embed(
            tmp_path,
            "listings",
            "https://example.com/repo.git",
            "splits/listings-module",
            {},
        )

        assert result == (False, None)

    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_embed_fails_when_embedded_manifest_is_invalid(
        self, mock_subtree, mock_add_module, mock_install, tmp_path
    ):
        """Embedding should fail fast when the embedded module manifest is malformed."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        result = _perform_module_embed(
            tmp_path,
            "auth",
            "https://example.com/repo.git",
            "splits/auth-module",
            {},
        )

        assert result == (False, None)
        mock_add_module.assert_not_called()
        mock_install.assert_not_called()

    def test_apply_mode_failure_cleans_partial_module_directory_and_tracking(
        self,
        tmp_path,
    ):
        """Apply embeds should remove failed subtree artifacts so reruns are not blocked."""

        def _fake_subtree_add(*, prefix: str, remote: str, branch: str, squash: bool):
            del remote, branch, squash
            module_dir = tmp_path / prefix
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "module.yml").write_text('name: blog\nversion: "0.82.0"\n')

        def _failing_applier(
            project_path: Path,
            config: dict[str, object],
            *,
            execution_mode: str,
        ) -> None:
            del project_path, config
            if execution_mode == APPLY_MODULE_EXECUTION_MODE:
                raise RuntimeError("apply-specific configuration failed")

        with (
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_add",
                side_effect=_fake_subtree_add,
            ),
            patch.dict(
                "quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY",
                {
                    "blog": ModuleConfigurator(
                        name="blog", configure=Mock(), apply=_failing_applier
                    )
                },
                clear=True,
            ),
        ):
            result = _perform_module_embed(
                tmp_path,
                "blog",
                "https://example.com/repo.git",
                "splits/blog-module",
                {"enabled": True},
                sync_dependencies=False,
                install_dependencies=False,
                execution_mode=APPLY_MODULE_EXECUTION_MODE,
            )

        assert result == (False, None)
        assert not (tmp_path / "modules" / "blog").exists()
        config_path = tmp_path / ".quickscale" / "config.yml"
        assert not config_path.exists() or "blog:" not in config_path.read_text()

    @patch("quickscale_cli.commands.module_commands._sync_module_dependencies")
    @patch("quickscale_cli.commands.module_commands._install_module_dependencies")
    @patch("quickscale_cli.commands.module_commands.add_module")
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_add")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_source_ref_forwarded_to_subtree_add_and_provenance_returned(
        self,
        mock_subtree,
        mock_add_module,
        mock_install,
        mock_sync_dependencies,
        tmp_path,
    ):
        """Phase 1: source_ref binds subtree add and populates provenance."""
        mock_sync_dependencies.return_value = True
        mock_install.return_value = True
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        resolved_sha = "b" * 40
        success, provenance = _perform_module_embed(
            tmp_path,
            "auth",
            "https://example.com/repo.git",
            "splits/auth-module",
            {},
            source_ref=resolved_sha,
        )

        assert success is True
        # subtree add received the resolved SHA, not the branch name
        mock_subtree.assert_called_once_with(
            prefix="modules/auth",
            remote="https://example.com/repo.git",
            branch=resolved_sha,
            squash=True,
        )
        # provenance carries the same source_ref and tracking metadata
        assert provenance is not None
        assert provenance.source_ref == resolved_sha
        assert provenance.tracking_branch == "splits/auth-module"
        assert provenance.module_name == "auth"
        assert provenance.prefix == "modules/auth"
        assert provenance.installed_version == "0.82.0"


class TestInstallModuleDependencies:
    """Tests for _install_module_dependencies function."""

    def test_resolve_embedded_module_install_path_prefers_nested_split_package(
        self,
        tmp_path,
    ):
        """Split-repo module layouts should keep using the nested package path."""
        module_dir = tmp_path / "modules" / "auth"
        nested_dir = module_dir / "quickscale_modules" / "auth"
        nested_dir.mkdir(parents=True)
        (nested_dir / "pyproject.toml").touch()
        (module_dir / "pyproject.toml").touch()

        resolved = _resolve_embedded_module_install_path(tmp_path, "auth")

        assert resolved == nested_dir

    def test_resolve_embedded_module_install_path_supports_root_package_layout(
        self,
        tmp_path,
    ):
        """Packaged modules like analytics should install from the module root."""
        module_dir = tmp_path / "modules" / "analytics"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

        resolved = _resolve_embedded_module_install_path(tmp_path, "analytics")

        assert resolved == module_dir

    def test_resolve_embedded_module_install_path_returns_none_without_pyproject(
        self,
        tmp_path,
    ):
        """Modules without Python packaging metadata should skip Poetry install."""
        module_dir = tmp_path / "modules" / "static_assets"
        module_dir.mkdir(parents=True)

        resolved = _resolve_embedded_module_install_path(tmp_path, "static_assets")

        assert resolved is None

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_successful_installation(self, mock_run, tmp_path):
        """Test successful dependency installation."""
        # Create module directory
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

        mock_run.side_effect = [
            Mock(returncode=0, stderr="", stdout=""),
            Mock(returncode=0, stderr="", stdout=""),
        ]

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is True
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == ["poetry", "lock"]
        assert mock_run.call_args_list[1][0][0] == ["poetry", "install"]

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_root_module_path_detection(self, mock_run, tmp_path):
        """Root-package modules should still install successfully."""
        module_dir = tmp_path / "modules" / "analytics"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

        mock_run.side_effect = [
            Mock(returncode=0, stderr="", stdout=""),
            Mock(returncode=0, stderr="", stdout=""),
        ]

        result = _install_module_dependencies(tmp_path, "analytics")

        assert result is True
        assert mock_run.call_args_list[0][0][0] == ["poetry", "lock"]
        assert mock_run.call_args_list[1][0][0] == ["poetry", "install"]

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_skips_install_when_no_python_package_detected(self, mock_run, tmp_path):
        """Modules without a Python package should skip Poetry installation cleanly."""
        module_dir = tmp_path / "modules" / "docs_only"
        module_dir.mkdir(parents=True)

        result = _install_module_dependencies(tmp_path, "docs_only")

        assert result is True
        mock_run.assert_not_called()

    def test_module_directory_not_found(self, tmp_path):
        """Test installation fails when module directory doesn't exist."""
        result = _install_module_dependencies(tmp_path, "nonexistent")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_poetry_lock_fails(self, mock_run, tmp_path):
        """Test installation fails when poetry lock fails."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

        mock_run.return_value = Mock(returncode=1, stderr="Error", stdout="")

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_poetry_install_fails(self, mock_run, tmp_path):
        """Test installation fails when poetry install fails."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

        mock_run.side_effect = [
            Mock(returncode=0, stderr="", stdout=""),
            Mock(returncode=1, stderr="Install error", stdout=""),
        ]

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is False

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_nested_module_path_detection(self, mock_run, tmp_path):
        """Nested module layouts should still install successfully."""
        # Create nested module structure
        module_dir = tmp_path / "modules" / "auth"
        nested_dir = module_dir / "quickscale_modules" / "auth"
        nested_dir.mkdir(parents=True)
        (nested_dir / "pyproject.toml").touch()

        mock_run.side_effect = [
            Mock(returncode=0, stderr="", stdout=""),
            Mock(returncode=0, stderr="", stdout=""),
        ]

        result = _install_module_dependencies(tmp_path, "auth")

        assert result is True
        assert mock_run.call_args_list[0][0][0] == ["poetry", "lock"]
        assert mock_run.call_args_list[1][0][0] == ["poetry", "install"]

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_subprocess_exception(self, mock_run, tmp_path):
        """Test handling of subprocess exceptions (CalledProcessError)."""
        import subprocess

        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "pyproject.toml").touch()

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

    def test_standalone_embed_regenerates_managed_wiring_immediately(self, tmp_path):
        """Standalone embed should keep its immediate managed-wiring pass."""
        module_dir = tmp_path / "modules" / "blog"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: blog\nversion: "0.82.0"\n')

        with (
            patch(
                "quickscale_cli.commands.module_commands._validate_git_environment",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_module_not_exists",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_remote_branch",
                return_value=True,
            ),
            patch("quickscale_cli.commands.module_commands.run_git_subtree_add"),
            patch("quickscale_cli.commands.module_commands.add_module"),
            patch(
                "quickscale_cli.commands.module_config.regenerate_managed_wiring",
                return_value=(True, "ok"),
            ) as mock_regenerate,
        ):
            result = embed_module(
                "blog",
                tmp_path,
                non_interactive=True,
                sync_dependencies=False,
                install_dependencies=False,
            )

        assert result is True
        mock_regenerate.assert_called_once()
        assert mock_regenerate.call_args.kwargs["module_names"] == ["blog"]
        assert mock_regenerate.call_args.kwargs["option_overrides"] == {
            "blog": {
                "posts_per_page": 10,
                "enable_rss": True,
                "api_rate_limit": "5/hour",
            }
        }

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    def test_billing_module_uses_standard_readiness_path(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_perform,
        tmp_path,
        capsys,
    ):
        """Billing should no longer be blocked by a stale standalone special case."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.return_value = (True, None)

        result = embed_module("billing", tmp_path)
        captured = capsys.readouterr()

        assert result is True
        assert "internal packaged Phase 1 foundation" not in captured.err
        assert (
            "Billing remains excluded from public quickscale embed" not in captured.err
        )
        mock_remote.assert_called_once()
        mock_perform.assert_called_once()

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
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
        mock_perform.return_value = (True, None)

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
    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_auth_migration_allow_unverifiable_forwarded(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_auth_check,
        mock_perform,
        tmp_path,
    ):
        """Test embed_module forwards allow_unverifiable_auth_state to guardrail."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_auth_check.return_value = True
        mock_perform.return_value = (True, None)

        result = embed_module(
            "auth",
            tmp_path,
            non_interactive=True,
            allow_unverifiable_auth_state=True,
        )

        assert result is True
        mock_auth_check.assert_called_once_with(tmp_path, True, True)

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_auth_migration_check_can_be_skipped(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_auth_check,
        mock_perform,
        tmp_path,
    ):
        """Test embed_module can bypass auth migration check when requested."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.return_value = (True, None)

        result = embed_module(
            "auth",
            tmp_path,
            non_interactive=True,
            skip_auth_migration_check=True,
        )

        assert result is True
        mock_auth_check.assert_not_called()

    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
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
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
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
        mock_perform.return_value = (True, None)

        configurator = Mock(return_value={"test": "config"})
        applier = Mock()

        with patch(
            "quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY",
            {
                "blog": ModuleConfigurator(
                    name="blog", configure=configurator, apply=applier
                )
            },
        ):
            result = embed_module("blog", tmp_path, non_interactive=True)

        assert result is True
        configurator.assert_called_once_with(non_interactive=True)

    @patch("quickscale_cli.commands.module_commands.resolve_remote_ref")
    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._check_auth_module_migrations")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_apply_embed_resolves_source_ref_once_and_carries_provenance(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_auth_check,
        mock_perform,
        mock_resolve,
        tmp_path,
    ):
        """Phase 1 seam: apply resolves source_ref once and forwards provenance."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_auth_check.return_value = True
        resolved_sha = "a" * 40
        mock_resolve.return_value = resolved_sha

        expected_provenance = ModuleEmbedProvenance(
            module_name="auth",
            prefix="modules/auth",
            tracking_branch="splits/auth-module",
            source_ref=resolved_sha,
            installed_version="0.82.0",
        )
        mock_perform.return_value = (True, expected_provenance)

        sink: list[ModuleEmbedProvenance] = []
        result = embed_module(
            "auth",
            tmp_path,
            non_interactive=True,
            execution_mode=APPLY_MODULE_EXECUTION_MODE,
            provenance_sink=sink,
        )

        assert result is True
        # source_ref resolved exactly once after branch validation
        mock_resolve.assert_called_once_with(
            "https://github.com/Experto-AI/quickscale.git",
            "splits/auth-module",
        )
        # resolved SHA forwarded to _perform_module_embed for subtree add
        mock_perform.assert_called_once()
        assert mock_perform.call_args.kwargs["source_ref"] == resolved_sha
        # provenance payload carried forward in the sink
        assert sink == [expected_provenance]
        assert sink[0].source_ref == resolved_sha
        assert sink[0].tracking_branch == "splits/auth-module"

    @patch("quickscale_cli.commands.module_commands.resolve_remote_ref")
    @patch("quickscale_cli.commands.module_commands._perform_module_embed")
    @patch("quickscale_cli.commands.module_commands._validate_remote_branch")
    @patch("quickscale_cli.commands.module_commands._validate_module_not_exists")
    @patch("quickscale_cli.commands.module_commands._validate_git_environment")
    @patch("quickscale_cli.commands.module_commands.MODULE_CONFIGURATOR_REGISTRY", {})
    def test_standalone_embed_does_not_resolve_source_ref(
        self,
        mock_git_env,
        mock_not_exists,
        mock_remote,
        mock_perform,
        mock_resolve,
        tmp_path,
    ):
        """Standalone embeds must not resolve source_ref (Phase 1 scope)."""
        mock_git_env.return_value = True
        mock_not_exists.return_value = True
        mock_remote.return_value = True
        mock_perform.return_value = (True, None)

        result = embed_module(
            "auth",
            tmp_path,
            non_interactive=True,
            skip_auth_migration_check=True,
        )

        assert result is True
        mock_resolve.assert_not_called()
        # No source_ref forwarded in standalone mode
        assert mock_perform.call_args.kwargs.get("source_ref") is None


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

    @pytest.mark.parametrize(
        ("state_contents", "expected_fragment"),
        [
            ("- invalid\n", "State file must be a YAML mapping"),
            (
                'version: "1"\nproject:\n  name: legacy-app\n  theme: showcase_react\n',
                "Legacy state schema detected",
            ),
        ],
    )
    def test_update_aborts_before_subtree_pull_when_state_is_invalid(
        self,
        tmp_path,
        monkeypatch,
        capsys,
        state_contents,
        expected_fragment,
    ):
        """Invalid applied state should abort before any subtree or config mutation."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(state_contents)
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        with (
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull"
            ) as mock_pull,
            patch(
                "quickscale_cli.commands.module_commands._sync_state_module_version"
            ) as mock_sync_state,
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update"
            ) as mock_commit,
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=False,
            )

        captured = capsys.readouterr()

        assert result is False
        assert "Failed to load .quickscale/state.yml" in captured.err
        assert expected_fragment in captured.err
        mock_pull.assert_not_called()
        mock_sync_state.assert_not_called()
        mock_commit.assert_not_called()

    def test_update_local_guard_blocks_before_subtree_pull_on_option_drift(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """Known local desired/applied drift should block update before subtree pull."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    '  created_at: "2025-01-01T00:00:00"',
                    '  last_applied: "2025-01-01T00:00:00"',
                    "modules:",
                    "  blog:",
                    "    name: blog",
                    '    version: "0.71.0"',
                    '    commit_sha: "abc123"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    options:",
                    "      enable_rss: true",
                ]
            )
            + "\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    "modules:",
                    "  blog:",
                    "    enable_rss: false",
                    "docker:",
                    "  start: false",
                ]
            )
            + "\n"
        )
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/blog", branch="splits/blog-module")

        with (
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull"
            ) as mock_pull,
            patch(
                "quickscale_cli.commands.module_commands._sync_state_module_version"
            ) as mock_sync_state,
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update"
            ) as mock_commit,
        ):
            result = _update_single_module(
                "blog",
                module_info,
                "https://example.com/repo.git",
                no_preview=False,
            )

        captured = capsys.readouterr()

        assert result is False
        assert "Pre-pull local guard blocked update for blog" in captured.err
        assert "quickscale apply" in captured.err
        assert "blog.enable_rss" in captured.err
        mock_pull.assert_not_called()
        mock_sync_state.assert_not_called()
        mock_commit.assert_not_called()

    def test_update_restores_pre_pull_snapshot_after_post_pull_failure(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Post-pull failures should restore module and tracking files from snapshot."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        module_manifest = module_dir / "module.yml"
        module_manifest.write_text('name: auth\nversion: "0.71.0"\n')

        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        legacy_config_path = quickscale_dir / "config.yml"
        legacy_config_path.write_text(
            "modules:\n  auth:\n    installed_version: 0.71.0\n"
        )
        state_path = quickscale_dir / "state.yml"
        original_state = (
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    '  created_at: "2025-01-01T00:00:00"',
                    '  last_applied: "2025-01-01T00:00:00"',
                    "modules:",
                    "  auth:",
                    "    name: auth",
                    '    version: "0.71.0"',
                    '    commit_sha: "abc123"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    options: {}",
                ]
            )
            + "\n"
        )
        state_path.write_text(original_state)
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        def _fake_subtree_pull(*, prefix: str, remote: str, branch: str, squash: bool):
            del remote, branch, squash
            (tmp_path / prefix / "module.yml").write_text(
                'name: auth\nversion: "0.82.0"\n'
            )
            return "updated"

        def _fake_sync_state_module_version(
            project_path: Path,
            module_name: str,
            version: str,
            *,
            commit_sha: str | None = None,
        ) -> None:
            del module_name, commit_sha
            (project_path / ".quickscale" / "state.yml").write_text(
                original_state.replace('version: "0.71.0"', f'version: "{version}"', 1)
            )

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref",
                return_value="a" * 40,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                side_effect=_fake_subtree_pull,
            ),
            patch(
                "quickscale_cli.commands.module_commands._read_embedded_module_version",
                return_value="0.82.0",
            ),
            patch(
                "quickscale_cli.commands.module_commands._sync_state_module_version",
                side_effect=_fake_sync_state_module_version,
            ),
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update",
                side_effect=Exception("commit failed after staging"),
            ),
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        assert result is False
        assert module_manifest.read_text() == 'name: auth\nversion: "0.71.0"\n'
        assert (
            legacy_config_path.read_text()
            == "modules:\n  auth:\n    installed_version: 0.71.0\n"
        )
        assert state_path.read_text() == original_state

    @patch(
        "quickscale_cli.commands.module_commands._ensure_authoritative_state_for_update"
    )
    @patch("quickscale_cli.commands.module_commands._commit_module_update")
    @patch("quickscale_cli.commands.module_commands._sync_state_module_version")
    @patch("quickscale_cli.commands.module_commands._read_embedded_module_version")
    @patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        return_value="a" * 40,
    )
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_successful_update(
        self,
        mock_pull,
        mock_resolve,
        mock_read_version,
        mock_sync_state,
        mock_commit,
        mock_ensure_state,
    ):
        """Test successful module update."""
        mock_pull.return_value = "Changes applied successfully"
        mock_read_version.return_value = "0.82.0"
        mock_ensure_state.return_value = Mock(modules={"auth": Mock(version="0.71.0")})
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        result = _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=False
        )

        assert result is True
        # CR-M5-P3-005: subtree pull must use the resolved SHA, not the
        # branch name, so the pulled content is bound to the exact commit
        # that was persisted to state.yml.
        mock_pull.assert_called_once_with(
            prefix="modules/auth",
            remote="https://example.com/repo.git",
            branch="a" * 40,
            squash=True,
        )
        assert mock_sync_state.call_args.args[:2] == (Path.cwd(), "auth")
        mock_commit.assert_called_once_with("auth", "modules/auth")

    @patch(
        "quickscale_cli.commands.module_commands._ensure_authoritative_state_for_update"
    )
    @patch("quickscale_cli.commands.module_commands._commit_module_update")
    @patch("quickscale_cli.commands.module_commands._sync_state_module_version")
    @patch("quickscale_cli.commands.module_commands._read_embedded_module_version")
    @patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        return_value="a" * 40,
    )
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_update_with_no_preview(
        self,
        mock_pull,
        mock_resolve,
        mock_read_version,
        mock_sync_state,
        mock_commit,
        mock_ensure_state,
    ):
        """Test update with preview disabled."""
        mock_pull.return_value = "Changes"
        mock_read_version.return_value = "0.82.0"
        mock_ensure_state.return_value = Mock(modules={"blog": Mock(version="0.71.0")})
        module_info = Mock(prefix="modules/blog", branch="splits/blog-module")

        result = _update_single_module(
            "blog", module_info, "https://example.com/repo.git", no_preview=True
        )

        assert result is True
        mock_pull.assert_called_once()
        mock_commit.assert_called_once_with("blog", "modules/blog")

    @patch(
        "quickscale_cli.commands.module_commands._ensure_authoritative_state_for_update"
    )
    @patch("quickscale_cli.commands.module_commands._read_embedded_module_version")
    @patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        return_value="a" * 40,
    )
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_update_manifest_error(
        self, mock_pull, mock_resolve, mock_read_version, mock_ensure_state
    ):
        """Manifest validation failures should stop the update before commit."""
        mock_pull.return_value = "Changes"
        mock_read_version.side_effect = ManifestError(
            "Manifest file not found: modules/auth/module.yml",
            "auth",
        )
        mock_ensure_state.return_value = Mock(modules={"auth": Mock(version="0.71.0")})
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        result = _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=False
        )

        assert result is False

    @patch(
        "quickscale_cli.commands.module_commands._ensure_authoritative_state_for_update"
    )
    @patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        return_value="a" * 40,
    )
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_update_git_error(self, mock_pull, mock_resolve, mock_ensure_state):
        """Test handling of GitError during update."""
        from quickscale_core.utils.git_utils import GitError

        mock_pull.side_effect = GitError("Pull failed")
        mock_ensure_state.return_value = Mock(modules={"auth": Mock(version="0.71.0")})
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        # Should not raise - error is handled internally
        result = _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=False
        )
        assert result is False

    @patch(
        "quickscale_cli.commands.module_commands._ensure_authoritative_state_for_update"
    )
    @patch("quickscale_cli.commands.module_commands._commit_module_update")
    @patch("quickscale_cli.commands.module_commands._sync_state_module_version")
    @patch("quickscale_cli.commands.module_commands._read_embedded_module_version")
    @patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        return_value="b" * 40,
    )
    @patch("quickscale_cli.commands.module_commands.run_git_subtree_pull")
    def test_subtree_pull_uses_resolved_ref_not_branch_name(
        self,
        mock_pull,
        mock_resolve,
        mock_read_version,
        mock_sync_state,
        mock_commit,
        mock_ensure_state,
    ):
        """CR-M5-P3-005 regression: subtree pull must bind to the resolved SHA.

        Simulates a scenario where the remote branch could advance between
        ``resolve_remote_ref`` and the subtree pull.  The pull must use the
        exact SHA returned by ``resolve_remote_ref`` (not the branch name)
        so the pulled content matches the ``commit_sha`` persisted to state.
        """
        mock_pull.return_value = "Changes applied"
        mock_read_version.return_value = "0.83.0"
        mock_ensure_state.return_value = Mock(modules={"auth": Mock(version="0.82.0")})
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        result = _update_single_module(
            "auth", module_info, "https://example.com/repo.git", no_preview=True
        )

        assert result is True
        # The subtree pull must receive the resolved SHA, not the branch name.
        pull_kwargs = mock_pull.call_args
        assert pull_kwargs.kwargs["branch"] == "b" * 40
        assert pull_kwargs.kwargs["branch"] != "splits/auth-module"
        # The commit_sha persisted to state must also be the resolved SHA.
        sync_call_kwargs = mock_sync_state.call_args.kwargs
        assert sync_call_kwargs["commit_sha"] == "b" * 40


class TestCommitModuleUpdate:
    """Tests for _commit_module_update function."""

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_commit_module_update_commits_changes(
        self,
        mock_run,
        tmp_path,
        monkeypatch,
    ):
        """Test commit helper stages paths and commits when changes exist."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "config.yml").write_text("modules: {}\n")
        (quickscale_dir / "state.yml").write_text("modules: {}\n")
        monkeypatch.chdir(tmp_path)

        mock_run.side_effect = [
            Mock(returncode=0),  # git add
            Mock(returncode=1),  # git diff --cached --quiet (changes staged)
            Mock(returncode=0),  # git commit
        ]

        _commit_module_update("auth", "modules/auth")

        add_call = mock_run.call_args_list[0]
        assert add_call.kwargs["check"] is True
        assert add_call.args[0] == [
            "git",
            "add",
            "modules/auth",
            ".quickscale/config.yml",
            ".quickscale/state.yml",
        ]

        commit_call = mock_run.call_args_list[2]
        assert commit_call.kwargs["check"] is True
        assert commit_call.args[0] == [
            "git",
            "commit",
            "-m",
            "chore(modules): update auth module",
        ]

    @patch("quickscale_cli.commands.module_commands.subprocess.run")
    def test_commit_module_update_skips_when_no_changes(self, mock_run):
        """Test commit helper returns early when no staged changes exist."""
        mock_run.side_effect = [
            Mock(returncode=0),  # git add
            Mock(returncode=0),  # git diff --cached --quiet (no changes)
        ]

        _commit_module_update("listings", "modules/listings")

        assert len(mock_run.call_args_list) == 2


class TestUpdateCommand:
    """Tests for update click command."""

    @patch("quickscale_cli.commands.module_commands._update_single_module")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_update_allows_billing_module_through_standard_readiness_path(
        self,
        mock_confirm,
        mock_validate,
        mock_manager_cls,
        mock_update,
    ):
        """Billing updates should no longer abort on a stale readiness override."""
        mock_confirm.return_value = True
        module_state = Mock(
            version="0.70.0",
            prefix="modules/billing",
            branch="splits/billing-module",
        )
        state = Mock(modules={"billing": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update, ["--no-preview"])

        assert result.exit_code == 0
        assert "internal packaged Phase 1 foundation" not in result.output
        assert (
            "Billing remains excluded from public quickscale embed" not in result.output
        )
        mock_update.assert_called_once()

    @patch("quickscale_cli.commands.module_commands._update_single_module")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_successful_update(
        self, mock_confirm, mock_validate, mock_manager_cls, mock_update
    ):
        """Test successful update of installed modules."""
        mock_confirm.return_value = True
        module_state = Mock(
            version="v0.70.0",
            prefix="modules/auth",
            branch="splits/auth-module",
        )
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update, ["--no-preview"])

        assert result.exit_code == 0

    @patch("quickscale_cli.commands.module_commands._update_single_module")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_update_stops_and_aborts_on_module_failure(
        self, mock_confirm, mock_validate, mock_manager_cls, mock_update
    ):
        """Test update aborts when a module fails to update."""
        mock_confirm.return_value = True
        auth_state = Mock(
            version="v0.70.0",
            prefix="modules/auth",
            branch="splits/auth-module",
        )
        listings_state = Mock(
            version="v0.70.0",
            prefix="modules/listings",
            branch="splits/listings-module",
        )
        state = Mock(modules={"auth": auth_state, "listings": listings_state})
        mock_manager_cls.return_value.load_state.return_value = state
        mock_update.side_effect = [True, False]

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update, ["--no-preview"])

        assert result.exit_code != 0
        assert "Module update stopped due to failure" in result.output
        assert "Unexpected error" not in result.output

    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    def test_no_modules_installed(self, mock_validate, mock_manager_cls):
        """Test update when no modules are installed."""
        state = Mock(modules={})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update)

        assert result.exit_code == 0
        assert "No modules installed" in result.output

    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_user_cancels_update(self, mock_confirm, mock_validate, mock_manager_cls):
        """Test update cancelled by user."""
        mock_confirm.return_value = False
        module_state = Mock(
            version="v0.70.0", prefix="modules/auth", branch="splits/auth-module"
        )
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(update)

        assert result.exit_code == 0
        assert "cancelled" in result.output or "❌" in result.output


class TestUpdateVersionDriftWarning:
    """Tests for the version drift warning invoked by 'quickscale update'."""

    def test_warn_version_drift_for_update_returns_empty_when_agreeing(self, tmp_path):
        """Drift warning is silent when state and config agree on versions."""
        from quickscale_core.config import add_module
        from quickscale_cli.commands.module_commands import (
            _warn_version_drift_for_update,
        )
        from quickscale_core.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        project = tmp_path / "myapp"
        project.mkdir()

        StateManager(project).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                ),
                modules={
                    "auth": ModuleState(name="auth", version="0.62.0"),
                },
            )
        )

        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="0.62.0",  # matches state
            project_path=project,
        )

        from quickscale_core.config import load_config as load_legacy

        config = load_legacy(project)
        drift = _warn_version_drift_for_update(project, config)
        assert drift == []

    def test_warn_version_drift_for_update_reports_disagreement(self, tmp_path):
        """Drift warning returns VersionDriftWarning when versions disagree."""
        from quickscale_core.config import add_module
        from quickscale_cli.commands.module_commands import (
            _warn_version_drift_for_update,
        )
        from quickscale_core.project_state import VersionDriftWarning
        from quickscale_core.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        project = tmp_path / "myapp"
        project.mkdir()

        StateManager(project).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                ),
                modules={
                    "auth": ModuleState(name="auth", version="0.62.0"),
                },
            )
        )

        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="0.63.0",  # drift
            project_path=project,
        )

        from quickscale_core.config import load_config as load_legacy

        config = load_legacy(project)
        drift = _warn_version_drift_for_update(project, config)
        assert len(drift) == 1
        assert isinstance(drift[0], VersionDriftWarning)
        assert drift[0].module == "auth"

    @patch("quickscale_cli.commands.module_commands._update_single_module")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands._validate_update_environment")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_update_emits_drift_warning_via_warn_helper(
        self, mock_confirm, mock_validate, mock_manager_cls, mock_update
    ):
        """Update should still run when drift is detected (drift is non-fatal)."""
        mock_confirm.return_value = True
        module_state = Mock(
            version="v0.70.0",
            prefix="modules/auth",
            branch="splits/auth-module",
        )
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state
        mock_update.return_value = True

        from click.testing import CliRunner

        # Patch the drift warning helper to a no-op so this test focuses on
        # command routing; the helper's own behavior is exercised above.
        with patch(
            "quickscale_cli.commands.module_commands._warn_version_drift_for_update",
            return_value=[],
        ) as mock_warn:
            runner = CliRunner()
            result = runner.invoke(update, ["--no-preview"])

        assert result.exit_code == 0
        mock_warn.assert_called_once()


class TestPushCommand:
    """Tests for push click command."""

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_push")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_successful_push(
        self, mock_confirm, mock_repo, mock_manager_cls, mock_push
    ):
        """Test successful push of module changes."""
        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_state = Mock(prefix="modules/auth", branch="splits/auth-module")
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

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

    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    def test_push_module_not_installed(self, mock_repo, mock_manager_cls):
        """Test push fails when module is not installed."""
        mock_repo.return_value = True
        state = Mock(modules={})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code != 0

    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_user_cancels_push(self, mock_confirm, mock_repo, mock_manager_cls):
        """Test push cancelled by user."""
        mock_repo.return_value = True
        mock_confirm.return_value = False
        module_state = Mock(prefix="modules/auth", branch="splits/auth-module")
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code == 0
        assert (
            "cancelled" in result.output
            or "Push cancelled" in result.output
            or "❌" in result.output
        )

    @patch("quickscale_cli.commands.module_commands.run_git_subtree_push")
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_push_with_custom_branch(
        self, mock_confirm, mock_repo, mock_manager_cls, mock_push
    ):
        """Test push with custom branch name."""
        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_state = Mock(prefix="modules/auth", branch="splits/auth-module")
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state

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
    @patch("quickscale_cli.commands.module_commands.ProjectStateManager")
    @patch("quickscale_cli.commands.module_commands.is_git_repo")
    @patch("quickscale_cli.commands.module_commands.click.confirm")
    def test_push_git_error(self, mock_confirm, mock_repo, mock_manager_cls, mock_push):
        """Test handling of GitError during push."""
        from quickscale_core.utils.git_utils import GitError

        mock_repo.return_value = True
        mock_confirm.return_value = True
        module_state = Mock(prefix="modules/auth", branch="splits/auth-module")
        state = Mock(modules={"auth": module_state})
        mock_manager_cls.return_value.load_state.return_value = state
        mock_push.side_effect = GitError("Push failed")

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(push, ["--module", "auth"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Phase 2.3b: update-path provenance persistence and safeguards
# ---------------------------------------------------------------------------


class TestUpdatePathProvenancePersistence:
    """Tests for Phase 2.3b update-path commit_sha persistence."""

    def test_update_persists_commit_sha_from_resolved_source_ref(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Update must persist the resolved source ref as commit_sha in state.yml."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        state_path = quickscale_dir / "state.yml"
        state_path.write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    '  created_at: "2025-01-01T00:00:00"',
                    '  last_applied: "2025-01-01T00:00:00"',
                    "modules:",
                    "  auth:",
                    "    name: auth",
                    '    version: "0.71.0"',
                    '    commit_sha: "old_sha"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    prefix: modules/auth",
                    "    branch: splits/auth-module",
                    '    installed_at: "2025-01-01"',
                ]
            )
            + "\n"
        )
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        expected_sha = "a" * 40

        def _fake_subtree_pull(*, prefix, remote, branch, squash):
            del remote, branch, squash
            (tmp_path / prefix / "module.yml").write_text(
                'name: auth\nversion: "0.82.0"\n'
            )
            return "updated"

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref",
                return_value=expected_sha,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                side_effect=_fake_subtree_pull,
            ),
            patch(
                "quickscale_cli.commands.module_commands._read_embedded_module_version",
                return_value="0.82.0",
            ),
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update",
            ),
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        assert result is True

        # Verify commit_sha was persisted to state.yml.
        import yaml

        persisted = yaml.safe_load(state_path.read_text())
        assert persisted["modules"]["auth"]["commit_sha"] == expected_sha
        assert persisted["modules"]["auth"]["version"] == "0.82.0"

    def test_update_aborts_when_authoritative_metadata_unavailable(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """Update must abort before git mutation when project metadata cannot be derived."""
        # No state.yml, no quickscale.yml — metadata cannot be derived.
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref"
            ) as mock_resolve,
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull"
            ) as mock_pull,
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        captured = capsys.readouterr()
        assert result is False
        assert "authoritative project metadata" in captured.err
        mock_resolve.assert_not_called()
        mock_pull.assert_not_called()

    def test_update_materializes_config_only_state_before_provenance(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Config-only projects must materialize state.yml before provenance persistence.

        CR-M5-P3-006: materialization requires an existing state.yml with
        authoritative timestamps.  This test provides a pre-M2 state.yml
        (with timestamps but no consolidated module tracking) so that
        materialization can proceed.
        """
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        # quickscale.yml provides project metadata and includes the module.
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth: {}\n"
        )

        # Pre-M2 state.yml with authoritative timestamps but no consolidated
        # module tracking — the scenario that triggers materialization.
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_html\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        # Legacy config.yml provides module tracking.
        (quickscale_dir / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            "    prefix: modules/auth\n"
            "    branch: splits/auth-module\n"
            "    installed_version: '0.71.0'\n"
            "    installed_at: '2025-01-01'\n"
        )
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        expected_sha = "b" * 40

        def _fake_subtree_pull(*, prefix, remote, branch, squash):
            del remote, branch, squash
            (tmp_path / prefix / "module.yml").write_text(
                'name: auth\nversion: "0.82.0"\n'
            )
            return "updated"

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref",
                return_value=expected_sha,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                side_effect=_fake_subtree_pull,
            ),
            patch(
                "quickscale_cli.commands.module_commands._read_embedded_module_version",
                return_value="0.82.0",
            ),
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update",
            ),
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        assert result is True

        # Verify state.yml was materialized and contains provenance.
        import yaml

        state_path = quickscale_dir / "state.yml"
        assert state_path.exists()
        persisted = yaml.safe_load(state_path.read_text())
        assert persisted["project"]["slug"] == "myproject"
        assert persisted["project"]["package"] == "myproject"
        assert persisted["project"]["theme"] == "showcase_html"
        # Timestamps preserved from the original state.yml.
        assert persisted["project"]["created_at"] == "2024-06-15T10:30:00"
        assert persisted["project"]["last_applied"] == "2024-12-01T14:45:00"
        assert "auth" in persisted["modules"]
        assert persisted["modules"]["auth"]["commit_sha"] == expected_sha
        assert persisted["modules"]["auth"]["version"] == "0.82.0"

    def test_update_resolves_source_ref_once_and_reuses_it(
        self,
        tmp_path,
        monkeypatch,
    ):
        """The resolved source ref must be used for both pull and persistence."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    "modules:",
                    "  auth:",
                    "    name: auth",
                    '    version: "0.71.0"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    prefix: modules/auth",
                    "    branch: splits/auth-module",
                    '    installed_at: "2025-01-01"',
                ]
            )
            + "\n"
        )
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        expected_sha = "c" * 40

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref",
                return_value=expected_sha,
            ) as mock_resolve,
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                return_value="updated",
            ),
            patch(
                "quickscale_cli.commands.module_commands._read_embedded_module_version",
                return_value="0.82.0",
            ),
            patch(
                "quickscale_cli.commands.module_commands._commit_module_update",
            ),
            patch(
                "quickscale_cli.commands.module_commands._sync_state_module_version",
            ) as mock_sync,
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        assert result is True
        mock_resolve.assert_called_once_with(
            "https://example.com/repo.git", "splits/auth-module"
        )
        # Verify the same SHA was passed to _sync_state_module_version.
        mock_sync.assert_called_once()
        assert mock_sync.call_args.kwargs["commit_sha"] == expected_sha

    def test_update_aborts_when_source_ref_cannot_be_resolved(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """Update must abort before subtree pull when source ref resolution fails."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myproject",
                    "  package: myproject",
                    "  theme: showcase_html",
                    "modules:",
                    "  auth:",
                    "    name: auth",
                    '    version: "0.71.0"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    prefix: modules/auth",
                    "    branch: splits/auth-module",
                    '    installed_at: "2025-01-01"',
                ]
            )
            + "\n"
        )
        monkeypatch.chdir(tmp_path)
        module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

        from quickscale_core.utils.git_utils import GitError

        with (
            patch(
                "quickscale_cli.commands.module_commands.resolve_remote_ref",
                side_effect=GitError("Remote branch not found"),
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull"
            ) as mock_pull,
        ):
            result = _update_single_module(
                "auth",
                module_info,
                "https://example.com/repo.git",
                no_preview=True,
            )

        captured = capsys.readouterr()
        assert result is False
        assert "resolve source ref" in captured.err
        mock_pull.assert_not_called()


# ============================================================================
# F2.6: Full provenance triple consistency for update path
# ============================================================================


class TestSyncStateModuleVersionTriple:
    """F2.6 tests: _sync_state_module_version refreshes the full provenance
    triple (version, commit_sha, embedded_at) consistently."""

    def test_sync_refreshes_full_triple(self, tmp_path):
        """Update path: _sync_state_module_version writes version,
        commit_sha, and refreshes embedded_at."""
        from quickscale_cli.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        # Pre-create state.yml with a module entry
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        initial_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            ),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.82.0",
                    commit_sha="a" * 40,
                    embedded_at="2025-01-01T00:00:00",
                ),
            },
        )
        state_manager = StateManager(tmp_path)
        state_manager.save(initial_state)

        # Call _sync_state_module_version with new version and commit_sha
        new_sha = "b" * 40
        _sync_state_module_version(
            tmp_path,
            "auth",
            "0.83.0",
            commit_sha=new_sha,
        )

        # Verify full triple was updated
        updated_state = state_manager.load()
        assert updated_state is not None
        assert "auth" in updated_state.modules
        module_state = updated_state.modules["auth"]
        # Full triple: version, commit_sha, embedded_at
        assert module_state.version == "0.83.0"
        assert module_state.commit_sha == new_sha
        assert module_state.embedded_at != "2025-01-01T00:00:00"
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""


# ============================================================================
# F2.7: Caller parity — update path sync helper produces same triple
# ============================================================================


class TestCallerParityUpdateSyncHelper:
    """F2.7 tests: _sync_state_module_version produces the same triple
    structure as the apply and no-op repair paths."""

    def test_sync_helper_produces_same_triple_as_other_paths(self, tmp_path):
        """_sync_state_module_version writes version, commit_sha, and
        embedded_at — the same triple that apply and no-op repair persist."""
        from quickscale_cli.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
            StateManager,
        )

        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        initial_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            ),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.82.0",
                    commit_sha="a" * 40,
                    embedded_at="2025-01-01T00:00:00",
                ),
            },
        )
        state_manager = StateManager(tmp_path)
        state_manager.save(initial_state)

        new_sha = "e" * 40
        _sync_state_module_version(
            tmp_path,
            "auth",
            "0.83.0",
            commit_sha=new_sha,
        )

        updated_state = state_manager.load()
        assert updated_state is not None
        module_state = updated_state.modules["auth"]
        # Same triple structure as apply and no-op repair paths.
        assert module_state.version == "0.83.0"
        assert module_state.commit_sha == new_sha
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""
        assert module_state.embedded_at != "2025-01-01T00:00:00"
