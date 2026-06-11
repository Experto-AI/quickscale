"""Backward-compatible shim for ``quickscale_cli.schema.delta``.

The canonical implementation now lives at :mod:`quickscale_core.schema.delta`.
This module re-exports the same public surface (``ConfigChange``,
``ConfigDelta``, ``ModuleConfigDelta``, ``ModuleDelta``, ``compute_delta``,
``format_delta``) so that existing
``from quickscale_cli.schema.delta import ...`` calls keep working
without modification.
"""

from quickscale_core.schema.delta import (
    ConfigChange,
    ConfigDelta,
    ModuleConfigDelta,
    ModuleDelta,
    compute_delta,
    format_delta,
)

__all__ = [
    "ConfigChange",
    "ConfigDelta",
    "ModuleConfigDelta",
    "ModuleDelta",
    "compute_delta",
    "format_delta",
]
