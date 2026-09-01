"""Tests for docker_utils module."""

import re
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quickscale_cli.utils.docker_utils import (
    BackendImageIdentity,
    BackendImageIdentityError,
    ContainerStatus,
    DockerContainerStatusError,
    DockerComposePluginRequiredError,
    IMAGE_DIGEST_ENV_VAR,
    IMAGE_REFERENCE_ENV_VAR,
    RESOURCE_PREFIX_ENV_VAR,
    build_backend_child_environment,
    build_backend_image_identity,
    exec_in_container,
    find_docker_compose,
    get_container_status,
    get_docker_compose_command,
    get_port_from_env,
    get_running_containers,
    is_docker_running,
    is_interactive,
    is_port_available,
    wait_for_port_release,
)


def _write_image_inputs(root, *, lock: bytes | None = b"lock-v1") -> None:
    """Create the minimal generated-project inputs for identity tests."""
    (root / "Dockerfile").write_bytes(b"FROM python:3.14-slim\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "generated-app"\nversion = "1.0.0"\n'
        'requires-python = ">=3.14,<3.15"\n'
    )
    if lock is not None:
        (root / "poetry.lock").write_bytes(lock)
    modules = root / "modules" / "auth"
    modules.mkdir(parents=True)
    (modules / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "quickscale-module-auth"\nversion = "0.87.0"\n'
    )


class TestBackendImageIdentity:
    """Tests for the canonical framed development image contract."""

    def test_same_inputs_in_different_directories_are_stable(self, tmp_path):
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        _write_image_inputs(first)
        _write_image_inputs(second)

        first_identity = build_backend_image_identity(first)
        second_identity = build_backend_image_identity(second)

        assert first_identity == second_identity
        assert re.fullmatch(
            r"quickscale-backend:sha256-[0-9a-f]{64}", first_identity.reference
        )
        assert first_identity.digest in first_identity.reference

    @pytest.mark.parametrize(
        "filename", ["Dockerfile", "pyproject.toml", "poetry.lock"]
    )
    def test_each_authoritative_file_invalidates_identity(self, tmp_path, filename):
        _write_image_inputs(tmp_path)
        original = build_backend_image_identity(tmp_path)
        path = tmp_path / filename
        if filename == "pyproject.toml":
            path.write_text(path.read_text().replace(">=3.14,<3.15", ">=3.14,<3.15.1"))
        else:
            path.write_bytes(path.read_bytes() + b"\nchanged\n")

        changed = build_backend_image_identity(tmp_path)
        assert changed.digest != original.digest

    def test_embedded_package_metadata_invalidates_identity(self, tmp_path):
        _write_image_inputs(tmp_path)
        original = build_backend_image_identity(tmp_path)
        module_metadata = tmp_path / "modules" / "auth" / "pyproject.toml"
        module_metadata.write_text(
            module_metadata.read_text().replace("0.87.0", "0.87.1")
        )

        assert build_backend_image_identity(tmp_path).digest != original.digest

    def test_fixed_build_arguments_are_manifest_inputs(self, tmp_path):
        _write_image_inputs(tmp_path)
        default = build_backend_image_identity(tmp_path)
        changed = build_backend_image_identity(
            tmp_path,
            build_args={"INSTALL_DEV": "false"},
        )

        assert changed.digest != default.digest

    def test_missing_lock_uses_explicit_marker(self, tmp_path):
        _write_image_inputs(tmp_path, lock=None)
        missing = build_backend_image_identity(tmp_path)
        (tmp_path / "poetry.lock").write_bytes(b"lock-v1")
        present = build_backend_image_identity(tmp_path)

        assert missing.digest != present.digest
        assert b"<missing-poetry-lock>" in missing.manifest

    def test_malformed_metadata_fails_before_any_compose_call(self, tmp_path):
        _write_image_inputs(tmp_path)
        (tmp_path / "pyproject.toml").write_text("not = [valid")
        with pytest.raises(BackendImageIdentityError):
            build_backend_image_identity(tmp_path)

    def test_secret_and_run_environment_do_not_influence_identity(
        self, tmp_path, monkeypatch
    ):
        _write_image_inputs(tmp_path)
        first = build_backend_image_identity(tmp_path)
        monkeypatch.setenv("PORT", "9123")
        monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
        monkeypatch.setenv(RESOURCE_PREFIX_ENV_VAR, "run-worker-123")

        assert build_backend_image_identity(tmp_path) == first

    def test_child_environment_is_copied_without_parent_mutation(self, monkeypatch):
        identity = BackendImageIdentity(
            "quickscale-backend:sha256-" + "a" * 64, "a" * 64, b""
        )
        monkeypatch.setenv("PORT", "9000")
        before = dict(os.environ)

        child = build_backend_child_environment(
            identity,
            base_environment=before,
            project_path=Path("project"),
        )

        assert child is not before
        assert child[IMAGE_REFERENCE_ENV_VAR] == identity.reference
        assert child[IMAGE_DIGEST_ENV_VAR] == identity.digest
        assert child[RESOURCE_PREFIX_ENV_VAR] == "project"
        assert dict(os.environ) == before

    def test_child_environment_uses_explicit_prefix_from_supplied_base(self):
        """A supplied child base is authoritative even when the parent differs."""
        identity = BackendImageIdentity(
            "quickscale-backend:sha256-" + "a" * 64,
            "a" * 64,
            b"",
        )

        child = build_backend_child_environment(
            identity,
            base_environment={RESOURCE_PREFIX_ENV_VAR: "base-scope"},
            project_path=Path("project"),
        )

        assert child[RESOURCE_PREFIX_ENV_VAR] == "base-scope"


