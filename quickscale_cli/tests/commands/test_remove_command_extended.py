"""Extended tests for remove_command.py - covering helper functions and edge cases."""

from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from quickscale_cli.commands.remove_command import (
    _check_module_exists,
    _log_step_result,
    _perform_removal_steps,
    _remove_module_directory,
    _show_module_not_found_error,
    _show_removal_warning,
    _show_success_message,
    _update_quickscale_yml,
    _update_settings_py,
    _update_state_for_removal,
    _update_urls_py,
    remove,
)
from quickscale_cli.schema.state_schema import StateManager


# ============================================================================
# _update_quickscale_yml
# ============================================================================


class TestUpdateQuickscaleYml:
    """Tests for _update_quickscale_yml"""

    def test_no_config_file(self, tmp_path):
        """Return True when no config file exists"""
        assert _update_quickscale_yml(tmp_path, "auth") is True

    def test_remove_module_from_config(self, tmp_path):
        """Successfully remove module from config"""
        config = {"modules": {"auth": {"options": {}}, "blog": {"options": {}}}}
        (tmp_path / "quickscale.yml").write_text(yaml.dump(config))

        result = _update_quickscale_yml(tmp_path, "auth")
        assert result is True

        updated = yaml.safe_load((tmp_path / "quickscale.yml").read_text())
        assert "auth" not in updated["modules"]
        assert "blog" in updated["modules"]

    def test_module_not_in_config(self, tmp_path):
        """No error when module not in config"""
        config = {"modules": {"blog": {}}}
        (tmp_path / "quickscale.yml").write_text(yaml.dump(config))

        result = _update_quickscale_yml(tmp_path, "auth")
        assert result is True

    def test_invalid_yaml(self, tmp_path):
        """Return False on YAML parse error"""
        (tmp_path / "quickscale.yml").write_text("invalid: [")
        result = _update_quickscale_yml(tmp_path, "auth")
        assert result is False

    def test_empty_config(self, tmp_path):
        """Handle empty config file"""
        (tmp_path / "quickscale.yml").write_text("")
        result = _update_quickscale_yml(tmp_path, "auth")
        assert result is True

    def test_no_modules_key(self, tmp_path):
        """Handle config without modules key"""
        (tmp_path / "quickscale.yml").write_text(
            yaml.dump({"project": {"name": "test"}})
        )
        result = _update_quickscale_yml(tmp_path, "auth")
        assert result is True


# ============================================================================
# _remove_module_directory
# ============================================================================


class TestRemoveModuleDirectory:
    """Tests for _remove_module_directory"""

    def test_directory_not_exists(self, tmp_path):
        """Return success when directory already gone"""
        success, msg = _remove_module_directory(tmp_path, "auth")
        assert success is True
        assert "not found" in msg

    def test_directory_removed(self, tmp_path):
        """Successfully remove module directory"""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "models.py").touch()

        success, msg = _remove_module_directory(tmp_path, "auth")
        assert success is True
        assert not module_dir.exists()

    def test_permission_error(self, tmp_path):
        """Handle permission error during removal"""
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)

        with patch("shutil.rmtree", side_effect=PermissionError("denied")):
            success, msg = _remove_module_directory(tmp_path, "auth")
            assert success is False
            assert "Failed" in msg


# ============================================================================
# _update_settings_py
# ============================================================================


class TestUpdateSettingsPy:
    """Tests for _update_settings_py"""

    def test_settings_not_found(self, tmp_path):
        """Return success when settings.py doesn't exist"""
        project = tmp_path / "myproject"
        project.mkdir()
        success, msg = _update_settings_py(project, "auth")
        assert success is True
        assert "not found" in msg

    def test_remove_module_references(self, tmp_path):
        """Remove module references from settings"""
        project = tmp_path / "myproject"
        settings_dir = project / "myproject" / "settings"
        settings_dir.mkdir(parents=True)
        settings = settings_dir / "base.py"
        settings.write_text(
            "INSTALLED_APPS = [\n"
            "    'django.contrib.admin',\n"
            "    'quickscale_modules_auth',\n"
            "\n"
            "    'other_app',\n"
            "]\n"
        )

        success, msg = _update_settings_py(project, "auth")
        assert success is True
        assert "Removed" in msg
        content = settings.read_text()
        assert "quickscale_modules_auth" not in content

    def test_no_module_references(self, tmp_path):
        """No changes when module not referenced"""
        project = tmp_path / "myproject"
        settings_dir = project / "myproject" / "settings"
        settings_dir.mkdir(parents=True)
        settings = settings_dir / "base.py"
        settings.write_text("INSTALLED_APPS = ['django.contrib.admin']\n")

        success, msg = _update_settings_py(project, "auth")
        assert success is True
        assert "settings.py" in msg

    def test_settings_write_error(self, tmp_path):
        """Handle write error"""
        project = tmp_path / "myproject"
        settings_dir = project / "myproject" / "settings"
        settings_dir.mkdir(parents=True)
        settings = settings_dir / "base.py"
        settings.write_text("quickscale_modules_auth\n")

        with patch.object(Path, "write_text", side_effect=OSError("write error")):
            success, msg = _update_settings_py(project, "auth")
            assert success is False
            assert "Failed" in msg


