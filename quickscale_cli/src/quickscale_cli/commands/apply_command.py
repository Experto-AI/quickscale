"""Apply command for executing project configuration

Implements `quickscale apply [config]` - executes quickscale.yml configuration
"""

import copy
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

import click
import yaml

from quickscale_cli.analytics_contract import (
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    resolve_analytics_module_options,
    validate_analytics_module_options,
)
from quickscale_cli.backups_contract import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    normalize_backups_module_options,
    sanitize_module_options,
)
from quickscale_cli.notifications_contract import (
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    notifications_live_delivery_configured,
    notifications_production_targeted,
    resolve_notifications_module_options,
    validate_notifications_module_options,
)
from quickscale_cli.module_catalog import (
    find_not_ready_modules,
    get_module_readiness_reason,
)
from quickscale_cli.social_contract import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
    validate_social_module_options,
)
from quickscale_cli.commands.module_commands import embed_module
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
from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_cli.schema.delta import ConfigDelta, compute_delta, format_delta
from quickscale_cli.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)
from quickscale_core.config import (
    load_config as load_module_tracking_config,
    normalize_installed_version,
    save_config as save_module_tracking_config,
)
from quickscale_core.utils.git_utils import is_working_directory_clean
from quickscale_core.generator import ProjectGenerator
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module
from quickscale_core.settings_manager import apply_mutable_config_changes


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


@dataclass(frozen=True)
class _GitIndexSnapshot:
    """Captured git index contents used to restore apply-owned staging."""

    index_path: Path
    contents: bytes | None


_UNSAFE_GITIGNORE_LEADING_CHARACTERS = frozenset({"!", "#"})
_UNSAFE_GITIGNORE_GLOB_CHARACTERS = frozenset({"*", "?", "["})
_APPLY_RECOVERY_FILENAME = "apply-recovery.yml"
_APPLY_RECOVERY_STEM = PurePosixPath(_APPLY_RECOVERY_FILENAME).stem
_PRE_EMBED_AUTHORITATIVE_GIT_PATHS = (
    "quickscale.yml",
    ".quickscale/state.yml",
    ".quickscale/config.yml",
)


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


def _resolve_git_index_path(project_path: Path) -> Path:
    """Resolve the git index path for regular repos and linked worktrees."""
    git_path = project_path / ".git"
    if git_path.is_dir():
        return git_path / "index"

    if git_path.is_file():
        try:
            git_reference = git_path.read_text().strip()
        except OSError:
            return git_path / "index"

        prefix = "gitdir:"
        if git_reference.startswith(prefix):
            git_dir = Path(git_reference[len(prefix) :].strip())
            if not git_dir.is_absolute():
                git_dir = (project_path / git_dir).resolve()
            return git_dir / "index"

    return git_path / "index"


def _capture_git_index_snapshot(project_path: Path) -> _GitIndexSnapshot | None:
    """Capture the current git index so apply can restore it after checkpoint failure."""
    index_path = _resolve_git_index_path(project_path)
    try:
        contents = index_path.read_bytes() if index_path.exists() else None
    except OSError as error:
        click.secho(
            f"❌ Failed to snapshot git index before apply checkpoint: {error}",
            fg="red",
            err=True,
        )
        return None

    return _GitIndexSnapshot(index_path=index_path, contents=contents)


def _restore_git_index_snapshot(snapshot: _GitIndexSnapshot) -> bool:
    """Restore the git index snapshot after an apply-owned checkpoint failure."""
    try:
        if snapshot.contents is None:
            if snapshot.index_path.exists():
                snapshot.index_path.unlink()
            return True

        snapshot.index_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.index_path.write_bytes(snapshot.contents)
        return True
    except OSError as error:
        click.secho(
            f"❌ Failed to restore git index after apply checkpoint failure: {error}",
            fg="red",
            err=True,
        )
        return False


def _restore_failed_apply_checkpoint(snapshot: _GitIndexSnapshot) -> None:
    """Best-effort index restore for failed apply-owned checkpoint commands."""
    if _restore_git_index_snapshot(snapshot):
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
        _restore_failed_apply_checkpoint(snapshot)
        return False

    committed, _ = _run_command(commit_cmd, project_path, commit_description)
    if committed:
        return True

    _restore_failed_apply_checkpoint(snapshot)
    return False


