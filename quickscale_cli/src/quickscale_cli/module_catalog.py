"""Backward-compatible shim for ``quickscale_cli.module_catalog``.

The canonical module catalog lives in
``quickscale_core.contracts.module_catalog`` as part of the shared
contract surface owned by ``quickscale_core``. This module re-exports
those names so existing CLI consumers continue to work without
modification.

Phase 0 of the QuickScale Phase 3 architecture improvements moved the
catalog out of the CLI package. The original symbols are preserved here
as thin re-exports.
"""

from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    ModuleCatalogEntry,
    find_not_ready_modules,
    get_module_entries,
    get_module_entry,
    get_module_names,
    get_module_readiness_reason,
)

__all__ = [
    "MODULE_CATALOG",
    "ModuleCatalogEntry",
    "find_not_ready_modules",
    "get_module_entries",
    "get_module_entry",
    "get_module_names",
    "get_module_readiness_reason",
]
