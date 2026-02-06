"""Extended tests for development_commands.py - covering error paths and missing lines."""

import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from quickscale_cli.commands.development_commands import (
    _dependencies_changed_since_last_build,
    _handle_up_error,
    _run_docker_exec_command,
    _show_port_conflict_error,
    _update_last_build_timestamp,
    _validate_project_and_docker,
    down,
    logs,
    manage,
    shell,
    up,
)


# ============================================================================
# _validate_project_and_docker
# ============================================================================


class TestValidateProjectAndDocker:
    """Tests for _validate_project_and_docker"""

    @patch("quickscale_cli.commands.development_commands.is_docker_running")
    @patch("quickscale_cli.commands.development_commands.is_in_quickscale_project")
    def test_not_in_project(self, mock_project, mock_docker):
        """Exit when not in project directory"""
        mock_project.return_value = False
        with pytest.raises(SystemExit):
            _validate_project_and_docker()

    @patch("quickscale_cli.commands.development_commands.is_docker_running")
    @patch("quickscale_cli.commands.development_commands.is_in_quickscale_project")
    def test_docker_not_running(self, mock_project, mock_docker):
        """Exit when Docker is not running"""
        mock_project.return_value = True
        mock_docker.return_value = False
        with pytest.raises(SystemExit):
            _validate_project_and_docker()


# ============================================================================
# _show_port_conflict_error
# ============================================================================


class TestShowPortConflictError:
    """Tests for _show_port_conflict_error"""

    def test_shows_error(self):
        """Show port conflict error message"""
        _show_port_conflict_error(8000)

    def test_shows_error_string_port(self):
        """Show port conflict error with string port"""
        _show_port_conflict_error("8080")


# ============================================================================
# _handle_up_error
# ============================================================================


class TestHandleUpError:
    """Tests for _handle_up_error"""

    def test_port_conflict_error(self):
        """Handle port conflict in error output"""
        error = subprocess.CalledProcessError(1, "docker-compose")
        error.stderr = "Bind for 0.0.0.0:8000 failed: port is already allocated"
        error.stdout = ""
        _handle_up_error(error)

    def test_generic_error(self):
        """Handle generic error output"""
        error = subprocess.CalledProcessError(1, "docker-compose")
        error.stderr = "Some other error"
        error.stdout = ""
        _handle_up_error(error)

    def test_error_no_output(self):
        """Handle error with no output"""
        error = subprocess.CalledProcessError(1, "docker-compose")
        error.stderr = ""
        error.stdout = ""
        _handle_up_error(error)

    def test_port_conflict_in_stdout(self):
        """Handle port conflict in stdout"""
        error = subprocess.CalledProcessError(1, "docker-compose")
        error.stderr = ""
        error.stdout = "Bind for 0.0.0.0:3000 failed: port is already allocated"
        _handle_up_error(error)


# ============================================================================
# _run_docker_exec_command
# ============================================================================


class TestRunDockerExecCommand:
    """Tests for _run_docker_exec_command"""

    @patch(
        "quickscale_cli.commands.development_commands.is_interactive",
        return_value=False,
    )
    @patch("subprocess.run")
    def test_non_interactive_capture(self, mock_run, mock_interactive):
        """Run command in non-interactive mode with capture"""
        mock_run.return_value = Mock(returncode=0, stdout="output", stderr="err")
        _run_docker_exec_command("container", ["echo", "hi"], capture=True)

    @patch(
        "quickscale_cli.commands.development_commands.is_interactive",
        return_value=False,
    )
    @patch("subprocess.run")
    def test_non_interactive_no_capture(self, mock_run, mock_interactive):
        """Run command in non-interactive mode without capture"""
        mock_run.return_value = Mock(returncode=0)
        _run_docker_exec_command("container", ["echo", "hi"], capture=False)

    @patch(
        "quickscale_cli.commands.development_commands.is_interactive", return_value=True
    )
    @patch("subprocess.run")
    def test_interactive_mode(self, mock_run, mock_interactive):
        """Run command in interactive mode"""
        mock_run.return_value = Mock(returncode=0)
        _run_docker_exec_command("container", ["bash"])