def _run_command(
    cmd: list[str],
    cwd: Path,
    description: str,
    capture: bool = True,
) -> tuple[bool, str]:
    """Run a shell command with progress output

    Args:
        cmd: Command and arguments
        cwd: Working directory
        description: Description for progress output
        capture: Whether to capture output

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
    """Generate project using ProjectGenerator"""
    try:
        click.echo(
            f"⏳ Generating project: {config.project.slug} "
            f"(package: {config.project.package})..."
        )

        generator = ProjectGenerator(theme=config.project.theme)
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


def _embed_module(
    project_path: Path,
    module_name: str,
    skip_auth_migration_check: bool = False,
) -> bool:
    """Embed a module using the embed_module function with non-interactive mode"""
    click.echo(f"⏳ Embedding module: {module_name}...")

    try:
        success = embed_module(
            module=module_name,
            project_path=project_path,
            non_interactive=True,
            allow_unverifiable_auth_state=True,
            skip_auth_migration_check=skip_auth_migration_check,
            sync_dependencies=False,
            install_dependencies=False,
            execution_mode=APPLY_MODULE_EXECUTION_MODE,
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


def _run_poetry_install(project_path: Path) -> bool:
    """Run poetry install in project"""
    return _run_command(
        ["poetry", "install"],
        project_path,
        "Installing dependencies (poetry install)",
    )[0]


def _run_poetry_lock(project_path: Path) -> bool:
    """Refresh the generated project's Poetry lockfile."""
    return _run_command(
        ["poetry", "lock"],
        project_path,
        "Refreshing dependencies (poetry lock)",
    )[0]


def _run_migrations(project_path: Path) -> bool:
    """Run Django migrations"""
    return _run_command(
        ["poetry", "run", "python", "manage.py", "migrate"],
        project_path,
        "Running migrations",
    )[0]


def _run_migrations_in_docker(project_path: Path) -> bool:
    """Run Django migrations inside the backend Docker container."""
    return _run_command(
        ["quickscale", "manage", "migrate"],
        project_path,
        "Running migrations (Docker)",
    )[0]


def _start_docker(
    project_path: Path, build: bool = True, verbose: bool = False
) -> bool:
    """Start Docker services using quickscale up

    Args:
        project_path: Path to the project directory
        build: Whether to build images before starting
        verbose: Whether to show Docker build output (useful for debugging)

    Returns:
        True if Docker started successfully, False otherwise
    """
    cmd = ["quickscale", "up"]
    if build:
        cmd.append("--build")

    if verbose:
        # Show Docker build output for debugging
        click.echo("⏳ Starting Docker services (showing build output)...")
        click.echo("=" * 50)
        try:
            result = subprocess.run(
                cmd,
                cwd=project_path,
                text=True,
                check=False,
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
        )
        return success


