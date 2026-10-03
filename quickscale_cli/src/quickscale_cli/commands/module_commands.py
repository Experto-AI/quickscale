"""Module management commands for QuickScale CLI.

The implementation lives in private sibling modules grouped by concern
(``_module_shared``, ``_module_embed``, ``_module_update``,
``_module_update_io``, ``_module_push``); this module owns the public command surface, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

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
from quickscale_cli.commands._module_shared import (
    ModuleExecutionMode as ModuleExecutionMode,
    STANDALONE_MODULE_EXECUTION_MODE as STANDALONE_MODULE_EXECUTION_MODE,
    APPLY_MODULE_EXECUTION_MODE as APPLY_MODULE_EXECUTION_MODE,
    ModuleEmbedProvenance as ModuleEmbedProvenance,
)
from quickscale_cli.commands._module_embed import (
    embed_module as embed_module,
)
from quickscale_cli.commands._module_update import (
    update as update,
)
from quickscale_cli.commands._module_push import (
    push as push,
)
