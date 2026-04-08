"""Extended tests for apply_command.py - covering helper functions and edge cases."""

from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import click
import pytest
import yaml

from quickscale_cli.backups_contract import (
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
)
from quickscale_cli.social_contract import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_cli.commands.apply_command import (
    EmbedModulesResult,
    _apply_mutable_config,
    _check_immutable_config_changes,
    _check_output_directory,
    _commit_pending_config_changes,
    _determine_output_path,
    _display_config_summary,
    _display_next_steps,
    _embed_module,
    _embed_modules_step,
    _ensure_backups_gitignore_rules,
    _execute_apply_steps,
    _generate_project,
    _generate_with_existing_config,
    _git_commit,
    _handle_delta_and_existing_state,
    _regenerate_managed_wiring_for_apply,
    _init_git,
    _init_git_with_config,
    _load_and_validate_config,
    _load_module_manifests,
    _normalize_backups_gitignore_entry,
    _prepare_apply_context,
    _run_command,
    _run_migrations,
    _run_migrations_in_docker,
    _run_poetry_lock,
    _run_poetry_install,
    _run_post_generation_steps,
    _render_analytics_env_example_block,
    _save_project_state,
    _sync_project_module_dependencies_for_apply,
    _start_docker,
    _sync_analytics_env_example,
    _sync_notifications_env_example,
    _update_module_config_in_state,
)
from quickscale_cli.schema.state_schema import ProjectState, QuickScaleState
from quickscale_core.generator import ProjectGenerator
from quickscale_core.manifest.loader import ManifestError


def _run_git(project_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command for apply checkpoint regression tests."""
    return subprocess.run(
        ["git", *args],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_apply_git_repo(project_path: Path) -> None:
    """Create a minimal repo with tracked QuickScale-managed files."""
    (project_path / ".quickscale").mkdir(parents=True, exist_ok=True)
    (project_path / "quickscale.yml").write_text(
        'version: "1"\n'
        "project:\n"
        "  slug: myapp\n"
        "  package: myapp\n"
        "  theme: showcase_html\n"
        "docker:\n"
        "  start: false\n"
    )
    (project_path / ".quickscale" / "state.yml").write_text(
        'version: "1"\n'
        "project:\n"
        "  slug: myapp\n"
        "  package: myapp\n"
        "  theme: showcase_html\n"
        '  created_at: "2025-01-01T00:00:00"\n'
        '  last_applied: "2025-01-01T00:00:00"\n'
        "modules: {}\n"
    )

    _run_git(project_path, "init")
    _run_git(project_path, "config", "user.email", "quickscale-tests@example.com")
    _run_git(project_path, "config", "user.name", "QuickScale Tests")
    _run_git(project_path, "add", "quickscale.yml", ".quickscale/state.yml")
    _run_git(project_path, "commit", "-m", "initial")


def _install_failing_pre_commit_hook(project_path: Path) -> None:
    """Install a hook that makes checkpoint commits fail deterministically."""
    hook_path = project_path / ".git" / "hooks" / "pre-commit"
    hook_path.write_text("#!/bin/sh\nexit 1\n")
    hook_path.chmod(0o755)


# ============================================================================
# _run_command
# ============================================================================


class TestRunCommand:
    """Tests for _run_command helper"""

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")
        success, output = _run_command(["echo", "hi"], Path("."), "Test cmd")
        assert success is True
        assert output == "output"

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_failure(self, mock_run):
        """Test failed command execution"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error msg")
        success, output = _run_command(["false"], Path("."), "Fail cmd")
        assert success is False
        assert "error msg" in output

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_file_not_found(self, mock_run):
        """Test command not found"""
        mock_run.side_effect = FileNotFoundError("nope")
        success, output = _run_command(["nonexistent"], Path("."), "Missing cmd")
        assert success is False
        assert "nope" in output

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_unexpected_error(self, mock_run):
        """Test unexpected exception"""
        mock_run.side_effect = RuntimeError("boom")
        success, output = _run_command(["cmd"], Path("."), "Error cmd")
        assert success is False
        assert "boom" in output

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_no_capture(self, mock_run):
        """Test command without capture"""
        mock_run.return_value = Mock(returncode=0, stdout=None, stderr=None)
        success, output = _run_command(["cmd"], Path("."), "No capture", capture=False)
        assert success is True
        assert output == ""


# ============================================================================
# _generate_project
# ============================================================================


class TestGenerateProject:
    """Tests for _generate_project"""

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_success(self, mock_gen_cls):
        """Test successful project generation"""
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is True

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_removed_theme_value_error_is_handled(self, mock_gen_cls):
        """Unsupported themes should be surfaced as invalid configuration."""
        mock_gen_cls.side_effect = ValueError("Invalid theme 'showcase_htmx'")
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_htmx"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_file_exists_error(self, mock_gen_cls):
        """Test FileExistsError handling"""
        mock_gen_cls.return_value.generate.side_effect = FileExistsError()
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_value_error(self, mock_gen_cls):
        """Test ValueError handling"""
        mock_gen_cls.return_value.generate.side_effect = ValueError("bad config")
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_generic_error(self, mock_gen_cls):
        """Test generic exception handling"""
        mock_gen_cls.return_value.generate.side_effect = RuntimeError("oops")
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False


# ============================================================================
# Git operations
# ============================================================================


class TestGitOperations:
    """Tests for _init_git, _git_commit"""

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_init_git_success(self, mock_run):
        """Test successful git init"""
        mock_run.return_value = (True, "")
        assert _init_git(Path("/tmp/proj")) is True

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_init_git_failure(self, mock_run):
        """Test failed git init"""
        mock_run.return_value = (False, "error")
        assert _init_git(Path("/tmp/proj")) is False

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_git_commit_success(self, mock_run):
        """Test successful git commit"""
        mock_run.return_value = (True, "")
        assert _git_commit(Path("/tmp/proj"), "msg") is True

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_git_commit_add_fails(self, mock_run):
        """Test git commit when git add fails"""
        mock_run.return_value = (False, "error")
        assert _git_commit(Path("/tmp/proj"), "msg") is False


# ============================================================================
# _embed_module
# ============================================================================


class TestEmbedModule:
    """Tests for _embed_module"""

    @patch("quickscale_cli.commands.apply_command.embed_module")
    def test_success(self, mock_embed):
        """Test successful module embedding"""
        mock_embed.return_value = True
        assert _embed_module(Path("/tmp/proj"), "auth") is True
        mock_embed.assert_called_once_with(
            module="auth",
            project_path=Path("/tmp/proj"),
            non_interactive=True,
            allow_unverifiable_auth_state=True,
            skip_auth_migration_check=False,
            sync_dependencies=False,
            install_dependencies=False,
            execution_mode="apply",
        )

    @patch("quickscale_cli.commands.apply_command.embed_module")
    def test_success_skip_auth_migration_check(self, mock_embed):
        """Test module embedding with auth migration check bypass."""
        mock_embed.return_value = True
        assert (
            _embed_module(
                Path("/tmp/proj"),
                "auth",
                skip_auth_migration_check=True,
            )
            is True
        )
        mock_embed.assert_called_once_with(
            module="auth",
            project_path=Path("/tmp/proj"),
            non_interactive=True,
            allow_unverifiable_auth_state=True,
            skip_auth_migration_check=True,
            sync_dependencies=False,
            install_dependencies=False,
            execution_mode="apply",
        )

    def test_apply_embed_defers_immediate_module_regeneration(self, tmp_path):
        """Apply embedding should skip the per-module managed-wiring pass."""
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
                "quickscale_cli.commands.module_config.regenerate_managed_wiring"
            ) as mock_regenerate,
        ):
            result = _embed_module(tmp_path, "blog")

        assert result is True
        mock_regenerate.assert_not_called()

    @patch("quickscale_cli.commands.apply_command.embed_module")
    def test_failure(self, mock_embed):
        """Test failed module embedding"""
        mock_embed.return_value = False
        assert _embed_module(Path("/tmp/proj"), "auth") is False

    @patch("quickscale_cli.commands.apply_command.embed_module")
    def test_exception(self, mock_embed):
        """Test exception during module embedding"""
        mock_embed.side_effect = RuntimeError("oops")
        assert _embed_module(Path("/tmp/proj"), "auth") is False


# ============================================================================
# _run_poetry_install / _run_migrations
# ============================================================================


class TestPostGenerationHelpers:
    """Tests for poetry install and migrations helpers"""

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_poetry_install(self, mock_run):
        """Test poetry install wrapper"""
        mock_run.return_value = (True, "")
        assert _run_poetry_install(Path("/tmp/proj")) is True

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_poetry_lock(self, mock_run):
        """Test poetry lock wrapper"""
        mock_run.return_value = (True, "")
        assert _run_poetry_lock(Path("/tmp/proj")) is True

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_migrations(self, mock_run):
        """Test run migrations wrapper"""
        mock_run.return_value = (True, "")
        assert _run_migrations(Path("/tmp/proj")) is True

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_migrations_in_docker(self, mock_run):
        """Test run migrations in docker wrapper"""
        mock_run.return_value = (True, "")
        assert _run_migrations_in_docker(Path("/tmp/proj")) is True


# ============================================================================
# _start_docker
# ============================================================================


