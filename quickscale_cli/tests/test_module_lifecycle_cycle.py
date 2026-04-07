"""Tests for module lifecycle cycle coverage."""

import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from quickscale_cli.commands.apply_command import EmbedModulesResult, apply  # type: ignore[import-untyped]
from quickscale_cli.commands.module_commands import push, update  # type: ignore[import-untyped]
from quickscale_cli.commands.remove_command import remove  # type: ignore[import-untyped]


def _write_quickscale_config(project_path: Path, include_auth: bool) -> None:
    """Write quickscale.yml with optional auth module"""
    modules_block = "  auth:\n" if include_auth else ""
    (project_path / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myproject",
                "  package: myproject",
                "  theme: showcase_html",
                "modules:",
                modules_block.rstrip("\n"),
                "docker:",
                "  start: false",
            ]
        )
        + "\n"
    )


def _write_quickscale_config_with_modules(
    project_path: Path,
    module_names: list[str],
) -> None:
    """Write quickscale.yml with an explicit module set."""
    config_data = {
        "version": "1",
        "project": {
            "slug": "myproject",
            "package": "myproject",
            "theme": "showcase_html",
        },
        "modules": {module_name: {} for module_name in module_names},
        "docker": {"start": False},
    }
    (project_path / "quickscale.yml").write_text(
        yaml.safe_dump(config_data, sort_keys=False)
    )


def _write_initial_state(project_path: Path) -> None:
    """Write .quickscale/state.yml with auth module installed"""
    state_data = {
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
                "name": "auth",
                "version": "0.71.0",
                "commit_sha": "abc123",
                "embedded_at": "2025-01-01T00:00:00",
                "options": {},
            }
        },
    }
    state_dir = project_path / ".quickscale"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.yml").write_text(yaml.safe_dump(state_data, sort_keys=False))


def _write_initial_state_with_modules(
    project_path: Path,
    module_names: list[str],
) -> None:
    """Write .quickscale/state.yml with the requested installed modules."""
    state_data = {
        "version": "1",
        "project": {
            "slug": "myproject",
            "package": "myproject",
            "theme": "showcase_html",
            "created_at": "2025-01-01T00:00:00",
            "last_applied": "2025-01-01T00:00:00",
        },
        "modules": {
            module_name: {
                "name": module_name,
                "version": "0.71.0",
                "commit_sha": "abc123",
                "embedded_at": "2025-01-01T00:00:00",
                "options": {},
            }
            for module_name in module_names
        },
    }
    state_dir = project_path / ".quickscale"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.yml").write_text(yaml.safe_dump(state_data, sort_keys=False))


def _write_initial_module_tracking(project_path: Path) -> None:
    """Write legacy .quickscale/config.yml tracking for installed modules."""
    config_data = {
        "default_remote": "https://github.com/Experto-AI/quickscale.git",
        "modules": {
            "auth": {
                "prefix": "modules/auth",
                "branch": "splits/auth-module",
                "installed_version": "0.71.0",
                "installed_at": "2025-01-01",
            }
        },
    }
    state_dir = project_path / ".quickscale"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "config.yml").write_text(yaml.safe_dump(config_data, sort_keys=False))


def _write_initial_module_tracking_with_modules(
    project_path: Path,
    module_names: list[str],
) -> None:
    """Write legacy .quickscale/config.yml for the requested installed modules."""
    config_data = {
        "default_remote": "https://github.com/Experto-AI/quickscale.git",
        "modules": {
            module_name: {
                "prefix": f"modules/{module_name}",
                "branch": f"splits/{module_name}-module",
                "installed_version": "0.71.0",
                "installed_at": "2025-01-01",
            }
            for module_name in module_names
        },
    }
    state_dir = project_path / ".quickscale"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "config.yml").write_text(yaml.safe_dump(config_data, sort_keys=False))


def _write_apply_recovery_state_with_modules(
    project_path: Path,
    module_names: list[str],
) -> None:
    """Write .quickscale/apply-recovery.yml for pending post-embed recovery."""
    recovery_data = {
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
                "name": module_name,
                "version": "0.71.0",
                "commit_sha": "abc123",
                "embedded_at": "2025-01-01T00:00:00",
                "options": {},
            }
            for module_name in module_names
        },
    }
    state_dir = project_path / ".quickscale"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "apply-recovery.yml").write_text(
        yaml.safe_dump(recovery_data, sort_keys=False)
    )


