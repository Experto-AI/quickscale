"""Configuration management for QuickScale modules.

The unified project state owner lives at
:mod:`quickscale_core.project_state` and re-exports the same names plus
:class:`ProjectStateManager` for callers that want a single entry point
over ``.quickscale/state.yml`` and ``.quickscale/config.yml``.
"""

from importlib import import_module
from typing import Any

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

_LAZY_EXPORTS = {
    "ProjectStateManager": (
        "quickscale_core.project_state",
        "ProjectStateManager",
    ),
    "ManagedFileHash": (
        "quickscale_core.project_state",
        "ManagedFileHash",
    ),
    "VersionDriftWarning": (
        "quickscale_core.project_state",
        "VersionDriftWarning",
    ),
    "check_version_drift": (
        "quickscale_core.project_state",
        "check_version_drift",
    ),
    "compute_file_hashes": (
        "quickscale_core.project_state",
        "compute_file_hashes",
    ),
    "DEFAULT_MANAGED_WIRING_PATHS": (
        "quickscale_core.project_state",
        "DEFAULT_MANAGED_WIRING_PATHS",
    ),
    "FILE_HASHES_FILENAME": (
        "quickscale_core.project_state",
        "FILE_HASHES_FILENAME",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve lazy re-exports to the unified project state owner."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)


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
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
]
