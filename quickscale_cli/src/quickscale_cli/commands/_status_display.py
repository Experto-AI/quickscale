"""Text and JSON rendering for the status command.

Implementation detail of :mod:`quickscale_cli.commands.status_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from pathlib import Path

import click

from quickscale_core.manifest import ModuleManifest
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.schema.state_schema import (
    QuickScaleState,
    StateManager,
)


import quickscale_core.schema.delta as _delta
import quickscale_cli.commands._status_context as _status_context
import quickscale_core.project_state_drift as _project_state_drift
import quickscale_core.project_state_hashes as _project_state_hashes
import quickscale_core.config as _config
import quickscale_core.schema.state_schema as _state_schema


def _display_project_info(state: QuickScaleState) -> None:
    """Display project information from state"""
    click.echo("\n📁 Project Information:")
    click.echo(f"   Slug: {state.project.slug}")
    click.echo(f"   Package: {state.project.package}")
    click.echo(f"   Theme: {state.project.theme}")
    click.echo(
        f"   Created: {_status_context._format_datetime(state.project.created_at)}"
    )
    click.echo(
        f"   Last Applied: {_status_context._format_datetime(state.project.last_applied)}"
    )


def _display_modules(state: QuickScaleState) -> None:
    """Display applied modules from state"""
    click.echo("\n📦 Applied Modules:")
    if not state.modules:
        click.echo("   (none)")
        return

    for name, module in state.modules.items():
        version_str = f"v{module.version}" if module.version else "unknown"
        embedded_at = (
            _status_context._format_datetime(module.embedded_at)
            if module.embedded_at
            else "unknown"
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

    delta = _delta.compute_delta(config, state, manifests)

    if delta.has_changes:
        click.echo("\n⚡ Pending Changes:")
        change_summary = _delta.format_delta(delta)
        for line in change_summary.splitlines():
            click.echo(f"   {line}")
        click.echo("\n💡 Run 'quickscale apply' to apply these changes")
    else:
        click.secho("\n✅ Configuration matches applied state", fg="green")


def _display_docker_status() -> None:
    """Display Docker container status if available"""
    status = _status_context._get_docker_status()

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
    except (
        _config.ConfigError,
        _state_schema.StateError,
        OSError,
    ) as error:
        click.echo(
            f"\n⚠️  Could not check version drift between .quickscale/state.yml "
            f"and .quickscale/config.yml: {error}"
        )
        return

    drift = _project_state_drift.check_version_drift(state, config)
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


def _display_state_consolidation(diagnostics: dict) -> None:
    """Display state-consolidation and legacy-file diagnostics."""
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


def _display_module_tracking(diagnostics: dict) -> None:
    """Display module tracking completeness."""
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


def _display_managed_files(diagnostics: dict) -> None:
    """Display managed-file consolidation status."""
    if diagnostics["managed_files_consolidated"]:
        click.secho("   Managed files: ✅ consolidated in state.yml", fg="green")
        return
    legacy_hashes_present = (
        _project_state_hashes.FILE_HASHES_FILENAME
        in diagnostics["legacy_files_present"]
    )
    if legacy_hashes_present and diagnostics["legacy_compat_active"]:
        click.secho(
            f"   Managed files: ⚠️  using legacy {_project_state_hashes.FILE_HASHES_FILENAME}",
            fg="yellow",
        )
    elif legacy_hashes_present:
        click.secho(
            f"   Managed files: no records (legacy "
            f"{_project_state_hashes.FILE_HASHES_FILENAME} ignored)",
            fg="yellow",
        )
    else:
        click.echo("   Managed files: no records")


def _display_filesystem_drift(diagnostics: dict) -> None:
    """Display typed filesystem drift diagnostics."""
    fs = diagnostics["filesystem_drift"]
    orphaned = fs["orphaned_modules"]
    missing = fs["missing_modules"]
    incomplete = fs.get("incomplete_modules", [])
    if not orphaned and not missing and not incomplete:
        click.secho("   Filesystem drift: ✅ clean", fg="green")
    else:
        parts: list[str] = []
        if orphaned:
            parts.append(f"{len(orphaned)} orphaned ({', '.join(orphaned)})")
        if missing:
            parts.append(f"{len(missing)} missing ({', '.join(missing)})")
        if incomplete:
            parts.append(f"{len(incomplete)} incomplete ({', '.join(incomplete)})")
        click.secho(f"   Filesystem drift: ⚠️  {'; '.join(parts)}", fg="yellow")

    if incomplete:
        click.echo(
            "\n⚠️  Incomplete Modules (directory present but module.yml missing):"
        )
        for module in incomplete:
            click.secho(f"   • {module}", fg="yellow")
        click.echo(
            "   These modules need a valid module.yml before they can be applied."
        )


def _display_managed_file_drift(diagnostics: dict) -> None:
    """Display managed-file content drift."""
    mf_drift = diagnostics["managed_file_drift"]
    if not mf_drift:
        click.secho("   Managed file drift: ✅ clean", fg="green")
    else:
        paths = ", ".join(r["path"] for r in mf_drift)
        click.secho(
            f"   Managed file drift: ⚠️  {len(mf_drift)} drifted ({paths})",
            fg="yellow",
        )


def _display_version_drift(diagnostics: dict) -> None:
    """Display module-version drift."""
    vd = diagnostics["version_drift"]
    if not vd:
        click.secho("   Version drift: ✅ clean", fg="green")
    else:
        modules_str = ", ".join(w["module"] for w in vd)
        click.secho(
            f"   Version drift: ⚠️  {len(vd)} disagreement(s) ({modules_str})",
            fg="yellow",
        )


def _display_contract_vintage(diagnostics: dict) -> None:
    """Display contract-vintage diagnostics."""
    cv = diagnostics.get("contract_vintage", {})
    module_count = cv.get("module_count", 0)
    behind_count = cv.get("modules_behind_count", 0)
    modules_behind = cv.get("modules_behind", [])
    project_step_count = cv.get("project_step_count", 0)
    project_steps_behind = cv.get("project_steps_behind", [])
    project_contract = cv.get("project_contract")

    click.echo("")
    click.secho("🏛️  Contract Vintage:", bold=True)

    if project_contract is None:
        has_state = cv.get("has_state", True)
        if has_state:
            msg = "   Project contract: unknown (legacy project — pre-v0.87.0)"
        else:
            msg = "   Project contract: unknown (no state yet — run 'quickscale apply')"
        click.secho(msg, fg="yellow")
    else:
        click.echo(f"   Project contract: {project_contract}")

    if project_step_count == 0:
        click.echo("   Generated-project contract steps: none declared")
    elif not project_steps_behind:
        click.secho(
            f"   Generated-project contract steps: {project_step_count}/"
            f"{project_step_count} satisfied ✅",
            fg="green",
        )
    else:
        click.secho(
            f"   Generated-project contract steps: "
            f"{project_step_count - len(project_steps_behind)}/{project_step_count}"
            f" satisfied — {len(project_steps_behind)} step(s) behind ⚠️",
            fg="yellow",
        )
        for entry in project_steps_behind:
            click.secho(
                f"\n   • generated project ({entry['id']}) requires"
                f" project_contract >= {entry['minimum']}",
                fg="yellow",
            )
            if entry.get("title"):
                click.echo(f"     {entry['title']}")
            for step in entry.get("manual_adoption_steps", []):
                click.echo(f"     {step}")

    if module_count == 0:
        click.echo("   Module vintage requirements: none declared")
    elif behind_count == 0:
        click.secho(
            f"   Module vintage: {module_count}/{module_count} satisfied ✅",
            fg="green",
        )
    else:
        click.secho(
            f"   Module vintage: {module_count - behind_count}/{module_count}"
            f" satisfied — {behind_count} module(s) behind ⚠️",
            fg="yellow",
        )
        for entry in modules_behind:
            click.secho(
                f"\n   • {entry['module']} requires project_contract"
                f" >= {entry['minimum']}",
                fg="yellow",
            )
            steps = entry.get("manual_adoption_steps", [])
            for step in steps:
                click.echo(f"     {step}")


def _display_drift_diagnostics(diagnostics: dict) -> None:
    """Display M2 drift and compatibility diagnostics in text format."""
    click.echo("\n🔍 M2 Drift & Compatibility:")
    _display_state_consolidation(diagnostics)
    _display_module_tracking(diagnostics)
    _display_managed_files(diagnostics)
    _display_filesystem_drift(diagnostics)
    _display_managed_file_drift(diagnostics)
    _display_version_drift(diagnostics)
    _display_contract_vintage(diagnostics)


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

        delta = _delta.compute_delta(config, state, manifests)
        output["pending_changes"] = {
            "has_changes": delta.has_changes,
            "modules_to_add": delta.modules_to_add,
            "modules_to_remove": delta.modules_to_remove,
            "modules_unchanged": delta.modules_unchanged,
            "theme_changed": delta.theme_changed,
        }

    docker_status = _status_context._get_docker_status()
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
        resolved_manifests = _status_context._load_module_manifests(
            project_path,
            list(state.modules.keys()),
        )

    # Display pending changes
    _display_pending_changes(config, state, resolved_manifests)

    # Display Docker status
    _display_docker_status()

    click.echo("")  # Final newline
