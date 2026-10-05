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
    ADAPTER_FUNCTIONS as ADAPTER_FUNCTIONS,
    build_database_plan as build_database_plan,
    capture_snapshot as capture_snapshot,
    execute_database_restore as execute_database_restore,
    fetch_snapshot_report as fetch_snapshot_report,
    record_verification as record_verification,
    set_rollback_pin as set_rollback_pin,
    sync_media as sync_media,
)
from quickscale_core.dr_engine.primitives import BackupError as BackupError

# ---------------------------------------------------------------------------
# DR orchestration surface — eager imports from orchestration (Django-aware)
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine._lock import (
    BackupLockError as BackupLockError,
    StagedAdminRestoreUpload as StagedAdminRestoreUpload,
    _cleanup_local_backup_file as _cleanup_local_backup_file,
    _release_backup_lock as _release_backup_lock,
)
from quickscale_core.dr_engine._sidecar import (
    _build_env_var_manifest as _build_env_var_manifest,
    _build_media_sync_manifest as _build_media_sync_manifest,
    _load_snapshot_sidecar_payload as _load_snapshot_sidecar_payload,
)
from quickscale_core.dr_engine._policy import (
    _build_policy_snapshot_from_model as _build_policy_snapshot_from_model,
    _ensure_default_policy_internal as _ensure_default_policy_internal,
    _load_active_policy_snapshot as _load_active_policy_snapshot,
    _validate_policy_snapshot_internal as _validate_policy_snapshot_internal,
)
from quickscale_core.dr_engine._metadata import (
    _build_release_metadata as _build_release_metadata,
    _collect_module_versions as _collect_module_versions,
    _database_server_version_query as _database_server_version_query,
    _get_git_revision as _get_git_revision,
    _get_project_slug as _get_project_slug,
    _get_source_environment as _get_source_environment,
    _read_setting_value as _read_setting_value,
)
from quickscale_core.dr_engine._report import (
    _build_snapshot_full_backup_contract as _build_snapshot_full_backup_contract,
    build_backup_snapshot_report as build_backup_snapshot_report,
    clear_backup_snapshot_rollback_pin as clear_backup_snapshot_rollback_pin,
    record_backup_snapshot_verification as record_backup_snapshot_verification,
    report_backup_snapshot as report_backup_snapshot,
    set_backup_snapshot_rollback_pin as set_backup_snapshot_rollback_pin,
    validate_backup_artifact as validate_backup_artifact,
)
from quickscale_core.dr_engine._paths import (
    _build_snapshot_local_root as _build_snapshot_local_root,
    _build_snapshot_remote_root as _build_snapshot_remote_root,
    _replace_policy_remote_prefix as _replace_policy_remote_prefix,
    _snapshot_sidecar_path as _snapshot_sidecar_path,
    build_backup_filename as build_backup_filename,
    get_local_backup_directory as get_local_backup_directory,
)
from quickscale_core.dr_engine._restore import (
    _cleanup_admin_restore_upload_directory as _cleanup_admin_restore_upload_directory,
    _ensure_postgresql_18_restore_runtime as _ensure_postgresql_18_restore_runtime,
    _get_restore_compatibility_issues as _get_restore_compatibility_issues,
    _resolve_admin_uploaded_restore_artifact as _resolve_admin_uploaded_restore_artifact,
    _resolve_restore_source as _resolve_restore_source,
    _restore_execution_allowed as _restore_execution_allowed,
    _stage_admin_restore_upload as _stage_admin_restore_upload,
    restore_admin_uploaded_backup as restore_admin_uploaded_backup,
    restore_backup_artifact as restore_backup_artifact,
    restore_backup_source as restore_backup_source,
)
from quickscale_core.dr_engine._state import (
    _clear_appended_artifact_note as _clear_appended_artifact_note,
    _get_authoritative_snapshot_for_artifact as _get_authoritative_snapshot_for_artifact,
    _record_prune_failure_without_masking_success as _record_prune_failure_without_masking_success,
    _rollback_remote_upload_after_persistence_failure as _rollback_remote_upload_after_persistence_failure,
    get_backup_snapshot as get_backup_snapshot,
)
from quickscale_core.dr_engine._remote import (
    _delete_private_remote_key as _delete_private_remote_key,
    _materialize_private_remote_key as _materialize_private_remote_key,
    _resolve_private_remote_credentials as _resolve_private_remote_credentials,
    _upload_to_private_remote as _upload_to_private_remote,
)
from quickscale_core.dr_engine._prune import (
    _is_path_within_root as _is_path_within_root,
    _path_uses_symlink_within_root as _path_uses_symlink_within_root,
    delete_artifact_files as delete_artifact_files,
    download_backup_path as download_backup_path,
    prune_expired_backups as prune_expired_backups,
)
from quickscale_core.dr_engine._capture import create_backup as create_backup
from quickscale_core.dr_engine._media import (
    sync_backup_snapshot_media as sync_backup_snapshot_media,
)