class TestIsInteractive:
    """Tests for is_interactive function."""

    def test_interactive_terminal(self):
        """Test when running in interactive terminal."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch("sys.stdin.isatty", return_value=True):
                assert is_interactive() is True

    def test_non_interactive_stdout(self):
        """Test when stdout is not a TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            with patch("sys.stdin.isatty", return_value=True):
                assert is_interactive() is False

    def test_non_interactive_stdin(self):
        """Test when stdin is not a TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch("sys.stdin.isatty", return_value=False):
                assert is_interactive() is False

    def test_non_interactive_both(self):
        """Test when both stdout and stdin are not TTYs."""
        with patch("sys.stdout.isatty", return_value=False):
            with patch("sys.stdin.isatty", return_value=False):
                assert is_interactive() is False


class TestIsDockerRunning:
    """Tests for is_docker_running function."""

    def test_docker_running_returns_true(self):
        """Test that docker running returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            assert is_docker_running() is True
            mock_run.assert_called_once()

    def test_docker_not_running_returns_false(self):
        """Test that docker not running returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker")
            assert is_docker_running() is False

    def test_docker_not_found_returns_false(self):
        """Test that docker not found returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert is_docker_running() is False

    def test_docker_timeout_returns_false(self):
        """Test that docker timeout returns False."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker", 5)
            assert is_docker_running() is False


class TestFindDockerCompose:
    """Tests for find_docker_compose function."""

    def test_compose_file_exists(self, tmp_path, monkeypatch):
        """Test finding existing docker-compose.yml."""
        monkeypatch.chdir(tmp_path)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        result = find_docker_compose()
        assert result is not None
        assert result.name == "docker-compose.yml"

    def test_compose_file_not_exists(self, tmp_path, monkeypatch):
        """Test when docker-compose.yml doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = find_docker_compose()
        assert result is None


class TestGetDockerComposeCommand:
    """Tests for get_docker_compose_command."""

    def test_docker_compose_v2_available(self):
        """Test when docker compose v2 plugin is available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = get_docker_compose_command()
            # v2 plugin (docker compose) is tried first and preferred
            assert result == ["docker", "compose"]

    def test_docker_compose_v2_required(self):
        """Test that missing v2 plugin raises a dedicated error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(DockerComposePluginRequiredError) as error:
                get_docker_compose_command()

            assert "docker compose" in str(error.value)


class TestGetContainerStatus:
    """Tests for get_container_status function."""

    @pytest.mark.parametrize(
        ("docker_status", "expected"),
        [
            (
                "test-container\trunning\tUp 3 seconds",
                ContainerStatus("running", display_status="Up 3 seconds"),
            ),
            (
                "test-container\tcreated\tCreated",
                ContainerStatus("created", display_status="Created"),
            ),
            (
                "test-container\texited\tExited (1) 3 seconds ago",
                ContainerStatus(
                    "exited", exit_code=1, display_status="Exited (1) 3 seconds ago"
                ),
            ),
        ],
    )
    def test_container_status_table(self, docker_status, expected):
        """Parse each exact Docker state from one mocked row."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=docker_status)
            result = get_container_status("test-container")
            assert result == expected

            command = mock_run.call_args.args[0]
            assert "name=^/test\\-container$" in command
            assert command[command.index("--format") + 1] == (
                "{{.Names}}\t{{.State}}\t{{.Status}}"
            )

    def test_container_not_found(self):
        """Successful empty output is the only absent result."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            result = get_container_status("nonexistent")
            assert result == ContainerStatus("absent")

    @pytest.mark.parametrize(
        "docker_status",
        [
            "test-container\trunning\tUp 3 seconds\nother-container\texited\tExited (1)",
            "test-container\tnonsense\tUnknown",
            "test-container\texited\tExited (not-an-integer)",
        ],
    )
    def test_ambiguous_or_malformed_output_fails_loudly(self, docker_status):
        """Multiple rows and malformed rows cannot become a usable state."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=docker_status)
            with pytest.raises(DockerContainerStatusError):
                get_container_status("test-container")

    @pytest.mark.parametrize(
        "error", [subprocess.CalledProcessError(1, "docker"), FileNotFoundError()]
    )
    def test_docker_invocation_failure_fails_loudly(self, error):
        """Docker nonzero and missing-binary failures are not absent states."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = error
            with pytest.raises(DockerContainerStatusError):
                get_container_status("test-container")

    def test_docker_timeout_fails_loudly(self):
        """A Docker query timeout cannot consume readiness's absent budget."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker", 5)
            with pytest.raises(DockerContainerStatusError, match="query failed"):
                get_container_status("test-container")


class TestExecInContainer:
    """Tests for exec_in_container function."""

    def test_exec_command_successfully(self):
        """Test executing command in container successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = exec_in_container("test-container", ["ls", "-la"])
            assert result == 0

    def test_exec_command_with_interactive_flag(self):
        """Test executing command with interactive flag."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = exec_in_container("test-container", ["bash"], interactive=True)

            # Verify -it flag was added
            call_args = mock_run.call_args[0][0]
            assert "-it" in call_args
            assert result == 0

    def test_exec_command_without_interactive_flag(self):
        """Test executing command without interactive flag."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = exec_in_container("test-container", ["ls"], interactive=False)

            # Verify -it flag was not added
            call_args = mock_run.call_args[0][0]
            assert "-it" not in call_args
            assert result == 0

    def test_exec_command_failure(self):
        """Test handling command execution failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)
            result = exec_in_container("test-container", ["failing-command"])
            assert result == 1

    def test_exec_command_subprocess_error(self):
        """Test handling subprocess error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Error")
            result = exec_in_container("test-container", ["command"])
            assert result == 1