def _abort_for_not_ready_modules(module_names: list[str], *, source: str) -> None:
    """Abort apply when placeholder modules appear in config or applied state."""
    not_ready = find_not_ready_modules(module_names)
    if not not_ready:
        return

    click.secho(
        f"\n❌ {source} references placeholder modules that are not ready:",
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


def _apply_mutable_config(
    project_path: Path,
    delta: ConfigDelta,
    manifests: dict[str, ModuleManifest],
) -> bool:
    """Apply mutable configuration changes to settings.py

    Returns True if all changes were applied successfully

    """
    if not delta.has_mutable_config_changes:
        return True

    click.echo("\n⏳ Applying mutable configuration changes...")

    all_success = True
    for module_name, change in delta.get_all_mutable_changes():
        if change.django_setting:
            results = apply_mutable_config_changes(
                project_path, module_name, {change.django_setting: change.new_value}
            )
            for setting_name, success, message in results:
                if success:
                    click.secho(f"  ✅ {message}", fg="green")
                else:
                    click.secho(f"  ❌ {message}", fg="red")
                    all_success = False

    if all_success:
        click.secho("✅ Mutable configuration changes applied", fg="green")

    return all_success


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

    click.echo("\n💡 To change immutable options:")
    modules_with_immutable = set(
        module_name for module_name, _ in delta.get_all_immutable_changes()
    )
    for module_name in modules_with_immutable:
        click.echo(f"   1. quickscale remove {module_name}")
        click.echo("   2. Update quickscale.yml with new options")
        click.echo("   3. quickscale apply")
        click.echo()

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

    click.echo("\n💡 Use the explicit remove workflow instead:")
    for module_name in delta.modules_to_remove:
        click.echo(f"   1. quickscale remove {module_name}")
    click.echo("   2. Re-run quickscale apply")
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
    for module_name, module_delta in delta.config_deltas.items():
        if module_delta.has_mutable_changes and module_name in state.modules:
            # Update options with new values
            current_options = state.modules[module_name].options or {}
            for change in module_delta.mutable_changes:
                current_options[change.option_name] = change.new_value
            state.modules[module_name].options = sanitize_module_options(
                module_name,
                current_options,
            )


def _sync_legacy_module_config_versions(
    project_path: Path,
    state: QuickScaleState,
) -> None:
    """Mirror normalized state versions into legacy module tracking for compatibility."""
    legacy_config = load_module_tracking_config(project_path)
    changed = False

    for module_name, module_state in state.modules.items():
        if module_name not in legacy_config.modules:
            continue

        normalized_version = normalize_installed_version(module_state.version)
        if normalized_version is None:
            continue

        if legacy_config.modules[module_name].installed_version != normalized_version:
            legacy_config.modules[module_name].installed_version = normalized_version
            changed = True

    if changed:
        save_module_tracking_config(legacy_config, project_path)
        click.secho("✅ Updated .quickscale/config.yml module versions", fg="green")


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
        _sanitize_loaded_module_configs(qs_config)
        normalized_yaml = generate_yaml(qs_config)
        normalized_data = yaml.safe_load(normalized_yaml) or {}
        normalized_modules = normalized_data.get("modules") or {}
        if normalized_modules != original_modules:
            config_path.write_text(normalized_yaml)
            click.secho(
                "✅ Sanitized legacy module config keys in quickscale.yml",
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
    _abort_for_not_ready_modules(
        list(qs_config.modules.keys()), source="quickscale.yml"
    )

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


def _sync_notifications_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Keep `.env.example` aligned with the notifications env-var names."""
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


def _sync_analytics_env_example(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Keep `.env.example` aligned with analytics env-var names and scope."""
    analytics_config = qs_config.modules.get("analytics")
    env_example_path = output_path / ".env.example"
    if not env_example_path.exists():
        return True

    start_marker = "# QuickScale Analytics (managed)"
    end_marker = "# End QuickScale Analytics"

    try:
        content = env_example_path.read_text()
    except OSError as e:
        click.secho(
            f"⚠️  Failed to read .env.example for analytics wiring: {e}",
            fg="yellow",
        )
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
    except OSError as e:
        click.secho(
            f"⚠️  Failed to update .env.example for analytics wiring: {e}",
            fg="yellow",
        )
        return False

    if rendered_block is None:
        click.secho("✅ Removed analytics env vars from .env.example", fg="green")
    else:
        click.secho("✅ Updated .env.example with analytics env vars", fg="green")
    return True


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
    """Ensure custom backups directories are ignored safely in git."""
    backups_config = qs_config.modules.get("backups")
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

    gitignore_path = project_path / ".gitignore"
    try:
        existing = gitignore_path.read_text() if gitignore_path.exists() else ""
    except OSError as error:
        click.secho(
            f"❌ Failed to read .gitignore for backups hardening: {error}",
            fg="red",
            err=True,
        )
        return False

    existing_entries = {line.strip() for line in existing.splitlines() if line.strip()}
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


def _handle_delta_and_existing_state(
    delta: ConfigDelta,
    existing_state: QuickScaleState | None,
    *,
    has_pending_post_embed_recovery: bool = False,
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

    if force:
        for item in output_path.iterdir():
            if item.name != "quickscale.yml":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    temp_dir = Path(tempfile.mkdtemp())
    temp_project = temp_dir / qs_config.project.slug

    if not _generate_project(qs_config, temp_project):
        shutil.rmtree(temp_dir)
        raise click.Abort()

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
) -> EmbedModulesResult:
    """Embed modules with fail-fast semantics."""
    embedded_modules: list[str] = []

    if no_modules or not modules_to_embed:
        if existing_state and not modules_to_embed:
            click.echo("⏭️  No new modules to embed")
        return EmbedModulesResult(success=True, embedded_modules=embedded_modules)

    skip_auth_migration_check = existing_state is None

    for module_name in modules_to_embed:
        if not _embed_module(
            output_path,
            module_name,
            skip_auth_migration_check=skip_auth_migration_check,
        ):
            if not is_working_directory_clean(output_path):
                if not _git_commit(
                    output_path,
                    f"Partial module: {module_name} (incomplete)",
                ):
                    click.secho(
                        "\n❌ Cannot continue 'quickscale apply' because QuickScale could not create the partial module checkpoint commit after embedding failed.",
                        fg="red",
                        err=True,
                    )
                    raise click.Abort()
            click.secho(
                f"❌ Module embedding failed for required module: {module_name}",
                fg="red",
                err=True,
            )
            return EmbedModulesResult(
                success=False,
                embedded_modules=embedded_modules,
                failed_module=module_name,
            )

        if not _git_commit(output_path, f"Add module: {module_name}"):
            click.secho(
                f"\n❌ Cannot continue 'quickscale apply' because QuickScale could not create the checkpoint commit for embedded module '{module_name}'.",
                fg="red",
                err=True,
            )
            raise click.Abort()

        embedded_modules.append(module_name)

    return EmbedModulesResult(success=True, embedded_modules=embedded_modules)


def _run_post_generation_steps(output_path: Path, run_migrations: bool = True) -> bool:
    """Refresh the lockfile, install dependencies, and optionally run migrations."""
    if not _run_poetry_lock(output_path):
        return False

    if not _run_poetry_install(output_path):
        return False

    if run_migrations and not _run_migrations(output_path):
        return False

    return True


def _sync_project_module_dependencies_for_apply(
    output_path: Path,
    qs_config: QuickScaleConfig,
) -> bool:
    """Sync missing module dependency entries into the generated project pyproject."""
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


def _build_project_state_snapshot(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
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
                created_at=timestamp,
                last_applied=timestamp,
            ),
            modules={},
        )
    else:
        new_state = copy.deepcopy(existing_state)
        new_state.project.last_applied = timestamp

    for module_name in embedded_modules:
        if module_name not in qs_config.modules:
            continue

        existing_module_state = new_state.modules.get(module_name)
        new_state.modules[module_name] = ModuleState(
            name=module_name,
            version=existing_module_state.version if existing_module_state else None,
            commit_sha=(
                existing_module_state.commit_sha if existing_module_state else None
            ),
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

    return new_state


def _get_apply_recovery_state_manager(project_path: Path) -> StateManager:
    """Return a state manager bound to the post-embed recovery snapshot."""
    recovery_manager = StateManager(project_path)
    recovery_manager.state_file = recovery_manager.state_dir / _APPLY_RECOVERY_FILENAME
    return recovery_manager


def _load_apply_recovery_state(project_path: Path) -> QuickScaleState | None:
    """Load any pending post-embed recovery snapshot."""
    return _get_apply_recovery_state_manager(project_path).load()


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
) -> bool:
    """Persist retry context for failures that happen after embedding succeeded."""
    try:
        recovery_state = _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
        )
        recovery_manager = _get_apply_recovery_state_manager(output_path)
        recovery_manager.save(recovery_state)
        click.secho(
            f"✅ Apply recovery saved to .quickscale/{_APPLY_RECOVERY_FILENAME}",
            fg="green",
        )
        return True
    except Exception as e:
        click.secho(
            f"❌ Failed to save apply recovery state: {e}",
            fg="red",
            err=True,
        )
        return False


