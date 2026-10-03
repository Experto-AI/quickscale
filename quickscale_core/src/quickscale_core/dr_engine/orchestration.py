"""DR orchestration — Django-aware backup/snapshot capture, sidecar lifecycle,
report building, prune, media sync, and remote storage operations.

This module is the public import path for DR orchestration and re-exports its
full former surface.  The implementation lives in private sibling modules
grouped by concern: ``_capture``, ``_report``, ``_restore``, ``_prune``,
``_media``, ``_remote``, ``_state``, ``_policy``, ``_metadata``, and
``_types``.  Every name previously bound here stays importable, and every test
patch target on this module path resolves through this facade at call time.
"""

from __future__ import annotations

import hashlib as hashlib
import os as os
import shutil as shutil
import subprocess as subprocess
from collections.abc import Iterator as Iterator, Sequence as Sequence
from contextlib import contextmanager as contextmanager
from copy import deepcopy as deepcopy
from dataclasses import replace as replace
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from importlib import import_module as import_module
from io import StringIO as StringIO
from pathlib import Path as Path
from tempfile import mkdtemp as mkdtemp
from typing import (
    TYPE_CHECKING as TYPE_CHECKING,
    Any as Any,
    Mapping as Mapping,
    Protocol as Protocol,
    cast as cast,
)

import django as django
from django.apps import apps as apps
from django.conf import settings as settings
from django.core.management import call_command as call_command
from django.utils import timezone as django_timezone  # noqa: F401

from quickscale_core.dr_engine.primitives import (  # noqa: F401
    BackupConfigurationError,
    BackupError,
    BackupPolicySnapshot,
    ShellCommandRunner,
    _compute_sha256,
    _database_engine_family,
    _dump_postgresql_database,
    _ENV_VAR_MANIFEST_FILENAME,
    _extract_any_major_version,
    _extract_leading_major_version,
    _get_postgresql_tool_version,
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _mint_snapshot_id,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
)

from quickscale_core.dr_engine.recovery import (  # noqa: F401
    ArtifactLike,
    BackupRestoreBlocked,
    RemoteMaterializer,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
    _collect_artifact_module_versions,
    _collect_local_backup_validation_issues,
    _detect_restore_file_format,
    _execute_restore_for_resolved_source as _core_execute_restore_for_resolved_source,
    _get_restore_compatibility_issues as _core_get_restore_compatibility_issues,
    _resolve_restore_source as _core_resolve_restore_source,
    _restore_execution_allowed as _core_restore_execution_allowed,
)

from quickscale_core.dr_engine.verification import (  # noqa: F401
    _build_clear_rollback_pin_fields,
    _build_verification_payload,
    _compute_rollback_pin_fields,
    _validate_verification_inputs,
)

# AF6 Phase 3 — re-exports from concern-focused sibling modules.

from quickscale_core.dr_engine._lock import (  # noqa: E402, F401
    BackupLockError,
    StagedAdminRestoreUpload,
    _acquire_backup_lock,
    _backup_creation_lock,
    _cleanup_local_backup_file,
    _clear_stale_backup_lock,
    _release_backup_lock,
)

from quickscale_core.dr_engine._paths import (  # noqa: E402, F401
    _build_snapshot_capture_resume_policy,
    _build_snapshot_database_descriptor,
    _build_snapshot_local_root,
    _build_snapshot_lock_directory,
    _build_snapshot_remote_root,
    _get_snapshot_report_children,
    _replace_policy_remote_prefix,
    _snapshot_capture_is_complete,
    _snapshot_sidecar_path,
    _snapshot_uses_private_remote,
    build_backup_filename,
    get_local_backup_directory,
)

from quickscale_core.dr_engine._sidecar import (  # noqa: E402, F401
    _build_env_var_manifest,
    _build_media_sync_manifest,
    _build_promotion_verification_placeholder,
    _capture_snapshot_sidecars,
    _load_snapshot_sidecar_payload,
    _persist_snapshot_sidecar_payload,
)

# SA89b Phase 1 — persistence module-level wrappers replace all direct ORM
# create/save/filter/get/refresh/update operations.

from quickscale_core.dr_engine.persistence import (  # noqa: E402, F401
    create_artifact,
    create_snapshot,
    get_authoritative_snapshot_for_artifact,
    get_backup_snapshot as _get_backup_snapshot_from_persistence,
    iter_expired_snapshots,
    iter_expired_unlinked_artifacts,
    refresh_snapshot,
    resolve_admin_uploaded_restore_artifact,
    save_artifact,
    save_snapshot,
    settings_policy_snapshot,
    update_artifact_after_restore,
)

# SA89b Phase 1 — isolated S3 adapter replaces direct S3Storage usage.

from quickscale_core._dr_remote_storage import (  # noqa: E402, F401
    delete_s3_key,
    upload_file_to_s3,
)

# SA232 — re-exports from the private implementation modules.

from quickscale_core.dr_engine._types import (
    _ROUTE_KIND_KEY as _ROUTE_KIND_KEY,
    _RemoteUploader as _RemoteUploader,
    _RemoteDeleter as _RemoteDeleter,
    _StorageBackendSelectionLike as _StorageBackendSelectionLike,
    _StorageHelpersModule as _StorageHelpersModule,
)

