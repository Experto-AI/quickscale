"""Status command for showing project state.

Implements `quickscale status` — displays current vs desired state and project
info.

The implementation lives in private sibling modules grouped by concern
(``_status_context``, ``_status_diagnostics``, ``_status_display``); this
module owns the public command surface and re-exports every name that
previously lived here (Module Conventions rule 28), so existing
``quickscale_cli.commands.status_command`` imports and test patch targets keep
working unchanged.
"""

from __future__ import annotations

import subprocess as subprocess
from pathlib import Path as Path

import click as click
import yaml as yaml

from quickscale_core.contracts.module_catalog import (
    find_not_ready_modules as find_not_ready_modules,
    get_module_readiness_reason as get_module_readiness_reason,
)
from quickscale_core.schema.config_schema import (
    ConfigValidationError as ConfigValidationError,
    QuickScaleConfig as QuickScaleConfig,
    validate_config as validate_config,
)
from quickscale_core.schema.delta import (
    compute_delta as compute_delta,
    format_delta as format_delta,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState as QuickScaleState,
    StateError as StateError,
    StateManager as StateManager,
)
from quickscale_core.config import ConfigError as ConfigError
from quickscale_core.contracts.module_discovery import (
    ModulePresenceRecord as ModulePresenceRecord,
    ModulePresenceState as ModulePresenceState,
    discover_module_presence as discover_module_presence,
)
from quickscale_core.manifest import ModuleManifest as ModuleManifest
from quickscale_core.manifest.loader import (
    ManifestError as ManifestError,
    get_manifest_for_module as get_manifest_for_module,
)
from quickscale_core.project_state import (
    FILE_HASHES_FILENAME as FILE_HASHES_FILENAME,
    ProjectStateManager as ProjectStateManager,
    check_version_drift as check_version_drift,
)
from quickscale_cli.commands.contract_vintage import (
    check_contract_vintage as _check_contract_vintage,  # noqa: F401 - private seam re-exported for callers and patchers
    load_declared_project_steps as load_declared_project_steps,
    load_shipped_contract_manifests as load_shipped_contract_manifests,
)
from quickscale_cli.commands._status_context import (
    _abort_for_manifest_error as _abort_for_manifest_error,
    _abort_for_not_ready_modules as _abort_for_not_ready_modules,
    _detect_project_context as _detect_project_context,
    _discover_project_module_presence as _discover_project_module_presence,
    _format_datetime as _format_datetime,
    _get_docker_status as _get_docker_status,
    _load_config as _load_config,
    _load_module_manifests as _load_module_manifests,
    _load_status_manifests as _load_status_manifests,
    _load_status_state_and_config as _load_status_state_and_config,
)
from quickscale_cli.commands._status_diagnostics import (
    _compute_drift_diagnostics as _compute_drift_diagnostics,
    _filesystem_drift_diagnostics as _filesystem_drift_diagnostics,
    _legacy_files_present as _legacy_files_present,
    _module_tracking_diagnostics as _module_tracking_diagnostics,
    _state_file_has_consolidated_sections as _state_file_has_consolidated_sections,
    _version_drift_diagnostics as _version_drift_diagnostics,
)
from quickscale_cli.commands._status_display import (
    _build_json_output as _build_json_output,
    _display_contract_vintage as _display_contract_vintage,
    _display_docker_status as _display_docker_status,
    _display_drift_diagnostics as _display_drift_diagnostics,
    _display_drift_warnings as _display_drift_warnings,
    _display_filesystem_drift as _display_filesystem_drift,
    _display_managed_file_drift as _display_managed_file_drift,
    _display_managed_file_drift_warnings as _display_managed_file_drift_warnings,
    _display_managed_files as _display_managed_files,
    _display_module_tracking as _display_module_tracking,
    _display_modules as _display_modules,
    _display_pending_changes as _display_pending_changes,
    _display_project_info as _display_project_info,
    _display_state_consolidation as _display_state_consolidation,
    _display_text_status as _display_text_status,
    _display_version_drift as _display_version_drift,
    _display_version_drift_warnings as _display_version_drift_warnings,
)


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

    state_manager, project_state_manager, state, config = _load_status_state_and_config(
        project_path, config_path
    )
    manifests, presence_records = _load_status_manifests(project_path, state)
    contract_module_names = {
        record.name
        for record in presence_records
        if record.state is ModulePresenceState.ACTIVE
        and state is not None
        and record.name in state.modules
    }
    contract_manifests = load_shipped_contract_manifests(contract_module_names)

    # Handle JSON output
    if json_output:
        drift_diagnostics = _compute_drift_diagnostics(
            project_path,
            state,
            project_state_manager,
            state_manager,
            manifests=manifests,
            presence_records=presence_records,
            contract_manifests=contract_manifests,
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
        project_path,
        state,
        project_state_manager,
        state_manager,
        manifests=manifests,
        presence_records=presence_records,
        contract_manifests=contract_manifests,
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
