"""
QuickScale runtime API facade — public re-export surface for generated-project code.

SA9.3: Pure re-export layer. No behavior change. All symbols are imported from
their canonical internal locations and re-exported so that module code imports
only from ``quickscale_core.runtime`` instead of reaching directly into
``dr_engine``, ``contracts``, or ``manifest`` internals.

SA9.4: Backups module imports now go through this facade instead of reaching
directly into ``dr_engine.{orchestration,primitives,recovery,verification}``.

NOTE: Symbols from ``dr_engine.orchestration``, ``dr_engine.recovery``, and
``dr_engine.verification`` are loaded lazily because ``orchestration`` depends
on ``quickscale_modules_backups.models`` at module level.  Direct imports
(``from quickscale_core.runtime import X``) work transparently via
``__getattr__`` — no extra imports needed by callers.
"""

from __future__ import annotations

import typing

# ---------------------------------------------------------------------------
# Social-manifest surface: path constants
# ---------------------------------------------------------------------------
from quickscale_core.contracts.module_options import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)

# ---------------------------------------------------------------------------
# Social-manifest surface: resolver
# ---------------------------------------------------------------------------
from quickscale_core.contracts.resolvers import resolve_social_module_options

# ---------------------------------------------------------------------------
# DR adapter surface
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.adapter import (
    ADAPTER_FUNCTIONS,
    build_database_plan,
    capture_snapshot,
    execute_database_restore,
    fetch_snapshot_report,
    record_verification,
    set_rollback_pin,
    sync_media,
)
from quickscale_core.dr_engine.primitives import BackupError

# ---------------------------------------------------------------------------
# Manifest assembler and resolver
# ---------------------------------------------------------------------------
from quickscale_core.manifest.assembler import assemble_wiring_spec
from quickscale_core.manifest.resolver import ResolverResult

# ---------------------------------------------------------------------------
# Social-manifest surface: renderers and helpers
# ---------------------------------------------------------------------------
from quickscale_core.manifest.social_manifest import (
    load_social_manifest,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    render_social_managed_views_module,
    social_provider_supports_embeds,
)

# ---------------------------------------------------------------------------
# Module wiring spec
# ---------------------------------------------------------------------------
from quickscale_core.module_wiring import ModuleWiringSpec

# ---------------------------------------------------------------------------
# Public API — __all__ includes both eagerly-available and lazy symbols
# ---------------------------------------------------------------------------

__all__ = [
    # DR adapter surface
    "ADAPTER_FUNCTIONS",
    "BackupError",
    "build_database_plan",
    "capture_snapshot",
    "execute_database_restore",
    "fetch_snapshot_report",
    "record_verification",
    "set_rollback_pin",
    "sync_media",
    # DR orchestration surface (backups module — lazy-loaded)
    "BackupLockError",  # noqa: F822
    "StagedAdminRestoreUpload",  # noqa: F822
    "build_backup_filename",  # noqa: F822
    "build_backup_snapshot_report",  # noqa: F822
    "clear_backup_snapshot_rollback_pin",  # noqa: F822
    "create_backup",  # noqa: F822
    "delete_artifact_files",  # noqa: F822
    "download_backup_path",  # noqa: F822
    "get_backup_snapshot",  # noqa: F822
    "get_local_backup_directory",  # noqa: F822
    "prune_expired_backups",  # noqa: F822
    "record_backup_snapshot_verification",  # noqa: F822
    "report_backup_snapshot",  # noqa: F822
    "restore_admin_uploaded_backup",  # noqa: F822
    "restore_backup_artifact",  # noqa: F822
    "restore_backup_source",  # noqa: F822
    # Admin uploaded-file staging/resolution/cleanup seam
    "_cleanup_admin_restore_upload_directory",  # noqa: F822
    "_resolve_admin_uploaded_restore_artifact",  # noqa: F822
    "_stage_admin_restore_upload",  # noqa: F822
    "set_backup_snapshot_rollback_pin",  # noqa: F822
    "sync_backup_snapshot_media",  # noqa: F822
    "validate_backup_artifact",  # noqa: F822
    # DR primitives surface
    "BackupConfigurationError",  # noqa: F822
    "BackupPolicySnapshot",  # noqa: F822
    "ShellCommandRunner",  # noqa: F822
    # DR recovery surface (backups module — lazy-loaded)
    "ArtifactLike",  # noqa: F822
    "BackupRestoreBlocked",  # noqa: F822
    "RemoteMaterializer",  # noqa: F822
    "ResolvedRestoreSource",  # noqa: F822
    "RestoreResult",  # noqa: F822
    "RestoreSourceResolutionMode",  # noqa: F822
    "RestoreWarning",  # noqa: F822
    # Manifest/resolver types
    "ModuleWiringSpec",
    "ResolverResult",
    "assemble_wiring_spec",
    # Social-manifest path constants
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LINK_TREE_PATH",
    # Social-manifest surface
    "load_social_manifest",
    "render_social_managed_init_module",
    "render_social_managed_urls_module",
    "render_social_managed_views_module",
    "resolve_social_module_options",
    "social_provider_supports_embeds",
]

# ---------------------------------------------------------------------------
# Lazy loading — backup-dependent submodules
# ---------------------------------------------------------------------------
# ``dr_engine.orchestration`` imports ``quickscale_modules_backups.models`` at
# module level, so we cannot import it eagerly without the backups module
# installed.  The following tables define which symbols belong to which
# submodule.  ``__getattr__`` loads the correct submodule on first access.