def _clear_apply_recovery_state(output_path: Path) -> None:
    """Remove any stale post-embed recovery snapshot."""
    recovery_path = _get_apply_recovery_state_manager(output_path).state_file
    if not recovery_path.exists():
        return

    try:
        recovery_path.unlink()
    except OSError as e:
        click.secho(f"⚠️  Failed to clear apply recovery state: {e}", fg="yellow")


def _save_project_state(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
) -> bool:
    """Save project state to .quickscale/state.yml."""
    try:
        state_manager = StateManager(output_path)
        new_state = _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
        )

        state_manager.save(new_state)
        click.secho("✅ State saved to .quickscale/state.yml", fg="green")
        try:
            _sync_legacy_module_config_versions(output_path, new_state)
        except Exception as e:
            click.secho(
                f"⚠️  Failed to mirror module versions into .quickscale/config.yml: {e}",
                fg="yellow",
            )
        return True
    except Exception as e:
        click.secho(f"❌ Failed to save state: {e}", fg="red", err=True)
        return False


def _display_next_steps(
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
        click.echo("  # Or run without Docker:")
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
            "  showcase_html and existing generated projects only receive the managed "
            "backend transport automatically; use manual theme adoption if you want "
            "those public pages."
        )

    click.echo("\n  Visit: http://localhost:8000")


