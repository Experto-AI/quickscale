"""Extended tests for status_command.py - covering helper functions and edge cases."""

import os
from unittest.mock import Mock, patch

import yaml
from click.testing import CliRunner

import pytest

from quickscale_cli.commands.status_command import (
    _build_json_output,
    _detect_project_context,
    _display_docker_status,
    _display_drift_warnings,
    _display_modules,
    _display_pending_changes,
    _display_project_info,
    _display_text_status,
    _format_datetime,
    _get_docker_status,
    _load_config,
    status,
)


# ============================================================================
# _get_docker_status
# ============================================================================


class TestGetDockerStatus:
    """Tests for _get_docker_status"""

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_running(self, mock_run):
        """Test Docker status when containers are running"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="myapp-web-1: Up 5 minutes\nmyapp-db-1: Up 5 minutes",
        )
        result = _get_docker_status()
        assert result is not None
        assert "myapp-web-1" in result
        assert "Up 5 minutes" in result["myapp-web-1"]

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_no_containers(self, mock_run):
        """Test Docker status with no running containers"""
        mock_run.return_value = Mock(returncode=0, stdout="")
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_not_available(self, mock_run):
        """Test when Docker is not available"""
        mock_run.side_effect = FileNotFoundError()
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_command_fails(self, mock_run):
        """Test when docker compose fails"""
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = _get_docker_status()
        assert result is None

    @patch("quickscale_cli.commands.status_command.subprocess.run")
    def test_docker_lines_without_separator(self, mock_run):
        """Test docker output without proper separator"""
        mock_run.return_value = Mock(returncode=0, stdout="no separator here")
        result = _get_docker_status()
        assert result is None


# ============================================================================
# _format_datetime
# ============================================================================


class TestFormatDatetime:
    """Tests for _format_datetime"""

    def test_valid_iso_datetime(self):
        """Format valid ISO datetime"""
        result = _format_datetime("2025-12-01T10:30:00")
        assert "2025-12-01" in result
        assert "10:30" in result

    def test_with_timezone(self):
        """Format datetime with timezone"""
        result = _format_datetime("2025-12-01T10:30:00Z")
        assert "2025-12-01" in result

    def test_invalid_datetime(self):
        """Return raw string for invalid datetime"""
        result = _format_datetime("not-a-date")
        assert result == "not-a-date"

    def test_none_value(self):
        """AttributeError raised for None since only ValueError/TypeError caught"""
        with pytest.raises(AttributeError):
            _format_datetime(None)


# ============================================================================
# _detect_project_context
# ============================================================================


class TestDetectProjectContext:
    """Tests for _detect_project_context"""

    def test_config_and_state_present(self, tmp_path, monkeypatch):
        """Detect project with both config and state"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "quickscale.yml").touch()
        (tmp_path / ".quickscale").mkdir()
        (tmp_path / ".quickscale" / "state.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is not None
        assert state_path is not None

    def test_only_config(self, tmp_path, monkeypatch):
        """Detect project with only config"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "quickscale.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is not None
        assert state_path is None

    def test_only_state(self, tmp_path, monkeypatch):
        """Detect project with only state"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()
        (tmp_path / ".quickscale" / "state.yml").touch()

        project_path, config_path, state_path = _detect_project_context()
        assert project_path == tmp_path
        assert config_path is None
        assert state_path is not None

    def test_not_in_project(self, tmp_path, monkeypatch):
        """Not in a QuickScale project"""
        monkeypatch.chdir(tmp_path)

        project_path, config_path, state_path = _detect_project_context()
        assert project_path is None


# ============================================================================
# _load_config
# ============================================================================


class TestLoadConfig:
    """Tests for _load_config"""

    def test_valid_config(self, tmp_path):
        """Load valid config"""
        config = tmp_path / "quickscale.yml"
        config.write_text(
            'version: "1"\nproject:\n  name: myapp\n  theme: showcase_html\n'
            "docker:\n  start: false\n"
        )
        result = _load_config(config)
        assert result is not None
        assert result.project.name == "myapp"

    def test_invalid_config(self, tmp_path):
        """Return None for invalid config"""
        config = tmp_path / "quickscale.yml"
        config.write_text("invalid yaml: [")
        result = _load_config(config)
        assert result is None


# ============================================================================
# _display_ functions
# ============================================================================


class TestDisplayFunctions:
    """Tests for display helper functions"""

    def test_display_project_info(self):
        """Display project information"""
        state = Mock()
        state.project.name = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01T00:00:00"
        state.project.last_applied = "2025-01-01T12:00:00"
        _display_project_info(state)

    def test_display_modules_empty(self):
        """Display modules when none installed"""
        state = Mock()
        state.modules = {}
        _display_modules(state)

    def test_display_modules_with_data(self):
        """Display modules with version and date"""
        state = Mock()
        module = Mock()
        module.version = "1.0.0"
        module.embedded_at = "2025-01-01T00:00:00"
        state.modules = {"auth": module}
        _display_modules(state)

    def test_display_modules_no_version(self):
        """Display modules without version"""
        state = Mock()
        module = Mock()
        module.version = None
        module.embedded_at = None
        state.modules = {"auth": module}
        _display_modules(state)

    def test_display_pending_changes_no_config(self):
        """Display pending changes when no config"""
        _display_pending_changes(None, None)

    def test_display_pending_changes_with_changes(self):
        """Display pending changes when changes exist"""
        config = Mock()
        config.version = "1"
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock(options={})}
        config.docker.start = False
        config.docker.build = False

        state = Mock()
        state.version = "1"
        state.project.name = "myapp"
        state.project.theme = "showcase_html"
        state.modules = {}

        with patch(
            "quickscale_cli.commands.status_command.compute_delta"
        ) as mock_delta:
            delta = Mock()
            delta.has_changes = True
            mock_delta.return_value = delta
            with patch(
                "quickscale_cli.commands.status_command.format_delta",
                return_value="+ auth",
            ):
                _display_pending_changes(config, state)

    def test_display_pending_changes_no_changes(self):
        """Display message when no changes"""
        config = Mock()
        state = Mock()

        with patch(
            "quickscale_cli.commands.status_command.compute_delta"
        ) as mock_delta:
            delta = Mock()
            delta.has_changes = False
            mock_delta.return_value = delta
            _display_pending_changes(config, state)

    @patch("quickscale_cli.commands.status_command._get_docker_status")
    def test_display_docker_status_running(self, mock_status):
        """Display Docker status for running containers"""
        mock_status.return_value = {
            "web": "Up 5 minutes",
            "db": "Exited (0)",
            "redis": "starting",
        }
        _display_docker_status()

    @patch("quickscale_cli.commands.status_command._get_docker_status")
    def test_display_docker_status_none(self, mock_status):
        """Display Docker status when not available"""
        mock_status.return_value = None
        _display_docker_status()