def _write_project_with_modules(project_path: Path, module_names: list[str]) -> None:
    """Write the minimal generated-project layout for remove/update/push tests."""
    project_path.mkdir()
    (project_path / "manage.py").write_text("# manage")

    for module_name in module_names:
        module_dir = project_path / "modules" / module_name
        module_dir.mkdir(parents=True)
        (module_dir / "__init__.py").write_text("")
        (module_dir / "module.yml").write_text(
            f'name: {module_name}\nversion: "0.71.0"\n'
        )

    _write_quickscale_config_with_modules(project_path, module_names)
    _write_initial_state_with_modules(project_path, module_names)
    _write_initial_module_tracking_with_modules(project_path, module_names)
    _write_managed_package_layout(project_path)


def _write_managed_package_layout(project_path: Path) -> None:
    """Write the minimal package files required for managed wiring regeneration."""
    package_dir = project_path / "myproject"
    (package_dir / "settings").mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "settings" / "__init__.py").write_text("")
    (package_dir / "settings" / "modules.py").write_text("MODULE_INSTALLED_APPS = []\n")
    (package_dir / "urls_modules.py").write_text("MODULE_URLPATTERNS = []\n")


def _write_backups_quickscale_config(
    base_path: Path,
    backups_options: dict[str, Any],
) -> None:
    """Write a quickscale.yml containing the backups module configuration."""
    config_data = {
        "version": "1",
        "project": {
            "slug": "myproject",
            "package": "myproject",
            "theme": "showcase_html",
        },
        "modules": {"backups": backups_options},
        "docker": {"start": False},
    }
    (base_path / "quickscale.yml").write_text(
        yaml.safe_dump(config_data, sort_keys=False)
    )


def _generate_minimal_project(
    qs_config: Any,
    output_path: Path,
    force: bool,
) -> None:
    """Create the smallest generated-project layout needed for apply tests."""
    del force
    output_path.mkdir(parents=True, exist_ok=True)
    package_dir = output_path / qs_config.project.package
    (package_dir / "settings").mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "urls.py").write_text("urlpatterns = []\n")
    (output_path / "manage.py").write_text("# manage\n")


def _embed_modules_into_project(
    output_path: Path,
    modules_to_embed: list[str],
    no_modules: bool,
    existing_state: Any,
) -> EmbedModulesResult:
    """Create embedded module directories without touching git subtrees."""
    del no_modules, existing_state
    for module_name in modules_to_embed:
        module_dir = output_path / "modules" / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "__init__.py").write_text("")
    return EmbedModulesResult(success=True, embedded_modules=modules_to_embed)


