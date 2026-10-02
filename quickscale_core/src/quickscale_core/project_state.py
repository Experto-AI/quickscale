"""Unified owner for QuickScale project state and module configuration.

Phase 2 (M2) makes ``.quickscale/state.yml`` the sole authority for
module-tracking metadata and managed-file drift records.  Legacy
``config.yml`` and ``file_hashes.yml`` are compatibility inputs only:
they are read-through imported when the consolidated sections are absent
from ``state.yml``, and ignored when the consolidated sections are
present.

The unified surface provides:

* :class:`ProjectStateManager` — load/save state with read-through
  import from legacy files when consolidated sections are absent.
* :class:`ManagedFileHash` — typed record of a managed file's last-known
  hash and the timestamp it was captured at (legacy ledger form).
* :class:`ManagedFileRecord` — consolidated form stored in ``state.yml``.
* :func:`compute_file_hashes` — hash managed wiring files for drift detection.
* :func:`check_version_drift` — compare module versions in state vs config.

The existing ``StateManager`` (``.quickscale/state.yml``) and
``ModuleConfig``/``load_config``/``save_config`` (``.quickscale/config.yml``)
helpers are re-exported here so that callers can adopt a single import
without changing semantics. The lower-level helpers remain in their original
modules and continue to work without modification.

The implementation now lives in the sibling ``project_state_*`` modules;
this module stays the import path every caller uses and re-exports its full
former surface.
"""

from __future__ import annotations

# Re-export the schema/state surface so callers can use a single import.
from quickscale_core.config import (  # noqa: F401
    ConfigError,
    ModuleConfig,
    ModuleInfo,
    add_module,
    load_config,
    normalize_installed_version,
    remove_module,
    save_config,
    update_module_version,
)
from quickscale_core.project_state_drift import check_version_drift
from quickscale_core.project_state_hashes import (
    DEFAULT_MANAGED_WIRING_PATHS,
    FILE_HASHES_FILENAME,
    compute_file_hashes,
    hash_managed_file,
)
from quickscale_core.project_state_manager import ProjectStateManager
from quickscale_core.project_state_records import (
    ManagedFileHash,
    VersionDriftWarning,
)
from quickscale_core.schema.state_schema import (  # noqa: F401
    ManagedFileRecord,
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)

__all__ = [
    # Re-exports from quickscale_core.config
    "ConfigError",
    "ModuleConfig",
    "ModuleInfo",
    "add_module",
    "load_config",
    "normalize_installed_version",
    "remove_module",
    "save_config",
    "update_module_version",
    # Re-exports from quickscale_core.schema.state_schema
    "ManagedFileRecord",
    "ModuleState",
    "ProjectState",
    "QuickScaleState",
    "StateError",
    "StateManager",
    # New unified surface
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
    "ManagedFileHash",
    "ProjectStateManager",
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "hash_managed_file",
]
