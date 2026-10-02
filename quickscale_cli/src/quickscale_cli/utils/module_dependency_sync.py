"""Helpers for syncing generated-project Poetry dependencies for embedded modules.

The implementation lives in private sibling modules grouped by concern
(``_dependency_io``, ``_dependency_write``, ``_dependency_sync_ops``); this
module re-exports every name that previously lived here (Module Conventions
rule 28), so existing
``quickscale_cli.utils.module_dependency_sync`` imports and test patch targets
keep working unchanged.
"""

from __future__ import annotations

import os as os
import re as re
import shutil as shutil
import sys as sys
import tomllib as tomllib
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any, Mapping as Mapping

from quickscale_core.manifest.loader import (
    ManifestError as ManifestError,
    get_manifest_for_module as get_manifest_for_module,
)

from quickscale_cli.utils._dependency_io import (
    _DEPENDENCY_NAME_PATTERN as _DEPENDENCY_NAME_PATTERN,
    _INSTALL_WHEELHOUSE_DIRNAME as _INSTALL_WHEELHOUSE_DIRNAME,
    _LOCAL_WHEELHOUSE_ENV as _LOCAL_WHEELHOUSE_ENV,
    _LOCAL_WHEEL_DISTRIBUTIONS as _LOCAL_WHEEL_DISTRIBUTIONS,
    _STORAGE_CLOUD_BACKENDS as _STORAGE_CLOUD_BACKENDS,
    _STORAGE_CLOUD_DEPENDENCIES as _STORAGE_CLOUD_DEPENDENCIES,
    _STORAGE_CLOUD_EXTRA as _STORAGE_CLOUD_EXTRA,
    _VERSION_PATTERN as _VERSION_PATTERN,
    DependencySyncError as DependencySyncError,
    ProjectDependencySyncResult as ProjectDependencySyncResult,
    _build_module_path_dependency_value as _build_module_path_dependency_value,
    _extract_dependency_name as _extract_dependency_name,
    _find_local_wheel_candidates as _find_local_wheel_candidates,
    _iter_required_dependency_names as _iter_required_dependency_names,
    _load_poetry_dependencies as _load_poetry_dependencies,
    _load_project_name as _load_project_name,
    _load_toml_file as _load_toml_file,
    _raise_for_missing_explicit_wheel as _raise_for_missing_explicit_wheel,
    _resolve_local_wheel_dependency as _resolve_local_wheel_dependency,
    _resolve_wheelhouse_dir as _resolve_wheelhouse_dir,
    _should_skip_manifest_dependency as _should_skip_manifest_dependency,
    resolve_embedded_module_install_path as resolve_embedded_module_install_path,
)
from quickscale_cli.utils._dependency_write import (
    _append_dependency_entries as _append_dependency_entries,
    _build_path_dependency_overrides as _build_path_dependency_overrides,
    _extract_version_tuple as _extract_version_tuple,
    _has_unresolvable_path_dependency as _has_unresolvable_path_dependency,
    _manifest_version_spec as _manifest_version_spec,
    _patch_module_path_dependencies as _patch_module_path_dependencies,
    _prefer_dependency_value as _prefer_dependency_value,
    _render_toml_literal as _render_toml_literal,
    _resolve_declared_dependency_path as _resolve_declared_dependency_path,
    _rewrite_dependency_lines as _rewrite_dependency_lines,
    _update_dependency_entries as _update_dependency_entries,
    _write_validated_toml as _write_validated_toml,
)
from quickscale_cli.utils._dependency_sync_ops import (
    _apply_pending_dependency_updates as _apply_pending_dependency_updates,
    _merge_preferred_dependency as _merge_preferred_dependency,
    _record_repin_update as _record_repin_update,
    _resolve_declared_dependency_value as _resolve_declared_dependency_value,
    _version_satisfies_bounded_pin as _version_satisfies_bounded_pin,
    _wheel_distribution_version as _wheel_distribution_version,
    sync_project_core_dependency as sync_project_core_dependency,
    sync_project_module_dependencies as sync_project_module_dependencies,
)