class TestStartDocker:
    """Tests for _start_docker"""

    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_start_docker_no_verbose(self, mock_run):
        """Test Docker start without verbose"""
        mock_run.return_value = (True, "")
        assert _start_docker(Path("/tmp/proj"), build=True, verbose=False) is True
        mock_run.assert_called_once_with(
            ["quickscale", "up", "--build"],
            Path("/tmp/proj"),
            "Starting Docker services",
            capture=False,
        )

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_start_docker_verbose_success(self, mock_run):
        """Test Docker start with verbose output"""
        mock_run.return_value = Mock(returncode=0)
        assert _start_docker(Path("/tmp/proj"), build=True, verbose=True) is True

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_start_docker_verbose_failure(self, mock_run):
        """Test Docker start verbose failure"""
        mock_run.return_value = Mock(returncode=1)
        assert _start_docker(Path("/tmp/proj"), build=True, verbose=True) is False

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_start_docker_verbose_file_not_found(self, mock_run):
        """Test Docker start verbose command not found"""
        mock_run.side_effect = FileNotFoundError()
        assert _start_docker(Path("/tmp/proj"), build=True, verbose=True) is False

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    def test_start_docker_verbose_exception(self, mock_run):
        """Test Docker start verbose generic exception"""
        mock_run.side_effect = RuntimeError("boom")
        assert _start_docker(Path("/tmp/proj"), build=True, verbose=True) is False


# ============================================================================
# _load_module_manifests
# ============================================================================


class TestLoadModuleManifests:
    """Tests for _load_module_manifests"""

    @patch("quickscale_cli.commands.apply_command.get_manifest_for_module")
    def test_loads_manifests(self, mock_get):
        """Test loading module manifests"""
        mock_manifest = Mock()
        mock_get.return_value = mock_manifest
        result = _load_module_manifests(Path("/tmp"), ["auth", "blog"])
        assert "auth" in result
        assert "blog" in result

    @patch("quickscale_cli.commands.apply_command.get_manifest_for_module")
    def test_skips_missing_manifests(self, mock_get):
        """Test skipping modules without manifests"""
        mock_get.return_value = None
        result = _load_module_manifests(Path("/tmp"), ["auth"])
        assert result == {}

    @patch("quickscale_cli.commands.apply_command.get_manifest_for_module")
    def test_strict_manifest_errors_propagate(self, mock_get):
        """Strict manifest mode should fail instead of silently degrading."""
        mock_get.side_effect = ManifestError("bad manifest", "auth")

        with pytest.raises(ManifestError, match="auth"):
            _load_module_manifests(Path("/tmp"), ["auth"], strict=True)


# ============================================================================
# _apply_mutable_config / _check_immutable_config_changes
# ============================================================================


class TestConfigChanges:
    """Tests for mutable/immutable config change handling"""

    def test_apply_mutable_no_changes(self):
        """Test apply mutable when no changes"""
        delta = Mock()
        delta.has_mutable_config_changes = False
        assert _apply_mutable_config(Path("/tmp"), delta, {}) is True

    @patch("quickscale_cli.commands.apply_command.apply_mutable_config_changes")
    def test_apply_mutable_success(self, mock_apply):
        """Test successful mutable config application"""
        mock_apply.return_value = [("SETTING", True, "Updated")]
        delta = Mock()
        delta.has_mutable_config_changes = True
        change = Mock()
        change.django_setting = "MY_SETTING"
        change.new_value = "new_val"
        delta.get_all_mutable_changes.return_value = [("auth", change)]

        result = _apply_mutable_config(Path("/tmp"), delta, {})
        assert result is True

    @patch("quickscale_cli.commands.apply_command.apply_mutable_config_changes")
    def test_apply_mutable_failure(self, mock_apply):
        """Test failed mutable config application"""
        mock_apply.return_value = [("SETTING", False, "Failed")]
        delta = Mock()
        delta.has_mutable_config_changes = True
        change = Mock()
        change.django_setting = "MY_SETTING"
        change.new_value = "new_val"
        delta.get_all_mutable_changes.return_value = [("auth", change)]

        result = _apply_mutable_config(Path("/tmp"), delta, {})
        assert result is False

    def test_check_immutable_no_changes(self):
        """Test no immutable changes"""
        delta = Mock()
        delta.has_immutable_config_changes = False
        assert _check_immutable_config_changes(delta) is True

    def test_check_immutable_has_changes(self):
        """Test immutable changes detected"""
        delta = Mock()
        delta.has_immutable_config_changes = True
        change = Mock()
        change.option_name = "auth_method"
        change.old_value = "email"
        change.new_value = "username"
        delta.get_all_immutable_changes.return_value = [("auth", change)]

        result = _check_immutable_config_changes(delta)
        assert result is False


# ============================================================================
# _update_module_config_in_state
# ============================================================================


class TestUpdateModuleConfigInState:
    """Tests for _update_module_config_in_state"""

    def test_updates_mutable_options(self):
        """Test updating module options after mutable changes"""
        state = Mock()
        state.modules = {"auth": Mock(options={"key": "old"})}
        config = Mock()
        delta = Mock()
        module_delta = Mock()
        module_delta.has_mutable_changes = True
        change = Mock()
        change.option_name = "key"
        change.new_value = "new"
        module_delta.mutable_changes = [change]
        delta.config_deltas = {"auth": module_delta}

        _update_module_config_in_state(state, config, delta)
        assert state.modules["auth"].options["key"] == "new"

    def test_no_mutable_changes(self):
        """Test no-op when no mutable changes"""
        state = Mock()
        state.modules = {"auth": Mock(options={"key": "old"})}
        delta = Mock()
        module_delta = Mock()
        module_delta.has_mutable_changes = False
        delta.config_deltas = {"auth": module_delta}

        _update_module_config_in_state(state, Mock(), delta)
        assert state.modules["auth"].options["key"] == "old"


# ============================================================================
# _load_and_validate_config
# ============================================================================


class TestLoadAndValidateConfig:
    """Tests for _load_and_validate_config"""

    def test_file_not_found(self, tmp_path):
        """Test config file not found"""
        with pytest.raises(click.Abort):
            _load_and_validate_config(tmp_path / "nonexistent.yml")

    def test_invalid_config(self, tmp_path):
        """Test invalid YAML config"""
        config = tmp_path / "quickscale.yml"
        config.write_text("version: '1'\n")
        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_valid_config(self, tmp_path):
        """Test valid config loading"""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n  theme: showcase_html\ndocker:\n  start: false\n'
        )
        result = _load_and_validate_config(config)
        assert result.project.slug == "myapp"

    def test_valid_config_with_empty_backups_module_uses_defaults(self, tmp_path):
        """Empty backups block should pass apply validation with default values."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  backups:\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)

        assert result.modules["backups"].options == {}

    @pytest.mark.parametrize("placeholder_module", ["billing", "teams"])
    def test_placeholder_modules_are_rejected_on_load(
        self, tmp_path, placeholder_module
    ):
        """Apply should reject placeholder modules even if they are hand-edited in."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            f"  {placeholder_module}:\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_legacy_backups_secrets_are_sanitized_on_load(self, tmp_path):
        """Legacy raw backup secrets should be rewritten to env-var references."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  backups:\n"
            "    target_mode: private_remote\n"
            "    remote_bucket_name: private-bucket\n"
            "    remote_region_name: auto\n"
            "    remote_access_key_id: legacy-key\n"
            "    remote_secret_access_key: legacy-secret\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert (
            result.modules["backups"].options["remote_access_key_id_env_var"]
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        assert (
            result.modules["backups"].options["remote_secret_access_key_env_var"]
            == DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )
        assert "legacy-key" not in rewritten
        assert "legacy-secret" not in rewritten
        assert (
            "remote_access_key_id_env_var: QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
            in rewritten
        )
        assert (
            "remote_secret_access_key_env_var: QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
            in rewritten
        )

    def test_auth_legacy_keys_are_sanitized_on_load(self, tmp_path):
        """Legacy auth keys should be pruned from quickscale.yml during apply load."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "    registration_enabled: true\n"
            "    allow_registration: false\n"
            "    social_providers:\n"
            "      - google\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert result.modules["auth"].options == {"registration_enabled": True}
        assert "allow_registration" not in rewritten
        assert "social_providers" not in rewritten
        assert "registration_enabled: true" in rewritten

    def test_legacy_notifications_secrets_are_sanitized_on_load(self, tmp_path):
        """Legacy notification secrets should be rewritten to env-var references."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  notifications:\n"
            "    resend_domain: mg.example.com\n"
            "    resend_api_key: raw-secret\n"
            "    webhook_secret: webhook-secret\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert (
            result.modules["notifications"].options["resend_api_key_env_var"]
            == "RESEND_API_KEY"
        )
        assert (
            result.modules["notifications"].options["webhook_secret_env_var"]
            == "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
        )
        assert "raw-secret" not in rewritten
        assert "webhook-secret" not in rewritten
        assert "resend_api_key_env_var: RESEND_API_KEY" in rewritten
        assert (
            "webhook_secret_env_var: QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
            in rewritten
        )

    def test_production_targeted_notifications_require_complete_live_config(
        self,
        tmp_path,
    ):
        """Production-targeted notifications configs must fail before apply."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  notifications:\n"
            "    sender_name: Ops\n"
            "    sender_email: ops@example.com\n"
            "    resend_domain: mg.example.com\n"
            '    resend_api_key_env_var: ""\n'
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_analytics_module_options_are_normalized_on_load(self, tmp_path):
        """Analytics provider and host values should be canonicalized on apply load."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  analytics:\n"
            "    provider: PostHog\n"
            "    posthog_api_key_env_var: ' OPS_POSTHOG_API_KEY '\n"
            "    posthog_host_env_var: ' OPS_POSTHOG_HOST '\n"
            "    posthog_host: eu.i.posthog.com/\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert result.modules["analytics"].options["provider"] == "posthog"
        assert (
            result.modules["analytics"].options["posthog_api_key_env_var"]
            == "OPS_POSTHOG_API_KEY"
        )
        assert (
            result.modules["analytics"].options["posthog_host_env_var"]
            == "OPS_POSTHOG_HOST"
        )
        assert (
            result.modules["analytics"].options["posthog_host"]
            == "https://eu.i.posthog.com"
        )
        assert "provider: posthog" in rewritten
        assert "https://eu.i.posthog.com" in rewritten

    def test_analytics_module_requires_valid_env_var_names(self, tmp_path):
        """Apply should reject analytics env-var references that are not env vars."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  analytics:\n"
            "    posthog_api_key_env_var: ops-posthog-api-key\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_social_module_options_are_normalized_on_load(self, tmp_path):
        """Social aliases and casing should be canonicalized during apply load."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  social:\n"
            "    layout_variant: GRID\n"
            "    provider_allowlist:\n"
            "      - Twitter\n"
            "      - YouTube\n"
            "      - twitter\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert result.modules["social"].options["layout_variant"] == "grid"
        assert result.modules["social"].options["provider_allowlist"] == [
            "x",
            "youtube",
        ]
        assert "layout_variant: grid" in rewritten
        assert "Twitter" not in rewritten

    def test_social_module_requires_at_least_one_enabled_surface(self, tmp_path):
        """Apply should reject social configs that disable every public surface."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  social:\n"
            "    link_tree_enabled: false\n"
            "    embeds_enabled: false\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_read_error(self, tmp_path):
        """Test generic read error"""
        config = tmp_path / "quickscale.yml"
        config.write_text("valid content")
        with patch.object(Path, "read_text", side_effect=OSError("disk error")):
            with pytest.raises(click.Abort):
                _load_and_validate_config(config)


