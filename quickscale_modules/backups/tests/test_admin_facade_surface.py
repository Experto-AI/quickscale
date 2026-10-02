"""Conformance gate: the split backups admin surface keeps its imports.

The admin implementation, restore form, and restore helpers live in private
sibling modules; every name the former ``quickscale_modules_backups.admin``
module exposed at import time must remain importable from the same path, with
identical defining objects, and the download service must stay patchable at
the admin module.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from django.contrib import admin as django_admin

from quickscale_modules_backups import (
    _admin_artifact,
    _admin_forms,
    admin as backups_admin,
    models as backups_models,
    services as backups_services,
)

EXPECTED_MODULE_SURFACE = frozenset(
    {
        "Any",
        "BackupArtifact",
        "BackupArtifactAdmin",
        "BackupError",
        "BackupPolicy",
        "BackupPolicyAdmin",
        "BackupPolicyRestoreForm",
        "BackupRestoreBlocked",
        "BackupSnapshot",
        "FileResponse",
        "HttpRequest",
        "HttpResponse",
        "HttpResponseRedirect",
        "Path",
        "PermissionDenied",
        "RestoreSourceResolutionMode",
        "STALE_RESTORE_THRESHOLD_MINUTES",
        "TemplateResponse",
        "admin",
        "cast",
        "delete_artifact_files",
        "dispatch_background_create",
        "dispatch_background_prune",
        "dispatch_background_restore",
        "download_backup_path",
        "ensure_default_policy",
        "format_html",
        "forms",
        "is_restore_stale",
        "json",
        "messages",
        "path",
        "prepare_admin_uploaded_restore_artifact",
        "reset_stale_restore",
        "restore_admin_uploaded_backup",
        "restore_backup_artifact",
        "reverse",
        "validate_backup_artifact",
    }
)


def test_facade_preserves_former_module_surface() -> None:
    """Every name the former module exposed stays importable from admin."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(dir(backups_admin)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_declares_every_former_public_name() -> None:
    """Every former name stays in ``__all__`` for wildcard consumers."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(backups_admin.__all__))
    assert not missing, f"facade __all__ dropped former public names: {missing}"


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert backups_admin.BackupPolicyRestoreForm is _admin_forms.BackupPolicyRestoreForm
    assert backups_admin.download_backup_path is backups_services.download_backup_path
    assert (
        backups_admin.dispatch_background_create
        is backups_services.dispatch_background_create
    )
    assert (
        backups_admin.dispatch_background_prune
        is backups_services.dispatch_background_prune
    )
    assert (
        backups_admin.dispatch_background_restore
        is backups_services.dispatch_background_restore
    )
    assert (
        backups_admin.restore_backup_artifact
        is backups_services.restore_backup_artifact
    )
    assert (
        backups_admin.restore_admin_uploaded_backup
        is backups_services.restore_admin_uploaded_backup
    )
    assert (
        backups_admin.prepare_admin_uploaded_restore_artifact
        is backups_services.prepare_admin_uploaded_restore_artifact
    )
    assert backups_admin.BackupArtifact is backups_models.BackupArtifact
    assert issubclass(
        backups_admin.BackupArtifactAdmin,
        _admin_artifact.BackupArtifactAdminBase,
    )


def test_download_seam_stays_patchable_from_the_facade() -> None:
    """The download service stays resolvable from the admin module namespace."""
    registered_admin = django_admin.site._registry[backups_models.BackupArtifact]

    ready_artifact = MagicMock()
    ready_artifact.status = backups_models.BackupArtifact.Status.READY
    with patch.object(backups_admin, "download_backup_path") as lookup:
        assert registered_admin._has_downloadable_local_file(ready_artifact) is True
    lookup.assert_called_once_with(ready_artifact)

    deleted_artifact = MagicMock()
    deleted_artifact.status = backups_models.BackupArtifact.Status.DELETED
    with patch.object(backups_admin, "download_backup_path") as lookup:
        assert registered_admin._has_downloadable_local_file(deleted_artifact) is False
    lookup.assert_not_called()


def test_moved_admin_service_lookups_stay_patchable_from_the_facade() -> None:
    """Former admin-module service lookups resolve through the facade hooks."""
    artifact_admin = django_admin.site._registry[backups_models.BackupArtifact]
    policy_admin = django_admin.site._registry[backups_models.BackupPolicy]

    restoring = MagicMock()
    restoring.status = backups_models.BackupArtifact.Status.RESTORING
    restoring.restore_started_at = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    with patch.object(backups_admin, "is_restore_stale", return_value=True) as stale:
        assert "Stale" in artifact_admin.stale_restore_warning(restoring)
        ineligible = policy_admin._get_admin_restore_ineligible_reason(restoring)
        assert ineligible is not None
        assert ineligible.startswith("This backup artifact's restore appears stale")
    assert stale.call_count == 2

    with (
        patch.object(
            backups_admin, "validate_backup_artifact", return_value=[]
        ) as validate,
        patch.object(django_admin.ModelAdmin, "message_user"),
    ):
        artifact_admin.validate_selected_backups(MagicMock(), [MagicMock()])
    validate.assert_called_once()

    with (
        patch.object(backups_admin, "is_restore_stale", return_value=True),
        patch.object(backups_admin, "reset_stale_restore") as reset,
        patch.object(django_admin.ModelAdmin, "message_user"),
    ):
        artifact_admin.reset_stale_restore_action(MagicMock(), [restoring])
    reset.assert_called_once_with(restoring)

    with (
        patch.object(backups_admin, "delete_artifact_files") as delete,
        patch.object(django_admin.ModelAdmin, "delete_queryset"),
    ):
        artifact_admin.delete_queryset(MagicMock(), [MagicMock()])
    delete.assert_called_once()
