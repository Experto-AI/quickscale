"""Project context assembly and fail-hard helpers for the status command.

Implementation detail of :mod:`quickscale_cli.commands.status_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations


from pathlib import Path

import click

from quickscale_core.contracts.module_discovery import ModulePresenceRecord
from quickscale_core.manifest import ModuleManifest
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.schema.state_schema import (
    QuickScaleState,
    StateManager,
)


import quickscale_core.schema.config_schema as _config_schema
import quickscale_core.contracts.module_discovery as _module_discovery
import quickscale_core.contracts.module_catalog as _module_catalog
import quickscale_core.manifest.loader_errors as _loader_errors
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.manifest.loader as _loader
import subprocess


def _get_docker_status() -> dict[str, str] | None:
    """Get Docker container status if running

    Returns:
        Dictionary with container names and status, or None if Docker not available

    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "{{.Name}}: {{.Status}}"],  # noqa: S607 - PATH-resolved executable by design
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
    except ValueError, TypeError:
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
    return _config_schema.validate_config(yaml_content)


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
        manifest = _loader.get_manifest_for_module(
            project_path, module_name, strict=strict
        )
        if manifest:
            manifests[module_name] = manifest
    return manifests


def _discover_project_module_presence(
    project_path: Path,
    module_names: list[str],
) -> list[ModulePresenceRecord]:
    """Capture typed filesystem presence for state-owned modules."""
    return _module_discovery.discover_module_presence(
        base_path=project_path / "modules",
        expected_names=module_names,
    )


def _abort_for_not_ready_modules(module_names: list[str], *, source: str) -> None:
    """Abort status when non-public-ready modules appear in config or applied state."""
    not_ready = _module_catalog.find_not_ready_modules(module_names)
    if not not_ready:
        return

    click.secho(
        f"\n❌ Unsupported non-public-ready module state detected in {source}:",
        fg="red",
        err=True,
        bold=True,
    )
    for module_name in not_ready:
        reason = _module_catalog.get_module_readiness_reason(module_name)
        if reason is not None:
            click.echo(f"  • {reason}", err=True)

    guidance = (
        "\n💡 Resolve the non-public-ready module state above before running "
        "'quickscale status' again."
    )

    click.echo(guidance, err=True)
    raise click.Abort()


def _abort_for_manifest_error(error: _loader_errors.ManifestError) -> None:
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


def _load_status_state_and_config(
    project_path: Path,
    config_path: Path | None,
) -> tuple[
    StateManager, ProjectStateManager, QuickScaleState | None, QuickScaleConfig | None
]:
    """Load status inputs and apply the command's fail-hard module policy."""
    state_manager = _state_schema.StateManager(project_path)
    project_state_manager = _project_state_manager.ProjectStateManager(project_path)
    try:
        state = state_manager.load()
    except _state_schema.StateError as error:
        click.secho(
            f"❌ Failed to load .quickscale/state.yml: {error}", fg="red", err=True
        )
        raise click.Abort() from error

    try:
        config = _load_config(config_path) if config_path else None
    except _config_schema.ConfigValidationError as error:
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
    return state_manager, project_state_manager, state, config


def _load_status_manifests(
    project_path: Path,
    state: QuickScaleState | None,
) -> tuple[dict[str, ModuleManifest] | None, list[ModulePresenceRecord]]:
    """Load active module manifests and preserve typed presence records."""
    manifests: dict[str, ModuleManifest] | None = None
    presence_records: list[ModulePresenceRecord] = []
    if not state or not state.modules:
        return manifests, presence_records

    presence_records = _discover_project_module_presence(
        project_path,
        list(state.modules.keys()),
    )
    active_module_names = [
        record.name
        for record in presence_records
        if record.state is _module_discovery.ModulePresenceState.ACTIVE
    ]
    try:
        manifests = _load_module_manifests(
            project_path,
            active_module_names,
            strict=True,
        )
    except _loader_errors.ManifestError as error:
        _abort_for_manifest_error(error)
    return manifests, presence_records