class TestPrepareApplyContext:
    """Tests for apply preflight context loading."""

    @pytest.mark.parametrize("placeholder_module", ["billing", "teams"])
    def test_rejects_placeholder_modules_in_existing_state(
        self, tmp_path, placeholder_module
    ):
        """Apply should abort when legacy state still references placeholders."""
        project_path = tmp_path / "myapp"
        project_path.mkdir()
        config_path = project_path / "quickscale.yml"
        config_path.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "docker:\n"
            "  start: false\n"
        )
        (project_path / ".quickscale").mkdir()
        (project_path / ".quickscale" / "state.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            f"  {placeholder_module}:\n"
            '    version: "0.1.0"\n'
        )

        with pytest.raises(click.Abort):
            _prepare_apply_context(config_path)

    def test_rejects_malformed_installed_manifests_before_delta(self, tmp_path):
        """Apply should fail before delta computation when an installed manifest is bad."""
        project_path = tmp_path / "myapp"
        project_path.mkdir()
        config_path = project_path / "quickscale.yml"
        config_path.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "docker:\n"
            "  start: false\n"
        )
        (project_path / ".quickscale").mkdir()
        (project_path / ".quickscale" / "state.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            '    version: "0.70.0"\n'
        )
        module_dir = project_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        with pytest.raises(click.Abort):
            _prepare_apply_context(config_path)

    def test_merges_pending_post_embed_recovery_without_authoritative_state(
        self, tmp_path
    ):
        """Apply should treat recovery snapshots as retry context, not a no-state project."""
        project_path = tmp_path / "myapp"
        project_path.mkdir()
        config_path = project_path / "quickscale.yml"
        config_path.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "docker:\n"
            "  start: false\n"
        )
        (project_path / ".quickscale").mkdir()
        (project_path / ".quickscale" / "apply-recovery.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            '  created_at: "2025-01-01T00:00:00"\n'
            '  last_applied: "2025-01-01T00:00:00"\n'
            "modules:\n"
            "  auth:\n"
            '    version: "0.82.0"\n'
            "    commit_sha:\n"
            '    embedded_at: "2025-01-01T00:00:00"\n'
            "    options: {}\n"
        )
        module_dir = project_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        ctx = _prepare_apply_context(config_path)

        assert ctx.has_pending_post_embed_recovery is True
        assert ctx.had_existing_state is False
        assert ctx.existing_state is not None
        assert list(ctx.existing_state.modules) == ["auth"]
        assert ctx.delta.has_changes is False


# ============================================================================
# _determine_output_path
# ============================================================================


class TestDetermineOutputPath:
    """Tests for _determine_output_path"""

    def test_config_in_project_dir(self, tmp_path):
        """Test config inside project directory"""
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        config_path = project_dir / "quickscale.yml"
        config_path.touch()
        result = _determine_output_path(config_path, "myapp")
        assert result == project_dir

    def test_config_outside_project_dir(self, tmp_path, monkeypatch):
        """Test config outside project directory"""
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "quickscale.yml"
        config_path.touch()
        result = _determine_output_path(config_path, "myapp")
        assert result == tmp_path / "myapp"


# ============================================================================
# _display_config_summary
# ============================================================================


class TestDisplayConfigSummary:
    """Tests for _display_config_summary"""

    def test_with_modules(self):
        """Test config summary display with modules"""
        config = Mock()
        config.project.slug = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(), "blog": Mock()}
        config.docker.start = True
        config.docker.build = True
        _display_config_summary(config)

    def test_without_modules(self):
        """Test config summary display without modules"""
        config = Mock()
        config.project.slug = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        config.docker.start = False
        config.docker.build = False
        _display_config_summary(config)


# ============================================================================
# _handle_delta_and_existing_state
# ============================================================================


class TestHandleDeltaAndExistingState:
    """Tests for _handle_delta_and_existing_state"""

    def test_no_existing_state(self):
        """Test with no existing state (new project)"""
        delta = Mock()
        _handle_delta_and_existing_state(delta, None)
        # Should return without doing anything

    def test_no_changes(self):
        """Test with matching config and state"""
        delta = Mock()
        delta.has_changes = False
        state = Mock()

        with pytest.raises(click.Abort):
            _handle_delta_and_existing_state(delta, state)

    def test_no_changes_with_pending_post_embed_recovery_continues(self):
        """Pending post-embed recovery should bypass the normal no-op abort."""
        delta = Mock()
        delta.has_changes = False
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.format_delta", return_value="none"
        ):
            _handle_delta_and_existing_state(
                delta,
                state,
                has_pending_post_embed_recovery=True,
            )

    def test_config_driven_module_removals_abort(self, capsys):
        """Apply must reject config-driven removals and defer to quickscale remove."""
        delta = Mock()
        delta.has_changes = True
        delta.modules_to_remove = ["auth", "blog"]
        delta.has_immutable_config_changes = False
        delta.theme_changed = False
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.format_delta", return_value="changes"
        ):
            with pytest.raises(click.Abort):
                _handle_delta_and_existing_state(delta, state)

        output = capsys.readouterr().out
        assert "config-driven module removals are not supported" in output
        assert "quickscale remove auth" in output
        assert "quickscale remove blog" in output

    def test_immutable_changes_abort(self):
        """Test abort on immutable changes"""
        delta = Mock()
        delta.has_changes = True
        delta.modules_to_remove = []
        delta.has_immutable_config_changes = True
        delta.theme_changed = False
        change = Mock()
        change.option_name = "method"
        change.old_value = "email"
        change.new_value = "username"
        delta.get_all_immutable_changes.return_value = [("auth", change)]
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.format_delta", return_value="changes"
        ):
            with pytest.raises(click.Abort):
                _handle_delta_and_existing_state(delta, state)

    def test_theme_changed_user_declines(self):
        """Test theme change warning when user declines"""
        delta = Mock()
        delta.has_changes = True
        delta.modules_to_remove = []
        delta.has_immutable_config_changes = False
        delta.theme_changed = True
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.format_delta", return_value="changes"
        ):
            with patch(
                "quickscale_cli.commands.apply_command.click.confirm",
                return_value=False,
            ):
                with pytest.raises(click.Abort):
                    _handle_delta_and_existing_state(delta, state)

    def test_theme_changed_user_accepts(self):
        """Test theme change warning when user accepts"""
        delta = Mock()
        delta.has_changes = True
        delta.modules_to_remove = []
        delta.has_immutable_config_changes = False
        delta.theme_changed = True
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.click.confirm", return_value=True
        ):
            with patch(
                "quickscale_cli.commands.apply_command.format_delta",
                return_value="changes",
            ):
                _handle_delta_and_existing_state(delta, state)


# ============================================================================
# _check_output_directory
# ============================================================================


