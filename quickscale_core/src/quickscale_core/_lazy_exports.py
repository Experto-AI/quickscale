"""Shared lazy re-export machinery for the split facade packages.

``quickscale_core.config`` and ``quickscale_core.schema`` both keep
backward-compatible lazy re-export maps that ultimately resolve through the
unified :mod:`quickscale_core.project_state` owner.  The shared map entries and
the attribute-resolution helper live here once so the two facades cannot drift
apart.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

#: Project-state symbols re-exported by both ``quickscale_core.config`` and
#: ``quickscale_core.schema``.  Each entry maps the public name to the module
#: and attribute that owns it.
PROJECT_STATE_EXPORTS: dict[str, tuple[str, str]] = {
    "ProjectStateManager": ("quickscale_core.project_state", "ProjectStateManager"),
    "ManagedFileHash": ("quickscale_core.project_state", "ManagedFileHash"),
    "ManagedFileRecord": ("quickscale_core.project_state", "ManagedFileRecord"),
    "VersionDriftWarning": ("quickscale_core.project_state", "VersionDriftWarning"),
    "check_version_drift": ("quickscale_core.project_state", "check_version_drift"),
    "compute_file_hashes": ("quickscale_core.project_state", "compute_file_hashes"),
    "DEFAULT_MANAGED_WIRING_PATHS": (
        "quickscale_core.project_state",
        "DEFAULT_MANAGED_WIRING_PATHS",
    ),
    "FILE_HASHES_FILENAME": ("quickscale_core.project_state", "FILE_HASHES_FILENAME"),
}


def resolve_lazy_export(
    exports: dict[str, tuple[str, str]],
    module_name: str,
    attribute: str,
) -> Any:
    """Resolve *attribute* through *exports*, raising ``AttributeError`` if absent."""
    target = exports.get(attribute)
    if target is None:
        raise AttributeError(f"module {module_name!r} has no attribute {attribute!r}")
    target_module, target_attribute = target
    return getattr(import_module(target_module), target_attribute)
