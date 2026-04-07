"""Extended tests for remove_command.py transactional behavior."""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from quickscale_cli.commands.remove_command import (
    _check_module_exists,
    _regenerate_managed_wiring_after_removal,
    _remove_module_directory,
    remove,
)
from quickscale_cli.schema.state_schema import StateManager


def _write_valid_remove_project(project_path: Path) -> None:
    module_dir = project_path / "modules" / "auth"
    module_dir.mkdir(parents=True)
    (module_dir / "__init__.py").write_text("")
    (module_dir / "models.py").write_text("# auth\n")

    package_dir = project_path / "myproject"
    (package_dir / "settings").mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "settings" / "__init__.py").write_text("")
    (package_dir / "settings" / "modules.py").write_text(
        "ORIGINAL_SETTINGS = ['auth']\n"
    )
    (package_dir / "urls_modules.py").write_text("ORIGINAL_URLS = ['auth']\n")
    managed_dir = package_dir / "quickscale_managed"
    managed_dir.mkdir()
    (managed_dir / "__init__.py").write_text("# original managed\n")
    (managed_dir / "social_views.py").write_text("ORIGINAL_MANAGED = True\n")

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
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-01-01T00:00:00",
                },
                "modules": {
                    "auth": {
                        "version": "0.71.0",
                        "commit_sha": "abc123",
                        "embedded_at": "2025-01-01T00:00:00",
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
                        "installed_at": "2025-01-01",
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


def _write_apply_recovery_state(project_path: Path, module_names: list[str]) -> None:
    quickscale_dir = project_path / ".quickscale"
    quickscale_dir.mkdir(exist_ok=True)
    (quickscale_dir / "apply-recovery.yml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "project": {
                    "slug": "myproject",
                    "package": "myproject",
                    "theme": "showcase_html",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-01-02T00:00:00",
                },
                "modules": {
                    module_name: {
                        "version": "0.71.0",
                        "commit_sha": "abc123",
                        "embedded_at": "2025-01-01T00:00:00",
                        "options": {},
                    }
                    for module_name in module_names
                },
            },
            sort_keys=False,
        )
    )


class TestRemoveHelpers:
    def test_directory_not_exists(self, tmp_path: Path) -> None:
        success, message = _remove_module_directory(tmp_path, "auth")
        assert success is True
        assert "not found" in message

    def test_directory_removed(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "models.py").touch()

        success, message = _remove_module_directory(tmp_path, "auth")

        assert success is True
        assert "Removed module directory" in message
        assert not module_dir.exists()

    def test_check_module_exists(self, tmp_path: Path) -> None:
        _write_valid_remove_project(tmp_path)

        state_manager = StateManager(tmp_path)
        in_state, in_fs, state = _check_module_exists(tmp_path, "auth", state_manager)

        assert in_state is True
        assert in_fs is True
        assert state is not None

    @patch("quickscale_cli.commands.remove_command.regenerate_managed_wiring")
    def test_regenerate_uses_remaining_modules_and_package(
        self,
        mock_regenerate,
        tmp_path: Path,
    ) -> None:
        mock_regenerate.return_value = (True, "ok")

        success, message = _regenerate_managed_wiring_after_removal(
            tmp_path,
            ["blog"],
            "myproject",
        )

        assert success is True
        assert "Regenerated" in message
        mock_regenerate.assert_called_once_with(
            tmp_path,
            module_names=["blog"],
            project_package="myproject",
        )


