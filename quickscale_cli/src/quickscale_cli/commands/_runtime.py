"""Docker, migration, Poetry, env-example, and gitignore step adapters.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep
working.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import click


from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)

# AF6 Phase 2 — core step bodies
from quickscale_cli.commands._types import (
    ApplyContext,
    _UNSAFE_GITIGNORE_GLOB_CHARACTERS,
    _UNSAFE_GITIGNORE_LEADING_CHARACTERS,
)
import quickscale_cli.commands.apply_command as _apply_command


def _run_poetry_install(project_path: Path) -> bool:
    """Run poetry install in project"""
    return _apply_command._run_command(
        ["poetry", "install"],
        project_path,
        "Installing dependencies (poetry install)",
        env=_apply_command._isolated_poetry_env(),
    )[0]


def _run_poetry_lock(project_path: Path) -> bool:
    """Refresh the generated project's Poetry lockfile."""
    return _apply_command._run_command(
        ["poetry", "lock"],
        project_path,
        "Refreshing dependencies (poetry lock)",
        env=_apply_command._isolated_poetry_env(),
    )[0]


def _run_migrations(project_path: Path) -> bool:
    """Run Django migrations"""
    return _apply_command._run_command(
        ["poetry", "run", "python", "manage.py", "migrate"],
        project_path,
        "Running migrations",
        env=_apply_command._isolated_poetry_env(),
    )[0]


def _run_migrations_in_docker_impl(project_path: Path) -> bool:
    """Original implementation used as callback for core step body."""
    return _apply_command._run_command(
        [sys.executable, "-m", "quickscale_cli.main", "manage", "migrate"],
        project_path,
        "Running migrations (Docker)",
        env=_apply_command._build_quickscale_env(),
    )[0]