def test_lifecycle_create_apply_remove_readd_apply_e2e_expected_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test add/apply -> remove -> re-add/apply cycle preserves expected state"""
    project_path = tmp_path / "myproject"
    project_path.mkdir()

    modules_auth_dir = project_path / "modules" / "auth"
    modules_auth_dir.mkdir(parents=True)
    (modules_auth_dir / "__init__.py").write_text("")
    (project_path / "manage.py").write_text("# manage")

    _write_quickscale_config(project_path, include_auth=True)
    _write_initial_state(project_path)
    _write_initial_module_tracking(project_path)
    _write_managed_package_layout(project_path)

    cli_runner = CliRunner()
    monkeypatch.chdir(project_path)

    remove_result = cli_runner.invoke(
        remove, ["auth", "--force"], catch_exceptions=False
    )
    assert remove_result.exit_code == 0
    assert not modules_auth_dir.exists()

    config_after_remove = yaml.safe_load((project_path / "quickscale.yml").read_text())
    assert "auth" not in config_after_remove.get("modules", {})

    legacy_tracking_after_remove = yaml.safe_load(
        (project_path / ".quickscale" / "config.yml").read_text()
    )
    assert "auth" not in legacy_tracking_after_remove.get("modules", {})

    _write_quickscale_config(project_path, include_auth=True)

    def _embed_step(
        output_path: Path,
        modules_to_embed: list[str],
        no_modules: bool,
        existing_state: Any,
    ) -> EmbedModulesResult:
        for module_name in modules_to_embed:
            module_dir = output_path / "modules" / module_name
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "__init__.py").write_text("")
        return EmbedModulesResult(success=True, embedded_modules=modules_to_embed)

    with (
        patch(
            "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            return_value=None,
        ),
        patch(
            "quickscale_cli.commands.apply_command._embed_modules_step",
            side_effect=_embed_step,
        ) as mock_embed_modules_step,
        patch(
            "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.apply_command._run_post_generation_steps",
            return_value=True,
        ),
    ):
        apply_result = cli_runner.invoke(
            apply,
            ["quickscale.yml", "--no-docker"],
            input="y\n",
            catch_exceptions=False,
        )

    assert apply_result.exit_code == 0
    assert mock_embed_modules_step.call_count == 1
    called_modules = mock_embed_modules_step.call_args.args[1]
    assert called_modules == ["auth"]

    assert (project_path / "modules" / "auth").exists()
    state_after_readd = yaml.safe_load(
        (project_path / ".quickscale" / "state.yml").read_text()
    )
    assert "auth" in state_after_readd["modules"]


def test_remove_with_pending_recovery_then_apply_does_not_resurrect_removed_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove should clear stale recovery state so later apply only adds desired modules."""
    project_path = tmp_path / "myproject"
    _write_project_with_modules(project_path, ["auth"])
    _write_apply_recovery_state_with_modules(project_path, ["auth"])

    runner = CliRunner()
    monkeypatch.chdir(project_path)

    remove_result = runner.invoke(
        remove,
        ["auth", "--force"],
        catch_exceptions=False,
    )

    assert remove_result.exit_code == 0
    assert not (project_path / ".quickscale" / "apply-recovery.yml").exists()
    assert not (project_path / "modules" / "auth").exists()

    _write_quickscale_config_with_modules(project_path, ["blog"])

    def _embed_step(
        output_path: Path,
        modules_to_embed: list[str],
        no_modules: bool,
        existing_state: Any,
    ) -> EmbedModulesResult:
        del no_modules, existing_state
        for module_name in modules_to_embed:
            module_dir = output_path / "modules" / module_name
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "__init__.py").write_text("")
        return EmbedModulesResult(success=True, embedded_modules=modules_to_embed)

    with (
        patch(
            "quickscale_cli.commands.apply_command._commit_pending_config_changes",
            return_value=None,
        ),
        patch(
            "quickscale_cli.commands.apply_command._embed_modules_step",
            side_effect=_embed_step,
        ) as mock_embed_modules_step,
        patch(
            "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.apply_command._run_post_generation_steps",
            return_value=True,
        ),
    ):
        apply_result = runner.invoke(
            apply,
            ["quickscale.yml", "--no-docker"],
            input="y\n",
            catch_exceptions=False,
        )

    assert apply_result.exit_code == 0
    assert mock_embed_modules_step.call_count == 1
    assert mock_embed_modules_step.call_args.args[1] == ["blog"]
    assert (project_path / "modules" / "blog").exists()
    assert not (project_path / "modules" / "auth").exists()

    state_after_apply = yaml.safe_load(
        (project_path / ".quickscale" / "state.yml").read_text()
    )
    assert set(state_after_apply["modules"]) == {"blog"}
    assert "auth" not in state_after_apply["modules"]


def test_apply_backups_local_adds_private_gitignore_and_state() -> None:
    """Backups local mode should persist state and harden the generated project."""
    cli_runner = CliRunner()

    with cli_runner.isolated_filesystem():
        workspace = Path.cwd()
        _write_backups_quickscale_config(
            workspace,
            {
                "retention_days": 30,
                "naming_prefix": "ops",
                "target_mode": "local",
                "local_directory": ".private/backups",
                "automation_enabled": True,
                "schedule": "0 4 * * *",
            },
        )

        with (
            patch(
                "quickscale_cli.commands.apply_command._generate_new_project",
                side_effect=_generate_minimal_project,
            ),
            patch(
                "quickscale_cli.commands.apply_command._init_git_with_config",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                side_effect=_embed_modules_into_project,
            ) as mock_embed_modules_step,
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
        ):
            result = cli_runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker"],
                input="y\n",
                catch_exceptions=False,
            )

        project_path = workspace / "myproject"

        assert result.exit_code == 0
        assert mock_embed_modules_step.call_args.args[1] == ["backups"]
        assert (project_path / "modules" / "backups").exists()
        assert (
            "Added backups ignore rule to .gitignore: .private/backups/"
            in result.output
        )
        assert "poetry run python manage.py backups_create" in result.output
        assert "backups_restore --file /path/to/BACKUP_FILENAME.dump" in result.output
        assert "JSON artifacts are export-only" in result.output

        gitignore_text = (project_path / ".gitignore").read_text()
        assert "# QuickScale private backup artifacts" in gitignore_text
        assert ".private/backups/" in gitignore_text

        state = yaml.safe_load((project_path / ".quickscale" / "state.yml").read_text())
        backups_options = state["modules"]["backups"]["options"]
        assert backups_options["target_mode"] == "local"
        assert backups_options["local_directory"] == ".private/backups"
        assert backups_options["schedule"] == "0 4 * * *"