def _prepare_apply_context(config_path: Path) -> ApplyContext:
    """Prepare all context needed for apply execution.

    Returns:
        ApplyContext with all loaded and computed data
    """
    # Load and validate configuration
    qs_config = _load_and_validate_config(config_path)

    # Determine output path
    output_path = _determine_output_path(config_path, qs_config.project.slug)

    # Load existing state if project exists
    state_manager = StateManager(output_path)
    try:
        authoritative_state = state_manager.load() if output_path.exists() else None
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
    """Regenerate managed module wiring files after embed/config changes."""
    desired_module_names = sorted(ctx.qs_config.modules.keys())
    if ctx.existing_state is None:
        selected_modules = embedded_modules
    else:
        # Existing state may include unchanged modules that should remain wired.
        selected_modules = sorted(
            set(ctx.delta.modules_unchanged) | set(embedded_modules)
        )

    # If no desired modules are configured, explicitly render empty managed files.
    if not desired_module_names:
        selected_modules = []

    options = {
        module_name: module_config.options
        for module_name, module_config in ctx.qs_config.modules.items()
    }

    success, message = regenerate_managed_wiring(
        ctx.output_path,
        module_names=selected_modules,
        option_overrides=options,
        project_package=ctx.qs_config.project.package,
    )
    if success:
        click.secho("✅ Managed module wiring regenerated", fg="green")
        return True

    click.secho(f"❌ Managed wiring regeneration failed: {message}", fg="red", err=True)
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
    click.echo("  • migrations")
    click.echo("  • docker start")
    click.echo("  • success completion output")


