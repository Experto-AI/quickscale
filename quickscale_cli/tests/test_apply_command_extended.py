"""Extended tests for apply_command.py - covering helper functions and edge cases."""

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest

from quickscale_cli.commands.apply_command import (
    _run_command,
    _generate_project,
    _init_git,
    _git_commit,
    _embed_module,
    _run_poetry_install,
    _run_migrations,
    _start_docker,
    _load_module_manifests,
    _apply_mutable_config,
    _check_immutable_config_changes,
    _update_module_config_in_state,
    _load_and_validate_config,
    _determine_output_path,
    _display_config_summary,
    _handle_delta_and_existing_state,
    _check_output_directory,
    _generate_with_existing_config,
    _init_git_with_config,
    _embed_modules_step,
    _run_post_generation_steps,
    _save_project_state,
    _display_next_steps,
)


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
        mock_config.project.name = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is True

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_showcase_htmx_not_implemented(self, mock_gen_cls):
        """Test showcase_htmx theme is rejected"""
        mock_config = Mock()
        mock_config.project.name = "myapp"
        mock_config.project.theme = "showcase_htmx"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_file_exists_error(self, mock_gen_cls):
        """Test FileExistsError handling"""
        mock_gen_cls.return_value.generate.side_effect = FileExistsError()
        mock_config = Mock()
        mock_config.project.name = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_value_error(self, mock_gen_cls):
        """Test ValueError handling"""
        mock_gen_cls.return_value.generate.side_effect = ValueError("bad config")
        mock_config = Mock()
        mock_config.project.name = "myapp"
        mock_config.project.theme = "showcase_html"
        result = _generate_project(mock_config, Path("/tmp/myapp"))
        assert result is False

    @patch("quickscale_cli.commands.apply_command.ProjectGenerator")
    def test_generic_error(self, mock_gen_cls):
        """Test generic exception handling"""
        mock_gen_cls.return_value.generate.side_effect = RuntimeError("oops")
        mock_config = Mock()
        mock_config.project.name = "myapp"
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
    def test_migrations(self, mock_run):
        """Test run migrations wrapper"""
        mock_run.return_value = (True, "")
        assert _run_migrations(Path("/tmp/proj")) is True


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
            'version: "1"\nproject:\n  name: myapp\n  theme: showcase_html\ndocker:\n  start: false\n'
        )
        result = _load_and_validate_config(config)
        assert result.project.name == "myapp"

    def test_read_error(self, tmp_path):
        """Test generic read error"""
        config = tmp_path / "quickscale.yml"
        config.write_text("valid content")
        with patch.object(Path, "read_text", side_effect=OSError("disk error")):
            with pytest.raises(click.Abort):
                _load_and_validate_config(config)


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
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(), "blog": Mock()}
        config.docker.start = True
        config.docker.build = True
        _display_config_summary(config)

    def test_without_modules(self):
        """Test config summary display without modules"""
        config = Mock()
        config.project.name = "myapp"
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

    def test_immutable_changes_abort(self):
        """Test abort on immutable changes"""
        delta = Mock()
        delta.has_changes = True
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
# _embed_modules_step
# ============================================================================


class TestEmbedModulesStep:
    """Tests for _embed_modules_step"""

    def test_no_modules(self):
        """Test with no modules flag"""
        result = _embed_modules_step(Path("/tmp"), ["auth"], True, None)
        assert result == []

    def test_empty_modules_list(self):
        """Test with empty modules list"""
        result = _embed_modules_step(Path("/tmp"), [], False, None)
        assert result == []

    def test_empty_modules_existing_state(self):
        """Test empty modules with existing state"""
        result = _embed_modules_step(Path("/tmp"), [], False, Mock())
        assert result == []

    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_successful_embed(self, mock_embed, mock_commit):
        """Test successful module embedding"""
        mock_embed.return_value = True
        mock_commit.return_value = True
        result = _embed_modules_step(Path("/tmp"), ["auth"], False, None)
        assert result == ["auth"]

    @patch("quickscale_cli.commands.apply_command.is_working_directory_clean")
    @patch("quickscale_cli.commands.apply_command._git_commit")
    @patch("quickscale_cli.commands.apply_command._embed_module")
    def test_failed_embed(self, mock_embed, mock_commit, mock_clean):
        """Test failed module embedding continues"""
        mock_embed.return_value = False
        mock_clean.return_value = False
        mock_commit.return_value = True
        result = _embed_modules_step(Path("/tmp"), ["auth"], False, None)
        assert result == []