def _run_migrations_in_docker(project_path: Path) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    Used for Docker migration path exclusively.
    """
    step_ctx = _apply_command.StepContext(output_path=project_path)
    outcome = _apply_command.step_run_migrations(
        step_ctx,
        should_auto_start_docker=True,
        docker_started=True,
        run_migrations_in_docker_fn=_apply_command._run_migrations_in_docker_impl,
        should_run_local_migrations=False,
    )
    return outcome.success


def _run_local_migrations(project_path: Path) -> bool:
    """Run local database migrations (existing-project or ``--no-docker`` path).

    AF5 Phase 4: This helper is called from step 13 to execute local
    migrations that were previously handled in step 10.  Delegates to
    the core step body through the same migration step function used
    for Docker migrations.
    """
    step_ctx = _apply_command.StepContext(output_path=project_path)
    outcome = _apply_command.step_run_migrations(
        step_ctx,
        should_auto_start_docker=False,
        docker_started=False,
        run_migrations_in_docker_fn=_apply_command._run_migrations_in_docker_impl,
        should_run_local_migrations=True,
        run_local_migrations_fn=_apply_command._run_migrations,
    )
    return outcome.success


def _should_check_stale_volumes(ctx: "ApplyContext") -> bool:
    """Return whether this apply is provisioning a project's database anew.

    ``had_existing_state`` is True only when an authoritative
    ``.quickscale/state.yml`` was loaded, so it stays False for a resumed
    apply — which carries a recovery ledger in ``existing_state`` but is
    still a first-time provision, and is exactly the case that must not
    silently adopt an unrelated project's volumes.
    """
    return not ctx.had_existing_state


def _preflight_stale_docker_volumes(project_path: Path) -> bool:
    """Handle leftover Compose volumes before a new project starts Docker.

    Compose names volumes after the project directory, so a freshly generated
    project reuses any volume left behind by an earlier project of the same
    name.  The stale database still carries that project's migration history,
    and Django then aborts with ``InconsistentMigrationHistory`` — an error
    that says nothing about the real cause.  Detect it first and let the
    operator remove the leftovers (destructive, so never automatic).

    Returns:
        True when it is safe to continue, False when the operator declined
        and the apply should stop.
    """
    stale_volumes = _apply_command.find_stale_project_volumes(project_path)
    if not stale_volumes:
        return True

    click.echo("")
    click.secho(
        "⚠️  Leftover Docker volumes found for this project name",
        fg="yellow",
        bold=True,
    )
    for volume in stale_volumes:
        click.echo(f"  • {volume}")
    click.echo(
        "\nThis project was just generated, so these volumes belong to an "
        "earlier\nproject that used the same directory name.  Starting on top "
        "of that old\ndatabase makes migrations fail with "
        "'InconsistentMigrationHistory'."
    )

    if _apply_command._AF5_DESTRUCTIVE_CONFIRM_BYPASS:
        return True

    click.echo("")
    if not click.confirm(
        "Remove these volumes and start from a clean database?", default=True
    ):
        click.secho(
            "\n❌ Keeping the existing volumes. Docker startup would fail on "
            "the stale database.",
            fg="yellow",
        )
        click.echo(
            "💡 Remove them yourself and re-run 'quickscale apply':\n"
            f"   docker volume rm {' '.join(stale_volumes)}"
        )
        return False

    # Containers left over from the earlier project keep its volumes
    # attached; release them first so removal can succeed.
    _apply_command.compose_down(project_path)

    removed, failed = _apply_command.remove_volumes(stale_volumes)
    for volume in removed:
        click.secho(f"✅ Removed volume: {volume}", fg="green")
    if failed:
        click.secho(
            "❌ Could not remove: " + ", ".join(failed),
            fg="red",
            err=True,
        )
        click.echo(
            "💡 A volume still in use must be released first:\n"
            "   quickscale down  # or: docker compose down",
            err=True,
        )
        return False
    return True


def _start_docker_impl(
    project_path: Path, build: bool = True, verbose: bool = False
) -> bool:
    """Original implementation used as callback for core step body."""
    cmd = [sys.executable, "-m", "quickscale_cli.main", "up"]
    if build:
        cmd.append("--build")
    if verbose:
        click.echo("⏳ Starting Docker services (showing build output)...")
        click.echo("=" * 50)
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                cmd,
                cwd=project_path,
                text=True,
                check=False,
                env=_apply_command._build_quickscale_env(),
            )
            click.echo("=" * 50)
            if result.returncode == 0:
                click.secho("✅ Starting Docker services", fg="green")
                return True
            else:
                click.secho("❌ Starting Docker services failed", fg="red")
                return False
        except FileNotFoundError:
            click.secho(f"❌ Command not found: {cmd[0]}", fg="red", err=True)
            return False
        except Exception as e:
            click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
            return False
    else:
        success, _ = _apply_command._run_command(
            cmd,
            project_path,
            "Starting Docker services",
            capture=False,
            env=_apply_command._build_quickscale_env(),
        )
        return success


def _start_docker(
    project_path: Path, build: bool = True, verbose: bool = False
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _apply_command.StepContext(
        output_path=project_path, verbose_docker=verbose
    )
    outcome = _apply_command.step_start_docker(
        step_ctx,
        should_auto_start_docker=True,
        start_docker_fn=lambda p, q: _apply_command._start_docker_impl(
            p,
            build=build,
            verbose=verbose,
        ),
    )
    return outcome.success


def _sync_env_example_blocks_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Shared ``.env.example`` sync used by every env-example station.

    One declaration-driven renderer owns the managed blocks for every
    configured credential-bearing module, so notifications, analytics,
    billing, storage, and backups all project from the same declared option
    set.  The sync is idempotent, which is what lets the three legacy
    stations below invoke it: any apply resume point among them lands a
    complete contract.
    """
    result = _apply_command.sync_env_example_blocks(output_path, qs_config)
    if not result.success:
        click.secho(
            "⚠️  Failed to update .env.example with the configured module "
            f"env vars: {result.detail}",
            fg="yellow",
        )
        return False
    if result.changed:
        click.secho("✅ Updated .env.example with module env vars", fg="green")
    return True


def _sync_notifications_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _apply_command.StepContext(output_path=output_path, qs_config=qs_config)
    outcome = _apply_command.step_notifications_env_sync(
        step_ctx,
        sync_notifications_fn=_apply_command._sync_env_example_blocks_impl,
    )
    return outcome.success


def _sync_analytics_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _apply_command.StepContext(output_path=output_path, qs_config=qs_config)
    outcome = _apply_command.step_analytics_env_sync(
        step_ctx,
        sync_analytics_fn=_apply_command._sync_env_example_blocks_impl,
    )
    return outcome.success


def _sync_billing_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _apply_command.StepContext(output_path=output_path, qs_config=qs_config)
    outcome = _apply_command.step_billing_env_sync(
        step_ctx,
        sync_billing_fn=_apply_command._sync_env_example_blocks_impl,
    )
    return outcome.success


def _normalize_backups_gitignore_entry(local_directory: str) -> str | None:
    """Return a safe repo-relative ignore entry for backup artifacts."""
    if any(
        ord(character) < 32 or ord(character) == 127 for character in local_directory
    ):
        return None

    raw_candidate = local_directory.strip()
    windows_path = PureWindowsPath(raw_candidate)
    if windows_path.drive or windows_path.is_absolute():
        return None

    candidate = raw_candidate.replace("\\", "/")
    if not candidate or candidate in {".", "./", "/"}:
        return None
    if candidate.startswith("/") or candidate.startswith("~"):
        return None

    normalized = candidate
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or normalized.startswith("/"):
        return None

    path = PurePosixPath(normalized)
    if not path.parts or any(part == ".." for part in path.parts):
        return None

    resolved = path.as_posix()
    if resolved.startswith(tuple(_UNSAFE_GITIGNORE_LEADING_CHARACTERS)):
        return None
    if any(character in _UNSAFE_GITIGNORE_GLOB_CHARACTERS for character in resolved):
        return None
    if resolved in {".", ".quickscale"}:
        return None
    return resolved if resolved.endswith("/") else f"{resolved}/"