# ============================================================================
# _dependencies_changed_since_last_build
# ============================================================================


class TestDependenciesChanged:
    """Tests for _dependencies_changed_since_last_build"""

    def test_no_build_state_file(self, tmp_path, monkeypatch):
        """Return False when no build state file"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()
        assert _dependencies_changed_since_last_build() is False

    def test_no_pyproject_file(self, tmp_path, monkeypatch):
        """Return False when no pyproject.toml"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()
        import json

        build_state = tmp_path / ".quickscale" / "build_state.json"
        build_state.write_text(
            json.dumps({"pyproject_mtime": 0, "poetry_lock_mtime": 0})
        )
        assert _dependencies_changed_since_last_build() is False

    def test_dependencies_changed(self, tmp_path, monkeypatch):
        """Return True when dependencies changed"""
        monkeypatch.chdir(tmp_path)
        import json

        (tmp_path / ".quickscale").mkdir()
        (tmp_path / "pyproject.toml").write_text("old")
        (tmp_path / "poetry.lock").write_text("old")

        build_state = tmp_path / ".quickscale" / "build_state.json"
        build_state.write_text(
            json.dumps({"pyproject_mtime": 0, "poetry_lock_mtime": 0})
        )

        assert _dependencies_changed_since_last_build() is True

    def test_dependencies_not_changed(self, tmp_path, monkeypatch):
        """Return False when dependencies unchanged"""
        monkeypatch.chdir(tmp_path)
        import json

        (tmp_path / ".quickscale").mkdir()
        (tmp_path / "pyproject.toml").write_text("content")
        (tmp_path / "poetry.lock").write_text("content")

        current_mtime = (tmp_path / "pyproject.toml").stat().st_mtime
        lock_mtime = (tmp_path / "poetry.lock").stat().st_mtime

        build_state = tmp_path / ".quickscale" / "build_state.json"
        build_state.write_text(
            json.dumps(
                {
                    "pyproject_mtime": current_mtime + 1,
                    "poetry_lock_mtime": lock_mtime + 1,
                }
            )
        )

        assert _dependencies_changed_since_last_build() is False

    def test_corrupt_build_state(self, tmp_path, monkeypatch):
        """Return False when build state is corrupt"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()
        (tmp_path / "pyproject.toml").write_text("content")
        (tmp_path / "poetry.lock").write_text("content")

        build_state = tmp_path / ".quickscale" / "build_state.json"
        build_state.write_text("not json")

        assert _dependencies_changed_since_last_build() is False


# ============================================================================
# _update_last_build_timestamp
# ============================================================================


class TestUpdateLastBuildTimestamp:
    """Tests for _update_last_build_timestamp"""

    def test_creates_build_state(self, tmp_path, monkeypatch):
        """Create build state file"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("content")
        (tmp_path / "poetry.lock").write_text("content")
        (tmp_path / ".quickscale").mkdir()

        _update_last_build_timestamp()

        import json

        build_state = tmp_path / ".quickscale" / "build_state.json"
        assert build_state.exists()
        data = json.loads(build_state.read_text())
        assert "pyproject_mtime" in data
        assert "poetry_lock_mtime" in data

    def test_creates_directory(self, tmp_path, monkeypatch):
        """Create .quickscale directory if missing"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("content")
        (tmp_path / "poetry.lock").write_text("content")

        _update_last_build_timestamp()
        assert (tmp_path / ".quickscale" / "build_state.json").exists()

    def test_no_dependency_files(self, tmp_path, monkeypatch):
        """Handle missing dependency files"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".quickscale").mkdir()

        _update_last_build_timestamp()

        import json

        data = json.loads((tmp_path / ".quickscale" / "build_state.json").read_text())
        assert data["pyproject_mtime"] == 0
        assert data["poetry_lock_mtime"] == 0


