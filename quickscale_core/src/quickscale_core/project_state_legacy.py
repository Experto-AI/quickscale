"""Legacy compatibility inputs for the unified project-state surface.

Legacy ``config.yml`` and ``file_hashes.yml`` are read-through imported only
while ``state.yml`` lacks consolidated sections (F12.2). This module owns the
pure helpers: raw state-file access, consolidated-section detection, raw
project timestamp reads, and the merge loops that fold legacy records into an
in-memory state. The unified owner stays importable from
``quickscale_core.project_state``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from quickscale_core.config.module_config import normalize_installed_version
from quickscale_core.schema.state_schema import ManagedFileRecord, ModuleState

if TYPE_CHECKING:
    from quickscale_core.config.module_config import ModuleConfig, ModuleInfo
    from quickscale_core.project_state_records import ManagedFileHash


def load_raw_state_data(state_file: Path) -> dict | None:
    """Return the raw parsed mapping of *state_file*, or ``None``.

    ``None`` covers a missing file, an unreadable or malformed YAML
    document, and any document whose top level is not a mapping.
    """
    if not state_file.exists():
        return None
    try:
        with open(state_file) as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError, OSError:
        return None

    if not isinstance(data, dict):
        return None
    return data


def state_data_has_consolidated_sections(data: dict) -> bool:
    """Check whether parsed ``state.yml`` data has consolidated sections.

    Returns True when the data contains either the ``managed_files``
    section, an explicit ``modules`` key (even when empty — signalling that
    M2 has authoritatively recorded "no modules"), or modules with
    consolidated tracking fields (``prefix``/``branch``/``installed_at``).
    This determines whether legacy ``config.yml`` and ``file_hashes.yml``
    should be read-through imported or ignored.
    """
    # Check for managed_files section.
    if "managed_files" in data:
        return True

    # An explicit empty ``modules: {}`` key means M2 has authoritatively
    # recorded "no modules tracked."  Legacy config.yml must NOT be
    # read-through imported in that case, because stale legacy entries
    # could resurrect modules that were explicitly removed.
    # Non-empty modules without consolidated fields still need legacy
    # read-through import (pre-M2 → M2 migration path).
    modules_data = data.get("modules")
    if modules_data is not None and isinstance(modules_data, dict) and not modules_data:
        return True

    return _has_consolidated_module_fields(modules_data)


def _has_consolidated_module_fields(modules_data: object) -> bool:
    """Return whether any module entry carries consolidated tracking fields."""
    if not isinstance(modules_data, dict):
        return False
    for _name, info in modules_data.items():
        if isinstance(info, dict) and (
            "prefix" in info or "branch" in info or "installed_at" in info
        ):
            return True
    return False


def read_project_timestamps(data: dict) -> tuple[str, str] | None:
    """Read project timestamps from raw ``state.yml`` without fabrication.

    Returns ``(created_at, last_applied)`` only when both fields are present
    as strings in the raw mapping, or ``None`` when either is absent or not
    a string.
    """
    project_data = data.get("project")
    if not isinstance(project_data, dict):
        return None

    created_at = project_data.get("created_at")
    last_applied = project_data.get("last_applied")
    if not isinstance(created_at, str) or not isinstance(last_applied, str):
        return None

    return (created_at, last_applied)


def merge_legacy_module_tracking(
    modules: dict[str, ModuleState],
    legacy_config: ModuleConfig | None,
) -> None:
    """Fold legacy ``config.yml`` module tracking into *modules*.

    Existing module states keep their consolidated fields and gain any that
    are missing; modules known only to the legacy config are created with
    their normalized installed version and tracking fields. ``None`` keeps
    *modules* unchanged.
    """
    if legacy_config is None:
        return

    for module_name, module_info in legacy_config.modules.items():
        if module_name in modules:
            # Merge tracking fields into existing module state.
            _fill_missing_tracking(modules[module_name], module_info)
        else:
            # Module exists in config but not in state — create a
            # minimal ModuleState with tracking fields.
            modules[module_name] = ModuleState(
                name=module_name,
                version=normalize_installed_version(module_info.installed_version),
                prefix=module_info.prefix,
                branch=module_info.branch,
                installed_at=module_info.installed_at,
            )


def _fill_missing_tracking(module_state: ModuleState, module_info: ModuleInfo) -> None:
    """Fill any consolidated tracking fields missing from *module_state*."""
    if module_state.prefix is None:
        module_state.prefix = module_info.prefix
    if module_state.branch is None:
        module_state.branch = module_info.branch
    if module_state.installed_at is None:
        module_state.installed_at = module_info.installed_at


def merge_legacy_file_hashes(
    managed_files: dict[str, ManagedFileRecord],
    legacy_hashes: dict[str, ManagedFileHash],
) -> None:
    """Fold legacy ``file_hashes.yml`` records into *managed_files*.

    Existing consolidated records win; legacy records are only added for
    paths the consolidated section does not already cover.
    """
    for path, record in legacy_hashes.items():
        if path not in managed_files:
            managed_files[path] = ManagedFileRecord(
                path=record.path,
                hash=record.hash,
                applied_at=record.applied_at,
            )
