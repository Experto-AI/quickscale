"""Configuration management for QuickScale modules.

The unified project state owner lives at
:mod:`quickscale_core.project_state` and re-exports the same names plus
:class:`ProjectStateManager` for callers that want a single entry point
over ``.quickscale/state.yml`` and ``.quickscale/config.yml``.
"""

from typing import Any

from quickscale_core._lazy_exports import PROJECT_STATE_EXPORTS, resolve_lazy_export
from quickscale_core.config.module_config import (
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

_LAZY_EXPORTS = dict(PROJECT_STATE_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve lazy re-exports to the unified project state owner."""
    return resolve_lazy_export(_LAZY_EXPORTS, __name__, name)


__all__ = [
    "ConfigError",
    "ModuleConfig",
    "ModuleInfo",
    "load_config",
    "save_config",
    "add_module",
    "remove_module",
    "normalize_installed_version",
    "update_module_version",
    "ProjectStateManager",
    "ManagedFileHash",
    "ManagedFileRecord",
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
]
