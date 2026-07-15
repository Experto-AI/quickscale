"""
QuickScale runtime API facade — DR / disaster recovery re-export surface.

This sub-module exports the DR adapter surface, DR engine primitives, and
all backup-dependent orchestration / recovery / persistence / verification
symbols as eager imports from the ``dr_engine`` sub-packages.  Module-owned
manifest adapters that only need the manifest/resolver surface should import
from ``quickscale_core.runtime.manifest`` instead.
"""

from __future__ import annotations

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
# DR orchestration surface — eager imports from orchestration (Django-aware)
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.orchestration import (  # noqa: F401
    BackupLockError,
    StagedAdminRestoreUpload,
    _build_env_var_manifest,
    _build_media_sync_manifest,
    _build_policy_snapshot_from_model,
    _build_policy_snapshot_from_settings,
    _build_release_metadata,
    _build_snapshot_full_backup_contract,
    _build_snapshot_local_root,
    _build_snapshot_remote_root,
    _cleanup_admin_restore_upload_directory,
    _cleanup_local_backup_file,
    _clear_appended_artifact_note,
    _collect_module_versions,
    _database_server_version_query,
    _delete_private_remote_key,
    _ensure_default_policy_internal,
    _ensure_postgresql_18_restore_runtime,
    _get_authoritative_snapshot_for_artifact,
    _get_git_revision,
    _get_project_slug,
    _get_restore_compatibility_issues,
    _get_source_environment,
    _is_path_within_root,
    _load_active_policy_snapshot,
    _load_snapshot_sidecar_payload,
    _materialize_private_remote_key,
    _path_uses_symlink_within_root,
    _read_setting_value,
    _record_prune_failure_without_masking_success,
    _release_backup_lock,
    _replace_policy_remote_prefix,
    _resolve_admin_uploaded_restore_artifact,
    _resolve_private_remote_credentials,
    _resolve_restore_source,
    _restore_execution_allowed,
    _rollback_remote_upload_after_persistence_failure,
    _snapshot_sidecar_path,
    _stage_admin_restore_upload,
    _upload_to_private_remote,
    _validate_policy_snapshot_internal,
    build_backup_filename,
    build_backup_snapshot_report,
    clear_backup_snapshot_rollback_pin,
    create_backup,
    delete_artifact_files,
    download_backup_path,
    get_backup_snapshot,
    get_local_backup_directory,
    prune_expired_backups,
    record_backup_snapshot_verification,
    report_backup_snapshot,
    restore_admin_uploaded_backup,
    restore_backup_artifact,
    restore_backup_source,
    set_backup_snapshot_rollback_pin,
    sync_backup_snapshot_media,
    validate_backup_artifact,
)

# ---------------------------------------------------------------------------
# DR primitives surface — additional Django-free symbols
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.primitives import (  # noqa: F401
    BackupConfigurationError,
    BackupPolicySnapshot,
    ShellCommandRunner,
    _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    _ENV_VAR_MANIFEST_FILENAME,
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOTS_DIRECTORY_NAME,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
    _build_pg_dump_command,
    _build_pg_restore_command,
    _build_snapshot_child_descriptor,
    _compute_sha256,
    _database_engine_family,
    _dump_postgresql_database,
    _expected_backup_format_for_engine,
    _extract_any_major_version,
    _extract_leading_major_version,
    _get_postgresql_tool_version,
    _mint_snapshot_id,
    _postgresql_18_client_tooling_guidance,
    _relative_snapshot_child_path,
    _run_shell_command,
    _write_json_file,
)

# ---------------------------------------------------------------------------
# DR recovery surface — Django-free restore contracts and helpers
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.recovery import (  # noqa: F401
    ArtifactLike,
    BackupRestoreBlocked,
    RemoteMaterializer,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
    _collect_local_backup_validation_issues,
    _detect_restore_file_format,
    _ensure_operator_supplied_custom_archive_valid,
    _execute_restore_for_resolved_source,
    _get_restore_source_compatibility_issues,
    _get_restore_source_validation_issues,
    _normalize_restore_file_path,
)

# ---------------------------------------------------------------------------
# DR persistence surface — Django-free persistence contracts
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.persistence import (  # noqa: F401
    BackupArtifactPersistence,
    BackupPolicyPersistence,
    PersistedBackupArtifact,
    PersistedBackupPolicy,
    PersistedBackupSnapshot,
    create_artifact,
    create_snapshot,
    ensure_default_policy,
    get_backup_artifact,
    get_authoritative_snapshot_for_artifact,
    has_any_policy,
    iter_expired_snapshots,
    iter_expired_unlinked_artifacts,
    load_default_policy,
    refresh_snapshot,
    register_backup_persistence,
    resolve_admin_uploaded_restore_artifact,
    save_artifact,
    save_default_policy,
    save_snapshot,
    update_artifact_after_restore,
)

# ---------------------------------------------------------------------------
# DR verification surface — Django-free verification helpers
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.verification import (  # noqa: F401
    _build_clear_rollback_pin_fields,
    _build_verification_payload,
    _compute_rollback_pin_fields,
    _validate_verification_inputs,
)

# ---------------------------------------------------------------------------
# Public API — DR surface (both eagerly-available and lazy symbols)
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
    # DR orchestration surface
    "BackupLockError",
    "StagedAdminRestoreUpload",
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
    # DR primitives surface
    "BackupConfigurationError",
    "BackupPolicySnapshot",
    "ShellCommandRunner",
    # DR recovery surface
    "ArtifactLike",
    "BackupRestoreBlocked",
    "RemoteMaterializer",
    "ResolvedRestoreSource",
    "RestoreResult",
    "RestoreSourceResolutionMode",
    "RestoreWarning",
    # DR persistence surface
    "BackupArtifactPersistence",
    "BackupPolicyPersistence",
    "PersistedBackupArtifact",
    "PersistedBackupPolicy",
    "PersistedBackupSnapshot",
    "create_artifact",
    "create_snapshot",
    "ensure_default_policy",
    "get_backup_artifact",
    "get_authoritative_snapshot_for_artifact",
    "has_any_policy",
    "iter_expired_snapshots",
    "iter_expired_unlinked_artifacts",
    "load_default_policy",
    "refresh_snapshot",
    "register_backup_persistence",
    "resolve_admin_uploaded_restore_artifact",
    "save_artifact",
    "save_default_policy",
    "save_snapshot",
    "update_artifact_after_restore",
]


def __dir__() -> list[str]:
    """Return sorted module __all__ for dir()."""
    return sorted(__all__)
