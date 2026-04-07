"""Tests for remove command."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from quickscale_cli.commands.remove_command import remove


def _write_project_with_auth(project_path: Path) -> None:
    modules_dir = project_path / "modules" / "auth"
    modules_dir.mkdir(parents=True)
    (modules_dir / "__init__.py").write_text("")
    (modules_dir / "models.py").write_text("# Models\n")

    package_dir = project_path / "myproject"
    (package_dir / "settings").mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "settings" / "__init__.py").write_text("")
    (package_dir / "settings" / "modules.py").write_text(
        "PREVIOUS_SETTINGS = ['auth']\n"
    )
    (package_dir / "urls_modules.py").write_text("MODULE_URLPATTERNS = ['auth']\n")
    managed_dir = package_dir / "quickscale_managed"
    managed_dir.mkdir()
    (managed_dir / "__init__.py").write_text("# managed\n")

    quickscale_dir = project_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "project": {
                    "slug": "myproject",
                    "package": "myproject",
                    "theme": "showcase_html",
                    "created_at": "2024-01-01T00:00:00",
                    "last_applied": "2024-01-01T00:00:00",
                },
                "modules": {
                    "auth": {
                        "version": "0.71.0",
                        "commit_sha": "abc123",
                        "embedded_at": "2024-01-01T00:00:00",
                        "options": {"registration_enabled": True},
                    }
                },
            },
            sort_keys=False,
        )
    )
    (quickscale_dir / "config.yml").write_text(
        yaml.safe_dump(
            {
                "default_remote": "https://github.com/Experto-AI/quickscale.git",
                "modules": {
                    "auth": {
                        "prefix": "modules/auth",
                        "branch": "splits/auth-module",
                        "installed_version": "0.71.0",
                        "installed_at": "2024-01-01",
                    }
                },
            },
            sort_keys=False,
        )
    )
    (project_path / "quickscale.yml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "project": {
                    "slug": "myproject",
                    "package": "myproject",
                    "theme": "showcase_html",
                },
                "modules": {
                    "auth": {"registration_enabled": True},
                },
                "docker": {
                    "start": False,
                    "build": False,
                    "create_superuser": False,
                },
            },
            sort_keys=False,
        )
    )


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project_with_module(tmp_path: Path) -> Path:
    project_path = tmp_path / "myproject"
    project_path.mkdir()
    _write_project_with_auth(project_path)
    return project_path


class TestRemoveCommand:
    def test_remove_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(remove, ["--help"])
        assert result.exit_code == 0
        assert "Remove an embedded module" in result.output

    def test_remove_module_no_force(
        self,
        cli_runner: CliRunner,
        project_with_module: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(project_with_module)

        result = cli_runner.invoke(
            remove,
            ["auth"],
            input="n\n",
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "warning" in result.output.lower() or "remove" in result.output.lower()
        assert (project_with_module / "modules" / "auth").exists()

    def test_remove_module_with_force(
        self,
        cli_runner: CliRunner,
        project_with_module: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(project_with_module)

        result = cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert not (project_with_module / "modules" / "auth").exists()

        state = yaml.safe_load(
            (project_with_module / ".quickscale" / "state.yml").read_text()
        )
        assert "auth" not in state.get("modules", {})

        config = yaml.safe_load((project_with_module / "quickscale.yml").read_text())
        assert "auth" not in config.get("modules", {})

        legacy_config = yaml.safe_load(
            (project_with_module / ".quickscale" / "config.yml").read_text()
        )
        assert "auth" not in legacy_config.get("modules", {})

    def test_remove_module_not_found(
        self,
        cli_runner: CliRunner,
        project_with_module: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(project_with_module)

        result = cli_runner.invoke(
            remove,
            ["nonexistent", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "not installed" in result.output.lower()

    def test_remove_outside_project(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "Unable to resolve project identity" in result.output

    def test_remove_preserves_other_legacy_tracking(
        self,
        cli_runner: CliRunner,
        project_with_module: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        legacy_config_path = project_with_module / ".quickscale" / "config.yml"
        legacy_config = yaml.safe_load(legacy_config_path.read_text())
        legacy_config["modules"]["blog"] = {
            "prefix": "modules/blog",
            "branch": "splits/blog-module",
            "installed_version": "0.71.0",
            "installed_at": "2024-01-02",
        }
        legacy_config_path.write_text(yaml.safe_dump(legacy_config, sort_keys=False))

        monkeypatch.chdir(project_with_module)
        result = cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        updated_legacy_config = yaml.safe_load(legacy_config_path.read_text())
        assert "auth" not in updated_legacy_config.get("modules", {})
        assert "blog" in updated_legacy_config.get("modules", {})