from quickscale_core.dr_engine._metadata import (
    _get_source_environment as _get_source_environment,
    _get_project_slug as _get_project_slug,
    _collect_module_versions as _collect_module_versions,
    _get_git_revision as _get_git_revision,
    _load_storage_helpers as _load_storage_helpers,
    _read_setting_value as _read_setting_value,
    _build_release_metadata as _build_release_metadata,
    _create_database_dump as _create_database_dump,
    _dump_database_as_json as _dump_database_as_json,
    _build_backup_metadata as _build_backup_metadata,
    _get_database_server_version as _get_database_server_version,
    _database_server_version_query as _database_server_version_query,
    _require_postgresql_18_contract as _require_postgresql_18_contract,
    _get_postgresql_18_guidance as _get_postgresql_18_guidance,
)

from quickscale_core.dr_engine._policy import (
    _validate_policy_snapshot_internal as _validate_policy_snapshot_internal,
    _load_active_policy_snapshot as _load_active_policy_snapshot,
    _ensure_default_policy_internal as _ensure_default_policy_internal,
    _build_policy_snapshot_from_model as _build_policy_snapshot_from_model,
)

from quickscale_core.dr_engine._state import (
    _mark_snapshot_failed as _mark_snapshot_failed,
    _mark_remote_upload_failure as _mark_remote_upload_failure,
    _rollback_remote_upload_after_persistence_failure as _rollback_remote_upload_after_persistence_failure,
    _record_prune_failure_without_masking_success as _record_prune_failure_without_masking_success,
    _persist_snapshot_metadata_on_artifact as _persist_snapshot_metadata_on_artifact,
    _clear_appended_artifact_note as _clear_appended_artifact_note,
    _resolve_snapshot_database_local_path as _resolve_snapshot_database_local_path,
    _mark_snapshot_descriptors_deleted as _mark_snapshot_descriptors_deleted,
    _get_authoritative_snapshot_for_artifact as _get_authoritative_snapshot_for_artifact,
    _resolve_artifact_remote_policy as _resolve_artifact_remote_policy,
    get_backup_snapshot as get_backup_snapshot,
)

from quickscale_core.dr_engine._remote import (
    _resolve_private_remote_credentials as _resolve_private_remote_credentials,
    _upload_to_private_remote as _upload_to_private_remote,
    _materialize_private_remote_key as _materialize_private_remote_key,
    _delete_private_remote_key as _delete_private_remote_key,
    _upload_snapshot_child_to_private_remote as _upload_snapshot_child_to_private_remote,
    _delete_snapshot_storage as _delete_snapshot_storage,
)

from quickscale_core.dr_engine._capture import (
    _complete_capture_after_dump as _complete_capture_after_dump,
    _resume_backup_capture as _resume_backup_capture,
    create_backup as create_backup,
)

from quickscale_core.dr_engine._report import (
    _resolve_snapshot_provenance_value as _resolve_snapshot_provenance_value,
    _build_snapshot_full_backup_contract as _build_snapshot_full_backup_contract,
    build_backup_snapshot_report as build_backup_snapshot_report,
    report_backup_snapshot as report_backup_snapshot,
    record_backup_snapshot_verification as record_backup_snapshot_verification,
    validate_backup_artifact as validate_backup_artifact,
    set_backup_snapshot_rollback_pin as set_backup_snapshot_rollback_pin,
    clear_backup_snapshot_rollback_pin as clear_backup_snapshot_rollback_pin,
)

from quickscale_core.dr_engine._prune import (
    delete_artifact_files as delete_artifact_files,
    prune_expired_backups as prune_expired_backups,
    _is_path_within_root as _is_path_within_root,
    _path_uses_symlink_within_root as _path_uses_symlink_within_root,
    _get_authoritative_local_backup_roots as _get_authoritative_local_backup_roots,
    download_backup_path as download_backup_path,
)

from quickscale_core.dr_engine._media import (
    _build_s3_storage_from_selection as _build_s3_storage_from_selection,
    _resolve_media_runtime as _resolve_media_runtime,
    _storage_object_key as _storage_object_key,
    _copy_media_item as _copy_media_item,
    sync_backup_snapshot_media as sync_backup_snapshot_media,
)

from quickscale_core.dr_engine._restore import (
    _get_restore_compatibility_issues as _get_restore_compatibility_issues,
    _resolve_restore_source as _resolve_restore_source,
    _resolve_authoritative_snapshot_dump as _resolve_authoritative_snapshot_dump,
    _ensure_postgresql_18_restore_runtime as _ensure_postgresql_18_restore_runtime,
    _restore_execution_allowed as _restore_execution_allowed,
    _execute_restore_for_resolved_source as _execute_restore_for_resolved_source,
    restore_backup_source as restore_backup_source,
    restore_backup_artifact as restore_backup_artifact,
    _stage_admin_restore_upload as _stage_admin_restore_upload,
    _iter_admin_restore_upload_chunks as _iter_admin_restore_upload_chunks,
    _cleanup_admin_restore_upload_directory as _cleanup_admin_restore_upload_directory,
    _resolve_admin_uploaded_restore_artifact as _resolve_admin_uploaded_restore_artifact,
    _persist_restore_artifact_metadata as _persist_restore_artifact_metadata,
    restore_admin_uploaded_backup as restore_admin_uploaded_backup,
)
