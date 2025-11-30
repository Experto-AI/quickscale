"""Tests for docker_utils module."""

import subprocess
from unittest.mock import Mock, patch

from quickscale_cli.utils.docker_utils import (
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

    def test_docker_compose_v1_fallback(self):
        """Test fallback to docker-compose v1 when v2 is not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = get_docker_compose_command()
            # Falls back to v1 standalone (docker-compose)
            assert result == ["docker-compose"]


class TestGetContainerStatus:
    """Tests for get_container_status function."""

    def test_container_running(self):
        """Test getting status of running container."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Up 5 minutes")
            result = get_container_status("test-container")
            assert result == "Up 5 minutes"

    def test_container_not_found(self):
        """Test when container is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            result = get_container_status("nonexistent")
            assert result is None

    def test_docker_error(self):
        """Test handling Docker errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker")
            result = get_container_status("test-container")
            assert result is None


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
        # Use a high port number unlikely to be in use
        result = is_port_available(54321)
        assert result is True

    def test_port_unavailable(self):
        """Test that a port in use is reported as unavailable."""
        import socket

        # Bind to a port to make it unavailable
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 54322))
        sock.listen(1)

        try:
            result = is_port_available(54322)
            assert result is False
        finally:
            sock.close()


class TestWaitForPortRelease:
    """Tests for wait_for_port_release function."""

    def test_port_already_available(self):
        """Test when port is already available."""
        result = wait_for_port_release(54323, timeout=1.0)
        assert result is True

    def test_port_becomes_available(self):
        """Test when port becomes available during wait."""
        import socket
        import threading

        # Bind to port temporarily
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 54324))
        sock.listen(1)

        # Release port after short delay
        def release_port():
            import time

            time.sleep(0.5)
            sock.close()

        thread = threading.Thread(target=release_port)
        thread.start()

        # Wait for port to become available
        result = wait_for_port_release(54324, timeout=2.0)
        thread.join()

        assert result is True

    def test_port_timeout(self):
        """Test timeout when port never becomes available."""
        import socket

        # Bind to port and keep it busy
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 54325))
        sock.listen(1)

        try:
            result = wait_for_port_release(54325, timeout=0.5)
            assert result is False
        finally:
            sock.close()


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

    def test_invalid_port_falls_back_to_default(self):
        """Test that invalid port value falls back to 8000."""
        import os

        original = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "invalid"
            result = get_port_from_env()
            assert result == 8000
        finally:
            if original is not None:
                os.environ["PORT"] = original
            else:
                os.environ.pop("PORT", None)