# ============================================================================
# Up command - port conflict and dependency warning
# ============================================================================


class TestUpCommandExtended:
    """Extended tests for up command"""

    def test_up_port_conflict(self):
        """Test up command when port is in use"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available",
                    return_value=False,
                ):
                    result = runner.invoke(up)
                    assert result.exit_code == 1
                    assert "already in use" in result.output

    def test_up_with_dependency_warning(self):
        """Test up with stale dependencies warning"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.is_port_available",
                    return_value=True,
                ):
                    with patch(
                        "quickscale_cli.commands.development_commands._dependencies_changed_since_last_build",
                        return_value=True,
                    ):
                        with patch(
                            "quickscale_cli.commands.development_commands.get_docker_compose_command",
                            return_value=["docker-compose"],
                        ):
                            with patch(
                                "subprocess.run", return_value=Mock(returncode=0)
                            ):
                                result = runner.invoke(up)
                                assert result.exit_code == 0
                                assert "Dependencies may have changed" in result.output


# ============================================================================
# Down command - port release warning
# ============================================================================


class TestDownCommandExtended:
    """Extended tests for down command"""

    def test_down_port_not_released(self):
        """Test down when port doesn't release in time"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command",
                    return_value=["docker-compose"],
                ):
                    with patch("subprocess.run", return_value=Mock(returncode=0)):
                        with patch(
                            "quickscale_cli.commands.development_commands.wait_for_port_release",
                            return_value=False,
                        ):
                            result = runner.invoke(down)
                            assert result.exit_code == 0
                            assert "still in use" in result.output


# ============================================================================
# Shell command - non-exit-code-1 error
# ============================================================================


class TestShellCommandExtended:
    """Extended tests for shell command"""

    def test_shell_non_1_error(self):
        """Test shell when container returns non-1 error code"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name",
                    return_value="web",
                ):
                    with patch(
                        "subprocess.run",
                        side_effect=subprocess.CalledProcessError(2, "docker"),
                    ):
                        result = runner.invoke(shell)
                        assert result.exit_code == 2
                        assert "Command failed" in result.output


# ============================================================================
# Manage command - no args handled already, test other errors
# ============================================================================


class TestManageCommandExtended:
    """Extended tests for manage command"""

    def test_manage_keyboard_interrupt(self):
        """Test manage command interrupted by user"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_web_container_name",
                    return_value="web",
                ):
                    with patch(
                        "quickscale_cli.commands.development_commands._run_docker_exec_command",
                        side_effect=KeyboardInterrupt,
                    ):
                        result = runner.invoke(manage, ["migrate"])
                        assert result.exit_code == 130


# ============================================================================
# Logs/Ps commands - keyboard interrupt
# ============================================================================


class TestLogsAndPsExtended:
    """Extended tests for logs and ps commands"""

    def test_logs_keyboard_interrupt(self):
        """Test logs command interrupted"""
        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command",
                    return_value=["docker-compose"],
                ):
                    with patch("subprocess.run", side_effect=KeyboardInterrupt):
                        result = runner.invoke(logs)
                        assert result.exit_code == 0

    def test_ps_failure(self):
        """Test ps command failure"""
        from quickscale_cli.commands.development_commands import ps as ps_cmd

        runner = CliRunner()

        with patch(
            "quickscale_cli.commands.development_commands.is_in_quickscale_project",
            return_value=True,
        ):
            with patch(
                "quickscale_cli.commands.development_commands.is_docker_running",
                return_value=True,
            ):
                with patch(
                    "quickscale_cli.commands.development_commands.get_docker_compose_command",
                    return_value=["docker-compose"],
                ):
                    with patch(
                        "subprocess.run",
                        side_effect=subprocess.CalledProcessError(1, "cmd"),
                    ):
                        result = runner.invoke(ps_cmd)
                        assert result.exit_code == 1