class TestRemoveTransactionalFailures:
    def test_preflight_abort_on_malformed_quickscale(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)
        (tmp_path / "quickscale.yml").write_text('version: "1"\nproject: [\n')

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "Failed to load quickscale.yml" in result.output
        assert (tmp_path / "modules" / "auth").exists()

        state = yaml.safe_load((tmp_path / ".quickscale" / "state.yml").read_text())
        assert "auth" in state.get("modules", {})

    def test_preflight_abort_on_malformed_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)
        (tmp_path / ".quickscale" / "state.yml").write_text("project: [\n")

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "Failed to load .quickscale/state.yml" in result.output
        assert (tmp_path / "modules" / "auth").exists()

        config = yaml.safe_load((tmp_path / "quickscale.yml").read_text())
        assert "auth" in config.get("modules", {})

    def test_regeneration_failure_rolls_back_all_mutations(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)
        _write_apply_recovery_state(tmp_path, ["auth", "blog"])

        package_dir = tmp_path / "myproject"
        original_settings = (package_dir / "settings" / "modules.py").read_text()
        original_urls = (package_dir / "urls_modules.py").read_text()
        original_managed = (
            package_dir / "quickscale_managed" / "social_views.py"
        ).read_text()
        original_apply_recovery = (
            tmp_path / ".quickscale" / "apply-recovery.yml"
        ).read_text()

        def _mutate_managed_outputs_then_fail(
            project_path: Path,
            *,
            module_names: list[str],
            project_package: str,
        ) -> tuple[bool, str]:
            del module_names, project_package
            package_dir = project_path / "myproject"
            (package_dir / "settings" / "modules.py").write_text("BROKEN_SETTINGS\n")
            (package_dir / "urls_modules.py").write_text("BROKEN_URLS\n")
            shutil.rmtree(package_dir / "quickscale_managed")
            return False, "boom"

        monkeypatch.chdir(tmp_path)
        with patch(
            "quickscale_cli.commands.remove_command.regenerate_managed_wiring",
            side_effect=_mutate_managed_outputs_then_fail,
        ):
            result = CliRunner().invoke(
                remove,
                ["auth", "--force"],
                catch_exceptions=False,
            )

        assert result.exit_code != 0
        assert "Remove failed" in result.output
        assert "removed successfully" not in result.output.lower()
        assert (tmp_path / "modules" / "auth").exists()

        config = yaml.safe_load((tmp_path / "quickscale.yml").read_text())
        assert "auth" in config.get("modules", {})

        state = yaml.safe_load((tmp_path / ".quickscale" / "state.yml").read_text())
        assert "auth" in state.get("modules", {})

        legacy_config = yaml.safe_load(
            (tmp_path / ".quickscale" / "config.yml").read_text()
        )
        assert "auth" in legacy_config.get("modules", {})
        assert (
            tmp_path / ".quickscale" / "apply-recovery.yml"
        ).read_text() == original_apply_recovery

        assert (
            package_dir / "settings" / "modules.py"
        ).read_text() == original_settings
        assert (package_dir / "urls_modules.py").read_text() == original_urls
        assert (
            package_dir / "quickscale_managed" / "social_views.py"
        ).read_text() == original_managed


class TestRemoveCommandIntegration:
    def test_remove_updates_pending_apply_recovery_snapshot(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)
        _write_apply_recovery_state(tmp_path, ["auth", "blog"])

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            remove,
            ["auth", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        recovery_state = yaml.safe_load(
            (tmp_path / ".quickscale" / "apply-recovery.yml").read_text()
        )
        assert set(recovery_state.get("modules", {})) == {"blog"}
        assert "auth" not in recovery_state.get("modules", {})

    def test_remove_does_not_materialize_future_desired_modules_during_regeneration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)

        config_path = tmp_path / "quickscale.yml"
        config = yaml.safe_load(config_path.read_text())
        config["modules"]["blog"] = {}
        config_path.write_text(yaml.safe_dump(config, sort_keys=False))

        recorded_call: dict[str, object] = {}

        def _record_regeneration(
            project_path: Path,
            *,
            module_names: list[str],
            project_package: str,
        ) -> tuple[bool, str]:
            recorded_call["project_path"] = project_path
            recorded_call["module_names"] = module_names
            recorded_call["project_package"] = project_package
            return True, "ok"

        monkeypatch.chdir(tmp_path)
        with patch(
            "quickscale_cli.commands.remove_command.regenerate_managed_wiring",
            side_effect=_record_regeneration,
        ):
            result = CliRunner().invoke(
                remove,
                ["auth", "--force"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert recorded_call == {
            "project_path": tmp_path,
            "module_names": [],
            "project_package": "myproject",
        }

        updated_config = yaml.safe_load(config_path.read_text())
        assert list(updated_config.get("modules", {}).keys()) == ["blog"]

        updated_state = yaml.safe_load(
            (tmp_path / ".quickscale" / "state.yml").read_text()
        )
        assert updated_state.get("modules", {}) == {}

    def test_remove_with_keep_data_success(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            remove,
            ["auth", "--force", "--keep-data"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "removed successfully" in result.output.lower()

    def test_remove_cancelled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_valid_remove_project(tmp_path)

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            remove,
            ["auth"],
            input="n\n",
            catch_exceptions=False,
        )

        assert result.exit_code != 0
        assert "cancelled" in result.output.lower()