class TestCheckOutputDirectory:
    """Tests for _check_output_directory"""

    def test_directory_not_exists(self, tmp_path):
        """Test when output directory doesn't exist"""
        output = tmp_path / "newproject"
        _check_output_directory(output, None, False)

    def test_empty_directory(self, tmp_path):
        """Test when output directory is empty"""
        output = tmp_path / "emptydir"
        output.mkdir()
        _check_output_directory(output, None, False)

    def test_existing_project(self, tmp_path):
        """Test when existing project detected"""
        output = tmp_path / "existing"
        output.mkdir()
        (output / "manage.py").touch()
        state = Mock()
        _check_output_directory(output, state, False)

    def test_directory_with_only_config(self, tmp_path):
        """Test directory with only quickscale.yml"""
        output = tmp_path / "proj"
        output.mkdir()
        (output / "quickscale.yml").touch()
        _check_output_directory(output, None, False)

    def test_non_empty_dir_no_force(self, tmp_path):
        """Test non-empty directory without force"""
        output = tmp_path / "proj"
        output.mkdir()
        (output / "file.txt").touch()
        with pytest.raises(click.Abort):
            _check_output_directory(output, None, False)

    def test_non_empty_dir_with_force(self, tmp_path):
        """Test non-empty directory with force"""
        output = tmp_path / "proj"
        output.mkdir()
        (output / "file.txt").touch()
        _check_output_directory(output, None, True)


# ============================================================================
# _init_git_with_config
# ============================================================================


class TestInitGitWithConfig:
    """Tests for _init_git_with_config"""

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command._init_git")
    def test_success(self, mock_init, mock_run, mock_commit):
        """Test successful git init with config"""
        mock_init.return_value = True
        mock_run.return_value = Mock(returncode=0)
        mock_commit.return_value = True
        _init_git_with_config(Path("/tmp/proj"))

    @patch("quickscale_cli.commands.apply_command._init_git")
    def test_git_init_fails(self, mock_init):
        """Test when git init fails"""
        mock_init.return_value = False
        _init_git_with_config(Path("/tmp/proj"))
        # Should not raise

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command._init_git")
    def test_commit_fails(self, mock_init, mock_run, mock_commit):
        """Test when initial commit fails"""
        mock_init.return_value = True
        mock_run.return_value = Mock(returncode=0)
        mock_commit.return_value = False
        _init_git_with_config(Path("/tmp/proj"))
        # Should not raise


# ============================================================================
# _commit_pending_config_changes
# ============================================================================


class TestCommitPendingConfigChanges:
    """Tests for _commit_pending_config_changes"""

    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_no_op_when_working_directory_is_clean(self, mock_clean):
        """Test that function does nothing when working directory is already clean"""
        mock_clean.return_value = True

        with patch("quickscale_cli.commands.apply_command.subprocess.run") as mock_run:
            _commit_pending_config_changes(Path("/tmp/test"))

        mock_run.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_stages_and_commits_config_files_when_dirty(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Test that config files are staged and committed when working directory is dirty"""
        mock_clean.return_value = False
        # First three subprocess calls inspect staged/unstaged/untracked changes.
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="quickscale.yml\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]
        mock_run_command.side_effect = [(True, ""), (True, "")]

        _commit_pending_config_changes(Path("/tmp/test"))

        first_checkpoint_call = mock_run_command.call_args_list[0]
        assert first_checkpoint_call.args[0] == [
            "git",
            "add",
            "--",
            "quickscale.yml",
        ]
        assert first_checkpoint_call.args[1] == Path("/tmp/test")
        assert (
            first_checkpoint_call.args[2]
            == "Staging pending QuickScale configuration changes"
        )

        second_checkpoint_call = mock_run_command.call_args_list[1]
        assert second_checkpoint_call.args == (
            [
                "git",
                "commit",
                "-m",
                "Update QuickScale configuration",
                "--",
                "quickscale.yml",
            ],
            Path("/tmp/test"),
            "Committing pending QuickScale configuration changes",
        )

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_excludes_apply_recovery_snapshot_from_checkpoint_pathspec(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Transient apply recovery files may coexist, but never enter the checkpoint commit."""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(
                returncode=0,
                stdout=(
                    "quickscale.yml\n"
                    ".quickscale/state.yml\n"
                    ".quickscale/apply-recovery.yml\n"
                ),
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
        ]
        mock_run_command.side_effect = [(True, ""), (True, "")]

        _commit_pending_config_changes(Path("/tmp/test"))

        first_checkpoint_call = mock_run_command.call_args_list[0]
        assert first_checkpoint_call.args[0] == [
            "git",
            "add",
            "--",
            "quickscale.yml",
            ".quickscale/state.yml",
        ]

        second_checkpoint_call = mock_run_command.call_args_list[1]
        assert second_checkpoint_call.args[0] == [
            "git",
            "commit",
            "-m",
            "Update QuickScale configuration",
            "--",
            "quickscale.yml",
            ".quickscale/state.yml",
        ]

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_only_transient_apply_recovery_dirty_skips_checkpoint_commit(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Pending recovery snapshots alone should not trigger a synthetic checkpoint commit."""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout=".quickscale/apply-recovery.yml\n", stderr=""),
        ]

        _commit_pending_config_changes(Path("/tmp/test"))

        mock_run_command.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_aborts_when_unrelated_changes_are_already_staged(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Apply must not create its synthetic commit with unrelated staged work."""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(
                returncode=0,
                stdout="quickscale.yml\nREADME.md\n",
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        with pytest.raises(click.Abort):
            _commit_pending_config_changes(Path("/tmp/test"))

        mock_run_command.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_aborts_when_unrelated_unstaged_changes_are_present(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Apply must abort when unrelated tracked changes remain unstaged."""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="README.md\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        with pytest.raises(click.Abort):
            _commit_pending_config_changes(Path("/tmp/test"))

        mock_run_command.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_aborts_when_unrelated_untracked_changes_are_present(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Apply must abort when unrelated untracked files are present."""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="quickscale.yml\n", stderr=""),
            Mock(returncode=0, stdout="notes.txt\n", stderr=""),
        ]

        with pytest.raises(click.Abort):
            _commit_pending_config_changes(Path("/tmp/test"))

        mock_run_command.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_command")
    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    def test_commits_both_quickscale_yml_and_state_yml(
        self, mock_clean, mock_subprocess, mock_run_command
    ):
        """Test that both quickscale.yml and .quickscale/state.yml changes are committed"""
        mock_clean.return_value = False
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout=".quickscale/state.yml\n", stderr=""),
            Mock(
                returncode=0,
                stdout="quickscale.yml\n",
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
        ]
        mock_run_command.side_effect = [(True, ""), (True, "")]

        _commit_pending_config_changes(Path("/tmp/test"))

        assert mock_run_command.call_count == 2

    def test_restores_preexisting_staged_state_when_checkpoint_commit_fails(
        self, tmp_path
    ):
        """Failed synthetic checkpoints must not leave apply-staged managed files behind."""
        _init_apply_git_repo(tmp_path)

        quickscale_config = tmp_path / "quickscale.yml"
        quickscale_config.write_text(
            quickscale_config.read_text() + "modules:\n  auth:\n"
        )
        _run_git(tmp_path, "add", "quickscale.yml")

        state_path = tmp_path / ".quickscale" / "state.yml"
        state_path.write_text(state_path.read_text() + "# pending state update\n")

        _install_failing_pre_commit_hook(tmp_path)

        with pytest.raises(click.Abort):
            _commit_pending_config_changes(tmp_path)

        staged_paths = _run_git(tmp_path, "diff", "--cached", "--name-only").stdout
        unstaged_paths = _run_git(tmp_path, "diff", "--name-only").stdout

        assert staged_paths.splitlines() == ["quickscale.yml"]
        assert unstaged_paths.splitlines() == [".quickscale/state.yml"]

    def test_checkpoint_commit_does_not_include_apply_recovery_snapshot(self, tmp_path):
        """Synthetic pre-embed commits must never absorb transient recovery snapshots."""
        _init_apply_git_repo(tmp_path)

        quickscale_config = tmp_path / "quickscale.yml"
        quickscale_config.write_text(
            quickscale_config.read_text() + "modules:\n  auth:\n"
        )

        state_path = tmp_path / ".quickscale" / "state.yml"
        state_path.write_text(state_path.read_text() + "# pending state update\n")

        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        recovery_path.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            '  created_at: "2025-01-01T00:00:00"\n'
            '  last_applied: "2025-01-02T00:00:00"\n'
            "modules:\n"
            "  auth:\n"
            '    version: "0.82.0"\n'
            "    commit_sha:\n"
            '    embedded_at: "2025-01-01T00:00:00"\n'
            "    options: {}\n"
        )

        _commit_pending_config_changes(tmp_path)

        commit_paths = set(
            _run_git(
                tmp_path,
                "show",
                "--pretty=format:",
                "--name-only",
                "HEAD",
            ).stdout.splitlines()
        )
        status_output = _run_git(tmp_path, "status", "--short").stdout.splitlines()

        assert "quickscale.yml" in commit_paths
        assert ".quickscale/state.yml" in commit_paths
        assert ".quickscale/apply-recovery.yml" not in commit_paths
        assert "?? .quickscale/apply-recovery.yml" in status_output

    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._commit_pending_config_changes")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_execute_apply_steps_aborts_before_embed_when_pre_embed_commit_aborts(
        self,
        mock_generate_new_project,
        mock_commit_pending,
        mock_embed_modules_step,
    ):
        """Existing-project apply should stop before subtree embed on staged-scope violations."""
        mock_commit_pending.side_effect = click.Abort()

        ctx = Mock()
        ctx.existing_state = Mock()
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with pytest.raises(click.Abort):
            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=False,
                no_modules=False,
                verbose_docker=False,
            )

        mock_generate_new_project.assert_not_called()
        mock_embed_modules_step.assert_not_called()


