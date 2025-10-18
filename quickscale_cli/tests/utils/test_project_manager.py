"""Tests for project_manager module."""

from unittest.mock import patch

from quickscale_cli.utils.project_manager import (
    get_db_container_name,
    get_project_state,
    get_web_container_name,
    is_in_quickscale_project,
)


class TestIsInQuickscaleProject:
    """Tests for is_in_quickscale_project function."""

    def test_in_project_directory(self, tmp_path, monkeypatch):
        """Test when in a QuickScale project directory."""
        monkeypatch.chdir(tmp_path)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        assert is_in_quickscale_project() is True

    def test_not_in_project_directory(self, tmp_path, monkeypatch):
        """Test when not in a QuickScale project directory."""
        monkeypatch.chdir(tmp_path)

        assert is_in_quickscale_project() is False


class TestGetProjectState:
    """Tests for get_project_state function."""

    def test_get_state_in_project(self, tmp_path, monkeypatch):
        """Test getting project state when in a project."""
        monkeypatch.chdir(tmp_path)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        with patch(
            "quickscale_cli.utils.project_manager.get_running_containers"
        ) as mock_containers:
            mock_containers.return_value = ["myproject-web-1", "myproject-db-1"]

            state = get_project_state()

            assert state["has_project"] is True
            assert state["project_dir"] == tmp_path
            assert state["project_name"] == tmp_path.name
            assert "myproject-web-1" in state["containers"]

    def test_get_state_not_in_project(self, tmp_path, monkeypatch):
        """Test getting project state when not in a project."""
        monkeypatch.chdir(tmp_path)

        state = get_project_state()

        assert state["has_project"] is False
        assert state["project_dir"] is None
        assert state["project_name"] is None
        assert state["containers"] == []


class TestContainerNames:
    """Tests for container name functions."""

    def test_get_web_container_name(self, tmp_path, monkeypatch):
        """Test getting web container name."""
        monkeypatch.chdir(tmp_path)

        result = get_web_container_name()
        assert result == f"{tmp_path.name}-web-1"

    def test_get_db_container_name(self, tmp_path, monkeypatch):
        """Test getting database container name."""
        monkeypatch.chdir(tmp_path)

        result = get_db_container_name()
        assert result == f"{tmp_path.name}-db-1"
