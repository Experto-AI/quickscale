"""Helpers for syncing generated-project Poetry dependencies for embedded modules.

The implementation lives in private sibling modules grouped by concern
(``_dependency_io``, ``_dependency_write``, ``_dependency_sync_ops``); this module re-exports public names for unchanged import paths and resolves
collaborators through the sibling modules that define them (decisions.md,
Split-Facade Seams).
"""

from __future__ import annotations


from quickscale_core.manifest.loader import (
    ManifestError as ManifestError,
    get_manifest_for_module as get_manifest_for_module,
)

from quickscale_cli.utils._dependency_io import (
    DependencySyncError as DependencySyncError,
    ProjectDependencySyncResult as ProjectDependencySyncResult,
    resolve_embedded_module_install_path as resolve_embedded_module_install_path,
)
from quickscale_cli.utils._dependency_sync_ops import (
    sync_project_core_dependency as sync_project_core_dependency,
    sync_project_module_dependencies as sync_project_module_dependencies,
)