# ============================================================================
# _display_drift_warnings
# ============================================================================


class TestDisplayDriftWarnings:
    """Tests for _display_drift_warnings"""

    def test_orphaned_modules(self):
        """Show orphaned module warnings"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": ["stale_module"],
            "missing_modules": [],
        }
        _display_drift_warnings(sm)

    def test_missing_modules(self):
        """Show missing module warnings"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": ["gone_module"],
        }
        _display_drift_warnings(sm)

    def test_no_drift(self):
        """No warnings when no drift"""
        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": [],
        }
        _display_drift_warnings(sm)


# ============================================================================
# _build_json_output
# ============================================================================


class TestBuildJsonOutput:
    """Tests for _build_json_output"""

    def test_with_state_and_config(self, tmp_path):
        """Build JSON with both state and config"""
        state = Mock()
        state.version = "1"
        state.project.name = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01"
        state.project.last_applied = "2025-01-01"
        module = Mock()
        module.version = "1.0"
        module.commit_sha = "abc"
        module.embedded_at = "2025-01-01"
        state.modules = {"auth": module}

        config = Mock()
        config.version = "1"
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {"auth": Mock()}
        config.docker.start = False
        config.docker.build = False

        delta = Mock()
        delta.has_changes = False
        delta.modules_to_add = []
        delta.modules_to_remove = []
        delta.modules_unchanged = ["auth"]
        delta.theme_changed = False

        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            with patch(
                "quickscale_cli.commands.status_command._load_module_manifests",
                return_value={},
            ):
                with patch(
                    "quickscale_cli.commands.status_command.compute_delta",
                    return_value=delta,
                ):
                    result = _build_json_output(
                        tmp_path, tmp_path / "quickscale.yml", state, config
                    )

        assert result["has_state"] is True
        assert "state" in result
        assert "config" in result
        assert "pending_changes" in result

    def test_without_state(self, tmp_path):
        """Build JSON without state"""
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            result = _build_json_output(tmp_path, None, None, None)

        assert result["has_state"] is False
        assert result["has_config"] is False

    def test_with_docker_status(self, tmp_path):
        """Build JSON with Docker status"""
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value={"web": "Up"},
        ):
            result = _build_json_output(tmp_path, None, None, None)
        assert "docker" in result


# ============================================================================
# _display_text_status
# ============================================================================


class TestDisplayTextStatus:
    """Tests for _display_text_status"""

    def test_no_state_no_config(self, tmp_path):
        """Abort when no state or config"""
        import click as click_mod

        sm = Mock()
        with pytest.raises(click_mod.Abort):
            _display_text_status(tmp_path, None, None, None, None, sm)

    def test_with_state_only(self, tmp_path):
        """Display with state but no config"""
        state = Mock()
        state.project.name = "myapp"
        state.project.theme = "showcase_html"
        state.project.created_at = "2025-01-01"
        state.project.last_applied = "2025-01-01"
        state.modules = {}

        sm = Mock()
        sm.verify_filesystem.return_value = {
            "orphaned_modules": [],
            "missing_modules": [],
        }

        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            _display_text_status(tmp_path, state, None, None, None, sm)

    def test_with_config_no_state(self, tmp_path):
        """Display with config but no state"""
        config = Mock()
        config.version = "1"
        config.project.name = "myapp"
        config.project.theme = "showcase_html"
        config.modules = {}
        config.docker.start = False
        config.docker.build = False

        sm = Mock()
        with patch(
            "quickscale_cli.commands.status_command._get_docker_status",
            return_value=None,
        ):
            with patch(
                "quickscale_cli.commands.status_command.compute_delta"
            ) as mock_delta:
                delta = Mock()
                delta.has_changes = False
                mock_delta.return_value = delta
                _display_text_status(tmp_path, None, config, None, None, sm)


# ============================================================================
# status command integration
# ============================================================================


class TestStatusCommandExtended:
    """Extended integration tests for status command"""

    def test_status_json_not_in_project(self):
        """Test JSON status outside project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(status, ["--json"])
            assert result.exit_code != 0

    def test_status_text_with_state_and_config(self):
        """Full text status with state and config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale")
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "name": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": "1.0",
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )
            with open("quickscale.yml", "w") as f:
                f.write(
                    'version: "1"\nproject:\n  name: testapp\n  theme: showcase_html\nmodules:\n  auth:\ndocker:\n  start: false\n'
                )

            result = runner.invoke(status)
            assert result.exit_code == 0
            assert "testapp" in result.output