# ---------------------------------------------------------------------------
# DR primitives surface — additional Django-free symbols
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.primitives import (  # noqa: F401
    BackupConfigurationError as BackupConfigurationError,
    BackupPolicySnapshot as BackupPolicySnapshot,
    ShellCommandRunner as ShellCommandRunner,
    _ENV_VAR_MANIFEST_FILENAME as _ENV_VAR_MANIFEST_FILENAME,
    _MEDIA_SYNC_MANIFEST_FILENAME as _MEDIA_SYNC_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME as _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME as _RELEASE_METADATA_FILENAME,
    _REQUIRED_POSTGRESQL_MAJOR as _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES as _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOTS_DIRECTORY_NAME as _SNAPSHOTS_DIRECTORY_NAME,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME as _SNAPSHOT_DATABASE_DIRECTORY_NAME,
    _build_pg_dump_command as _build_pg_dump_command,
    _build_pg_restore_command as _build_pg_restore_command,
    _build_snapshot_child_descriptor as _build_snapshot_child_descriptor,
    _compute_sha256 as _compute_sha256,
    _database_engine_family as _database_engine_family,
    _dump_postgresql_database as _dump_postgresql_database,
    _expected_backup_format_for_engine as _expected_backup_format_for_engine,
    _extract_any_major_version as _extract_any_major_version,
    _extract_leading_major_version as _extract_leading_major_version,
    _get_postgresql_tool_version as _get_postgresql_tool_version,
    _mint_snapshot_id as _mint_snapshot_id,
    _postgresql_18_client_tooling_guidance as _postgresql_18_client_tooling_guidance,
    _relative_snapshot_child_path as _relative_snapshot_child_path,
    _run_shell_command as _run_shell_command,
    _write_json_file as _write_json_file,
)

# ---------------------------------------------------------------------------
# DR recovery surface — Django-free restore contracts and helpers
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.recovery import (  # noqa: F401
    ArtifactLike as ArtifactLike,
    BackupRestoreBlocked as BackupRestoreBlocked,
    RemoteMaterializer as RemoteMaterializer,
    ResolvedRestoreSource as ResolvedRestoreSource,
    RestoreResult as RestoreResult,
    RestoreSourceResolutionMode as RestoreSourceResolutionMode,
    RestoreWarning as RestoreWarning,
    _collect_local_backup_validation_issues as _collect_local_backup_validation_issues,
    _detect_restore_file_format as _detect_restore_file_format,
    _ensure_operator_supplied_custom_archive_valid as _ensure_operator_supplied_custom_archive_valid,
    _execute_restore_for_resolved_source as _execute_restore_for_resolved_source,
    _get_restore_source_compatibility_issues as _get_restore_source_compatibility_issues,
    _get_restore_source_validation_issues as _get_restore_source_validation_issues,
    _normalize_restore_file_path as _normalize_restore_file_path,
)

# ---------------------------------------------------------------------------
# DR persistence surface — Django-free persistence contracts
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.persistence import (  # noqa: F401
    BackupArtifactPersistence as BackupArtifactPersistence,
    BackupPolicyPersistence as BackupPolicyPersistence,
    PersistedBackupArtifact as PersistedBackupArtifact,
    PersistedBackupPolicy as PersistedBackupPolicy,
    PersistedBackupSnapshot as PersistedBackupSnapshot,
    create_artifact as create_artifact,
    create_snapshot as create_snapshot,
    ensure_default_policy as ensure_default_policy,
    get_backup_artifact as get_backup_artifact,
    get_authoritative_snapshot_for_artifact as get_authoritative_snapshot_for_artifact,
    has_any_policy as has_any_policy,
    iter_expired_snapshots as iter_expired_snapshots,
    iter_expired_unlinked_artifacts as iter_expired_unlinked_artifacts,
    load_default_policy as load_default_policy,
    refresh_snapshot as refresh_snapshot,
    register_backup_persistence as register_backup_persistence,
    resolve_admin_uploaded_restore_artifact as resolve_admin_uploaded_restore_artifact,
    save_artifact as save_artifact,
    save_default_policy as save_default_policy,
    save_snapshot as save_snapshot,
    settings_policy_snapshot as settings_policy_snapshot,
    update_artifact_after_restore as update_artifact_after_restore,
)

# ---------------------------------------------------------------------------
# DR verification surface — Django-free verification helpers
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.verification import (  # noqa: F401
    _build_clear_rollback_pin_fields as _build_clear_rollback_pin_fields,
    _build_verification_payload as _build_verification_payload,
    _compute_rollback_pin_fields as _compute_rollback_pin_fields,
    _validate_verification_inputs as _validate_verification_inputs,
)

# NOTE: this sub-module deliberately declares no ``__all__``.  The combined
# ``quickscale_core.runtime`` facade owns the single hardcoded public-surface
# literal that the SA9.2 compatibility checker resolves; duplicating it here
# would only create a second list to keep in sync.


def __dir__() -> list[str]:
    """Return the public DR surface for dir()."""
    return sorted(name for name in globals() if not name.startswith("_"))
