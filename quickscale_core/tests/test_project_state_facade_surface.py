"""Conformance gate: the split project-state owner keeps its import surface.

SA231 moved the implementation into sibling ``project_state_*`` modules.
Every name the former ``quickscale_core.project_state`` module exposed at
import time must remain importable from the same module path, and the lazy
re-export maps in ``quickscale_core.config`` and ``quickscale_core.schema``
must keep resolving through it.
"""

import quickscale_core.project_state as project_state
from quickscale_core import config, schema
from quickscale_core.project_state_drift import check_version_drift
from quickscale_core.project_state_hashes import (
    DEFAULT_MANAGED_WIRING_PATHS,
    FILE_HASHES_FILENAME,
    compute_file_hashes,
    hash_managed_file,
)
from quickscale_core.project_state_manager import ProjectStateManager
from quickscale_core.project_state_records import ManagedFileHash, VersionDriftWarning

EXPECTED_MODULE_SURFACE = frozenset(
    {
        "ConfigError",
        "ModuleConfig",
        "ModuleInfo",
        "add_module",
        "load_config",
        "normalize_installed_version",
        "remove_module",
        "save_config",
        "update_module_version",
        "ManagedFileRecord",
        "ModuleState",
        "ProjectState",
        "QuickScaleState",
        "StateError",
        "StateManager",
        "DEFAULT_MANAGED_WIRING_PATHS",
        "FILE_HASHES_FILENAME",
        "ManagedFileHash",
        "ProjectStateManager",
        "VersionDriftWarning",
        "check_version_drift",
        "compute_file_hashes",
        "hash_managed_file",
    }
)

CONFIG_LAZY_EXPORTS = (
    "ProjectStateManager",
    "ManagedFileHash",
    "ManagedFileRecord",
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
)

SCHEMA_LAZY_EXPORTS = tuple(
    name for name in CONFIG_LAZY_EXPORTS if name != "ManagedFileRecord"
)


def test_facade_preserves_former_module_surface() -> None:
    """Every name the former module exposed stays importable from project_state."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(dir(project_state)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_declares_every_former_public_name() -> None:
    """Every former public name stays in ``__all__`` for wildcard consumers."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(project_state.__all__))
    assert not missing, f"facade __all__ dropped former public names: {missing}"


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert project_state.ProjectStateManager is ProjectStateManager
    assert project_state.ManagedFileHash is ManagedFileHash
    assert project_state.VersionDriftWarning is VersionDriftWarning
    assert project_state.check_version_drift is check_version_drift
    assert project_state.compute_file_hashes is compute_file_hashes
    assert project_state.hash_managed_file is hash_managed_file
    assert project_state.FILE_HASHES_FILENAME == FILE_HASHES_FILENAME
    assert project_state.DEFAULT_MANAGED_WIRING_PATHS is DEFAULT_MANAGED_WIRING_PATHS


def test_lazy_reexport_maps_still_resolve_through_the_facade() -> None:
    """The config/schema lazy maps keep returning the facade's objects."""
    for name in CONFIG_LAZY_EXPORTS:
        assert getattr(config, name) is getattr(project_state, name)
    for name in SCHEMA_LAZY_EXPORTS:
        assert getattr(schema, name) is getattr(project_state, name)
