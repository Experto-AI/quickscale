"""Extended tests for development_commands.py - covering error paths and missing lines."""

import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from quickscale_cli.commands.development_commands import (
    _SUPERUSER_SENTINEL,
    _dependencies_changed_since_last_build,
    _handle_superuser_after_up,
    _handle_up_error,
    _run_docker_compose_up,
    _run_docker_exec_command,
    _show_port_conflict_error,
    _superuser_exists_in_backend,
    _update_last_build_timestamp,
    _validate_project_and_docker,
    down,
    logs,
    manage,
    shell,
    up,
)
from quickscale_cli.utils.docker_utils import DockerComposePluginRequiredError
from quickscale_cli.utils.project_manager import ProjectConfigLoadError


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
        error = subprocess.CalledProcessError(1, ["docker", "compose"])
        error.stderr = "Bind for 0.0.0.0:8000 failed: port is already allocated"
        error.stdout = ""
        _handle_up_error(error)


class TestVerifierComposeProjectPropagation:
    """Only an exact verifier marker changes Compose project selection."""

    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_valid_marker_is_inserted_before_compose_up(self, mock_run, monkeypatch):
        monkeypatch.setenv(
            "QUICKSCALE_VERIFY_COMPOSE_PROJECT",
            "qs-sa117b-" + "a" * 32,
        )
        mock_run.return_value = Mock(returncode=0)

        _run_docker_compose_up(["docker", "compose"], build=False, no_cache=False)

        assert mock_run.call_args.args[0] == [
            "docker",
            "compose",
            "--project-name",
            "qs-sa117b-" + "a" * 32,
            "up",
            "-d",
        ]

    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_valid_marker_is_inserted_before_verbose_compose_up(
        self, mock_run, monkeypatch
    ):
        """The marker is preserved on the build/verbose Compose route."""
        marker = "qs-sa117b-" + "b" * 32
        monkeypatch.setenv("QUICKSCALE_VERIFY_COMPOSE_PROJECT", marker)
        mock_run.return_value = Mock(returncode=0)

        _run_docker_compose_up(["docker", "compose"], build=True, no_cache=False)

        assert mock_run.call_args.args[0] == [
            "docker",
            "compose",
            "--project-name",
            marker,
            "--progress",
            "plain",
            "up",
            "-d",
            "--build",
        ]

    @pytest.mark.parametrize("marker", [None, "qs-sa117b-bad", "qs-sa117b-" + "A" * 32])
    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_absent_or_malformed_marker_preserves_ordinary_command(
        self, mock_run, monkeypatch, marker
    ):
        if marker is None:
            monkeypatch.delenv("QUICKSCALE_VERIFY_COMPOSE_PROJECT", raising=False)
        else:
            monkeypatch.setenv("QUICKSCALE_VERIFY_COMPOSE_PROJECT", marker)
        mock_run.return_value = Mock(returncode=0)

        _run_docker_compose_up(["docker", "compose"], build=False, no_cache=False)

        assert mock_run.call_args.args[0] == ["docker", "compose", "up", "-d"]

    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_absent_marker_preserves_verbose_compose_argv(self, mock_run, monkeypatch):
        """No marker must leave the build/verbose Compose argv unchanged."""
        monkeypatch.delenv("QUICKSCALE_VERIFY_COMPOSE_PROJECT", raising=False)
        mock_run.return_value = Mock(returncode=0)

        _run_docker_compose_up(["docker", "compose"], build=True, no_cache=False)

        assert mock_run.call_args.args[0] == [
            "docker",
            "compose",
            "--progress",
            "plain",
            "up",
            "-d",
            "--build",
        ]

    def test_generic_error(self):
        """Handle generic error output"""
        error = subprocess.CalledProcessError(1, ["docker", "compose"])
        error.stderr = "Some other error"
        error.stdout = ""
        _handle_up_error(error)

    def test_error_no_output(self):
        """Handle error with no output"""
        error = subprocess.CalledProcessError(1, ["docker", "compose"])
        error.stderr = ""
        error.stdout = ""
        _handle_up_error(error)

    def test_port_conflict_in_stdout(self):
        """Handle port conflict in stdout"""
        error = subprocess.CalledProcessError(1, ["docker", "compose"])
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
# _superuser_exists_in_backend
# ============================================================================