# ============================================================================
# _run_post_generation_steps
# ============================================================================


class TestRunPostGenerationSteps:
    """Tests for _run_post_generation_steps"""

    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_all_succeed(self, mock_poetry, mock_migrate):
        """Test when all steps succeed"""
        mock_poetry.return_value = True
        mock_migrate.return_value = True
        _run_post_generation_steps(Path("/tmp"))

    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_poetry_fails(self, mock_poetry, mock_migrate):
        """Test when poetry install fails"""
        mock_poetry.return_value = False
        mock_migrate.return_value = True
        _run_post_generation_steps(Path("/tmp"))
        # Should not raise

    @patch("quickscale_cli.commands.apply_command._run_migrations")
    @patch("quickscale_cli.commands.apply_command._run_poetry_install")
    def test_migrations_fail(self, mock_poetry, mock_migrate):
        """Test when migrations fail"""
        mock_poetry.return_value = True
        mock_migrate.return_value = False
        _run_post_generation_steps(Path("/tmp"))
        # Should not raise


# ============================================================================
# _save_project_state
# ============================================================================


class TestSaveProjectState:
    """Tests for _save_project_state"""

    def test_new_project_state(self, tmp_path):
        """Test saving state for new project"""
        config = Mock()
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={"key": "val"})}
        delta = Mock()
        delta.config_deltas = {}

        _save_project_state(tmp_path, config, None, ["auth"], delta)
        assert (tmp_path / ".quickscale" / "state.yml").exists()

    def test_existing_project_state(self, tmp_path):
        """Test saving state for existing project"""
        # Pre-create state dir
        (tmp_path / ".quickscale").mkdir()

        existing_state = Mock()
        existing_state.project.last_applied = "old"
        existing_state.modules = {}

        config = Mock()
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"blog": Mock(options={})}
        delta = Mock()
        delta.config_deltas = {}

        _save_project_state(tmp_path, config, existing_state, ["blog"], delta)

    def test_save_state_error(self, tmp_path):
        """Test state save error handling"""
        config = Mock()
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        delta = Mock()
        delta.config_deltas = {}

        with patch("quickscale_cli.commands.apply_command.StateManager") as mock_sm:
            mock_sm.return_value.save.side_effect = OSError("write error")
            _save_project_state(tmp_path, config, None, [], delta)
            # Should not raise


# ============================================================================
# _display_next_steps
# ============================================================================


class TestDisplayNextSteps:
    """Tests for _display_next_steps"""

    def test_with_docker(self, monkeypatch, tmp_path):
        """Test next steps display with Docker"""
        monkeypatch.chdir(tmp_path)
        config = Mock()
        config.project.name = "myapp"
        config.docker.start = True
        _display_next_steps(tmp_path / "myapp", config, False)

    def test_without_docker(self, monkeypatch, tmp_path):
        """Test next steps display without Docker"""
        config = Mock()
        config.project.name = "myapp"
        config.docker.start = False
        _display_next_steps(Path.cwd(), config, True)


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
        mock_config.project.name = "myapp"

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
        mock_config.project.name = "myapp"

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
        mock_config.project.name = "myapp"

        def fake_generate(config, path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "manage.py").touch()
            return True

        mock_gen.side_effect = fake_generate

        _generate_with_existing_config(mock_config, output, config_file, True)
        assert not (output / "old_file.txt").exists()
        assert (output / "manage.py").exists()
