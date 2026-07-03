"""Thin Django-facing service layer for the QuickScale backups module.

All DR orchestration logic lives in ``quickscale_core.dr_engine.orchestration``.
This module keeps the small set of Django-facing wrappers and shared protocol
types that the backups app still owns locally.

``services.py`` is intentionally under 400 LOC. Every new orchestration
feature should go in ``dr_engine/``, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from quickscale_modules_backups.models import BackupPolicy

from quickscale_core.runtime import (  # noqa: F401
    # orchestration surface
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
    _cleanup_local_backup_file,
    _clear_appended_artifact_note,
    _collect_module_versions,
    _database_server_version_query,
    _delete_private_remote_key,
    _ensure_postgresql_18_restore_runtime,
    _get_git_revision,
    _get_project_slug,
    _get_restore_compatibility_issues,
    _get_source_environment,
    _is_path_within_root,
    _load_snapshot_sidecar_payload,
    _materialize_private_remote_key,
    _path_uses_symlink_within_root,
    _read_setting_value,
    _record_prune_failure_without_masking_success,
    _release_backup_lock,
    _replace_policy_remote_prefix,
    _resolve_private_remote_credentials,
    _resolve_restore_source,
    _restore_execution_allowed,
    _rollback_remote_upload_after_persistence_failure,
    _snapshot_sidecar_path,
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
    # primitives surface
    BackupConfigurationError,
    BackupError,
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
    # recovery surface
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
    # verification surface
    _build_clear_rollback_pin_fields,
    _build_verification_payload,
    _compute_rollback_pin_fields,
    _validate_verification_inputs,
)

# ---------------------------------------------------------------------------
# Protocols (reference BackupPolicySnapshot — defined here to avoid circular
# imports with dr_engine which already imports from models)
# ---------------------------------------------------------------------------


class RemoteUploader(Protocol):
    """Protocol used for optional private remote artifact offload."""

    def __call__(self, local_path: Path, policy: "BackupPolicySnapshot") -> str: ...


class RemoteDeleter(Protocol):
    """Protocol used for private remote artifact deletion."""

    def __call__(self, remote_key: str, policy: "BackupPolicySnapshot") -> None: ...


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
    """Ensure a default policy row exists for admin-driven workflows.

    Delegates the implementation to ``dr_engine.orchestration``.
    """
    from quickscale_core.runtime import _ensure_default_policy_internal

    return _ensure_default_policy_internal()


def load_policy_snapshot() -> BackupPolicySnapshot:
    """Load the active runtime policy snapshot with managed settings precedence.

    Delegates to the engine-owned implementation for model access.
    """
    from quickscale_core.runtime import _load_active_policy_snapshot

    return _load_active_policy_snapshot()


def validate_policy_snapshot(policy: BackupPolicySnapshot) -> list[str]:
    """Return human-readable validation issues for a backup policy snapshot.

    Delegates to the engine-owned validation core.
    """
    return _validate_policy_snapshot_internal(policy)
