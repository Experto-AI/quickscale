"""Drift and compatibility diagnostics for the status command.

Implementation detail of :mod:`quickscale_cli.commands.status_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from quickscale_core.contracts.module_discovery import ModulePresenceRecord
from quickscale_core.manifest import ModuleManifest
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.state_schema import (
    QuickScaleState,
    StateManager,
)

import quickscale_cli.commands.status_command as _status_command


def _state_file_has_consolidated_sections(state_dir: Path) -> bool:
    """Check whether ``state.yml`` on disk has consolidated sections.

    Returns True when the state file exists and contains the
    ``managed_files`` section, an explicit (even empty) ``modules`` key, or
    modules with consolidated tracking fields
    (``prefix``/``branch``/``installed_at``) — the same authoritative-state
    markers ``ProjectStateManager`` uses.
    """
    state_file = state_dir / "state.yml"
    if not state_file.exists():
        return False
    try:
        with open(state_file) as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError, OSError:
        return False

    if not isinstance(data, dict):
        return False

    if "managed_files" in data:
        return True

    modules_data = data.get("modules")
    if modules_data is not None and isinstance(modules_data, dict) and not modules_data:
        # An explicit empty ``modules: {}`` key records "no modules tracked"
        # authoritatively; legacy config.yml must not be read through (SA207).
        return True

    if isinstance(modules_data, dict):
        for _name, info in modules_data.items():
            if isinstance(info, dict) and (
                "prefix" in info or "branch" in info or "installed_at" in info
            ):
                return True

    return False


def _legacy_files_present(state_dir: Path) -> list[str]:
    """Return legacy state files that are present on disk."""
    legacy_files: list[str] = []
    config_yml = state_dir / "config.yml"
    file_hashes_yml = state_dir / _status_command.FILE_HASHES_FILENAME
    if config_yml.exists():
        legacy_files.append("config.yml")
    if file_hashes_yml.exists():
        legacy_files.append(_status_command.FILE_HASHES_FILENAME)
    return legacy_files


def _module_tracking_diagnostics(
    state: QuickScaleState | None,
) -> tuple[int, int, list[str]]:
    """Return total, consolidated, and incomplete module tracking values."""
    modules = state.modules if state else {}
    needing_consolidation = [
        name for name, module in modules.items() if not module.has_consolidated_tracking
    ]
    total = len(modules)
    return total, total - len(needing_consolidation), sorted(needing_consolidation)


def _filesystem_drift_diagnostics(
    project_path: Path,
    state: QuickScaleState | None,
    state_manager: StateManager,
    presence_records: list[ModulePresenceRecord] | None,
) -> dict[str, list[str]]:
    """Return filesystem drift, including typed incomplete-module states."""
    modules = state.modules if state else {}
    fs_drift = state_manager.verify_filesystem()
    records = presence_records
    if records is None:
        records = _status_command._discover_project_module_presence(
            project_path, list(modules)
        )

    state_module_names = set(modules)
    incomplete = sorted(
        record.name
        for record in records
        if record.name in state_module_names
        and record.state is _status_command.ModulePresenceState.INCOMPLETE
    )
    missing = sorted(
        record.name
        for record in records
        if record.name in state_module_names
        and record.state is _status_command.ModulePresenceState.ABSENT
    )
    return {
        "orphaned_modules": sorted(fs_drift.get("orphaned_modules", [])),
        "missing_modules": missing,
        "incomplete_modules": incomplete,
    }


def _version_drift_diagnostics(
    project_state_manager: ProjectStateManager,
) -> list[dict[str, object]]:
    """Return serializable version drift diagnostics."""
    try:
        state = project_state_manager.load_state()
        config = project_state_manager.load_config()
    except (
        _status_command.ConfigError,
        _status_command.StateError,
        OSError,
    ):
        state = None
        config = None

    return [
        {
            "module": warning.module,
            "state_version": warning.state_version,
            "config_version": warning.config_version,
        }
        for warning in _status_command.check_version_drift(state, config)
    ]


def _compute_drift_diagnostics(
    project_path: Path,
    state: QuickScaleState | None,
    project_state_manager: ProjectStateManager,
    state_manager: StateManager,
    manifests: dict[str, ModuleManifest] | None = None,
    presence_records: list[ModulePresenceRecord] | None = None,
    contract_manifests: dict[str, ModuleManifest] | None = None,
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
    * ``filesystem_drift`` — orphaned, missing, and incomplete modules.
    * ``managed_file_drift`` — managed files that drifted since last apply.
    * ``version_drift`` — version disagreements between state and config.
    """
    state_dir = project_path / ".quickscale"
    consolidated_on_disk = _status_command._state_file_has_consolidated_sections(
        state_dir
    )

    # Check which legacy files exist on disk.
    legacy_files_present = _status_command._legacy_files_present(state_dir)

    legacy_compat_active = (not consolidated_on_disk) and bool(legacy_files_present)

    # Module tracking completeness.
    (
        module_tracking_total,
        module_tracking_consolidated,
        modules_needing_consolidation,
    ) = _status_command._module_tracking_diagnostics(state)

    # Filesystem drift (orphaned/missing/incomplete modules).
    filesystem_drift = _status_command._filesystem_drift_diagnostics(
        project_path,
        state,
        state_manager,
        presence_records,
    )

    # Managed files consolidation.
    managed_files_consolidated = bool(state and state.managed_files)

    # Managed file drift.
    managed_drift_records = project_state_manager.detect_managed_file_drift()
    managed_file_drift = [
        {"path": r.path, "expected_hash": r.hash} for r in managed_drift_records
    ]

    # Version drift between state and config.
    version_drift = _status_command._version_drift_diagnostics(project_state_manager)

    # SA10.2: contract-vintage check.
    project_contract = state.project.project_contract if state else None
    vintage_manifests = (
        contract_manifests if contract_manifests is not None else manifests
    )
    contract_vintage = _status_command._check_contract_vintage(
        project_contract,
        vintage_manifests,
        project_steps=_status_command.load_declared_project_steps(),
        adopted_steps=(
            state.project.adopted_contract_steps if state is not None else None
        ),
    )
    contract_vintage["has_state"] = state is not None

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
            "orphaned_modules": filesystem_drift["orphaned_modules"],
            "missing_modules": filesystem_drift["missing_modules"],
            "incomplete_modules": filesystem_drift["incomplete_modules"],
        },
        "managed_file_drift": managed_file_drift,
        "version_drift": version_drift,
        "contract_vintage": contract_vintage,
    }
