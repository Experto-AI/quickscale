"""Status command for showing project state

Implements `quickscale status` - displays current vs desired state and project info
"""

import subprocess
from pathlib import Path

import click
import yaml

from quickscale_cli.module_catalog import (
    find_not_ready_modules,
    get_module_readiness_reason,
)
from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    QuickScaleConfig,
    validate_config,
)
from quickscale_cli.schema.delta import compute_delta, format_delta
from quickscale_cli.schema.state_schema import QuickScaleState, StateError, StateManager
from quickscale_core.config import ConfigError
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module
from quickscale_core.project_state import (
    FILE_HASHES_FILENAME,
    ProjectStateManager,
    check_version_drift,
)


def _get_docker_status() -> dict[str, str] | None:
    """Get Docker container status if running

    Returns:
        Dictionary with container names and status, or None if Docker not available

    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "{{.Name}}: {{.Status}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            status = {}
            for line in result.stdout.strip().splitlines():
                if ": " in line:
                    name, state = line.split(": ", 1)
                    status[name] = state
            return status if status else None
    except FileNotFoundError:
        pass
    return None


def _format_datetime(iso_string: str) -> str:
    """Format ISO datetime string for display"""
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_string


def _detect_project_context() -> tuple[Path | None, Path | None, Path | None]:
    """Detect project context from current directory

    Returns:
        Tuple of (project_path, config_path, state_path) - any may be None

    """
    cwd = Path.cwd()

    # Check for quickscale.yml in current directory
    config_path = cwd / "quickscale.yml"
    state_path = cwd / ".quickscale" / "state.yml"

    if config_path.exists() or state_path.exists():
        return (
            cwd,
            config_path if config_path.exists() else None,
            state_path if state_path.exists() else None,
        )

    # Not in a QuickScale project
    return None, None, None


def _load_config(config_path: Path) -> QuickScaleConfig | None:
    """Load and validate quickscale.yml"""
    yaml_content = config_path.read_text()
    return validate_config(yaml_content)


def _load_module_manifests(
    project_path: Path,
    module_names: list[str],
    *,
    strict: bool = False,
) -> dict[str, ModuleManifest]:
    """Load manifests for installed modules

    Args:
        project_path: Path to the project root
        module_names: List of module names to load manifests for

    Returns:
        Dictionary mapping module names to their manifests

    """
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


def _abort_for_not_ready_modules(module_names: list[str], *, source: str) -> None:
    """Abort status when non-public-ready modules appear in config or applied state."""
    not_ready = find_not_ready_modules(module_names)
    if not not_ready:
        return

    click.secho(
        f"\n❌ Unsupported non-public-ready module state detected in {source}:",
        fg="red",
        err=True,
        bold=True,
    )
    for module_name in not_ready:
        reason = get_module_readiness_reason(module_name)
        if reason is not None:
            click.echo(f"  • {reason}", err=True)

    guidance = (
        "\n💡 Resolve the non-public-ready module state above before running "
        "'quickscale status' again."
    )

    click.echo(guidance, err=True)
    raise click.Abort()


def _abort_for_manifest_error(error: ManifestError) -> None:
    """Abort status with an actionable manifest validation message."""
    click.secho(
        "\n❌ Installed module manifest error during 'status':",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo(f"  • {error}", err=True)
    click.echo(
        "\n💡 Fix the embedded module.yml or remove and re-embed the affected "
        "module before running 'quickscale status' again.",
        err=True,
    )
    raise click.Abort()


def _display_project_info(state: QuickScaleState) -> None:
    """Display project information from state"""
    click.echo("\n📁 Project Information:")
    click.echo(f"   Slug: {state.project.slug}")
    click.echo(f"   Package: {state.project.package}")
    click.echo(f"   Theme: {state.project.theme}")
    click.echo(f"   Created: {_format_datetime(state.project.created_at)}")
    click.echo(f"   Last Applied: {_format_datetime(state.project.last_applied)}")


def _display_modules(state: QuickScaleState) -> None:
    """Display applied modules from state"""
    click.echo("\n📦 Applied Modules:")
    if not state.modules:
        click.echo("   (none)")
        return

    for name, module in state.modules.items():
        version_str = f"v{module.version}" if module.version else "unknown"
        embedded_at = (
            _format_datetime(module.embedded_at) if module.embedded_at else "unknown"
        )
        click.echo(f"   • {name} ({version_str}) - embedded {embedded_at}")


def _display_pending_changes(
    config: QuickScaleConfig | None,
    state: QuickScaleState | None,
    manifests: dict[str, ModuleManifest] | None = None,
) -> None:
    """Display pending changes between config and state"""
    if config is None:
        return

    delta = compute_delta(config, state, manifests)

    if delta.has_changes:
        click.echo("\n⚡ Pending Changes:")
        change_summary = format_delta(delta)
        for line in change_summary.splitlines():
            click.echo(f"   {line}")
        click.echo("\n💡 Run 'quickscale apply' to apply these changes")
    else:
        click.secho("\n✅ Configuration matches applied state", fg="green")


def _display_docker_status() -> None:
    """Display Docker container status if available"""
    status = _get_docker_status()

    if status is None:
        return

    click.echo("\n🐳 Docker Status:")
    for name, state in status.items():
        # Determine color based on status
        if "Up" in state or "running" in state.lower():
            color = "green"
        elif "Exited" in state or "stopped" in state.lower():
            color = "yellow"
        else:
            color = "white"
        click.secho(f"   • {name}: {state}", fg=color)


def _display_drift_warnings(state_manager: StateManager) -> None:
    """Display warnings about state/filesystem drift"""
    drift = state_manager.verify_filesystem()

    if drift["orphaned_modules"]:
        click.echo("\n⚠️  Orphaned Modules (in filesystem but not in state):")
        for module in drift["orphaned_modules"]:
            click.secho(f"   • {module}", fg="yellow")
        click.echo("   These modules may have been manually added.")

    if drift["missing_modules"]:
        click.echo("\n⚠️  Missing Modules (in state but not in filesystem):")
        for module in drift["missing_modules"]:
            click.secho(f"   • {module}", fg="red")
        click.echo("   These modules may have been manually removed.")


def _display_managed_file_drift_warnings(
    project_state_manager: ProjectStateManager,
) -> None:
    """Display warnings about managed wiring files that drifted since apply."""
    drifted = project_state_manager.detect_managed_file_drift()
    if not drifted:
        return

    click.echo("\n⚠️  Managed file drift detected (file changed since last apply):")
    for record in drifted:
        click.secho(
            f"   • {record.path} (expected hash {record.hash[:12]}…)",
            fg="yellow",
        )
    click.echo(
        "   These managed files were modified after the last 'quickscale apply'. "
        "Re-run apply to restore them, or commit your edits if they are intentional."
    )


def _display_version_drift_warnings(
    project_state_manager: ProjectStateManager,
) -> None:
    """Display warnings about module version drift between state and config."""
    try:
        state = project_state_manager.load_state()
        config = project_state_manager.load_config()
    except (ConfigError, StateError, OSError) as error:
        click.echo(
            f"\n⚠️  Could not check version drift between .quickscale/state.yml "
            f"and .quickscale/config.yml: {error}"
        )
        return

    drift = check_version_drift(state, config)
    if not drift:
        return

    click.echo(
        "\n⚠️  Module version drift between .quickscale/state.yml and "
        ".quickscale/config.yml:"
    )
    for warning in drift:
        click.secho(f"   • {warning.message}", fg="yellow")
    click.echo(
        "   Apply will reconcile .quickscale/config.yml to the canonical state version."
    )


def _state_file_has_consolidated_sections(state_dir: Path) -> bool:
    """Check whether ``state.yml`` on disk has consolidated sections.

    Returns True when the state file exists and contains either the
    ``managed_files`` section or modules with consolidated tracking
    fields (``prefix``/``branch``/``installed_at``).
    """
    state_file = state_dir / "state.yml"
    if not state_file.exists():
        return False
    try:
        with open(state_file) as handle:
            data = yaml.safe_load(handle) or {}
    except (yaml.YAMLError, OSError):
        return False

    if not isinstance(data, dict):
        return False

    if "managed_files" in data:
        return True

    modules_data = data.get("modules", {})
    if isinstance(modules_data, dict):
        for _name, info in modules_data.items():
            if isinstance(info, dict) and (
                "prefix" in info or "branch" in info or "installed_at" in info
            ):
                return True

    return False


def _compute_drift_diagnostics(
    project_path: Path,
    state: QuickScaleState | None,
    project_state_manager: ProjectStateManager,
    state_manager: StateManager,
) -> dict:
    """Compute M2 drift and compatibility diagnostics.

    Returns a dictionary suitable for both text display and JSON serialization.
    The diagnostics cover:

    * ``state_consolidated`` — whether ``state.yml`` on disk carries the
      consolidated sections (``managed_files`` or module tracking fields).
    * ``legacy_files_present`` — which legacy files exist on disk.
    * ``legacy_compat_active`` — whether read-through import from legacy
      files is active (consolidated sections absent and legacy files present).
    * ``module_tracking`` — per-module consolidated tracking status.
    * ``managed_files_consolidated`` — whether the ``managed_files`` section
      is populated in state.
    * ``filesystem_drift`` — orphaned and missing modules.
    * ``managed_file_drift`` — managed files that drifted since last apply.
    * ``version_drift`` — version disagreements between state and config.
    """
    state_dir = project_path / ".quickscale"
    consolidated_on_disk = _state_file_has_consolidated_sections(state_dir)

    # Check which legacy files exist on disk.
    legacy_files_present: list[str] = []
    config_yml = state_dir / "config.yml"
    file_hashes_yml = state_dir / FILE_HASHES_FILENAME
    if config_yml.exists():
        legacy_files_present.append("config.yml")
    if file_hashes_yml.exists():
        legacy_files_present.append(FILE_HASHES_FILENAME)

    legacy_compat_active = (not consolidated_on_disk) and bool(legacy_files_present)

    # Module tracking completeness.
    modules = state.modules if state else {}
    module_tracking_total = len(modules)
    modules_needing_consolidation: list[str] = []
    for name, mod in modules.items():
        if not mod.has_consolidated_tracking:
            modules_needing_consolidation.append(name)
    module_tracking_consolidated = module_tracking_total - len(
        modules_needing_consolidation
    )

    # Managed files consolidation.
    managed_files_consolidated = bool(state and state.managed_files)

    # Filesystem drift (orphaned/missing modules).
    fs_drift = state_manager.verify_filesystem()

    # Managed file drift.
    managed_drift_records = project_state_manager.detect_managed_file_drift()
    managed_file_drift = [
        {"path": r.path, "expected_hash": r.hash} for r in managed_drift_records
    ]

    # Version drift between state and config.
    try:
        loaded_state = project_state_manager.load_state()
        loaded_config = project_state_manager.load_config()
    except (ConfigError, StateError, OSError):
        loaded_state = None
        loaded_config = None

    version_warnings = check_version_drift(loaded_state, loaded_config)
    version_drift = [
        {
            "module": w.module,
            "state_version": w.state_version,
            "config_version": w.config_version,
        }
        for w in version_warnings
    ]

    return {
        "state_consolidated": consolidated_on_disk,
        "legacy_files_present": legacy_files_present,
        "legacy_compat_active": legacy_compat_active,
        "module_tracking": {
            "total": module_tracking_total,
            "consolidated": module_tracking_consolidated,
            "needs_consolidation": sorted(modules_needing_consolidation),
        },
        "managed_files_consolidated": managed_files_consolidated,
        "filesystem_drift": {
            "orphaned_modules": sorted(fs_drift.get("orphaned_modules", [])),
            "missing_modules": sorted(fs_drift.get("missing_modules", [])),
        },
        "managed_file_drift": managed_file_drift,
        "version_drift": version_drift,
    }


def _display_drift_diagnostics(diagnostics: dict) -> None:
    """Display M2 drift and compatibility diagnostics in text format."""
    click.echo("\n🔍 M2 Drift & Compatibility:")

    # State consolidation status.
    if diagnostics["state_consolidated"]:
        click.secho("   State consolidation: ✅ consolidated", fg="green")
    else:
        click.secho(
            "   State consolidation: ⚠️  legacy mode (read-through import active)",
            fg="yellow",
        )

    # Legacy files on disk.
    legacy = diagnostics["legacy_files_present"]
    if legacy:
        if diagnostics["legacy_compat_active"]:
            click.secho(
                f"   Legacy files on disk: {', '.join(legacy)} (active compatibility inputs)",
                fg="yellow",
            )
        else:
            click.echo(
                f"   Legacy files on disk: {', '.join(legacy)} (ignored — consolidated)"
            )
    else:
        click.echo("   Legacy files on disk: none")

    # Module tracking completeness.
    mt = diagnostics["module_tracking"]
    if mt["total"] == 0:
        click.echo("   Module tracking: (no modules)")
    elif mt["needs_consolidation"]:
        click.secho(
            f"   Module tracking: {mt['consolidated']}/{mt['total']} consolidated"
            f" — needs consolidation: {', '.join(mt['needs_consolidation'])}",
            fg="yellow",
        )
    else:
        click.secho(
            f"   Module tracking: {mt['consolidated']}/{mt['total']} fully consolidated",
            fg="green",
        )

    # Managed files consolidation.
    if diagnostics["managed_files_consolidated"]:
        click.secho("   Managed files: ✅ consolidated in state.yml", fg="green")
    else:
        if FILE_HASHES_FILENAME in diagnostics["legacy_files_present"]:
            click.secho(
                f"   Managed files: ⚠️  using legacy {FILE_HASHES_FILENAME}",
                fg="yellow",
            )
        else:
            click.echo("   Managed files: no records")

    # Filesystem drift.
    fs = diagnostics["filesystem_drift"]
    orphaned = fs["orphaned_modules"]
    missing = fs["missing_modules"]
    if not orphaned and not missing:
        click.secho("   Filesystem drift: ✅ clean", fg="green")
    else:
        parts: list[str] = []
        if orphaned:
            parts.append(f"{len(orphaned)} orphaned ({', '.join(orphaned)})")
        if missing:
            parts.append(f"{len(missing)} missing ({', '.join(missing)})")
        click.secho(f"   Filesystem drift: ⚠️  {'; '.join(parts)}", fg="yellow")

    # Managed file drift.
    mf_drift = diagnostics["managed_file_drift"]
    if not mf_drift:
        click.secho("   Managed file drift: ✅ clean", fg="green")
    else:
        paths = ", ".join(r["path"] for r in mf_drift)
        click.secho(
            f"   Managed file drift: ⚠️  {len(mf_drift)} drifted ({paths})",
            fg="yellow",
        )

    # Version drift.
    vd = diagnostics["version_drift"]
    if not vd:
        click.secho("   Version drift: ✅ clean", fg="green")
    else:
        modules_str = ", ".join(w["module"] for w in vd)
        click.secho(
            f"   Version drift: ⚠️  {len(vd)} disagreement(s) ({modules_str})",
            fg="yellow",
        )


def _build_json_output(
    project_path: Path,
    config_path: Path | None,
    state: QuickScaleState | None,
    config: QuickScaleConfig | None,
    manifests: dict[str, ModuleManifest] | None = None,
    drift_diagnostics: dict | None = None,
) -> dict:
    """Build JSON output for status command."""

    output: dict = {
        "project_path": str(project_path),
        "has_config": config_path is not None and config_path.exists(),
        "has_state": state is not None,
    }

    if state:
        output["state"] = {
            "version": state.version,
            "project": {
                "slug": state.project.slug,
                "package": state.project.package,
                "theme": state.project.theme,
                "created_at": state.project.created_at,
                "last_applied": state.project.last_applied,
            },
            "modules": {
                name: {
                    "version": module.version,
                    "commit_sha": module.commit_sha,
                    "embedded_at": module.embedded_at,
                }
                for name, module in state.modules.items()
            },
        }

    if config:
        output["config"] = {
            "version": config.version,
            "project": {
                "slug": config.project.slug,
                "package": config.project.package,
                "theme": config.project.theme,
            },
            "modules": list(config.modules.keys()),
            "docker": {
                "start": config.docker.start,
                "build": config.docker.build,
            },
        }

        delta = compute_delta(config, state, manifests)
        output["pending_changes"] = {
            "has_changes": delta.has_changes,
            "modules_to_add": delta.modules_to_add,
            "modules_to_remove": delta.modules_to_remove,
            "modules_unchanged": delta.modules_unchanged,
            "theme_changed": delta.theme_changed,
        }

    docker_status = _get_docker_status()
    if docker_status:
        output["docker"] = docker_status

    # Phase 4: include explicit drift/compatibility diagnostics.
    if drift_diagnostics is not None:
        output["drift"] = drift_diagnostics

    return output


def _display_text_status(
    project_path: Path,
    state: QuickScaleState | None,
    config: QuickScaleConfig | None,
    config_path: Path | None,
    state_path: Path | None,
    state_manager: StateManager,
    project_state_manager: ProjectStateManager,
    manifests: dict[str, ModuleManifest] | None = None,
    drift_diagnostics: dict | None = None,
) -> None:
    """Display status in text format."""
    # Display header
    click.echo("\n🔍 QuickScale Project Status")
    click.echo("=" * 40)

    # Handle case where neither state nor config exists
    if state is None and config is None:
        click.secho("\n⚠️  No state or configuration found", fg="yellow")
        click.echo("   This might be a new or corrupted project.")
        if config_path:
            click.echo(f"\n   Expected config: {config_path}")
        if state_path:
            click.echo(f"   Expected state: {state_path}")
        raise click.Abort()

    # Display state information
    if state:
        _display_project_info(state)
        _display_modules(state)
        _display_drift_warnings(state_manager)
        _display_managed_file_drift_warnings(project_state_manager)
        _display_version_drift_warnings(project_state_manager)
    else:
        click.secho("\n⚠️  No state file found (.quickscale/state.yml)", fg="yellow")
        click.echo("   Run 'quickscale apply' to initialize the project state.")

    # Phase 4: display explicit M2 drift & compatibility diagnostics.
    if drift_diagnostics is not None:
        _display_drift_diagnostics(drift_diagnostics)

    resolved_manifests = manifests
    if resolved_manifests is None and state and state.modules:
        resolved_manifests = _load_module_manifests(
            project_path,
            list(state.modules.keys()),
        )

    # Display pending changes
    _display_pending_changes(config, state, resolved_manifests)

    # Display Docker status
    _display_docker_status()

    click.echo("")  # Final newline


@click.command()
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format",
)
def status(json_output: bool) -> None:
    """
    Show project status and state information.

    Displays project information, applied modules, pending changes,
    and Docker status for the current QuickScale project.

    \b
    Examples:
      quickscale status          # Show status in current directory
      quickscale status --json   # Output as JSON

    \b
    Information displayed:
      - Project name, theme, and timestamps
      - Applied modules with versions
      - Pending changes (diff between config and state)
      - Docker container status (if running)
    """
    import json as json_module

    # Detect project context
    project_path, config_path, state_path = _detect_project_context()

    if project_path is None:
        click.secho(
            "❌ Not in a QuickScale project directory",
            fg="red",
            err=True,
        )
        click.echo("\n💡 Run this command from a directory containing:", err=True)
        click.echo("   - quickscale.yml (configuration file), or", err=True)
        click.echo("   - .quickscale/state.yml (state file)", err=True)
        raise click.Abort()

    # Load state and config
    state_manager = StateManager(project_path)
    project_state_manager = ProjectStateManager(project_path)
    try:
        state = state_manager.load()
    except StateError as error:
        click.secho(
            f"❌ Failed to load .quickscale/state.yml: {error}", fg="red", err=True
        )
        raise click.Abort() from error

    try:
        config = _load_config(config_path) if config_path else None
    except ConfigValidationError as error:
        click.secho(f"❌ Invalid quickscale.yml:\n{error}", fg="red", err=True)
        raise click.Abort() from error
    except OSError as error:
        click.secho(f"❌ Failed to read quickscale.yml: {error}", fg="red", err=True)
        raise click.Abort() from error

    if config is not None:
        _abort_for_not_ready_modules(
            list(config.modules.keys()), source="quickscale.yml"
        )
    if state is not None:
        _abort_for_not_ready_modules(
            list(state.modules.keys()),
            source=".quickscale/state.yml",
        )

    manifests: dict[str, ModuleManifest] | None = None
    if state and state.modules:
        try:
            manifests = _load_module_manifests(
                project_path,
                list(state.modules.keys()),
                strict=True,
            )
        except ManifestError as error:
            _abort_for_manifest_error(error)

    # Handle JSON output
    if json_output:
        drift_diagnostics = _compute_drift_diagnostics(
            project_path, state, project_state_manager, state_manager
        )
        output = _build_json_output(
            project_path,
            config_path,
            state,
            config,
            manifests,
            drift_diagnostics=drift_diagnostics,
        )
        click.echo(json_module.dumps(output, indent=2))
        return

    # Compute drift diagnostics for text output.
    drift_diagnostics = _compute_drift_diagnostics(
        project_path, state, project_state_manager, state_manager
    )

    # Display text status
    _display_text_status(
        project_path,
        state,
        config,
        config_path,
        state_path,
        state_manager,
        project_state_manager,
        manifests,
        drift_diagnostics=drift_diagnostics,
    )
