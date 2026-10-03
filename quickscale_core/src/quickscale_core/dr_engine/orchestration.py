"""DR orchestration — Django-aware backup/snapshot capture, sidecar lifecycle,
report building, prune, media sync, and remote storage operations.

This module is the public import path for DR orchestration: it re-exports
public names one way from the private sibling modules that define them
(``_capture``, ``_report``, ``_restore``, ``_prune``, ``_media``, ``_remote``,
``_state``, ``_policy``, ``_metadata``, ...).  Collaborators resolve through
the defining module, never through this re-export path
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from quickscale_core.dr_engine.primitives import (  # noqa: F401
    BackupConfigurationError as BackupConfigurationError,
    BackupError as BackupError,
    BackupPolicySnapshot as BackupPolicySnapshot,
    ShellCommandRunner as ShellCommandRunner,
)

from quickscale_core.dr_engine.recovery import (  # noqa: F401
    ArtifactLike as ArtifactLike,
    BackupRestoreBlocked as BackupRestoreBlocked,
    RemoteMaterializer as RemoteMaterializer,
    ResolvedRestoreSource as ResolvedRestoreSource,
    RestoreResult as RestoreResult,
    RestoreSourceResolutionMode as RestoreSourceResolutionMode,
    RestoreWarning as RestoreWarning,
)

from quickscale_core.dr_engine._lock import (  # noqa: F401
    BackupLockError as BackupLockError,
    StagedAdminRestoreUpload as StagedAdminRestoreUpload,
)

from quickscale_core.dr_engine._paths import (  # noqa: F401
    build_backup_filename as build_backup_filename,
    get_local_backup_directory as get_local_backup_directory,
)

from quickscale_core.dr_engine.persistence import (  # noqa: F401
    create_artifact as create_artifact,
    create_snapshot as create_snapshot,
    get_authoritative_snapshot_for_artifact as get_authoritative_snapshot_for_artifact,
    iter_expired_snapshots as iter_expired_snapshots,
    iter_expired_unlinked_artifacts as iter_expired_unlinked_artifacts,
    refresh_snapshot as refresh_snapshot,
    resolve_admin_uploaded_restore_artifact as resolve_admin_uploaded_restore_artifact,
    save_artifact as save_artifact,
    save_snapshot as save_snapshot,
    settings_policy_snapshot as settings_policy_snapshot,
    update_artifact_after_restore as update_artifact_after_restore,
)

from quickscale_core._dr_remote_storage import (  # noqa: F401
    delete_s3_key as delete_s3_key,
    upload_file_to_s3 as upload_file_to_s3,
)

from quickscale_core.dr_engine._state import (  # noqa: F401
    get_backup_snapshot as get_backup_snapshot,
)

from quickscale_core.dr_engine._capture import (  # noqa: F401
    create_backup as create_backup,
)

from quickscale_core.dr_engine._report import (  # noqa: F401
    build_backup_snapshot_report as build_backup_snapshot_report,
    report_backup_snapshot as report_backup_snapshot,
    record_backup_snapshot_verification as record_backup_snapshot_verification,
    validate_backup_artifact as validate_backup_artifact,
    set_backup_snapshot_rollback_pin as set_backup_snapshot_rollback_pin,
    clear_backup_snapshot_rollback_pin as clear_backup_snapshot_rollback_pin,
)

from quickscale_core.dr_engine._prune import (  # noqa: F401
    delete_artifact_files as delete_artifact_files,
    prune_expired_backups as prune_expired_backups,
    download_backup_path as download_backup_path,
)

from quickscale_core.dr_engine._media import (  # noqa: F401
    sync_backup_snapshot_media as sync_backup_snapshot_media,
)

from quickscale_core.dr_engine._restore import (  # noqa: F401
    restore_backup_source as restore_backup_source,
    restore_backup_artifact as restore_backup_artifact,
    restore_admin_uploaded_backup as restore_admin_uploaded_backup,
)
