"""
Django-facing service layer for the QuickScale backups module.

Model-touching lifecycle dispatch (restore claiming, background
backup-create and pruning invocations) and admin-facing wrappers
live here. Engine-pure orchestration logic belongs in
``quickscale_core.dr_engine``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import mkdtemp
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

from django.utils import timezone as django_timezone

from quickscale_modules_backups.models import BackupArtifact, BackupPolicy

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


# ---------------------------------------------------------------------------
# SA43 / SA20 — Async restore dispatch lifecycle
# ---------------------------------------------------------------------------

_ARTIFACT_RESTORE_CLAIMABLE_STATUSES: frozenset[str] = frozenset(
    {
        BackupArtifact.STATUS_READY,
        BackupArtifact.STATUS_VALIDATED,
        BackupArtifact.STATUS_FAILED,
        BackupArtifact.STATUS_RESTORED,
    }
)
"""Pre-claim statuses eligible for an atomic restore claim.

Excludes STATUS_DELETED (terminal — never restorable) and
STATUS_RESTORING (already claimed by another request).
"""


def _atomic_claim_restore(artifact: BackupArtifact) -> bool:
    """Atomically claim *artifact* for restore via DB compare-and-swap.

    Uses a single filtered ``update()`` to transition the artifact from an
    eligible pre-claim status to ``STATUS_RESTORING``.  Only the caller that
    wins the race sees ``updated > 0``; losers re-read the artifact and
    return ``False``.

    After a successful claim the in-memory *artifact* is refreshed from the
    database so its attributes reflect ``STATUS_RESTORING`` /
    ``restore_started_at`` / ``restore_error``.  After a failed claim the
    in-memory *artifact* is also refreshed so the caller can inspect the
    current status to surface an appropriate reason.

    Callers **must** snapshot ``artifact.status``, ``restore_started_at``,
    and ``restore_error`` *before* calling this function if they need to
    roll back on a subsequent spawn failure.
    """
    now = django_timezone.now()
    updated = BackupArtifact.objects.filter(
        pk=artifact.pk,
        status__in=_ARTIFACT_RESTORE_CLAIMABLE_STATUSES,
    ).update(
        status=BackupArtifact.STATUS_RESTORING,
        restore_started_at=now,
        restore_error="",
        updated_at=now,
    )
    artifact.refresh_from_db()
    return updated > 0


def _get_manage_py() -> str:
    """Return the path to manage.py for subprocess management-command dispatch.

    Raises
    ------
    BackupError
        When neither ``sys.argv[0]`` nor ``settings.BASE_DIR / manage.py``
        resolves to an existing file.
    """
    script = Path(sys.argv[0])
    if script.name == "manage.py" and script.exists():
        return str(script)
    try:
        from django.conf import settings

        base = Path(settings.BASE_DIR)
        candidate = base / "manage.py"
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    raise BackupError("manage.py could not be resolved")


def prepare_admin_uploaded_restore_artifact(
    uploaded_file: Any,
    confirmation: str,
) -> BackupArtifact:
    """Stage, resolve, materialize, and persist an admin-uploaded restore artifact.

    Safely copies an uploaded backup file to the authoritative backup
    directory, resolves it to a trusted ``BackupArtifact``, and persists
    the local path on that artifact.  The returned artifact is ready for
    ``dispatch_background_restore``.

    Parameters
    ----------
    uploaded_file :
        The uploaded file from the admin form (Django ``UploadedFile``).
    confirmation :
        Exact artifact filename that the operator re-typed.

    Returns
    -------
    BackupArtifact
        The trusted artifact with ``local_path`` persisted to the
        authoritative backup directory.

    Raises
    ------
    BackupRestoreBlocked
        When the resolved artifact is already ``STATUS_RESTORING``, or
        the confirmation does not match the artifact filename.
    BackupError
        When the uploaded file does not resolve to a trusted artifact
        (no match, ambiguous match, or incomplete snapshot contract).
    """
    staging_directory = Path(mkdtemp(prefix="quickscale-backups-admin-upload-"))
    try:
        staged_upload = _stage_admin_restore_upload(
            uploaded_file,
            staging_directory=staging_directory,
        )
        trusted_artifact = _resolve_admin_uploaded_restore_artifact(
            checksum_sha256=staged_upload.checksum_sha256,
            size_bytes=staged_upload.size_bytes,
        )
    except Exception:
        _cleanup_admin_restore_upload_directory(staging_directory)
        raise

    # CR-SA20-REV-001: Reject already-restoring artifacts with parity to
    # the recorded-artifact branch.  CR-SA38-001: stale-aware — a stale
    # STATUS_RESTORING artifact surfaces the same recovery guidance as
    # _get_admin_restore_ineligible_reason rather than a permanent block.
    if trusted_artifact.status == BackupArtifact.STATUS_RESTORING:
        _cleanup_admin_restore_upload_directory(staging_directory)
        if is_restore_stale(trusted_artifact):
            raise BackupRestoreBlocked(
                "This backup artifact's restore appears stale "
                f"(started at {trusted_artifact.restore_started_at:%Y-%m-%d %H:%M:%S} UTC) — "
                "the child process likely died. Reset the artifact status "
                "from the BackupArtifact admin list to retry."
            )
        raise BackupRestoreBlocked(
            "This backup artifact is currently being "
            "restored. Wait for the restore to "
            "complete before retrying."
        )

    confirm_value = confirmation.strip()
    if confirm_value != trusted_artifact.filename:
        _cleanup_admin_restore_upload_directory(staging_directory)
        raise BackupRestoreBlocked(
            "Confirmation must exactly match the backup filename."
        )

    # CR-SA20-005: Always remap to a trusted path under
    # get_local_backup_directory().  Ignore any unsafe persisted
    # local_path — persist only after a successful copy.
    policy_snapshot = load_policy_snapshot()
    local_dir = get_local_backup_directory(policy_snapshot)
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / trusted_artifact.filename

    # Skip the copy when the staged upload is already at the
    # target path (same file from testing or inline materialization).
    if staged_upload.local_path.resolve() != local_path.resolve():
        local_path.unlink(missing_ok=True)
        shutil.copy2(staged_upload.local_path, local_path)

    _cleanup_admin_restore_upload_directory(staging_directory)

    # Persist local_path only after successful copy so a failed copy
    # does not leave a dangling path on the artifact.
    trusted_artifact.local_path = str(local_path)
    trusted_artifact.save(update_fields=["local_path", "updated_at"])

    return trusted_artifact


def dispatch_background_restore(
    artifact: BackupArtifact,
    *,
    confirmation: str,
) -> None:
    """Persist STATUS_RESTORING, then dispatch ``backups_restore`` via Popen.

    Parameters
    ----------
    artifact :
        The backup artifact to restore.  Must be in a claimable status
        (READY / VALIDATED / FAILED / RESTORED).
    confirmation :
        Exact artifact filename to pass as ``--confirm`` to the management
        command.

    Raises
    ------
    BackupRestoreBlocked
        When the artifact cannot be claimed for restore (already claimed
        by another request, or deleted between eligibility check and claim).
    """
    manage_py = _get_manage_py()

    # CR-SA20-007: Snapshot pre-spawn state so that a spawn failure can
    # roll back cleanly, preserving prior restore_started_at and
    # restore_error on retry from FAILED / RESTORED.
    pre_spawn_status = artifact.status
    pre_spawn_restore_started_at = artifact.restore_started_at
    pre_spawn_restore_error = artifact.restore_error

    # CR-SA20-REV-002: Atomic compare-and-swap — concurrent submissions
    # for the same artifact cannot both dispatch Popen.
    if not _atomic_claim_restore(artifact):
        if artifact.status == BackupArtifact.STATUS_DELETED:
            raise BackupRestoreBlocked(
                "Deleted backup artifacts cannot be restored from admin."
            )
        raise BackupRestoreBlocked(
            "This backup artifact is currently being "
            "restored. Wait for the restore to "
            "complete before retrying."
        )

    try:
        subprocess.Popen(
            [
                sys.executable,
                manage_py,
                "backups_restore",
                str(artifact.pk),
                "--confirm",
                confirmation,
                "--local-only",
            ],
            close_fds=True,
        )
    except Exception:
        # Rollback: restore pre-spawn status/metadata so a spawn failure
        # never strands the artifact in STATUS_RESTORING or loses prior
        # failure metadata on retry.
        artifact.status = pre_spawn_status
        artifact.restore_started_at = pre_spawn_restore_started_at
        artifact.restore_error = pre_spawn_restore_error
        artifact.save(
            update_fields=[
                "status",
                "restore_started_at",
                "restore_error",
                "updated_at",
            ]
        )
        raise


# ---------------------------------------------------------------------------
# SA37 — Async create/prune dispatch lifecycle
# ---------------------------------------------------------------------------


def dispatch_background_create(
    *,
    trigger: str = "admin",
) -> None:
    """Dispatch ``backups_create`` via subprocess, returning immediately.

    Spawns the ``backups_create`` management command in a background
    subprocess so the admin request returns without blocking on
    ``pg_dump`` or optional S3 upload.

    Parameters
    ----------
    trigger :
        Provenance to pass as ``--trigger <value>``.  Preserves
        backward-compatible ``--scheduled`` for the scheduled path.

    Raises
    ------
    BackupError
        When ``subprocess.Popen`` itself fails (not a command error).
    """
    manage_py = _get_manage_py()
    argv = [sys.executable, manage_py, "backups_create"]
    if trigger == "scheduled":
        argv.append("--scheduled")
    elif trigger != "manual":
        # CR-SA37-001: pass non-default triggers (e.g. "admin") as
        # --trigger so the management command preserves provenance.
        argv.extend(["--trigger", trigger])

    try:
        subprocess.Popen(argv, close_fds=True)
    except Exception as exc:
        raise BackupError(
            f"Failed to dispatch background backup creation: {exc}"
        ) from exc


def dispatch_background_prune() -> None:
    """Dispatch ``backups_prune`` via subprocess, returning immediately.

    Spawns the ``backups_prune`` management command in a background
    subprocess so the admin request returns without blocking on
    file deletion or remote cleanup.

    Raises
    ------
    BackupError
        When ``subprocess.Popen`` itself fails (not a command error).
    """
    manage_py = _get_manage_py()
    try:
        subprocess.Popen(
            [sys.executable, manage_py, "backups_prune"],
            close_fds=True,
        )
    except Exception as exc:
        raise BackupError(
            f"Failed to dispatch background backup pruning: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# SA38 — Stale restore detection and guarded reset
# ---------------------------------------------------------------------------

STALE_RESTORE_THRESHOLD_MINUTES: int = 30
"""Threshold beyond which a STATUS_RESTORING artifact is considered stale.