class TestSuperuserExistsInBackend:
    """Tests for _superuser_exists_in_backend"""

    _DJANGO_BANNER = "12 objects imported automatically (use -v 2 for details).\n"

    @patch("subprocess.run")
    def test_banner_plus_sentinel_0_returns_false(self, mock_run):
        """Return False when Django banner precedes QUICKSCALE_SUPERUSER=0."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=self._DJANGO_BANNER + "QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is False

    @patch("subprocess.run")
    def test_banner_plus_sentinel_1_returns_true(self, mock_run):
        """Return True when Django banner precedes QUICKSCALE_SUPERUSER=1."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=self._DJANGO_BANNER + "QUICKSCALE_SUPERUSER=1\n",
            stderr="",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is True

    @patch("subprocess.run")
    def test_banner_without_sentinel_returns_none(self, mock_run):
        """Return None when banner is present but sentinel line is absent."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=self._DJANGO_BANNER,
            stderr="",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is None

    @patch("subprocess.run")
    def test_nonzero_exit_operational_error_returns_none(self, mock_run):
        """Return None when manage.py shell exits non-zero (e.g. OperationalError)."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="django.db.utils.OperationalError",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is None

    @patch("subprocess.run")
    def test_empty_stdout_returns_none(self, mock_run):
        """Return None when stdout is completely empty (no banner, no sentinel)."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        assert _superuser_exists_in_backend("myproject-backend-1") is None

    @patch("subprocess.run")
    def test_malformed_sentinel_value_returns_none(self, mock_run):
        """Return None when sentinel line has an unexpected value."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=maybe\n",
            stderr="",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is None

    # --- SA129-TEST-001: producer argv / script / subprocess inspection ---

    @patch("subprocess.run")
    def test_probe_complete_argv(self, mock_run):
        """The probe passes the exact docker exec argv to subprocess.run."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        argv = mock_run.call_args.args[0]
        assert argv == [
            "docker",
            "exec",
            "myapp-backend-1",
            "python",
            "manage.py",
            "shell",
            "-c",
            argv[7],  # script slot; asserted structurally below
        ]
        # Structural: first 7 elements are the fixed docker/exec/python prefix.
        assert argv[:7] == [
            "docker",
            "exec",
            "myapp-backend-1",
            "python",
            "manage.py",
            "shell",
            "-c",
        ]

    @patch("subprocess.run")
    def test_probe_script_contains_orm_query(self, mock_run):
        """The inline script queries get_user_model().objects.filter(is_superuser=True).exists()."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        script = mock_run.call_args.args[0][-1]
        assert "get_user_model().objects.filter(is_superuser=True).exists()" in script

    @patch("subprocess.run")
    def test_probe_script_emits_sentinel_line(self, mock_run):
        """The inline script prints QUICKSCALE_SUPERUSER={int(exists)}."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        script = mock_run.call_args.args[0][-1]
        assert "print(f'" in script
        assert _SUPERUSER_SENTINEL in script
        assert "{int(exists)}" in script

    @patch("subprocess.run")
    def test_probe_script_always_exits_zero(self, mock_run):
        """The inline script calls sys.exit(0) unconditionally."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        script = mock_run.call_args.args[0][-1]
        assert "sys.exit(0)" in script

    @patch("subprocess.run")
    def test_probe_argv_has_no_no_imports_flag(self, mock_run):
        """The probe command does not pass --no-imports to manage.py shell."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        argv = mock_run.call_args.args[0]
        assert "--no-imports" not in argv

    @patch("subprocess.run")
    def test_probe_subprocess_kwargs_capture_and_text(self, mock_run):
        """subprocess.run is called with capture_output=True and text=True."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="QUICKSCALE_SUPERUSER=0\n",
            stderr="",
        )
        _superuser_exists_in_backend("myapp-backend-1")

        assert mock_run.call_args.kwargs.get("capture_output") is True
        assert mock_run.call_args.kwargs.get("text") is True

    # --- SA129-TEST-001: reverse-scan proof ---

    @patch("subprocess.run")
    def test_reverse_scan_finds_last_sentinel_not_first(self, mock_run):
        """Reverse scan returns the last sentinel line, not the first.

        Django 5.2+ emits an auto-import banner to stdout before the script's
        own output.  If the scan were forward, it would hit the banner first
        and find no sentinel; a forward scan would also be vulnerable to a
        malicious or accidental earlier sentinel line.  Reverse scan ensures
        the *last* sentinel wins.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "QUICKSCALE_SUPERUSER=0\n"
                "12 objects imported automatically (use -v 2 for details).\n"
                "QUICKSCALE_SUPERUSER=1\n"
            ),
            stderr="",
        )

        assert _superuser_exists_in_backend("myproject-backend-1") is True


# ============================================================================
# _handle_superuser_after_up
# ============================================================================


class TestHandleSuperuserAfterUp:
    """Tests for _handle_superuser_after_up tri-state branching and messages.

    SA129-TEST-001 requires proof that the handler exercises every branch of
    the ``_superuser_exists_in_backend`` tri-state (True / False / None) and
    that each user-facing message is byte-unchanged.

    These tests call ``_handle_superuser_after_up`` directly with a mock config
    and patch ``_superuser_exists_in_backend`` to control the probe result,
    rather than invoking the full ``up`` CLI command.
    """

    def _make_config(self, create_superuser: bool = True):
        """Return a minimal mock config with docker.create_superuser set."""
        config = Mock()
        config.docker = Mock()
        config.docker.create_superuser = create_superuser
        return config

    # --- True path: superuser exists, skip creation ---

    @patch("quickscale_cli.commands.development_commands.is_interactive")
    @patch("quickscale_cli.commands.development_commands._superuser_exists_in_backend")
    @patch("quickscale_cli.commands.development_commands.get_backend_container_name")
    def test_true_skips_creation_with_message(
        self, mock_container, mock_probe, mock_interactive, capsys
    ):
        """When probe returns True, print skip message and do not create."""
        mock_container.return_value = "myapp-backend-1"
        mock_probe.return_value = True
        mock_interactive.return_value = False

        _handle_superuser_after_up(self._make_config())
        captured = capsys.readouterr()

        # The handler prints the exact skip message and nothing else.
        assert (
            captured.out
            == "ℹ️  Superuser already exists. Skipping createsuperuser step.\n"
        )
        assert captured.err == ""

    # --- False path: no superuser, non-interactive ---

    @patch("quickscale_cli.commands.development_commands.is_interactive")
    @patch("quickscale_cli.commands.development_commands._superuser_exists_in_backend")
    @patch("quickscale_cli.commands.development_commands.get_backend_container_name")
    def test_false_noninteractive_prints_warning_and_manual_hint(
        self, mock_container, mock_probe, mock_interactive, capsys
    ):
        """When probe returns False in non-interactive mode, warn and hint."""
        mock_container.return_value = "myapp-backend-1"
        mock_probe.return_value = False
        mock_interactive.return_value = False

        _handle_superuser_after_up(self._make_config())
        captured = capsys.readouterr()

        # Exact output: secho warning + echo hint, then return (no createsuperuser).
        assert (
            "⚠️  Superuser creation is enabled but requires interactive input."
            in captured.out
        )
        assert "   Run: quickscale manage createsuperuser" in captured.out
        assert "Creating Django superuser..." not in captured.out

    # --- False path: no superuser, interactive ---

    @patch("quickscale_cli.commands.development_commands._run_docker_exec_command")
    @patch("quickscale_cli.commands.development_commands.is_interactive")
    @patch("quickscale_cli.commands.development_commands._superuser_exists_in_backend")
    @patch("quickscale_cli.commands.development_commands.get_backend_container_name")
    def test_false_interactive_runs_createsuperuser(
        self, mock_container, mock_probe, mock_interactive, mock_exec, capsys
    ):
        """When probe returns False in interactive mode, run createsuperuser."""
        mock_container.return_value = "myapp-backend-1"
        mock_probe.return_value = False
        mock_interactive.return_value = True

        _handle_superuser_after_up(self._make_config())
        captured = capsys.readouterr()

        assert "👤 Creating Django superuser..." in captured.out
        mock_exec.assert_called_once_with(
            "myapp-backend-1",
            ["python", "manage.py", "createsuperuser"],
            capture=False,
        )

    # --- None path: probe returns None, non-interactive ---

    @patch("quickscale_cli.commands.development_commands.is_interactive")
    @patch("quickscale_cli.commands.development_commands._superuser_exists_in_backend")
    @patch("quickscale_cli.commands.development_commands.get_backend_container_name")
    def test_none_noninteractive_prints_could_not_verify(
        self, mock_container, mock_probe, mock_interactive, capsys
    ):
        """When probe returns None in non-interactive mode, warn with exact message."""
        mock_container.return_value = "myapp-backend-1"
        mock_probe.return_value = None
        mock_interactive.return_value = False

        _handle_superuser_after_up(self._make_config())
        captured = capsys.readouterr()

        assert "⚠️  Could not verify superuser status." in captured.out
        assert "   Run: quickscale manage createsuperuser" in captured.out
        assert "Creating Django superuser..." not in captured.out

    # --- None path: probe returns None, interactive ---

    @patch("quickscale_cli.commands.development_commands._run_docker_exec_command")
    @patch("quickscale_cli.commands.development_commands.is_interactive")
    @patch("quickscale_cli.commands.development_commands._superuser_exists_in_backend")
    @patch("quickscale_cli.commands.development_commands.get_backend_container_name")
    def test_none_interactive_continues_to_createsuperuser(
        self, mock_container, mock_probe, mock_interactive, mock_exec, capsys
    ):
        """When probe returns None in interactive mode, warn then proceed."""
        mock_container.return_value = "myapp-backend-1"
        mock_probe.return_value = None
        mock_interactive.return_value = True

        _handle_superuser_after_up(self._make_config())
        captured = capsys.readouterr()

        assert "⚠️  Could not verify superuser status." in captured.out
        assert "   Proceeding with interactive superuser creation." in captured.out
        assert "👤 Creating Django superuser..." in captured.out
        mock_exec.assert_called_once_with(
            "myapp-backend-1",
            ["python", "manage.py", "createsuperuser"],
            capture=False,
        )

    # --- Guard: config=None does nothing ---

    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_config_none_does_nothing(self, mock_run):
        """When config is None the handler returns without probing."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        _handle_superuser_after_up(None)

        mock_run.assert_not_called()

    # --- Guard: create_superuser=False does nothing ---

    @patch("quickscale_cli.commands.development_commands.subprocess.run")
    def test_create_superuser_false_does_nothing(self, mock_run):
        """When create_superuser is False the handler returns without probing."""
        config = self._make_config(create_superuser=False)
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        _handle_superuser_after_up(config)

        mock_run.assert_not_called()


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

    def test_up_aborts_when_quickscale_yml_is_invalid(self):
        """Development up should fail hard when strict config loading fails."""
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
                    "quickscale_cli.commands.development_commands.get_project_config",
                    side_effect=ProjectConfigLoadError(
                        "Invalid quickscale.yml: Line 8: Legacy auth desired-config key 'modules.auth.allow_registration' is no longer supported\n"
                        "  Suggestion: Use modules.auth.registration_enabled: true|false."
                    ),
                ):
                    result = runner.invoke(up)

        assert result.exit_code == 1
        assert "quickscale.yml is invalid" in result.output
        assert "allow_registration" in result.output
        assert "registration_enabled" in result.output

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
                            return_value=["docker", "compose"],
                        ):
                            with patch(
                                "quickscale_cli.commands.development_commands.get_backend_container_name",
                                return_value="myproject-backend-1",
                            ):
                                with patch(
                                    "subprocess.run", return_value=Mock(returncode=0)
                                ):
                                    result = runner.invoke(up)
                                    assert result.exit_code == 0
                                    assert (
                                        "Dependencies may have changed" in result.output
                                    )

    def test_up_requires_compose_v2_plugin(self):
        """Test up shows remediation when the Compose v2 plugin is unavailable."""
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
                        "quickscale_cli.commands.development_commands.get_docker_compose_command",
                        side_effect=DockerComposePluginRequiredError(
                            "Docker Compose v2 is required."
                        ),
                    ):
                        result = runner.invoke(up)

        assert result.exit_code == 1
        assert "Docker Compose v2 plugin is required" in result.output
        assert "docker compose" in result.output


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
                    return_value=["docker", "compose"],
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name",
                    return_value="backend",
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
                    "quickscale_cli.commands.development_commands.get_backend_container_name",
                    return_value="backend",
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
                    return_value=["docker", "compose"],
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
                    return_value=["docker", "compose"],
                ):
                    with patch(
                        "subprocess.run",
                        side_effect=subprocess.CalledProcessError(1, "cmd"),
                    ):
                        result = runner.invoke(ps_cmd)
                        assert result.exit_code == 1