def test_apply_backups_private_remote_stays_offline_with_env_var_refs() -> None:
    """Private remote mode should stay offline and persist env-var references."""
    cli_runner = CliRunner()

    with cli_runner.isolated_filesystem():
        workspace = Path.cwd()
        _write_backups_quickscale_config(
            workspace,
            {
                "retention_days": 14,
                "naming_prefix": "db",
                "target_mode": "private_remote",
                "local_directory": ".quickscale/backups",
                "remote_bucket_name": "private-bucket",
                "remote_prefix": "ops/backups",
                "remote_endpoint_url": "https://account.r2.example.com",
                "remote_region_name": "auto",
                "remote_access_key_id_env_var": "OPS_BACKUPS_ACCESS_KEY_ID",
                "remote_secret_access_key_env_var": "OPS_BACKUPS_SECRET_ACCESS_KEY",
                "automation_enabled": True,
                "schedule": "0 2 * * *",
            },
        )

        with (
            patch(
                "quickscale_cli.commands.apply_command._generate_new_project",
                side_effect=_generate_minimal_project,
            ),
            patch(
                "quickscale_cli.commands.apply_command._init_git_with_config",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.apply_command._embed_modules_step",
                side_effect=_embed_modules_into_project,
            ) as mock_embed_modules_step,
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
        ):
            result = cli_runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker"],
                input="y\n",
                catch_exceptions=False,
            )

        project_path = workspace / "myproject"
        state_text = (project_path / ".quickscale" / "state.yml").read_text()

        assert result.exit_code == 0
        assert mock_embed_modules_step.call_args.args[1] == ["backups"]
        assert (project_path / "modules" / "backups").exists()
        assert "OPS_BACKUPS_ACCESS_KEY_ID" in result.output
        assert "OPS_BACKUPS_SECRET_ACCESS_KEY" in result.output
        assert "Configure runtime credentials via env vars" in result.output
        assert "backups_restore --file /path/to/BACKUP_FILENAME.dump" in result.output
        assert "Freshly generated Docker and GitHub CI files" in result.output

        gitignore_text = (project_path / ".gitignore").read_text()
        assert ".quickscale/backups/" in gitignore_text
        assert "\n.quickscale/\n" not in f"\n{gitignore_text}"

        assert "remote_access_key_id_env_var: OPS_BACKUPS_ACCESS_KEY_ID" in state_text
        assert (
            "remote_secret_access_key_env_var: OPS_BACKUPS_SECRET_ACCESS_KEY"
            in state_text
        )
        assert "remote_access_key_id:" not in state_text
        assert "remote_secret_access_key:" not in state_text

        state = yaml.safe_load(state_text)
        backups_options = state["modules"]["backups"]["options"]
        assert backups_options["remote_bucket_name"] == "private-bucket"
        assert (
            backups_options["remote_endpoint_url"] == "https://account.r2.example.com"
        )
        assert backups_options["remote_region_name"] == "auto"


