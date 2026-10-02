"""Module management commands for QuickScale CLI.

The implementation lives in private sibling modules grouped by concern
(``_module_shared``, ``_module_embed``, ``_module_update``,
``_module_update_io``, ``_module_push``); this module re-exports every name
that previously lived here (Module Conventions rule 28), so existing
``quickscale_cli.commands.module_commands`` imports and test patch targets
keep working unchanged.
"""

import shutil as shutil
import subprocess as subprocess
from dataclasses import dataclass as dataclass
from datetime import datetime as datetime
from collections.abc import Callable as Callable
from pathlib import Path as Path
from tempfile import TemporaryDirectory as TemporaryDirectory
from typing import (
    Any as Any,
    Literal as Literal,
)
import click as click
from quickscale_core import __version__ as quickscale_version  # noqa: F401
from quickscale_core.contracts.module_catalog import (
    get_module_readiness_reason as get_module_readiness_reason,
)
from quickscale_core.schema.config_schema import validate_config as validate_config
from quickscale_core.schema.state_schema import (
    ManagedFileRecord as ManagedFileRecord,
    StateError as StateError,
    StateManager as StateManager,
)
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError as DependencySyncError,
    resolve_embedded_module_install_path as _resolve_install_path_from_dependency_sync,  # noqa: F401
    sync_project_module_dependencies as sync_project_module_dependencies,
)
from quickscale_cli.utils.auth_migration import (
    assess_auth_migration_state as assess_auth_migration_state,
    format_auth_migration_remediation as format_auth_migration_remediation,
)
from quickscale_cli.utils.module_wiring_manager import (
    regenerate_managed_wiring as regenerate_managed_wiring,
)
from quickscale_core.apply import (
    LedgerError as LedgerError,
    LedgerManager as LedgerManager,
)
from quickscale_core.config import (
    ConfigError as ConfigError,
    add_module as add_module,
    load_config as load_config,
    normalize_installed_version as normalize_installed_version,
    remove_module as remove_module,
)
from quickscale_core.advisory_lock import (
    AdvisoryLock as AdvisoryLock,
    AdvisoryLockContentionError as AdvisoryLockContentionError,
)
from quickscale_core.project_state import (
    DEFAULT_MANAGED_WIRING_PATHS as DEFAULT_MANAGED_WIRING_PATHS,
    ProjectStateManager as ProjectStateManager,
    check_version_drift as check_version_drift,
    compute_file_hashes as compute_file_hashes,
)
from quickscale_core.manifest.loader import (
    ManifestError as ManifestError,
    ModuleVersionMismatchError as ModuleVersionMismatchError,
    assert_manifest_version_matches_core as assert_manifest_version_matches_core,
    get_manifest_for_module as get_manifest_for_module,
)
from quickscale_core.utils.git_utils import (
    GitError as GitError,
    check_remote_branch_exists as check_remote_branch_exists,
    check_remote_tag_exists as check_remote_tag_exists,
    is_git_repo as is_git_repo,
    is_working_directory_clean as is_working_directory_clean,
    resolve_remote_ref as resolve_remote_ref,
    resolve_remote_tag as resolve_remote_tag,
    resolve_split_branch as resolve_split_branch,
    resolve_split_tag as resolve_split_tag,
    run_git_subtree_add as run_git_subtree_add,
    run_git_subtree_pull as run_git_subtree_pull,
    run_git_subtree_push as run_git_subtree_push,
    validate_tag_name as validate_tag_name,
)
from quickscale_core.utils.poetry_env import (
    build_isolated_poetry_env as build_isolated_poetry_env,
)
from .module_config import MODULE_CONFIGURATOR_REGISTRY as MODULE_CONFIGURATOR_REGISTRY
from .contract_vintage import (
    enforce_shipped_contract_vintage as enforce_shipped_contract_vintage,
    record_contract_adoption as record_contract_adoption,
)
from .module_output import (
    _print_installation_error as _print_installation_error,
    _report_local_pre_pull_guard_block as _report_local_pre_pull_guard_block,
    _report_missing_split_tag as _report_missing_split_tag,
    _report_split_ref_override as _report_split_ref_override,
    _resolve_embed_source_ref as _resolve_embed_source_ref,
    _validate_embed_theme as _validate_embed_theme,
)
from quickscale_cli.commands._module_shared import (
    ModuleExecutionMode as ModuleExecutionMode,
    STANDALONE_MODULE_EXECUTION_MODE as STANDALONE_MODULE_EXECUTION_MODE,
    APPLY_MODULE_EXECUTION_MODE as APPLY_MODULE_EXECUTION_MODE,
    _LazyModuleChoice as _LazyModuleChoice,
    _UpdatePathSnapshot as _UpdatePathSnapshot,
    ModuleEmbedProvenance as ModuleEmbedProvenance,
    _validate_git_environment as _validate_git_environment,
    _validate_module_not_exists as _validate_module_not_exists,
    _validate_remote_branch as _validate_remote_branch,
    _check_auth_module_migrations as _check_auth_module_migrations,
    _resolve_embedded_module_install_path as _resolve_embedded_module_install_path,
    _read_embedded_module_version as _read_embedded_module_version,
    _sync_state_module_version as _sync_state_module_version,
    _warn_version_drift_for_update as _warn_version_drift_for_update,
    _validate_module_readiness as _validate_module_readiness,
    _validate_update_environment as _validate_update_environment,
)
from quickscale_cli.commands._module_embed import (
    _cleanup_failed_apply_embed as _cleanup_failed_apply_embed,
    _record_embed_provenance as _record_embed_provenance,
    _cleanup_failed_apply_embed_if_needed as _cleanup_failed_apply_embed_if_needed,
    _perform_module_embed as _perform_module_embed,
    embed_module as embed_module,
    _install_module_dependencies as _install_module_dependencies,
    _sync_module_dependencies as _sync_module_dependencies,
)
from quickscale_cli.commands._module_update import (
    _ensure_authoritative_state_for_update as _ensure_authoritative_state_for_update,
    _load_update_recovery_state as _load_update_recovery_state,
    _check_local_pre_pull_guard as _check_local_pre_pull_guard,
    _rollback_failed_module_update as _rollback_failed_module_update,
    _report_module_update_error as _report_module_update_error,
    _update_single_module as _update_single_module,
    update as update,
)
from quickscale_cli.commands._module_update_io import (
    _remove_update_path as _remove_update_path,
    _snapshot_update_path as _snapshot_update_path,
    _restore_update_snapshot as _restore_update_snapshot,
    _restore_update_snapshots as _restore_update_snapshots,
    _record_update_mutation_snapshots as _record_update_mutation_snapshots,
    _refresh_git_index_after_update_rollback as _refresh_git_index_after_update_rollback,
    _commit_contract_adoption as _commit_contract_adoption,
    _regenerate_and_record_managed_wiring as _regenerate_and_record_managed_wiring,
    _record_managed_wiring_hashes as _record_managed_wiring_hashes,
    _git_tracks_path as _git_tracks_path,
    _path_in_commit as _path_in_commit,
    _commit_regenerated_managed_wiring as _commit_regenerated_managed_wiring,
    _roll_back_partial_module_update as _roll_back_partial_module_update,
    _commit_module_update as _commit_module_update,
)
from quickscale_cli.commands._module_push import (
    push as push,
)