# ============================================================================
# _embed_modules_step
# ============================================================================


class TestEmbedModulesStep:
    """Tests for _embed_modules_step"""

    def test_no_modules(self):
        """Test with no modules flag"""
        result = _embed_modules_step(Path("/tmp"), ["auth"], True, None)
        assert result == EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )

    def test_empty_modules_list(self):
        """Test with empty modules list"""
        result = _embed_modules_step(Path("/tmp"), [], False, None)
        assert result == EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )

    def test_empty_modules_existing_state(self):
        """Test empty modules with existing state"""
        result = _embed_modules_step(Path("/tmp"), [], False, Mock())
        assert result == EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_successful_embed(self, mock_embed, mock_commit):
        """Test successful module embedding"""
        mock_embed.return_value = True
        mock_commit.return_value = True
        result = _embed_modules_step(Path("/tmp"), ["auth"], False, None)
        assert result == EmbedModulesResult(
            success=True,
            embedded_modules=["auth"],
            failed_module=None,
        )
        mock_embed.assert_called_once_with(
            Path("/tmp"),
            "auth",
            skip_auth_migration_check=True,
        )

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_successful_embed_aborts_when_checkpoint_commit_fails(
        self, mock_embed, mock_commit
    ):
        """Apply must hard-stop when a module checkpoint commit fails."""
        mock_embed.return_value = True
        mock_commit.return_value = False

        with pytest.raises(click.Abort):
            _embed_modules_step(Path("/tmp"), ["auth"], False, None)

        mock_commit.assert_called_once_with(Path("/tmp"), "Add module: auth")

    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_failed_embed(self, mock_embed, mock_commit, mock_clean):
        """Test failed module embedding fails fast."""
        mock_embed.return_value = False
        mock_clean.return_value = False
        mock_commit.return_value = True
        result = _embed_modules_step(Path("/tmp"), ["auth"], False, None)
        assert result == EmbedModulesResult(
            success=False,
            embedded_modules=[],
            failed_module="auth",
        )

    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_failed_embed_aborts_when_partial_checkpoint_commit_fails(
        self, mock_embed, mock_commit, mock_clean
    ):
        """Apply must hard-stop when the partial embed checkpoint cannot be committed."""
        mock_embed.return_value = False
        mock_clean.return_value = False
        mock_commit.return_value = False

        with pytest.raises(click.Abort):
            _embed_modules_step(Path("/tmp"), ["auth"], False, None)

        mock_commit.assert_called_once_with(
            Path("/tmp"),
            "Partial module: auth (incomplete)",
        )

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_existing_project_does_not_skip_auth_guard(self, mock_embed, mock_commit):
        """Existing projects should still run auth migration guardrail."""
        mock_embed.return_value = True
        mock_commit.return_value = True

        _embed_modules_step(Path("/tmp"), ["auth"], False, Mock())

        mock_embed.assert_called_once_with(
            Path("/tmp"),
            "auth",
            skip_auth_migration_check=False,
        )


# ============================================================================
# _run_post_generation_steps
# ============================================================================


class TestRunPostGenerationSteps:
    """Tests for _run_post_generation_steps"""

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_all_succeed(self, mock_poetry, mock_migrate, mock_lock):
        """Test when all steps succeed"""
        mock_lock.return_value = True
        mock_poetry.return_value = True
        mock_migrate.return_value = True
        assert _run_post_generation_steps(Path("/tmp")) is True

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_poetry_lock_fails(self, mock_poetry, mock_migrate, mock_lock):
        """Test when poetry lock fails"""
        mock_lock.return_value = False
        mock_poetry.return_value = True
        mock_migrate.return_value = True

        assert _run_post_generation_steps(Path("/tmp")) is False
        mock_poetry.assert_not_called()
        mock_migrate.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_poetry_install_fails(self, mock_poetry, mock_migrate, mock_lock):
        """Test when poetry install fails"""
        mock_lock.return_value = True
        mock_poetry.return_value = False
        mock_migrate.return_value = True
        assert _run_post_generation_steps(Path("/tmp")) is False
        mock_migrate.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_migrations_fail(self, mock_poetry, mock_migrate, mock_lock):
        """Test when migrations fail"""
        mock_lock.return_value = True
        mock_poetry.return_value = True
        mock_migrate.return_value = False
        assert _run_post_generation_steps(Path("/tmp")) is False

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_skip_migrations(self, mock_poetry, mock_migrate, mock_lock):
        """Test migration step can be deferred."""
        mock_lock.return_value = True
        mock_poetry.return_value = True
        assert _run_post_generation_steps(Path("/tmp"), run_migrations=False) is True
        mock_migrate.assert_not_called()


class TestSyncProjectModuleDependenciesForApply:
    """Tests for apply-time batch dependency synchronization."""

    @patch("quickscale_cli.commands.apply_command.sync_project_module_dependencies")
    def test_syncs_all_configured_modules(self, mock_sync):
        qs_config = Mock()
        qs_config.modules = {
            "auth": Mock(options={"registration_enabled": True}),
            "storage": Mock(options={"backend": "local"}),
        }
        mock_sync.return_value = Mock(
            changed=True,
            added_package_dependencies=["django-allauth"],
            added_path_dependencies=["quickscale-module-auth"],
        )

        result = _sync_project_module_dependencies_for_apply(
            Path("/tmp/proj"), qs_config
        )

        assert result is True
        mock_sync.assert_called_once_with(
            Path("/tmp/proj"),
            {
                "auth": {"registration_enabled": True},
                "storage": {"backend": "local"},
            },
        )

    @patch("quickscale_cli.commands.apply_command.sync_project_module_dependencies")
    def test_sync_failure_returns_false(self, mock_sync):
        qs_config = Mock()
        qs_config.modules = {"auth": Mock(options={})}
        mock_sync.side_effect = ManifestError("bad manifest", "auth")

        result = _sync_project_module_dependencies_for_apply(
            Path("/tmp/proj"), qs_config
        )

        assert result is False


# ============================================================================
# _save_project_state
# ============================================================================


