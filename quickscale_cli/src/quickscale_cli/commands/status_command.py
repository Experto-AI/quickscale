"""Status command for showing project state

Implements `quickscale status` - displays current vs desired state and project info
"""

import subprocess
from pathlib import Path

import click

from quickscale_cli.schema.config_schema import QuickScaleConfig, validate_config
from quickscale_cli.schema.delta import compute_delta, format_delta
from quickscale_cli.schema.state_schema import QuickScaleState, StateManager
from quickscale_core.manifest import ModuleManifest
from quickscale_core.manifest.loader import get_manifest_for_module


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
    try:
        yaml_content = config_path.read_text()
        return validate_config(yaml_content)
    except Exception:
        return None


def _load_module_manifests(
    project_path: Path, module_names: list[str]
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
        manifest = get_manifest_for_module(project_path, module_name)
        if manifest:
            manifests[module_name] = manifest
    return manifests


def _display_project_info(state: QuickScaleState) -> None:
    """Display project information from state"""
    click.echo("\n📁 Project Information:")
    click.echo(f"   Name: {state.project.name}")
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


def _build_json_output(
    project_path: Path,
    config_path: Path | None,
    state: QuickScaleState | None,
    config: QuickScaleConfig | None,
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
                "name": state.project.name,
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
                "name": config.project.name,
                "theme": config.project.theme,
            },
            "modules": list(config.modules.keys()),
            "docker": {
                "start": config.docker.start,
                "build": config.docker.build,
            },
        }

        # Load manifests for accurate config change detection
        json_manifests = None
        if state and state.modules:
            json_manifests = _load_module_manifests(
                project_path, list(state.modules.keys())
            )
        delta = compute_delta(config, state, json_manifests)
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

    return output


def _display_text_status(
    project_path: Path,
    state: QuickScaleState | None,
    config: QuickScaleConfig | None,
    config_path: Path | None,
    state_path: Path | None,
    state_manager: StateManager,
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
    else:
        click.secho("\n⚠️  No state file found (.quickscale/state.yml)", fg="yellow")
        click.echo("   Run 'quickscale apply' to initialize the project state.")

    # Load manifests for installed modules (needed for config change detection)
    manifests: dict[str, ModuleManifest] | None = None
    if state and state.modules:
        manifests = _load_module_manifests(project_path, list(state.modules.keys()))

    # Display pending changes
    _display_pending_changes(config, state, manifests)

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
    state = state_manager.load()
    config = _load_config(config_path) if config_path else None

    # Handle JSON output
    if json_output:
        output = _build_json_output(project_path, config_path, state, config)
        click.echo(json_module.dumps(output, indent=2))
        return

    # Display text status
    _display_text_status(
        project_path, state, config, config_path, state_path, state_manager
    )
