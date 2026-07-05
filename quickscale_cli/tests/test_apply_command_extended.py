"""Extended tests for apply_command.py - covering helper functions and edge cases."""
# ruff: noqa: E402 — AF5 Phase 4: module-level bypass set before imports

from pathlib import Path
import subprocess
from unittest.mock import ANY, Mock, patch

import click
import pytest
import shutil as _real_shutil
import yaml

from quickscale_core.contracts.module_options import (
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.resolvers import default_notifications_module_options

# AF5 Phase 4: Bypass the late destructive/remote confirmation gate in
# all tests so test output assertions remain stable.  Each test function
# sets this at module-load time; individual tests may override.
import quickscale_cli.commands.apply_command as _apply_command_mod

_apply_command_mod._AF5_DESTRUCTIVE_CONFIRM_BYPASS = True

from quickscale_cli.commands.apply_command import (
    ApplyContext,
    EmbedModulesResult,
    ModuleEmbedProvenance,
    _attempt_provenance_repair_if_needed,
    _build_project_state_snapshot,
    _check_output_directory,
    _clear_apply_recovery_state,
    _commit_pending_config_changes,
    _determine_output_path,
    _display_config_summary,
    _display_next_steps,
    _embed_module,
    _embed_modules_step,
    _ensure_backups_gitignore_rules,
    _execute_apply_steps,
    _execute_apply_steps_locked,
    _finalize_apply_state,
    _generate_project,
    _generate_with_existing_config,
    _git_commit,
    _handle_delta_and_existing_state,
    _populate_consolidated_tracking_from_legacy,
    _regenerate_managed_wiring_for_apply,
    _init_git,
    _init_git_with_config,
    _load_and_validate_config,
    _load_module_manifests,
    _normalize_backups_gitignore_entry,
    _prepare_apply_context,
    _print_apply_failure_summary,
    _provenance_repair_might_be_needed,
    _refresh_context_after_lock,
    _render_billing_env_example_block,
    _run_command,
    _run_migrations,
    _run_migrations_in_docker,
    _run_poetry_lock,
    _run_poetry_install,
    _run_post_generation_steps,
    _render_analytics_env_example_block,
    _save_apply_recovery_state,
    _save_project_state,
    _sync_billing_env_example,
    _sync_project_module_dependencies_for_apply,
    _start_docker,
    _sync_analytics_env_example,
    _sync_notifications_env_example,
    _update_module_config_in_state,
)
from quickscale_cli.commands.module_commands import _update_single_module
from quickscale_core.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)
from quickscale_core.config import ConfigError
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
        mock_config.modules = {}
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
        mock_config.modules = {}
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
        mock_config.modules = {}
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
        mock_config.modules = {}
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
        mock_config.modules = {}
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_selected_modules_forwarded_from_quickscale_config(self, mock_gen_cls):
        """Fresh apply must forward ``selected_modules`` from ``config.modules``.

        ProjectGenerator treats ``selected_modules=None`` as the legacy default
        (emit every per-module surface) and a list as the active selection. The
        apply path must pass the actual selection so the React theme gating
        matches ``quickscale.yml``. Existing-project apply does not call
        ``_generate_project`` at all, so its legacy behavior is preserved.
        """
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_react"
        mock_config.modules = {
            "auth": Mock(),
            "blog": Mock(),
            "notifications": Mock(),
        }

        result = _generate_project(mock_config, Path("/tmp/myapp"))

        assert result is True
        mock_gen_cls.assert_called_once_with(
            theme="showcase_react",
            selected_modules=["auth", "blog", "notifications"],
        )

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_selected_modules_empty_list_when_no_modules(self, mock_gen_cls):
        """An empty ``modules`` block should forward an empty selection list."""
        mock_config = Mock()
        mock_config.project.slug = "myapp"
        mock_config.project.package = "myapp"
        mock_config.project.theme = "showcase_react"
        mock_config.modules = {}

        result = _generate_project(mock_config, Path("/tmp/myapp"))

        assert result is True
        mock_gen_cls.assert_called_once_with(
            theme="showcase_react",
            selected_modules=[],
        )


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

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_git_commit_success(self, mock_run, mock_subprocess):
        """Test successful git commit"""
        mock_subprocess.return_value = Mock(returncode=0, stdout="tree123\n", stderr="")
        mock_run.return_value = (True, "")
        assert _git_commit(Path("/tmp/proj"), "msg") is True

    @patch("quickscale_cli.commands.apply_command.subprocess.run")
    @patch("quickscale_cli.commands.apply_command._run_command")
    def test_git_commit_add_fails(self, mock_run, mock_subprocess):
        """Test git commit when git add fails"""
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="tree123\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]
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
            provenance_sink=None,
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
            provenance_sink=None,
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

    def test_teams_placeholder_module_is_rejected_on_load(self, tmp_path):
        """Apply should reject placeholder modules even if they are hand-edited in."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  teams:\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

    def test_billing_module_requires_auth_on_load(self, tmp_path, capsys):
        """Apply load should reject billing until auth is present for implied orgs."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  billing:\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )

    def test_billing_module_loads_with_auth_on_load(self, tmp_path):
        """Apply load should materialize orgs and notifications for billing."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "  billing:\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert set(result.modules.keys()) == {
            "auth",
            "billing",
            "notifications",
            "orgs",
        }
        assert result.modules["orgs"].options == {}
        assert result.modules["notifications"].options == (
            default_notifications_module_options()
        )
        assert "orgs:" in rewritten
        assert "notifications:" in rewritten
        assert "sender_email: noreply@example.com" in rewritten
        assert "resend_api_key_env_var: RESEND_API_KEY" in rewritten

    def test_orgs_module_requires_auth_on_load(self, tmp_path, capsys):
        """Apply load should reject orgs until auth is present in the desired config."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  orgs:\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )

    def test_orgs_module_loads_with_auth_on_load(self, tmp_path):
        """Apply load should materialize notifications once auth and orgs are configured."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "  orgs:\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert set(result.modules.keys()) == {"auth", "orgs", "notifications"}
        assert result.modules["notifications"].options == (
            default_notifications_module_options()
        )
        assert "notifications:" in rewritten
        assert "sender_email: noreply@example.com" in rewritten
        assert "resend_api_key_env_var: RESEND_API_KEY" in rewritten

    def test_crm_module_materializes_orgs_and_notifications_on_load(self, tmp_path):
        """Apply load should persist orgs+notifications when crm is configured with auth."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
            "  crm:\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)
        rewritten = config.read_text()

        assert set(result.modules.keys()) == {
            "auth",
            "crm",
            "notifications",
            "orgs",
        }
        assert result.modules["orgs"].options == {}
        assert result.modules["notifications"].options == (
            default_notifications_module_options()
        )
        assert "orgs:" in rewritten
        assert "notifications:" in rewritten
        assert "sender_email: noreply@example.com" in rewritten
        assert "resend_api_key_env_var: RESEND_API_KEY" in rewritten

    def test_crm_module_requires_auth_on_load_via_implied_orgs(self, tmp_path, capsys):
        """Apply load should reject crm until auth is present because crm implies orgs."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  crm:\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        error_output = capsys.readouterr().err
        assert (
            "Organizations requires the auth module before apply can continue"
            in error_output
        )

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

    def test_auth_legacy_keys_fail_before_sanitize_on_load(self, tmp_path):
        """Desired-config auth must fail before apply load tries to sanitize it."""
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

        original = config.read_text()

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        assert config.read_text() == original
        assert "allow_registration" in original
        assert "social_providers" in original

    def test_legacy_notifications_secrets_raise_on_load(self, tmp_path):
        """Legacy notification secrets raise ConfigValidationError instead of silent rewrite."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  notifications:\n"
            "    sender_email: ops@example.com\n"
            "    resend_domain: mg.example.com\n"
            "    resend_api_key: raw-secret\n"
            "    webhook_secret: webhook-secret\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        rewritten = config.read_text()
        assert "resend_api_key" in rewritten
        assert "webhook_secret" in rewritten

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

    def test_live_targeted_notifications_reject_placeholder_sender_email(
        self,
        tmp_path,
        capsys,
    ):
        """Apply should reject the default placeholder sender for live Resend targets."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  notifications:\n"
            "    sender_name: QuickScale\n"
            "    sender_email: noreply@example.com\n"
            "    resend_domain: mg.example.com\n"
            "docker:\n"
            "  start: false\n"
        )

        with pytest.raises(click.Abort):
            _load_and_validate_config(config)

        error_output = capsys.readouterr().err
        assert "noreply@example.com" in error_output
        assert "sender_email" in error_output

    def test_console_safe_notifications_allow_placeholder_sender_email(
        self,
        tmp_path,
    ):
        """Console-safe notifications should still allow the default placeholder sender."""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  notifications:\n"
            "    sender_name: QuickScale\n"
            "    sender_email: noreply@example.com\n"
            "docker:\n"
            "  start: false\n"
        )

        result = _load_and_validate_config(config)

        assert result.modules["notifications"].options["sender_email"] == (
            "noreply@example.com"
        )
        assert result.modules["notifications"].options.get("resend_domain", "") == ""

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
        """Social aliases and casing should be canonicalized during apply load.

        Social implies orgs, and orgs requires auth, so auth must be present
        for social config to pass the prerequisite check.
        """
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            "modules:\n"
            "  auth:\n"
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

    def test_rejects_teams_placeholder_module_in_existing_state(self, tmp_path):
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
            "  teams:\n"
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
            'git_index_checkpoint: "cafebabedeadbeefcafebabedeadbeefcafebabe"\n'
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
            Mock(returncode=0, stdout="tree123\n", stderr=""),
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
            Mock(returncode=0, stdout="tree123\n", stderr=""),
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
            Mock(returncode=0, stdout="tree123\n", stderr=""),
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

    @patch("quickscale_cli.commands.apply_command._handle_delta_and_existing_state")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._commit_pending_config_changes")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_execute_apply_steps_aborts_before_embed_when_pre_embed_commit_aborts(
        self,
        mock_generate_new_project,
        mock_commit_pending,
        mock_embed_modules_step,
        mock_handle_delta,
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
            provenance_sink=ANY,
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
            provenance_sink=ANY,
        )

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_provenance_collected_from_embed(self, mock_embed, mock_commit):
        """Phase 1 checkpoint: provenance payloads are collected per module."""
        mock_commit.return_value = True

        def _fake_embed(
            path, module_name, *, skip_auth_migration_check, provenance_sink
        ):
            del path, skip_auth_migration_check
            if provenance_sink is not None:
                provenance_sink.append(
                    ModuleEmbedProvenance(
                        module_name=module_name,
                        prefix=f"modules/{module_name}",
                        tracking_branch=f"splits/{module_name}-module",
                        source_ref="c" * 40,
                        installed_version="0.82.0",
                    )
                )
            return True

        mock_embed.side_effect = _fake_embed
        result = _embed_modules_step(Path("/tmp"), ["auth", "blog"], False, None)

        assert result.success is True
        assert result.embedded_modules == ["auth", "blog"]
        assert result.provenance_payloads is not None
        assert "auth" in result.provenance_payloads
        assert "blog" in result.provenance_payloads
        assert result.provenance_payloads["auth"].source_ref == "c" * 40
        assert (
            result.provenance_payloads["blog"].tracking_branch == "splits/blog-module"
        )


# ============================================================================
# Phase 2: Provenance persistence into state and recovery
# ============================================================================


class TestProvenancePersistence:
    """Phase 2 tests: provenance flows into authoritative and recovery state."""

    def test_build_snapshot_populates_commit_sha_from_provenance(self, tmp_path):
        """Phase 2 checkpoint: _build_project_state_snapshot writes commit_sha
        from provenance source_ref into the module state."""
        # Create a minimal embedded module manifest so version normalization works
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        resolved_sha = "d" * 40
        provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        state = _build_project_state_snapshot(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=provenance,
        )

        assert "auth" in state.modules
        assert state.modules["auth"].commit_sha == resolved_sha

    def test_build_snapshot_without_provenance_preserves_existing_commit_sha(
        self, tmp_path
    ):
        """Without provenance, existing commit_sha is preserved (no regression)."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        existing_state = QuickScaleState(
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
                    commit_sha="e" * 40,
                ),
            },
        )

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        state = _build_project_state_snapshot(
            tmp_path,
            config,
            existing_state=existing_state,
            embedded_modules=["auth"],
            delta=delta,
        )

        assert state.modules["auth"].commit_sha == "e" * 40

    def test_save_recovery_state_contains_provenance_commit_sha(self, tmp_path):
        """Phase 2 checkpoint: recovery file carries the same commit_sha as
        authoritative state would."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        resolved_sha = "f" * 40
        provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        result = _save_apply_recovery_state(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=provenance,
            checkpoint_tree_id="d" * 40,
        )

        assert result is True
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        assert recovery_path.exists()

        # Load the recovery file and verify commit_sha is present
        recovery_manager = StateManager(tmp_path)
        recovery_manager.state_file = recovery_path
        recovery_state = recovery_manager.load()
        assert recovery_state is not None
        assert "auth" in recovery_state.modules
        assert recovery_state.modules["auth"].commit_sha == resolved_sha

    def test_save_project_state_persists_provenance_commit_sha(self, tmp_path):
        """Phase 2 checkpoint: authoritative state.yml carries commit_sha
        from provenance."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        resolved_sha = "a" * 40
        provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        result = _save_project_state(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=provenance,
        )

        assert result is True
        state_path = tmp_path / ".quickscale" / "state.yml"
        assert state_path.exists()

        state_manager = StateManager(tmp_path)
        saved_state = state_manager.load()
        assert saved_state is not None
        assert "auth" in saved_state.modules
        assert saved_state.modules["auth"].commit_sha == resolved_sha

    def test_clear_recovery_after_successful_finalize(self, tmp_path):
        """Phase 2 checkpoint: recovery file is removed after successful
        authoritative state save."""
        # Pre-create a recovery file
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        recovery_path.write_text("dummy: recovery\n")
        assert recovery_path.exists()

        _clear_apply_recovery_state(tmp_path)

        assert not recovery_path.exists()

    def test_save_recovery_state_writes_exact_checkpoint_tree_id(self, tmp_path):
        """F12.1e checkpoint: _save_apply_recovery_state writes the threaded
        checkpoint_tree_id into the recovery ledger, not a re-captured value."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        delta = Mock()
        delta.config_deltas = {}

        tree_id = "aabbccddeeff00112233445566778899aabbccdd"

        result = _save_apply_recovery_state(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=[],
            delta=delta,
            checkpoint_tree_id=tree_id,
        )

        assert result is True
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        assert recovery_path.exists()

        recovery_data = yaml.safe_load(recovery_path.read_text())
        assert recovery_data["git_index_checkpoint"] == tree_id

    def test_save_recovery_state_persists_diff_checkpoint_tree_id(self, tmp_path):
        """The threaded checkpoint_tree_id is persisted verbatim, proving no
        re-capture replaces it with a later tree value."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        delta = Mock()
        delta.config_deltas = {}

        threaded_id = "bbccddeeff00112233445566778899aabbccddee"

        result = _save_apply_recovery_state(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=[],
            delta=delta,
            checkpoint_tree_id=threaded_id,
        )

        assert result is True
        recovery_data = yaml.safe_load(
            (tmp_path / ".quickscale" / "apply-recovery.yml").read_text()
        )
        assert recovery_data["git_index_checkpoint"] == threaded_id

    def test_finalize_clears_recovery_on_success(self, tmp_path):
        """Phase 2: _finalize_apply_state clears recovery after successful save."""
        # Pre-create a recovery file
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        recovery_path.write_text("dummy: recovery\n")

        ctx = Mock()
        ctx.output_path = tmp_path
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.project.package = "myapp"
        ctx.qs_config.project.theme = "showcase_html"
        ctx.qs_config.modules = {}
        ctx.existing_state = None
        ctx.delta = Mock()
        ctx.delta.config_deltas = {}

        post_embed_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
            ),
            modules={},
        )

        _finalize_apply_state(ctx, post_embed_state, checkpoint_tree_id="e" * 40)

        # Recovery should be cleared after successful finalize
        assert not recovery_path.exists()
        # Authoritative state should exist
        assert (tmp_path / ".quickscale" / "state.yml").exists()


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
    def test_migrations_not_run_in_step_10_anymore(
        self, mock_poetry, mock_migrate, mock_lock
    ):
        """AF5 Phase 4: Step 10 no longer runs migrations (deferred to step 13).
        Even if _run_migrations would fail, _run_post_generation_steps
        succeeds because migration execution was removed from this step."""
        mock_lock.return_value = True
        mock_poetry.return_value = True
        mock_migrate.return_value = False  # Would fail if called — but won't be
        assert _run_post_generation_steps(Path("/tmp")) is True
        mock_migrate.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._run_poetry_lock")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_migrations_not_run_in_step_10(self, mock_poetry, mock_migrate, mock_lock):
        """AF5 Phase 4: Step 10 does not run migrations (deferred to step 13)."""
        mock_lock.return_value = True
        mock_poetry.return_value = True
        assert _run_post_generation_steps(Path("/tmp")) is True
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

        # SA10.1: new project state should include project_contract
        state_data = yaml.safe_load(
            (tmp_path / ".quickscale" / "state.yml").read_text()
        )
        assert "project_contract" in state_data.get("project", {})

    def test_existing_project_state(self, tmp_path):
        """Test saving state for existing project (legacy-missing project_contract)."""
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
        # Sanity: legacy state has no project_contract
        assert existing_state.project.project_contract is None

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
        # SA10.1: legacy-missing project_contract must remain None (unknown
        # vintage) — the apply-state snapshot must not backfill it.
        state_data = yaml.safe_load(
            (tmp_path / ".quickscale" / "state.yml").read_text()
        )
        project_data = state_data.get("project", {})
        assert "project_contract" in project_data
        assert project_data["project_contract"] is None

    def test_existing_project_state_preserves_set_contract(self, tmp_path):
        """Existing state with a non-null project_contract is preserved."""
        (tmp_path / ".quickscale").mkdir()

        existing_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
                project_contract="0.87.0",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            ),
            modules={},
        )

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        delta = Mock()
        delta.config_deltas = {}

        assert _save_project_state(tmp_path, config, existing_state, [], delta) is True
        state_data = yaml.safe_load(
            (tmp_path / ".quickscale" / "state.yml").read_text()
        )
        project_data = state_data.get("project", {})
        assert project_data.get("project_contract") == "0.87.0"

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
        """Apply state should use embedded manifest versions.

        Phase 3: config.yml is no longer mirrored. Only state.yml is authoritative.
        """
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
        # Phase 3: config.yml is no longer mirrored by apply.
        assert legacy_config["modules"]["auth"]["installed_version"] == "v0.70.0"


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


