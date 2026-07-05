"""
Thin Django-facing service layer for the QuickScale backups module.

All DR orchestration logic lives in ``quickscale_core.dr_engine.orchestration``.
This module keeps the small set of Django-facing wrappers and shared protocol
types that the backups app still owns locally.

``services.py`` is intentionally under 400 LOC. Every new orchestration
feature should go in ``dr_engine/``, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from quickscale_core.runtime import (  # noqa: F401
    _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    _ENV_VAR_MANIFEST_FILENAME,
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
    _SNAPSHOTS_DIRECTORY_NAME,
    # recovery surface
    ArtifactLike,
    # primitives surface
    BackupConfigurationError,
    BackupError,
    # orchestration surface
    BackupLockError,
    BackupPolicySnapshot,
    BackupRestoreBlocked,
    RemoteMaterializer,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
    ShellCommandRunner,
    StagedAdminRestoreUpload,
    # verification surface
    _build_clear_rollback_pin_fields,
    _build_env_var_manifest,
    _build_media_sync_manifest,
    _build_pg_dump_command,
    _build_pg_restore_command,
    _build_policy_snapshot_from_model,
    _build_policy_snapshot_from_settings,
    _build_release_metadata,
    _build_snapshot_child_descriptor,
    _build_snapshot_full_backup_contract,
    _build_snapshot_local_root,
    _build_snapshot_remote_root,
    _build_verification_payload,
    # Admin uploaded-file staging/resolution/cleanup seam
    _cleanup_admin_restore_upload_directory,
    _cleanup_local_backup_file,
    _clear_appended_artifact_note,
    _collect_local_backup_validation_issues,
    _collect_module_versions,
    _compute_rollback_pin_fields,
    _compute_sha256,
    _database_engine_family,
    _database_server_version_query,
    _delete_private_remote_key,
    _detect_restore_file_format,
    _dump_postgresql_database,
    _ensure_operator_supplied_custom_archive_valid,
    _ensure_postgresql_18_restore_runtime,
    _execute_restore_for_resolved_source,
    _expected_backup_format_for_engine,
    _extract_any_major_version,
    _extract_leading_major_version,
    _get_git_revision,
    _get_postgresql_tool_version,
    _get_project_slug,
    _get_restore_compatibility_issues,
    _get_restore_source_compatibility_issues,
    _get_restore_source_validation_issues,
    _get_source_environment,
    _is_path_within_root,
    _load_snapshot_sidecar_payload,
    _materialize_private_remote_key,
    _mint_snapshot_id,
    _normalize_restore_file_path,
    _path_uses_symlink_within_root,
    _postgresql_18_client_tooling_guidance,
    _read_setting_value,
    _record_prune_failure_without_masking_success,
    _relative_snapshot_child_path,
    _release_backup_lock,
    _replace_policy_remote_prefix,
    _resolve_admin_uploaded_restore_artifact,
    _resolve_private_remote_credentials,
    _resolve_restore_source,
    _restore_execution_allowed,
    _rollback_remote_upload_after_persistence_failure,
    _run_shell_command,
    _snapshot_sidecar_path,
    _stage_admin_restore_upload,
    _upload_to_private_remote,
    _validate_policy_snapshot_internal,
    _validate_verification_inputs,
    _write_json_file,
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

from quickscale_modules_backups.models import BackupPolicy

# ---------------------------------------------------------------------------
# Protocols (reference BackupPolicySnapshot — defined here to avoid circular
# imports with dr_engine which already imports from models)
# ---------------------------------------------------------------------------


class RemoteUploader(Protocol):
    """Protocol used for optional private remote artifact offload."""

    def __call__(self, local_path: Path, policy: BackupPolicySnapshot) -> str: ...


class RemoteDeleter(Protocol):
    """Protocol used for private remote artifact deletion."""

    def __call__(self, remote_key: str, policy: BackupPolicySnapshot) -> None: ...


class StorageBackendSelectionLike(Protocol):
    """Typed shape used from the storage helper module."""

    backend: str
    django_backend: str
    use_s3_compatible: bool
    options: dict[str, Any]


class StorageHelpersModule(Protocol):
    """Typed subset of the storage helper module used by backups."""

    def list_s3_compatible_media_inventory(
        self,
        settings_obj: Any,
    ) -> list[dict[str, Any]]: ...

    def select_storage_backend(
        self,
        settings_obj: Any,
    ) -> StorageBackendSelectionLike: ...


# ---------------------------------------------------------------------------
# Policy helpers (thin Django-facing wrappers)
# ---------------------------------------------------------------------------


def ensure_default_policy() -> BackupPolicy:
    """
    Ensure a default policy row exists for admin-driven workflows.

    Delegates the implementation to ``dr_engine.orchestration``.
    """
    from quickscale_core.runtime import _ensure_default_policy_internal

    return _ensure_default_policy_internal()


def load_policy_snapshot() -> BackupPolicySnapshot:
    """
    Load the active runtime policy snapshot with managed settings precedence.

    Delegates to the engine-owned implementation for model access.
    """
    from quickscale_core.runtime import _load_active_policy_snapshot

    return _load_active_policy_snapshot()


def validate_policy_snapshot(policy: BackupPolicySnapshot) -> list[str]:
    """
    Return human-readable validation issues for a backup policy snapshot.

    Delegates to the engine-owned validation core.
    """
    return _validate_policy_snapshot_internal(policy)