class TestSaveProjectState:
    """Tests for _save_project_state"""

    def test_new_project_state(self, tmp_path):
        """Test saving state for new project"""
        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={"key": "val"})}
        delta = Mock()
        delta.config_deltas = {}

        assert _save_project_state(tmp_path, config, None, ["auth"], delta) is True
        assert (tmp_path / ".quickscale" / "state.yml").exists()

    def test_existing_project_state(self, tmp_path):
        """Test saving state for existing project"""
        # Pre-create state dir
        (tmp_path / ".quickscale").mkdir()

        existing_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            ),
            modules={},
        )

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"blog": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        assert (
            _save_project_state(tmp_path, config, existing_state, ["blog"], delta)
            is True
        )

    def test_save_state_error(self, tmp_path):
        """Test state save error handling"""
        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        delta = Mock()
        delta.config_deltas = {}

        with patch("quickscale_cli.commands.apply_command.StateManager") as mock_sm:
            mock_sm.return_value.save.side_effect = OSError("write error")
            assert _save_project_state(tmp_path, config, None, [], delta) is False

    def test_backups_state_save_sanitizes_legacy_secret_values(self, tmp_path):
        """Backups state should persist env-var references, not raw secrets."""
        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {
            "backups": Mock(
                options={
                    "target_mode": "private_remote",
                    "remote_bucket_name": "private-bucket",
                    "remote_region_name": "auto",
                    "remote_access_key_id": "legacy-key",
                    "remote_secret_access_key": "legacy-secret",
                }
            )
        }
        delta = Mock()
        delta.config_deltas = {}

        assert _save_project_state(tmp_path, config, None, ["backups"], delta) is True

        state_text = (tmp_path / ".quickscale" / "state.yml").read_text()
        assert "legacy-key" not in state_text
        assert "legacy-secret" not in state_text
        assert "remote_access_key_id_env_var" in state_text
        assert "remote_secret_access_key_env_var" in state_text

    def test_state_and_legacy_config_versions_sync_from_embedded_manifest(
        self, tmp_path
    ):
        """Apply state should use embedded manifest versions and mirror them to config."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            "    prefix: modules/auth\n"
            "    branch: splits/auth-module\n"
            "    installed_version: v0.70.0\n"
            "    installed_at: '2025-01-01'\n"
        )

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        assert _save_project_state(tmp_path, config, None, ["auth"], delta) is True

        state_data = yaml.safe_load((quickscale_dir / "state.yml").read_text())
        legacy_config = yaml.safe_load((quickscale_dir / "config.yml").read_text())

        assert state_data["modules"]["auth"]["version"] == "0.82.0"
        assert legacy_config["modules"]["auth"]["installed_version"] == "0.82.0"


# ============================================================================
# _display_next_steps
# ============================================================================


class TestDisplayNextSteps:
    """Tests for _display_next_steps"""

    def test_with_docker(self, monkeypatch, tmp_path):
        """Test next steps display with Docker"""
        monkeypatch.chdir(tmp_path)
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = True
        _display_next_steps(tmp_path / "myapp", config, False)

    def test_without_docker(self, monkeypatch, tmp_path, capsys):
        """Test next steps display without Docker"""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        _display_next_steps(Path.cwd(), config, True)
        output = capsys.readouterr().out

        assert "quickscale manage migrate" in output
        assert "poetry run python manage.py migrate" in output

    def test_with_docker_start_failure(self, monkeypatch, tmp_path, capsys):
        """Test next steps display when Docker auto-start fails."""
        monkeypatch.chdir(tmp_path)
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = True

        _display_next_steps(tmp_path / "myapp", config, False, docker_started=False)
        output = capsys.readouterr().out

        assert "Docker auto-start failed during apply" in output
        assert "quickscale up --build" in output

    def test_backups_private_remote_mentions_runtime_env_vars(
        self,
        tmp_path,
        capsys,
    ):
        """Backups next steps should direct operators to env-var credentials."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {
            "backups": Mock(
                options={
                    "target_mode": "private_remote",
                    "remote_access_key_id_env_var": "OPS_BACKUPS_ACCESS_KEY_ID",
                    "remote_secret_access_key_env_var": "OPS_BACKUPS_SECRET_ACCESS_KEY",
                }
            )
        }

        _display_next_steps(tmp_path, config, False)
        output = capsys.readouterr().out

        assert "OPS_BACKUPS_ACCESS_KEY_ID" in output
        assert "OPS_BACKUPS_SECRET_ACCESS_KEY" in output
        assert "Configure runtime credentials via env vars" in output
        assert "backups_restore --file /path/to/BACKUP_FILENAME.dump" in output
        assert "JSON artifacts are export-only" in output
        assert "Admin download and validate stay local-file-only in v1." in output
        assert "Freshly generated Docker and GitHub CI files" in output

    def test_backups_existing_project_mentions_manual_pg18_tooling_adoption(
        self,
        tmp_path,
        capsys,
    ):
        """Existing-project apply output should call out manual Docker/CI/E2E adoption."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {"backups": Mock(options={})}

        _display_next_steps(tmp_path, config, False, existing_project=True)
        output = capsys.readouterr().out

        assert (
            "quickscale apply does not rewrite user-owned Docker/CI/E2E files" in output
        )
        assert "predates the backups follow-up" in output

    def test_notifications_live_delivery_mentions_dns_and_env_vars(
        self,
        tmp_path,
        capsys,
    ):
        """Notifications next steps should call out DNS verification and env vars."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {
            "notifications": Mock(
                options={
                    "enabled": True,
                    "sender_name": "Ops",
                    "sender_email": "ops@example.com",
                    "resend_domain": "mg.example.com",
                    "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                    "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                    "default_tags": ["quickscale", "ops"],
                    "allowed_tags": ["quickscale", "ops", "transactional"],
                }
            )
        }

        _display_next_steps(tmp_path, config, False)
        output = capsys.readouterr().out

        assert "Verify SPF/DKIM in Resend for mg.example.com" in output
        assert "OPS_RESEND_API_KEY" in output
        assert "OPS_NOTIFICATIONS_WEBHOOK_SECRET" in output

    def test_analytics_mentions_posthog_env_vars_and_manual_frontend_adoption(
        self,
        tmp_path,
        capsys,
    ):
        """Analytics next steps should call out PostHog env vars and scope."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {
            "analytics": Mock(
                options={
                    "enabled": True,
                    "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                    "posthog_host_env_var": "OPS_POSTHOG_HOST",
                    "posthog_host": "https://eu.i.posthog.com",
                }
            )
        }

        _display_next_steps(tmp_path, config, False)
        output = capsys.readouterr().out

        assert "PostHog dashboard" in output
        assert "OPS_POSTHOG_API_KEY" in output
        assert "OPS_POSTHOG_HOST" in output
        assert "VITE_POSTHOG_KEY" in output
        assert "Existing React and HTML theme files remain user-owned" in output
        assert "CSP or referrer-policy restrictions" in output

    def test_analytics_disabled_mentions_reenable_instruction(
        self,
        tmp_path,
        capsys,
    ):
        """Disabled analytics should still produce explicit operator guidance."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {"analytics": Mock(options={"enabled": False})}

        _display_next_steps(tmp_path, config, False)
        output = capsys.readouterr().out

        assert "Analytics is embedded but disabled" in output
        assert "when you are ready to capture events" in output

    def test_social_mentions_managed_transport_and_manual_theme_adoption(
        self,
        tmp_path,
        capsys,
    ):
        """Social next steps should call out the managed transport and support matrix."""
        config = Mock()
        config.project.slug = "myapp"
        config.docker.start = False
        config.modules = {"social": Mock(options={})}

        _display_next_steps(tmp_path, config, False)
        output = capsys.readouterr().out

        assert SOCIAL_INTEGRATION_BASE_PATH in output
        assert SOCIAL_INTEGRATION_EMBEDS_PATH in output
        assert SOCIAL_LINK_TREE_PATH in output
        assert SOCIAL_EMBEDS_PATH in output
        assert (
            "Fresh showcase_react generations keep Django-owned public pages" in output
        )
        assert (
            "showcase_html and existing generated projects only receive the managed backend transport automatically"
            in output
        )
        assert "manual theme adoption" in output


class TestNotificationsEnvExampleSync:
    """Tests for notifications `.env.example` synchronization."""

    def test_sync_notifications_env_example_replaces_managed_block(self, tmp_path):
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            "SECRET_KEY=test\n"
            "# QuickScale Notifications (managed)\n"
            "OLD_RESEND=\n"
            "OLD_WEBHOOK=\n"
            "# End QuickScale Notifications\n"
        )
        qs_config = Mock()
        qs_config.modules = {
            "notifications": Mock(
                options={
                    "enabled": True,
                    "sender_name": "Ops",
                    "sender_email": "ops@example.com",
                    "resend_domain": "mg.example.com",
                    "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                    "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                    "default_tags": ["quickscale", "ops"],
                    "allowed_tags": ["quickscale", "ops", "transactional"],
                }
            )
        }

        result = _sync_notifications_env_example(tmp_path, qs_config)

        assert result is True
        updated = env_example.read_text()
        assert "OLD_RESEND" not in updated
        assert "OLD_WEBHOOK" not in updated
        assert "OPS_RESEND_API_KEY=" in updated
        assert "OPS_NOTIFICATIONS_WEBHOOK_SECRET=" in updated


class TestAnalyticsEnvExampleSync:
    """Tests for analytics `.env.example` synchronization."""

    def test_render_analytics_env_example_block_uses_custom_env_vars(self):
        """The rendered analytics block should expose runtime and Vite env vars."""
        block = _render_analytics_env_example_block(
            {
                "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                "posthog_host_env_var": "OPS_POSTHOG_HOST",
                "posthog_host": "https://eu.i.posthog.com",
            }
        )

        assert "# QuickScale Analytics (managed)" in block
        assert "OPS_POSTHOG_API_KEY=" in block
        assert "OPS_POSTHOG_HOST=" in block
        assert "VITE_POSTHOG_KEY=" in block
        assert "VITE_POSTHOG_HOST=" in block
        assert "https://eu.i.posthog.com" in block

    def test_sync_analytics_env_example_replaces_managed_block(self, tmp_path):
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            "SECRET_KEY=test\n"
            "# QuickScale Analytics (managed)\n"
            "OLD_POSTHOG_KEY=\n"
            "OLD_POSTHOG_HOST=\n"
            "# End QuickScale Analytics\n"
        )
        qs_config = Mock()
        qs_config.modules = {
            "analytics": Mock(
                options={
                    "enabled": True,
                    "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                    "posthog_host_env_var": "OPS_POSTHOG_HOST",
                    "posthog_host": "https://eu.i.posthog.com",
                }
            )
        }

        result = _sync_analytics_env_example(tmp_path, qs_config)

        assert result is True
        updated = env_example.read_text()
        assert "OLD_POSTHOG_KEY" not in updated
        assert "OLD_POSTHOG_HOST" not in updated
        assert "OPS_POSTHOG_API_KEY=" in updated
        assert "OPS_POSTHOG_HOST=" in updated
        assert "VITE_POSTHOG_KEY=" in updated
        assert "VITE_POSTHOG_HOST=" in updated

    def test_sync_analytics_env_example_removes_managed_block_when_disabled(
        self,
        tmp_path,
    ):
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            "SECRET_KEY=test\n"
            "# QuickScale Analytics (managed)\n"
            "POSTHOG_API_KEY=\n"
            "POSTHOG_HOST=\n"
            "# End QuickScale Analytics\n"
            "KEEP_ME=1\n"
        )
        qs_config = Mock()
        qs_config.modules = {"analytics": Mock(options={"enabled": False})}

        result = _sync_analytics_env_example(tmp_path, qs_config)

        assert result is True
        updated = env_example.read_text()
        assert "# QuickScale Analytics (managed)" not in updated
        assert "POSTHOG_API_KEY=" not in updated
        assert "KEEP_ME=1" in updated


# ============================================================================
# Backups-specific helpers
# ============================================================================


