"""Apply command for executing project configuration

Implements `quickscale apply [config]` - executes quickscale.yml configuration
"""

import copy
import os
import subprocess
import sys
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

import click
import yaml

from quickscale_core.contracts.module_options import (
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    DEFAULT_BILLING_CURRENCY,
    DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
    DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
    DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    normalize_backups_module_options,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    sanitize_module_options,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.resolvers import (
    resolve_analytics_module_options,
    validate_analytics_module_options,
    resolve_billing_module_options,
    validate_billing_module_options,
    validate_blog_module_options,
    validate_crm_module_options,
    validate_forms_module_options,
    validate_orgs_module_options,
    validate_storage_module_options,
    notifications_live_delivery_configured,
    notifications_production_targeted,
    resolve_notifications_module_options,
    validate_notifications_module_options,
    validate_social_module_options,
)
from quickscale_core.contracts.module_catalog import (
    find_not_ready_modules,
    get_module_readiness_reason,
)
from quickscale_core.manifest.implications import resolve_module_implications

from quickscale_cli.commands.apply_support import (
    _build_quickscale_env,
    _confirm_apply,
    _report_theme_preflight_error,
)
from quickscale_cli.commands.apply_support import _resolve_apply_raw_root  # noqa: F401
from quickscale_cli.commands.module_commands import embed_module, ModuleEmbedProvenance
from quickscale_cli.commands.module_config import (
    APPLY_MODULE_EXECUTION_MODE,
    get_default_backups_config,
    validate_backups_module_options,
)
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError,
    sync_project_module_dependencies,
)
from quickscale_cli.utils.module_wiring_manager import regenerate_managed_wiring
from quickscale_cli.utils.railway_utils import (
    deploy_railway_service,
    get_app_service_name,
)
from quickscale_core.schema.config_schema import (
    ConfigValidationError,
    ModuleConfig,
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_core.schema.delta import ConfigDelta, compute_delta, format_delta
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)
from quickscale_core import __version__ as quickscale_version
from quickscale_core.config import (
    normalize_installed_version,
)
from quickscale_core.apply import (
    APPLY_STEPS,
    ApplyExecutor,
    ApplyStep,
    LedgerError,
    LedgerManager,
    RecoveryLedger,
)
from quickscale_core.advisory_lock import (
    AdvisoryLock,
    AdvisoryLockContentionError,
)
from quickscale_core.project_state import (
    ConfigError,
    DEFAULT_MANAGED_WIRING_PATHS,
    ProjectStateManager,
    VersionDriftWarning,
    check_version_drift,
    compute_file_hashes,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError,
    validate_theme_preflight,
)
from quickscale_core.utils.git_utils import (
    GitError,
    is_working_directory_clean,
    resolve_remote_ref,
    validate_module_name,
    validate_tag_name,
)
from quickscale_core.generator import ProjectGenerator
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module
from quickscale_core.manifest.required_modules import (
    check_required_module_versions,
)

# AF6 Phase 2 — core step bodies
from quickscale_core.apply.steps import (
    GitIndexSnapshot,
    step_apply_mutable_config,
    step_backups_gitignore,
    step_capture_hashes,
    step_display_next_steps,
    step_embed_modules,
    step_finalize_state,
    step_notifications_env_sync,
    step_analytics_env_sync,
    step_billing_env_sync,
    step_post_embed_snapshot,
    step_post_generation_setup,
    step_railway_deploy,
    step_regenerate_wiring,
    step_run_migrations,
    step_start_docker,
    step_sync_dependencies,
)
from quickscale_core.apply.steps.types import StepContext, StepOutcome


@dataclass
class ApplyContext:
    """Context object for the apply command execution."""

    config_path: Path
    qs_config: QuickScaleConfig
    output_path: Path
    state_manager: StateManager
    existing_state: QuickScaleState | None
    manifests: dict[str, ModuleManifest]
    delta: ConfigDelta
    has_pending_post_embed_recovery: bool = False
    had_existing_state: bool = False


@dataclass
class EmbedModulesResult:
    """Result for module embedding step."""

    success: bool
    embedded_modules: list[str]
    failed_module: str | None = None
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None


@dataclass(frozen=True)
class _GitIndexTreeSnapshot:
    """Captured git index tree used to restore apply-owned staging."""

    tree_id: str


_UNSAFE_GITIGNORE_LEADING_CHARACTERS = frozenset({"!", "#"})
_UNSAFE_GITIGNORE_GLOB_CHARACTERS = frozenset({"*", "?", "["})
_APPLY_RECOVERY_FILENAME = "apply-recovery.yml"
_APPLY_RECOVERY_STEM = PurePosixPath(_APPLY_RECOVERY_FILENAME).stem

#: Test-support flag: when ``True``, the late destructive/remote
#: confirmation gate is silently bypassed.  Set by tests to avoid
#: interactive prompts during ``_execute_apply_steps_locked`` without
#: patching ``click.confirm``.
_AF5_DESTRUCTIVE_CONFIRM_BYPASS: bool = False

_PRE_EMBED_AUTHORITATIVE_GIT_PATHS = (
    "quickscale.yml",
    ".quickscale/state.yml",
    ".quickscale/config.yml",
)

#: Registry-backed failed-step labels (sourced from quickscale_core.apply).
#: Kept byte-identical to the former ad-hoc literals so that operator-visible
#: failure-summary text and recovery sentinels remain stable.
_FAILED_STEP = {
    step.step_id: step.failed_step_label
    for step in APPLY_STEPS
    if step.failed_step_label is not None
}


def _is_pre_embed_authoritative_path(path: str) -> bool:
    """Return whether a path belongs to authoritative QuickScale config state."""
    return path in _PRE_EMBED_AUTHORITATIVE_GIT_PATHS


def _is_transient_apply_recovery_path(path: str) -> bool:
    """Return whether a path is a transient apply-recovery artifact."""
    relative_path = PurePosixPath(path)
    return relative_path.parent == PurePosixPath(
        ".quickscale"
    ) and relative_path.name.startswith(_APPLY_RECOVERY_STEM)


def _is_pre_embed_allowed_dirty_path(path: str) -> bool:
    """Return whether a dirty path is apply-owned and safe to ignore or checkpoint."""
    return _is_pre_embed_authoritative_path(path) or _is_transient_apply_recovery_path(
        path
    )


def _get_pre_embed_checkpoint_paths(paths: list[str]) -> list[str]:
    """Return authoritative paths that belong in the synthetic pre-embed commit."""
    path_set = set(paths)
    return [path for path in _PRE_EMBED_AUTHORITATIVE_GIT_PATHS if path in path_set]


def _capture_git_index_snapshot(project_path: Path) -> _GitIndexTreeSnapshot | None:
    """Capture the current git index tree for later index-only restoration."""
    try:
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        click.secho(
            f"❌ Failed to snapshot git index before apply checkpoint: {error}",
            fg="red",
            err=True,
        )
        return None
    if result.returncode != 0:
        click.secho(
            "❌ Failed to snapshot git index before apply checkpoint.",
            fg="red",
            err=True,
        )
        if result.stderr:
            click.echo(result.stderr.strip(), err=True)
        return None

    tree_id = result.stdout.strip()
    if not tree_id:
        click.secho(
            "❌ Failed to snapshot git index before apply checkpoint: git write-tree returned no tree id.",
            fg="red",
            err=True,
        )
        return None

    return _GitIndexTreeSnapshot(tree_id=tree_id)