class TestBillingEnvExampleSync:
    """Tests for billing `.env.example` synchronization."""

    def test_render_billing_env_example_block_uses_default_env_vars(self):
        """Billing env-example rendering should expose the default Stripe env vars."""
        block = _render_billing_env_example_block({})

        assert "# QuickScale Billing (managed)" in block
        assert "STRIPE_PUBLISHABLE_KEY=" in block
        assert "STRIPE_SECRET_KEY=" in block
        assert "QUICKSCALE_BILLING_WEBHOOK_SECRET=" in block
        assert "# Billing currency from quickscale.yml: usd" in block

    def test_sync_billing_env_example_appends_normalized_managed_block(self, tmp_path):
        env_example = tmp_path / ".env.example"
        env_example.write_text("SECRET_KEY=test\n")
        qs_config = Mock()
        qs_config.modules = {
            "billing": Mock(
                options={
                    "publishable_key_env_var": " OPS_STRIPE_PUBLISHABLE_KEY ",
                    "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
                    "webhook_secret_env_var": " OPS_BILLING_WEBHOOK_SECRET ",
                    "billing_currency": " EUR ",
                }
            )
        }

        result = _sync_billing_env_example(tmp_path, qs_config)

        assert result is True
        updated = env_example.read_text()
        assert "SECRET_KEY=test" in updated
        assert "OPS_STRIPE_PUBLISHABLE_KEY=" in updated
        assert "OPS_STRIPE_SECRET_KEY=" in updated
        assert "OPS_BILLING_WEBHOOK_SECRET=" in updated
        assert "# Billing currency from quickscale.yml: eur" in updated

    def test_sync_billing_env_example_replaces_managed_block(self, tmp_path):
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            "SECRET_KEY=test\n"
            "# QuickScale Billing (managed)\n"
            "OLD_STRIPE_PUBLISHABLE_KEY=\n"
            "OLD_STRIPE_SECRET_KEY=\n"
            "OLD_BILLING_WEBHOOK_SECRET=\n"
            "# End QuickScale Billing\n"
            "KEEP_ME=1\n"
        )
        qs_config = Mock()
        qs_config.modules = {
            "billing": Mock(
                options={
                    "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
                    "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
                    "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                    "billing_currency": "EUR",
                }
            )
        }

        result = _sync_billing_env_example(tmp_path, qs_config)

        assert result is True
        updated = env_example.read_text()
        assert "OLD_STRIPE_PUBLISHABLE_KEY" not in updated
        assert "OLD_STRIPE_SECRET_KEY" not in updated
        assert "OLD_BILLING_WEBHOOK_SECRET" not in updated
        assert updated.count("# QuickScale Billing (managed)") == 1
        assert updated.count("# End QuickScale Billing") == 1
        assert "OPS_STRIPE_PUBLISHABLE_KEY=" in updated
        assert "OPS_STRIPE_SECRET_KEY=" in updated
        assert "OPS_BILLING_WEBHOOK_SECRET=" in updated
        assert "# Billing currency from quickscale.yml: eur" in updated
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_apply_uses_single_final_managed_wiring_regeneration(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_save_state.assert_called_once()
        assert mock_save_state.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["auth"],
            ctx.delta,
        )
        assert "state_snapshot" not in mock_save_state.call_args.kwargs
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_dependency_install_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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

        mock_run_post.assert_called_once_with(ctx.output_path)
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_managed_wiring_failure_aborts_when_recovery_state_cannot_be_saved(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["auth"],
            ctx.delta,
        )
        state_snapshot = mock_save_recovery.call_args.kwargs["state_snapshot"]
        assert state_snapshot is not None
        assert list(state_snapshot.modules) == ["auth"]
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_analytics_env_sync_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
        mock_run_post.assert_not_called()
        mock_display_next_steps.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_billing_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_billing_env_sync_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_billing_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Apply should abort cleanly if billing env-example sync fails."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_billing_env_sync.return_value = False

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"billing": Mock(options={})}
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
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
        mock_sync_module_dependencies.assert_not_called()
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_backups_gitignore_failure_aborts_apply_and_saves_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            ["backups"],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_all_none_some_modules_use_same_docker_path(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_run_post.assert_called_once_with(ctx.output_path)
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_without_docker_autostart_defers_migrations_in_post_step(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_run_post.assert_called_once_with(ctx.output_path)
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_new_project_no_docker_with_docker_autostart_skips_all_migrations(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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

        mock_run_post.assert_called_once_with(ctx.output_path)
        mock_start_docker.assert_not_called()
        mock_run_migrations_in_docker.assert_not_called()
        mock_display_next_steps.assert_called_once_with(
            ctx.output_path,
            ctx.qs_config,
            True,
            None,
            existing_project=False,
        )

    @patch("quickscale_cli.commands.apply_command._handle_delta_and_existing_state")
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_existing_project_local_migrations_failure_aborts_apply_and_saves_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_handle_delta,
    ):
        """Existing-project local migration failures must take the recovery-gated abort path."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_poetry_lock.return_value = True
        mock_poetry_install.return_value = True
        mock_run_migrations.return_value = False

        ctx = Mock()
        ctx.existing_state = QuickScaleState(
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
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_docker_autostart_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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

        mock_run_post.assert_called_once_with(ctx.output_path)
        mock_run_migrations_in_docker.assert_not_called()
        mock_run_migrations.assert_not_called()
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_docker_migrations_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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

        mock_run_post.assert_called_once_with(ctx.output_path)
        mock_run_migrations_in_docker.assert_called_once_with(ctx.output_path)
        mock_run_migrations.assert_not_called()
        mock_save_state.assert_not_called()
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_authoritative_state_save_failure_preserves_recovery_and_aborts(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
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
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
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
        mock_save_state.assert_called_once()
        assert mock_save_state.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_state.call_args.kwargs["state_snapshot"] is not None
        mock_save_recovery.assert_called_once()
        assert mock_save_recovery.call_args.args == (
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            [],
            ctx.delta,
        )
        assert mock_save_recovery.call_args.kwargs["state_snapshot"] is not None
        mock_clear_recovery.assert_not_called()
        mock_display_next_steps.assert_not_called()

    # ------------------------------------------------------------------ #
    # F12.3a: Pre-embed recovery coverage                                 #
    # ------------------------------------------------------------------ #

    def test_generation_failure_aborts_apply_before_git_init(self):
        """Pre-embed generation failure must abort apply before git init
        and before advisory lock acquisition."""
        with patch(
            "quickscale_cli.commands.apply_command._generate_new_project",
            side_effect=click.Abort(),
        ):
            with patch(
                "quickscale_cli.commands.apply_command._init_git_with_config"
            ) as mock_init_git:
                with patch(
                    "quickscale_cli.commands.apply_command.AdvisoryLock"
                ) as mock_lock_cls:
                    ctx = Mock()
                    ctx.existing_state = None
                    ctx.output_path = Path("/tmp/proj")

                    with pytest.raises(click.Abort):
                        _execute_apply_steps(
                            ctx,
                            force=False,
                            no_docker=False,
                            no_modules=False,
                        )

                    mock_init_git.assert_not_called()
                    mock_lock_cls.assert_not_called()

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_git_init_failure_does_not_block_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Pre-embed git init failure must not block apply from continuing."""
        mock_init_git.return_value = False  # git init fails
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = True

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

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=False,
            no_modules=False,
        )

        # Pre-embed generation was called
        mock_generate_new_project.assert_called_once_with(
            ctx.qs_config,
            ctx.output_path,
            False,
        )
        # _init_git was called (by the real _init_git_with_config) and returned False
        mock_init_git.assert_called_once_with(ctx.output_path)
        # Locked section still proceeds after non-fatal git init failure
        mock_embed_modules_step.assert_called_once()
        mock_regenerate_wiring.assert_called_once()
        mock_display_next_steps.assert_called_once()

    # ------------------------------------------------------------------ #
    # F12.3b: Railway deploy integration                                  #
    # ------------------------------------------------------------------ #

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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_railway_deploy_skipped_when_not_linked(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Railway deploy must be skipped when railway.json does not exist."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = True

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

        # Confirm railway.json does NOT exist at output_path
        railway_json = ctx.output_path / "railway.json"
        assert not railway_json.exists()

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=False,
            no_modules=False,
        )

        mock_save_state.assert_called_once()
        mock_display_next_steps.assert_called_once()

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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_railway_deploy_triggers_when_linked(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
        tmp_path,
    ):
        """Railway deploy must trigger when .railway directory exists at output_path."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = True

        # Create .railway directory so deploy gate triggers
        (tmp_path / ".railway").mkdir(parents=True, exist_ok=True)

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = tmp_path
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.modules = {}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command.deploy_railway_service",
        ) as mock_deploy:
            mock_deploy.return_value = Mock(
                returncode=0, stderr="", stdout="Deploy started"
            )

            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=False,
                no_modules=False,
            )

        mock_deploy.assert_called_once_with(
            project_path=tmp_path,
            service_name="myapp",
        )
        mock_save_state.assert_called_once()
        mock_display_next_steps.assert_called_once()

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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_railway_deploy_failure_aborts_with_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
        tmp_path,
    ):
        """Railway deploy failure must abort apply and save recovery state."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True

        # Create .railway directory so deploy gate triggers
        (tmp_path / ".railway").mkdir(parents=True, exist_ok=True)

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = tmp_path
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.modules = {}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with (
            patch(
                "quickscale_cli.commands.apply_command.deploy_railway_service",
            ) as mock_deploy,
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ) as mock_save_recovery,
        ):
            mock_deploy.return_value = Mock(
                returncode=1, stderr="Deployment failed: build error", stdout=""
            )

            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                )

        mock_deploy.assert_called_once_with(
            project_path=tmp_path,
            service_name="myapp",
        )
        mock_save_recovery.assert_called_once()
        mock_save_state.assert_not_called()
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_railway_deploy_cli_not_installed_aborts_with_recovery(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
        tmp_path,
    ):
        """Railway deploy must abort with recovery when Railway CLI is not installed."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True

        # Create .railway directory so deploy gate triggers
        (tmp_path / ".railway").mkdir(parents=True, exist_ok=True)

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = tmp_path
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.modules = {}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = True

        with (
            patch(
                "quickscale_cli.commands.apply_command.deploy_railway_service",
                side_effect=FileNotFoundError("Railway CLI not found"),
            ) as mock_deploy,
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ) as mock_save_recovery,
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                )

        mock_deploy.assert_called_once_with(
            project_path=tmp_path,
            service_name="myapp",
        )
        mock_save_recovery.assert_called_once()
        mock_save_state.assert_not_called()
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
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_railway_deploy_with_no_docker_and_docker_start(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_save_state,
        mock_display_next_steps,
        tmp_path,
    ):
        """Railway deploy must still trigger when --no-docker overrides docker.start.

        CR-F12.3B-002 regression: when docker.start=True but --no-docker is used,
        local migrations run before the deploy trigger fires.
        """
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = True

        # Create .railway directory so deploy gate triggers
        (tmp_path / ".railway").mkdir(parents=True, exist_ok=True)

        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = tmp_path
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = []
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.modules = {}
        ctx.qs_config.docker.start = True  # Docker-first project
        ctx.qs_config.docker.build = True

        with patch(
            "quickscale_cli.commands.apply_command.deploy_railway_service",
        ) as mock_deploy:
            mock_deploy.return_value = Mock(
                returncode=0, stderr="", stdout="Deploy started"
            )

            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=True,  # --no-docker overrides docker.start
                no_modules=False,
            )

        mock_deploy.assert_called_once_with(
            project_path=tmp_path,
            service_name="myapp",
        )
        mock_save_state.assert_called_once()
        mock_display_next_steps.assert_called_once()

    # ------------------------------------------------------------------
    # SA18.9: Step 4 abort path regression
    # ------------------------------------------------------------------

    @patch("quickscale_cli.commands.apply_command._save_apply_recovery_state")
    @patch(
        "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply"
    )
    @patch("quickscale_cli.commands.apply_command._print_apply_failure_summary")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_step4_hash_capture_failure_aborts_apply(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_print_failure,
        mock_capture_hashes,
        mock_save_recovery,
    ):
        """SA18.9: Step 4 failure must abort apply with the correct
        failed_step label through the full CLI pipeline.

        Regression: _execute_apply_steps_locked -> _capture_managed_file_hashes_after_apply
        -> _abort_after_post_embed_failure.
        """
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_capture_hashes.return_value = Mock(
            success=False,
            message="Simulated hash capture failure",
            failed_step_label="capture managed file hashes",
        )
        mock_save_recovery.return_value = True

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

        with pytest.raises(click.Abort):
            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=False,
                no_modules=False,
                verbose_docker=False,
            )

        # Verify step 4 was reached
        mock_capture_hashes.assert_called_once_with(ctx.output_path, ctx.qs_config, ANY)

        # Verify recovery state was saved (proving _abort_after_post_embed_failure
        # was reached with the correct failed_step)
        mock_save_recovery.assert_called_once()

        # Verify the failed_step label propagated correctly
        mock_print_failure.assert_called_once_with(
            failed_step="capture managed file hashes",
            reason=ANY,
        )

        # Verify subsequent steps were NOT reached
        mock_regenerate_wiring.assert_called_once()  # step 3 ran

    @patch("quickscale_cli.commands.apply_command._save_apply_recovery_state")
    @patch(
        "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply"
    )
    @patch("quickscale_cli.commands.apply_command._print_apply_failure_summary")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    def test_step4_hash_failure_recovery_save_fails_still_aborts(
        self,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_print_failure,
        mock_capture_hashes,
        mock_save_recovery,
    ):
        """When recovery state cannot be saved after step 4 failure,
        apply must still abort with a descriptive message."""
        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_capture_hashes.return_value = Mock(
            success=False,
            message="Simulated hash capture failure",
            failed_step_label="capture managed file hashes",
        )
        mock_save_recovery.return_value = False

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

        with pytest.raises(click.Abort):
            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=False,
                no_modules=False,
                verbose_docker=False,
            )

        # When recovery state cannot be saved, the failure message must
        # reference the recovery persistence failure (still aborts).
        mock_print_failure.assert_called_once_with(
            failed_step="apply recovery state persistence",
            reason=ANY,
        )


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

    @patch("quickscale_cli.commands.apply_command._generate_project")
    def test_force_with_failure_preserves_original(self, mock_gen, tmp_path):
        """Test force flag + generation failure preserves original project."""
        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")
        (output / "original_file.txt").write_text("preserve me")
        (output / "subdir").mkdir()
        (output / "subdir" / "nested.txt").write_text("nested")

        mock_gen.return_value = False
        mock_config = Mock()
        mock_config.project.slug = "myapp"

        with pytest.raises(click.Abort):
            _generate_with_existing_config(mock_config, output, config_file, True)

        # Original content must be preserved after a failed force generation
        assert config_file.read_text() == "original config"
        assert (output / "original_file.txt").exists()
        assert (output / "original_file.txt").read_text() == "preserve me"
        assert (output / "subdir").exists()
        assert (output / "subdir" / "nested.txt").exists()
        assert (output / "subdir" / "nested.txt").read_text() == "nested"

    @patch("quickscale_cli.commands.apply_command._generate_project")
    def test_force_staging_failure_rollback(self, mock_gen, tmp_path):
        """Force mode must restore original files if staging-phase filesystem ops fail.

        Proves CR-SA22-001 rollback: after the backup phase succeeds but a
        filesystem operation during the staging swap fails, the function
        restores all original files from backup and raises click.Abort().
        """
        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")
        (output / "original_file.txt").write_text("preserve me")
        (output / "subdir").mkdir()
        (output / "subdir" / "nested.txt").write_text("nested")

        mock_config = Mock()
        mock_config.project.slug = "myapp"

        def fake_generate(config, path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "manage.py").touch()
            (path / "new_file.py").touch()
            return True

        mock_gen.side_effect = fake_generate

        # Controlled shutil.move side effect:
        #   calls 1-2: backup phase (original_file.txt, subdir) -> real move
        #   call 3: first staging move (manage.py) -> real move
        #   call 4: second staging move (new_file.py) -> OSError
        #   calls 5+: rollback phase (restore from backup) -> real move
        move_counter: list[int] = [0]
        real_move = _real_shutil.move

        def controlled_move(src: str, dst: str) -> None:
            move_counter[0] += 1
            if move_counter[0] == 4:
                raise OSError("Simulated filesystem failure during staging swap")
            return real_move(src, dst)

        with patch("shutil.move", controlled_move):
            with pytest.raises(click.Abort):
                _generate_with_existing_config(mock_config, output, config_file, True)

        # Original files must be restored after rollback
        assert config_file.read_text() == "original config"
        assert (output / "original_file.txt").exists()
        assert (output / "original_file.txt").read_text() == "preserve me"
        assert (output / "subdir").exists()
        assert (output / "subdir" / "nested.txt").exists()
        assert (output / "subdir" / "nested.txt").read_text() == "nested"
        # Partially-moved staged files must be cleaned up by rollback
        assert not (output / "manage.py").exists()
        assert not (output / "new_file.py").exists()

    def test_force_temp_dirs_on_same_filesystem(self, tmp_path):
        """Force mode must create staging and backup dirs under output_path.parent
        to guarantee same-filesystem move semantics (CR-SA22-001)."""
        import tempfile as _real_tempfile

        # Save reference to real mkdtemp before any patches
        real_mkdtemp = _real_tempfile.mkdtemp

        output = tmp_path / "myapp"
        output.mkdir()
        config_file = output / "quickscale.yml"
        config_file.write_text("original config")
        (output / "old_file.txt").touch()

        mock_config = Mock()
        mock_config.project.slug = "myapp"

        captured_kwargs: list[dict] = []

        def tracking_mkdtemp(**kwargs: object) -> str:
            captured_kwargs.append(dict(kwargs))
            return real_mkdtemp(**kwargs)

        def fake_generate(config, path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "manage.py").touch()
            return True

        with patch("tempfile.mkdtemp", tracking_mkdtemp):
            with patch(
                "quickscale_cli.commands.apply_command._generate_project",
                side_effect=fake_generate,
            ):
                _generate_with_existing_config(mock_config, output, config_file, True)

        # mkdtemp called twice: once for staging (temp_dir), once for backup
        assert len(captured_kwargs) == 2, (
            f"Expected 2 mkdtemp calls, got {len(captured_kwargs)}"
        )
        expected_dir = str(output.parent)
        for i, kwargs in enumerate(captured_kwargs):
            assert kwargs.get("dir") == expected_dir, (
                f"mkdtemp call {i}: expected dir={expected_dir!r}, got {kwargs!r}"
            )


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


# ============================================================================
# CR-001 regression: apply planning must use ProjectStateManager.load_state()
# ============================================================================


class TestCR001PrepareApplyContextLegacyReadThrough:
    """CR-001: _prepare_apply_context must use ProjectStateManager.load_state().

    When ``state.yml`` lacks consolidated sections, apply planning must
    read-through import legacy ``config.yml`` module-tracking metadata
    instead of bypassing it via raw ``StateManager.load()``.
    """

    def test_prepare_apply_context_read_through_imports_legacy_config(self, tmp_path):
        """Apply planning must surface legacy config.yml tracking via load_state()."""
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
        qs_dir = project_path / ".quickscale"
        qs_dir.mkdir()
        # state.yml WITHOUT consolidated sections (no managed_files, no
        # module tracking fields like prefix/branch/installed_at).
        (qs_dir / "state.yml").write_text(
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
        )
        # Legacy config.yml WITH module tracking metadata.
        (qs_dir / "config.yml").write_text(
            'version: "1"\n'
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            '    installed_version: "0.82.0"\n'
            "    prefix: auth_\n"
            "    branch: main\n"
            '    installed_at: "2025-06-01T00:00:00"\n'
        )
        # Manifest for the installed module so strict loading succeeds.
        module_dir = project_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        ctx = _prepare_apply_context(config_path)

        # The loaded state must carry the legacy tracking fields via
        # read-through import, proving ProjectStateManager.load_state()
        # was used instead of raw StateManager.load().
        assert ctx.existing_state is not None
        auth_state = ctx.existing_state.modules.get("auth")
        assert auth_state is not None
        assert auth_state.prefix == "auth_"
        assert auth_state.branch == "main"
        assert auth_state.installed_at == "2025-06-01T00:00:00"


class TestCR001RefreshContextAfterLockLegacyReadThrough:
    """CR-001: _refresh_context_after_lock must use ProjectStateManager.load_state().

    The post-lock refresh must also read-through import legacy config.yml
    data so that locked planning operates on the same consolidated view.
    """

    def test_refresh_context_after_lock_read_through_imports_legacy(self, tmp_path):
        """Post-lock refresh must surface legacy config.yml tracking via load_state()."""
        project_path = tmp_path / "myapp"
        project_path.mkdir()
        qs_dir = project_path / ".quickscale"
        qs_dir.mkdir()
        # state.yml WITHOUT consolidated sections.
        (qs_dir / "state.yml").write_text(
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
        )
        # Legacy config.yml WITH module tracking metadata.
        (qs_dir / "config.yml").write_text(
            'version: "1"\n'
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            '    installed_version: "0.82.0"\n'
            "    prefix: auth_\n"
            "    branch: main\n"
            '    installed_at: "2025-06-01T00:00:00"\n'
        )
        # Manifest for the installed module.
        module_dir = project_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.82.0"\n')

        # Build a minimal ApplyContext with pre-lock state that lacks
        # legacy tracking (simulating raw StateManager.load() behavior).
        pre_lock_state = StateManager(project_path).load()
        assert pre_lock_state is not None
        # Pre-lock: auth module state has no tracking fields.
        assert pre_lock_state.modules["auth"].prefix is None

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}
        qs_config.docker.start = False
        qs_config.docker.build = False

        ctx = ApplyContext(
            config_path=project_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=project_path,
            state_manager=StateManager(project_path),
            existing_state=pre_lock_state,
            manifests={},
            delta=Mock(),
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        _refresh_context_after_lock(ctx)

        # Post-lock refresh must have read-through imported legacy tracking.
        assert ctx.existing_state is not None
        auth_state = ctx.existing_state.modules.get("auth")
        assert auth_state is not None
        assert auth_state.prefix == "auth_"
        assert auth_state.branch == "main"
        assert auth_state.installed_at == "2025-06-01T00:00:00"

    def test_malformed_recovery_ledger_fails_hard_in_refresh(self, tmp_path) -> None:
        """CR-F12.1D-001: malformed apply-recovery.yml must fail hard in
        _refresh_context_after_lock instead of being silently treated as absent."""
        project_path = tmp_path / "myapp"
        project_path.mkdir()
        qs_dir = project_path / ".quickscale"
        qs_dir.mkdir()
        # Valid state.yml so the refresh proceeds past the authoritative
        # state load to the recovery state load.
        (qs_dir / "state.yml").write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_html\n"
            '  created_at: "2025-01-01T00:00:00"\n'
            '  last_applied: "2025-01-01T00:00:00"\n'
            "modules: {}\n"
        )
        # Malformed recovery ledger — not valid YAML for the schema.
        (qs_dir / "apply-recovery.yml").write_text("not-a-valid-ledger: [broken\n")

        pre_lock_state = StateManager(project_path).load()
        assert pre_lock_state is not None

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {}
        qs_config.docker.start = False
        qs_config.docker.build = False

        ctx = ApplyContext(
            config_path=project_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=project_path,
            state_manager=StateManager(project_path),
            existing_state=pre_lock_state,
            manifests={},
            delta=Mock(),
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        # Must propagate StateError/LedgerError instead of suppressing it.
        with pytest.raises(StateError, match="Failed to parse recovery ledger"):
            _refresh_context_after_lock(ctx)


# ============================================================================
# CR-002 regression: post-lock gate re-evaluation
# ============================================================================


class TestCR002PostLockGateReEvaluation:
    """CR-002: apply must re-run gate decisions after the lock refresh.

    If another concurrent apply finishes between the pre-lock read and
    lock acquisition, the refreshed state may show no changes. Apply
    must abort instead of continuing to mutate based on stale decisions.
    """

    @patch("quickscale_cli.commands.apply_command._refresh_context_after_lock")
    @patch("quickscale_cli.commands.apply_command.AdvisoryLock")
    def test_post_lock_no_op_aborts_apply(self, mock_lock_cls, mock_refresh):
        """Apply must abort when post-lock refresh reveals no changes."""

        def _simulate_concurrent_apply_won(ctx):
            """Simulate another apply winning the race: delta becomes no-op."""
            ctx.existing_state = QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                    created_at="2025-01-01T00:00:00",
                    last_applied="2025-06-17T00:00:00",
                ),
                modules={},
            )
            ctx.delta = Mock()
            ctx.delta.has_changes = False
            ctx.delta.modules_to_remove = []
            ctx.delta.has_immutable_config_changes = False
            ctx.delta.theme_changed = False
            ctx.has_pending_post_embed_recovery = False
            ctx.had_existing_state = True

        mock_refresh.side_effect = _simulate_concurrent_apply_won

        mock_lock = Mock()
        mock_lock_cls.return_value = mock_lock

        # Pre-lock context: delta shows changes (apply would proceed).
        pre_lock_delta = Mock()
        pre_lock_delta.has_changes = True
        pre_lock_delta.modules_to_add = ["auth"]
        pre_lock_delta.modules_to_remove = []
        pre_lock_delta.has_immutable_config_changes = False
        pre_lock_delta.theme_changed = False
        pre_lock_delta.modules_unchanged = []

        ctx = Mock()
        ctx.existing_state = QuickScaleState(
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
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = pre_lock_delta
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = False
        ctx.has_pending_post_embed_recovery = False
        ctx.had_existing_state = True

        with pytest.raises(click.Abort):
            _execute_apply_steps(
                ctx,
                force=False,
                no_docker=True,
                no_modules=False,
                verbose_docker=False,
            )

        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()

    @patch("quickscale_cli.commands.apply_command._refresh_context_after_lock")
    @patch("quickscale_cli.commands.apply_command.AdvisoryLock")
    def test_post_lock_immutable_changes_abort_apply(self, mock_lock_cls, mock_refresh):
        """Apply must abort when post-lock refresh reveals immutable changes."""

        def _simulate_immutable_changes_appear(ctx):
            """Simulate state change that introduces immutable config changes."""
            ctx.existing_state = QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                    created_at="2025-01-01T00:00:00",
                    last_applied="2025-06-17T00:00:00",
                ),
                modules={},
            )
            immutable_change = Mock()
            immutable_change.option_name = "method"
            immutable_change.old_value = "email"
            immutable_change.new_value = "username"
            ctx.delta = Mock()
            ctx.delta.has_changes = True
            ctx.delta.modules_to_remove = []
            ctx.delta.has_immutable_config_changes = True
            ctx.delta.get_all_immutable_changes.return_value = [
                ("auth", immutable_change)
            ]
            ctx.delta.theme_changed = False
            ctx.has_pending_post_embed_recovery = False
            ctx.had_existing_state = True

        mock_refresh.side_effect = _simulate_immutable_changes_appear

        mock_lock = Mock()
        mock_lock_cls.return_value = mock_lock

        pre_lock_delta = Mock()
        pre_lock_delta.has_changes = True
        pre_lock_delta.modules_to_add = ["auth"]
        pre_lock_delta.modules_to_remove = []
        pre_lock_delta.has_immutable_config_changes = False
        pre_lock_delta.theme_changed = False
        pre_lock_delta.modules_unchanged = []

        ctx = Mock()
        ctx.existing_state = QuickScaleState(
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
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = pre_lock_delta
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = False
        ctx.has_pending_post_embed_recovery = False
        ctx.had_existing_state = True

        with patch(
            "quickscale_cli.commands.apply_command.format_delta",
            return_value="changes",
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=True,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()

    @patch("quickscale_cli.commands.apply_command._refresh_context_after_lock")
    @patch("quickscale_cli.commands.apply_command.AdvisoryLock")
    def test_post_lock_config_removal_aborts_apply(self, mock_lock_cls, mock_refresh):
        """Apply must abort when post-lock refresh reveals config-driven removals."""

        def _simulate_config_removal_appears(ctx):
            """Simulate state change that introduces module removals."""
            ctx.existing_state = QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                    created_at="2025-01-01T00:00:00",
                    last_applied="2025-06-17T00:00:00",
                ),
                modules={},
            )
            ctx.delta = Mock()
            ctx.delta.has_changes = True
            ctx.delta.modules_to_remove = ["auth"]
            ctx.delta.has_immutable_config_changes = False
            ctx.delta.theme_changed = False
            ctx.has_pending_post_embed_recovery = False
            ctx.had_existing_state = True

        mock_refresh.side_effect = _simulate_config_removal_appears

        mock_lock = Mock()
        mock_lock_cls.return_value = mock_lock

        pre_lock_delta = Mock()
        pre_lock_delta.has_changes = True
        pre_lock_delta.modules_to_add = ["auth"]
        pre_lock_delta.modules_to_remove = []
        pre_lock_delta.has_immutable_config_changes = False
        pre_lock_delta.theme_changed = False
        pre_lock_delta.modules_unchanged = []

        ctx = Mock()
        ctx.existing_state = QuickScaleState(
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
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = pre_lock_delta
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = False
        ctx.qs_config.docker.build = False
        ctx.has_pending_post_embed_recovery = False
        ctx.had_existing_state = True

        with patch(
            "quickscale_cli.commands.apply_command.format_delta",
            return_value="changes",
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps(
                    ctx,
                    force=False,
                    no_docker=True,
                    no_modules=False,
                    verbose_docker=False,
                )

        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()


# ============================================================================
# CR-F12.3B-002 regression: recovery-rerun migration gate
# ============================================================================


class TestCRF12_3B_002RecoveryRerunMigrationGate:
    """CR-F12.3B-002: recovery rerun migration gate must use post-refresh context.

    When a recovery rerun acquires the lock, ``_refresh_context_after_lock``
    populates ``ctx.existing_state`` from the recovery ledger. The migration
    gate inside ``_execute_apply_steps_locked`` must re-evaluate using this
    fresh ``ctx.existing_state`` — not a stale pre-lock capture — so that
    local migrations run before Railway deploy (CR-F12.3B-002).
    """

    @patch("quickscale_cli.commands.apply_command._display_next_steps")
    @patch("quickscale_cli.commands.apply_command._save_project_state")
    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_post_generation_steps")
    @patch(
        "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply"
    )
    @patch("quickscale_cli.commands.apply_command._sync_analytics_env_example")
    @patch("quickscale_cli.commands.apply_command._sync_notifications_env_example")
    @patch("quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules")
    @patch("quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply")
    @patch("quickscale_cli.commands.apply_command._capture_git_index_snapshot")
    @patch("quickscale_cli.commands.apply_command._embed_modules_step")
    @patch("quickscale_cli.commands.apply_command._init_git_with_config")
    @patch("quickscale_cli.commands.apply_command._generate_new_project")
    @patch("quickscale_cli.commands.apply_command._refresh_context_after_lock")
    @patch("quickscale_cli.commands.apply_command.AdvisoryLock")
    def test_recovery_rerun_migration_gate_uses_post_lock_context(
        self,
        mock_lock_cls,
        mock_refresh,
        mock_generate_new_project,
        mock_init_git,
        mock_embed_modules_step,
        mock_capture_checkpoint,
        mock_regenerate_wiring,
        mock_backups_gitignore,
        mock_notifications_env_sync,
        mock_analytics_env_sync,
        mock_sync_module_dependencies,
        mock_run_post,
        mock_run_migrations,
        mock_save_state,
        mock_display_next_steps,
    ):
        """Recovery rerun: migration gate re-evaluates with refreshed context.

        Pre-lock ``ctx.existing_state`` is None (no authoritative state.yml,
        only a recovery ledger).  After ``_refresh_context_after_lock``
        populates state from the ledger, the migration gate must see an
        existing project and schedule local migrations.
        """

        def _simulate_recovery_rerun(ctx):
            """Simulate a rerun that populates state after lock acquisition."""
            ctx.existing_state = QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp",
                    package="myapp",
                    theme="showcase_html",
                    created_at="2025-01-01T00:00:00",
                    last_applied="2025-06-21T00:00:00",
                ),
                modules={},
            )
            ctx.delta = Mock()
            ctx.delta.modules_to_add = []
            ctx.delta.has_changes = False
            ctx.delta.modules_to_remove = []
            ctx.delta.has_immutable_config_changes = False
            ctx.delta.theme_changed = False
            ctx.has_pending_post_embed_recovery = True
            ctx.had_existing_state = True

        mock_refresh.side_effect = _simulate_recovery_rerun

        mock_lock = Mock()
        mock_lock_cls.return_value = mock_lock

        mock_embed_modules_step.return_value = EmbedModulesResult(
            success=True,
            embedded_modules=[],
            failed_module=None,
        )
        mock_capture_checkpoint.return_value = Mock(tree_id="a" * 40)
        mock_regenerate_wiring.return_value = True
        mock_backups_gitignore.return_value = True
        mock_notifications_env_sync.return_value = True
        mock_analytics_env_sync.return_value = True
        mock_sync_module_dependencies.return_value = True
        mock_run_post.return_value = True
        mock_save_state.return_value = True

        # Pre-lock: existing_state is None so a stale pre-lock capture
        # would set existing_project=False.  The fix must use the
        # post-refresh ctx.existing_state instead.
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

        _execute_apply_steps(
            ctx,
            force=False,
            no_docker=True,
            no_modules=False,
            verbose_docker=False,
        )

        # The migration gate must re-evaluate with the post-refresh
        # context: existing_state is populated → existing_project=True →
        # Local migrations are now deferred to step 13 (AF5 Phase 4).
        mock_run_post.assert_called_once_with(ctx.output_path)


# ============================================================================
# Phase 3: Bounded no-op provenance repair
# ============================================================================


class TestPhase3NoOpProvenanceRepair:
    """Phase 3 tests: bounded best-effort provenance repair for no-op scenarios."""

    def test_successful_repair_writes_state_and_second_apply_is_noop(self, tmp_path):
        """Phase 3 checkpoint: successful repair writes state, second apply is true no-op."""
        # Create a minimal module manifest
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        # Build state with missing commit_sha
        existing_state = QuickScaleState(
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
                    version="0.83.0",
                    commit_sha=None,  # Missing!
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}

        # Delta shows no changes (no-op scenario)
        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        # Mock resolve_remote_ref to return a SHA
        resolved_sha = "b" * 40
        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref",
            return_value=resolved_sha,
        ):
            _attempt_provenance_repair_if_needed(ctx)

        # Verify state was written with repaired commit_sha
        state_path = tmp_path / ".quickscale" / "state.yml"
        assert state_path.exists()

        state_manager = StateManager(tmp_path)
        saved_state = state_manager.load()
        assert saved_state is not None
        assert "auth" in saved_state.modules
        assert saved_state.modules["auth"].commit_sha == resolved_sha

        # Verify no recovery file was created
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        assert not recovery_path.exists()

        # Verify delta was refreshed to show no changes
        assert ctx.delta.has_changes is False

    def test_failed_repair_warns_and_preserves_noop(self, tmp_path):
        """Phase 3 checkpoint: failed repair warns, does not write state, preserves no-op."""
        # Create a minimal module manifest
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        # Build state with missing commit_sha
        existing_state = QuickScaleState(
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
                    version="0.83.0",
                    commit_sha=None,  # Missing!
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}

        # Delta shows no changes (no-op scenario)
        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        # Mock resolve_remote_ref to raise an error
        from quickscale_core.utils.git_utils import GitError

        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref",
            side_effect=GitError("Network error"),
        ):
            _attempt_provenance_repair_if_needed(ctx)

        # Verify state was NOT written
        state_path = tmp_path / ".quickscale" / "state.yml"
        assert not state_path.exists()

        # Verify no recovery file was created
        recovery_path = tmp_path / ".quickscale" / "apply-recovery.yml"
        assert not recovery_path.exists()

        # Verify existing state still has missing commit_sha
        assert existing_state.modules["auth"].commit_sha is None

    def test_no_repair_attempted_when_no_missing_commit_sha(self, tmp_path):
        """Phase 3: repair is skipped when all modules have commit_sha."""
        # Build state with commit_sha already present
        existing_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
            ),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.83.0",
                    commit_sha="a" * 40,  # Already present
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.modules = {"auth": Mock(options={})}

        delta = Mock()
        delta.has_changes = False

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        # Mock resolve_remote_ref - should NOT be called
        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref"
        ) as mock_resolve:
            _attempt_provenance_repair_if_needed(ctx)
            mock_resolve.assert_not_called()

    def test_no_repair_attempted_when_delta_has_changes(self, tmp_path):
        """Phase 3: repair is skipped when delta has changes (not a no-op)."""
        # Build state with missing commit_sha
        existing_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
            ),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.83.0",
                    commit_sha=None,
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.modules = {"auth": Mock(options={})}

        # Delta HAS changes (not a no-op)
        delta = Mock()
        delta.has_changes = True

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        # Mock resolve_remote_ref - should NOT be called
        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref"
        ) as mock_resolve:
            _attempt_provenance_repair_if_needed(ctx)
            mock_resolve.assert_not_called()


# ============================================================================
# Phase 4: Full provenance triple consistency
# ============================================================================


class TestProvenanceTripleConsistency:
    """F2.6 tests: all three paths persist the full provenance triple
    (version, commit_sha, embedded_at) consistently."""

    def test_apply_path_populates_full_triple(self, tmp_path):
        """Apply path: _build_project_state_snapshot populates version,
        commit_sha, and embedded_at for freshly embedded modules."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        resolved_sha = "a" * 40
        provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        state = _build_project_state_snapshot(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=provenance,
        )

        assert "auth" in state.modules
        module_state = state.modules["auth"]
        # Full triple: version, commit_sha, embedded_at
        assert module_state.version == "0.83.0"
        assert module_state.commit_sha == resolved_sha
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""

    def test_noop_repair_backfills_full_triple(self, tmp_path):
        """No-op repair: _attempt_provenance_repair_if_needed backfills
        version, commit_sha, and embedded_at for modules with missing
        commit_sha."""
        # Create a minimal module manifest
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        # Build state with missing commit_sha and no embedded_at
        existing_state = QuickScaleState(
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
                    version=None,  # Missing!
                    commit_sha=None,  # Missing!
                    embedded_at="",  # Empty!
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}

        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        resolved_sha = "c" * 40
        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref",
            return_value=resolved_sha,
        ):
            _attempt_provenance_repair_if_needed(ctx)

        # Verify full triple was backfilled
        state_path = tmp_path / ".quickscale" / "state.yml"
        assert state_path.exists()

        state_manager = StateManager(tmp_path)
        saved_state = state_manager.load()
        assert saved_state is not None
        assert "auth" in saved_state.modules
        module_state = saved_state.modules["auth"]
        # Full triple: version, commit_sha, embedded_at
        assert module_state.commit_sha == resolved_sha
        assert module_state.version == "0.83.0"
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""


