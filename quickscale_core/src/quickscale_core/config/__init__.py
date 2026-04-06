"""Configuration management for QuickScale modules."""

from quickscale_core.config.module_config import (
    ModuleConfig,
    ModuleInfo,
    add_module,
    load_config,
    normalize_installed_version,
    remove_module,
    save_config,
    update_module_version,
)

__all__ = [
    "ModuleConfig",
    "ModuleInfo",
    "load_config",
    "save_config",
    "add_module",
    "remove_module",
    "normalize_installed_version",
    "update_module_version",
]