def test_apply_embed_failure_after_subtree_add_preserves_prior_modules_and_allows_rerun() -> (
    None
):
    """Apply-mode subtree failures should not leave stale module state blocking retry."""
    cli_runner = CliRunner()

    with cli_runner.isolated_filesystem():
        workspace = Path.cwd()
        _write_quickscale_config_with_modules(workspace, ["auth", "blog"])

        def _fake_subtree_add(
            *,
            prefix: str,
            remote: str,
            branch: str,
            squash: bool,
        ) -> None:
            del remote, branch, squash
            module_name = Path(prefix).name
            module_dir = project_path / prefix
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "__init__.py").write_text("")
            (module_dir / "module.yml").write_text(
                f'name: {module_name}\nversion: "0.82.0"\n'
            )

        def _failing_blog_applier(
            project_path_arg: Path,
            config: dict[str, object],
            *,
            execution_mode: str,
        ) -> None:
            del project_path_arg, config
            raise RuntimeError(f"{execution_mode} blog failure")

        project_path = workspace / "myproject"

        with (
            patch(
                "quickscale_cli.commands.apply_command._generate_new_project",
                side_effect=_generate_minimal_project,
            ),
            patch(
                "quickscale_cli.commands.apply_command._init_git_with_config",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.apply_command._git_commit",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command.is_working_directory_clean",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_git_environment",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_remote_branch",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_add",
                side_effect=_fake_subtree_add,
            ),
            patch.dict(
                "quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS",
                {
                    "auth": (Mock(return_value={}), Mock()),
                    "blog": (
                        Mock(return_value={"enabled": True}),
                        _failing_blog_applier,
                    ),
                },
                clear=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
        ):
            first_result = cli_runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker"],
                input="y\n",
                catch_exceptions=False,
            )

        assert first_result.exit_code != 0
        assert (project_path / "modules" / "auth").exists()
        assert not (project_path / "modules" / "blog").exists()

        first_state = yaml.safe_load(
            (project_path / ".quickscale" / "state.yml").read_text()
        )
        first_legacy_config = yaml.safe_load(
            (project_path / ".quickscale" / "config.yml").read_text()
        )

        assert set(first_state["modules"]) == {"auth"}
        assert set(first_legacy_config["modules"]) == {"auth"}

        with (
            patch(
                "quickscale_cli.commands.apply_command._commit_pending_config_changes",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.apply_command._git_commit",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command.is_working_directory_clean",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_git_environment",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands._validate_remote_branch",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_add",
                side_effect=_fake_subtree_add,
            ),
            patch.dict(
                "quickscale_cli.commands.module_commands.MODULE_CONFIGURATORS",
                {
                    "auth": (Mock(return_value={}), Mock()),
                    "blog": (Mock(return_value={"enabled": True}), Mock()),
                },
                clear=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._regenerate_managed_wiring_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._sync_project_module_dependencies_for_apply",
                return_value=True,
            ),
            patch(
                "quickscale_cli.commands.apply_command._run_post_generation_steps",
                return_value=True,
            ),
        ):
            rerun_result = cli_runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker"],
                input="y\n",
                catch_exceptions=False,
            )

        assert rerun_result.exit_code == 0
        assert (project_path / "modules" / "blog").exists()

        final_state = yaml.safe_load(
            (project_path / ".quickscale" / "state.yml").read_text()
        )
        final_legacy_config = yaml.safe_load(
            (project_path / ".quickscale" / "config.yml").read_text()
        )

        assert set(final_state["modules"]) == {"auth", "blog"}
        assert set(final_legacy_config["modules"]) == {"auth", "blog"}