# ============================================================================
# CR-F26-001: Lock-discipline regression coverage
# ============================================================================


class TestProvenanceRepairMightBeNeeded:
    """Tests for _provenance_repair_might_be_needed probe."""

    def test_returns_false_when_no_existing_state(self, tmp_path):
        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=Mock(),
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=None,
            manifests={},
            delta=Mock(has_changes=False),
        )
        assert _provenance_repair_might_be_needed(ctx) is False

    def test_returns_false_when_delta_has_changes(self, tmp_path):
        existing_state = QuickScaleState(
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
                    version=None,
                    commit_sha=None,
                    embedded_at="",
                    branch="splits/auth-module",
                ),
            },
        )
        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=Mock(),
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=Mock(has_changes=True),
        )
        assert _provenance_repair_might_be_needed(ctx) is False

    def test_returns_true_when_modules_missing_commit_sha(self, tmp_path):
        existing_state = QuickScaleState(
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
                    version=None,
                    commit_sha=None,
                    embedded_at="",
                    branch="splits/auth-module",
                ),
            },
        )
        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=Mock(),
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=Mock(has_changes=False),
        )
        assert _provenance_repair_might_be_needed(ctx) is True

    def test_returns_false_when_all_modules_have_commit_sha(self, tmp_path):
        existing_state = QuickScaleState(
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
                    version="0.83.0",
                    commit_sha="a" * 40,
                    embedded_at="2025-01-01T00:00:00",
                    branch="splits/auth-module",
                ),
            },
        )
        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=Mock(),
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=Mock(has_changes=False),
        )
        assert _provenance_repair_might_be_needed(ctx) is False