def _restore_git_index_snapshot(
    project_path: Path,
    snapshot: _GitIndexTreeSnapshot,
) -> bool:
    """Restore the git index snapshot after an apply-owned checkpoint failure."""
    try:
        result = subprocess.run(
            ["git", "read-tree", "--reset", snapshot.tree_id],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        click.secho(
            f"❌ Failed to restore git index after apply checkpoint failure: {error}",
            fg="red",
            err=True,
        )
        return False
    if result.returncode == 0:
        return True

    click.secho(
        "❌ Failed to restore git index after apply checkpoint failure.",
        fg="red",
        err=True,
    )
    if result.stderr:
        click.echo(result.stderr.strip(), err=True)
    return False


def _restore_failed_apply_checkpoint(
    project_path: Path,
    snapshot: _GitIndexTreeSnapshot,
) -> None:
    """Best-effort index restore for failed apply-owned checkpoint commands."""
    if _restore_git_index_snapshot(project_path, snapshot):
        return

    click.secho(
        "❌ QuickScale could not restore the git index after the failed apply checkpoint.",
        fg="red",
        err=True,
    )


def _stage_and_commit_with_index_restore(
    project_path: Path,
    *,
    stage_cmd: list[str],
    stage_description: str,
    commit_cmd: list[str],
    commit_description: str,
) -> bool:
    """Run an apply-owned stage/commit pair and restore the prior index on failure."""
    snapshot = _capture_git_index_snapshot(project_path)
    if snapshot is None:
        return False

    staged, _ = _run_command(stage_cmd, project_path, stage_description)
    if not staged:
        _restore_failed_apply_checkpoint(project_path, snapshot)
        return False

    committed, _ = _run_command(commit_cmd, project_path, commit_description)
    if committed:
        return True

    _restore_failed_apply_checkpoint(project_path, snapshot)
    return False


def _run_command(
    cmd: list[str],
    cwd: Path,
    description: str,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a shell command with progress output

    Args:
        cmd: Command and arguments
        cwd: Working directory
        description: Description for progress output
        capture: Whether to capture output
        env: Optional environment dict for the subprocess.
            When ``None`` (default), the subprocess inherits the parent's
            environment (``os.environ``).

    Returns:
        Tuple of (success, output)

    """
    click.echo(f"⏳ {description}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
            env=env,
        )
        if result.returncode == 0:
            click.secho(f"✅ {description}", fg="green")
            return True, result.stdout if capture else ""
        else:
            click.secho(f"❌ {description} failed", fg="red")
            if capture and result.stderr:
                click.echo(result.stderr, err=True)
            return False, result.stderr if capture else ""
    except FileNotFoundError as e:
        click.secho(f"❌ Command not found: {cmd[0]}", fg="red", err=True)
        return False, str(e)
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        return False, str(e)


def _generate_project(config: QuickScaleConfig, output_path: Path) -> bool:
    """Generate project using ProjectGenerator

    Fresh-generation only. ``selected_modules`` is forwarded from
    ``config.modules.keys()`` so the React theme gating sees the same module
    selection the user declared in ``quickscale.yml``. Existing-project apply
    paths do not call this function, so the legacy ``selected_modules=None``
    behavior of :class:`ProjectGenerator` remains reachable for them.
    """
    try:
        click.echo(
            f"⏳ Generating project: {config.project.slug} "
            f"(package: {config.project.package})..."
        )

        generator = ProjectGenerator(
            theme=config.project.theme,
            selected_modules=list(config.modules.keys()),
        )
        # mypy can resolve an older installed quickscale-core signature here.
        generate_project = cast(Any, generator.generate)
        generate_project(
            config.project.slug,
            output_path,
            package_name=config.project.package,
        )

        click.secho(f"✅ Project generated: {output_path}", fg="green")
        return True
    except FileExistsError:
        click.secho(
            f"❌ Directory already exists: {output_path}",
            fg="red",
            err=True,
        )
        click.echo("   Use --force to overwrite or choose a different name", err=True)
        return False
    except ValueError as e:
        click.secho(f"❌ Invalid project configuration: {e}", fg="red", err=True)
        return False
    except Exception as e:
        click.secho(f"❌ Failed to generate project: {e}", fg="red", err=True)
        return False


def _init_git(project_path: Path) -> bool:
    """Initialize git repository"""
    success, _ = _run_command(
        ["git", "init"],
        project_path,
        "Initializing git repository",
    )
    return success


def _git_commit(project_path: Path, message: str) -> bool:
    """Create a git commit"""
    return _stage_and_commit_with_index_restore(
        project_path,
        stage_cmd=["git", "add", "-A"],
        stage_description=f"Staging files for: {message}",
        commit_cmd=["git", "commit", "-m", message],
        commit_description=f"Committing: {message}",
    )


def _parse_split_ref_overrides(split_refs: tuple[str, ...]) -> dict[str, str]:
    """Parse repeatable ``MODULE=REF`` values without lossy normalization."""
    parsed: dict[str, str] = {}
    seen_modules: set[str] = set()
    for raw_value in split_refs:
        module_name, separator, split_ref = raw_value.partition("=")
        if not separator:
            raise click.BadParameter(
                f"invalid --split-ref value {raw_value!r}: expected MODULE=REF",
                param_hint="--split-ref",
            )
        try:
            validate_module_name(module_name)
            validate_tag_name(split_ref)
        except GitError as error:
            raise click.BadParameter(
                f"invalid --split-ref value {raw_value!r}: {error}",
                param_hint="--split-ref",
            ) from error
        if module_name in seen_modules:
            raise click.BadParameter(
                f"duplicate module {module_name!r} in --split-ref value {raw_value!r}",
                param_hint="--split-ref",
            )
        seen_modules.add(module_name)
        parsed[module_name] = split_ref
    return parsed


def _module_names_to_embed(ctx: ApplyContext) -> set[str]:
    """Return the exact module target set for this apply pass."""
    if ctx.existing_state is None:
        return set(ctx.qs_config.modules.keys())
    return set(ctx.delta.modules_to_add)


def _validate_split_ref_override_coverage(
    ctx: ApplyContext,
    split_ref_overrides: Mapping[str, str] | None,
    *,
    no_modules: bool,
) -> None:
    """Require explicit overrides to cover exactly the modules being added."""
    overrides = split_ref_overrides or {}
    if not overrides:
        return
    if no_modules:
        raise click.UsageError("--split-ref cannot be combined with --no-modules")

    target_modules = _module_names_to_embed(ctx)
    if not target_modules:
        raise click.UsageError(
            "--split-ref cannot be used when this apply has no modules to embed"
        )

    unknown = sorted(set(overrides) - target_modules)
    missing = sorted(target_modules - set(overrides))
    if unknown or missing:
        details: list[str] = []
        if unknown:
            details.append("unknown modules: " + ", ".join(unknown))
        if missing:
            details.append("missing modules: " + ", ".join(missing))
        raise click.UsageError(
            "--split-ref mappings must cover exactly the modules being embedded ("
            + "; ".join(details)
            + ")"
        )


def _embed_module(
    project_path: Path,
    module_name: str,
    skip_auth_migration_check: bool = False,
    provenance_sink: list[ModuleEmbedProvenance] | None = None,
    split_ref: str | None = None,
) -> bool:
    """Embed a module using the embed_module function with non-interactive mode"""
    click.echo(f"⏳ Embedding module: {module_name}...")

    try:
        embed_kwargs: dict[str, Any] = {
            "module": module_name,
            "project_path": project_path,
            "non_interactive": True,
            "allow_unverifiable_auth_state": True,
            "skip_auth_migration_check": skip_auth_migration_check,
            "sync_dependencies": False,
            "install_dependencies": False,
            "execution_mode": APPLY_MODULE_EXECUTION_MODE,
            "provenance_sink": provenance_sink,
        }
        if split_ref is not None:
            embed_kwargs["split_ref"] = split_ref
        success = embed_module(
            **embed_kwargs,
        )

        if success:
            click.secho(f"✅ Module embedded: {module_name}", fg="green")
            return True
        else:
            click.secho(f"❌ Failed to embed module: {module_name}", fg="red", err=True)
            return False
    except Exception as e:
        click.secho(f"❌ Unexpected error embedding module: {e}", fg="red", err=True)
        return False


def _isolated_poetry_env() -> dict[str, str]:
    """Build a subprocess environment that keeps Poetry off an ambient venv.

    Poetry treats an active ``VIRTUAL_ENV`` as taking precedence over its own
    per-project virtualenv resolution. If the caller's shell has a venv
    activated (e.g. a developer running the CLI/tests from within the main
    repo's venv), an unmodified ``poetry install``/``poetry lock`` for a
    generated project installs straight into that unrelated venv instead of
    one scoped to the generated project.
    """
    env = os.environ.copy()
    venv_path = env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
    if venv_path:
        venv_bin = str(Path(venv_path) / "bin")
        env["PATH"] = os.pathsep.join(
            p for p in env.get("PATH", "").split(os.pathsep) if p != venv_bin
        )
    env["POETRY_VIRTUALENVS_IN_PROJECT"] = "true"
    return env


def _run_poetry_install(project_path: Path) -> bool:
    """Run poetry install in project"""
    return _run_command(
        ["poetry", "install"],
        project_path,
        "Installing dependencies (poetry install)",
        env=_isolated_poetry_env(),
    )[0]


def _run_poetry_lock(project_path: Path) -> bool:
    """Refresh the generated project's Poetry lockfile."""
    return _run_command(
        ["poetry", "lock"],
        project_path,
        "Refreshing dependencies (poetry lock)",
        env=_isolated_poetry_env(),
    )[0]


def _run_migrations(project_path: Path) -> bool:
    """Run Django migrations"""
    return _run_command(
        ["poetry", "run", "python", "manage.py", "migrate"],
        project_path,
        "Running migrations",
    )[0]


def _run_migrations_in_docker_impl(project_path: Path) -> bool:
    """Original implementation used as callback for core step body."""
    return _run_command(
        [sys.executable, "-m", "quickscale_cli.main", "manage", "migrate"],
        project_path,
        "Running migrations (Docker)",
        env=_build_quickscale_env(),
    )[0]


def _run_migrations_in_docker(project_path: Path) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    Used for Docker migration path exclusively.
    """
    step_ctx = StepContext(output_path=project_path)
    outcome = step_run_migrations(
        step_ctx,
        should_auto_start_docker=True,
        docker_started=True,
        run_migrations_in_docker_fn=_run_migrations_in_docker_impl,
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
    step_ctx = StepContext(output_path=project_path)
    outcome = step_run_migrations(
        step_ctx,
        should_auto_start_docker=False,
        docker_started=False,
        run_migrations_in_docker_fn=_run_migrations_in_docker_impl,
        should_run_local_migrations=True,
        run_local_migrations_fn=_run_migrations,
    )
    return outcome.success


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
            result = subprocess.run(
                cmd,
                cwd=project_path,
                text=True,
                check=False,
                env=_build_quickscale_env(),
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
        success, _ = _run_command(
            cmd,
            project_path,
            "Starting Docker services",
            capture=False,
            env=_build_quickscale_env(),
        )
        return success


def _start_docker(
    project_path: Path, build: bool = True, verbose: bool = False
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = StepContext(output_path=project_path, verbose_docker=verbose)
    outcome = step_start_docker(
        step_ctx,
        should_auto_start_docker=True,
        start_docker_fn=lambda p, q: _start_docker_impl(
            p,
            build=build,
            verbose=verbose,
        ),
    )
    return outcome.success


def _abort_for_not_ready_modules(module_names: list[str], *, source: str) -> None:
    """Abort apply when non-public-ready modules appear in config or applied state."""
    not_ready = find_not_ready_modules(module_names)
    if not not_ready:
        return

    click.secho(
        f"\n❌ {source} references modules that are not public-ready:",
        fg="red",
        err=True,
        bold=True,
    )
    for module_name in not_ready:
        reason = get_module_readiness_reason(module_name)
        if reason is not None:
            click.echo(f"  • {reason}", err=True)

    click.echo(
        "\n💡 Remove these modules from quickscale.yml or the unsupported project "
        "state before running 'quickscale apply'.",
        err=True,
    )
    raise click.Abort()


def _abort_for_manifest_error(error: ManifestError, *, command_name: str) -> None:
    """Abort apply/status with an actionable manifest validation message."""
    click.secho(
        f"\n❌ Installed module manifest error during '{command_name}':",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo(f"  • {error}", err=True)
    click.echo(
        "\n💡 Fix the embedded module.yml or remove and re-embed the affected "
        f"module before running 'quickscale {command_name}' again.",
        err=True,
    )
    raise click.Abort()


def _validate_required_module_versions(
    manifests: dict[str, ModuleManifest],
) -> None:
    """Validate required-module version constraints and abort on violation.

    Delegates to :func:`check_required_module_versions` and maps
    the raised :class:`ManifestError` to the existing abort pattern.
    """
    # SA7.4: version-floor check applies only when we have manifests
    # for installed modules to cross-reference.
    if not manifests:
        return
    try:
        check_required_module_versions(manifests)
    except ManifestError as error:
        _abort_for_manifest_error(error, command_name="apply")


def _load_module_manifests(
    project_path: Path,
    module_names: list[str],
    *,
    strict: bool = False,
) -> dict[str, ModuleManifest]:
    """Load manifests for all installed modules"""
    manifests: dict[str, ModuleManifest] = {}
    for module_name in module_names:
        try:
            manifest = get_manifest_for_module(project_path, module_name, strict=strict)
        except ManifestError as error:
            if strict and "Manifest file not found:" not in str(error):
                raise
            manifest = None
        if manifest:
            manifests[module_name] = manifest
    return manifests


def _check_immutable_config_changes(delta: ConfigDelta) -> bool:
    """Check for immutable config changes and show errors

    Returns True if there are no immutable changes (safe to proceed)
    Returns False if there are immutable changes (should abort)

    """
    if not delta.has_immutable_config_changes:
        return True

    click.secho(
        "\n❌ Cannot apply: Immutable configuration changes detected!",
        fg="red",
        bold=True,
    )
    click.echo("\nThe following options cannot be changed after embed:\n")

    for module_name, change in delta.get_all_immutable_changes():
        click.echo(f"  ✗ {module_name}.{change.option_name}:")
        click.echo(f"    Current: {change.old_value}")
        click.echo(f"    Desired: {change.new_value}")

    click.secho(
        "\n⚠️  DATA LOSS WARNING: the only safe path is remove + re-add,",
        fg="yellow",
        bold=True,
    )
    click.echo(
        "   which drops the module's database tables/migrations and discards\n"
        "   any user edits inside the module's managed files."
    )

    click.echo("\n💡 To change immutable options:")
    modules_with_immutable = set(
        module_name for module_name, _ in delta.get_all_immutable_changes()
    )
    for module_name in modules_with_immutable:
        click.echo(f"   1. quickscale remove {module_name}")
        click.echo("   2. Update quickscale.yml with new options")
        click.echo("   3. quickscale apply")
        click.echo()

    click.echo(
        "   `quickscale remove` snapshots every mutable file (module dir,\n"
        "   managed settings/urls, quickscale.yml, .quickscale state) before\n"
        "   mutating and rolls back automatically if removal fails, so it is\n"
        "   the safe path for changing an immutable option."
    )

    return False


def _abort_for_config_driven_module_removals(delta: ConfigDelta) -> None:
    """Reject desired-state removals that must go through quickscale remove."""
    if not delta.modules_to_remove:
        return

    click.secho(
        "\n❌ Cannot apply: config-driven module removals are not supported.",
        fg="red",
        bold=True,
    )
    click.echo("\nThe following installed modules were removed from quickscale.yml:\n")
    for module_name in delta.modules_to_remove:
        click.echo(f"  ✗ {module_name}")

    click.secho(
        "\n⚠️  DATA LOSS WARNING: deleting a module from quickscale.yml and",
        fg="yellow",
        bold=True,
    )
    click.echo(
        "   applying will not run the explicit remove path, so you would lose\n"
        "   `quickscale remove`'s built-in snapshot/rollback safety for the\n"
        "   module dir, managed settings/urls, quickscale.yml, and .quickscale\n"
        "   state. The explicit remove workflow is the safe path."
    )

    click.echo("\n💡 Use the explicit remove workflow instead:")
    for module_name in delta.modules_to_remove:
        click.echo(f"   1. quickscale remove {module_name}")
    click.echo("   2. Re-run quickscale apply")
    click.echo(
        "   `quickscale remove` snapshots every mutable file before mutating\n"
        "   and rolls back automatically if removal fails."
    )
    click.echo(
        "\nApply will not partially remove installed modules from managed wiring "
        "without also updating authoritative module state."
    )
    raise click.Abort()


def _update_module_config_in_state(
    state: QuickScaleState,
    config: QuickScaleConfig,
    delta: ConfigDelta,
) -> None:
    """Update module options in state after mutable config changes"""
    del config
    config_deltas = getattr(delta, "config_deltas", {})
    if not isinstance(config_deltas, Mapping):
        return

    for module_name, module_delta in config_deltas.items():
        if module_delta.has_mutable_changes and module_name in state.modules:
            # Update options with new values
            current_options = state.modules[module_name].options or {}
            for change in module_delta.mutable_changes:
                current_options[change.option_name] = change.new_value
            state.modules[module_name].options = sanitize_module_options(
                module_name,
                current_options,
            )


def _resolve_managed_wiring_paths(
    qs_config: QuickScaleConfig,
) -> list[str]:
    """Return the managed wiring file paths that apply should track.

    Paths are repo-relative (forward slashes) so they match the keys
    written by :func:`compute_file_hashes`. The returned list always
    includes the default managed wiring files; module-specific managed
    files inside ``<package>/quickscale_managed/`` are not enumerated
    here because they are owned by individual modules and may be
    introduced or removed without breaking the drift signal.
    """
    package = qs_config.project.package
    return [f"{package}/{relative}" for relative in DEFAULT_MANAGED_WIRING_PATHS]


def _warn_version_drift_for_apply(
    project_path: Path,
    qs_config: QuickScaleConfig,
) -> list[VersionDriftWarning]:
    """Surface module version drift between state and legacy config.

    Called near the start of apply so users can see drift before any
    mutation. Drift between state and config is non-fatal: apply
    reconciles the two at finalize time via
    :func:`_sync_legacy_module_config_versions`. The warnings exist so
    that operations and status can surface the gap.
    """
    state_manager = ProjectStateManager(project_path)
    try:
        state = state_manager.load_state()
        config = state_manager.load_config()
    except (StateError, ConfigError) as error:
        click.secho(
            f"⚠️  Could not read managed state files for drift check: {error}",
            fg="yellow",
        )
        return []

    drift = check_version_drift(state, config)
    if not drift:
        return []

    del qs_config
    click.secho(
        "\n⚠️  Module version drift between .quickscale/state.yml and "
        ".quickscale/config.yml:",
        fg="yellow",
        bold=True,
    )
    for warning in drift:
        click.echo(f"  • {warning.message}")
    click.echo(
        "\n💡 Apply will reconcile .quickscale/config.yml to the canonical "
        "state-managed version. The drift is informational and not fatal.",
    )
    return drift


def _capture_managed_file_hashes_after_apply(
    project_path: Path,
    qs_config: QuickScaleConfig,
    state: QuickScaleState,
) -> StepOutcome:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    Returns the :class:`StepOutcome` from the core step body.
    SA18.9 made this a fail-hard step — `quickscale apply` will abort
    when the outcome carries ``success=False``.
    """

    def _resolve_paths() -> list[str]:
        return _resolve_managed_wiring_paths(qs_config)

    def _compute_hashes(path: Path, paths: list[str]) -> dict[str, str]:
        return compute_file_hashes(path, paths)

    def _record_hash(path_str: str, digest: str) -> None:
        state.managed_files[path_str] = ManagedFileRecord(path=path_str, hash=digest)

    def _reporter(message: str, *, ok: bool = True) -> None:
        if ok:
            click.echo(message)
        else:
            click.secho(message, fg="yellow")

    step_ctx = StepContext(
        output_path=project_path,
        qs_config=qs_config,
        reporter=_reporter,
    )
    return step_capture_hashes(
        step_ctx,
        compute_file_hashes_fn=_compute_hashes,
        resolve_managed_wiring_paths_fn=_resolve_paths,
        record_hash_fn=_record_hash,
    )


def _sanitize_loaded_module_configs(qs_config: QuickScaleConfig) -> list[str]:
    """Normalize module configs so legacy keys never persist after apply."""
    sanitized_modules: list[str] = []
    for module_name, module_config in qs_config.modules.items():
        normalized = sanitize_module_options(module_name, module_config.options or {})
        if normalized == (module_config.options or {}):
            continue
        module_config.options = normalized
        sanitized_modules.append(module_name)
    return sanitized_modules


def _materialize_implied_module_configs(qs_config: QuickScaleConfig) -> list[str]:
    """Add explicit module config blocks required by selected modules."""
    implied_configs = resolve_module_implications(qs_config.modules.keys())
    if not implied_configs:
        return []

    for module_name, options in implied_configs.items():
        qs_config.modules[module_name] = ModuleConfig(
            name=module_name,
            options=sanitize_module_options(module_name, options),
        )

    return list(implied_configs.keys())


def _load_and_validate_config(config_path: Path) -> QuickScaleConfig:
    """Load and validate configuration from file."""
    if not config_path.exists():
        click.secho(
            f"❌ Configuration file not found: {config_path}", fg="red", err=True
        )
        click.echo(
            "\n💡 Create a configuration with: quickscale plan <project-slug>",
            err=True,
        )
        raise click.Abort()

    click.echo(f"\n📋 Reading configuration: {config_path}")
    try:
        yaml_content = config_path.read_text()
        qs_config = validate_config(yaml_content)
        original_data = yaml.safe_load(yaml_content) or {}
        original_modules = original_data.get("modules") or {}
        sanitized_modules = _sanitize_loaded_module_configs(qs_config)
        implied_modules = _materialize_implied_module_configs(qs_config)
        normalized_yaml = generate_yaml(qs_config)
        normalized_data = yaml.safe_load(normalized_yaml) or {}
        normalized_modules = normalized_data.get("modules") or {}
        if normalized_modules != original_modules:
            config_path.write_text(normalized_yaml)
            if sanitized_modules:
                click.secho(
                    "✅ Sanitized legacy module config keys in quickscale.yml",
                    fg="green",
                )
            if implied_modules:
                click.secho(
                    "✅ Added implied module config to quickscale.yml: "
                    + ", ".join(implied_modules),
                    fg="green",
                )
        _validate_module_prerequisites(qs_config)
        return qs_config
    except ConfigValidationError as e:
        click.secho(f"\n❌ Configuration error:\n{e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"\n❌ Failed to read configuration: {e}", fg="red", err=True)
        raise click.Abort()


def _validate_module_prerequisites(qs_config: QuickScaleConfig) -> None:
    """Validate actionable module-specific prerequisites before apply proceeds."""
    if "orgs" in qs_config.modules and "auth" not in qs_config.modules:
        click.secho(
            "\n❌ Organizations requires the auth module before apply can continue:",
            fg="red",
            err=True,
        )
        click.echo(
            "  • Add 'auth' under modules in quickscale.yml before applying orgs.",
            err=True,
        )
        click.echo(
            "\n💡 Organizations relies on the QuickScale auth login flow and "
            "django-allauth account adapter hooks. Re-run 'quickscale plan "
            "--reconfigure --configure-modules' or edit quickscale.yml to add "
            "auth, then re-run 'quickscale apply'.",
            err=True,
        )
        raise click.Abort()

    if "orgs" in qs_config.modules:
        orgs_issues = validate_orgs_module_options(
            qs_config.modules["orgs"].options or {}
        )
        if orgs_issues:
            click.secho(
                "\n❌ Orgs module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in orgs_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the orgs option values.",
                err=True,
            )
            raise click.Abort()

    billing_config = qs_config.modules.get("billing")
    if billing_config is not None:
        billing_issues = validate_billing_module_options(billing_config.options or {})
        if billing_issues:
            click.secho(
                "\n❌ Billing module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in billing_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or "
                "edit quickscale.yml to correct the billing option values. "
                "Billing apply requires valid env-var references and a supported "
                "currency code.",
                err=True,
            )
            raise click.Abort()

        if "auth" not in qs_config.modules:
            click.secho(
                "\n❌ Billing requires the auth module before apply can continue:",
                fg="red",
                err=True,
            )
            click.echo(
                "  • Add 'auth' under modules in quickscale.yml before applying billing.",
                err=True,
            )
            click.echo(
                "\n💡 Billing relies on the QuickScale auth login flow and "
                "AUTH_USER_MODEL. Re-run 'quickscale plan --reconfigure "
                "--configure-modules' or edit quickscale.yml to add auth, then "
                "re-run 'quickscale apply'.",
                err=True,
            )
            raise click.Abort()

    _abort_for_not_ready_modules(
        list(qs_config.modules.keys()), source="quickscale.yml"
    )

    blog_config = qs_config.modules.get("blog")
    if blog_config is not None:
        blog_issues = validate_blog_module_options(blog_config.options or {})
        if blog_issues:
            click.secho(
                "\n❌ Blog module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in blog_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the blog option values. "
                "Blog apply requires valid posts_per_page, enable_rss, and api_rate_limit.",
                err=True,
            )
            raise click.Abort()

    forms_config = qs_config.modules.get("forms")
    if forms_config is not None:
        forms_issues = validate_forms_module_options(forms_config.options or {})
        if forms_issues:
            click.secho(
                "\n❌ Forms module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in forms_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the forms option values. "
                "Forms apply requires valid forms_per_page, rate_limit, "
                "data_retention_days, and boolean flags.",
                err=True,
            )
            raise click.Abort()

    storage_config = qs_config.modules.get("storage")
    if storage_config is not None:
        storage_issues = validate_storage_module_options(storage_config.options or {})
        if storage_issues:
            click.secho(
                "\n❌ Storage module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in storage_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the storage option values. "
                "Storage apply requires a valid backend and optional booleans.",
                err=True,
            )
            raise click.Abort()

    backups_config = qs_config.modules.get("backups")
    if backups_config is not None:
        issues = validate_backups_module_options(backups_config.options or {})
        if issues:
            click.secho(
                "\n❌ Backups module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to supply the missing private-remote env-var references.",
                err=True,
            )
            raise click.Abort()

    analytics_config = qs_config.modules.get("analytics")
    if analytics_config is not None:
        analytics_issues = validate_analytics_module_options(
            analytics_config.options or {}
        )
        if analytics_issues:
            click.secho(
                "\n❌ Analytics module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in analytics_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the analytics values. Existing React and HTML "
                "theme files remain user-owned and are not rewritten by analytics apply.",
                err=True,
            )
            raise click.Abort()

    social_config = qs_config.modules.get("social")
    if social_config is not None:
        social_issues = validate_social_module_options(social_config.options or {})
        if social_issues:
            click.secho(
                "\n❌ Social module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in social_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the social settings. This phase wires the "
                "managed backend transport, and the canonical public paths remain "
                f"{SOCIAL_LINK_TREE_PATH} and {SOCIAL_EMBEDS_PATH} for fresh "
                "showcase_react generations or manual theme adoption.",
                err=True,
            )
            raise click.Abort()

    crm_config = qs_config.modules.get("crm")
    if crm_config is not None:
        crm_issues = validate_crm_module_options(crm_config.options or {})
        if crm_issues:
            click.secho(
                "\n❌ CRM module configuration is incomplete for apply:",
                fg="red",
                err=True,
            )
            for issue in crm_issues:
                click.echo(f"  • {issue}", err=True)
            click.echo(
                "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
                "quickscale.yml to correct the CRM option values.",
                err=True,
            )
            raise click.Abort()

    notifications_config = qs_config.modules.get("notifications")
    if notifications_config is None:
        return

    notifications_options = notifications_config.options or {}
    notification_issues = validate_notifications_module_options(notifications_options)
    if not notification_issues:
        return

    click.secho(
        "\n❌ Notifications module configuration is incomplete for apply:",
        fg="red",
        err=True,
    )
    for issue in notification_issues:
        click.echo(f"  • {issue}", err=True)
    if notifications_production_targeted(notifications_options):
        click.echo(
            "\n💡 This configuration targets live Resend delivery, so apply refuses "
            "to leave production on the console email backend. Complete the missing "
            "notifications settings first.",
            err=True,
        )
    else:
        click.echo(
            "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or edit "
            "quickscale.yml to correct the notifications values.",
            err=True,
        )
    raise click.Abort()


def _render_notifications_env_example_block(
    options: Mapping[str, Any] | None,
) -> str:
    """Render the managed notifications section for `.env.example`."""
    resolved = resolve_notifications_module_options(options)
    resend_api_key_env_var = str(
        resolved.get(
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
            DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
        )
        or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
    ).strip()
    webhook_secret_env_var = str(
        resolved.get(
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
            DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
        )
        or DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
    ).strip()
    resend_domain = str(resolved.get("resend_domain", "")).strip()
    sender_email = str(resolved.get("sender_email", "noreply@example.com")).strip()

    lines = [
        "# QuickScale Notifications (managed)",
        "# Leave these blank until your verified Resend domain is ready for live delivery.",
        f"# Sender address from quickscale.yml: {sender_email}",
    ]
    if resend_domain:
        lines.append(f"# Verified Resend domain from quickscale.yml: {resend_domain}")
    lines.extend(
        [
            f"{resend_api_key_env_var}=",
            f"{webhook_secret_env_var}=",
            "# End QuickScale Notifications",
        ]
    )
    return "\n".join(lines)


def _sync_notifications_env_example_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Original implementation used as callback for core step body."""
    notifications_config = qs_config.modules.get("notifications")
    env_example_path = output_path / ".env.example"
    if notifications_config is None or not env_example_path.exists():
        return True
    start_marker = "# QuickScale Notifications (managed)"
    end_marker = "# End QuickScale Notifications"
    rendered_block = _render_notifications_env_example_block(
        notifications_config.options or {}
    )
    try:
        content = env_example_path.read_text()
    except OSError as e:
        click.secho(
            f"⚠️  Failed to read .env.example for notifications wiring: {e}",
            fg="yellow",
        )
        return False
    if start_marker in content and end_marker in content:
        before, remainder = content.split(start_marker, maxsplit=1)
        _, after = remainder.split(end_marker, maxsplit=1)
        replacement = rendered_block + after
        updated_content = before + replacement
    else:
        suffix = "" if content.endswith("\n") else "\n"
        updated_content = content + suffix + "\n" + rendered_block + "\n"
    try:
        env_example_path.write_text(updated_content)
    except OSError as e:
        click.secho(
            f"⚠️  Failed to update .env.example for notifications wiring: {e}",
            fg="yellow",
        )
        return False
    click.secho("✅ Updated .env.example with notifications env vars", fg="green")
    return True


def _sync_notifications_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = StepContext(output_path=output_path, qs_config=qs_config)
    outcome = step_notifications_env_sync(
        step_ctx,
        sync_notifications_fn=_sync_notifications_env_example_impl,
    )
    return outcome.success


def _render_analytics_env_example_block(
    options: Mapping[str, Any] | None,
) -> str:
    """Render the managed analytics section for `.env.example`."""
    resolved = resolve_analytics_module_options(options)
    api_key_env_var = str(
        resolved.get(
            "posthog_api_key_env_var",
            DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
        )
        or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
    ).strip()
    host_env_var = str(
        resolved.get(
            "posthog_host_env_var",
            DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
        )
        or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR
    ).strip()
    host = str(
        resolved.get("posthog_host", ANALYTICS_POSTHOG_DEFAULT_HOST)
        or ANALYTICS_POSTHOG_DEFAULT_HOST
    ).strip()

    return "\n".join(
        [
            "# QuickScale Analytics (managed)",
            "# Runtime PostHog variables for the backend analytics module.",
            "# VITE_* variables are for fresh showcase_react generations or manual frontend adoption.",
            f"# Leave {host_env_var} blank to fall back to {host}.",
            f"{api_key_env_var}=",
            f"{host_env_var}=",
            "VITE_POSTHOG_KEY=",
            "VITE_POSTHOG_HOST=",
            "# End QuickScale Analytics",
        ]
    )


def _sync_analytics_env_example_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Original implementation used as callback for core step body."""
    analytics_config = qs_config.modules.get("analytics")
    env_example_path = output_path / ".env.example"
    if not env_example_path.exists():
        return True
    start_marker = "# QuickScale Analytics (managed)"
    end_marker = "# End QuickScale Analytics"
    try:
        content = env_example_path.read_text()
    except OSError:
        return False
    rendered_block: str | None = None
    if analytics_config is not None:
        resolved = resolve_analytics_module_options(analytics_config.options or {})
        if bool(resolved.get("enabled", True)):
            rendered_block = _render_analytics_env_example_block(resolved)
    if start_marker in content and end_marker in content:
        before, remainder = content.split(start_marker, maxsplit=1)
        _, after = remainder.split(end_marker, maxsplit=1)
        if rendered_block is None:
            updated_content = before.rstrip("\n")
            if after.strip():
                if updated_content:
                    updated_content += "\n"
                updated_content += after.lstrip("\n")
            elif updated_content:
                updated_content += "\n"
        else:
            updated_content = before + rendered_block + after
    else:
        if rendered_block is None:
            return True
        suffix = "" if content.endswith("\n") else "\n"
        updated_content = content + suffix + "\n" + rendered_block + "\n"
    try:
        env_example_path.write_text(updated_content)
    except OSError:
        return False
    return True


def _sync_analytics_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = StepContext(output_path=output_path, qs_config=qs_config)
    outcome = step_analytics_env_sync(
        step_ctx,
        sync_analytics_fn=_sync_analytics_env_example_impl,
    )
    return outcome.success


def _render_billing_env_example_block(
    options: Mapping[str, Any] | None,
) -> str:
    """Render the managed billing section for `.env.example`."""
    resolved = resolve_billing_module_options(options)
    publishable_key_env_var = str(
        resolved.get(
            "publishable_key_env_var",
            DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
        )
        or DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR
    ).strip()
    secret_key_env_var = str(
        resolved.get(
            "secret_key_env_var",
            DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
        )
        or DEFAULT_BILLING_SECRET_KEY_ENV_VAR
    ).strip()
    webhook_secret_env_var = str(
        resolved.get(
            "webhook_secret_env_var",
            DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
        )
        or DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR
    ).strip()
    billing_currency = str(
        resolved.get("billing_currency", DEFAULT_BILLING_CURRENCY)
        or DEFAULT_BILLING_CURRENCY
    ).strip()

    return "\n".join(
        [
            "# QuickScale Billing (managed)",
            "# Runtime Stripe variables for the backend billing module.",
            f"# Billing currency from quickscale.yml: {billing_currency}",
            f"{publishable_key_env_var}=",
            f"{secret_key_env_var}=",
            f"{webhook_secret_env_var}=",
            "# End QuickScale Billing",
        ]
    )


def _sync_billing_env_example_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Original implementation used as callback for core step body."""
    billing_config = qs_config.modules.get("billing")
    env_example_path = output_path / ".env.example"
    if billing_config is None or not env_example_path.exists():
        return True
    start_marker = "# QuickScale Billing (managed)"
    end_marker = "# End QuickScale Billing"
    rendered_block = _render_billing_env_example_block(billing_config.options or {})
    try:
        content = env_example_path.read_text()
    except OSError:
        return False
    if start_marker in content and end_marker in content:
        before, remainder = content.split(start_marker, maxsplit=1)
        _, after = remainder.split(end_marker, maxsplit=1)
        replacement = rendered_block + after
        updated_content = before + replacement
    else:
        suffix = "" if content.endswith("\n") else "\n"
        updated_content = content + suffix + "\n" + rendered_block + "\n"
    try:
        env_example_path.write_text(updated_content)
    except OSError:
        return False
    return True


def _sync_billing_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = StepContext(output_path=output_path, qs_config=qs_config)
    outcome = step_billing_env_sync(
        step_ctx,
        sync_billing_fn=_sync_billing_env_example_impl,
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
        options = normalize_backups_module_options(backups_config.options or {})
        default_local_directory = str(get_default_backups_config()["local_directory"])
        local_directory = options.get("local_directory", default_local_directory)
        entry = _normalize_backups_gitignore_entry(str(local_directory))
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

    step_ctx = StepContext(output_path=project_path, qs_config=qs_config)
    outcome = step_backups_gitignore(step_ctx, ensure_backups_ignore_fn=_impl)
    return outcome.success


def _determine_output_path(config_path: Path, project_slug: str) -> Path:
    """Determine output directory for project."""
    config_path = config_path.resolve()
    if config_path.parent.name == project_slug:
        return config_path.parent
    return Path.cwd() / project_slug


def _display_config_summary(qs_config: QuickScaleConfig) -> None:
    """Display configuration summary."""
    click.echo("\n🚀 Applying configuration:")
    click.echo(f"   Project slug: {qs_config.project.slug}")
    click.echo(f"   Python package: {qs_config.project.package}")
    click.echo(f"   Theme: {qs_config.project.theme}")
    if qs_config.modules:
        click.echo(f"   Modules: {', '.join(qs_config.modules.keys())}")
    else:
        click.echo("   Modules: (none)")
    click.echo(
        f"   Docker: start={qs_config.docker.start}, build={qs_config.docker.build}"
    )


def _provenance_repair_might_be_needed(ctx: ApplyContext) -> bool:
    """Check whether any installed module has a missing commit_sha.

    This is a cheap pre-lock probe used to decide whether the no-op gate
    should defer to the locked provenance-repair path instead of aborting
    immediately.  It does NOT perform the repair or write state.
    """
    if ctx.existing_state is None:
        return False
    if ctx.delta.has_changes:
        return False
    return any(
        module_state.commit_sha is None
        for module_state in ctx.existing_state.modules.values()
    )


def _attempt_provenance_repair_if_needed(ctx: ApplyContext) -> None:
    """Phase 3: Attempt bounded provenance repair for no-op scenarios.

    When delta.has_changes is False but some installed modules have missing
    commit_sha, attempt one bounded resolve_remote_ref() using existing
    tracking metadata. If successful, write authoritative state once. If
    resolution fails, warn and preserve no-op behavior.

    .. note::
       This function writes to ``.quickscale/state.yml`` and MUST only be
       called while the advisory lock is held (see :func:`_execute_apply_steps`).
    """
    if ctx.existing_state is None:
        return

    # Only attempt repair when this would otherwise be a no-op
    if ctx.delta.has_changes:
        return

    # Check if any installed modules have missing commit_sha
    modules_needing_repair = [
        module_name
        for module_name, module_state in ctx.existing_state.modules.items()
        if module_state.commit_sha is None
    ]

    if not modules_needing_repair:
        return

    click.echo(
        "\n🔧 Attempting provenance repair for modules with missing commit_sha..."
    )

    repaired_any = False
    repair_timestamp = datetime.now().isoformat()
    for module_name in modules_needing_repair:
        module_state = ctx.existing_state.modules[module_name]
        if module_state.branch is None:
            click.secho(
                f"⚠️  Cannot repair {module_name}: missing tracking branch metadata",
                fg="yellow",
            )
            continue

        # Use the default QuickScale remote URL
        remote = "https://github.com/Experto-AI/quickscale.git"
        branch = module_state.branch

        try:
            resolved_sha = resolve_remote_ref(remote, branch)
            module_state.commit_sha = resolved_sha
            # Backfill the full provenance triple: also refresh embedded_at
            # to the repair timestamp and ensure version is populated from
            # the embedded manifest when available.
            module_state.embedded_at = repair_timestamp
            manifest = get_manifest_for_module(ctx.output_path, module_name)
            if manifest is not None:
                normalized_version = normalize_installed_version(manifest.version)
                if normalized_version is not None:
                    module_state.version = normalized_version
            repaired_any = True
            click.secho(f"✅ Repaired {module_name}: {resolved_sha[:8]}", fg="green")
        except Exception as e:
            click.secho(
                f"⚠️  Could not resolve {module_name} from {branch}: {e}",
                fg="yellow",
            )

    if repaired_any:
        # Write authoritative state once with repaired commit_sha
        # Do NOT create recovery file — this is a best-effort repair
        try:
            state_manager = StateManager(ctx.output_path)
            state_manager.save(ctx.existing_state)
            click.secho(
                "✅ Updated .quickscale/state.yml with repaired provenance",
                fg="green",
            )
            # Refresh the delta so the next check sees no changes
            ctx.delta = compute_delta(ctx.qs_config, ctx.existing_state, ctx.manifests)
        except Exception as e:
            click.secho(
                f"⚠️  Failed to save repaired state: {e}",
                fg="yellow",
            )
    else:
        click.secho(
            "⚠️  Provenance repair could not resolve any modules. "
            "State remains unchanged.",
            fg="yellow",
        )


def _handle_delta_and_existing_state(
    delta: ConfigDelta,
    existing_state: QuickScaleState | None,
    *,
    has_pending_post_embed_recovery: bool = False,
    has_pending_provenance_repair: bool = False,
) -> None:
    """Handle delta display and abort conditions for existing state."""
    if existing_state is None:
        return

    click.echo("\n📊 Change Detection:")
    click.echo(format_delta(delta))

    if not delta.has_changes:
        if has_pending_post_embed_recovery:
            click.echo(
                "\n♻️  Pending post-embed apply recovery detected. "
                "Re-running the remaining apply steps."
            )
            return
        if has_pending_provenance_repair:
            click.echo(
                "\n🔧 Provenance repair needed. "
                "Continuing under advisory lock to repair state."
            )
            return
        click.secho(
            "\n✅ Nothing to do. Configuration matches applied state.", fg="green"
        )
        raise click.Abort()

    _abort_for_config_driven_module_removals(delta)

    if not _check_immutable_config_changes(delta):
        raise click.Abort()

    if delta.theme_changed:
        click.secho(
            "\n⚠️  WARNING: Theme changes are not supported after initial project generation!",
            fg="red",
            bold=True,
        )
        click.echo(
            "   Theme changes require regenerating the entire project from scratch.",
        )
        if not click.confirm("Continue anyway?", default=False):
            raise click.Abort()


def _check_output_directory(
    output_path: Path, existing_state: QuickScaleState | None, force: bool
) -> None:
    """Check if output directory is valid and handle existing content."""
    if not output_path.exists() or not any(output_path.iterdir()):
        click.echo(f"\n📁 Output directory: {output_path}")
        return

    if existing_state is not None:
        click.echo(f"\n📁 Existing project detected: {output_path}")
        click.echo("   Performing incremental apply (only changes will be made)")
        return

    existing_files = list(output_path.iterdir())
    if len(existing_files) == 1 and existing_files[0].name == "quickscale.yml":
        return

    if not force:
        click.secho(
            f"\n❌ Directory already exists and is not empty: {output_path}",
            fg="red",
            err=True,
        )
        click.echo(
            "   Use --force to overwrite or remove the directory first",
            err=True,
        )
        raise click.Abort()
    else:
        click.secho(
            f"\n⚠️  --force: Will overwrite existing content in {output_path}",
            fg="yellow",
        )


def _generate_new_project(
    qs_config: QuickScaleConfig, output_path: Path, force: bool
) -> None:
    """Generate project for new installations."""
    if output_path.exists():
        quickscale_yml_path = output_path / "quickscale.yml"
        if quickscale_yml_path.exists():
            _generate_with_existing_config(
                qs_config, output_path, quickscale_yml_path, force
            )
        else:
            if not _generate_project(qs_config, output_path):
                raise click.Abort()
    else:
        if not _generate_project(qs_config, output_path):
            raise click.Abort()


def _generate_with_existing_config(
    qs_config: QuickScaleConfig,
    output_path: Path,
    quickscale_yml_path: Path,
    force: bool,
) -> None:
    """Generate project when quickscale.yml already exists in output path."""
    import shutil
    import tempfile

    saved_config = quickscale_yml_path.read_text()

    temp_dir = Path(tempfile.mkdtemp(dir=str(output_path.parent)))
    temp_project = temp_dir / qs_config.project.slug

    if not _generate_project(qs_config, temp_project):
        shutil.rmtree(temp_dir)
        raise click.Abort()

    if force:
        # Backup+swap+rollback: move existing content to a same-filesystem backup
        # dir, swap staged files in, and restore the originals on failure.
        backup_dir = Path(tempfile.mkdtemp(dir=str(output_path.parent)))
        try:
            for item in output_path.iterdir():
                if item.name != "quickscale.yml":
                    shutil.move(str(item), str(backup_dir / item.name))
        except Exception:
            # Backup phase failed — restore whatever was moved to backup
            for item in backup_dir.iterdir():
                shutil.move(str(item), str(output_path / item.name))
            shutil.rmtree(backup_dir)
            shutil.rmtree(temp_dir)
            raise click.Abort()

        try:
            for item in temp_project.iterdir():
                dest = output_path / item.name
                shutil.move(str(item), str(dest))
        except Exception:
            # Staging swap failed — remove partially-moved files, restore originals
            for item in list(output_path.iterdir()):
                if item.name != "quickscale.yml":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            for item in backup_dir.iterdir():
                shutil.move(str(item), str(output_path / item.name))
            shutil.rmtree(backup_dir)
            shutil.rmtree(temp_dir)
            raise click.Abort()

        shutil.rmtree(backup_dir)
    else:
        for item in temp_project.iterdir():
            dest = output_path / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))

    shutil.rmtree(temp_dir)

    quickscale_yml_path.write_text(saved_config)
    click.secho(f"✅ Project generated: {output_path}", fg="green")


def _init_git_with_config(output_path: Path) -> None:
    """Initialize git repository with configuration."""
    if not _init_git(output_path):
        click.secho("⚠️  Git initialization failed, continuing...", fg="yellow")
        return

    subprocess.run(
        ["git", "config", "user.email", "quickscale@example.com"],
        cwd=output_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QuickScale"],
        cwd=output_path,
        capture_output=True,
    )

    if not _git_commit(output_path, "Initial project structure"):
        click.secho("⚠️  Initial commit failed, continuing...", fg="yellow")


def _list_git_changed_paths(
    project_path: Path,
    git_args: list[str],
    *,
    description: str,
) -> list[str]:
    """Return changed git paths for pre-embed safety checks."""
    result = subprocess.run(
        ["git", *git_args],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        click.secho(
            f"\n❌ Failed to inspect {description} before module embedding.",
            fg="red",
            err=True,
        )
        if result.stderr:
            click.echo(result.stderr.strip(), err=True)
        raise click.Abort()

    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def _commit_pending_config_changes(output_path: Path) -> None:
    """Commit pending QuickScale config changes before module embedding

    Stages and commits authoritative QuickScale config/state changes so
    git subtree operations have a clean working directory. Called before
    embedding modules in existing projects.

    Args:
        output_path: Path to the project directory

    """
    if is_working_directory_clean(output_path):
        return

    staged_paths = _list_git_changed_paths(
        output_path,
        ["diff", "--cached", "--name-only"],
        description="staged changes",
    )
    unstaged_paths = _list_git_changed_paths(
        output_path,
        ["diff", "--name-only"],
        description="unstaged changes",
    )
    untracked_paths = _list_git_changed_paths(
        output_path,
        ["ls-files", "--others", "--exclude-standard"],
        description="untracked files",
    )

    dirty_paths = sorted(set(staged_paths) | set(unstaged_paths) | set(untracked_paths))
    unrelated_dirty_paths = [
        path for path in dirty_paths if not _is_pre_embed_allowed_dirty_path(path)
    ]
    checkpoint_paths = _get_pre_embed_checkpoint_paths(dirty_paths)

    if unrelated_dirty_paths:
        click.secho(
            "\n❌ Cannot embed modules during 'quickscale apply' because unrelated staged, unstaged, or untracked changes are present:",
            fg="red",
            err=True,
        )
        for path in unrelated_dirty_paths:
            click.echo(f"  • {path}", err=True)
        click.echo(
            "\n💡 Commit, stash, or clean the unrelated changes and re-run 'quickscale apply'. Existing-project apply only permits dirty authoritative QuickScale files in quickscale.yml, .quickscale/state.yml, or .quickscale/config.yml before module embedding.",
            err=True,
        )
        raise click.Abort()

    if not checkpoint_paths:
        return

    if _stage_and_commit_with_index_restore(
        output_path,
        stage_cmd=["git", "add", "--", *checkpoint_paths],
        stage_description="Staging pending QuickScale configuration changes",
        commit_cmd=[
            "git",
            "commit",
            "-m",
            "Update QuickScale configuration",
            "--",
            *checkpoint_paths,
        ],
        commit_description="Committing pending QuickScale configuration changes",
    ):
        return

    click.secho(
        "\n❌ Cannot continue 'quickscale apply' because QuickScale could not checkpoint managed configuration changes before module embedding.",
        fg="red",
        err=True,
    )
    raise click.Abort()


def _embed_modules_step(
    output_path: Path,
    modules_to_embed: list[str],
    no_modules: bool,
    existing_state: QuickScaleState | None,
    split_ref_overrides: Mapping[str, str] | None = None,
) -> EmbedModulesResult:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    if no_modules or not modules_to_embed:
        if existing_state and not modules_to_embed:
            click.echo("⏭️  No new modules to embed")
        return EmbedModulesResult(success=True, embedded_modules=[])

    step_ctx = StepContext(
        output_path=output_path,
        existing_state=existing_state,
    )

    overrides = split_ref_overrides or {}

    def _embed_one_module(
        path: Path,
        module_name: str,
        *,
        skip_auth_migration_check: bool,
        provenance_sink: list[ModuleEmbedProvenance] | None,
    ) -> bool:
        embed_kwargs: dict[str, Any] = {
            "skip_auth_migration_check": skip_auth_migration_check,
            "provenance_sink": provenance_sink,
        }
        if module_name in overrides:
            embed_kwargs["split_ref"] = overrides[module_name]
        return _embed_module(
            path,
            module_name,
            **embed_kwargs,
        )

    outcome = step_embed_modules(
        step_ctx,
        modules_to_embed=modules_to_embed,
        no_modules=no_modules,
        embed_one_module=_embed_one_module,
        commit_changes=_git_commit,
        is_working_directory_clean_fn=is_working_directory_clean,
    )

    if outcome.success:
        return EmbedModulesResult(
            success=True,
            embedded_modules=step_ctx.embedded_modules,
            provenance_payloads=(
                step_ctx.provenance_payloads if step_ctx.provenance_payloads else None
            ),
        )

    # Failure path — distinguish hard-stop (commit failure) from soft-stop
    # (embed failure) to match historical behavior expected by tests.
    if step_ctx.embed_commit_failure:
        raise click.Abort()

    return EmbedModulesResult(
        success=False,
        embedded_modules=step_ctx.embedded_modules,
        failed_module=step_ctx.embed_failed_module,
    )


def _run_post_generation_steps_impl(
    output_path: Path,
) -> bool:
    """Original implementation used as callback for core step body.

    AF5 Phase 4: No longer runs migrations.  Local migrations are deferred
    to step 13 (the late confirmable phase) together with Docker migrations,
    Railway deploy, and other destructive/remote operations.
    """
    if not _run_poetry_lock(output_path):
        return False
    if not _run_poetry_install(output_path):
        return False
    return True


def _run_post_generation_steps(output_path: Path) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    AF5 Phase 4: No longer passes ``run_migrations``.  Local migrations
    are deferred to step 13.
    """
    step_ctx = StepContext(output_path=output_path)
    outcome = step_post_generation_setup(
        step_ctx,
        run_post_gen_steps_fn=_run_post_generation_steps_impl,
    )
    return outcome.success


def _sync_project_module_dependencies_for_apply_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Original implementation used as callback for core step body."""
    if not qs_config.modules:
        return True
    click.echo("\n⏳ Syncing module dependency entries...")
    try:
        sync_result = sync_project_module_dependencies(
            output_path,
            {
                module_name: module_config.options or {}
                for module_name, module_config in qs_config.modules.items()
            },
        )
    except (DependencySyncError, ManifestError) as error:
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
    step_ctx = StepContext(output_path=output_path, qs_config=qs_config)
    outcome = step_sync_dependencies(
        step_ctx,
        sync_project_deps_fn=_sync_project_module_dependencies_for_apply_impl,
    )
    return outcome.success


def _populate_consolidated_tracking_from_legacy(
    project_path: Path,
    state: QuickScaleState,
) -> None:
    """Merge consolidated tracking fields from legacy config.yml into state.

    After ``embed_module`` runs, the legacy ``config.yml`` carries
    ``prefix``, ``branch``, and ``installed_at`` for each embedded module.
    This helper reads those values and populates the corresponding
    :class:`ModuleState` fields so that ``state.yml`` is self-contained
    after apply.  Modules already carrying consolidated tracking are
    left untouched.

    F12.2: fail-closed — ``ConfigError`` / ``OSError`` propagate instead
    of being silently swallowed.  ``load_config`` returns a default empty
    config when the file does not exist, so this is a no-op for
    config-only / non-consolidated projects.
    """
    from quickscale_core.config import load_config as _load_legacy_config

    # load_config returns an empty default ModuleConfig when the file does
    # not exist, so a missing config.yml is a safe no-op.  Malformed or
    # unreadable legacy config propagates as ConfigError / OSError
    # (fail-close per F12.2).
    legacy_config = _load_legacy_config(project_path)

    for module_name, module_info in legacy_config.modules.items():
        module_state = state.modules.get(module_name)
        if module_state is None:
            continue
        if module_state.prefix is None:
            module_state.prefix = module_info.prefix
        if module_state.branch is None:
            module_state.branch = module_info.branch
        if module_state.installed_at is None:
            module_state.installed_at = module_info.installed_at


def _build_project_state_snapshot(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
) -> QuickScaleState:
    """Build the state snapshot used for success or retry recovery."""
    timestamp = datetime.now().isoformat()

    if existing_state is None:
        new_state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug=qs_config.project.slug,
                package=qs_config.project.package,
                theme=qs_config.project.theme,
                project_contract=quickscale_version,
                created_at=timestamp,
                last_applied=timestamp,
            ),
            modules={},
        )
    else:
        new_state = copy.deepcopy(existing_state)
        new_state.project.last_applied = timestamp
        # SA10.1: project_contract is generation-vintage evidence.
        # Fresh states set it from the current version (above).
        # Existing states preserve whatever they already have — legacy
        # projects that predate SA10.1 keep None (unknown vintage)
        # so future SA10.2 can distinguish "already on this contract"
        # from "unknown — needs manual adoption review".

    for module_name in embedded_modules:
        if module_name not in qs_config.modules:
            continue

        existing_module_state = new_state.modules.get(module_name)
        # Phase 2: populate commit_sha from the provenance payload when
        # available.  The provenance source_ref is the exact commit SHA
        # resolved once during apply embed (Phase 1 seam).
        provenance = (provenance_payloads or {}).get(module_name)
        commit_sha = (
            provenance.source_ref
            if provenance is not None
            else (existing_module_state.commit_sha if existing_module_state else None)
        )
        new_state.modules[module_name] = ModuleState(
            name=module_name,
            version=existing_module_state.version if existing_module_state else None,
            commit_sha=commit_sha,
            embedded_at=(
                existing_module_state.embedded_at
                if existing_module_state is not None
                else timestamp
            ),
            options=sanitize_module_options(
                module_name,
                qs_config.modules[module_name].options,
            ),
        )

    _update_module_config_in_state(new_state, qs_config, delta)

    for module_name, module_state in new_state.modules.items():
        manifest = get_manifest_for_module(output_path, module_name)
        if manifest is None:
            continue

        normalized_version = normalize_installed_version(manifest.version)
        if normalized_version is not None:
            module_state.version = normalized_version

    # Populate consolidated module-tracking fields (prefix, branch,
    # installed_at) from the legacy config.yml that embed_module wrote
    # during this apply pass.  This ensures state.yml is self-contained
    # after apply so that fresh push/update/status work from state alone.
    _populate_consolidated_tracking_from_legacy(output_path, new_state)

    return new_state


def _get_apply_recovery_manager(project_path: Path) -> LedgerManager:
    """Return a LedgerManager bound to the recovery ledger file."""
    return LedgerManager(project_path)


def _load_apply_recovery_state(project_path: Path) -> QuickScaleState | None:
    """Load any pending post-embed recovery snapshot.

    Returns the embedded applied-state (:class:`QuickScaleState`) when the
    recovery ledger file exists and is valid, or ``None`` when the file
    does not exist.  Malformed content raises :class:`LedgerError` which
    propagates as a ``StateError`` to existing callers.
    """
    mgr = _get_apply_recovery_manager(project_path)
    ledger = mgr.load()
    if ledger is None:
        return None
    return ledger.applied_state


def _merge_apply_recovery_state(
    existing_state: QuickScaleState | None,
    recovery_state: QuickScaleState | None,
) -> QuickScaleState | None:
    """Overlay recovery modules onto the authoritative state for retry planning."""
    if recovery_state is None:
        return existing_state

    if existing_state is None:
        return recovery_state

    merged_state = copy.deepcopy(existing_state)
    merged_state.project.last_applied = recovery_state.project.last_applied
    for module_name, module_state in recovery_state.modules.items():
        merged_state.modules[module_name] = copy.deepcopy(module_state)
    return merged_state


def _save_apply_recovery_state(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    state_snapshot: QuickScaleState | None = None,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
    checkpoint_tree_id: str,
) -> bool:
    """Persist retry context for failures that happen after embedding succeeded.

    The *checkpoint_tree_id* is the exact git tree id captured at the post-embed
    checkpoint so the recovery ledger records the authoritative index state
    rather than a later tree re-captured at save time.  It is **required** —
    the F12.1e contract fails hard when the checkpoint reference is unavailable.

    AF5 Phase 1: AF6-era (``resume_checkpoint``-absent) ledgers are handled
    conservatively — the new field is preserved if present and silently
    ``None`` if absent.
    """
    try:
        recovery_state = state_snapshot or _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
            provenance_payloads=provenance_payloads,
        )
        mgr = _get_apply_recovery_manager(output_path)

        # Carry forward any existing resume_checkpoint from the on-disk
        # ledger so AF5 metadata is preserved across recovery rewrites.
        existing_ledger = mgr.load()
        resume_checkpoint = (
            existing_ledger.resume_checkpoint if existing_ledger is not None else None
        )

        ledger = RecoveryLedger(
            applied_state=recovery_state,
            resume_checkpoint=resume_checkpoint,
            step_progress=None,
            git_index_checkpoint=checkpoint_tree_id,
        )
        mgr.save(ledger)
        click.secho(
            f"✅ Apply recovery saved to .quickscale/{_APPLY_RECOVERY_FILENAME}",
            fg="green",
        )
        return True
    except (LedgerError, OSError) as e:
        click.secho(
            f"❌ Failed to save apply recovery state: {e}",
            fg="red",
            err=True,
        )
        return False
    except Exception as e:
        click.secho(
            f"❌ Failed to save apply recovery state: {e}",
            fg="red",
            err=True,
        )
        return False


def _clear_apply_recovery_state(output_path: Path) -> None:
    """Remove any stale post-embed recovery snapshot."""
    mgr = _get_apply_recovery_manager(output_path)
    if not mgr.ledger_file.exists():
        return

    try:
        mgr.ledger_file.unlink()
    except OSError as e:
        click.secho(f"⚠️  Failed to clear apply recovery state: {e}", fg="yellow")


def _save_project_state(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    state_snapshot: QuickScaleState | None = None,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
) -> bool:
    """Save project state to .quickscale/state.yml.

    F12.2: helper-level fail-open (catches all exceptions, returns
    ``False``).  This is a deliberate pattern so that callers can decide
    the correct recovery action.  All direct callers handle the ``False``
    return by persisting recovery state and/or aborting with a clear
    message — the effective behavior is fail-closed.
    """
    try:
        state_manager = StateManager(output_path)
        new_state = state_snapshot or _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
            provenance_payloads=provenance_payloads,
        )

        state_manager.save(new_state)
        click.secho("✅ State saved to .quickscale/state.yml", fg="green")
        return True
    except Exception as e:
        click.secho(f"❌ Failed to save state: {e}", fg="red", err=True)
        return False


def _display_next_steps_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
    no_docker: bool,
    docker_started: bool | None = None,
    existing_project: bool = False,
) -> None:
    """Display success message and next steps."""
    click.echo("\n" + "=" * 50)
    click.secho("🎉 Apply complete!", fg="green", bold=True)
    click.echo("=" * 50)

    click.echo("\n📋 Next steps:")
    if output_path != Path.cwd():
        click.echo(f"  cd {qs_config.project.slug}")

    if qs_config.docker.start and not no_docker:
        if docker_started is False:
            click.echo("  # Docker auto-start failed during apply")
            click.echo("  quickscale up --build  # Retry Docker startup")
            click.echo("  quickscale logs        # View failure details")
        else:
            click.echo("  # Docker services should be running")
            click.echo("  quickscale logs backend  # View logs")
            click.echo("  quickscale ps        # Check status")
    else:
        click.echo("  quickscale up        # Start Docker services")
        click.echo("  quickscale manage migrate  # Run migrations after services start")
        click.echo("  # Or run without Docker:")
        click.echo("  poetry run python manage.py migrate")
        click.echo("  poetry run python manage.py runserver")

    modules = qs_config.modules if isinstance(qs_config.modules, Mapping) else {}
    if "backups" in modules:
        backups_options = normalize_backups_module_options(
            modules["backups"].options or {}
        )
        click.echo("\n  # Backups operations")
        click.echo("  poetry run python manage.py backups_create")
        click.echo(
            "  poetry run python manage.py backups_restore <id> --confirm BACKUP_FILENAME.dump --dry-run"
        )
        click.echo(
            "  poetry run python manage.py backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run"
        )
        click.echo(
            "  export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true  # Required for destructive restores outside local DEBUG"
        )
        click.echo(
            "  JSON artifacts are export-only; generated PostgreSQL projects restore only PostgreSQL 18 custom dumps."
        )
        click.echo("  Admin download and validate stay local-file-only in v1.")
        if existing_project:
            click.echo(
                "  quickscale apply does not rewrite user-owned Docker/CI/E2E files; manually adopt the PostgreSQL 18 tooling updates if this project predates the backups follow-up."
            )
        else:
            click.echo(
                "  Freshly generated Docker and GitHub CI files already install PostgreSQL 18 client tooling."
            )
        if backups_options.get("target_mode") == "private_remote":
            access_key_env_var = str(
                backups_options.get(
                    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
                    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
                )
                or DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
            )
            secret_key_env_var = str(
                backups_options.get(
                    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
                    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
                )
                or DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
            )
            click.echo(
                "  Configure runtime credentials via env vars "
                f"`{access_key_env_var}` and `{secret_key_env_var}` before relying "
                "on scheduled or production restore workflows."
            )

    if "notifications" in modules:
        notifications_options = resolve_notifications_module_options(
            modules["notifications"].options or {}
        )
        resend_api_key_env_var = str(
            notifications_options.get(
                NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
                DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
            )
            or DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
        )
        webhook_secret_env_var = str(
            notifications_options.get(
                NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
                DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
            )
            or DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
        )
        click.echo("\n  # Notifications setup")
        if bool(notifications_options.get("enabled", True)):
            if notifications_live_delivery_configured(notifications_options):
                resend_domain = str(
                    notifications_options.get("resend_domain", "")
                ).strip()
                click.echo(
                    "  Verify SPF/DKIM in Resend for "
                    + (resend_domain or "your sending domain")
                    + "."
                )
                click.echo(
                    f"  Set `{resend_api_key_env_var}` before relying on live email delivery."
                )
            else:
                click.echo(
                    "  Local development remains on the console email backend until "
                    "you configure a verified Resend domain."
                )
                click.echo(
                    f"  When ready, set `{resend_api_key_env_var}` and re-run `quickscale apply`."
                )
            click.echo(
                f"  Set `{webhook_secret_env_var}` before enabling signed delivery webhooks."
            )
        else:
            click.echo(
                "  Notifications is embedded but disabled. Re-enable it in quickscale.yml "
                "when you are ready to own email delivery through the module."
            )

    if "analytics" in modules:
        analytics_options = resolve_analytics_module_options(
            modules["analytics"].options or {}
        )
        click.echo("\n  # Analytics setup")
        if bool(analytics_options.get("enabled", True)):
            posthog_api_key_env_var = str(
                analytics_options.get(
                    "posthog_api_key_env_var",
                    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
                )
                or DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
            )
            posthog_host_env_var = str(
                analytics_options.get(
                    "posthog_host_env_var",
                    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
                )
                or DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR
            )
            posthog_host = str(
                analytics_options.get(
                    "posthog_host",
                    ANALYTICS_POSTHOG_DEFAULT_HOST,
                )
                or ANALYTICS_POSTHOG_DEFAULT_HOST
            )
            click.echo("  PostHog dashboard: https://app.posthog.com")
            click.echo(
                "  Live events: https://app.posthog.com/project/<project-id>/activity/explore"
            )
            click.echo(
                "  Set runtime Railway service variables: "
                f"`{posthog_api_key_env_var}` and optionally `{posthog_host_env_var}`."
            )
            click.echo(
                f"  Leave `{posthog_host_env_var}` blank to fall back to {posthog_host}."
            )
            click.echo(
                "  Set build-time `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` only for "
                "fresh `showcase_react` generations or manual frontend adoption."
            )
            click.echo(
                "  Existing React and HTML theme files remain user-owned; quickscale apply "
                "does not rewrite them for analytics."
            )
            click.echo(
                "  If you enforce CSP or referrer-policy restrictions, allow outbound "
                "requests to your configured PostHog API host."
            )
        else:
            click.echo(
                "  Analytics is embedded but disabled. Re-enable it in quickscale.yml "
                "when you are ready to capture events."
            )

    if "social" in modules:
        click.echo("\n  # Social integration")
        click.echo(
            "  Managed backend transport: "
            + f"{SOCIAL_INTEGRATION_BASE_PATH} and {SOCIAL_INTEGRATION_EMBEDS_PATH}"
        )
        click.echo(
            "  Fresh showcase_react generations keep Django-owned public pages at "
            + f"{SOCIAL_LINK_TREE_PATH} and {SOCIAL_EMBEDS_PATH}"
        )
        click.echo(
            "  showcase_react and existing generated projects only receive the managed "
            "backend transport automatically; use manual theme adoption if you want "
            "those public pages."
        )

    click.echo("\n  Visit: http://localhost:8000")


def _display_next_steps(
    output_path: Path,
    qs_config: QuickScaleConfig,
    no_docker: bool,
    docker_started: bool | None = None,
    *,
    existing_project: bool = False,
) -> None:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = StepContext(output_path=output_path, qs_config=qs_config)
    step_display_next_steps(
        step_ctx,
        display_next_steps_fn=_display_next_steps_impl,
        no_docker=no_docker,
        docker_started=docker_started,
        existing_project=existing_project,
    )


def _prepare_apply_context(config_path: Path) -> ApplyContext:
    """Prepare all context needed for apply execution.

    Returns:
        ApplyContext with all loaded and computed data
    """
    # Load and validate configuration
    qs_config = _load_and_validate_config(config_path)

    # Determine output path
    output_path = _determine_output_path(config_path, qs_config.project.slug)

    # Load existing state if project exists.
    # Use ProjectStateManager.load_state() for read-through legacy
    # compatibility so that apply planning sees the same consolidated
    # state as the rest of M2 (CR-001).
    project_state_manager = ProjectStateManager(output_path)
    state_manager = StateManager(output_path)
    try:
        authoritative_state = (
            project_state_manager.load_state() if output_path.exists() else None
        )
    except StateError as error:
        click.secho(
            f"\n❌ Failed to load .quickscale/state.yml: {error}",
            fg="red",
            err=True,
        )
        raise click.Abort() from error

    try:
        recovery_state = (
            _load_apply_recovery_state(output_path) if output_path.exists() else None
        )
    except StateError as error:
        click.secho(
            f"\n❌ Failed to load .quickscale/{_APPLY_RECOVERY_FILENAME}: {error}",
            fg="red",
            err=True,
        )
        raise click.Abort() from error

    existing_state = _merge_apply_recovery_state(authoritative_state, recovery_state)

    # Load manifests for modules (needed for config change detection)
    manifests: dict[str, ModuleManifest] = {}
    if existing_state and existing_state.modules:
        _abort_for_not_ready_modules(
            list(existing_state.modules.keys()),
            source=".quickscale/state.yml",
        )
        try:
            manifests = _load_module_manifests(
                output_path,
                list(existing_state.modules.keys()),
                strict=True,
            )
        except ManifestError as error:
            _abort_for_manifest_error(error, command_name="apply")

        # SA7.4: validate required-module version constraints
        _validate_required_module_versions(manifests)

    # Compute delta
    delta = compute_delta(qs_config, existing_state, manifests)

    return ApplyContext(
        config_path=config_path,
        qs_config=qs_config,
        output_path=output_path,
        state_manager=state_manager,
        existing_state=existing_state,
        manifests=manifests,
        delta=delta,
        has_pending_post_embed_recovery=recovery_state is not None,
        had_existing_state=authoritative_state is not None,
    )


def _regenerate_managed_wiring_for_apply(
    ctx: ApplyContext,
    embedded_modules: list[str],
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""

    def _wiring_fn(
        output_path: Path,
        module_names: list[str],
        qs_config: Any,
        existing_state: Any | None,
        delta: Any | None,
    ) -> tuple[bool, str]:
        try:
            desired_module_names = sorted(qs_config.modules.keys())
            if existing_state is None:
                selected = module_names
            else:
                unchanged = getattr(delta, "modules_unchanged", []) if delta else []
                selected = sorted(set(unchanged) | set(module_names))
            if not desired_module_names:
                selected = []
            options = {m: c.options for m, c in qs_config.modules.items()}
            return regenerate_managed_wiring(
                output_path,
                module_names=selected,
                option_overrides=options,
                project_package=qs_config.project.package,
            )
        except Exception as exc:
            # Reducing the exception to str(exc) discards the traceback, which
            # is why installed-context failures like the SA112 managed-wiring
            # NameError have stayed undiagnosable across cycles. Surface the
            # full traceback to stderr when QUICKSCALE_DEBUG is set so the
            # actual raising frame can be captured; default behavior (and the
            # returned message) is unchanged.
            if os.environ.get("QUICKSCALE_DEBUG"):
                click.echo(traceback.format_exc(), err=True)
            return False, str(exc)

    step_ctx = _build_step_context(ctx, embedded_modules=embedded_modules)
    outcome = step_regenerate_wiring(
        step_ctx,
        embedded_modules=embedded_modules,
        regenerate_wiring_fn=_wiring_fn,
    )

    if outcome.success:
        if step_ctx.reporter:
            step_ctx.reporter("Managed module wiring regenerated", ok=True)
        return True

    click.secho(
        f"❌ Managed wiring regeneration failed: {outcome.message}", fg="red", err=True
    )
    return False


def _print_apply_failure_summary(failed_step: str, reason: str) -> None:
    """Print explicit failure summary and skipped steps."""
    click.echo("\n" + "=" * 50)
    click.secho("❌ Apply failed", fg="red", bold=True)
    click.echo("=" * 50)
    click.echo(f"\nFailed step: {failed_step}")
    click.echo(f"Reason: {reason}")
    click.echo("\nSkipped downstream steps:")
    click.echo("  • poetry install")
    click.echo("  • docker start")
    click.echo("  • database migrations")
    click.echo("  • railway deploy")
    click.echo("  • success completion output")


def _abort_after_post_embed_failure(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
    failed_step: str,
    reason: str,
) -> None:
    """Persist rerunnable recovery state before aborting post-embed failures."""
    if _save_apply_recovery_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        list(post_embed_state.modules.keys()),
        ctx.delta,
        state_snapshot=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
    ):
        _print_apply_failure_summary(failed_step=failed_step, reason=reason)
        raise click.Abort()

    _print_apply_failure_summary(
        failed_step="apply recovery state persistence",
        reason=(
            f"{failed_step} failed and QuickScale could not save "
            f".quickscale/{_APPLY_RECOVERY_FILENAME} for rerun recovery."
        ),
    )
    raise click.Abort()


def _finalize_apply_state(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
) -> None:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""

    def _save_state() -> bool:
        return _save_project_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            list(post_embed_state.modules.keys()),
            ctx.delta,
            state_snapshot=post_embed_state,
        )

    def _save_recovery(*, checkpoint_tree_id: str) -> bool:
        return _save_apply_recovery_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            list(post_embed_state.modules.keys()),
            ctx.delta,
            state_snapshot=post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )

    def _clear_recovery() -> None:
        _clear_apply_recovery_state(ctx.output_path)

    step_ctx = _build_step_context(ctx, state_snapshot=post_embed_state)
    outcome = step_finalize_state(
        step_ctx,
        save_project_state_fn=_save_state,
        save_recovery_state_fn=_save_recovery,
        clear_recovery_state_fn=_clear_recovery,
        checkpoint_tree_id=checkpoint_tree_id,
    )

    if outcome.success:
        return

    _print_apply_failure_summary(
        failed_step=_FAILED_STEP.get(
            "authoritative state persistence", "authoritative state persistence"
        ),
        reason=str(outcome.message),
    )
    raise click.Abort()


def _context_has_pending_post_embed_recovery(ctx: Any) -> bool:
    """Safely read the recovery flag from real contexts and loose test doubles."""
    value = getattr(ctx, "has_pending_post_embed_recovery", False)
    return value if isinstance(value, bool) else False


def _context_had_existing_state(ctx: Any) -> bool:
    """Safely determine whether apply started from authoritative state."""
    value = getattr(ctx, "had_existing_state", False)
    if isinstance(value, bool):
        return value
    return getattr(ctx, "existing_state", None) is not None


def _refresh_context_after_lock(ctx: ApplyContext) -> None:
    """Re-read authoritative state and recompute delta after lock acquisition.

    The pre-lock context loaded in :func:`_prepare_apply_context` may be
    stale if another concurrent apply finished between the initial read
    and lock acquisition.  Re-read state and recompute the delta so that
    the locked planning phase operates on fresh data.

    This is a no-op when the output path does not exist, has no
    authoritative state, or when the refresh would produce an inconsistent
    context (e.g. Mock objects in tests).
    """
    if not ctx.output_path.exists():
        return

    # Use ProjectStateManager.load_state() for read-through legacy
    # compatibility so the post-lock refresh sees the same consolidated
    # state as the rest of M2 (CR-001).
    project_state_manager = ProjectStateManager(ctx.output_path)
    try:
        authoritative_state = project_state_manager.load_state()
    except StateError:
        return  # Keep the pre-lock context; the locked path will surface errors.

    # If we could not load authoritative state, keep the pre-lock context.
    # This handles both fresh-project paths and test fixtures that use
    # non-project directories.
    if authoritative_state is None:
        return

    # F12.1d: malformed authoritative recovery ledger must fail hard
    # rather than being silently treated as absent.  LedgerError
    # (subclass of StateError) propagates to the operator.
    recovery_state = _load_apply_recovery_state(ctx.output_path)

    merged_state = _merge_apply_recovery_state(authoritative_state, recovery_state)

    # Reload manifests for the refreshed state.
    manifests: dict[str, ModuleManifest] = {}
    if merged_state and merged_state.modules:
        try:
            manifests = _load_module_manifests(
                ctx.output_path,
                list(merged_state.modules.keys()),
                strict=True,
            )
        except ManifestError:
            manifests = {}

        # SA7.4: re-validate required-module version constraints with
        # fresh manifests so a concurrent module update is not missed.
        try:
            check_required_module_versions(manifests)
        except ManifestError as error:
            _abort_for_manifest_error(error, command_name="apply")

    delta = compute_delta(ctx.qs_config, merged_state, manifests)

    ctx.existing_state = merged_state
    ctx.manifests = manifests
    ctx.delta = delta
    ctx.has_pending_post_embed_recovery = recovery_state is not None
    ctx.had_existing_state = True


# ---------------------------------------------------------------------------
# AF6 Phase 2 — Step context adapter
# ---------------------------------------------------------------------------


def _build_step_context(
    ctx: ApplyContext,
    *,
    state_snapshot: Any = None,
    embedded_modules: list[str] | None = None,
    no_docker: bool = False,
    verbose_docker: bool = False,
) -> StepContext:
    """Build a core-safe :class:`StepContext` from the CLI-level :class:`ApplyContext`."""
    return StepContext(
        output_path=ctx.output_path,
        qs_config=ctx.qs_config,
        existing_state=getattr(ctx, "existing_state", None),
        state_snapshot=state_snapshot,
        manifests=getattr(ctx, "manifests", {}),
        delta=getattr(ctx, "delta", None),
        embedded_modules=embedded_modules or [],
        no_docker=no_docker,
        verbose_docker=verbose_docker,
    )


# ---------------------------------------------------------------------------
# AF6 Phase 2 — CLI adapters for inline step bodies
# ---------------------------------------------------------------------------


def _exec_step_post_embed_snapshot(
    ctx: ApplyContext,
    embedded_modules: list[str],
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None,
) -> tuple[QuickScaleState | None, str | None]:
    """Adapter for step 2 (post-embed state snapshot + git index capture).

    Returns ``(post_embed_state, checkpoint_tree_id)`` on success, or
    ``(None, None)`` and raises ``click.Abort`` on failure.
    """
    step_ctx = _build_step_context(ctx, embedded_modules=embedded_modules)

    def _build_snapshot() -> QuickScaleState | None:
        return _build_project_state_snapshot(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            embedded_modules,
            ctx.delta,
            provenance_payloads=provenance_payloads,
        )

    def _capture_index() -> GitIndexSnapshot | None:
        snapshot = _capture_git_index_snapshot(ctx.output_path)
        if snapshot is None:
            return None
        return GitIndexSnapshot(tree_id=snapshot.tree_id)

    outcome = step_post_embed_snapshot(
        step_ctx,
        build_state_snapshot=_build_snapshot,
        capture_git_index=_capture_index,
    )

    if not outcome.success:
        _print_apply_failure_summary(
            failed_step="post-embed state snapshot",
            reason=str(outcome.message),
        )
        raise click.Abort()

    post_embed_state = cast(QuickScaleState, step_ctx.state_snapshot)
    return post_embed_state, step_ctx.checkpoint_tree_id or ""


def _exec_step_apply_mutable_config(ctx: ApplyContext) -> None:
    """Adapter for step 11 (apply mutable config).

    Informational step — never fails.
    """
    step_ctx = _build_step_context(ctx)
    step_apply_mutable_config(step_ctx)


def _exec_step_railway_deploy(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
) -> None:
    """Adapter for step 14 (Railway deploy).

    Raises ``click.Abort`` on failure via ``_abort_after_post_embed_failure``.
    """
    is_railway_linked = (ctx.output_path / ".railway").is_dir()

    def _deploy_fn(
        project_path: Path,
        service_name: str,
    ) -> Any:
        return deploy_railway_service(
            project_path=project_path,
            service_name=service_name,
        )

    step_ctx = _build_step_context(ctx, state_snapshot=post_embed_state)

    outcome = step_railway_deploy(
        step_ctx,
        is_railway_linked=is_railway_linked,
        deploy_railway_fn=_deploy_fn,
        get_service_name_fn=get_app_service_name,
    )

    if not outcome.success:
        _abort_after_post_embed_failure(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
            failed_step="railway deploy",
            reason=str(outcome.message),
        )


def _execute_apply_steps(
    ctx: ApplyContext,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    verbose_docker: bool = False,
    split_ref_overrides: Mapping[str, str] | None = None,
) -> None:
    """Execute the apply steps after confirmation."""
    click.echo("\n" + "=" * 50)
    click.echo("🔧 Starting apply process...")
    click.echo("=" * 50)

    has_pending_post_embed_recovery = _context_has_pending_post_embed_recovery(ctx)

    # Surface module version drift between state and legacy config early.
    # Drift is non-fatal: apply reconciles the two at finalize time.
    _warn_version_drift_for_apply(ctx.output_path, ctx.qs_config)

    # Generate project (only for new projects)
    project_generated = False
    if ctx.existing_state is None:
        _generate_new_project(ctx.qs_config, ctx.output_path, force)
        project_generated = True
    else:
        click.echo("⏭️  Skipping project generation (project already exists)")

    # Initialize git (only for new projects)
    if project_generated:
        _init_git_with_config(ctx.output_path)

    # Acquire advisory lock after project directory exists but before any
    # state mutation. For new projects, the directory was just created by
    # project generation. For existing projects, it already exists.
    lock = AdvisoryLock(ctx.output_path, operation="apply")
    try:
        lock.acquire()
    except AdvisoryLockContentionError as error:
        click.secho(f"❌ {error}", fg="red", err=True)
        raise click.Abort() from error

    try:
        # Re-read authoritative state and recompute delta after acquiring
        # the lock so that planning uses fresh state, not a stale snapshot
        # taken before the lock was held.
        _refresh_context_after_lock(ctx)
        _validate_split_ref_override_coverage(
            ctx,
            split_ref_overrides,
            no_modules=no_modules,
        )

        # Phase 3: Attempt bounded provenance repair before no-op detection
        _attempt_provenance_repair_if_needed(ctx)

        # Re-run top-level gate decisions with the refreshed state so that
        # stale pre-lock no-op / immutable-change / config-removal decisions
        # cannot continue mutating under the lock if another apply won the
        # race between the initial read and lock acquisition (CR-002).
        _handle_delta_and_existing_state(
            ctx.delta,
            ctx.existing_state,
            has_pending_post_embed_recovery=ctx.has_pending_post_embed_recovery,
        )

        _execute_apply_steps_locked(
            ctx,
            force,
            no_docker,
            no_modules,
            verbose_docker,
            project_generated=project_generated,
            has_pending_post_embed_recovery=has_pending_post_embed_recovery,
            split_ref_overrides=split_ref_overrides,
        )
    finally:
        lock.release()


def _execute_apply_steps_locked(
    ctx: ApplyContext,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    verbose_docker: bool = False,
    *,
    project_generated: bool = False,
    has_pending_post_embed_recovery: bool = False,
    split_ref_overrides: Mapping[str, str] | None = None,
) -> None:
    """Execute the apply steps while holding the advisory lock.

    AF5 Phase 2: When *has_pending_post_embed_recovery* is ``True``, the
    function uses :class:`ApplyExecutor` to determine the first unsatisfied
    step from the recovery ledger's ``resume_checkpoint`` and skips
    already-completed non-destructive steps.  After each step executes, a
    checkpoint is written to the recovery ledger.
    """
    # ------------------------------------------------------------------
    # AF5 Phase 2 — determine resume state
    # ------------------------------------------------------------------
    executor = ApplyExecutor(ctx.output_path)
    _af5_first_step: ApplyStep | None = None

    if has_pending_post_embed_recovery:
        try:
            checkpoint = executor.get_checkpoint()
            _af5_first_step = executor.find_first_unsatisfied_step(checkpoint)
        except LedgerError:
            # Malformed checkpoint — fall back to running from step 1.
            _af5_first_step = None
            click.secho(
                "⚠️  Could not read apply recovery checkpoint. Re-running from step 1.",
                fg="yellow",
            )

    def _should_run(step_order: int) -> bool:
        """Return ``True`` when the step at *step_order* should execute
        (not be skipped by the recovery checkpoint)."""
        if _af5_first_step is None:
            return True
        return step_order >= _af5_first_step.order

    def _checkpoint_step(
        step: ApplyStep,
        *,
        checkpoint_tree_id: str | None = None,
        state_snapshot: QuickScaleState | None = None,
    ) -> None:
        """Write checkpoint progress for a completed step.

        Args:
            step: The step that just completed.
            checkpoint_tree_id: Optional git tree id to seed the
                recovery ledger with the real post-embed checkpoint
                instead of a placeholder (AF5-CR-002).
            state_snapshot: Optional ``QuickScaleState`` snapshot to
                use as the recovery ledger's applied_state (seeds
                real project metadata instead of fallback placeholders).
        """
        try:
            executor.checkpoint_step(
                step,
                checkpoint_tree_id=checkpoint_tree_id,
                state_snapshot=state_snapshot,
            )
        except LedgerError:
            click.secho(
                f"⚠️  Could not write apply checkpoint for step "
                f"'{step.step_id}'. Continuing anyway.",
                fg="yellow",
            )

    # ------------------------------------------------------------------
    # Step 1: Embed modules
    # ------------------------------------------------------------------
    modules_to_embed = (
        ctx.delta.modules_to_add
        if ctx.existing_state
        else list(ctx.qs_config.modules.keys())
    )

    # For existing projects, commit any pending QuickScale config changes
    # (e.g. quickscale.yml updated by `quickscale plan`) before embedding
    # modules, so git subtree has a clean working directory to operate on.
    if ctx.existing_state is not None and modules_to_embed:
        _commit_pending_config_changes(ctx.output_path)

    if split_ref_overrides:
        embed_result = _embed_modules_step(
            ctx.output_path,
            modules_to_embed,
            no_modules,
            ctx.existing_state,
            split_ref_overrides,
        )
    else:
        embed_result = _embed_modules_step(
            ctx.output_path,
            modules_to_embed,
            no_modules,
            ctx.existing_state,
        )
    embedded_modules = embed_result.embedded_modules
    provenance_payloads = embed_result.provenance_payloads

    if not embed_result.success:
        # Persist successful partial embeds (explicit no-rollback contract).
        if not _save_project_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            embedded_modules,
            ctx.delta,
            provenance_payloads=provenance_payloads,
        ):
            _print_apply_failure_summary(
                failed_step=_FAILED_STEP["authoritative state persistence"],
                reason=(
                    f"required module '{embed_result.failed_module}' failed to embed, "
                    "and QuickScale could not save partial authoritative state to "
                    ".quickscale/state.yml."
                ),
            )
            raise click.Abort()
        _clear_apply_recovery_state(ctx.output_path)
        _print_apply_failure_summary(
            failed_step=_FAILED_STEP["module embedding"],
            reason=f"required module '{embed_result.failed_module}' failed to embed",
        )
        raise click.Abort()

    # ------------------------------------------------------------------
    # Step 2a: Post-embed required-module version floor re-validation
    # ------------------------------------------------------------------
    # The pre-embed check in _prepare_apply_context and
    # _refresh_context_after_lock only examines already-installed manifests.
    # After embedding a new module, its manifest may carry version floors
    # that were not visible before embed (e.g. newly added billing requires
    # orgs>=0.86.0 but orgs was already installed at 0.85.0).  Re-validate
    # the full post-embed module set before continuing to wiring, dependency
    # sync, or migration steps.
    if embedded_modules:
        post_embed_manifests = _load_module_manifests(
            ctx.output_path,
            list(ctx.qs_config.modules.keys()),
            strict=True,
        )
        try:
            check_required_module_versions(post_embed_manifests)
        except ManifestError as error:
            # Modules were already embedded — persist partial state
            # before aborting so the operator can inspect or repair.
            if not _save_project_state(
                ctx.output_path,
                ctx.qs_config,
                ctx.existing_state,
                embedded_modules,
                ctx.delta,
                provenance_payloads=provenance_payloads,
            ):
                _print_apply_failure_summary(
                    failed_step=_FAILED_STEP["authoritative state persistence"],
                    reason=(
                        f"Required-module version floor violated after embed: {error}, "
                        "and QuickScale could not save partial authoritative state to "
                        ".quickscale/state.yml."
                    ),
                )
            _clear_apply_recovery_state(ctx.output_path)
            _abort_for_manifest_error(error, command_name="apply")

    # ------------------------------------------------------------------
    # Step 2: Post-embed state snapshot
    # ------------------------------------------------------------------
    # When recovering past step 1, use the recovery ledger's applied_state
    # as the post-embed state and its git_index_checkpoint as the tree id.
    if _should_run(2):
        post_embed_state, checkpoint_tree_id = _exec_step_post_embed_snapshot(
            ctx,
            embedded_modules,
            provenance_payloads,
        )
    else:
        _recovery_ledger = executor.load_ledger()
        if _recovery_ledger is not None:
            post_embed_state = _recovery_ledger.applied_state
            checkpoint_tree_id = _recovery_ledger.git_index_checkpoint
        else:
            # Fallback — should not happen in recovery mode.
            post_embed_state, checkpoint_tree_id = _exec_step_post_embed_snapshot(
                ctx,
                embedded_modules,
                provenance_payloads,
            )

    # Narrow the optional types: the adapter raises click.Abort on failure,
    # so these are always populated past this point.
    assert post_embed_state is not None
    assert checkpoint_tree_id is not None

    # AF5 Phase 2 checkpoint: after step 2, the recovery ledger exists.
    # Write progress for step 1 (if modules were embedded) and step 2.
    # Seed both checkpoints with the real post-embed snapshot and
    # checkpoint_tree_id so the recovery ledger is self-describing
    # and does not carry placeholder state (AF5-CR-002).
    if _should_run(2) and _embed_modules_ran_successfully(embed_result):
        _checkpoint_step(
            APPLY_STEPS[0],
            checkpoint_tree_id=checkpoint_tree_id,
            state_snapshot=post_embed_state,
        )  # step 1 — embed modules
    if _should_run(2) and embedded_modules:
        _checkpoint_step(
            APPLY_STEPS[1],
            checkpoint_tree_id=checkpoint_tree_id,
            state_snapshot=post_embed_state,
        )  # step 2 — post-embed snapshot

    # ------------------------------------------------------------------
    # Step 3: Managed module wiring generation
    # ------------------------------------------------------------------
    if _should_run(3):
        if not _regenerate_managed_wiring_for_apply(ctx, embedded_modules):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["managed module wiring generation"],
                reason="unable to render managed settings, URL, and integration files",
            )
        _checkpoint_step(APPLY_STEPS[2])  # step 3

    # ------------------------------------------------------------------
    # Step 4: Capture managed file hashes
    # ------------------------------------------------------------------
    if _should_run(4):
        step4_outcome = _capture_managed_file_hashes_after_apply(
            ctx.output_path, ctx.qs_config, post_embed_state
        )
        if not step4_outcome.success:
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["capture managed file hashes"],
                reason=str(step4_outcome.message),
            )
        _checkpoint_step(APPLY_STEPS[3])  # step 4

    # ------------------------------------------------------------------
    # Step 5: Backups gitignore hardening
    # ------------------------------------------------------------------
    if _should_run(5):
        if not _ensure_backups_gitignore_rules(ctx.output_path, ctx.qs_config):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["backups gitignore hardening"],
                reason="Unable to update .gitignore with the configured private backups directory.",
            )
        _checkpoint_step(APPLY_STEPS[4])  # step 5

    # ------------------------------------------------------------------
    # Step 6: Notifications env example sync
    # ------------------------------------------------------------------
    if _should_run(6):
        if not _sync_notifications_env_example(ctx.output_path, ctx.qs_config):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["notifications env example sync"],
                reason="Unable to update .env.example with the configured notifications env-var names.",
            )
        _checkpoint_step(APPLY_STEPS[5])  # step 6

    # ------------------------------------------------------------------
    # Step 7: Analytics env example sync
    # ------------------------------------------------------------------
    if _should_run(7):
        if not _sync_analytics_env_example(ctx.output_path, ctx.qs_config):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["analytics env example sync"],
                reason="Unable to update .env.example with the configured analytics env-var names.",
            )
        _checkpoint_step(APPLY_STEPS[6])  # step 7

    # ------------------------------------------------------------------
    # Step 8: Billing env example sync
    # ------------------------------------------------------------------
    if _should_run(8):
        if not _sync_billing_env_example(ctx.output_path, ctx.qs_config):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["billing env example sync"],
                reason="Unable to update .env.example with the configured billing env-var names.",
            )
        _checkpoint_step(APPLY_STEPS[7])  # step 8

    # ------------------------------------------------------------------
    # Step 9: Module dependency sync
    # ------------------------------------------------------------------
    if _should_run(9):
        if not _sync_project_module_dependencies_for_apply(
            ctx.output_path,
            ctx.qs_config,
        ):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["module dependency sync"],
                reason="Unable to reconcile embedded-module Poetry dependency entries in pyproject.toml.",
            )
        _checkpoint_step(APPLY_STEPS[8])  # step 9

    # ------------------------------------------------------------------
    # Step 10: Post-generation dependency setup (no migrations)
    # ------------------------------------------------------------------
    # AF5 Phase 4: Step 10 only handles poetry lock + install.  All
    # migration execution — local, Docker, --no-docker — is deferred
    # to step 13 in the late confirmable phase below.
    should_auto_start_docker = not no_docker and ctx.qs_config.docker.start
    should_run_local_migrations = (ctx.existing_state is not None) and (
        not ctx.qs_config.docker.start or no_docker
    )

    if _should_run(10):
        if not _run_post_generation_steps(
            ctx.output_path,
        ):
            _abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP[
                    "post-generation dependency and migration setup"
                ],
                reason="Poetry lock refresh or dependency installation failed after module dependency sync.",
            )
        _checkpoint_step(APPLY_STEPS[9])  # step 10

    # ------------------------------------------------------------------
    # Late confirmation gate — destructive/remote phase (steps 11-16)
    # ------------------------------------------------------------------
    # AF5 Phase 4: All destructive and remote operations — Docker startup,
    # database migrations (local and Docker), Railway deploy — are grouped
    # into this separately-confirmable phase so the operator can inspect
    # the non-destructive results of steps 1-10 before committing to
    # operations that touch the database, Docker, or external services.
    #
    # When ``_AF5_DESTRUCTIVE_CONFIRM_BYPASS`` is ``True`` (test mode),
    # the gate is silently skipped without printing or prompting.
    if not _AF5_DESTRUCTIVE_CONFIRM_BYPASS:
        click.echo("\n" + "=" * 50)
        click.secho("⚠️  DESTRUCTIVE / REMOTE OPERATIONS AHEAD", fg="red", bold=True)
        click.echo("=" * 50)
        click.echo(
            "\nThe following steps will modify your database and/or external services:"
        )
        click.echo("  • Apply mutable configuration changes")
        if should_auto_start_docker:
            click.echo("  • Start Docker services")
            click.echo("  • Run database migrations (inside Docker backend container)")
        elif should_run_local_migrations:
            click.echo("  • Run database migrations (local)")
        else:
            click.echo("  • Database migrations step (no migration path configured)")
        click.echo("  • Trigger Railway deployment (if Railway-linked)")
        click.echo("  • Finalize authoritative apply state")
        click.echo("  • Display next steps\n")
        if not click.confirm(
            "Proceed with destructive/remote operations?", default=True
        ):
            click.secho(
                "\n❌ Destructive/remote phase cancelled. Steps 1-10 completed successfully.",
                fg="yellow",
            )
            raise click.Abort()

    # ------------------------------------------------------------------
    # Steps 11-16: Destructive/remote operations with per-step
    # checkpointing (AF5 Phase 4).
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step 11: Apply mutable config
    # ------------------------------------------------------------------
    if _should_run(11):
        _exec_step_apply_mutable_config(ctx)
        _checkpoint_step(APPLY_STEPS[10])  # step 11

    # ------------------------------------------------------------------
    # Step 12: Docker startup
    # ------------------------------------------------------------------
    docker_started: bool | None = None
    if _should_run(12):
        if should_auto_start_docker:
            docker_started = _start_docker(
                ctx.output_path, ctx.qs_config.docker.build, verbose_docker
            )
            if not docker_started:
                _abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["docker startup"],
                    reason="Docker auto-start failed. Run 'quickscale logs' to inspect the failing service.",
                )
        _checkpoint_step(APPLY_STEPS[11])  # step 12

    # ------------------------------------------------------------------
    # Step 13: Database migrations (local or Docker)
    # ------------------------------------------------------------------
    # AF5 Phase 4: This single step handles all migration paths.
    # Docker-first projects run migrations inside the container;
    # existing-project and --no-docker paths run local migrations.
    if _should_run(13):
        if should_auto_start_docker and docker_started:
            if not _run_migrations_in_docker(ctx.output_path):
                _abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["database migrations"],
                    reason="Migrations failed inside Docker backend container. Run 'quickscale logs backend' for details.",
                )
        elif should_run_local_migrations:
            if not _run_local_migrations(ctx.output_path):
                _abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["database migrations"],
                    reason="Local database migrations failed. Run 'poetry run python manage.py migrate' manually for details.",
                )
        _checkpoint_step(APPLY_STEPS[12])  # step 13

    # ------------------------------------------------------------------
    # Step 14: Railway deploy
    # ------------------------------------------------------------------
    if _should_run(14):
        _exec_step_railway_deploy(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )
        _checkpoint_step(APPLY_STEPS[13])  # step 14

    # ------------------------------------------------------------------
    # Step 15: Finalize apply state
    # ------------------------------------------------------------------
    # No checkpoint after finalize: the step body already clears the
    # recovery ledger on success.  Writing another checkpoint here
    # would recreate a bogus recovery ledger with placeholder state
    # (AF5-CR-001).
    if _should_run(15):
        _finalize_apply_state(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )

    # ------------------------------------------------------------------
    # Step 16: Display next steps
    # ------------------------------------------------------------------
    # No checkpoint after display: there are no further steps to resume
    # from and writing one would recreate the stale recovery ledger
    # that step 15 just cleared (AF5-CR-001).
    if _should_run(16):
        _display_next_steps(
            ctx.output_path,
            ctx.qs_config,
            no_docker,
            docker_started,
            existing_project=ctx.existing_state is not None,
        )


def _embed_modules_ran_successfully(embed_result: EmbedModulesResult) -> bool:
    """Return ``True`` when modules were actually embedded (not a no-op)."""
    return embed_result.success and bool(embed_result.embedded_modules)


def _resolve_apply_preflight(config_path: Path) -> Path:
    """Validate themes before apply performs any operational mutation."""
    resolve_root = _resolve_apply_raw_root(config_path)
    try:
        validate_theme_preflight(
            resolve_root,
            config_path=config_path,
            defer_config_errors=True,
        )
    except ThemeValidationError as exc:
        _report_theme_preflight_error(exc)
        raise click.Abort() from exc
    return resolve_root


@click.command()
@click.argument(
    "config",
    required=False,
    type=click.Path(exists=True),
    default="quickscale.yml",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing project directory",
)
@click.option(
    "--no-docker",
    is_flag=True,
    help="Skip Docker operations even if configured",
)
@click.option(
    "--no-modules",
    is_flag=True,
    help="Skip module embedding",
)
@click.option(
    "--split-ref",
    "split_refs",
    metavar="MODULE=REF",
    multiple=True,
    help="Use an explicit split ref for each module being embedded (repeatable).",
)
@click.option(
    "--verbose-docker",
    is_flag=True,
    help="Show Docker build output (useful for debugging build issues)",
)
def apply(
    config: str,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    split_refs: tuple[str, ...],
    verbose_docker: bool,
) -> None:
    """
    Execute project configuration from quickscale.yml.

    Generates a Django project based on the configuration file,
    embeds selected modules, and optionally starts Docker services.

    Apply is resumable from the first unsatisfied step when a
    recovery checkpoint exists (``.quickscale/apply-recovery.yml``).
    Steps 11-16 are gated behind a destructive/remote confirmation
    prompt: the operator must explicitly confirm before Docker startup,
    database migrations, Railway deploy, or state finalization proceed.

    \b
    Examples:
      quickscale apply                    # Use quickscale.yml in current dir
      quickscale apply myapp/quickscale.yml  # Use specific config file
      quickscale apply --force            # Overwrite existing project
      quickscale apply --no-docker        # Skip Docker operations
      quickscale apply --verbose-docker   # Show Docker build output

    \b
    Execution Order:
      1. Validate configuration
      2. Generate project (new projects only)
      3. Initialize git + initial commit (new projects only)
      4. Embed modules (fail-fast on required module failure)
      5. Snapshot post-embed state for recovery
      6. Regenerate managed module wiring
      7. Capture managed file hashes
      8. Harden backups gitignore + sync env-example files
      9. Sync embedded-module Poetry dependencies
      10. Refresh poetry.lock + install
      --- destructive/remote phase (operator confirmation required) ---
      11. Apply mutable config changes
      12. Start Docker (if configured)
      13. Run database migrations (Docker or local)
      14. Trigger Railway deploy (if Railway-linked)
      15. Finalize authoritative state
      16. Display next steps
    """
    split_ref_overrides = _parse_split_ref_overrides(split_refs)
    config_path = Path(config)
    _resolve_apply_preflight(config_path)

    # Prepare context
    ctx = _prepare_apply_context(config_path)
    _validate_split_ref_override_coverage(
        ctx,
        split_ref_overrides,
        no_modules=no_modules,
    )

    # Display configuration summary
    _display_config_summary(ctx.qs_config)

    # Probe whether provenance repair might be needed before the no-op gate.
    # The actual repair is deferred to the locked path inside
    # _execute_apply_steps (CR-F26-001).
    has_pending_provenance_repair = _provenance_repair_might_be_needed(ctx)

    # Handle delta and existing state
    _handle_delta_and_existing_state(
        ctx.delta,
        ctx.existing_state,
        has_pending_post_embed_recovery=ctx.has_pending_post_embed_recovery,
        has_pending_provenance_repair=has_pending_provenance_repair,
    )

    # Check output directory
    _check_output_directory(ctx.output_path, ctx.existing_state, force)

    show_docker_output = _confirm_apply(
        ctx,
        no_docker=no_docker,
        verbose_docker=verbose_docker,
    )

    # Execute apply steps
    _execute_apply_steps(
        ctx,
        force,
        no_docker,
        no_modules,
        show_docker_output,
        split_ref_overrides,
    )