def _ensure_backups_gitignore_rules(
    project_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""

    def _impl(path: Path, config: QuickScaleConfig) -> bool:
        backups_config = config.modules.get("backups")
        if backups_config is None:
            return True
        options = _apply_command.resolve_manifest_module_options(
            "backups", backups_config.options or {}
        )
        local_directory = options["local_directory"]
        entry = _apply_command._normalize_backups_gitignore_entry(str(local_directory))
        if entry is None:
            click.secho(
                "⚠️  Skipping automatic backups .gitignore update because "
                "`modules.backups.local_directory` is not a safe repo-relative path.",
                fg="yellow",
            )
            return True
        gitignore_path = path / ".gitignore"
        try:
            existing = gitignore_path.read_text() if gitignore_path.exists() else ""
        except OSError as error:
            click.secho(
                f"❌ Failed to read .gitignore for backups hardening: {error}",
                fg="red",
                err=True,
            )
            return False
        existing_entries = {
            line.strip() for line in existing.splitlines() if line.strip()
        }
        if entry in existing_entries:
            return True
        new_content = existing
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        if "# QuickScale private backup artifacts" not in new_content:
            new_content += "\n# QuickScale private backup artifacts\n"
        new_content += f"{entry}\n"
        try:
            gitignore_path.write_text(new_content)
        except OSError as error:
            click.secho(
                f"❌ Failed to update .gitignore for backups hardening: {error}",
                fg="red",
                err=True,
            )
            return False
        click.secho(f"✅ Added backups ignore rule to .gitignore: {entry}", fg="green")
        return True

    step_ctx = _apply_command.StepContext(output_path=project_path, qs_config=qs_config)
    outcome = _apply_command.step_backups_gitignore(
        step_ctx, ensure_backups_ignore_fn=_impl
    )
    return outcome.success


def _run_post_generation_steps_impl(
    output_path: Path,
) -> bool:
    """Original implementation used as callback for core step body.

    AF5 Phase 4: No longer runs migrations.  Local migrations are deferred
    to step 13 (the late confirmable phase) together with Docker migrations,
    Railway deploy, and other destructive/remote operations.
    """
    if not _apply_command._run_poetry_lock(output_path):
        return False
    if not _apply_command._run_poetry_install(output_path):
        return False
    return True


def _run_post_generation_steps(output_path: Path) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    AF5 Phase 4: No longer passes ``run_migrations``.  Local migrations
    are deferred to step 13.
    """
    step_ctx = _apply_command.StepContext(output_path=output_path)
    outcome = _apply_command.step_post_generation_setup(
        step_ctx,
        run_post_gen_steps_fn=_apply_command._run_post_generation_steps_impl,
    )
    return outcome.success


def _sync_project_module_dependencies_for_apply_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Original implementation used as callback for core step body."""
    try:
        if _apply_command.sync_project_core_dependency(output_path):
            click.echo("  • Pinned quickscale-core to the local wheelhouse")
    except _apply_command.DependencySyncError as error:
        click.secho(f"❌ Core dependency sync failed: {error}", fg="red", err=True)
        return False
    if not qs_config.modules:
        return True
    click.echo("\n⏳ Syncing module dependency entries...")
    try:
        sync_result = _apply_command.sync_project_module_dependencies(
            output_path,
            {
                module_name: module_config.options or {}
                for module_name, module_config in qs_config.modules.items()
            },
        )
    except (_apply_command.DependencySyncError, _apply_command.ManifestError) as error:
        click.secho(f"❌ Module dependency sync failed: {error}", fg="red", err=True)
        return False
    if sync_result.added_package_dependencies:
        click.echo(
            "  • Added package dependencies: "
            + ", ".join(sync_result.added_package_dependencies)
        )
    if sync_result.added_path_dependencies:
        click.echo(
            "  • Added module path dependencies: "
            + ", ".join(sync_result.added_path_dependencies)
        )
    if not sync_result.changed:
        click.echo("  • Module dependency entries already in sync")
    click.secho("✅ Module dependency entries synced", fg="green")
    return True


def _sync_project_module_dependencies_for_apply(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _apply_command.StepContext(output_path=output_path, qs_config=qs_config)
    outcome = _apply_command.step_sync_dependencies(
        step_ctx,
        sync_project_deps_fn=_apply_command._sync_project_module_dependencies_for_apply_impl,
    )
    return outcome.success