class TestHandleDeltaPendingProvenanceRepair:
    """CR-F26-001: no-op gate must defer to locked provenance-repair path."""

    def test_noop_gate_defers_when_provenance_repair_pending(self):
        """has_pending_provenance_repair=True must bypass the no-op abort."""
        delta = Mock()
        delta.has_changes = False
        state = Mock()

        with patch(
            "quickscale_cli.commands.apply_command.format_delta", return_value="none"
        ):
            # Must NOT raise click.Abort
            _handle_delta_and_existing_state(
                delta,
                state,
                has_pending_provenance_repair=True,
            )

    def test_noop_gate_still_aborts_without_provenance_repair(self):
        """Without the flag, no-op must still abort as before."""
        delta = Mock()
        delta.has_changes = False
        state = Mock()

        with pytest.raises(click.Abort):
            _handle_delta_and_existing_state(
                delta,
                state,
                has_pending_provenance_repair=False,
            )

    def test_noop_repair_does_not_write_state_before_lock(self, tmp_path):
        """CR-F26-001 regression: the pre-lock probe must not write state.yml.

        The probe (_provenance_repair_might_be_needed) is read-only.  The
        actual state write must only happen inside the locked path.
        """
        existing_state = QuickScaleState(
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
                    version=None,
                    commit_sha=None,
                    embedded_at="",
                    branch="splits/auth-module",
                ),
            },
        )
        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=Mock(),
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=Mock(has_changes=False),
        )

        # The probe is read-only — it must not create state.yml
        result = _provenance_repair_might_be_needed(ctx)
        assert result is True

        state_path = tmp_path / ".quickscale" / "state.yml"
        assert not state_path.exists(), (
            "CR-F26-001: pre-lock probe must not write state.yml"
        )


