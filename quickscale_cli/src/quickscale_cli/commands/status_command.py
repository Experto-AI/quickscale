"""Status command for showing project state.

Implements `quickscale status` — displays current vs desired state and project
info.

The implementation lives in private sibling modules grouped by concern
(``_status_context``, ``_status_diagnostics``, ``_status_display``); this module owns the public command surface, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations


import click as click

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
    load_declared_project_steps as load_declared_project_steps,
    load_shipped_contract_manifests as load_shipped_contract_manifests,
)
import quickscale_core.contracts.module_discovery as _module_discovery
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_cli.commands._status_context as _status_context
import quickscale_cli.commands._status_diagnostics as _status_diagnostics
import quickscale_cli.commands._status_display as _status_display


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
    project_path, config_path, state_path = _status_context._detect_project_context()

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

    state_manager, project_state_manager, state, config = (
        _status_context._load_status_state_and_config(project_path, config_path)
    )
    manifests, presence_records = _status_context._load_status_manifests(
        project_path, state
    )
    contract_module_names = {
        record.name
        for record in presence_records
        if record.state is _module_discovery.ModulePresenceState.ACTIVE
        and state is not None
        and record.name in state.modules
    }
    contract_manifests = _contract_vintage.load_shipped_contract_manifests(
        contract_module_names
    )

    # Handle JSON output
    if json_output:
        drift_diagnostics = _status_diagnostics._compute_drift_diagnostics(
            project_path,
            state,
            project_state_manager,
            state_manager,
            manifests=manifests,
            presence_records=presence_records,
            contract_manifests=contract_manifests,
        )
        output = _status_display._build_json_output(
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
    drift_diagnostics = _status_diagnostics._compute_drift_diagnostics(
        project_path,
        state,
        project_state_manager,
        state_manager,
        manifests=manifests,
        presence_records=presence_records,
        contract_manifests=contract_manifests,
    )

    # Display text status
    _status_display._display_text_status(
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