def _abort_after_post_embed_failure(
    ctx: ApplyContext,
    embedded_modules: list[str],
    *,
    failed_step: str,
    reason: str,
) -> None:
    """Persist rerunnable recovery state before aborting post-embed failures."""
    if _save_apply_recovery_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        embedded_modules,
        ctx.delta,
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
    embedded_modules: list[str],
) -> None:
    """Persist authoritative state and keep rerun recovery if it fails."""
    if _save_project_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        embedded_modules,
        ctx.delta,
    ):
        _clear_apply_recovery_state(ctx.output_path)
        return

    recovery_saved = _save_apply_recovery_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        embedded_modules,
        ctx.delta,
    )
    if recovery_saved:
        _print_apply_failure_summary(
            failed_step="authoritative state persistence",
            reason=(
                "All apply steps completed, but QuickScale could not save "
                ".quickscale/state.yml. Recovery state was saved to "
                f".quickscale/{_APPLY_RECOVERY_FILENAME} so apply remains rerunnable."
            ),
        )
        raise click.Abort()

    _print_apply_failure_summary(
        failed_step="authoritative state persistence",
        reason=(
            "All apply steps completed, but QuickScale could not save "
            ".quickscale/state.yml and could not preserve rerunnable recovery state "
            f"in .quickscale/{_APPLY_RECOVERY_FILENAME}."
        ),
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


def _execute_apply_steps(
    ctx: ApplyContext,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    verbose_docker: bool = False,
) -> None:
    """Execute the apply steps after confirmation."""
    click.echo("\n" + "=" * 50)
    click.echo("🔧 Starting apply process...")
    click.echo("=" * 50)

    has_pending_post_embed_recovery = _context_has_pending_post_embed_recovery(ctx)

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

    # Embed modules
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

    embed_result = _embed_modules_step(
        ctx.output_path, modules_to_embed, no_modules, ctx.existing_state
    )
    embedded_modules = embed_result.embedded_modules

    if not embed_result.success:
        # Persist successful partial embeds (explicit no-rollback contract).
        if not _save_project_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            embedded_modules,
            ctx.delta,
        ):
            _print_apply_failure_summary(
                failed_step="authoritative state persistence",
                reason=(
                    f"required module '{embed_result.failed_module}' failed to embed, "
                    "and QuickScale could not save partial authoritative state to "
                    ".quickscale/state.yml."
                ),
            )
            raise click.Abort()
        _clear_apply_recovery_state(ctx.output_path)
        _print_apply_failure_summary(
            failed_step="module embedding",
            reason=f"required module '{embed_result.failed_module}' failed to embed",
        )
        raise click.Abort()

    # Deterministic managed wiring generation for selected modules.
    if not _regenerate_managed_wiring_for_apply(ctx, embedded_modules):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="managed module wiring generation",
            reason="unable to render managed settings, URL, and integration files",
        )

    if not _ensure_backups_gitignore_rules(ctx.output_path, ctx.qs_config):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="backups gitignore hardening",
            reason="Unable to update .gitignore with the configured private backups directory.",
        )

    if not _sync_notifications_env_example(ctx.output_path, ctx.qs_config):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="notifications env example sync",
            reason="Unable to update .env.example with the configured notifications env-var names.",
        )

    if not _sync_analytics_env_example(ctx.output_path, ctx.qs_config):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="analytics env example sync",
            reason="Unable to update .env.example with the configured analytics env-var names.",
        )

    if not _sync_project_module_dependencies_for_apply(
        ctx.output_path,
        ctx.qs_config,
    ):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="module dependency sync",
            reason="Unable to reconcile embedded-module Poetry dependency entries in pyproject.toml.",
        )

    should_auto_start_docker = not no_docker and ctx.qs_config.docker.start

    # Run post-generation steps. Defer migrations until after Docker startup
    # when auto-start is enabled, so PostgreSQL is reachable.
    if not _run_post_generation_steps(
        ctx.output_path,
        run_migrations=not should_auto_start_docker,
    ):
        _abort_after_post_embed_failure(
            ctx,
            embedded_modules,
            failed_step="post-generation dependency and migration setup",
            reason="Poetry lock refresh, dependency installation, or local migrations failed after module dependency sync.",
        )

    # Apply mutable configuration changes
    if ctx.existing_state and ctx.delta.has_mutable_config_changes:
        click.secho(
            "✅ Mutable configuration changes applied via managed wiring",
            fg="green",
        )

    # Start Docker
    docker_started: bool | None = None
    if should_auto_start_docker:
        docker_started = _start_docker(
            ctx.output_path, ctx.qs_config.docker.build, verbose_docker
        )
        if not docker_started:
            _abort_after_post_embed_failure(
                ctx,
                embedded_modules,
                failed_step="docker startup",
                reason="Docker auto-start failed. Run 'quickscale logs' to inspect the failing service.",
            )

    # For Docker auto-start projects, run migrations in the backend container
    # so database connectivity uses the internal Docker network.
    if should_auto_start_docker:
        if docker_started:
            if not _run_migrations_in_docker(ctx.output_path):
                _abort_after_post_embed_failure(
                    ctx,
                    embedded_modules,
                    failed_step="database migrations",
                    reason="Migrations failed inside Docker backend container. Run 'quickscale logs backend' for details.",
                )

    # Save state
    _finalize_apply_state(ctx, embedded_modules)

    # Display next steps
    _display_next_steps(
        ctx.output_path,
        ctx.qs_config,
        no_docker,
        docker_started,
        existing_project=(
            _context_had_existing_state(ctx)
            or (ctx.existing_state is not None and not has_pending_post_embed_recovery)
        ),
    )


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
    "--verbose-docker",
    is_flag=True,
    help="Show Docker build output (useful for debugging build issues)",
)
def apply(
    config: str, force: bool, no_docker: bool, no_modules: bool, verbose_docker: bool
) -> None:
    """
    Execute project configuration from quickscale.yml.

    Generates a Django project based on the configuration file,
    embeds selected modules, and optionally starts Docker services.

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
      2. Generate project
      3. Initialize git + initial commit
      4. Embed modules (if configured, fail-fast on required module failure)
      5. Regenerate managed module wiring files
    6. Refresh poetry.lock + run poetry install
      7. Start Docker (if configured)
      8. Run migrations (after Docker auto-start when enabled)
    """
    # Prepare context
    ctx = _prepare_apply_context(Path(config))

    # Display configuration summary
    _display_config_summary(ctx.qs_config)

    # Handle delta and existing state
    _handle_delta_and_existing_state(
        ctx.delta,
        ctx.existing_state,
        has_pending_post_embed_recovery=ctx.has_pending_post_embed_recovery,
    )

    # Check output directory
    _check_output_directory(ctx.output_path, ctx.existing_state, force)

    # Ask about Docker build output visibility if Docker will be started
    show_docker_output = verbose_docker
    if (
        not no_docker
        and ctx.qs_config.docker.start
        and ctx.qs_config.docker.build
        and not verbose_docker
    ):
        show_docker_output = click.confirm(
            "\n🐳 Show Docker build output? (useful for debugging build issues)",
            default=False,
        )

    # Confirm before proceeding
    if not click.confirm("\n❓ Proceed with apply?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    # Execute apply steps
    _execute_apply_steps(ctx, force, no_docker, no_modules, show_docker_output)
