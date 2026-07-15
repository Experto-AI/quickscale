"""
QuickScale runtime API facade — combined re-export surface.

This is the public import path for generated-project code and module-owned
adapters.  It re-exports all symbols from two sub-modules:

* ``runtime.dr`` — DR adapter functions, primitives, and all backup-dependent
  symbols (orchestration, recovery, persistence, verification) via eager
  imports from the ``dr_engine`` sub-packages.
* ``runtime.manifest`` — manifest resolver, assembler, social-manifest path
  constants, renderers, and wiring types.

Module-owned adapters (e.g. ``quickscale_modules_social.adapter``) should
import from ``quickscale_core.runtime.manifest`` directly to avoid pulling
in the DR surface at import time and triggering circular imports.

Backward-compatible: all existing imports from ``quickscale_core.runtime``
continue to work through this combined facade.

``__all__`` is a hardcoded literal (union of both sub-module exports) so
the SA9.2 module-core compatibility checker's static analysis can resolve
all symbols without Python import-time side effects.
"""

from __future__ import annotations

import typing

# Import sub-modules as module objects.  dr symbols are now eagerly imported
# as module-level names in dr.py; runtime.__getattr__ delegates to sub-module
# hasattr/getattr for any non-__all__ private symbols.
from quickscale_core.runtime import dr as _dr  # noqa: F401
from quickscale_core.runtime import manifest as _manifest  # noqa: F401

# ---------------------------------------------------------------------------
# Public API — complete hardcoded literal union of dr.__all__ and
# manifest.__all__.  Kept as a literal so the SA9.2 static-analysis
# checker (check_module_core_compatibility.py) can resolve every
# symbol without importing the sub-modules.
#
# When adding a new public symbol to dr.py or manifest.py, add it
# here too.  The compatibility checker will catch any mismatch.
# ---------------------------------------------------------------------------
__all__ = [
    # DR adapter surface (from dr)
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
    "_cleanup_admin_restore_upload_directory",
    "_get_authoritative_snapshot_for_artifact",
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
    # Module wiring spec (from manifest)
    "ModuleWiringSpec",
    # Manifest/resolver types
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


def __getattr__(name: str) -> typing.Any:
    """Resolve attribute from ``dr`` or ``manifest`` sub-module."""
    if hasattr(_dr, name):
        return getattr(_dr, name)
    if hasattr(_manifest, name):
        return getattr(_manifest, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Return sorted module.__all__ for dir()."""
    return sorted(__all__)
