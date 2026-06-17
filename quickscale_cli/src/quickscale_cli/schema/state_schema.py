"""Backward-compatible shim for ``quickscale_cli.schema.state_schema``.

The canonical implementation now lives at
:mod:`quickscale_core.schema.state_schema`. This module re-exports the
same public surface (``ModuleState``, ``ProjectState``,
``QuickScaleState``, ``StateError``, ``StateManager``,
``ManagedFileRecord``) so that existing
``from quickscale_cli.schema.state_schema import ...`` calls keep
working without modification.
"""

from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)

__all__ = [
    "ModuleState",
    "ProjectState",
    "QuickScaleState",
    "StateError",
    "StateManager",
    "ManagedFileRecord",
]