class TestBackupsApplyHelpers:
    """Tests for backups config sanitization and gitignore helpers."""

    @pytest.mark.parametrize(
        ("local_directory", "expected"),
        [
            (".private/backups", ".private/backups/"),
            ("./ops/backups", "ops/backups/"),
            ("./!foo", None),
            ("./#foo", None),
            (r".\\!foo", None),
            ("!ops/backups", None),
            (" #ops/backups", None),
            ("ops/*/backups", None),
            ("ops/backups?", None),
            ("ops/[draft]/backups", None),
            ("ops/backups\nmodules/auth", None),
            ("ops/backups\rmodules/auth", None),
            ("ops/backup\x00s", None),
            (r"C:\\backups", None),
            ("C:backups", None),
            ("C:/backups", None),
            (r"D:ops\\backups", None),
            ("/var/backups", None),
            ("../outside", None),
            (".quickscale", None),
        ],
    )
    def test_normalize_backups_gitignore_entry(self, local_directory, expected):
        assert _normalize_backups_gitignore_entry(local_directory) == expected

    def test_ensure_backups_gitignore_rules_adds_repo_relative_entry(self, tmp_path):
        qs_config = Mock()
        qs_config.modules = {
            "backups": Mock(options={"local_directory": ".private/backups"})
        }

        result = _ensure_backups_gitignore_rules(tmp_path, qs_config)

        assert result is True
        gitignore_text = (tmp_path / ".gitignore").read_text()
        assert "# QuickScale private backup artifacts" in gitignore_text
        assert ".private/backups/" in gitignore_text

    def test_ensure_backups_gitignore_rules_uses_default_directory_for_empty_config(
        self,
        tmp_path,
    ):
        qs_config = Mock()
        qs_config.modules = {"backups": Mock(options={})}

        result = _ensure_backups_gitignore_rules(tmp_path, qs_config)

        assert result is True
        gitignore_text = (tmp_path / ".gitignore").read_text()
        assert ".quickscale/backups/" in gitignore_text

    def test_ensure_backups_gitignore_rules_returns_false_when_gitignore_read_fails(
        self,
        tmp_path,
    ):
        qs_config = Mock()
        qs_config.modules = {
            "backups": Mock(options={"local_directory": ".private/backups"})
        }
        (tmp_path / ".gitignore").write_text("existing\n")

        with patch.object(Path, "read_text", side_effect=OSError("read denied")):
            result = _ensure_backups_gitignore_rules(tmp_path, qs_config)

        assert result is False

    def test_ensure_backups_gitignore_rules_returns_false_when_gitignore_write_fails(
        self,
        tmp_path,
    ):
        qs_config = Mock()
        qs_config.modules = {
            "backups": Mock(options={"local_directory": ".private/backups"})
        }

        with patch.object(Path, "write_text", side_effect=OSError("write denied")):
            result = _ensure_backups_gitignore_rules(tmp_path, qs_config)

        assert result is False

    @pytest.mark.parametrize(
        "local_directory",
        [
            "./!foo",
            "./#foo",
            r".\!foo",
            "!ops/backups",
            "#ops/backups",
            "ops/*/backups",
            "ops/backups?",
            "ops/[draft]/backups",
            "ops/backups\n!modules/auth",
            "ops/backups\x00private",
        ],
    )
    def test_ensure_backups_gitignore_rules_skips_unsafe_gitignore_patterns(
        self,
        tmp_path,
        local_directory,
    ):
        qs_config = Mock()
        qs_config.modules = {
            "backups": Mock(options={"local_directory": local_directory})
        }

        result = _ensure_backups_gitignore_rules(tmp_path, qs_config)

        assert result is True
        assert not (tmp_path / ".gitignore").exists()


# ============================================================================
# _execute_apply_steps
# ============================================================================