# ============================================================================
# F2.7: Caller parity across provenance paths
# ============================================================================


class TestCallerParityAcrossProvenancePaths:
    """F2.7 tests: all provenance-writing callers follow the same pattern.

    Caller parity means:
    1. Each path resolves the source ref exactly once per module.
    2. For apply and update, the resolved SHA drives both the git subtree
       operation and state persistence.  No-op repair resolves once and
       backfills authoritative state but performs no git operation.
    3. All convergent paths persist the full provenance triple
       (version, commit_sha, embedded_at).
    4. Standalone embed intentionally diverges (no source_ref resolution).
    """

    def test_apply_path_resolves_source_ref_once_and_persists_triple(self, tmp_path):
        """Apply path: embed_module(APPLY_MODE) resolves source_ref once,
        carries it via ModuleEmbedProvenance, and persists the full triple."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        resolved_sha = "a" * 40
        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        state = _build_project_state_snapshot(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=provenance,
        )

        # Full triple persisted from the resolved source_ref.
        module_state = state.modules["auth"]
        assert module_state.commit_sha == resolved_sha
        assert module_state.version == "0.83.0"
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""

    def test_update_path_resolves_source_ref_once_and_persists_triple(self, tmp_path):
        """Update path: _update_single_module resolves source_ref once and
        persists the full triple via _sync_state_module_version."""
        from quickscale_core.schema.state_schema import StateManager

        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        state_path = quickscale_dir / "state.yml"
        state_path.write_text(
            "\n".join(
                [
                    'version: "1"',
                    "project:",
                    "  slug: myapp",
                    "  package: myapp",
                    "  theme: showcase_html",
                    '  created_at: "2025-01-01T00:00:00"',
                    '  last_applied: "2025-01-01T00:00:00"',
                    "modules:",
                    "  auth:",
                    "    name: auth",
                    '    version: "0.82.0"',
                    '    commit_sha: "old_sha"',
                    '    embedded_at: "2025-01-01T00:00:00"',
                    "    prefix: modules/auth",
                    "    branch: splits/auth-module",
                    '    installed_at: "2025-01-01"',
                ]
            )
            + "\n"
        )

        resolved_sha = "b" * 40

        def _fake_subtree_pull(*, prefix, remote, branch, squash):
            del remote, branch, squash
            (tmp_path / prefix / "module.yml").write_text(
                'name: auth\nversion: "0.83.0"\n'
            )
            return "updated"

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            module_info = Mock(prefix="modules/auth", branch="splits/auth-module")

            with (
                patch(
                    "quickscale_cli.commands.module_commands.resolve_remote_ref",
                    return_value=resolved_sha,
                ) as mock_resolve,
                patch(
                    "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                    side_effect=_fake_subtree_pull,
                ),
                patch(
                    "quickscale_cli.commands.module_commands._read_embedded_module_version",
                    return_value="0.83.0",
                ),
                patch(
                    "quickscale_cli.commands.module_commands._commit_module_update",
                ),
            ):
                result = _update_single_module(
                    "auth",
                    module_info,
                    "https://github.com/Experto-AI/quickscale.git",
                    no_preview=True,
                )
        finally:
            os.chdir(original_cwd)

        assert result is True
        # Source ref resolved exactly once.
        mock_resolve.assert_called_once()

        # Full triple persisted from the resolved source_ref.
        state_manager = StateManager(tmp_path)
        updated_state = state_manager.load()
        assert updated_state is not None
        module_state = updated_state.modules["auth"]
        assert module_state.commit_sha == resolved_sha
        assert module_state.version == "0.83.0"
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""
        assert module_state.embedded_at != "2025-01-01T00:00:00"

    def test_noop_repair_resolves_source_ref_once_and_persists_triple(self, tmp_path):
        """No-op repair: _attempt_provenance_repair_if_needed resolves
        remote_ref once and backfills the full triple."""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        existing_state = QuickScaleState(
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
                    version=None,
                    commit_sha=None,
                    embedded_at="",
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}

        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=existing_state,
            manifests={},
            delta=delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        resolved_sha = "c" * 40
        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref",
            return_value=resolved_sha,
        ) as mock_resolve:
            _attempt_provenance_repair_if_needed(ctx)

        # Source ref resolved exactly once.
        mock_resolve.assert_called_once()

        # Full triple persisted from the resolved source_ref.
        state_manager = StateManager(tmp_path)
        saved_state = state_manager.load()
        assert saved_state is not None
        module_state = saved_state.modules["auth"]
        assert module_state.commit_sha == resolved_sha
        assert module_state.version == "0.83.0"
        assert module_state.embedded_at is not None
        assert module_state.embedded_at != ""

    def test_all_convergent_paths_persist_same_triple_structure(self, tmp_path):
        """All three convergent paths produce the same triple fields.

        This test proves structural parity: apply, update, and no-op repair
        all persist version, commit_sha, and embedded_at as non-empty values.
        """
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text('name: auth\nversion: "0.83.0"\n')

        resolved_sha = "d" * 40

        # --- Apply path ---
        config = Mock()
        config.project.slug = "myapp"
        config.project.package = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        apply_provenance = {
            "auth": ModuleEmbedProvenance(
                module_name="auth",
                prefix="modules/auth",
                tracking_branch="splits/auth-module",
                source_ref=resolved_sha,
                installed_version="0.83.0",
            )
        }

        apply_state = _build_project_state_snapshot(
            tmp_path,
            config,
            existing_state=None,
            embedded_modules=["auth"],
            delta=delta,
            provenance_payloads=apply_provenance,
        )
        apply_module = apply_state.modules["auth"]

        # --- No-op repair path ---
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        repair_existing_state = QuickScaleState(
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
                    version=None,
                    commit_sha=None,
                    embedded_at="",
                    branch="splits/auth-module",
                ),
            },
        )

        qs_config = Mock()
        qs_config.project.slug = "myapp"
        qs_config.project.package = "myapp"
        qs_config.project.theme = "showcase_html"
        qs_config.modules = {"auth": Mock(options={})}

        repair_delta = Mock()
        repair_delta.has_changes = False
        repair_delta.modules_to_add = []
        repair_delta.modules_to_remove = []

        ctx = ApplyContext(
            config_path=tmp_path / "quickscale.yml",
            qs_config=qs_config,
            output_path=tmp_path,
            state_manager=StateManager(tmp_path),
            existing_state=repair_existing_state,
            manifests={},
            delta=repair_delta,
            has_pending_post_embed_recovery=False,
            had_existing_state=True,
        )

        with patch(
            "quickscale_cli.commands.apply_command.resolve_remote_ref",
            return_value=resolved_sha,
        ):
            _attempt_provenance_repair_if_needed(ctx)

        state_manager = StateManager(tmp_path)
        repair_state = state_manager.load()
        assert repair_state is not None
        repair_module = repair_state.modules["auth"]

        # --- Structural parity assertion ---
        # Both paths persist the same triple fields with non-empty values.
        for path_name, module_state in [
            ("apply", apply_module),
            ("no-op repair", repair_module),
        ]:
            assert module_state.commit_sha == resolved_sha, (
                f"{path_name}: commit_sha mismatch"
            )
            assert module_state.version == "0.83.0", f"{path_name}: version mismatch"
            assert module_state.embedded_at is not None, (
                f"{path_name}: embedded_at is None"
            )
            assert module_state.embedded_at != "", f"{path_name}: embedded_at is empty"

    def test_standalone_embed_intentionally_diverges_from_provenance_resolution(
        self,
    ):
        """Standalone embed does NOT resolve source_ref.

        This is intentional divergence: standalone embeds use the tracking
        branch name directly for the subtree add and do not produce a
        ModuleEmbedProvenance payload.  Caller parity applies to the three
        convergent paths (apply, update, no-op repair); standalone embed
        is documented as intentionally divergent.
        """
        # This test documents the intentional divergence.  The actual
        # behavior is tested by test_standalone_embed_does_not_resolve_source_ref
        # in test_module_commands.py.  Here we assert the design contract:
        # standalone embeds do not participate in the provenance resolution
        # pattern that apply/update/no-op repair follow.
        from quickscale_cli.commands.module_config import (
            STANDALONE_MODULE_EXECUTION_MODE,
        )

        # Standalone mode is the default for embed_module.
        assert STANDALONE_MODULE_EXECUTION_MODE != "apply"
        # The ModuleEmbedProvenance is only produced when source_ref is
        # resolved, which only happens in APPLY_MODULE_EXECUTION_MODE.
        # Standalone embeds leave provenance_sink empty.


# ============================================================================
# F12.1c Phase 3: Caller-Parity Pass — failure-summary text parity
# ============================================================================


# All 12 unique failed_step labels from APPLY_STEPS (registry-backed).
# NOTE: reason strings here are synthetic/shortened for formatter-shape testing.
_F12_1C_UNIQUE_FAILED_STEP_LABELS: list[tuple[str, str]] = [
    ("module embedding", "required module 'blog' failed to embed"),
    ("post-embed state snapshot", "could not compute post-embed state"),
    ("managed module wiring generation", "unable to render managed files"),
    ("backups gitignore hardening", "unable to update .gitignore"),
    ("notifications env example sync", "unable to sync notifications env vars"),
    ("analytics env example sync", "unable to sync analytics env vars"),
    ("billing env example sync", "unable to sync billing env vars"),
    ("module dependency sync", "unable to reconcile module deps"),
    (
        "post-generation dependency and migration setup",
        "poetry lock/install failed",
    ),
    ("docker startup", "Docker auto-start failed"),
    ("database migrations", "migrations failed inside Docker"),
    ("authoritative state persistence", "could not save authoritative state"),
]


def _expected_failure_summary_lines(failed_step: str, reason: str) -> list[str]:
    """Return the expected output lines from _print_apply_failure_summary.

    AF5 Phase 4: Updated skipped-steps list to reflect the new destructive/
    remote phase boundary.  Migrations are now grouped with Docker startup
    and Railway deploy in the late confirmable phase.
    """
    sep = "=" * 50
    return [
        "",
        sep,
        "❌ Apply failed",
        sep,
        "",
        f"Failed step: {failed_step}",
        f"Reason: {reason}",
        "",
        "Skipped downstream steps:",
        "  • poetry install",
        "  • docker start",
        "  • database migrations",
        "  • railway deploy",
        "  • success completion output",
    ]


class TestApplyFailureSummaryParity:
    """F12.1c Phase 3 + closeout: Failure-summary output parity for all 15 callers.

    The 12 unique registry-backed labels are tested via parametrized
    direct calls to :func:`_print_apply_failure_summary` with synthetic
    reason strings, proving the formatter shape (header, label, reason,
    skipped-steps tail).  The three ``authoritative state persistence``
    callers are tested via caller-driven integration-style tests that
    exercise the real production branches with exact byte-identical
    line-by-line assertions.  The sentinel ``apply recovery state
    persistence`` is tested as a literal outside the registry.  The 11
    non-authoritative caller branches are tested via real production
    failure branches through :func:`_execute_apply_steps_locked` with
    exact byte-identical line-by-line parity (F12.1c-closeout).
    """

    @pytest.mark.parametrize("failed_step,reason", _F12_1C_UNIQUE_FAILED_STEP_LABELS)
    def test_failure_summary_exact_output(self, capsys, failed_step, reason):
        """Every registry-backed failed_step label produces byte-identical summary."""
        _print_apply_failure_summary(failed_step=failed_step, reason=reason)

        captured = capsys.readouterr()
        output_lines = captured.out.splitlines()

        expected = _expected_failure_summary_lines(failed_step, reason)
        assert output_lines == expected, (
            f"Output mismatch for failed_step={failed_step!r}"
        )

        # Also confirm the label survived through to stderr (secho to stdout
        # for the header, but no err output from _print_apply_failure_summary).
        assert captured.err == ""

    @pytest.mark.parametrize("failed_step,reason", _F12_1C_UNIQUE_FAILED_STEP_LABELS)
    def test_failure_summary_contains_label_and_reason(
        self, capsys, failed_step, reason
    ):
        """Substring smoke test: each label and reason appears in output."""
        _print_apply_failure_summary(failed_step=failed_step, reason=reason)

        captured = capsys.readouterr()
        output = captured.out

        assert failed_step in output
        assert reason in output
        assert "❌ Apply failed" in output
        assert "Skipped downstream steps:" in output
        assert "  • poetry install" in output
        assert "  • docker start" in output
        assert "  • database migrations" in output
        assert "  • railway deploy" in output
        assert "  • success completion output" in output

    # ------------------------------------------------------------------
    # Sentinel structural check (not in registry)
    # ------------------------------------------------------------------

    def test_sentinel_apply_recovery_state_persistence_not_in_registry(self):
        """The sentinel 'apply recovery state persistence' is a literal, not
        registry-backed.  It must not appear in APPLY_STEPS with a
        failed_step_label."""
        from quickscale_core.apply import APPLY_STEPS

        sentinel = "apply recovery state persistence"
        registry_labels = {
            s.failed_step_label for s in APPLY_STEPS if s.failed_step_label is not None
        }
        registry_ids = {s.step_id for s in APPLY_STEPS}

        assert sentinel not in registry_labels, (
            "The sentinel must not be registry-backed"
        )
        assert sentinel not in registry_ids, "The sentinel must not appear as a step_id"

    # ------------------------------------------------------------------
    # Sentinel caller-driven literal test (exact byte-identical)
    # ------------------------------------------------------------------

    def test_sentinel_apply_recovery_state_persistence_literal_output(self, capsys):
        """The sentinel 'apply recovery state persistence' is emitted as a
        literal when post-embed failure abort cannot save recovery state.
        Output must contain exactly that literal — not sourced from any
        registry — plus the failed-step reason referencing the original
        step failure and apply-recovery.yml.
        """
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=False,
            ) as mock_save_recovery,
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "apply recovery state persistence",
            "managed module wiring generation failed and QuickScale "
            "could not save .quickscale/apply-recovery.yml for rerun recovery.",
        )
        assert lines == expected, "Byte-identical output mismatch for sentinel literal"
        assert captured.err == ""
        mock_save_recovery.assert_called_once()

    # ------------------------------------------------------------------
    # Authoritative-state-persistence callers (exact byte-identical)
    # ------------------------------------------------------------------

    def test_authoritative_state_persistence_site_1_partial_embed_save_failure(
        self, capsys
    ):
        """Site 1 (L2747-L2754): partial embed saved state but final save failed.
        Output must show ``Failed step: authoritative state persistence``
        with the exact reason text containing the failed module name and
        ``.quickscale/state.yml``.  Recovery state must not be cleared.
        """
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
            ) as mock_embed,
            patch(
                "quickscale_cli.commands.apply_command._save_project_state",
                return_value=False,
            ) as mock_save_state,
            patch(
                "quickscale_cli.commands.apply_command._clear_apply_recovery_state",
            ) as mock_clear_recovery,
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            mock_embed.return_value = EmbedModulesResult(
                success=False,
                embedded_modules=["auth"],
                failed_module="blog",
            )

            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "authoritative state persistence",
            "required module 'blog' failed to embed, and QuickScale "
            "could not save partial authoritative state to "
            ".quickscale/state.yml.",
        )
        assert lines == expected, (
            "Byte-identical output mismatch for authoritative site 1"
        )
        assert captured.err == ""
        mock_save_state.assert_called_once()
        mock_clear_recovery.assert_not_called()

    def test_authoritative_state_persistence_site_2_recovery_preserved(self, capsys):
        """Site 2 (L2537-L2544): state save failed, recovery was preserved.
        Output must be exact byte-identical with reason mentioning
        ``apply-recovery.yml`` and ``rerunnable``.
        """
        ctx = Mock()
        ctx.output_path = Path("/tmp/proj")
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.project.package = "myapp"
        ctx.qs_config.project.theme = "showcase_html"
        ctx.qs_config.modules = {}
        ctx.existing_state = None
        ctx.delta = Mock()
        ctx.delta.config_deltas = {}

        post_embed_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
            ),
            modules={},
        )

        with (
            patch(
                "quickscale_cli.commands.apply_command._save_project_state",
                return_value=False,
            ) as mock_save_state,
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ) as mock_save_recovery,
            patch(
                "quickscale_cli.commands.apply_command._clear_apply_recovery_state",
            ) as mock_clear_recovery,
        ):
            with pytest.raises(click.Abort):
                _finalize_apply_state(
                    ctx, post_embed_state, checkpoint_tree_id="c" * 40
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "authoritative state persistence",
            "All apply steps completed, but QuickScale could not save "
            ".quickscale/state.yml. Recovery state was saved to "
            ".quickscale/apply-recovery.yml so apply remains rerunnable.",
        )
        assert lines == expected, (
            "Byte-identical output mismatch for authoritative site 2"
        )
        assert captured.err == ""
        mock_save_state.assert_called_once()
        mock_save_recovery.assert_called_once()
        mock_clear_recovery.assert_not_called()

    def test_authoritative_state_persistence_site_3_recovery_not_preserved(
        self, capsys
    ):
        """Site 3 (L2547-L2554): state save AND recovery save both failed.
        Output must be exact byte-identical with reason mentioning both
        ``.quickscale/state.yml`` and ``could not preserve rerunnable
        recovery state``.
        """
        ctx = Mock()
        ctx.output_path = Path("/tmp/proj")
        ctx.qs_config = Mock()
        ctx.qs_config.project.slug = "myapp"
        ctx.qs_config.project.package = "myapp"
        ctx.qs_config.project.theme = "showcase_html"
        ctx.qs_config.modules = {}
        ctx.existing_state = None
        ctx.delta = Mock()
        ctx.delta.config_deltas = {}

        post_embed_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
            ),
            modules={},
        )

        with (
            patch(
                "quickscale_cli.commands.apply_command._save_project_state",
                return_value=False,
            ) as mock_save_state,
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=False,
            ) as mock_save_recovery,
            patch(
                "quickscale_cli.commands.apply_command._clear_apply_recovery_state",
            ) as mock_clear_recovery,
        ):
            with pytest.raises(click.Abort):
                _finalize_apply_state(
                    ctx, post_embed_state, checkpoint_tree_id="c" * 40
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "authoritative state persistence",
            "All apply steps completed, but QuickScale could not save "
            ".quickscale/state.yml and could not preserve rerunnable "
            "recovery state in .quickscale/apply-recovery.yml.",
        )
        assert lines == expected, (
            "Byte-identical output mismatch for authoritative site 3"
        )
        assert captured.err == ""
        mock_save_state.assert_called_once()
        mock_save_recovery.assert_called_once()
        mock_clear_recovery.assert_not_called()

    # ====================================================================
    # F12.1c-closeout: caller-driven parity for 11 non-authoritative branches
    # ====================================================================

    def test_non_auth_module_embedding(self, capsys):
        """Non-authoritative caller (L2757-L2760): embed failed, state save succeeded."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=False,
                    embedded_modules=["auth"],
                    failed_module="auth",
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_project_state",
                return_value=True,
            ) as mock_save,
            patch(
                "quickscale_cli.commands.apply_command._clear_apply_recovery_state",
            ) as mock_clear,
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "module embedding",
            "required module 'auth' failed to embed",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: module embedding"
        )
        assert captured.err == ""
        mock_save.assert_called_once()
        mock_clear.assert_called_once()

    def test_non_auth_post_embed_state_snapshot(self, capsys):
        """Non-authoritative caller (L2773-L2779): state snapshot raised."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                side_effect=ValueError("oops"),
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "post-embed state snapshot",
            "QuickScale could not compute the post-embed state required "
            "for safe apply recovery: oops",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: post-embed state snapshot"
        )
        assert captured.err == ""

    def test_non_auth_managed_wiring(self, capsys):
        """Non-auth (L2784-L2789) abort Path A: managed module wiring generation."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "managed module wiring generation",
            "unable to render managed settings, URL, and integration files",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: managed wiring"
        )
        assert captured.err == ""

    def test_non_auth_backups_gitignore(self, capsys):
        """Non-auth (L2798-L2803) abort Path A: backups gitignore hardening."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "backups gitignore hardening",
            "Unable to update .gitignore with the configured private "
            "backups directory.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: backups gitignore"
        )
        assert captured.err == ""

    def test_non_auth_notifications_env_sync(self, capsys):
        """Non-auth (L2806-L2811) abort Path A: notifications env example sync."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "notifications env example sync",
            "Unable to update .env.example with the configured "
            "notifications env-var names.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: notifications env sync"
        )
        assert captured.err == ""

    def test_non_auth_analytics_env_sync(self, capsys):
        """Non-auth (L2814-L2819) abort Path A: analytics env example sync."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "analytics env example sync",
            "Unable to update .env.example with the configured "
            "analytics env-var names.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: analytics env sync"
        )
        assert captured.err == ""

    def test_non_auth_billing_env_sync(self, capsys):
        """Non-auth (L2822-L2827) abort Path A: billing env example sync."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_billing_env_example",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "billing env example sync",
            "Unable to update .env.example with the configured billing env-var names.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: billing env sync"
        )
        assert captured.err == ""

    def test_non_auth_module_dependency_sync(self, capsys):
        """Non-auth (L2833-L2838) abort Path A: module dependency sync."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_billing_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "module dependency sync",
            "Unable to reconcile embedded-module Poetry dependency "
            "entries in pyproject.toml.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: dep sync"
        )
        assert captured.err == ""

    def test_non_auth_post_gen_steps(self, capsys):
        """Non-auth (L2851-L2856) abort Path A: post-gen dependency / migration setup."""
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

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_billing_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "post-generation dependency and migration setup",
            "Poetry lock refresh or dependency installation failed after "
            "module dependency sync.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: post-gen steps"
        )
        assert captured.err == ""

    def test_non_auth_docker_startup(self, capsys):
        """Non-auth (L2872-L2877) abort Path A: docker startup failed."""
        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_billing_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._start_docker",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "docker startup",
            "Docker auto-start failed. Run 'quickscale logs' to "
            "inspect the failing service.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: docker startup"
        )
        assert captured.err == ""

    def test_non_auth_database_migrations(self, capsys):
        """Non-auth (L2884-L2889) abort Path A: database migrations inside Docker."""
        ctx = Mock()
        ctx.existing_state = None
        ctx.output_path = Path("/tmp/proj")
        ctx.manifests = {}
        ctx.delta = Mock()
        ctx.delta.modules_to_add = ["auth"]
        ctx.delta.has_mutable_config_changes = False
        ctx.qs_config = Mock()
        ctx.qs_config.modules = {"auth": Mock(options={})}
        ctx.qs_config.docker.start = True
        ctx.qs_config.docker.build = True

        with (
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                return_value=EmbedModulesResult(
                    success=True,
                    embedded_modules=["auth"],
                    failed_module=None,
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._build_project_state_snapshot",
                return_value=QuickScaleState(
                    version="1",
                    project=ProjectState(
                        slug="myapp",
                        package="myapp",
                        theme="showcase_html",
                    ),
                ),
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_git_index_snapshot",
                return_value=Mock(tree_id="a" * 40),
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._ensure_backups_gitignore_rules",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_notifications_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_analytics_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_billing_env_example",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._start_docker",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_migrations_in_docker",
                return_value=False,
            ),
            patch(
                "quickscale_cli.commands.apply_command._save_apply_recovery_state",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._capture_managed_file_hashes_after_apply",
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            ),
        ):
            with pytest.raises(click.Abort):
                _execute_apply_steps_locked(
                    ctx,
                    force=False,
                    no_docker=False,
                    no_modules=False,
                    verbose_docker=False,
                )

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        expected = _expected_failure_summary_lines(
            "database migrations",
            "Migrations failed inside Docker backend container. "
            "Run 'quickscale logs backend' for details.",
        )
        assert lines == expected, (
            "Byte-identical mismatch for non-auth caller: database migrations"
        )
        assert captured.err == ""


# ============================================================================
# F12.2: _populate_consolidated_tracking_from_legacy
# ============================================================================


class TestPopulateConsolidatedTrackingFromLegacy:
    """Tests for _populate_consolidated_tracking_from_legacy (F12.2 fail-closed)."""

    def test_missing_config_is_no_op(self, tmp_path):
        """When config.yml does not exist, the function is a no-op.

        ``load_config`` returns an empty default config for missing files,
        so no error is raised and module tracking fields are left untouched.
        """
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )

        # Should not raise despite config.yml being absent
        _populate_consolidated_tracking_from_legacy(tmp_path, state)

        # auth module should still be present with unchanged fields
        assert "auth" in state.modules
        assert state.modules["auth"].version == "0.62.0"

    def test_empty_config_is_no_op(self, tmp_path):
        """When config.yml exists but is empty/trivial, the loop is a no-op."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".quickscale" / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\nmodules: {}\n"
        )

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )

        _populate_consolidated_tracking_from_legacy(tmp_path, state)
        assert "auth" in state.modules

    def test_malformed_config_raises_config_error(self, tmp_path):
        """F12.2: malformed config.yml must raise ConfigError (fail-closed)."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".quickscale" / "config.yml").write_text(
            "invalid: [unclosed bracket\n"
        )

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={},
        )

        with pytest.raises(ConfigError):
            _populate_consolidated_tracking_from_legacy(tmp_path, state)

    def test_populates_tracking_from_legacy(self, tmp_path):
        """Consolidated tracking fields are populated from a valid legacy config."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".quickscale" / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            "    prefix: modules/auth\n"
            "    branch: splits/auth-module\n"
            "    installed_version: v0.62.0\n"
            "    installed_at: '2026-06-20'\n"
        )

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    prefix=None,
                    branch=None,
                    installed_at=None,
                ),
            },
        )

        _populate_consolidated_tracking_from_legacy(tmp_path, state)

        auth = state.modules["auth"]
        assert auth.prefix == "modules/auth"
        assert auth.branch == "splits/auth-module"
        assert auth.installed_at == "2026-06-20"

    def test_existing_tracking_not_overwritten(self, tmp_path):
        """Modules already carrying consolidated tracking are left untouched."""
        (tmp_path / ".quickscale").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".quickscale" / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            "    prefix: modules/auth\n"
            "    branch: splits/auth-module\n"
            "    installed_version: v0.62.0\n"
            "    installed_at: '2026-06-20'\n"
        )

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    prefix="modules/auth",
                    branch="splits/auth-module",
                    installed_at="2026-06-19",
                ),
            },
        )

        # installed_at should NOT be overwritten (already populated)
        _populate_consolidated_tracking_from_legacy(tmp_path, state)
        assert state.modules["auth"].installed_at == "2026-06-19"