def test_update_after_successful_remove_only_targets_remaining_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update should only process modules left in legacy tracking after remove."""
    project_path = tmp_path / "myproject"
    _write_project_with_modules(project_path, ["auth", "blog"])

    runner = CliRunner()
    monkeypatch.chdir(project_path)

    remove_result = runner.invoke(
        remove,
        ["auth", "--force"],
        catch_exceptions=False,
    )

    assert remove_result.exit_code == 0
    legacy_tracking = yaml.safe_load(
        (project_path / ".quickscale" / "config.yml").read_text()
    )
    assert set(legacy_tracking.get("modules", {})) == {"blog"}

    with (
        patch(
            "quickscale_cli.commands.module_commands._validate_update_environment",
            return_value=None,
        ),
        patch(
            "quickscale_cli.commands.module_commands.click.confirm",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.module_commands._update_single_module",
            return_value=True,
        ) as mock_update_single_module,
    ):
        result = runner.invoke(update, ["--no-preview"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_update_single_module.assert_called_once()
    module_name, module_info, remote, no_preview = (
        mock_update_single_module.call_args.args
    )
    assert module_name == "blog"
    assert module_info.prefix == "modules/blog"
    assert module_info.branch == "splits/blog-module"
    assert remote == "https://github.com/Experto-AI/quickscale.git"
    assert no_preview is True


def test_push_after_successful_remove_treats_removed_module_as_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Push should reject removed modules while still allowing remaining ones."""
    project_path = tmp_path / "myproject"
    _write_project_with_modules(project_path, ["auth", "blog"])

    runner = CliRunner()
    monkeypatch.chdir(project_path)

    remove_result = runner.invoke(
        remove,
        ["auth", "--force"],
        catch_exceptions=False,
    )

    assert remove_result.exit_code == 0

    with (
        patch("quickscale_cli.commands.module_commands.is_git_repo", return_value=True),
        patch(
            "quickscale_cli.commands.module_commands.click.confirm",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.module_commands.run_git_subtree_push"
        ) as mock_push,
    ):
        remaining_result = runner.invoke(
            push,
            ["--module", "blog"],
            catch_exceptions=False,
        )

        assert remaining_result.exit_code == 0
        mock_push.assert_called_once_with(
            prefix="modules/blog",
            remote="https://github.com/Experto-AI/quickscale.git",
            branch="feature/blog-improvements",
        )

        mock_push.reset_mock()
        removed_result = runner.invoke(
            push,
            ["--module", "auth"],
            catch_exceptions=False,
        )

    assert removed_result.exit_code != 0
    assert "not installed" in removed_result.output.lower()
    mock_push.assert_not_called()


@pytest.mark.e2e
def test_update_auto_commits_each_module_e2e(tmp_path: Path) -> None:
    """Test update creates one git commit per successful module update"""
    project_path = tmp_path / "update-e2e"
    project_path.mkdir()

    subprocess.run(["git", "init"], cwd=project_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "QuickScale Test"],
        cwd=project_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@quickscale.dev"],
        cwd=project_path,
        check=True,
    )

    module_names = ["auth", "listings"]
    for module_name in module_names:
        module_dir = project_path / "modules" / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "README.md").write_text(f"{module_name} baseline\n")
        (module_dir / "module.yml").write_text(
            f'name: {module_name}\nversion: "0.1.0"\n'
        )

    subprocess.run(["git", "add", "."], cwd=project_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: baseline"],
        cwd=project_path,
        check=True,
    )

    baseline_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=project_path,
        check=True,
        capture_output=True,
        text=True,
    )

    auth_info = Mock(
        prefix="modules/auth",
        branch="splits/auth-module",
        installed_version="v0.1.0",
    )
    listings_info = Mock(
        prefix="modules/listings",
        branch="splits/listings-module",
        installed_version="v0.1.0",
    )
    config = Mock(
        modules={"auth": auth_info, "listings": listings_info},
        default_remote="https://github.com/Experto-AI/quickscale.git",
    )

    def _fake_subtree_pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        touched_file = project_path / prefix / "README.md"
        current = touched_file.read_text()
        touched_file.write_text(current + "updated\n")
        return "updated"

    runner = CliRunner()
    original_cwd = Path.cwd()
    try:
        os.chdir(project_path)
        with (
            patch(
                "quickscale_cli.commands.module_commands.load_config",
                return_value=config,
            ),
            patch(
                "quickscale_cli.commands.module_commands.run_git_subtree_pull",
                side_effect=_fake_subtree_pull,
            ),
            patch(
                "quickscale_cli.commands.module_commands.update_module_version",
                return_value=None,
            ),
            patch(
                "quickscale_cli.commands.module_commands.click.confirm",
                return_value=True,
            ),
        ):
            result = runner.invoke(update, ["--no-preview"], catch_exceptions=False)
    finally:
        os.chdir(original_cwd)

    assert result.exit_code == 0

    log_result = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project_path,
        check=True,
        capture_output=True,
        text=True,
    )
    final_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=project_path,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_messages = log_result.stdout.splitlines()
    assert "chore(modules): update auth module" in commit_messages
    assert "chore(modules): update listings module" in commit_messages
    assert int(final_count.stdout.strip()) == int(baseline_count.stdout.strip()) + 2
