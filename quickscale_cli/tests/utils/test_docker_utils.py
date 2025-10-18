"""Tests for docker_utils module."""

import subprocess
from unittest.mock import Mock, patch

from quickscale_cli.utils.docker_utils import (
    find_docker_compose,
    get_container_status,
    get_docker_compose_command,
    get_running_containers,
    is_docker_running,
)


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
    """Tests for get_docker_compose_command function."""

    def test_docker_compose_command_available(self):
        """Test when docker-compose command is available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = get_docker_compose_command()
            assert result == ["docker-compose"]

    def test_docker_compose_fallback(self):
        """Test fallback to docker compose."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = get_docker_compose_command()
            assert result == ["docker", "compose"]


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


class TestGetRunningContainers:
    """Tests for get_running_containers function."""

    def test_get_multiple_containers(self):
        """Test getting list of running containers."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="container1\ncontainer2\ncontainer3")
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