# ============================================================================
# _update_urls_py
# ============================================================================


class TestUpdateUrlsPy:
    """Tests for _update_urls_py"""

    def test_urls_not_found(self, tmp_path):
        """Return success when urls.py doesn't exist"""
        project = tmp_path / "myproject"
        project.mkdir()
        success, msg = _update_urls_py(project, "auth")
        assert success is True
        assert "not found" in msg

    def test_remove_module_urls(self, tmp_path):
        """Remove module URLs"""
        project = tmp_path / "myproject"
        (project / "myproject").mkdir(parents=True)
        urls = project / "myproject" / "urls.py"
        urls.write_text(
            "urlpatterns = [\n"
            '    path("admin/", admin.site.urls),\n'
            '    path("auth/", include("quickscale_modules_auth.urls")),\n'
            "]\n"
        )

        success, msg = _update_urls_py(project, "auth")
        assert success is True
        assert "Removed" in msg
        content = urls.read_text()
        assert "quickscale_modules_auth" not in content

    def test_no_module_urls(self, tmp_path):
        """No changes when module not in urls"""
        project = tmp_path / "myproject"
        (project / "myproject").mkdir(parents=True)
        urls = project / "myproject" / "urls.py"
        urls.write_text("urlpatterns = []\n")

        success, msg = _update_urls_py(project, "auth")
        assert success is True
        assert "urls.py" in msg

    def test_urls_write_error(self, tmp_path):
        """Handle write error"""
        project = tmp_path / "myproject"
        (project / "myproject").mkdir(parents=True)
        urls = project / "myproject" / "urls.py"
        urls.write_text("quickscale_modules_auth\n")

        with patch.object(Path, "write_text", side_effect=OSError("write error")):
            success, msg = _update_urls_py(project, "auth")
            assert success is False
            assert "Failed" in msg


# ============================================================================
# _check_module_exists
# ============================================================================