A killed restore child (OOM, redeploy) can strand STATUS_RESTORING
indefinitely because the child only sets STATUS_FAILED on Python
exceptions, never on SIGKILL.  This constant defines the staleness
boundary so operators can reset stranded artifacts without manual
DB edits.
"""


def is_restore_stale(artifact: BackupArtifact) -> bool:
    """Return whether a ``STATUS_RESTORING`` artifact exceeds the stale threshold.

    Parameters
    ----------
    artifact :
        The backup artifact to check.  Only ``STATUS_RESTORING`` artifacts
        with a non-None ``restore_started_at`` older than 30 minutes are
        considered stale.

    Returns
    -------
    bool
        ``True`` when the artifact is stale and eligible for reset.
    """
    if artifact.status != BackupArtifact.STATUS_RESTORING:
        return False
    if artifact.restore_started_at is None:
        return False
    threshold = django_timezone.now() - timedelta(
        minutes=STALE_RESTORE_THRESHOLD_MINUTES
    )
    return artifact.restore_started_at < threshold


def reset_stale_restore(artifact: BackupArtifact) -> None:
    """Reset a stranded ``STATUS_RESTORING`` artifact to ``STATUS_FAILED``.

    Uses a database-level compare-and-swap (CAS) so a concurrently
    finishing child process never has its terminal status overwritten.
    Only resets artifacts whose ``restore_started_at`` exceeds the stale
    threshold (30 minutes).  Non-stale ``STATUS_RESTORING`` artifacts and
    artifacts not in ``STATUS_RESTORING`` are rejected with
    ``BackupRestoreBlocked``.

    After a successful reset the in-memory *artifact* is refreshed from
    the database.  After a failed CAS the in-memory *artifact* is also
    refreshed so the caller can inspect the current status.

    Parameters
    ----------
    artifact :
        The backup artifact to reset.

    Raises
    ------
    BackupRestoreBlocked
        When the artifact is not ``STATUS_RESTORING``, or when the restore
        is still within the stale threshold.
    """
    # Early guard: reject non-RESTORING artifacts immediately so the
    # restore_error format string below never receives None
    # restore_started_at.
    if artifact.status != BackupArtifact.STATUS_RESTORING:
        artifact.refresh_from_db()
        raise BackupRestoreBlocked(
            "Only backup artifacts with status 'Restoring...' can be reset."
        )

    threshold = django_timezone.now() - timedelta(
        minutes=STALE_RESTORE_THRESHOLD_MINUTES
    )
    now = django_timezone.now()
    updated = BackupArtifact.objects.filter(
        pk=artifact.pk,
        status=BackupArtifact.STATUS_RESTORING,
        restore_started_at__lt=threshold,
    ).update(
        status=BackupArtifact.STATUS_FAILED,
        restore_error=(
            "Restore reset: the child process likely died or was killed. "
            f"Artifact was stranded in STATUS_RESTORING since "
            f"{artifact.restore_started_at:%Y-%m-%d %H:%M:%S} UTC."
        ),
        updated_at=now,
    )
    artifact.refresh_from_db()
    if updated == 0:
        if artifact.status != BackupArtifact.STATUS_RESTORING:
            raise BackupRestoreBlocked(
                "Only backup artifacts with status 'Restoring...' can be reset."
            )
        raise BackupRestoreBlocked(
            "This backup artifact's restore is still in progress — "
            "restore_started_at is within the 30-minute stale threshold."
        )
