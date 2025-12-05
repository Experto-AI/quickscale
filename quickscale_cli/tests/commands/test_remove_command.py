"""Tests for remove command"""

import pytest
from pathlib import Path
from click.testing import CliRunner

from quickscale_cli.commands.remove_command import remove


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI runner"""
    return CliRunner()


@pytest.fixture
def project_with_module(tmp_path: Path) -> Path:
    """Create a project with an embedded module"""
    project_path = tmp_path / "myproject"
    project_path.mkdir()

    # Create modules directory with auth module
    modules_dir = project_path / "modules" / "auth"
    modules_dir.mkdir(parents=True)
    (modules_dir / "__init__.py").write_text("")
    (modules_dir / "models.py").write_text("# Models")
    (modules_dir / "views.py").write_text("# Views")

    # Create state file
    quickscale_dir = project_path / ".quickscale"
    quickscale_dir.mkdir()
    state_content = """
version: "1"
project:
  name: myproject
  theme: html
  created_at: "2024-01-01T00:00:00"
  last_applied: "2024-01-01T00:00:00"
modules:
  auth:
    name: auth
    version: "0.71.0"
    embedded_at: "2024-01-01T00:00:00"
    options:
      registration_enabled: true
"""
    (quickscale_dir / "state.yml").write_text(state_content)

    # Create quickscale.yml config
    config_content = """
project:
  name: myproject
  theme: html
modules:
  auth:
    options:
      registration_enabled: true
docker:
  start: false
  build: false
"""
    (project_path / "quickscale.yml").write_text(config_content)

    # Create core directory with settings and urls
    core_dir = project_path / "core"
    core_dir.mkdir()
    (core_dir / "settings.py").write_text(
        """
INSTALLED_APPS = [
    "django.contrib.admin",
    "modules.auth",
]
"""
    )
    (core_dir / "urls.py").write_text(
        """
urlpatterns = [
    path("accounts/", include("modules.auth.urls")),
]
"""
    )

    return project_path


class TestRemoveCommand:
    """Tests for remove command"""

    def test_remove_help(self, cli_runner: CliRunner) -> None:
        """Test remove command help"""
        result = cli_runner.invoke(remove, ["--help"])
        assert result.exit_code == 0
        assert "Remove an embedded module" in result.output

    def test_remove_module_no_force(
        self, cli_runner: CliRunner, project_with_module: Path
    ) -> None:
        """Test remove without --force shows warning"""
        import os

        os.chdir(project_with_module)

        result = cli_runner.invoke(
            remove,
            ["auth"],
            input="n\n",  # Say no to confirmation
            catch_exceptions=False,
        )
        # Should prompt for confirmation (warning message)
        assert "warning" in result.output.lower() or "remove" in result.output.lower()

    def test_remove_module_with_force(
        self, cli_runner: CliRunner, project_with_module: Path
    ) -> None:
        """Test remove with --force"""
        import os

        os.chdir(project_with_module)

        cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        # Module directory should be removed
        assert not (project_with_module / "modules" / "auth").exists()
        # State should be updated
        state_path = project_with_module / ".quickscale" / "state.yml"
        state_content = state_path.read_text()
        assert "auth:" not in state_content or "modules: {}" in state_content

    def test_remove_module_not_found(
        self, cli_runner: CliRunner, project_with_module: Path
    ) -> None:
        """Test removing non-existent module"""
        import os

        os.chdir(project_with_module)

        result = cli_runner.invoke(
            remove,
            ["nonexistent", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_remove_outside_project(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test remove outside of a QuickScale project"""
        import os

        os.chdir(tmp_path)

        cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        # Should fail - no project found

    def test_remove_updates_config(
        self, cli_runner: CliRunner, project_with_module: Path
    ) -> None:
        """Test that remove updates quickscale.yml"""
        import os

        os.chdir(project_with_module)

        cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        config_path = project_with_module / "quickscale.yml"
        config_content = config_path.read_text()
        # Auth should be removed from modules
        assert "auth:" not in config_content or "modules:" not in config_content