class TestCheckModuleExists:
    """Tests for _check_module_exists"""

    def test_module_in_state_and_filesystem(self, tmp_path):
        """Module exists in both state and filesystem"""
        (tmp_path / "modules" / "auth").mkdir(parents=True)
        (tmp_path / ".quickscale").mkdir()
        state_content = {
            "version": "1",
            "project": {
                "name": "test",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {"auth": {"name": "auth", "embedded_at": "2025-01-01"}},
        }
        (tmp_path / ".quickscale" / "state.yml").write_text(yaml.dump(state_content))

        sm = StateManager(tmp_path)
        in_state, in_fs, state = _check_module_exists(tmp_path, "auth", sm)
        assert in_state is True
        assert in_fs is True

    def test_module_not_anywhere(self, tmp_path):
        """Module doesn't exist"""
        sm = StateManager(tmp_path)
        in_state, in_fs, state = _check_module_exists(tmp_path, "auth", sm)
        assert in_state is False
        assert in_fs is False


# ============================================================================
# _show_module_not_found_error
# ============================================================================


class TestShowModuleNotFoundError:
    """Tests for _show_module_not_found_error"""

    def test_with_installed_modules(self):
        """Show error with list of installed modules"""
        state = Mock()
        state.modules = {"blog": Mock(), "crm": Mock()}
        _show_module_not_found_error("auth", state)

    def test_with_no_modules(self):
        """Show error with no installed modules"""
        state = Mock()
        state.modules = {}
        _show_module_not_found_error("auth", state)

    def test_with_none_state(self):
        """Show error with None state"""
        _show_module_not_found_error("auth", None)


# ============================================================================
# _show_removal_warning / _show_success_message
# ============================================================================


class TestShowMessages:
    """Tests for display message functions"""

    def test_show_removal_warning_with_data(self):
        """Show removal warning without keep_data"""
        _show_removal_warning("auth", keep_data=False)

    def test_show_removal_warning_keep_data(self):
        """Show removal warning with keep_data"""
        _show_removal_warning("auth", keep_data=True)

    def test_show_success_message(self):
        """Show success message"""
        _show_success_message("auth", keep_data=False)

    def test_show_success_message_keep_data(self):
        """Show success message with keep_data"""
        _show_success_message("auth", keep_data=True)


# ============================================================================
# _log_step_result
# ============================================================================


class TestLogStepResult:
    """Tests for _log_step_result"""

    def test_success_error_mode(self):
        """Test success in error mode"""
        _log_step_result(True, "Done", is_error=True)

    def test_failure_error_mode(self):
        """Test failure in error mode"""
        _log_step_result(False, "Failed", is_error=True)

    def test_success_warning_mode(self):
        """Test success in warning mode"""
        _log_step_result(True, "Done", is_error=False)

    def test_failure_warning_mode(self):
        """Test failure in warning mode"""
        _log_step_result(False, "Warning", is_error=False)


# ============================================================================
# _update_state_for_removal
# ============================================================================


class TestUpdateStateForRemoval:
    """Tests for _update_state_for_removal"""

    def test_remove_module_from_state(self, tmp_path):
        """Successfully remove module from state"""
        (tmp_path / ".quickscale").mkdir()
        state_data = {
            "version": "1",
            "project": {
                "name": "test",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {"auth": {"name": "auth", "embedded_at": "2025-01-01"}},
        }
        (tmp_path / ".quickscale" / "state.yml").write_text(yaml.dump(state_data))

        sm = StateManager(tmp_path)
        state = sm.load()
        _update_state_for_removal(state, "auth", sm)

        updated = sm.load()
        assert "auth" not in (updated.modules if updated else {})

    def test_none_state(self, tmp_path):
        """Handle None state"""
        sm = StateManager(tmp_path)
        _update_state_for_removal(None, "auth", sm)

    def test_module_not_in_state(self, tmp_path):
        """Handle module not in state"""
        (tmp_path / ".quickscale").mkdir()
        state_data = {
            "version": "1",
            "project": {
                "name": "test",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {},
        }
        (tmp_path / ".quickscale" / "state.yml").write_text(yaml.dump(state_data))

        sm = StateManager(tmp_path)
        state = sm.load()
        _update_state_for_removal(state, "auth", sm)

    def test_save_error(self, tmp_path):
        """Handle save error gracefully"""
        state = Mock()
        state.modules = {"auth": Mock()}
        sm = Mock()
        sm.save.side_effect = OSError("write error")

        _update_state_for_removal(state, "auth", sm)
        # Should not raise


# ============================================================================
# _perform_removal_steps
# ============================================================================


class TestPerformRemovalSteps:
    """Tests for _perform_removal_steps"""

    def test_full_removal(self, tmp_path):
        """Test complete module removal"""
        # Create project structure
        project = tmp_path / "myproject"
        project.mkdir()
        module_dir = project / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "models.py").touch()

        # State
        (project / ".quickscale").mkdir()
        state_data = {
            "version": "1",
            "project": {
                "name": "myproject",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {"auth": {"name": "auth", "embedded_at": "2025-01-01"}},
        }
        (project / ".quickscale" / "state.yml").write_text(yaml.dump(state_data))

        # Settings
        settings_dir = project / "myproject" / "settings"
        settings_dir.mkdir(parents=True)
        (settings_dir / "base.py").write_text("quickscale_modules_auth\n")

        # URLs
        (project / "myproject" / "urls.py").write_text("quickscale_modules_auth\n")

        sm = StateManager(project)
        state = sm.load()
        _perform_removal_steps(project, "auth", state, sm)

        assert not module_dir.exists()


# ============================================================================
# remove command integration
# ============================================================================


class TestRemoveCommandIntegration:
    """Integration tests for remove command"""

    def test_remove_with_keep_data(self, tmp_path):
        """Test remove with --keep-data flag"""
        from click.testing import CliRunner

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "modules" / "auth").mkdir(parents=True)
        (project / ".quickscale").mkdir()
        state_data = {
            "version": "1",
            "project": {
                "name": "myproject",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {"auth": {"name": "auth", "embedded_at": "2025-01-01"}},
        }
        (project / ".quickscale" / "state.yml").write_text(yaml.dump(state_data))

        runner = CliRunner()
        import os

        os.chdir(project)
        result = runner.invoke(
            remove, ["auth", "--force", "--keep-data"], catch_exceptions=False
        )
        assert "removed successfully" in result.output

    def test_remove_cancelled(self, tmp_path):
        """Test remove cancelled by user"""
        from click.testing import CliRunner

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "modules" / "auth").mkdir(parents=True)
        (project / ".quickscale").mkdir()
        state_data = {
            "version": "1",
            "project": {
                "name": "myproject",
                "theme": "html",
                "created_at": "2025-01-01",
                "last_applied": "2025-01-01",
            },
            "modules": {"auth": {"name": "auth", "embedded_at": "2025-01-01"}},
        }
        (project / ".quickscale" / "state.yml").write_text(yaml.dump(state_data))

        runner = CliRunner()
        import os

        os.chdir(project)
        result = runner.invoke(remove, ["auth"], input="n\n", catch_exceptions=False)
        assert result.exit_code != 0 or "Cancelled" in result.output
