"""
QuickScale runtime API facade — combined re-export surface.

This is the public import path for generated-project code and module-owned
adapters.  It re-exports all symbols from two sub-modules:

* ``runtime.dr`` — DR adapter functions, primitives, and lazy backup-dependent
  symbols (orchestration, recovery, verification).
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

# Import sub-modules as module objects — no eager ``from ... import *``
# for lazy-loaded DR symbols (orchestration, recovery, verification).
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
    # DR orchestration surface — backups module (lazy-loaded)
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
    "_resolve_admin_uploaded_restore_artifact",
    "_stage_admin_restore_upload",
    "set_backup_snapshot_rollback_pin",
    "sync_backup_snapshot_media",
    "validate_backup_artifact",
    # DR primitives surface
    "BackupConfigurationError",
    "BackupPolicySnapshot",
    "ShellCommandRunner",
    # DR recovery surface — backups module (lazy-loaded)
    "ArtifactLike",
    "BackupRestoreBlocked",
    "RemoteMaterializer",
    "ResolvedRestoreSource",
    "RestoreResult",
    "RestoreSourceResolutionMode",
    "RestoreWarning",
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
    """Include lazy symbols in module dir()."""
    return sorted(__all__)
