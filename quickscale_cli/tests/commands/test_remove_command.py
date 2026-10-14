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
                    "theme": "showcase_react",
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
                    "theme": "showcase_react",
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


def _write_project_with_modules(
    project_path: Path, module_names: tuple[str, ...]
) -> None:
    """Write a generated-project layout embedding *module_names* with real manifests."""
    modules_root = Path(__file__).resolve().parents[3] / "quickscale_modules"
    for name in module_names:
        module_dir = project_path / "modules" / name
        module_dir.mkdir(parents=True)
        (module_dir / "__init__.py").write_text("")
        (module_dir / "module.yml").write_text(
            (modules_root / name / "module.yml").read_text()
        )

    package_dir = project_path / "myproject"
    (package_dir / "settings").mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "settings" / "__init__.py").write_text("")
    (package_dir / "settings" / "modules.py").write_text("# managed\n")
    (package_dir / "urls_modules.py").write_text("# managed\n")

    quickscale_dir = project_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "project": {
                    "slug": "myproject",
                    "package": "myproject",
                    "theme": "showcase_react",
                    "created_at": "2024-01-01T00:00:00",
                    "last_applied": "2024-01-01T00:00:00",
                },
                "modules": {
                    name: {
                        "version": "0.88.0",
                        "commit_sha": "abc123",
                        "embedded_at": "2024-01-01T00:00:00",
                        "options": {},
                    }
                    for name in module_names
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
                    name: {
                        "prefix": f"modules/{name}",
                        "branch": f"splits/{name}-module",
                        "installed_version": "0.88.0",
                        "installed_at": "2024-01-01",
                    }
                    for name in module_names
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
                    "theme": "showcase_react",
                },
                "modules": {name: {} for name in module_names},
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

        # Phase 3: remove no longer writes to legacy config.yml.
        # The legacy config.yml is a read-through compatibility input only.
        legacy_config = yaml.safe_load(
            (project_with_module / ".quickscale" / "config.yml").read_text()
        )
        # Legacy config.yml is no longer mutated by remove; auth remains as-is.
        assert "auth" in legacy_config.get("modules", {})

    def test_remove_refuses_a_module_a_remaining_module_requires(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rule 39: removal refuses while an installed module requires the target.

        The remaining set (listings, orgs, auth, notifications) is valid only
        with storage, whose shared editor mount listings' admin needs; the
        removal rolls back and names the requirement.
        """
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        _write_project_with_modules(
            project_path, ("auth", "listings", "notifications", "orgs", "storage")
        )
        monkeypatch.chdir(project_path)

        result = cli_runner.invoke(
            remove,
            ["storage", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "'listings' requires 'storage'" in result.output
        state = yaml.safe_load((project_path / ".quickscale" / "state.yml").read_text())
        assert "storage" in state.get("modules", {})
        assert (project_path / "modules" / "storage").exists()

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

    def test_remove_records_regenerated_managed_hashes(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A removal refreshes the managed-file hashes, seam declaration included.

        The removal's regeneration creates the theme seam declaration in a
        project that predates it; without a hash record that managed file
        would stay invisible to drift detection, and the regenerated wiring
        files would read as drift instead.
        """
        from quickscale_core.project_state import (
            ProjectStateManager,
            hash_managed_file,
        )
        from quickscale_core.schema.state_schema import StateManager

        project_path = tmp_path / "myproject"
        project_path.mkdir()
        _write_project_with_modules(project_path, ("auth",))
        monkeypatch.chdir(project_path)

        result = cli_runner.invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        seam_relative = "frontend/src/quickscaleSeam.d.ts"
        state = StateManager(project_path).load()
        assert state is not None
        for relative in (
            "myproject/settings/modules.py",
            "myproject/urls_modules.py",
            seam_relative,
        ):
            assert relative in state.managed_files
            assert state.managed_files[relative].hash == hash_managed_file(
                project_path / relative
            )
        assert ProjectStateManager(project_path).detect_managed_file_drift() == []

        # A later edit of the regenerated declaration is detected.
        (project_path / seam_relative).write_text("// edited\n")
        drift = ProjectStateManager(project_path).detect_managed_file_drift()
        assert any(record.path == seam_relative for record in drift)

    def test_remove_orphan_keeps_survivor_legacy_tracking(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Removing a filesystem-only orphan keeps the survivor's legacy tracking.

        The survivor's branch, prefix, and installed_at live only in the
        legacy config.yml, and the removal's hash refresh materializes the
        consolidated state; the legacy read-through must run before that save,
        or the survivor's update and push tracking is lost.
        """
        from quickscale_core.project_state import ProjectStateManager

        project_path = tmp_path / "myproject"
        project_path.mkdir()
        _write_project_with_modules(project_path, ("storage",))
        orphan_dir = project_path / "modules" / "orphan"
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "__init__.py").write_text("")
        monkeypatch.chdir(project_path)

        result = cli_runner.invoke(
            remove,
            ["orphan", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        state = ProjectStateManager(project_path).load_state()
        assert state is not None
        assert state.modules["storage"].branch == "splits/storage-module"
        assert state.modules["storage"].prefix == "modules/storage"
        assert state.modules["storage"].installed_at == "2024-01-01"

    def test_remove_preserves_other_legacy_tracking(
        self,
        cli_runner: CliRunner,
        project_with_module: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        legacy_config_path = project_with_module / ".quickscale" / "config.yml"
        legacy_config = yaml.safe_load(legacy_config_path.read_text())
        legacy_config["modules"]["storage"] = {
            "prefix": "modules/storage",
            "branch": "splits/storage-module",
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
        # Phase 3: remove no longer writes to legacy config.yml.
        # The legacy config.yml is a read-through compatibility input only.
        updated_legacy_config = yaml.safe_load(legacy_config_path.read_text())
        # Legacy config.yml is no longer mutated by remove; auth remains as-is.
        assert "auth" in updated_legacy_config.get("modules", {})
        assert "storage" in updated_legacy_config.get("modules", {})