_LAZY_ADAPTER_SYMBOLS: set[str] = set()
_LAZY_ORCHESTRATION_SYMBOLS: frozenset[str] = frozenset(
    {
        "BackupLockError",
        "StagedAdminRestoreUpload",
        "_build_env_var_manifest",
        "_build_media_sync_manifest",
        "_build_policy_snapshot_from_model",
        "_build_policy_snapshot_from_settings",
        "_build_release_metadata",
        "_build_snapshot_full_backup_contract",
        "_build_snapshot_local_root",
        "_build_snapshot_remote_root",
        "_cleanup_local_backup_file",
        "_clear_appended_artifact_note",
        "_collect_module_versions",
        "_database_server_version_query",
        "_delete_private_remote_key",
        "_ensure_default_policy_internal",
        "_ensure_postgresql_18_restore_runtime",
        "_get_git_revision",
        "_get_project_slug",
        "_get_restore_compatibility_issues",
        "_get_source_environment",
        "_is_path_within_root",
        "_load_active_policy_snapshot",
        "_load_snapshot_sidecar_payload",
        "_materialize_private_remote_key",
        "_path_uses_symlink_within_root",
        "_read_setting_value",
        "_record_prune_failure_without_masking_success",
        "_release_backup_lock",
        "_replace_policy_remote_prefix",
        "_resolve_private_remote_credentials",
        "_resolve_restore_source",
        "_restore_execution_allowed",
        "_rollback_remote_upload_after_persistence_failure",
        "_snapshot_sidecar_path",
        "_upload_to_private_remote",
        "_validate_policy_snapshot_internal",
        "build_backup_filename",
        "build_backup_snapshot_report",
        "clear_backup_snapshot_rollback_pin",
        "create_backup",
        "delete_artifact_files",
        "download_backup_path",
        "get_backup_snapshot",
        "get_local_backup_directory",
        "prune_expired_backups",
        "record_backup_snapshot_verification",
        "report_backup_snapshot",
        "restore_admin_uploaded_backup",
        "restore_backup_artifact",
        "restore_backup_source",
        # Admin uploaded-file staging/resolution/cleanup seam
        "_cleanup_admin_restore_upload_directory",
        "_resolve_admin_uploaded_restore_artifact",
        "_stage_admin_restore_upload",
        "set_backup_snapshot_rollback_pin",
        "sync_backup_snapshot_media",
        "validate_backup_artifact",
    }
)
_LAZY_PRIMITIVES_ADDITIONAL_SYMBOLS: frozenset[str] = frozenset(
    {
        "BackupConfigurationError",
        "BackupPolicySnapshot",
        "ShellCommandRunner",
        "_DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR",
        "_DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
        "_ENV_VAR_MANIFEST_FILENAME",
        "_MEDIA_SYNC_MANIFEST_FILENAME",
        "_PROMOTION_VERIFICATION_FILENAME",
        "_RELEASE_METADATA_FILENAME",
        "_REQUIRED_POSTGRESQL_MAJOR",
        "_REQUIRED_SNAPSHOT_SIDECAR_FILENAMES",
        "_SNAPSHOTS_DIRECTORY_NAME",
        "_SNAPSHOT_DATABASE_DIRECTORY_NAME",
        "_build_pg_dump_command",
        "_build_pg_restore_command",
        "_build_snapshot_child_descriptor",
        "_compute_sha256",
        "_database_engine_family",
        "_dump_postgresql_database",
        "_expected_backup_format_for_engine",
        "_extract_any_major_version",
        "_extract_leading_major_version",
        "_get_postgresql_tool_version",
        "_mint_snapshot_id",
        "_postgresql_18_client_tooling_guidance",
        "_relative_snapshot_child_path",
        "_run_shell_command",
        "_write_json_file",
    }
)
_LAZY_RECOVERY_SYMBOLS: frozenset[str] = frozenset(
    {
        "ArtifactLike",
        "BackupRestoreBlocked",
        "RemoteMaterializer",
        "ResolvedRestoreSource",
        "RestoreResult",
        "RestoreSourceResolutionMode",
        "RestoreWarning",
        "_collect_local_backup_validation_issues",
        "_detect_restore_file_format",
        "_ensure_operator_supplied_custom_archive_valid",
        "_execute_restore_for_resolved_source",
        "_get_restore_source_compatibility_issues",
        "_get_restore_source_validation_issues",
        "_normalize_restore_file_path",
    }
)
_LAZY_VERIFICATION_SYMBOLS: frozenset[str] = frozenset(
    {
        "_build_clear_rollback_pin_fields",
        "_build_verification_payload",
        "_compute_rollback_pin_fields",
        "_validate_verification_inputs",
    }
)


def __getattr__(name: str) -> typing.Any:
    """Lazy-load backup-dependent symbols from their canonical submodules."""
    if name in _LAZY_ORCHESTRATION_SYMBOLS:
        import quickscale_core.dr_engine.orchestration as _lazy_orch

        return getattr(_lazy_orch, name)

    if name in _LAZY_PRIMITIVES_ADDITIONAL_SYMBOLS:
        import quickscale_core.dr_engine.primitives as _lazy_prim

        return getattr(_lazy_prim, name)

    if name in _LAZY_RECOVERY_SYMBOLS:
        import quickscale_core.dr_engine.recovery as _lazy_rec

        return getattr(_lazy_rec, name)

    if name in _LAZY_VERIFICATION_SYMBOLS:
        import quickscale_core.dr_engine.verification as _lazy_ver

        return getattr(_lazy_ver, name)

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Include lazy symbols in module dir()."""
    return sorted(__all__)