class TestGetRunningContainers:
    """Tests for get_running_containers function."""

    def test_get_multiple_containers(self):
        """Test getting list of running containers."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="container1\ncontainer2\ncontainer3"
            )
            result = get_running_containers()
            assert result == ["container1", "container2", "container3"]

    def test_no_containers_running(self):
        """Test when no containers are running."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            result = get_running_containers()
            assert result == []

    def test_docker_error(self):
        """Test handling Docker errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker")
            result = get_running_containers()
            assert result == []


class TestIsPortAvailable:
    """Tests for is_port_available function."""

    def test_port_available(self):
        """Test that an unused port is reported as available."""
        mock_socket = Mock()
        mock_socket.bind.return_value = None

        with patch("quickscale_cli.utils.docker_utils.socket.socket") as mock_factory:
            mock_factory.return_value = mock_socket

            result = is_port_available(54321)

        assert result is True
        mock_socket.bind.assert_called_once_with(("0.0.0.0", 54321))
        mock_socket.close.assert_called_once()

    def test_port_unavailable(self):
        """Test that a port in use is reported as unavailable."""
        mock_socket = Mock()
        mock_socket.bind.side_effect = OSError("Address already in use")

        with patch("quickscale_cli.utils.docker_utils.socket.socket") as mock_factory:
            mock_factory.return_value = mock_socket

            result = is_port_available(54322)

        assert result is False
        mock_socket.bind.assert_called_once_with(("0.0.0.0", 54322))
        mock_socket.close.assert_called_once()


class TestWaitForPortRelease:
    """Tests for wait_for_port_release function."""

    def test_port_already_available(self):
        """Test when port is already available."""
        with patch(
            "quickscale_cli.utils.docker_utils.is_port_available", return_value=True
        ) as mock_is_available:
            result = wait_for_port_release(54323, timeout=1.0)

        assert result is True
        mock_is_available.assert_called_once_with(54323)

    def test_port_becomes_available(self):
        """Test when port becomes available during wait."""
        with (
            patch(
                "quickscale_cli.utils.docker_utils.is_port_available",
                side_effect=[False, False, True],
            ) as mock_is_available,
            patch("quickscale_cli.utils.docker_utils.time.sleep") as mock_sleep,
        ):
            result = wait_for_port_release(54324, timeout=2.0, interval=0.2)

        assert result is True
        assert mock_is_available.call_count == 3
        assert mock_sleep.call_count == 2

    def test_port_timeout(self):
        """Test timeout when port never becomes available."""
        with (
            patch(
                "quickscale_cli.utils.docker_utils.is_port_available",
                return_value=False,
            ),
            patch("quickscale_cli.utils.docker_utils.time.sleep"),
        ):
            result = wait_for_port_release(54325, timeout=0.5, interval=0.1)

        assert result is False


class TestGetPortFromEnv:
    """Tests for get_port_from_env function."""

    def test_default_port(self):
        """Test that default port is 8000."""
        import os

        # Ensure PORT is not set
        original = os.environ.pop("PORT", None)
        try:
            result = get_port_from_env()
            assert result == 8000
        finally:
            if original is not None:
                os.environ["PORT"] = original

    def test_custom_port_from_env(self):
        """Test reading custom port from environment."""
        import os

        original = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "9000"
            result = get_port_from_env()
            assert result == 9000
        finally:
            if original is not None:
                os.environ["PORT"] = original
            else:
                os.environ.pop("PORT", None)

    def test_invalid_port_raises_value_error(self):
        """Test that invalid port values fail hard with a descriptive error."""
        import os

        original = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "invalid"
            with pytest.raises(
                ValueError,
                match=r"PORT environment variable must be an integer, got 'invalid'",
            ):
                get_port_from_env()
        finally:
            if original is not None:
                os.environ["PORT"] = original
            else:
                os.environ.pop("PORT", None)