class TestExecuteApplySteps:
    """Tests for _execute_apply_steps module-selection matrix."""

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_apply_uses_single_final_managed_wiring_regeneration(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Apply should rely on one final authoritative managed-wiring pass."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=["blog"],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"blog": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=False,
            no_modules=False,
            verbose_docker=False,
        )

        mock_regenerate_wiring.assert_called_once_with(ctx, ["blog"])

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_partial_embed_failure_persists_completed_modules_before_abort(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Apply should save successful embeds before aborting on a later embed failure."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=False,
            embedded_modules=["auth"],
            failed_module="blog",
        )

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth", "blog"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {
            "auth": Mock(options={}),
            "blog": Mock(options={}),
        }
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_generate_new_project.assert_called_once_with(
            ctx.qs_config,
            ctx.output_path,
            False,
        )
        mock_init_git.assert_called_once_with(ctx.output_path)
        mock_save_state.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["auth"],
            ctx.delta,
        )
        mock_save_recovery.assert_not_called()
        mock_regenerate_wiring.assert_not_called()
        mock_backups_gitignore.assert_not_called()
        mock_notifications_env_sync.assert_not_called()
        mock_analytics_env_sync.assert_not_called()
        mock_sync_module_dependencies.assert_not_called()
        mock_run_post.assert_not_called()
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._clear_apply_recovery_state")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_partial_embed_failure_does_not_clear_recovery_when_state_save_fails(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_save_state,
        mock_clear_recovery,
        capsys,
    ):
        """Recovery state must remain untouched until partial authoritative state saves."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=False,
            embedded_modules=["auth"],
            failed_module="blog",
        )
        mock_save_state.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth", "blog"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {
            "auth": Mock(options={}),
            "blog": Mock(options={}),
        }
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with pytest.raises(click.Abort):
            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=False,
                no_modules=False,
                verbose_docker=False,
            )

        combined_output = capsys.readouterr()
        text = combined_output.out + combined_output.err
        assert "authoritative state persistence" in text
        assert "could not save partial authoritative state" in text
        mock_clear_recovery.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_dependency_install_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Apply should abort if poetry lock/install fails after dependency sync."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"forms": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_managed_wiring_failure_aborts_when_recovery_state_cannot_be_saved(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_save_state,
        mock_display_next_steps,
        capsys,
    ):
        """Post-embed failures must not silently continue when recovery persistence fails."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=["auth"],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state",
            return_value=False,
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        combined_output = capsys.readouterr()
        text = combined_output.out + combined_output.err
        assert "apply recovery state persistence" in text
        assert "managed module wiring generation failed" in text
        assert ".quickscale/apply-recovery.yml" in text
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["auth"],
            ctx.delta,
        )
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_analytics_env_sync_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Apply should abort cleanly if analytics env-example sync fails."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"analytics": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_run_post.assert_not_called()
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_backups_gitignore_failure_aborts_apply_and_saves_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Backups gitignore failures must use the post-embed recovery path."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=["backups"],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["backups"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"backups": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["backups"],
            ctx.delta,
        )
        mock_notifications_env_sync.assert_not_called()
        mock_analytics_env_sync.assert_not_called()
        mock_sync_module_dependencies.assert_not_called()
        mock_run_post.assert_not_called()
        mock_display_next_steps.assert_not_called()

    @pytest.mark.parametrize(
        "modules",
        [
            {},
            {"auth": Mock(options={})},
            {
                "auth": Mock(options={}),
                "blog": Mock(options={}),
                "listings": Mock(options={}),
                "crm": Mock(options={}),
                "billing": Mock(options={}),
                "teams": Mock(options={}),
            },
        ],
    )
    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations_in_docker")
    @patch("quickscale_cli.commands.apply_command._start_docker")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_all_none_some_modules_use_same_docker_path(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_start_docker,
        mock_run_migrations_in_docker,
        mock_save_state,
        mock_display_next_steps,
        modules,
    ):
        """Docker startup flow should be identical for none/some/all module sets."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_start_docker.return_value = True
        mock_run_migrations_in_docker.return_value = True

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False

        ctx.qs_config = Mock()
        ctx.qs_config.modules = modules
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=False,
            no_modules=False,
            verbose_docker=False,
        )

        mock_embed_modules_step.assert_called_once_with(
            ctx.output_path,
            list(modules.keys()),
            False,
            None,
        )
        mock_sync_module_dependencies.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
        )
        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_start_docker.assert_called_once_with(ctx.output_path, True, False)
        mock_run_migrations_in_docker.assert_called_once_with(ctx.output_path)
        mock_display_next_steps.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            False,
            True,
            existing_project=False,
        )

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations_in_docker")
    @patch("quickscale_cli.commands.apply_command._start_docker")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_without_docker_autostart_defers_migrations_in_post_step(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_start_docker,
        mock_run_migrations_in_docker,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Fresh scaffolds without Docker auto-start should defer migrations."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"blog": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=False,
            no_modules=False,
            verbose_docker=False,
        )

        mock_sync_module_dependencies.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
        )
        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_start_docker.assert_not_called()
        mock_run_migrations_in_docker.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations_in_docker")
    @patch("quickscale_cli.commands.apply_command._start_docker")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_no_docker_with_docker_autostart_skips_all_migrations(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_start_docker,
        mock_run_migrations_in_docker,
        mock_save_state,
        mock_display_next_steps,
    ):
        """--no-docker should not fall back to local migrations for Docker-first projects."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=True,
            no_modules=False,
            verbose_docker=False,
        )

        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_start_docker.assert_not_called()
        mock_run_migrations_in_docker.assert_not_called()
        mock_display_next_steps.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            True,
            None,
            existing_project=False,
        )

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_existing_project_local_migrations_failure_aborts_apply_and_saves_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_poetry_lock,
        mock_poetry_install,
        mock_run_migrations,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Existing-project local migration failures must take the recovery-gated abort path."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_poetry_lock.return_value = True
        mock_poetry_install.return_value = True
        mock_run_migrations.return_value = False

        ctx = Mock()
        ctx.existing_state = Mock()
        ctx.had_existing_state = True
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"blog": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_run_migrations.assert_called_once_with(ctx.output_path)
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_migrations_in_docker")
    @patch("quickscale_cli.commands.apply_command._start_docker")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_docker_autostart_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_start_docker,
        mock_run_migrations_in_docker,
        mock_run_migrations,
        mock_save_state,
        mock_display_next_steps,
    ):
        """If Docker startup fails, apply aborts without local migration fallback."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_start_docker.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"listings": Mock(options={})}
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_run_migrations_in_docker.assert_not_called()
        mock_run_migrations.assert_not_called()
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_migrations_in_docker")
    @patch("quickscale_cli.commands.apply_command._start_docker")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_docker_migrations_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_start_docker,
        mock_run_migrations_in_docker,
        mock_run_migrations,
        mock_save_state,
        mock_display_next_steps,
    ):
        """If Docker migrations fail, apply aborts and does not continue."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_start_docker.return_value = True
        mock_run_migrations_in_docker.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"listings": Mock(options={})}
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state"
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_run_post.assert_called_once_with(ctx.output_path, run_migrations=False)
        mock_run_migrations_in_docker.assert_called_once_with(ctx.output_path)
        mock_run_migrations.assert_not_called()
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._clear_apply_recovery_state")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_authoritative_state_save_failure_preserves_recovery_and_aborts(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_clear_recovery,
        mock_display_next_steps,
        capsys,
    ):
        """Apply must not report success or clear recovery when state persistence fails."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command._save_apply_recovery_state",
            return_value=True,
        ) as mock_save_recovery:
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        combined_output = capsys.readouterr()
        text = combined_output.out + combined_output.err
        assert "authoritative state persistence" in text
        assert ".quickscale/state.yml" in text
        assert ".quickscale/apply-recovery.yml" in text
        mock_save_state.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_save_recovery.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        mock_clear_recovery.assert_not_called()
        mock_display_next_steps.assert_not_called()


# ============================================================================
# _generate_with_existing_config
# ============================================================================


class TestGenerateWithExistingConfig:
    """Tests for _generate_with_existing_config"""

    @patch("quickscale_cli.commands.apply_command._generate_project")
    def test_success(self, mock_gen, tmp_path):
        """Test generation with existing config"""
        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")

        mock_config = Mock()
        mock_config.project.slug = "myapp"

        # Mock _generate_project to create project structure in temp dir
        def fake_generate(config, path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "manage.py").touch()
            return True

        mock_gen.side_effect = fake_generate

        _generate_with_existing_config(mock_config, output, config_file, False)
        assert config_file.read_text() == "original config"
        assert (output / "manage.py").exists()

    @patch("quickscale_cli.commands.apply_command._generate_project")
    def test_failure(self, mock_gen, tmp_path):
        """Test generation failure"""
        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")

        mock_gen.return_value = False
        mock_config = Mock()
        mock_config.project.slug = "myapp"

        with pytest.raises(click.Abort):
            _generate_with_existing_config(mock_config, output, config_file, False)

    @patch("quickscale_cli.commands.apply_command._generate_project")
    def test_with_force(self, mock_gen, tmp_path):
        """Test generation with force flag"""
        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")
        (output / "old_file.txt").touch()

        mock_config = Mock()
        mock_config.project.slug = "myapp"

        def fake_generate(config, path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "manage.py").touch()
            return True

        mock_gen.side_effect = fake_generate

        _generate_with_existing_config(mock_config, output, config_file, True)
        assert not (output / "old_file.txt").exists()
        assert (output / "manage.py").exists()


class TestGitCheckpointRestoration:
    """Regression coverage for apply-owned checkpoint cleanup."""

    def test_git_commit_restores_preexisting_staged_state_when_commit_fails(
        self, tmp_path
    ):
        """Checkpoint commit failure should restore the prior index exactly."""
        _init_apply_git_repo(tmp_path)

        quickscale_config = tmp_path / "quickscale.yml"
        quickscale_config.write_text(
            quickscale_config.read_text() + "modules:\n  auth:\n"
        )
        _run_git(tmp_path, "add", "quickscale.yml")

        module_file = tmp_path / "modules" / "auth" / "module.yml"
        module_file.parent.mkdir(parents=True, exist_ok=True)
        module_file.write_text('name: auth\nversion: "0.83.0"\n')

        _install_failing_pre_commit_hook(tmp_path)

        assert _git_commit(tmp_path, "Add module: auth") is False

        staged_paths = _run_git(tmp_path, "diff", "--cached", "--name-only").stdout
        status_output = _run_git(tmp_path, "status", "--short").stdout.splitlines()

        assert staged_paths.splitlines() == ["quickscale.yml"]
        assert "?? modules/" in status_output


class TestManagedSocialApplyRegression:
    """Regression coverage for existing-project managed social apply behavior."""

    def test_existing_project_social_regeneration_preserves_showcase_react_files(
        self, tmp_path
    ):
        """Existing-project apply should refresh managed backend files without theme churn."""
        project_name = "social_existing_project"
        output_path = tmp_path / project_name
        generator = ProjectGenerator(theme="showcase_react")
        generator.generate(project_name, output_path)

        frontend_page = (
            output_path / "frontend" / "src" / "pages" / "SocialEmbedsPublicPage.tsx"
        )
        public_template = output_path / "templates" / "social" / "embeds.html"

        frontend_page.write_text(
            "// user-owned showcase_react customization\n" + frontend_page.read_text()
        )
        public_template.write_text(
            "<!-- user-owned social embeds template -->\n" + public_template.read_text()
        )

        expected_frontend_page = frontend_page.read_text()
        expected_public_template = public_template.read_text()

        ctx = Mock()
        ctx.output_path = output_path
        ctx.existing_state = Mock()
        ctx.delta = Mock()
        ctx.delta.modules_unchanged = ["social"]
        ctx.qs_config = Mock()
        ctx.qs_config.project.package = project_name
        ctx.qs_config.modules = {
            "social": Mock(
                options={
                    "layout_variant": "grid",
                    "provider_allowlist": ["youtube", "tiktok"],
                    "cache_ttl_seconds": 600,
                    "links_per_page": 18,
                    "embeds_per_page": 9,
                }
            )
        }

        assert _regenerate_managed_wiring_for_apply(ctx, embedded_modules=[]) is True
        assert frontend_page.read_text() == expected_frontend_page
        assert public_template.read_text() == expected_public_template

        managed_settings = (
            output_path / project_name / "settings" / "modules.py"
        ).read_text()
        managed_social_views = (
            output_path / project_name / "quickscale_managed" / "social_views.py"
        ).read_text()

        assert "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE" in managed_settings
        assert "build_social_link_tree_payload" in managed_social_views
        assert "build_social_embeds_payload" in managed_social_views


class TestManagedAnalyticsApplyRegression:
    """Regression coverage for existing-project analytics apply behavior."""

    def test_existing_project_analytics_regeneration_preserves_user_owned_frontend_files(
        self, tmp_path
    ):
        """Existing-project apply should refresh backend analytics wiring without frontend churn."""
        project_name = "analytics_existing_project"
        output_path = tmp_path / project_name
        generator = ProjectGenerator(theme="showcase_react")
        generator.generate(project_name, output_path)

        package_json = output_path / "frontend" / "package.json"
        main_file = output_path / "frontend" / "src" / "main.tsx"
        app_file = output_path / "frontend" / "src" / "App.tsx"
        index_template = output_path / "templates" / "index.html"

        package_json.write_text(
            package_json.read_text().replace(
                '  "version": "0.0.1",\n',
                '  "version": "0.0.1",\n  "userOwnedPackageMarker": true,\n',
            )
        )
        main_file.write_text(
            "// user-owned analytics bootstrap customization\n" + main_file.read_text()
        )
        app_file.write_text(
            "// user-owned app routing customization\n" + app_file.read_text()
        )
        index_template.write_text(
            "<!-- user-owned index template customization -->\n"
            + index_template.read_text()
        )

        expected_package_json = package_json.read_text()
        expected_main_file = main_file.read_text()
        expected_app_file = app_file.read_text()
        expected_index_template = index_template.read_text()

        ctx = Mock()
        ctx.output_path = output_path
        ctx.existing_state = Mock()
        ctx.delta = Mock()
        ctx.delta.modules_unchanged = ["analytics"]
        ctx.qs_config = Mock()
        ctx.qs_config.project.package = project_name
        ctx.qs_config.modules = {
            "analytics": Mock(
                options={
                    "enabled": True,
                    "posthog_api_key_env_var": "POSTHOG_API_KEY",
                    "posthog_host_env_var": "POSTHOG_HOST",
                    "posthog_host": "https://eu.i.posthog.com",
                    "exclude_debug": True,
                    "exclude_staff": False,
                    "anonymous_by_default": True,
                }
            )
        }

        assert _regenerate_managed_wiring_for_apply(ctx, embedded_modules=[]) is True
        assert package_json.read_text() == expected_package_json
        assert main_file.read_text() == expected_main_file
        assert app_file.read_text() == expected_app_file
        assert index_template.read_text() == expected_index_template

        managed_settings = (
            output_path / project_name / "settings" / "modules.py"
        ).read_text()

        assert "QUICKSCALE_ANALYTICS_ENABLED" in managed_settings
        assert "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR" in managed_settings
